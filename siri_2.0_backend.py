"""
JARVIS 2.0 - Backend con agente, memoria persistente y recordatorios proactivos
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import json
import os
import sqlite3
from datetime import datetime, date
from dotenv import load_dotenv
import anthropic
import openai
from elevenlabs.client import ElevenLabs
import base64
import tempfile
from typing import Optional
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from rag import retrieve_context

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
TIMEZONE = os.getenv("TIMEZONE", "Europe/Madrid")

client_anthropic = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
client_openai = openai.OpenAI(api_key=OPENAI_API_KEY)
client_elevenlabs = ElevenLabs(api_key=ELEVENLABS_API_KEY)

# ── DATABASE ──────────────────────────────────────────────────────────────────

DB_PATH = "jarvis_memory.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            remind_at DATETIME NOT NULL,
            notified INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            due_date DATE,
            completed INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            content TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ── TOOL DEFINITIONS ──────────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "save_reminder",
        "description": "Guarda un recordatorio con fecha y hora exacta. JARVIS avisará proactivamente cuando llegue ese momento, sin que el usuario tenga que preguntar.",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Qué recordar"},
                "remind_at": {"type": "string", "description": "Fecha y hora en formato ISO 8601 (YYYY-MM-DDTHH:MM:SS)"}
            },
            "required": ["text", "remind_at"]
        }
    },
    {
        "name": "save_task",
        "description": "Guarda una tarea pendiente, con fecha límite opcional.",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Descripción de la tarea"},
                "due_date": {"type": "string", "description": "Fecha límite en formato YYYY-MM-DD (opcional)"}
            },
            "required": ["text"]
        }
    },
    {
        "name": "get_today_pending",
        "description": "Obtiene todas las tareas pendientes y recordatorios de hoy y próximos. Usar cuando el usuario pregunta qué tiene pendiente.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "complete_task",
        "description": "Marca una tarea como completada.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "integer", "description": "ID de la tarea"}
            },
            "required": ["task_id"]
        }
    },
    {
        "name": "save_note",
        "description": "Guarda una nota o información importante para consultar más tarde.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Título de la nota (opcional)"},
                "content": {"type": "string", "description": "Contenido de la nota"}
            },
            "required": ["content"]
        }
    },
    {
        "name": "search_notes",
        "description": "Busca en las notas guardadas.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Término a buscar en notas"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "delete_reminder",
        "description": "Cancela un recordatorio pendiente.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reminder_id": {"type": "integer", "description": "ID del recordatorio a cancelar"}
            },
            "required": ["reminder_id"]
        }
    }
]

# ── TOOL EXECUTORS ────────────────────────────────────────────────────────────

def execute_tool(name: str, inputs: dict) -> dict:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    try:
        if name == "save_reminder":
            c.execute(
                "INSERT INTO reminders (text, remind_at) VALUES (?, ?)",
                (inputs["text"], inputs["remind_at"])
            )
            conn.commit()
            return {"success": True, "id": c.lastrowid, "remind_at": inputs["remind_at"]}

        elif name == "save_task":
            c.execute(
                "INSERT INTO tasks (text, due_date) VALUES (?, ?)",
                (inputs["text"], inputs.get("due_date"))
            )
            conn.commit()
            return {"success": True, "task_id": c.lastrowid}

        elif name == "get_today_pending":
            today = date.today().isoformat()
            c.execute("""
                SELECT id, text, due_date FROM tasks
                WHERE completed = 0 AND (due_date IS NULL OR due_date <= ?)
                ORDER BY due_date ASC NULLS LAST
            """, (today,))
            tasks = [dict(r) for r in c.fetchall()]

            c.execute("""
                SELECT id, text, remind_at FROM reminders
                WHERE notified = 0
                ORDER BY remind_at ASC
            """)
            reminders = [dict(r) for r in c.fetchall()]
            return {"tasks": tasks, "reminders": reminders}

        elif name == "complete_task":
            c.execute("UPDATE tasks SET completed = 1 WHERE id = ?", (inputs["task_id"],))
            conn.commit()
            return {"success": True}

        elif name == "save_note":
            c.execute(
                "INSERT INTO notes (title, content) VALUES (?, ?)",
                (inputs.get("title"), inputs["content"])
            )
            conn.commit()
            return {"success": True, "note_id": c.lastrowid}

        elif name == "search_notes":
            q = f"%{inputs['query']}%"
            c.execute("""
                SELECT id, title, content, created_at FROM notes
                WHERE title LIKE ? OR content LIKE ?
                ORDER BY created_at DESC LIMIT 5
            """, (q, q))
            return {"notes": [dict(r) for r in c.fetchall()]}

        elif name == "delete_reminder":
            c.execute("DELETE FROM reminders WHERE id = ? AND notified = 0", (inputs["reminder_id"],))
            conn.commit()
            deleted = c.rowcount > 0
            return {"success": deleted}

        else:
            return {"error": f"Herramienta desconocida: {name}"}

    except Exception as e:
        logger.error(f"Error en tool {name}: {e}")
        return {"error": str(e)}
    finally:
        conn.close()

# ── FASTAPI + WEBSOCKET ───────────────────────────────────────────────────────

app = FastAPI(title="JARVIS 2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for conn in self.active_connections:
            try:
                await conn.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcast: {e}")

manager = ConnectionManager()

# ── AGENT LOOP ────────────────────────────────────────────────────────────────

conversation_history = []
MAX_HISTORY = 20

def add_to_history(role: str, content: str):
    conversation_history.append({"role": role, "content": content})
    if len(conversation_history) > MAX_HISTORY:
        conversation_history.pop(0)

async def run_agent(user_input: str) -> str:
    messages = [*conversation_history[-10:], {"role": "user", "content": user_input}]

    system_prompt = (
        f"Eres JARVIS, asistente IA personal. Responde siempre en español, de forma concisa y profesional. "
        f"Fecha y hora actual: {datetime.now().strftime('%A %d de %B de %Y, %H:%M')}. "
        "Usa las herramientas disponibles cuando el usuario quiera guardar tareas, recordatorios o notas, "
        "o cuando pregunte qué tiene pendiente. Confirma las acciones brevemente. Máximo 2-3 oraciones."
    )

    context = retrieve_context(client_openai, user_input)
    if context:
        system_prompt += (
            "\n\nUsa la siguiente información de los documentos del usuario para responder si es relevante "
            "a la pregunta. Si no tiene relación, ignórala y responde con tu conocimiento general.\n\n"
            f"{context}"
        )

    while True:
        response = client_anthropic.messages.create(
            model="claude-opus-4-5",
            max_tokens=500,
            system=system_prompt,
            tools=TOOLS,
            messages=messages
        )

        if response.stop_reason == "end_turn":
            text = next((b.text for b in response.content if hasattr(b, "text")), "")
            add_to_history("user", user_input)
            add_to_history("assistant", text)
            return text

        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                logger.info(f"Tool: {block.name} → {block.input}")
                result = execute_tool(block.name, block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result, ensure_ascii=False)
                })

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

# ── TTS ───────────────────────────────────────────────────────────────────────

async def text_to_speech(text: str) -> Optional[bytes]:
    try:
        audio_stream = client_elevenlabs.generate(
            text=text,
            voice="George",
            model="eleven_multilingual_v2",
            stream=False
        )
        return b"".join(audio_stream)
    except Exception as e:
        logger.error(f"ElevenLabs TTS error: {e}")

    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.setProperty('rate', 150)
        engine.setProperty('volume', 1.0)
        engine.setProperty('voice', 'spanish')
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
            tmp_path = tmp.name
        engine.save_to_file(text, tmp_path)
        engine.runAndWait()
        with open(tmp_path, 'rb') as f:
            return f.read()
    except Exception as e:
        logger.error(f"pyttsx3 fallback error: {e}")
        return None

# ── PROACTIVE SCHEDULER ───────────────────────────────────────────────────────

async def check_reminders():
    """Revisa cada 30 segundos si hay recordatorios que disparar."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute(
        "SELECT id, text FROM reminders WHERE remind_at <= ? AND notified = 0",
        (now,)
    )
    due = c.fetchall()
    for rid, text in due:
        c.execute("UPDATE reminders SET notified = 1 WHERE id = ?", (rid,))
        notification = f"Recordatorio: {text}"
        logger.info(f"Disparando: {notification}")
        audio_bytes = await text_to_speech(notification)
        await manager.broadcast({
            "type": "proactive_reminder",
            "text": notification,
            "audio": base64.b64encode(audio_bytes).decode() if audio_bytes else None,
            "audio_type": "audio/mp3"
        })
    conn.commit()
    conn.close()

scheduler = AsyncIOScheduler(timezone=TIMEZONE)

@app.on_event("startup")
async def startup():
    scheduler.add_job(check_reminders, "interval", seconds=30)
    scheduler.start()
    logger.info("Scheduler iniciado — revisando recordatorios cada 30s")

@app.on_event("shutdown")
async def shutdown():
    scheduler.shutdown()

# ── WEBSOCKET ENDPOINT ────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    logger.info("Cliente conectado")
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if message.get("type") == "audio":
                user_text = message.get("text", "").strip()
                if not user_text:
                    continue
                await websocket.send_json({"type": "status", "status": "processing"})
                try:
                    ai_response = await run_agent(user_text)
                    audio_bytes = await text_to_speech(ai_response)
                    await websocket.send_json({
                        "type": "response",
                        "text": ai_response,
                        "audio": base64.b64encode(audio_bytes).decode() if audio_bytes else None,
                        "audio_type": "audio/mp3"
                    })
                except Exception as e:
                    logger.error(f"Agent error: {e}")
                    await websocket.send_json({"type": "error", "message": str(e)})
                await websocket.send_json({"type": "status", "status": "ready"})

            elif message.get("type") == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WS error: {e}")
        manager.disconnect(websocket)

# ── REST ENDPOINTS ────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "online", "service": "JARVIS 2.0"}

@app.get("/api/tasks")
async def get_tasks():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM tasks WHERE completed = 0 ORDER BY due_date ASC")
    tasks = [dict(r) for r in c.fetchall()]
    conn.close()
    return {"tasks": tasks}

@app.get("/api/reminders")
async def get_reminders():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM reminders WHERE notified = 0 ORDER BY remind_at ASC")
    reminders = [dict(r) for r in c.fetchall()]
    conn.close()
    return {"reminders": reminders}

if __name__ == "__main__":
    import uvicorn
    print("""
    ╔══════════════════════════════════════╗
    ║       JARVIS 2.0 — Agente IA        ║
    ║  WebSocket: ws://localhost:8000/ws  ║
    ║  API:       http://localhost:8000   ║
    ╚══════════════════════════════════════╝
    """)
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)

"""
JARVIS 2.0 - Backend con agente, memoria persistente y recordatorios proactivos
"""

from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
import json
import os
import re
import sqlite3
from datetime import datetime, date
from dotenv import load_dotenv
import anthropic
import openai
from elevenlabs import VoiceSettings
from elevenlabs.client import ElevenLabs
import base64
import tempfile
from typing import AsyncIterator, Optional
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from rag import retrieve_context
import car
import weather

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")  # voz premade "George"
# eleven_flash_v2_5 es el de menor latencia; eleven_multilingual_v2 suena algo mejor pero tarda más.
ELEVENLABS_MODEL_ID = os.getenv("ELEVENLABS_MODEL_ID", "eleven_flash_v2_5")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-5")
OWNER_NAME = os.getenv("OWNER_NAME", "Nacho")
TIMEZONE = os.getenv("TIMEZONE", "Europe/Madrid")
JARVIS_API_TOKEN = os.getenv("JARVIS_API_TOKEN")

HOME_LAT = os.getenv("HOME_LAT")
HOME_LON = os.getenv("HOME_LON")

MERCEDES_CLIENT_ID = os.getenv("MERCEDES_CLIENT_ID")
MERCEDES_CLIENT_SECRET = os.getenv("MERCEDES_CLIENT_SECRET")
MERCEDES_REFRESH_TOKEN = os.getenv("MERCEDES_REFRESH_TOKEN")
MERCEDES_VIN = os.getenv("MERCEDES_VIN")
MERCEDES_CONFIGURED = all(
    [MERCEDES_CLIENT_ID, MERCEDES_CLIENT_SECRET, MERCEDES_REFRESH_TOKEN, MERCEDES_VIN]
)

client_anthropic = anthropic.AsyncAnthropic(api_key=CLAUDE_API_KEY)
client_openai = openai.OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
client_elevenlabs = ElevenLabs(api_key=ELEVENLABS_API_KEY)


def require_token(authorization: Optional[str] = Header(None)) -> None:
    """Protege los endpoints REST que quedan expuestos a internet (Atajos de Siri, etc.)."""
    if not JARVIS_API_TOKEN:
        logger.warning("JARVIS_API_TOKEN no configurado — endpoint sin protección.")
        return
    expected = f"Bearer {JARVIS_API_TOKEN}"
    if not authorization or authorization != expected:
        raise HTTPException(status_code=401, detail="Token inválido o ausente")

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
    c.execute("""
        CREATE TABLE IF NOT EXISTS preferences (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
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
    },
    {
        "name": "remember_preference",
        "description": "Recuerda de forma permanente una preferencia o dato personal estable del usuario (p. ej. 'café': 'solo, sin azúcar'). Si la clave ya existe, se actualiza. Lo que guardes aquí lo sabrás en todas las conversaciones futuras.",
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Tema corto, p. ej. 'café', 'equipo de fútbol', 'pareja'"},
                "value": {"type": "string", "description": "El dato a recordar"}
            },
            "required": ["key", "value"]
        }
    },
    {
        "name": "forget_preference",
        "description": "Olvida una preferencia guardada cuando el usuario lo pide o deja de ser cierta.",
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Clave de la preferencia a olvidar"}
            },
            "required": ["key"]
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

        elif name == "remember_preference":
            c.execute(
                "INSERT INTO preferences (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP",
                (inputs["key"].strip().lower(), inputs["value"])
            )
            conn.commit()
            return {"success": True}

        elif name == "forget_preference":
            c.execute("DELETE FROM preferences WHERE key = ?", (inputs["key"].strip().lower(),))
            conn.commit()
            return {"success": c.rowcount > 0}

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

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

# Corta en fin de frase para poder empezar a hablar antes de tener la respuesta entera.
SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")


def load_preferences() -> list[tuple[str, str]]:
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT key, value FROM preferences ORDER BY key").fetchall()
    conn.close()
    return rows


def build_system_prompt(user_input: str) -> str:
    now = datetime.now()
    fecha = f"{DIAS[now.weekday()]} {now.day} de {MESES[now.month - 1]} de {now.year}, {now:%H:%M}"

    prompt = (
        f"Eres JARVIS, el asistente personal de {OWNER_NAME}. Hablas español de España con un tono "
        "sereno, elegante y un punto de ironía británica, como un mayordomo brillante y leal. "
        "Todo lo que dices se lee en voz alta, a menudo mientras conduce: responde en una a tres "
        "frases cortas, sin listas, sin markdown y sin emojis. Ve al grano, con ingenio cuando encaje, "
        f"y llámale {OWNER_NAME} de vez en cuando, sin abusar. "
        "Nunca inventes datos sobre su agenda, su coche, su correo o sus cosas: si no tienes el dato, "
        "dilo con naturalidad. "
        "Usa las herramientas cuando quiera guardar tareas, recordatorios o notas, o pregunte qué "
        "tiene pendiente, y confirma las acciones en pocas palabras. "
        "Cuando te cuente una preferencia o un dato personal estable (cómo le gusta el café, su "
        "equipo, nombres de gente cercana, rutinas), guárdalo con remember_preference sin preguntar.\n\n"
        f"Ahora es {fecha}."
    )

    preferences = load_preferences()
    if preferences:
        prompt += f"\n\nLo que ya sabes de {OWNER_NAME}:\n" + "\n".join(
            f"- {key}: {value}" for key, value in preferences
        )

    context = retrieve_context(client_openai, user_input) if client_openai else ""
    if context:
        prompt += (
            "\n\nUsa la siguiente información de sus documentos si es relevante para la pregunta. "
            "Si no tiene relación, ignórala.\n\n"
            f"{context}"
        )
    return prompt


async def stream_agent(user_input: str) -> AsyncIterator[str]:
    """Genera la respuesta frase a frase según llega de Claude, ejecutando las
    herramientas que pida por el camino."""
    messages = [*conversation_history[-10:], {"role": "user", "content": user_input}]
    system_prompt = build_system_prompt(user_input)
    spoken = []

    while True:
        buffer = ""
        async with client_anthropic.messages.stream(
            model=CLAUDE_MODEL,
            max_tokens=500,
            system=system_prompt,
            tools=TOOLS,
            messages=messages,
        ) as stream:
            async for delta in stream.text_stream:
                buffer += delta
                *sentences, buffer = SENTENCE_END.split(buffer)
                for sentence in sentences:
                    if sentence.strip():
                        spoken.append(sentence.strip())
                        yield sentence.strip()
            final = await stream.get_final_message()

        if buffer.strip():
            spoken.append(buffer.strip())
            yield buffer.strip()

        if final.stop_reason != "tool_use":
            break

        assistant_content = []
        tool_results = []
        for block in final.content:
            if block.type == "text":
                assistant_content.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                assistant_content.append(
                    {"type": "tool_use", "id": block.id, "name": block.name, "input": block.input}
                )
                logger.info(f"Tool: {block.name} → {block.input}")
                result = execute_tool(block.name, block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result, ensure_ascii=False),
                })

        messages.append({"role": "assistant", "content": assistant_content})
        messages.append({"role": "user", "content": tool_results})

    add_to_history("user", user_input)
    add_to_history("assistant", " ".join(spoken))


async def run_agent(user_input: str) -> str:
    return " ".join([sentence async for sentence in stream_agent(user_input)])

# ── TTS ───────────────────────────────────────────────────────────────────────

# Voz serena y estable, tipo mayordomo: poca variación, algo de estilo.
VOICE_SETTINGS = VoiceSettings(stability=0.6, similarity_boost=0.8, style=0.25, use_speaker_boost=True)


async def text_to_speech(text: str) -> Optional[bytes]:
    # Las llamadas de TTS son bloqueantes: en un hilo aparte para poder
    # sintetizar una frase mientras Claude sigue generando la siguiente.
    return await asyncio.to_thread(_text_to_speech_sync, text)


def _text_to_speech_sync(text: str) -> Optional[bytes]:
    try:
        audio_stream = client_elevenlabs.text_to_speech.convert(
            ELEVENLABS_VOICE_ID,
            text=text,
            model_id=ELEVENLABS_MODEL_ID,
            voice_settings=VOICE_SETTINGS,
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

async def stream_response(websocket: WebSocket, user_text: str):
    """Manda cada frase con su audio en cuanto está lista. La síntesis de cada
    frase arranca mientras Claude sigue escribiendo la siguiente, y se envían
    en orden para que el cliente las reproduzca seguidas."""
    queue: asyncio.Queue = asyncio.Queue()

    async def produce():
        try:
            async for sentence in stream_agent(user_text):
                await queue.put((sentence, asyncio.create_task(text_to_speech(sentence))))
        finally:
            await queue.put(None)

    producer = asyncio.create_task(produce())
    while (item := await queue.get()) is not None:
        sentence, tts_task = item
        audio_bytes = await tts_task
        await websocket.send_json({
            "type": "response_chunk",
            "text": sentence,
            "audio": base64.b64encode(audio_bytes).decode() if audio_bytes else None,
            "audio_type": "audio/mp3",
        })
    await producer
    await websocket.send_json({"type": "response_done"})


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    if JARVIS_API_TOKEN and websocket.query_params.get("token") != JARVIS_API_TOKEN:
        await websocket.close(code=1008)
        return
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
                    await stream_response(websocket, user_text)
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

class AskRequest(BaseModel):
    text: str


@app.get("/health")
async def health():
    return {"status": "online", "service": "JARVIS 2.0"}

@app.get("/api/tasks", dependencies=[Depends(require_token)])
async def get_tasks():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM tasks WHERE completed = 0 ORDER BY due_date ASC")
    tasks = [dict(r) for r in c.fetchall()]
    conn.close()
    return {"tasks": tasks}

@app.get("/api/reminders", dependencies=[Depends(require_token)])
async def get_reminders():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM reminders WHERE notified = 0 ORDER BY remind_at ASC")
    reminders = [dict(r) for r in c.fetchall()]
    conn.close()
    return {"reminders": reminders}

# ── ATAJOS DE SIRI ────────────────────────────────────────────────────────────

@app.post("/api/ask", dependencies=[Depends(require_token)])
async def ask(request: AskRequest):
    """Para el Atajo 'Oye Siri, JARVIS': manda la pregunta ya transcrita por Siri
    y devuelve la respuesta en texto y audio para que el Atajo la reproduzca."""
    user_text = request.text.strip()
    if not user_text:
        raise HTTPException(status_code=400, detail="texto vacío")
    ai_response = await run_agent(user_text)
    audio_bytes = await text_to_speech(ai_response)
    return {
        "text": ai_response,
        "audio": base64.b64encode(audio_bytes).decode() if audio_bytes else None,
        "audio_type": "audio/mp3",
    }


def _get_fuel_status() -> Optional[dict]:
    if not MERCEDES_CONFIGURED:
        return None
    return car.get_fuel_status(
        MERCEDES_VIN, MERCEDES_CLIENT_ID, MERCEDES_CLIENT_SECRET, MERCEDES_REFRESH_TOKEN
    )


def _get_lock_status() -> Optional[bool]:
    if not MERCEDES_CONFIGURED:
        return None
    return car.get_lock_status(
        MERCEDES_VIN, MERCEDES_CLIENT_ID, MERCEDES_CLIENT_SECRET, MERCEDES_REFRESH_TOKEN
    )


@app.get("/api/car/status", dependencies=[Depends(require_token)])
async def car_status():
    """Estado crudo del coche, para que el Atajo decida si avisa de que está abierto."""
    fuel = _get_fuel_status()
    return {
        "locked": _get_lock_status(),
        "fuel_percent": fuel["fuel_percent"] if fuel else None,
        "range_km": fuel["range_km"] if fuel else None,
    }


@app.get("/api/carplay/greeting", dependencies=[Depends(require_token)])
async def carplay_greeting():
    """Para la automatización 'al conectar CarPlay': frase de bienvenida con lo
    que realmente se pudo consultar (combustible/autonomía y clima). Si algo no
    está configurado o falla, simplemente se omite esa parte — nunca se inventa."""
    parts = []
    hour = datetime.now().hour
    saludo = "Buenos días" if hour < 13 else ("Buenas tardes" if hour < 21 else "Buenas noches")
    parts.append(f"{saludo}, {OWNER_NAME}.")

    fuel = _get_fuel_status()
    if fuel:
        parts.append(
            f"Depósito al {fuel['fuel_percent']:.0f}%, "
            f"unos {fuel['range_km']:.0f} km de autonomía."
        )

    if HOME_LAT and HOME_LON:
        temp = weather.get_current_temperature(float(HOME_LAT), float(HOME_LON))
        if temp is not None:
            parts.append(f"Fuera hacen {temp:.0f} grados.")

    text = " ".join(parts)
    audio_bytes = await text_to_speech(text)
    return {
        "text": text,
        "audio": base64.b64encode(audio_bytes).decode() if audio_bytes else None,
        "audio_type": "audio/mp3",
    }

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

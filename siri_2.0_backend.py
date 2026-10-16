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
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
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
import google_services
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
    },
    # ── Correo (Gmail) ──
    {
        "name": "check_email",
        "description": "Lista los correos sin leer de la bandeja principal (sin promociones ni redes sociales): remitente, asunto y un extracto. Úsalo cuando pregunte si tiene correo o qué le ha llegado.",
        "input_schema": {
            "type": "object",
            "properties": {
                "max_results": {"type": "integer", "description": "Cuántos listar (por defecto 5)"}
            }
        }
    },
    {
        "name": "search_email",
        "description": "Busca correos con la sintaxis de búsqueda de Gmail (p. ej. 'from:banco', 'subject:factura newer_than:7d'). Sirve también para encontrar la dirección de alguien a quien quiera escribir.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Consulta de búsqueda de Gmail"},
                "max_results": {"type": "integer", "description": "Cuántos devolver (por defecto 5)"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "read_email",
        "description": "Lee el contenido completo de un correo (y lo marca como leído). Resúmelo en voz alta en una o dos frases salvo que pida que se lo leas entero.",
        "input_schema": {
            "type": "object",
            "properties": {
                "email_id": {"type": "string", "description": "id del correo, de check_email o search_email"}
            },
            "required": ["email_id"]
        }
    },
    {
        "name": "prepare_email_reply",
        "description": "Prepara una respuesta a un correo, SIN enviarla. Después lee en voz alta a quién va y lo que dice, y pregunta si lo envías. Solo se envía si en su siguiente mensaje lo confirma (confirm_pending_action).",
        "input_schema": {
            "type": "object",
            "properties": {
                "email_id": {"type": "string", "description": "id del correo al que se responde"},
                "body": {"type": "string", "description": "Texto de la respuesta, ya redactado y listo para enviar"}
            },
            "required": ["email_id", "body"]
        }
    },
    {
        "name": "prepare_new_email",
        "description": "Prepara un correo nuevo, SIN enviarlo. Si no conoces la dirección, búscala antes con search_email. Después lee el destinatario y el texto y pregunta si lo envías.",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Dirección de correo del destinatario"},
                "subject": {"type": "string", "description": "Asunto"},
                "body": {"type": "string", "description": "Texto del correo"}
            },
            "required": ["to", "subject", "body"]
        }
    },
    # ── WhatsApp ──
    {
        "name": "prepare_whatsapp",
        "description": "Prepara un WhatsApp para un contacto de su iPhone, SIN enviarlo. Después dile a quién va y lo que dice, y pregunta si lo envías. Solo funciona cuando habla desde el iPhone. No puedes leer sus WhatsApp, solo enviarlos.",
        "input_schema": {
            "type": "object",
            "properties": {
                "contact_name": {"type": "string", "description": "Nombre del contacto tal como lo tendría en la agenda del iPhone"},
                "text": {"type": "string", "description": "Texto del mensaje"}
            },
            "required": ["contact_name", "text"]
        }
    },
    # ── Confirmación de envíos ──
    {
        "name": "confirm_pending_action",
        "description": "Ejecuta lo que preparaste en el turno anterior (correo, WhatsApp o borrar una cita). Llámalo SOLO si en este mensaje confirma claramente ('sí', 'envíalo', 'adelante').",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "cancel_pending_action",
        "description": "Descarta lo que tenías preparado, si dice que no o que lo deje.",
        "input_schema": {"type": "object", "properties": {}}
    },
    # ── Agenda (Google Calendar) ──
    {
        "name": "get_calendar_events",
        "description": "Citas de su Google Calendar. Por defecto, las de hoy. Para mañana usa days_ahead=1; para la semana, days=7.",
        "input_schema": {
            "type": "object",
            "properties": {
                "days_ahead": {"type": "integer", "description": "Desde qué día empezar: 0 = hoy, 1 = mañana..."},
                "days": {"type": "integer", "description": "Cuántos días incluir (por defecto 1)"}
            }
        }
    },
    {
        "name": "create_calendar_event",
        "description": "Crea una cita en su Google Calendar. Si no dice cuánto dura, ponle una hora. Confirma después en pocas palabras qué has agendado y cuándo.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Título de la cita"},
                "start": {"type": "string", "description": "Inicio, hora local, formato YYYY-MM-DDTHH:MM:SS"},
                "end": {"type": "string", "description": "Fin, hora local, formato YYYY-MM-DDTHH:MM:SS"},
                "location": {"type": "string", "description": "Lugar (opcional)"},
                "description": {"type": "string", "description": "Notas (opcional)"}
            },
            "required": ["title", "start", "end"]
        }
    },
    {
        "name": "prepare_delete_calendar_event",
        "description": "Prepara borrar una cita de su calendario, SIN borrarla. Di cuál es y pregunta si la borras.",
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string", "description": "id de la cita, de get_calendar_events"},
                "title": {"type": "string", "description": "Título de la cita, para confirmarlo en voz alta"}
            },
            "required": ["event_id", "title"]
        }
    },
    # ── Coche y entorno ──
    {
        "name": "get_car_status",
        "description": "Estado real de su Mercedes: nivel de combustible, autonomía en km y si está cerrado. Úsalo cuando pregunte por gasolina, autonomía o si cerró el coche.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "get_weather",
        "description": "Temperatura actual en su zona.",
        "input_schema": {"type": "object", "properties": {}}
    }
]

# ── CONTEXTO DE CADA PETICIÓN Y ACCIONES PENDIENTES ───────────────────────────

@dataclass
class AgentContext:
    channel: str  # "iphone" (Atajos de Siri) o "pantalla" (interfaz holográfica)
    can_send_whatsapp: bool = False
    turn: int = 0
    client_actions: list = field(default_factory=list)
    awaiting_confirmation: bool = False


PENDING_TTL_SECONDS = 300
pending_action: Optional[dict] = None
agent_turn = 0


def _set_pending(ctx: AgentContext, action_type: str, payload: dict, summary: dict) -> dict:
    global pending_action
    pending_action = {
        "type": action_type,
        "payload": payload,
        "summary": summary,
        "turn": ctx.turn,
        "created": datetime.now(),
    }
    ctx.awaiting_confirmation = True
    return {"prepared": True, "not_sent_yet": True, **summary,
            "next_step": "Léeselo en voz alta y pregunta si lo envías/ejecutas."}


def current_pending(turn: int) -> Optional[dict]:
    """Lo preparado en el turno inmediatamente anterior. Exigir que haya un mensaje
    del usuario en medio garantiza que nada se envía sin que él lo haya oído."""
    if not pending_action:
        return None
    if pending_action["turn"] != turn - 1:
        return None
    if datetime.now() - pending_action["created"] > timedelta(seconds=PENDING_TTL_SECONDS):
        return None
    return pending_action


def _confirm_pending(ctx: AgentContext) -> dict:
    global pending_action
    action = current_pending(ctx.turn)
    if not action:
        pending_action = None
        return {"error": "No hay nada preparado pendiente de confirmar (o ha caducado). Prepáralo de nuevo."}

    pending_action = None
    payload = action["payload"]
    if action["type"] == "email_reply":
        return google_services.reply(payload["email_id"], payload["body"])
    if action["type"] == "email_new":
        return google_services.send(payload["to"], payload["subject"], payload["body"])
    if action["type"] == "calendar_delete":
        return google_services.delete_event(payload["event_id"])
    if action["type"] == "whatsapp":
        if not ctx.can_send_whatsapp:
            return {"error": "Desde aquí no se pueden enviar WhatsApp, solo desde el iPhone."}
        ctx.client_actions.append({"type": "send_whatsapp", **payload})
        return {"success": True, "note": "El iPhone lo está enviando ahora."}
    return {"error": f"Acción desconocida: {action['type']}"}


def _car_status() -> dict:
    if not MERCEDES_CONFIGURED:
        return {"error": "La conexión con el Mercedes todavía no está configurada."}
    fuel = _get_fuel_status()
    locked = _get_lock_status()
    if fuel is None and locked is None:
        return {"error": "No he podido consultar el coche ahora mismo."}
    return {
        "fuel_percent": fuel["fuel_percent"] if fuel else None,
        "range_km": fuel["range_km"] if fuel else None,
        "locked": locked,
    }


def execute_integration_tool(name: str, inputs: dict, ctx: AgentContext) -> dict:
    global pending_action
    if name == "check_email":
        return google_services.list_unread(inputs.get("max_results", 5))
    if name == "search_email":
        return google_services.search(inputs["query"], inputs.get("max_results", 5))
    if name == "read_email":
        return google_services.read(inputs["email_id"])
    if name == "prepare_email_reply":
        preview = google_services.reply_preview(inputs["email_id"])
        return _set_pending(ctx, "email_reply", inputs, {**preview, "body": inputs["body"]})
    if name == "prepare_new_email":
        return _set_pending(ctx, "email_new", inputs, inputs)
    if name == "prepare_whatsapp":
        if not ctx.can_send_whatsapp:
            return {"error": "Los WhatsApp solo se pueden enviar cuando habla desde el iPhone."}
        payload = {"contact": inputs["contact_name"], "text": inputs["text"]}
        return _set_pending(ctx, "whatsapp", payload, payload)
    if name == "confirm_pending_action":
        return _confirm_pending(ctx)
    if name == "cancel_pending_action":
        pending_action = None
        return {"success": True}
    if name == "get_calendar_events":
        return google_services.events_for_days(TIMEZONE, inputs.get("days_ahead", 0), inputs.get("days", 1))
    if name == "create_calendar_event":
        return google_services.create_event(
            inputs["title"], inputs["start"], inputs["end"], TIMEZONE,
            inputs.get("location"), inputs.get("description"),
        )
    if name == "prepare_delete_calendar_event":
        return _set_pending(ctx, "calendar_delete", {"event_id": inputs["event_id"]}, {"title": inputs["title"]})
    if name == "get_car_status":
        return _car_status()
    if name == "get_weather":
        if not (HOME_LAT and HOME_LON):
            return {"error": "No tengo configurada la ubicación para el tiempo."}
        temp = weather.get_current_temperature(float(HOME_LAT), float(HOME_LON))
        return {"temperature_c": temp} if temp is not None else {"error": "No he podido consultar el tiempo."}
    return {"error": f"Herramienta desconocida: {name}"}


INTEGRATION_TOOLS = {
    "check_email", "search_email", "read_email", "prepare_email_reply", "prepare_new_email",
    "prepare_whatsapp", "confirm_pending_action", "cancel_pending_action",
    "get_calendar_events", "create_calendar_event", "prepare_delete_calendar_event",
    "get_car_status", "get_weather",
}

# ── TOOL EXECUTORS ────────────────────────────────────────────────────────────

def execute_tool(name: str, inputs: dict, ctx: AgentContext) -> dict:
    if name in INTEGRATION_TOOLS:
        try:
            return execute_integration_tool(name, inputs, ctx)
        except google_services.GoogleNotConfigured as e:
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Error en tool {name}: {e}")
            return {"error": f"Ha fallado {name}: {e}"}

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


def build_system_prompt(user_input: str, ctx: AgentContext) -> str:
    now = datetime.now(ZoneInfo(TIMEZONE))
    fecha = f"{DIAS[now.weekday()]} {now.day} de {MESES[now.month - 1]} de {now.year}, {now:%H:%M}"
    canal = (
        "Te habla desde el iPhone o el coche a través de Siri: puedes enviar WhatsApp."
        if ctx.channel == "iphone"
        else "Te habla desde la pantalla de casa u oficina: desde aquí no se pueden enviar WhatsApp."
    )

    prompt = (
        f"Eres JARVIS, el asistente personal de {OWNER_NAME}. Hablas español de España con un tono "
        "sereno, elegante y un punto de ironía británica, como un mayordomo brillante y leal. "
        "Todo lo que dices se lee en voz alta, a menudo mientras conduce: responde en una a tres "
        "frases cortas, sin listas, sin markdown y sin emojis. Ve al grano, con ingenio cuando encaje, "
        f"y llámale {OWNER_NAME} de vez en cuando, sin abusar. "
        "Nunca inventes datos sobre su agenda, su coche, su correo o sus cosas: si no tienes el dato, "
        "dilo con naturalidad. "
        "No cierres con preguntas de cortesía como '¿algo más?': pregunta solo cuando necesites "
        "una respuesta suya. "
        "Tienes acceso a su Gmail, su Google Calendar, su Mercedes y el tiempo; úsalos sin pedir "
        "permiso para consultar. Para tareas, recordatorios y notas usa las herramientas propias y "
        "confirma en pocas palabras. "
        "Enviar correos, enviar WhatsApp o borrar citas va siempre en dos pasos: primero lo preparas "
        "y le dices en voz alta a quién va y qué dice; solo cuando en su siguiente mensaje diga que "
        "sí, llamas a confirm_pending_action. Nunca digas que algo está enviado si no lo has confirmado. "
        "Sus WhatsApp no los puedes leer: si te lo pide, dile que en el coche Siri se los lee con "
        "'Oye Siri, lee mis mensajes'. "
        "Cuando te cuente una preferencia o un dato personal estable (cómo le gusta el café, su "
        "equipo, nombres de gente cercana, rutinas), guárdalo con remember_preference sin preguntar.\n\n"
        f"Ahora es {fecha}. {canal}"
    )

    pending = current_pending(ctx.turn)
    if pending:
        prompt += (
            "\n\nEn tu mensaje anterior preparaste esto y le preguntaste si seguir adelante: "
            f"{json.dumps({'tipo': pending['type'], **pending['summary']}, ensure_ascii=False)}. "
            "Si ahora lo confirma, llama a confirm_pending_action; si dice que no, a cancel_pending_action."
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


async def stream_agent(user_input: str, ctx: AgentContext) -> AsyncIterator[str]:
    """Genera la respuesta frase a frase según llega de Claude, ejecutando las
    herramientas que pida por el camino."""
    global agent_turn
    agent_turn += 1
    ctx.turn = agent_turn

    messages = [*conversation_history[-10:], {"role": "user", "content": user_input}]
    system_prompt = build_system_prompt(user_input, ctx)
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
                # En un hilo: Gmail, Calendar y Mercedes hacen llamadas de red bloqueantes.
                result = await asyncio.to_thread(execute_tool, block.name, block.input, ctx)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result, ensure_ascii=False),
                })

        messages.append({"role": "assistant", "content": assistant_content})
        messages.append({"role": "user", "content": tool_results})

    add_to_history("user", user_input)
    add_to_history("assistant", " ".join(spoken))


async def run_agent(user_input: str, ctx: AgentContext) -> str:
    return " ".join([sentence async for sentence in stream_agent(user_input, ctx)])

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
            async for sentence in stream_agent(user_text, AgentContext(channel="pantalla")):
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
    ctx = AgentContext(channel="iphone", can_send_whatsapp=True)
    ai_response = await run_agent(user_text, ctx)
    audio_bytes = await text_to_speech(ai_response)
    return {
        "text": ai_response,
        "audio": base64.b64encode(audio_bytes).decode() if audio_bytes else None,
        "audio_type": "audio/mp3",
        # El Atajo vuelve a escuchar si JARVIS ha hecho una pregunta o espera un "sí".
        "expects_reply": ctx.awaiting_confirmation or ai_response.rstrip().endswith("?"),
        # Lo que el Atajo tiene que hacer en el iPhone, p. ej. enviar un WhatsApp ya confirmado.
        "client_action": ctx.client_actions[-1] if ctx.client_actions else None,
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
    fuel, locked = await asyncio.gather(
        asyncio.to_thread(_get_fuel_status), asyncio.to_thread(_get_lock_status)
    )
    return {
        "locked": locked,
        "fuel_percent": fuel["fuel_percent"] if fuel else None,
        "range_km": fuel["range_km"] if fuel else None,
    }


async def _safe(func, *args):
    """Ejecuta una consulta bloqueante en un hilo; si falla, None en vez de romper el saludo."""
    try:
        return await asyncio.to_thread(func, *args)
    except Exception as e:
        logger.error(f"Saludo: fallo en {func.__name__}: {e}")
        return None


def _calendar_today() -> Optional[dict]:
    """{'event': próxima cita o None} si se pudo consultar; None si no hay calendario."""
    if not google_services.is_configured():
        return None
    return {"event": google_services.next_event_today(TIMEZONE)}


def _temperature() -> Optional[float]:
    if not (HOME_LAT and HOME_LON):
        return None
    return weather.get_current_temperature(float(HOME_LAT), float(HOME_LON))


@app.get("/api/carplay/greeting", dependencies=[Depends(require_token)])
async def carplay_greeting():
    """Para la automatización 'al conectar CarPlay': frase de bienvenida con lo
    que realmente se pudo consultar (combustible, tiempo, próxima cita y correos).
    Si algo no está configurado o falla, se omite esa parte: nunca se inventa."""
    tz = ZoneInfo(TIMEZONE)
    hour = datetime.now(tz).hour
    saludo = "Buenos días" if 6 <= hour < 13 else ("Buenas tardes" if 13 <= hour < 21 else "Buenas noches")
    parts = [f"{saludo}, {OWNER_NAME}."]

    fuel, temp, calendar, unread = await asyncio.gather(
        _safe(_get_fuel_status),
        _safe(_temperature),
        _safe(_calendar_today),
        _safe(google_services.count_unread),
    )

    if fuel:
        parts.append(
            f"Depósito al {fuel['fuel_percent']:.0f}%, "
            f"unos {fuel['range_km']:.0f} km de autonomía."
        )
    if temp is not None:
        parts.append(f"Fuera hacen {temp:.0f} grados.")
    if calendar and calendar["event"]:
        event = calendar["event"]
        start = datetime.fromisoformat(event["start"]).astimezone(tz)
        parts.append(f"Tu próxima cita es a las {start:%H:%M}: {event['title']}.")
    elif calendar:
        parts.append("Hoy no tienes más citas.")
    if unread:
        parts.append(f"Tienes {unread} correo{'s' if unread != 1 else ''} sin leer.")

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

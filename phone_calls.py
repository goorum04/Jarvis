"""
Llamadas de teléfono en nombre de Nacho (reservas, citas, preguntar horarios).

Las hace un agente de voz de ElevenLabs desde un número propio de JARVIS:
- Twilio (por defecto): un número español, francés... que ElevenLabs usa para llamar.
- Línea SIP (CALL_PROVIDER=sip_trunk): por ejemplo, una línea de Andorra
  Telecom, si la ofrecen, para llamar con un número +376.

El agente se crea una vez con `python crear_agente_llamadas.py`, que deja
ELEVENLABS_AGENT_ID y ELEVENLABS_PHONE_NUMBER_ID en el .env.
"""
import logging
import os
import re
from typing import Optional

from elevenlabs.client import ElevenLabs

logger = logging.getLogger(__name__)

OUTCOMES = ["confirmado", "no_disponible", "pendiente", "sin_respuesta", "otro"]

AGENT_PROMPT = """Eres el asistente de inteligencia artificial de {{owner_name}} y estás haciendo una llamada de teléfono en su nombre a {{business_name}}.

Lo que tienes que conseguir: {{task}}
Margen que te ha dado {{owner_name}}: {{limits}}
Teléfono de contacto, solo si te lo piden: {{callback_phone}}

Cómo comportarte:
- Ya te has presentado como asistente de inteligencia artificial. Si te preguntan, confírmalo siempre con naturalidad; nunca digas que eres una persona.
- Habla en castellano. Si te contestan en catalán o en francés, cambia a ese idioma.
- Sé breve, amable y concreto, como una persona educada al teléfono. Deja hablar y no interrumpas.
- Acepta solo lo que esté dentro del margen. Si no hay nada dentro del margen, da las gracias y di que lo consultarás con {{owner_name}}.
- No aceptes pagos, señales ni depósitos, y no des datos de tarjetas ni más datos personales que el nombre y el teléfono de contacto. Si los piden, di que {{owner_name}} lo gestionará directamente.
- No inventes nada. Si preguntan algo que no sabes (alergias, terraza, trona, motivo), di que lo consultarás.
- Cuando quede cerrado, o esté claro que no se puede, repite el resumen ("Entonces, mesa para cuatro mañana a las nueve a nombre de {{owner_name}}"), despídete y cuelga con end_call.
- Si salta un contestador o un menú automático sin opción útil, cuelga sin dejar mensaje."""

FIRST_MESSAGE = (
    "Hola, buenas. Le llamo de parte de {{owner_name}}; soy su asistente de inteligencia artificial. {{opening_line}}"
)

DATA_COLLECTION = {
    "outcome": {
        "type": "string",
        "enum": OUTCOMES,
        "description": "Resultado: confirmado (quedó cerrado lo que se pedía), no_disponible (no había nada dentro del margen), "
                       "pendiente (lo tienen que confirmar más tarde), sin_respuesta (no contestaron, contestador o menú), otro.",
    },
    "confirmed_details": {
        "type": "string",
        "description": "Lo acordado exactamente (día, hora, número de personas, nombre de la reserva...), o vacío si no se acordó nada.",
    },
    "event_start": {
        "type": "string",
        "description": "Si quedó confirmada una reserva o cita, su fecha y hora de inicio en formato YYYY-MM-DDTHH:MM:SS. Si no, vacío.",
    },
    "notes": {
        "type": "string",
        "description": "Lo que hay que contarle a la persona que encargó la llamada: condiciones, alternativas ofrecidas, preguntas que quedaron pendientes.",
    },
}


class CallsNotConfigured(Exception):
    pass


def _client() -> ElevenLabs:
    return ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))


def is_configured() -> bool:
    return bool(os.getenv("ELEVENLABS_API_KEY") and os.getenv("ELEVENLABS_AGENT_ID") and os.getenv("ELEVENLABS_PHONE_NUMBER_ID"))


def normalize_number(raw: str) -> Optional[str]:
    """Número en formato internacional (+376..., +34..., +33...). Los números
    sin prefijo se interpretan como de Andorra (6 cifras), España (9 cifras,
    empezando por 6, 7, 8 o 9) o Francia (10 cifras, empezando por 0)."""
    digits = re.sub(r"[^\d+]", "", raw or "")
    if digits.startswith("00"):
        digits = "+" + digits[2:]
    if digits.startswith("+"):
        return digits if 8 <= len(digits) <= 16 else None
    if len(digits) == 6:
        return "+376" + digits
    if len(digits) == 9 and digits[0] in "6789":
        return "+34" + digits
    if len(digits) == 10 and digits.startswith("0"):
        return "+33" + digits[1:]
    return None


def agent_config(owner_name: str, voice_id: str, timezone: str) -> dict:
    """Configuración del agente de llamadas para la API de ElevenLabs."""
    languages = [code.strip() for code in os.getenv("CALL_LANGUAGES", "ca,fr").split(",") if code.strip()]
    return {
        "agent": {
            "first_message": FIRST_MESSAGE,
            "language": "es",
            "dynamic_variables": {"dynamic_variable_placeholders": {
                "owner_name": owner_name, "business_name": "el negocio", "task": "", "limits": "ninguno",
                "callback_phone": "no hay; di que te pondrás en contacto tú", "opening_line": "",
            }},
            "prompt": {
                "prompt": AGENT_PROMPT,
                # Al teléfono manda la rapidez de respuesta: un modelo ágil.
                "llm": os.getenv("CALL_AGENT_LLM", "claude-sonnet-5-5"),
                "temperature": 0.3,
                "timezone": timezone,
                "built_in_tools": {
                    "end_call": {"name": "end_call", "params": {"system_tool_type": "end_call"}},
                    "language_detection": {"name": "language_detection", "params": {"system_tool_type": "language_detection"}},
                    "voicemail_detection": {"name": "voicemail_detection", "params": {"system_tool_type": "voicemail_detection"}},
                },
            },
        },
        "language_presets": {code: {"overrides": {}} for code in languages},
        "tts": {"voice_id": voice_id, "model_id": "eleven_flash_v2_5"},
        "conversation": {"max_duration_seconds": int(os.getenv("CALL_MAX_SECONDS", "300"))},
    }


def platform_settings() -> dict:
    return {
        "data_collection": DATA_COLLECTION,
        "call_limits": {"daily_limit": int(os.getenv("MAX_CALLS_PER_DAY", "5")), "agent_concurrency_limit": 1},
        "summary_language": "es",
    }


def start_call(to_number: str, variables: dict) -> str:
    """Lanza la llamada y devuelve el id de la conversación para seguirla."""
    if not is_configured():
        raise CallsNotConfigured("Las llamadas no están configuradas: hay que ejecutar crear_agente_llamadas.py.")
    calls = _client().conversational_ai
    provider = calls.sip_trunk if os.getenv("CALL_PROVIDER", "twilio") == "sip_trunk" else calls.twilio
    response = provider.outbound_call(
        agent_id=os.getenv("ELEVENLABS_AGENT_ID"),
        agent_phone_number_id=os.getenv("ELEVENLABS_PHONE_NUMBER_ID"),
        to_number=to_number,
        conversation_initiation_client_data={"dynamic_variables": {k: str(v) for k, v in variables.items()}},
    )
    if not getattr(response, "success", False) or not getattr(response, "conversation_id", None):
        raise RuntimeError(f"La llamada no se pudo iniciar: {getattr(response, 'message', 'sin detalle')}")
    return response.conversation_id


def call_result(conversation_id: str) -> Optional[dict]:
    """Resultado de la llamada, o None si todavía está en curso."""
    conversation = _client().conversational_ai.conversations.get(conversation_id)
    if conversation.status not in ("done", "failed"):
        return None
    analysis = conversation.analysis
    collected = {}
    if analysis and analysis.data_collection_results:
        collected = {key: item.value for key, item in analysis.data_collection_results.items()}
    outcome = collected.get("outcome") if collected.get("outcome") in OUTCOMES else None
    if conversation.status == "failed":
        outcome = outcome or "sin_respuesta"
    return {
        "status": conversation.status,
        "outcome": outcome or "otro",
        "confirmed_details": collected.get("confirmed_details") or "",
        "event_start": collected.get("event_start") or "",
        "notes": collected.get("notes") or "",
        "summary": analysis.transcript_summary if analysis else "",
        "duration_secs": conversation.metadata.call_duration_secs if conversation.metadata else 0,
        "termination_reason": conversation.metadata.termination_reason if conversation.metadata else None,
    }

"""
Avisos al iPhone de Nacho cuando JARVIS tiene algo que decir sin que se lo
pregunten (recordatorios, correo importante, gasolina, hora de salir).

Dos opciones, se usa la que esté configurada en el .env (o las dos):

- Pushcut (recomendado): PUSHCUT_SECRET + PUSHCUT_NOTIFICATION. La
  notificación se crea en la app Pushcut y puede lanzar un Atajo que lea el
  aviso en voz alta (el texto llega como "input"). Ver CONFIGURAR_JARVIS.md.
- ntfy (gratis, solo notificación): NTFY_TOPIC (y NTFY_SERVER si no es ntfy.sh).
"""
import logging
import os
from typing import Optional
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)


def is_configured() -> bool:
    return bool(os.getenv("PUSHCUT_SECRET") or os.getenv("NTFY_TOPIC"))


def _pushcut(title: str, text: str, url: Optional[str], urgent: bool) -> bool:
    secret = os.getenv("PUSHCUT_SECRET")
    if not secret:
        return False
    name = os.getenv("PUSHCUT_NOTIFICATION", "JARVIS")
    body = {"title": title, "text": text, "input": text, "isTimeSensitive": urgent}
    if url:
        body["defaultAction"] = {"name": "Abrir", "url": url}
    response = httpx.post(
        f"https://api.pushcut.io/{quote(secret)}/notifications/{quote(name)}", json=body, timeout=10
    )
    response.raise_for_status()
    return True


def _ntfy(title: str, text: str, url: Optional[str], urgent: bool) -> bool:
    topic = os.getenv("NTFY_TOPIC")
    if not topic:
        return False
    server = os.getenv("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
    body = {"topic": topic, "title": title, "message": text, "priority": 5 if urgent else 3}
    if url:
        body["click"] = url
    response = httpx.post(server, json=body, timeout=10)
    response.raise_for_status()
    return True


def notify(title: str, text: str, url: Optional[str] = None, urgent: bool = False) -> bool:
    """Devuelve True si al menos un canal lo entregó. Nunca lanza excepción."""
    delivered = False
    for channel in (_pushcut, _ntfy):
        try:
            delivered = channel(title, text, url, urgent) or delivered
        except Exception as e:
            logger.error(f"Aviso por {channel.__name__} fallido: {e}")
    if not delivered:
        logger.warning(f"Aviso sin entregar (sin canal configurado o con error): {title} — {text}")
    return delivered

"""
Avisos propios de JARVIS en el iPhone, la tablet o el ordenador, sin Pushcut:
notificaciones web (Web Push) del panel instalado en la pantalla de inicio.

En el iPhone funcionan con el panel añadido a la pantalla de inicio (iOS 16.4
o posterior): Conexiones → «Avisos en este dispositivo» → Activar. Cada
dispositivo que los activa queda apuntado en push_subscriptions.json.

Las claves VAPID (la firma de los avisos) se generan solas la primera vez y
se guardan en el .env.
"""
import json
import logging
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SUBSCRIPTIONS_FILE = Path(__file__).parent / "push_subscriptions.json"
_lock = threading.Lock()


def _load() -> list[dict]:
    try:
        return json.loads(SUBSCRIPTIONS_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save(subscriptions: list[dict]) -> None:
    SUBSCRIPTIONS_FILE.write_text(json.dumps(subscriptions, ensure_ascii=False, indent=2))
    SUBSCRIPTIONS_FILE.chmod(0o600)


def public_key() -> str:
    """Clave pública que el navegador necesita para suscribirse (se crea si falta)."""
    from cryptography.hazmat.primitives import serialization
    from py_vapid import Vapid01, b64urlencode

    with _lock:
        if not os.getenv("VAPID_PRIVATE_KEY"):
            vapid = Vapid01()
            vapid.generate_keys()
            private = vapid.private_key.private_bytes(
                serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
            import conexiones  # aquí para no importarse mutuamente al arrancar
            conexiones.save_env({"VAPID_PRIVATE_KEY": b64urlencode(private)})
        vapid = Vapid01.from_string(os.environ["VAPID_PRIVATE_KEY"])
        raw = vapid.public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
        return b64urlencode(raw)


def subscribe(subscription: dict, device: str = "") -> int:
    """Apunta un dispositivo. Devuelve cuántos hay."""
    endpoint = subscription.get("endpoint", "")
    keys = subscription.get("keys") or {}
    if not endpoint.startswith("https://") or not keys.get("p256dh") or not keys.get("auth"):
        raise ValueError("Suscripción no válida.")
    with _lock:
        subscriptions = [s for s in _load() if s["endpoint"] != endpoint]
        subscriptions.append({
            "endpoint": endpoint, "keys": {"p256dh": keys["p256dh"], "auth": keys["auth"]},
            "device": device[:80], "since": datetime.now().isoformat(timespec="minutes"),
        })
        _save(subscriptions)
        return len(subscriptions)


def unsubscribe(endpoint: str) -> None:
    with _lock:
        _save([s for s in _load() if s["endpoint"] != endpoint])


def devices() -> list[dict]:
    return [{"device": s.get("device") or "Dispositivo", "since": s.get("since"), "endpoint": s["endpoint"]} for s in _load()]


def is_configured() -> bool:
    return bool(_load())


def send(title: str, text: str, url: Optional[str] = None, urgent: bool = False) -> bool:
    """Manda el aviso a todos los dispositivos apuntados. True si llegó a alguno.
    Los que el navegador ha dado de baja (404/410) se quitan solos."""
    from pywebpush import WebPushException, webpush

    subscriptions = _load()
    if not subscriptions:
        return False
    payload = json.dumps({"title": title, "body": text, "url": url or "/"}, ensure_ascii=False)
    claims = {"sub": f"mailto:{os.getenv('VAPID_CONTACT', 'jarvis@localhost')}"}
    delivered, gone = False, []
    for subscription in subscriptions:
        try:
            webpush(
                {"endpoint": subscription["endpoint"], "keys": subscription["keys"]},
                data=payload, vapid_private_key=os.environ.get("VAPID_PRIVATE_KEY"), vapid_claims=dict(claims),
                ttl=4 * 3600, headers={"Urgency": "high" if urgent else "normal"}, timeout=10,
            )
            delivered = True
        except WebPushException as e:
            status = getattr(e.response, "status_code", None)
            if status in (404, 410):
                gone.append(subscription["endpoint"])
            else:
                logger.error(f"No se pudo mandar el aviso web a {subscription.get('device')}: {e}")
        except Exception as e:
            logger.error(f"No se pudo mandar el aviso web a {subscription.get('device')}: {e}")
    for endpoint in gone:
        unsubscribe(endpoint)
    return delivered

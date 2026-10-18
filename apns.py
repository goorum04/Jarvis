"""
Avisos de la app de iPhone «JARVIS» (servicio de avisos de Apple, APNs).

La app, al abrirla, pide permiso y apunta el iPhone en JARVIS
(/api/push/apns). Para mandarle avisos hace falta la clave de avisos de la
cuenta de desarrollador de Apple (un archivo .p8), que va en el código de
preparación: APNS_KEY_ID, APNS_TEAM_ID, APNS_KEY_P8 (el .p8 en base64) y
APNS_TOPIC (el identificador de la app, el mismo IOS_BUNDLE_ID con que se
compila). Ver GUIA_INSTALACION.md, «App de iPhone».
"""
import base64
import json
import logging
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

DEVICES_FILE = Path(__file__).parent / "apns_devices.json"
HOSTS = {"production": "https://api.push.apple.com", "sandbox": "https://api.sandbox.push.apple.com"}
DEFAULT_TOPIC = "com.goorum04.jarvis"

_lock = threading.Lock()
_jwt_cache: dict = {}


def _env(key: str) -> str:
    return os.getenv(key, "").strip()


def is_ready() -> bool:
    """¿Está la clave de avisos de Apple para poder mandarlos?"""
    return bool(_env("APNS_KEY_ID") and _env("APNS_TEAM_ID") and _env("APNS_KEY_P8"))


def _load() -> list[dict]:
    try:
        return json.loads(DEVICES_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save(devices: list[dict]) -> None:
    DEVICES_FILE.write_text(json.dumps(devices, ensure_ascii=False, indent=2))
    DEVICES_FILE.chmod(0o600)


def register(device_token: str, environment: str = "production", device: str = "iPhone") -> int:
    token = device_token.strip().lower()
    if not token or any(c not in "0123456789abcdef" for c in token) or len(token) < 32:
        raise ValueError("Identificador de iPhone no válido.")
    if environment not in HOSTS:
        raise ValueError("Entorno de avisos no válido.")
    with _lock:
        devices = [d for d in _load() if d["token"] != token]
        devices.append({"token": token, "environment": environment, "device": device[:80],
                        "since": datetime.now().isoformat(timespec="minutes")})
        _save(devices)
        return len(devices)


def unregister(device_token: str) -> None:
    with _lock:
        _save([d for d in _load() if d["token"] != device_token.strip().lower()])


def devices() -> list[dict]:
    return _load()


def is_configured() -> bool:
    return is_ready() and bool(_load())


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _token() -> str:
    """El JWT con que Apple reconoce a JARVIS. Vale una hora; se renueva a los 50 min."""
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

    key_id, team_id = _env("APNS_KEY_ID"), _env("APNS_TEAM_ID")
    cached = _jwt_cache.get((key_id, team_id))
    if cached and time.time() - cached[1] < 50 * 60:
        return cached[0]
    raw = _env("APNS_KEY_P8")
    pem = raw.encode() if "BEGIN PRIVATE KEY" in raw else base64.b64decode(raw + "=" * (-len(raw) % 4))
    private_key = serialization.load_pem_private_key(pem, password=None)
    header = _b64(json.dumps({"alg": "ES256", "kid": key_id}, separators=(",", ":")).encode())
    issued = int(time.time())
    claims = _b64(json.dumps({"iss": team_id, "iat": issued}, separators=(",", ":")).encode())
    signing_input = f"{header}.{claims}".encode()
    r, s = decode_dss_signature(private_key.sign(signing_input, ec.ECDSA(hashes.SHA256())))
    token = f"{header}.{claims}.{_b64(r.to_bytes(32, 'big') + s.to_bytes(32, 'big'))}"
    _jwt_cache[(key_id, team_id)] = (token, issued)
    return token


def send(title: str, text: str, url: Optional[str] = None, urgent: bool = False) -> bool:
    """Manda el aviso a todos los iPhone con la app. True si llegó a alguno. Los
    que Apple da por desinstalados (410 o BadDeviceToken) se quitan solos."""
    devices = _load()
    if not devices or not is_ready():
        return False
    payload = {"aps": {"alert": {"title": title, "body": text}, "sound": "default"}}
    if url:
        payload["url"] = url
    headers = {
        "authorization": f"bearer {_token()}",
        "apns-topic": _env("APNS_TOPIC") or DEFAULT_TOPIC,
        "apns-push-type": "alert",
        "apns-priority": "10" if urgent else "5",
    }
    delivered, gone = False, []
    with httpx.Client(http2=True, timeout=10) as client:
        for device in devices:
            try:
                response = client.post(f"{HOSTS[device['environment']]}/3/device/{device['token']}",
                                       json=payload, headers=headers)
            except Exception as e:
                logger.error(f"No se pudo mandar el aviso a la app ({device.get('device')}): {e}")
                continue
            if response.status_code == 200:
                delivered = True
                continue
            reason = ""
            try:
                reason = response.json().get("reason", "")
            except Exception:
                pass
            if response.status_code == 410 or reason in ("BadDeviceToken", "Unregistered", "DeviceTokenNotForTopic"):
                gone.append(device["token"])
            else:
                logger.error(f"Apple rechazó el aviso ({response.status_code} {reason})")
    for token in gone:
        unregister(token)
    return delivered

"""
La pulsera WHOOP de Nacho: recuperación de hoy, cómo durmió, esfuerzo del día
y entrenamientos recientes (API oficial de WHOOP, v2, solo lectura).

Nacho la conecta él mismo desde el panel (Conexiones → WHOOP → Conectar) con
su cuenta de WHOOP. Quien instala solo crea una vez la app en
developer-dashboard.whoop.com y pega su Client ID y Client Secret en el
apartado Preparación (ver CONFIGURAR_JARVIS.md, paso 12).

WHOOP cambia el refresh token en cada renovación (el anterior deja de valer),
así que el nuevo se guarda en el .env al momento y las renovaciones van de
una en una. Si algo falla, las funciones lanzan una excepción en vez de
inventar datos.
"""
import logging
import os
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

AUTH_URL = "https://api.prod.whoop.com/oauth/oauth2/auth"
TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"
API_BASE = "https://api.prod.whoop.com/developer/v2"
# offline: sin él WHOOP no da refresh token y habría que reconectar cada hora.
SCOPES = "read:recovery read:cycles read:sleep read:workout read:profile offline"

_lock = threading.Lock()
_access_token: Optional[str] = None
_token_expiry = 0.0


class WhoopNotConfigured(Exception):
    pass


def _env(key: str) -> str:
    return os.getenv(key, "").strip()


def app_ready() -> bool:
    return bool(_env("WHOOP_CLIENT_ID") and _env("WHOOP_CLIENT_SECRET"))


def is_configured() -> bool:
    return app_ready() and bool(_env("WHOOP_REFRESH_TOKEN"))


def _save_refresh_token(token: str) -> None:
    import conexiones  # aquí para no importarse mutuamente al arrancar
    conexiones.save_env({"WHOOP_REFRESH_TOKEN": token})


def _store_tokens(data: dict) -> None:
    global _access_token, _token_expiry
    _access_token = data["access_token"]
    _token_expiry = time.time() + int(data.get("expires_in", 3600)) - 60
    if data.get("refresh_token"):
        _save_refresh_token(data["refresh_token"])


def exchange_code(code: str, redirect_uri: str) -> None:
    """Vuelta del «Conectar»: cambia el código por el permiso permanente."""
    response = httpx.post(TOKEN_URL, data={
        "grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri,
        "client_id": _env("WHOOP_CLIENT_ID"), "client_secret": _env("WHOOP_CLIENT_SECRET"),
    }, timeout=15)
    if response.status_code >= 400:
        logger.error(f"WHOOP rechazó el código: {response.status_code} {response.text[:300]}")
        response.raise_for_status()
    data = response.json()
    if not data.get("refresh_token"):
        raise WhoopNotConfigured("WHOOP no ha dado un permiso permanente (falta el permiso offline).")
    with _lock:
        _store_tokens(data)


def _token() -> str:
    if not is_configured():
        raise WhoopNotConfigured("La pulsera WHOOP no está conectada: se conecta en el panel, en Conexiones.")
    with _lock:
        if _access_token and time.time() < _token_expiry:
            return _access_token
        response = httpx.post(TOKEN_URL, data={
            "grant_type": "refresh_token", "refresh_token": _env("WHOOP_REFRESH_TOKEN"),
            "client_id": _env("WHOOP_CLIENT_ID"), "client_secret": _env("WHOOP_CLIENT_SECRET"),
            "scope": "offline",
        }, timeout=15)
        if response.status_code in (400, 401):
            logger.error(f"WHOOP no renovó el permiso: {response.text[:300]}")
            raise WhoopNotConfigured("El permiso de WHOOP ha caducado: hay que volver a conectarla desde el panel.")
        response.raise_for_status()
        _store_tokens(response.json())
        return _access_token


def _get(path: str, params: Optional[dict] = None) -> dict:
    response = httpx.get(f"{API_BASE}{path}", params=params, headers={"Authorization": f"Bearer {_token()}"}, timeout=15)
    response.raise_for_status()
    return response.json()


def _scored(record: Optional[dict]) -> Optional[dict]:
    """WHOOP solo da números cuando ha terminado de calcularlos (SCORED)."""
    if record and record.get("score_state") == "SCORED" and record.get("score"):
        return record["score"]
    return None


def _hours(millis) -> Optional[float]:
    return round(millis / 3_600_000, 1) if millis is not None else None


def zone(recovery_percent: float) -> str:
    # Los colores con los que la propia app de WHOOP muestra la recuperación.
    if recovery_percent >= 67:
        return "verde"
    if recovery_percent >= 34:
        return "amarilla"
    return "roja"


def profile() -> dict:
    data = _get("/user/profile/basic")
    return {"name": " ".join(p for p in (data.get("first_name"), data.get("last_name")) if p), "email": data.get("email")}


def recovery() -> Optional[dict]:
    """Recuperación de hoy (tras la última noche). None si aún no está calculada."""
    records = _get("/recovery", {"limit": 1}).get("records", [])
    score = _scored(records[0] if records else None)
    if not score:
        return None
    return {
        "recovery_percent": score.get("recovery_score"),
        "zone": zone(score.get("recovery_score") or 0),
        "resting_heart_rate": score.get("resting_heart_rate"),
        "hrv_ms": round(score["hrv_rmssd_milli"]) if score.get("hrv_rmssd_milli") is not None else None,
        "spo2_percent": score.get("spo2_percentage"),
        "skin_temp_c": score.get("skin_temp_celsius"),
        "calibrating": score.get("user_calibrating", False),
    }


def last_sleep() -> Optional[dict]:
    """La última noche (las siestas no cuentan)."""
    for record in _get("/activity/sleep", {"limit": 5}).get("records", []):
        if record.get("nap"):
            continue
        score = _scored(record)
        if not score:
            return None
        stages = score.get("stage_summary") or {}
        asleep = sum(stages.get(k) or 0 for k in (
            "total_light_sleep_time_milli", "total_slow_wave_sleep_time_milli", "total_rem_sleep_time_milli"))
        need = score.get("sleep_needed") or {}
        needed = sum(need.get(k) or 0 for k in (
            "baseline_milli", "need_from_sleep_debt_milli", "need_from_recent_strain_milli", "need_from_recent_nap_milli"))
        return {
            "start": record.get("start"),
            "end": record.get("end"),
            "hours_asleep": _hours(asleep),
            "hours_needed": _hours(needed) if needed else None,
            "minutes_asleep": round(asleep / 60_000),
            "minutes_needed": round(needed / 60_000) if needed else None,
            "performance_percent": score.get("sleep_performance_percentage"),
            "efficiency_percent": score.get("sleep_efficiency_percentage"),
            "consistency_percent": score.get("sleep_consistency_percentage"),
            "deep_hours": _hours(stages.get("total_slow_wave_sleep_time_milli")),
            "rem_hours": _hours(stages.get("total_rem_sleep_time_milli")),
            "disturbances": stages.get("disturbance_count"),
            "respiratory_rate": score.get("respiratory_rate"),
        }
    return None


def today_strain() -> Optional[dict]:
    """Esfuerzo del día en curso (escala de WHOOP de 0 a 21)."""
    records = _get("/cycle", {"limit": 1}).get("records", [])
    score = _scored(records[0] if records else None)
    if not score:
        return None
    return {
        "strain": round(score["strain"], 1) if score.get("strain") is not None else None,
        "kcal": round(score["kilojoule"] / 4.184) if score.get("kilojoule") is not None else None,
        "average_heart_rate": score.get("average_heart_rate"),
        "max_heart_rate": score.get("max_heart_rate"),
    }


def recent_workouts(days: int = 7, limit: int = 10) -> list[dict]:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    workouts = []
    for record in _get("/activity/workout", {"limit": min(limit, 25), "start": since}).get("records", []):
        score = _scored(record) or {}
        minutes = None
        try:
            start = datetime.fromisoformat(record["start"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(record["end"].replace("Z", "+00:00"))
            minutes = round((end - start).total_seconds() / 60)
        except (KeyError, TypeError, ValueError, AttributeError):
            pass
        workouts.append({
            "sport": record.get("sport_name"),
            "start": record.get("start"),
            "minutes": minutes,
            "strain": round(score["strain"], 1) if score.get("strain") is not None else None,
            "average_heart_rate": score.get("average_heart_rate"),
            "kcal": round(score["kilojoule"] / 4.184) if score.get("kilojoule") is not None else None,
            "distance_km": round(score["distance_meter"] / 1000, 2) if score.get("distance_meter") else None,
        })
    return workouts


def summary(include_workouts: bool = True) -> dict:
    """Todo junto. Cada parte es None si WHOOP aún no la ha calculado o falla."""
    if not is_configured():
        raise WhoopNotConfigured("La pulsera WHOOP no está conectada: se conecta en el panel, en Conexiones.")
    result = {}
    parts = [("recovery", recovery), ("sleep", last_sleep), ("strain", today_strain)]
    if include_workouts:
        parts.append(("workouts", recent_workouts))
    for key, fetch in parts:
        try:
            result[key] = fetch()
        except WhoopNotConfigured:
            raise
        except Exception as e:
            logger.error(f"Error consultando {key} de WHOOP: {e}")
            result[key] = None
    return result

"""
Integración con la API de Mercedes-Benz (Vehicle Status API) para leer
el estado real del coche: nivel de combustible, autonomía y si está
cerrado.

Requisitos para que esto funcione:
1. Registrarse como desarrollador en https://developer.mercedes-benz.com
2. Crear una app con acceso a la "Vehicle Status API" para el VIN del C63.
3. Generar un refresh token (flujo OAuth2 estándar de Mercedes) y guardarlo
   en MERCEDES_REFRESH_TOKEN dentro del .env, junto con MERCEDES_CLIENT_ID,
   MERCEDES_CLIENT_SECRET y MERCEDES_VIN.

IMPORTANTE: los nombres de recurso usados abajo (fuelstatus, doorlockstatus,
fuelLevelPercent, rangeLiquid, doorLockStatusOverall) son los más comunes en
la documentación pública de Mercedes, pero hay que confirmarlos contra la
documentación real una vez tengas acceso — pueden variar según mercado o
tipo de suscripción. Si un campo no encaja, revisa el JSON crudo que
devuelve la API (queda logueado como error) y ajusta las claves aquí.

Si algo falla (credenciales, red, campo inesperado) estas funciones
devuelven None en vez de inventar datos — nunca hay que mostrarle a Nacho
un nivel de combustible o un estado de cierre que no venga realmente del
coche.
"""
import logging
import time
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

TOKEN_URL = "https://id.mercedes-benz.com/as/token.oauth2"
API_BASE = "https://api.mercedes-benz.com/vehicledata/v2"

_cached_access_token: Optional[str] = None
_cached_token_expiry: float = 0.0


def _get_access_token(client_id: str, client_secret: str, refresh_token: str) -> Optional[str]:
    global _cached_access_token, _cached_token_expiry
    if _cached_access_token and time.time() < _cached_token_expiry:
        return _cached_access_token

    try:
        response = httpx.post(
            TOKEN_URL,
            data={"grant_type": "refresh_token", "refresh_token": refresh_token},
            auth=(client_id, client_secret),
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        _cached_access_token = data["access_token"]
        _cached_token_expiry = time.time() + data.get("expires_in", 3600) - 60
        return _cached_access_token
    except Exception as e:
        logger.error(f"No se pudo renovar el token de Mercedes: {e}")
        return None


def _get_resource(
    vin: str, resource: str, client_id: str, client_secret: str, refresh_token: str
) -> Optional[dict]:
    token = _get_access_token(client_id, client_secret, refresh_token)
    if not token:
        return None
    try:
        response = httpx.get(
            f"{API_BASE}/vehicles/{vin}/resources/{resource}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error consultando '{resource}' de Mercedes: {e}")
        return None


def get_fuel_status(
    vin: str, client_id: str, client_secret: str, refresh_token: str
) -> Optional[dict]:
    """Devuelve {'fuel_percent': float, 'range_km': float} o None si no se pudo consultar."""
    data = _get_resource(vin, "fuelstatus", client_id, client_secret, refresh_token)
    if not data:
        return None
    try:
        return {
            "fuel_percent": data["fuelLevelPercent"]["value"],
            "range_km": data["rangeLiquid"]["value"],
        }
    except (KeyError, TypeError) as e:
        logger.error(f"Formato inesperado en fuelstatus de Mercedes: {e} — datos: {data}")
        return None


def get_lock_status(
    vin: str, client_id: str, client_secret: str, refresh_token: str
) -> Optional[bool]:
    """Devuelve True si está cerrado, False si está abierto, None si no se pudo consultar."""
    data = _get_resource(vin, "doorlockstatus", client_id, client_secret, refresh_token)
    if not data:
        return None
    try:
        return data["doorLockStatusOverall"]["value"] == "LOCKED"
    except (KeyError, TypeError) as e:
        logger.error(f"Formato inesperado en doorlockstatus de Mercedes: {e} — datos: {data}")
        return None

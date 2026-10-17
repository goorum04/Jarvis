"""
Integración con la API de Mercedes-Benz (Vehicle Status API) para leer
el estado real del coche: nivel de combustible, autonomía y si está
cerrado.

Requisitos para que esto funcione:
1. Registrarse como desarrollador en https://developer.mercedes-benz.com
2. Crear una app con acceso a la "Vehicle Status API" para el VIN del C63.
3. Poner MERCEDES_CLIENT_ID y MERCEDES_CLIENT_SECRET en el .env (o en el
   panel), y que Nacho pulse «Conectar» en Mercedes me desde la sección
   Conexiones del panel: eso guarda MERCEDES_REFRESH_TOKEN y MERCEDES_VIN.

IMPORTANTE: los nombres de recurso usados abajo (fuelstatus, doorlockstatus,
fuelLevelPercent, rangeLiquid, doorLockStatusOverall, tires,
tirepressurefrontleft...) son los más comunes en
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
import os
import time
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# Inicio de sesión de Mercedes me (lo usa el botón «Conectar» del panel). Si el
# portal de desarrolladores indica otras direcciones o permisos, se cambian en
# el .env sin tocar el código.
AUTH_URL = os.getenv("MERCEDES_AUTH_URL", "https://id.mercedes-benz.com/as/authorization.oauth2")
TOKEN_URL = os.getenv("MERCEDES_TOKEN_URL", "https://id.mercedes-benz.com/as/token.oauth2")
SCOPES = os.getenv(
    "MERCEDES_SCOPES",
    "mb:vehicle:mbdata:fuelstatus mb:vehicle:mbdata:vehiclelock mb:vehicle:mbdata:vehiclestatus offline_access",
)
API_BASE = "https://api.mercedes-benz.com/vehicledata/v2"

_cached_access_token: Optional[str] = None
_cached_token_expiry: float = 0.0
# Si Mercedes entrega un refresh token nuevo al renovar, el anterior deja de
# valer: se usa (y se guarda en el .env) el último recibido.
_latest_refresh_token: Optional[str] = None


def _get_access_token(client_id: str, client_secret: str, refresh_token: str) -> Optional[str]:
    global _cached_access_token, _cached_token_expiry
    if _cached_access_token and time.time() < _cached_token_expiry:
        return _cached_access_token

    global _latest_refresh_token
    refresh_token = _latest_refresh_token or refresh_token
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
        new_refresh = data.get("refresh_token")
        if new_refresh and new_refresh != refresh_token:
            _latest_refresh_token = new_refresh
            import conexiones  # aquí para no importarse mutuamente al arrancar
            conexiones.save_env({"MERCEDES_REFRESH_TOKEN": new_refresh})
        return _cached_access_token
    except Exception as e:
        logger.error(f"No se pudo renovar el token de Mercedes: {e}")
        return None


def _get_resource(
    vin: str, resource: str, client_id: str, client_secret: str, refresh_token: str,
    kind: str = "resources",
) -> Optional[dict]:
    token = _get_access_token(client_id, client_secret, refresh_token)
    if not token:
        return None
    try:
        response = httpx.get(
            f"{API_BASE}/vehicles/{vin}/{kind}/{resource}",
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


TIRES = {
    "front_left": "tirepressurefrontleft",
    "front_right": "tirepressurefrontright",
    "rear_left": "tirepressurerearleft",
    "rear_right": "tirepressurerearright",
}
TIRE_WARNING = "tirewarningprw"


def _flatten(data) -> dict:
    """Mercedes devuelve los recursos como {nombre: {"value": ...}} o como una
    lista de esos diccionarios, según la API: se aceptan las dos formas."""
    items = data if isinstance(data, list) else [data]
    flat = {}
    for item in items:
        if isinstance(item, dict):
            for key, value in item.items():
                flat[key.lower()] = value.get("value") if isinstance(value, dict) else value
    return flat


def get_tire_status(
    vin: str, client_id: str, client_secret: str, refresh_token: str
) -> Optional[dict]:
    """Presión de cada rueda en bar y si el coche marca aviso de presión.
    None si no se pudo consultar."""
    data = _get_resource(vin, "tires", client_id, client_secret, refresh_token, kind="containers")
    if not data:
        return None
    flat = _flatten(data)
    try:
        # Mercedes da la presión en kPa: 100 kPa = 1 bar.
        pressures = {wheel: round(float(flat[name]) / 100, 2) for wheel, name in TIRES.items() if flat.get(name) is not None}
    except (TypeError, ValueError) as e:
        logger.error(f"Formato inesperado en la presión de neumáticos: {e} — datos: {data}")
        return None
    if not pressures:
        logger.error(f"Sin datos de presión de neumáticos en la respuesta de Mercedes: {data}")
        return None
    warning = flat.get(TIRE_WARNING)
    return {
        "bar": pressures,
        # Cualquier valor distinto de 0/false/"0" se trata como aviso encendido.
        "warning": str(warning).lower() not in ("0", "false", "none", "") if warning is not None else None,
    }


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

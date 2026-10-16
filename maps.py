"""
Tiempos de viaje con tráfico real (Google Routes API) y enlaces de navegación
para CarPlay. Requiere GOOGLE_MAPS_API_KEY (Google Cloud Console → activar
"Routes API"; es de pago por uso, unos céntimos al día con este uso).
"""
import logging
import os
from typing import Optional
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"


def is_configured() -> bool:
    return bool(os.getenv("GOOGLE_MAPS_API_KEY"))


def _waypoint(place) -> dict:
    if isinstance(place, (tuple, list)):
        return {"location": {"latLng": {"latitude": float(place[0]), "longitude": float(place[1])}}}
    return {"address": place}


def travel_minutes(origin, destination: str) -> Optional[dict]:
    """origin: (lat, lon) o dirección. Devuelve {'minutes', 'km'} o None si no se pudo calcular."""
    key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not key:
        return None
    try:
        response = httpx.post(
            ROUTES_URL,
            headers={"X-Goog-Api-Key": key, "X-Goog-FieldMask": "routes.duration,routes.distanceMeters"},
            json={
                "origin": _waypoint(origin),
                "destination": _waypoint(destination),
                "travelMode": "DRIVE",
                "routingPreference": "TRAFFIC_AWARE",
                "languageCode": "es-ES",
            },
            timeout=10,
        )
        response.raise_for_status()
        routes = response.json().get("routes") or []
        if not routes:
            return None
        seconds = int(str(routes[0]["duration"]).rstrip("s"))
        return {"minutes": round(seconds / 60), "km": round(routes[0].get("distanceMeters", 0) / 1000, 1)}
    except Exception as e:
        logger.error(f"Error calculando la ruta a '{destination}': {e}")
        return None


def navigation_url(destination: str) -> str:
    """Enlace que abre la navegación en la app elegida (NAV_APP: apple, google o waze)."""
    app = os.getenv("NAV_APP", "apple").lower()
    encoded = quote(destination)
    if app == "google":
        return f"comgooglemaps://?daddr={encoded}&directionsmode=driving"
    if app == "waze":
        return f"https://waze.com/ul?q={encoded}&navigate=yes"
    return f"maps://?daddr={encoded}&dirflg=d"

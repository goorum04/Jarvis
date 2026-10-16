"""
Clima actual vía Open-Meteo (gratis, sin API key). HOME_LAT/HOME_LON en el
.env marcan la ubicación de referencia (p. ej. la de casa de Nacho).
"""
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


def get_current_temperature(lat: float, lon: float) -> Optional[float]:
    try:
        response = httpx.get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": lat, "longitude": lon, "current": "temperature_2m"},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()["current"]["temperature_2m"]
    except Exception as e:
        logger.error(f"Error consultando el clima: {e}")
        return None

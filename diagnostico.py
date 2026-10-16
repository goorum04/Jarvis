"""
Comprueba cada pieza de JARVIS contra los servicios reales y dice qué funciona,
qué falta configurar y cómo arreglarlo. Se ejecuta en el PC de JARVIS:

    python diagnostico.py                  # revisa todo
    python diagnostico.py --probar-avisos  # además manda un aviso de prueba al iPhone

Ninguna comprobación gasta créditos de IA ni de voz, ni cambia nada en las
cuentas de Nacho (salvo el aviso de prueba, si se pide).
"""
import os
import sys
from typing import Callable

from dotenv import load_dotenv

load_dotenv()

import car  # noqa: E402
import google_services  # noqa: E402
import maps  # noqa: E402
import notifier  # noqa: E402
import store  # noqa: E402
import weather  # noqa: E402

OK, AVISO, FALLO, APAGADO = "ok", "aviso", "fallo", "sin configurar"
ICONS = {OK: "✅", AVISO: "⚠️ ", FALLO: "❌", APAGADO: "➖"}


def _result(name, status, detail, fix=""):
    return {"name": name, "status": status, "detail": detail, "fix": fix}


def _env(name: str) -> str:
    """Valor del .env, tratando como vacío el texto de ejemplo (sk-ant-..., sk_...)."""
    value = os.getenv(name, "").strip()
    return "" if value.endswith("...") else value


def _short_error(e: Exception) -> str:
    """Los SDK incluyen cabeceras HTTP enteras en el error: se deja solo lo útil."""
    status = getattr(e, "status_code", None)
    body = getattr(e, "body", None)
    message = body.get("detail", {}).get("message") if isinstance(body, dict) and isinstance(body.get("detail"), dict) else None
    if status:
        return f"HTTP {status}" + (f": {message}" if message else "")
    return str(e)[:200]


def check_token():
    token = os.getenv("JARVIS_API_TOKEN", "")
    if not token:
        return _result("Token de acceso", FALLO, "JARVIS_API_TOKEN está vacío: cualquiera podría usar JARVIS.",
                       "Pon en .env una contraseña larga y aleatoria (guía, paso 1).")
    if len(token) < 24:
        return _result("Token de acceso", AVISO, f"El token tiene solo {len(token)} caracteres.",
                       "Usa al menos 24 caracteres aleatorios.")
    return _result("Token de acceso", OK, "Configurado.")


def check_claude():
    import anthropic
    model = os.getenv("JARVIS_MODEL", "claude-opus-5-5")
    if not _env("CLAUDE_API_KEY"):
        return _result("Claude (cerebro)", FALLO, "Falta CLAUDE_API_KEY.", "Créala en console.anthropic.com (guía, paso 1).")
    try:
        anthropic.Anthropic(api_key=_env("CLAUDE_API_KEY")).models.retrieve(model)
        return _result("Claude (cerebro)", OK, f"Clave válida, modelo {model} disponible.")
    except anthropic.AuthenticationError:
        return _result("Claude (cerebro)", FALLO, "La clave de Claude no es válida.", "Revisa CLAUDE_API_KEY.")
    except anthropic.NotFoundError:
        return _result("Claude (cerebro)", FALLO, f"El modelo {model} no existe para esta cuenta.", "Revisa JARVIS_MODEL.")
    except Exception as e:
        return _result("Claude (cerebro)", FALLO, f"No se pudo conectar: {e}")


def check_voice():
    from elevenlabs.client import ElevenLabs
    key = _env("ELEVENLABS_API_KEY")
    voice_id = os.getenv("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")
    if not key:
        return _result("Voz (ElevenLabs)", AVISO, "Sin ELEVENLABS_API_KEY: JARVIS responde con la voz de Siri.",
                       "Créala en elevenlabs.io (guía, paso 1).")
    try:
        voice = ElevenLabs(api_key=key).voices.get(voice_id)
        return _result("Voz (ElevenLabs)", OK, f"Clave válida, voz «{voice.name}».")
    except Exception as e:
        return _result("Voz (ElevenLabs)", FALLO, f"Fallo con la clave o la voz {voice_id}: {_short_error(e)}",
                       "Revisa ELEVENLABS_API_KEY y ELEVENLABS_VOICE_ID.")


def check_google():
    if not google_services.is_configured():
        return [_result("Gmail y Calendar", APAGADO, "Sin conectar.",
                        "Ejecuta autorizar_google.py (guía, paso 2).")]
    results = []
    try:
        profile = google_services._gmail().users().getProfile(userId="me").execute()
        results.append(_result("Gmail", OK, f"Conectado como {profile.get('emailAddress')}."))
    except Exception as e:
        results.append(_result("Gmail", FALLO, str(e), "Vuelve a ejecutar autorizar_google.py."))
    try:
        google_services._calendar().events().list(calendarId="primary", maxResults=1).execute()
        results.append(_result("Google Calendar", OK, "Conectado."))
    except Exception as e:
        results.append(_result("Google Calendar", FALLO, str(e), "Vuelve a ejecutar autorizar_google.py."))
    try:
        google_services._docs()
        results.append(_result("Google Docs", OK, "Permiso para crear documentos concedido."))
    except google_services.GoogleNotConfigured as e:
        results.append(_result("Google Docs", AVISO, str(e), "Ejecuta de nuevo autorizar_google.py."))
    return results


def check_mercedes():
    keys = ["MERCEDES_CLIENT_ID", "MERCEDES_CLIENT_SECRET", "MERCEDES_REFRESH_TOKEN", "MERCEDES_VIN"]
    if not all(os.getenv(k) for k in keys):
        return [_result("Mercedes", APAGADO, "Sin credenciales.", "Guía, paso 4.")]
    args = [os.getenv(k) for k in ("MERCEDES_VIN", "MERCEDES_CLIENT_ID", "MERCEDES_CLIENT_SECRET", "MERCEDES_REFRESH_TOKEN")]
    fix = "Mira el error en la consola (sale el JSON de Mercedes) y ajusta los nombres en car.py."
    fuel, locked, tires = car.get_fuel_status(*args), car.get_lock_status(*args), car.get_tire_status(*args)
    return [
        _result("Mercedes: combustible", OK if fuel else FALLO,
                f"{fuel['fuel_percent']:.0f}%, {fuel['range_km']:.0f} km." if fuel else "No se pudo leer.", "" if fuel else fix),
        _result("Mercedes: cierre", OK if locked is not None else FALLO,
                ("Cerrado." if locked else "Abierto.") if locked is not None else "No se pudo leer.",
                "" if locked is not None else fix),
        _result("Mercedes: neumáticos", OK if tires else FALLO,
                ", ".join(f"{w}: {b} bar" for w, b in tires["bar"].items()) if tires else "No se pudo leer.",
                "" if tires else fix),
    ]


def check_calls():
    import phone_calls
    if not phone_calls.is_configured():
        return _result("Llamadas en su nombre", APAGADO, "Sin agente de voz ni número.",
                       "Guía, paso 11: número de Twilio y ./jarvis.sh llamadas.")
    try:
        calls = phone_calls._client().conversational_ai
        calls.agents.get(os.getenv("ELEVENLABS_AGENT_ID"))
        number = calls.phone_numbers.get(os.getenv("ELEVENLABS_PHONE_NUMBER_ID"))
        return _result("Llamadas en su nombre", OK, f"Agente listo; llama desde {getattr(number, 'phone_number', 'el número configurado')}.")
    except Exception as e:
        return _result("Llamadas en su nombre", FALLO, _short_error(e),
                       "Vuelve a ejecutar ./jarvis.sh llamadas (revisa los datos de Twilio en .env).")


def check_store():
    if not store.is_configured():
        return _result("Tienda online", APAGADO, "Sin conectar.", "Guía, paso 5.")
    try:
        sales = store.sales_summary("today", os.getenv("TIMEZONE", "Europe/Madrid"))
        return _result("Tienda online", OK, f"{store.platform()}: hoy {sales['orders']} pedidos.")
    except Exception as e:
        return _result("Tienda online", FALLO, str(e), "Revisa las credenciales de la tienda en .env.")


def check_maps():
    if not maps.is_configured():
        return _result("Tráfico y rutas", APAGADO, "Sin GOOGLE_MAPS_API_KEY: no hay aviso de hora de salir.", "Guía, paso 3.")
    origin = os.getenv("HOME_ADDRESS") or "Andorra la Vella"
    destination = os.getenv("WORK_ADDRESS") or "Escaldes-Engordany"
    route = maps.travel_minutes(origin, destination)
    if not route:
        return _result("Tráfico y rutas", FALLO, "No se pudo calcular una ruta de prueba.",
                       "Comprueba que la Routes API está activada para esa clave.")
    return _result("Tráfico y rutas", OK, f"Casa → oficina: {route['minutes']} min ({route['km']} km) ahora mismo.")


def check_weather():
    lat, lon = os.getenv("HOME_LAT"), os.getenv("HOME_LON")
    if not (lat and lon):
        return _result("Tiempo", APAGADO, "Sin HOME_LAT/HOME_LON.", "Pon las coordenadas de casa en .env.")
    temp = weather.get_current_temperature(float(lat), float(lon))
    return _result("Tiempo", OK if temp is not None else FALLO,
                   f"Fuera hacen {temp:.0f} grados." if temp is not None else "No se pudo consultar.")


def check_notifications(send_test: bool):
    if not notifier.is_configured():
        return _result("Avisos al iPhone", AVISO, "Sin Pushcut ni ntfy: los avisos solo salen en la pantalla.", "Guía, paso 7.")
    if not send_test:
        return _result("Avisos al iPhone", OK, "Configurados (usa --probar-avisos para mandar uno de prueba).")
    delivered = notifier.notify("JARVIS", "Aviso de prueba: si lees esto, los avisos funcionan.")
    return _result("Avisos al iPhone", OK if delivered else FALLO,
                   "Aviso de prueba enviado: revisa el iPhone." if delivered else "No se pudo entregar.",
                   "" if delivered else "Revisa PUSHCUT_SECRET / NTFY_TOPIC.")


def check_public_url():
    import httpx
    url = os.getenv("PUBLIC_URL", "").rstrip("/")
    if not url:
        return _result("Acceso desde fuera", APAGADO, "Sin PUBLIC_URL: el iPhone no puede llegar a JARVIS.",
                       "Instala Tailscale y vuelve a ejecutar instalar.command (guía, paso 6).")
    try:
        response = httpx.get(f"{url}/health", timeout=10)
        response.raise_for_status()
        return _result("Acceso desde fuera", OK, f"{url} responde con HTTPS.")
    except Exception as e:
        return _result("Acceso desde fuera", FALLO, f"{url} no responde: {_short_error(e)}",
                       "Con Tailscale: comprueba que está abierto y que Funnel sigue activo "
                       "(tailscale funnel status). Con dominio propio: revisa el DNS, Caddy y el puerto 443.")


def run_checks(send_test: bool = False) -> list[dict]:
    checks: list[Callable] = [
        check_token, check_claude, check_voice, check_google, check_mercedes, check_calls, check_store,
        check_maps, check_weather, lambda: check_notifications(send_test), check_public_url,
    ]
    results = []
    for check in checks:
        try:
            outcome = check()
        except Exception as e:
            outcome = _result(getattr(check, "__name__", "comprobación"), FALLO, f"Error inesperado: {e}")
        results.extend(outcome if isinstance(outcome, list) else [outcome])
    return results


def main():
    results = run_checks(send_test="--probar-avisos" in sys.argv)
    print("\n  JARVIS — comprobación de puesta en marcha\n")
    for r in results:
        print(f"  {ICONS[r['status']]} {r['name']}: {r['detail']}")
        if r["fix"] and r["status"] != OK:
            print(f"      → {r['fix']}")
    failures = sum(r["status"] == FALLO for r in results)
    print(f"\n  {sum(r['status'] == OK for r in results)} bien, {failures} con fallos, "
          f"{sum(r['status'] in (AVISO, APAGADO) for r in results)} por configurar o mejorar.\n")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()

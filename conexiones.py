"""
Conexiones que Nacho hace él mismo desde el panel (botón «Conexiones»), sin
pasarle claves ni contraseñas a nadie:

- Google (Gmail, Calendar y Docs) y Mercedes me: botón «Conectar», inicia
  sesión con su cuenta y acepta los permisos (OAuth).
- WooCommerce: botón «Conectar», aprueba el acceso de solo lectura en su
  propia tienda y WooCommerce le entrega la clave directamente a JARVIS.
- El resto (Claude, voz, avisos, mapas, Shopify, llamadas): pega la clave en
  un formulario del panel.

Todo va del navegador de Nacho directo a su Mac: las claves se guardan en el
.env y los permisos de Google en google_token.json. El panel nunca recibe de
vuelta una clave guardada; solo ve si está puesta o no.

Lo único que prepara una vez quien instala JARVIS es la «identidad» de la app
en Google y en Mercedes (el cliente OAuth): ver CONFIGURAR_JARVIS.md.
"""
import json
import logging
import os
import re
import secrets
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode

import httpx

import car
import google_services
import whoop

logger = logging.getLogger(__name__)

# Google puede devolver menos permisos de los pedidos (Nacho puede desmarcar
# alguno en su pantalla). Sin esto, la librería lo trataría como un error.
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")

BASE_DIR = Path(__file__).parent
ENV_FILE = BASE_DIR / ".env"
# Datos no secretos para el panel: con qué cuenta se conectó cada cosa y cuándo.
META_FILE = BASE_DIR / "conexiones.json"

PENDING_TTL = 15 * 60  # segundos que tiene Nacho para completar un «Conectar»
_pending: dict[str, dict] = {}

ENV_NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")
LOCAL_ORIGIN = re.compile(r"^http://(localhost|127\.0\.0\.1)(:\d+)?$")


class ConexionError(Exception):
    """Algo que Nacho puede entender y arreglar (se le muestra tal cual)."""


# ── .env ──────────────────────────────────────────────────────────────────────

def _env_line(key: str, value: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_\-.:/@+=,]*", value):
        return f"{key}={value}"
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'{key}="{escaped}"'


def save_env(values: dict[str, str]) -> None:
    """Escribe o cambia variables del .env y las aplica ya a este proceso."""
    lines = ENV_FILE.read_text().splitlines() if ENV_FILE.exists() else []
    for key, value in values.items():
        if not ENV_NAME.match(key):
            raise ConexionError(f"Nombre de ajuste no válido: {key}")
        value = value.strip()
        if "\n" in value or "\r" in value:
            raise ConexionError("Una clave no puede tener saltos de línea.")
        line = _env_line(key, value)
        for i, existing in enumerate(lines):
            if existing.split("=", 1)[0].strip() == key:
                lines[i] = line
                break
        else:
            lines.append(line)
        os.environ[key] = value
    ENV_FILE.write_text("\n".join(lines) + "\n")
    ENV_FILE.chmod(0o600)


def clear_env(keys: list[str]) -> None:
    save_env({key: "" for key in keys})


def _env(key: str) -> str:
    value = os.getenv(key, "").strip()
    return "" if value.endswith("...") else value  # texto de ejemplo del .env.example


# ── Datos para el panel ──────────────────────────────────────────────────────

def _meta() -> dict:
    try:
        return json.loads(META_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _set_meta(service: str, info: Optional[dict]) -> None:
    meta = _meta()
    if info is None:
        meta.pop(service, None)
    else:
        meta[service] = {**info, "since": datetime.now().isoformat(timespec="minutes")}
    META_FILE.write_text(json.dumps(meta, ensure_ascii=False, indent=2))


def _field(env: str, label: str, secret: bool = True, help: str = "", optional: bool = False) -> dict:
    return {"env": env, "label": label, "secret": secret, "help": help, "optional": optional}


# kind: "oauth" (botón Conectar con su cuenta), "woo" (aprobación en la tienda)
# o "keys" (formulario). Los campos de "setup" son la identidad de la app que
# prepara una vez quien instala; los de "fields", los datos del propio Nacho.
SERVICES = [
    {
        "id": "google", "name": "Gmail, Calendar y Docs", "kind": "oauth",
        "what": "Leer y responder su correo, ver y crear citas en su agenda y crear documentos.",
        "note": "Si Google avisa de que la app no está verificada, es normal: es la app privada de JARVIS. "
                "Pulsa «Configuración avanzada» → «Ir a JARVIS» y deja marcadas todas las casillas.",
        "setup": [
            _field("GOOGLE_OAUTH_CLIENT_ID", "ID de cliente OAuth de Google", secret=False),
            _field("GOOGLE_OAUTH_CLIENT_SECRET", "Secreto del cliente OAuth de Google"),
        ],
        "fields": [],
    },
    {
        "id": "mercedes", "name": "Mercedes me", "kind": "oauth",
        "what": "Consultar combustible, autonomía, cierre y presión de neumáticos del coche.",
        "setup": [
            _field("MERCEDES_CLIENT_ID", "Client ID del proyecto de Mercedes", secret=False),
            _field("MERCEDES_CLIENT_SECRET", "Client Secret del proyecto de Mercedes"),
        ],
        "fields": [
            _field("MERCEDES_VIN", "Número de bastidor (VIN)", secret=False,
                   help="Campo (E) del permiso de circulación; empieza por W1K."),
        ],
    },
    {
        "id": "whoop", "name": "Pulsera WHOOP", "kind": "oauth",
        "what": "Saber cómo ha dormido, su recuperación de hoy, el esfuerzo del día y sus entrenamientos.",
        "setup": [
            _field("WHOOP_CLIENT_ID", "Client ID de la app de WHOOP", secret=False),
            _field("WHOOP_CLIENT_SECRET", "Client Secret de la app de WHOOP"),
        ],
        "fields": [],
    },
    {
        "id": "woocommerce", "name": "Tienda WooCommerce", "kind": "woo",
        "what": "Ventas, pedidos y avisos de la tienda (solo lectura).",
        "setup": [],
        "fields": [
            _field("WOO_URL", "Dirección de la tienda", secret=False, help="Por ejemplo https://mitienda.com"),
        ],
    },
    {
        "id": "shopify", "name": "Tienda Shopify", "kind": "keys",
        "what": "Ventas, pedidos y avisos de la tienda (solo lectura).",
        "link": "https://help.shopify.com/es/manual/apps/app-types/custom-apps",
        "setup": [],
        "fields": [
            _field("SHOPIFY_SHOP", "Dirección de la tienda", secret=False, help="Por ejemplo mitienda.myshopify.com"),
            _field("SHOPIFY_ACCESS_TOKEN", "Token de la app (permisos read_orders y read_products)"),
        ],
    },
    {
        "id": "casa", "name": "Casa y trabajo", "kind": "keys",
        "what": "Para el tiempo, el tráfico, la hora de salir y «llévame a casa» o «a la oficina».",
        "setup": [],
        "fields": [
            _field("HOME_ADDRESS", "Dirección de casa", secret=False),
            _field("WORK_ADDRESS", "Dirección de la oficina", secret=False, optional=True),
            _field("HOME_LAT", "Latitud de casa", secret=False,
                   help="En Google Maps, mantén pulsada tu casa: salen dos números; el primero es la latitud."),
            _field("HOME_LON", "Longitud de casa", secret=False, help="El segundo número."),
        ],
    },
    {
        "id": "claude", "name": "Cerebro (Claude)", "kind": "keys",
        "what": "La inteligencia de JARVIS. Sin esto no puede responder.",
        "link": "https://console.anthropic.com/settings/keys",
        "setup": [],
        "fields": [_field("CLAUDE_API_KEY", "API key de Anthropic")],
    },
    {
        "id": "voz", "name": "Voz (ElevenLabs)", "kind": "keys",
        "what": "La voz propia de JARVIS. Sin esto responde con la voz de Siri.",
        "link": "https://elevenlabs.io/app/settings/api-keys",
        "setup": [],
        "fields": [
            _field("ELEVENLABS_API_KEY", "API key de ElevenLabs"),
            _field("ELEVENLABS_VOICE_ID", "ID de la voz", secret=False, optional=True,
                   help="Vacío = la voz de serie."),
        ],
    },
    {
        "id": "avisos", "name": "Avisos al iPhone", "kind": "keys",
        "what": "Que JARVIS le avise sin que pregunte: recordatorios, gasolina, correo importante.",
        "link": "https://www.pushcut.io",
        "setup": [],
        "fields": [
            _field("PUSHCUT_SECRET", "Secret de Pushcut", optional=True,
                   help="App Pushcut → Ajustes → API."),
            _field("PUSHCUT_NOTIFICATION", "Nombre de la notificación en Pushcut", secret=False, optional=True),
            _field("NTFY_TOPIC", "Tema de ntfy (alternativa gratuita)", optional=True),
        ],
    },
    {
        "id": "mapas", "name": "Tráfico y rutas", "kind": "keys",
        "what": "Avisarle de cuándo salir hacia sus citas según el tráfico.",
        "link": "https://console.cloud.google.com/google/maps-apis/credentials",
        "setup": [],
        "fields": [_field("GOOGLE_MAPS_API_KEY", "Clave de Google Maps (Routes API)")],
    },
    {
        "id": "llamadas", "name": "Llamadas en su nombre", "kind": "keys",
        "what": "Que JARVIS llame a restaurantes y negocios para reservar por él.",
        "link": "https://console.twilio.com",
        "setup": [],
        "fields": [
            _field("TWILIO_ACCOUNT_SID", "Account SID de Twilio", secret=False),
            _field("TWILIO_AUTH_TOKEN", "Auth Token de Twilio"),
            _field("TWILIO_PHONE_NUMBER", "Número de JARVIS en Twilio", secret=False, help="Con prefijo, p. ej. +34…"),
        ],
    },
]
_BY_ID = {s["id"]: s for s in SERVICES}


def _service(service_id: str) -> dict:
    if service_id not in _BY_ID:
        raise ConexionError("Esa conexión no existe.")
    return _BY_ID[service_id]


def _google_client_config() -> Optional[dict]:
    # El cliente «Aplicación web» pegado en el panel sirve también desde el
    # iPhone; el google_credentials.json antiguo («App de escritorio») solo
    # funciona con el panel abierto en el propio Mac.
    client_id, client_secret = _env("GOOGLE_OAUTH_CLIENT_ID"), _env("GOOGLE_OAUTH_CLIENT_SECRET")
    if client_id and client_secret:
        return {"web": {
            "client_id": client_id, "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }}
    if google_services.CLIENT_SECRETS_FILE.exists():
        return json.loads(google_services.CLIENT_SECRETS_FILE.read_text())
    return None


def _connected(service_id: str) -> bool:
    if service_id == "google":
        return google_services.is_configured()
    if service_id == "mercedes":
        return bool(_env("MERCEDES_REFRESH_TOKEN") and _env("MERCEDES_VIN"))
    if service_id == "whoop":
        return whoop.is_configured()
    if service_id == "woocommerce":
        return bool(_env("WOO_URL") and _env("WOO_CONSUMER_KEY") and _env("WOO_CONSUMER_SECRET"))
    if service_id == "shopify":
        return bool(_env("SHOPIFY_SHOP") and _env("SHOPIFY_ACCESS_TOKEN"))
    if service_id == "avisos":
        return bool(_env("PUSHCUT_SECRET") or _env("NTFY_TOPIC"))
    if service_id == "llamadas":
        return bool(_env("ELEVENLABS_AGENT_ID") and _env("ELEVENLABS_PHONE_NUMBER_ID"))
    return all(_env(f["env"]) for f in _BY_ID[service_id]["fields"] if not f["optional"])


def _ready(service: dict) -> bool:
    """¿Está preparada la identidad de la app para poder darle a «Conectar»?"""
    if service["id"] == "google":
        return _google_client_config() is not None
    return all(_env(f["env"]) for f in service["setup"])


def _public_field(field: dict) -> dict:
    value = _env(field["env"])
    # Las claves nunca salen del Mac: el panel solo sabe si están puestas.
    return {**field, "set": bool(value), "value": "" if field["secret"] else value}


def list_services() -> list[dict]:
    meta = _meta()
    result = []
    for service in SERVICES:
        info = {
            **{k: v for k, v in service.items() if k not in ("setup", "fields")},
            "setup": [_public_field(f) for f in service["setup"]],
            "fields": [_public_field(f) for f in service["fields"]],
            "ready": _ready(service),
            "connected": _connected(service["id"]),
            "account": meta.get(service["id"], {}).get("account"),
            "since": meta.get(service["id"], {}).get("since"),
        }
        if service["id"] == "woocommerce":
            info["needs_public_url"] = not _env("PUBLIC_URL").startswith("https://")
        if service["id"] == "llamadas":
            info["keys_saved"] = all(_env(f["env"]) for f in service["fields"])
        result.append(info)
    return result


def save_fields(service_id: str, values: dict[str, str]) -> bool:
    """Guarda lo que Nacho ha escrito en el formulario. Un campo vacío no borra
    lo que ya había (el panel nunca muestra las claves guardadas). Devuelve
    True si algo ha cambiado (y por tanto hay que reiniciar JARVIS)."""
    service = _service(service_id)
    allowed = {f["env"] for f in service["setup"] + service["fields"]}
    changes = {}
    for key, value in values.items():
        if key not in allowed:
            raise ConexionError(f"{key} no pertenece a {service['name']}.")
        if isinstance(value, str) and value.strip():
            changes[key] = value.strip()
    for key, name, low, high in (("HOME_LAT", "La latitud", -90, 90), ("HOME_LON", "La longitud", -180, 180)):
        if key in changes:
            try:
                value = float(changes[key].replace(",", "."))
            except ValueError:
                raise ConexionError(f"{name} tiene que ser un número, por ejemplo 42.5078.")
            if not low <= value <= high:
                raise ConexionError("Ese número no es una coordenada válida.")
            changes[key] = str(value)
    if "WOO_URL" in changes:
        changes["WOO_URL"] = _normalize_store_url(changes["WOO_URL"])
    if "SHOPIFY_SHOP" in changes:
        changes["SHOPIFY_SHOP"] = changes["SHOPIFY_SHOP"].replace("https://", "").replace("http://", "").strip("/")
    if service_id == "shopify" and changes:
        changes["STORE_PLATFORM"] = "shopify"
    if not changes:
        return False
    save_env(changes)
    return True


def disconnect(service_id: str) -> bool:
    """Quita el permiso o las claves de su cuenta (no toca la identidad de la app)."""
    service = _service(service_id)
    if service_id == "google":
        google_services.TOKEN_FILE.unlink(missing_ok=True)
        _set_meta("google", None)
        return False
    keys = [f["env"] for f in service["fields"]]
    if service_id == "mercedes":
        keys = ["MERCEDES_REFRESH_TOKEN"]
    elif service_id == "whoop":
        keys = ["WHOOP_REFRESH_TOKEN"]
    elif service_id == "woocommerce":
        keys += ["WOO_CONSUMER_KEY", "WOO_CONSUMER_SECRET"]
    elif service_id == "llamadas":
        keys += ["ELEVENLABS_PHONE_NUMBER_ID"]
    if service_id in ("woocommerce", "shopify") and os.getenv("STORE_PLATFORM", "").lower() == service_id:
        keys.append("STORE_PLATFORM")
    clear_env(keys)
    _set_meta(service_id, None)
    return service_id != "whoop"  # WHOOP lee su permiso al momento: no hace falta reiniciar


# ── «Conectar»: inicio y vuelta del inicio de sesión ─────────────────────────

def callback_base(origin: str) -> str:
    """Dirección a la que Google o Mercedes devuelven a Nacho tras aceptar. Tiene
    que ser la misma desde la que abrió el panel, y solo se aceptan la del propio
    Mac o la pública de JARVIS (así nadie puede desviar el permiso a otro sitio)."""
    origin = (origin or "").rstrip("/")
    public = _env("PUBLIC_URL").rstrip("/")
    if origin and (origin == public or LOCAL_ORIGIN.match(origin)):
        return origin
    raise ConexionError("Abre el panel desde la dirección de JARVIS (la de Tailscale o la del propio Mac).")


def _new_pending(service_id: str, **data) -> str:
    now = time.time()
    for key in [k for k, v in _pending.items() if now - v["created"] > PENDING_TTL]:
        del _pending[key]
    state = secrets.token_urlsafe(24)
    _pending[state] = {"service": service_id, "created": now, **data}
    return state


def _take_pending(state: str, service_id: str) -> dict:
    pending = _pending.pop(state or "", None)
    if not pending or pending["service"] != service_id or time.time() - pending["created"] > PENDING_TTL:
        raise ConexionError("El enlace de conexión ha caducado o no es válido. Vuelve a pulsar «Conectar».")
    return pending


def pending_origin(state: str, service_id: str) -> Optional[str]:
    """Desde dónde abrió Nacho el panel al pulsar «Conectar» (None si el enlace no vale)."""
    pending = _pending.get(state or "")
    return pending["origin"] if pending and pending["service"] == service_id else None


def cancel(state: str) -> None:
    _pending.pop(state or "", None)


def start(service_id: str, origin: str) -> str:
    """Devuelve la dirección a la que hay que mandar a Nacho para que acepte."""
    service = _service(service_id)
    if service["kind"] == "keys":
        raise ConexionError(f"{service['name']} se conecta pegando la clave, no con un botón.")
    if not _ready(service):
        raise ConexionError(f"Falta preparar {service['name']}: lo hace una vez quien instala JARVIS.")
    base = callback_base(origin)

    if service_id == "google":
        from google_auth_oauthlib.flow import Flow
        redirect_uri = f"{base}/api/conexiones/google/callback"
        flow = Flow.from_client_config(_google_client_config(), scopes=google_services.SCOPES, redirect_uri=redirect_uri)
        url, state = flow.authorization_url(access_type="offline", prompt="consent", include_granted_scopes="true")
        _pending[state] = {"service": "google", "created": time.time(), "flow": flow, "origin": base}
        return url

    if service_id == "mercedes":
        if not _env("MERCEDES_VIN"):
            raise ConexionError("Escribe primero el número de bastidor (VIN) y guárdalo.")
        redirect_uri = f"{base}/api/conexiones/mercedes/callback"
        state = _new_pending("mercedes", redirect_uri=redirect_uri, origin=base)
        return f"{car.AUTH_URL}?" + urlencode({
            "response_type": "code", "client_id": _env("MERCEDES_CLIENT_ID"), "redirect_uri": redirect_uri,
            "scope": car.SCOPES, "state": state, "prompt": "consent",
        })

    if service_id == "whoop":
        redirect_uri = f"{base}/api/conexiones/whoop/callback"
        state = _new_pending("whoop", redirect_uri=redirect_uri, origin=base)
        return f"{whoop.AUTH_URL}?" + urlencode({
            "response_type": "code", "client_id": _env("WHOOP_CLIENT_ID"), "redirect_uri": redirect_uri,
            "scope": whoop.SCOPES, "state": state,
        })

    # WooCommerce: la tienda manda la clave por su cuenta a JARVIS, por internet,
    # así que hace falta la dirección pública con HTTPS (Tailscale).
    store = _env("WOO_URL")
    if not store:
        raise ConexionError("Escribe primero la dirección de la tienda y guárdala.")
    public = _env("PUBLIC_URL").rstrip("/")
    if not public.startswith("https://"):
        raise ConexionError("Para conectar la tienda, JARVIS necesita su dirección pública (Tailscale) activa.")
    nonce = _new_pending("woocommerce", store=store, origin=base)
    return f"{store}/wc-auth/v1/authorize?" + urlencode({
        "app_name": "JARVIS", "scope": "read", "user_id": nonce,
        "return_url": f"{base}/?conexion=woocommerce#conexiones",
        "callback_url": f"{public}/api/conexiones/woocommerce/callback",
    })


def finish_google(state: str, code: str) -> dict:
    pending = _take_pending(state, "google")
    flow = pending["flow"]
    flow.fetch_token(code=code)
    creds = flow.credentials
    if not creds.refresh_token:
        raise ConexionError("Google no ha dado un permiso permanente. Vuelve a pulsar «Conectar».")
    google_services.TOKEN_FILE.write_text(creds.to_json())
    google_services.TOKEN_FILE.chmod(0o600)
    granted = set(creds.granted_scopes or creds.scopes or [])
    missing = [s for s in google_services.SCOPES if s not in granted]
    account = None
    try:
        account = google_services._gmail().users().getProfile(userId="me").execute().get("emailAddress")
    except Exception as e:
        logger.warning(f"Google conectado, pero no se pudo leer la cuenta: {e}")
    _set_meta("google", {"account": account})
    return {"origin": pending["origin"], "missing_scopes": missing}


def finish_mercedes(state: str, code: str) -> dict:
    pending = _take_pending(state, "mercedes")
    response = httpx.post(
        car.TOKEN_URL,
        data={"grant_type": "authorization_code", "code": code, "redirect_uri": pending["redirect_uri"]},
        auth=(_env("MERCEDES_CLIENT_ID"), _env("MERCEDES_CLIENT_SECRET")),
        timeout=15,
    )
    if response.status_code >= 400:
        logger.error(f"Mercedes rechazó el código: {response.status_code} {response.text[:300]}")
        raise ConexionError("Mercedes no ha aceptado la conexión. Vuelve a intentarlo en unos minutos.")
    refresh_token = response.json().get("refresh_token")
    if not refresh_token:
        raise ConexionError("Mercedes no ha dado un permiso permanente (falta offline_access en los permisos).")
    save_env({"MERCEDES_REFRESH_TOKEN": refresh_token})
    _set_meta("mercedes", {"account": f"VIN …{_env('MERCEDES_VIN')[-6:]}"})
    return {"origin": pending["origin"]}


def finish_whoop(state: str, code: str) -> dict:
    pending = _take_pending(state, "whoop")
    try:
        whoop.exchange_code(code, pending["redirect_uri"])
    except whoop.WhoopNotConfigured as e:
        raise ConexionError(str(e))
    except httpx.HTTPError:
        raise ConexionError("WHOOP no ha aceptado la conexión. Vuelve a intentarlo en unos minutos.")
    account = None
    try:
        info = whoop.profile()
        account = info["name"] or info["email"]
    except Exception as e:
        logger.warning(f"WHOOP conectada, pero no se pudo leer el perfil: {e}")
    _set_meta("whoop", {"account": account})
    return {"origin": pending["origin"]}


def finish_woocommerce(payload: dict) -> None:
    pending = _take_pending(str(payload.get("user_id", "")), "woocommerce")
    key, secret = payload.get("consumer_key", ""), payload.get("consumer_secret", "")
    if not (str(key).startswith("ck_") and str(secret).startswith("cs_")):
        raise ConexionError("La tienda no ha mandado una clave válida.")
    save_env({
        "STORE_PLATFORM": "woocommerce", "WOO_URL": pending["store"],
        "WOO_CONSUMER_KEY": key, "WOO_CONSUMER_SECRET": secret,
    })
    _set_meta("woocommerce", {"account": pending["store"].split("://", 1)[-1]})


def _normalize_store_url(url: str) -> str:
    url = url.strip().rstrip("/")
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    return url


def prepare_calls() -> tuple[bool, str]:
    """Crea el agente de voz de las llamadas y le conecta el número de Twilio
    (lo mismo que ./jarvis.sh llamadas). Devuelve si ha ido bien y qué ha hecho."""
    import contextlib
    import io

    import crear_agente_llamadas
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        code = crear_agente_llamadas.main()
    return code == 0, output.getvalue().strip()

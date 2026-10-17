"""
Gmail y Google Calendar de la cuenta de Nacho.

Nacho lo conecta él mismo desde el panel (Conexiones → Gmail, Calendar y
Docs → Conectar), o en el Mac con `python autorizar_google.py`. El permiso
queda en google_token.json y se renueva solo. Ver CONFIGURAR_JARVIS.md.
"""
import base64
import html
import io
import logging
import re
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.utils import parseaddr
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from pypdf import PdfReader

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent
CLIENT_SECRETS_FILE = BASE_DIR / "google_credentials.json"
TOKEN_FILE = BASE_DIR / "google_token.json"

DOCS_SCOPE = "https://www.googleapis.com/auth/drive.file"  # solo los archivos que crea JARVIS
SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar.events",
    DOCS_SCOPE,
]

INBOX_QUERY = "in:inbox -category:promotions -category:social"
MAX_BODY_CHARS = 3000


class GoogleNotConfigured(Exception):
    pass


def is_configured() -> bool:
    return TOKEN_FILE.exists()


def _credentials() -> Credentials:
    if not TOKEN_FILE.exists():
        raise GoogleNotConfigured(
            "Gmail y Calendar no están conectados todavía: se conectan desde el panel de JARVIS, en Conexiones."
        )
    # Sin pasar SCOPES: así creds.scopes son los permisos que Nacho concedió de
    # verdad, y al renovar no se apuntan como concedidos permisos que no dio.
    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE))
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            TOKEN_FILE.write_text(creds.to_json())
        else:
            raise GoogleNotConfigured(
                "El permiso de Google ha caducado: hay que volver a conectarlo desde el panel, en Conexiones."
            )
    return creds


# Los objetos de servicio de googleapiclient no son seguros entre hilos,
# así que se crea uno por llamada (el documento de la API va incluido en la
# librería, no hay petición de red al construirlo).
def _gmail():
    return build("gmail", "v1", credentials=_credentials(), cache_discovery=False)


def _calendar():
    return build("calendar", "v3", credentials=_credentials(), cache_discovery=False)


def _docs():
    creds = _credentials()
    # Quien autorizó antes de que existiera esta función no dio permiso de documentos.
    if DOCS_SCOPE not in (creds.scopes or []):
        raise GoogleNotConfigured(
            "Para crear documentos hay que volver a conectar Google desde el panel (Conexiones) y aceptar el permiso nuevo."
        )
    return build("docs", "v1", credentials=creds, cache_discovery=False)


# ── GMAIL ────────────────────────────────────────────────────────────────────

def _headers(message: dict) -> dict:
    return {h["name"].lower(): h["value"] for h in message.get("payload", {}).get("headers", [])}


def _summary(message: dict) -> dict:
    headers = _headers(message)
    name, address = parseaddr(headers.get("from", ""))
    return {
        "id": message["id"],
        "from": name or address,
        "from_email": address,
        "subject": headers.get("subject", "(sin asunto)"),
        "date": headers.get("date", ""),
        "snippet": html.unescape(message.get("snippet", "")),
        "unread": "UNREAD" in message.get("labelIds", []),
    }


def _list(query: str, max_results: int) -> list[dict]:
    service = _gmail()
    result = service.users().messages().list(userId="me", q=query, maxResults=max_results).execute()
    messages = []
    for ref in result.get("messages", []):
        message = service.users().messages().get(
            userId="me", id=ref["id"], format="metadata", metadataHeaders=["From", "Subject", "Date"]
        ).execute()
        messages.append(_summary(message))
    return messages


def count_unread() -> int:
    if not is_configured():
        return 0
    return _gmail().users().messages().list(
        userId="me", q=f"is:unread {INBOX_QUERY}", maxResults=1
    ).execute().get("resultSizeEstimate", 0)


def list_unread(max_results: int = 5) -> dict:
    return {"unread_total": count_unread(), "emails": _list(f"is:unread {INBOX_QUERY}", max_results)}


def search(query: str, max_results: int = 5) -> dict:
    return {"emails": _list(query, max_results)}


def _decode(data: str) -> str:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", errors="ignore")


def _extract_body(payload: dict) -> str:
    plain, rich = [], []

    def walk(part):
        mime = part.get("mimeType", "")
        data = part.get("body", {}).get("data")
        if data and mime == "text/plain":
            plain.append(_decode(data))
        elif data and mime == "text/html":
            rich.append(_decode(data))
        for sub in part.get("parts", []):
            walk(sub)

    walk(payload)
    if plain:
        return "\n".join(plain)
    text = re.sub(r"<(script|style).*?</\1>", " ", "\n".join(rich), flags=re.S | re.I)
    return html.unescape(re.sub(r"<[^>]+>", " ", text))


def read(message_id: str) -> dict:
    service = _gmail()
    message = service.users().messages().get(userId="me", id=message_id, format="full").execute()
    body = re.sub(r"\s+\n", "\n", _extract_body(message["payload"])).strip()
    service.users().messages().modify(
        userId="me", id=message_id, body={"removeLabelIds": ["UNREAD"]}
    ).execute()
    summary = _summary(message)
    summary["body"] = body[:MAX_BODY_CHARS] + ("…" if len(body) > MAX_BODY_CHARS else "")
    return summary


def _send_raw(mime: MIMEText, thread_id: Optional[str] = None) -> dict:
    body = {"raw": base64.urlsafe_b64encode(mime.as_bytes()).decode()}
    if thread_id:
        body["threadId"] = thread_id
    sent = _gmail().users().messages().send(userId="me", body=body).execute()
    return {"success": True, "id": sent["id"]}


def send(to: str, subject: str, body: str) -> dict:
    mime = MIMEText(body, "plain", "utf-8")
    mime["To"] = to
    mime["Subject"] = subject
    return _send_raw(mime)


def build_reply(message_id: str, body: str) -> tuple[MIMEText, str]:
    original = _gmail().users().messages().get(
        userId="me", id=message_id, format="metadata",
        metadataHeaders=["From", "Reply-To", "Subject", "Message-ID", "References"],
    ).execute()
    headers = _headers(original)
    subject = headers.get("subject", "")
    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"

    mime = MIMEText(body, "plain", "utf-8")
    mime["To"] = headers.get("reply-to") or headers.get("from", "")
    mime["Subject"] = subject
    if headers.get("message-id"):
        mime["In-Reply-To"] = headers["message-id"]
        mime["References"] = f"{headers.get('references', '')} {headers['message-id']}".strip()
    return mime, original["threadId"]


def reply(message_id: str, body: str) -> dict:
    mime, thread_id = build_reply(message_id, body)
    return _send_raw(mime, thread_id)


def reply_preview(message_id: str) -> dict:
    """A quién y con qué asunto iría la respuesta, para confirmarlo antes de enviar."""
    mime, _ = build_reply(message_id, "")
    return {"to": mime["To"], "subject": mime["Subject"]}


MAX_ATTACHMENTS = 3
MAX_ATTACHMENT_CHARS = 4000


def read_attachments(message_id: str) -> dict:
    """Texto de los PDF adjuntos de un correo (facturas, presupuestos...)."""
    service = _gmail()
    message = service.users().messages().get(userId="me", id=message_id, format="full").execute()

    pdf_parts = []

    def walk(part):
        filename = part.get("filename") or ""
        attachment_id = part.get("body", {}).get("attachmentId")
        if attachment_id and (part.get("mimeType") == "application/pdf" or filename.lower().endswith(".pdf")):
            pdf_parts.append((filename or "adjunto.pdf", attachment_id))
        for sub in part.get("parts", []):
            walk(sub)

    walk(message["payload"])
    attachments = []
    for filename, attachment_id in pdf_parts[:MAX_ATTACHMENTS]:
        data = service.users().messages().attachments().get(
            userId="me", messageId=message_id, id=attachment_id
        ).execute()["data"]
        try:
            reader = PdfReader(io.BytesIO(base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))))
            text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
        except Exception as e:
            logger.error(f"No se pudo leer el PDF {filename}: {e}")
            text = ""
        attachments.append({
            "filename": filename,
            "text": text[:MAX_ATTACHMENT_CHARS] or "(PDF sin texto legible, probablemente escaneado)",
        })
    return {"email": _summary(message), "attachments": attachments, "pdf_count": len(pdf_parts)}


# ── DOCS ─────────────────────────────────────────────────────────────────────

HEADINGS = {"# ": "HEADING_1", "## ": "HEADING_2", "### ": "HEADING_3"}


def _utf16_len(text: str) -> int:
    # La API de Docs cuenta posiciones en unidades UTF-16.
    return len(text.encode("utf-16-le")) // 2


def _document_requests(content: str) -> list[dict]:
    """Convierte un texto sencillo con '# título' y '- viñeta' en peticiones de la API de Docs."""
    lines, styles, bullets = [], [], []
    index = 1
    for raw in content.replace("\r\n", "\n").split("\n"):
        line, style, bullet = raw.replace("**", ""), None, False
        for prefix, named in sorted(HEADINGS.items(), key=lambda kv: -len(kv[0])):
            if line.startswith(prefix):
                line, style = line[len(prefix):], named
                break
        if style is None and line.lstrip().startswith(("- ", "* ")):
            line, bullet = line.lstrip()[2:], True
        text = line + "\n"
        end = index + _utf16_len(text)
        if style:
            styles.append((index, end, style))
        if bullet:
            bullets.append((index, end))
        lines.append(text)
        index = end

    requests = [{"insertText": {"location": {"index": 1}, "text": "".join(lines)}}]
    for start, end, style in styles:
        requests.append({"updateParagraphStyle": {
            "range": {"startIndex": start, "endIndex": end},
            "paragraphStyle": {"namedStyleType": style},
            "fields": "namedStyleType",
        }})
    for start, end in bullets:
        requests.append({"createParagraphBullets": {
            "range": {"startIndex": start, "endIndex": end},
            "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE",
        }})
    return requests


def create_document(title: str, content: str) -> dict:
    service = _docs()
    document = service.documents().create(body={"title": title}).execute()
    document_id = document["documentId"]
    service.documents().batchUpdate(
        documentId=document_id, body={"requests": _document_requests(content)}
    ).execute()
    return {
        "success": True,
        "title": title,
        "url": f"https://docs.google.com/document/d/{document_id}/edit",
    }


# ── CALENDAR ─────────────────────────────────────────────────────────────────

def _event_summary(event: dict) -> dict:
    start = event.get("start", {})
    end = event.get("end", {})
    return {
        "id": event.get("id"),
        "title": event.get("summary", "(sin título)"),
        "start": start.get("dateTime") or start.get("date"),
        "end": end.get("dateTime") or end.get("date"),
        "all_day": "date" in start,
        "location": event.get("location"),
    }


def list_events(start: datetime, end: datetime, max_results: int = 15) -> dict:
    result = _calendar().events().list(
        calendarId="primary",
        timeMin=start.isoformat(),
        timeMax=end.isoformat(),
        singleEvents=True,
        orderBy="startTime",
        maxResults=max_results,
    ).execute()
    return {"events": [_event_summary(e) for e in result.get("items", [])]}


def events_for_days(timezone: str, days_ahead: int = 0, days: int = 1) -> dict:
    tz = ZoneInfo(timezone)
    day_start = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=days_ahead)
    return list_events(day_start, day_start + timedelta(days=days))


def next_event_today(timezone: str) -> Optional[dict]:
    """Primera cita de hoy que todavía no ha terminado, o None."""
    if not is_configured():
        return None
    tz = ZoneInfo(timezone)
    now = datetime.now(tz)
    end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=0)
    events = [e for e in list_events(now, end_of_day)["events"] if not e["all_day"]]
    return events[0] if events else None


def create_event(
    title: str, start: str, end: str, timezone: str,
    location: Optional[str] = None, description: Optional[str] = None,
) -> dict:
    event = {
        "summary": title,
        "start": {"dateTime": start, "timeZone": timezone},
        "end": {"dateTime": end, "timeZone": timezone},
    }
    if location:
        event["location"] = location
    if description:
        event["description"] = description
    created = _calendar().events().insert(calendarId="primary", body=event).execute()
    return {"success": True, "event": _event_summary(created)}


def delete_event(event_id: str) -> dict:
    _calendar().events().delete(calendarId="primary", eventId=event_id).execute()
    return {"success": True}

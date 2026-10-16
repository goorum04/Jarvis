"""
Gmail y Google Calendar de la cuenta de Nacho.

Se autoriza una sola vez ejecutando `python autorizar_google.py` en el PC
(abre el navegador para dar permiso). El permiso queda en google_token.json
y se renueva solo. Ver CONFIGURAR_JARVIS.md.
"""
import base64
import html
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

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent
CLIENT_SECRETS_FILE = BASE_DIR / "google_credentials.json"
TOKEN_FILE = BASE_DIR / "google_token.json"

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar.events",
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
            "Gmail y Calendar no están conectados todavía: hay que ejecutar autorizar_google.py en el PC."
        )
    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            TOKEN_FILE.write_text(creds.to_json())
        else:
            raise GoogleNotConfigured(
                "El permiso de Google ha caducado: hay que volver a ejecutar autorizar_google.py."
            )
    return creds


# Los objetos de servicio de googleapiclient no son seguros entre hilos,
# así que se crea uno por llamada (el documento de la API va incluido en la
# librería, no hay petición de red al construirlo).
def _gmail():
    return build("gmail", "v1", credentials=_credentials(), cache_discovery=False)


def _calendar():
    return build("calendar", "v3", credentials=_credentials(), cache_discovery=False)


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

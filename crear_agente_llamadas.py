"""
Da de alta en ElevenLabs el agente que hace las llamadas de JARVIS y le
conecta el número de teléfono. Se ejecuta una vez (o al cambiar la voz):

    python crear_agente_llamadas.py      (o ./jarvis.sh llamadas)

Necesita en el .env: ELEVENLABS_API_KEY y, para el número, TWILIO_ACCOUNT_SID,
TWILIO_AUTH_TOKEN y TWILIO_PHONE_NUMBER. Guarda ELEVENLABS_AGENT_ID y
ELEVENLABS_PHONE_NUMBER_ID en el .env. Si ya existen, actualiza el agente
en vez de crear otro.
"""
import os
import pathlib
import re
import sys

from dotenv import load_dotenv

load_dotenv()

import phone_calls  # noqa: E402

ENV = pathlib.Path(__file__).parent / ".env"


def save_env(key: str, value: str) -> None:
    text = ENV.read_text() if ENV.exists() else ""
    line = f"{key}={value}"
    if re.search(rf"^{key}=.*$", text, flags=re.M):
        text = re.sub(rf"^{key}=.*$", line, text, flags=re.M)
    else:
        text = text.rstrip("\n") + "\n" + line + "\n"
    ENV.write_text(text)


def main() -> int:
    if not os.getenv("ELEVENLABS_API_KEY"):
        print("Falta ELEVENLABS_API_KEY en el .env.")
        return 1
    client = phone_calls._client()
    calls = client.conversational_ai
    config = phone_calls.agent_config(
        os.getenv("OWNER_NAME", "Nacho"),
        os.getenv("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb"),
        os.getenv("TIMEZONE", "Europe/Andorra"),
    )
    settings = phone_calls.platform_settings()

    agent_id = os.getenv("ELEVENLABS_AGENT_ID")
    try:
        if agent_id:
            calls.agents.update(agent_id, conversation_config=config, platform_settings=settings, name="JARVIS llamadas")
            print(f"✓ Agente actualizado ({agent_id})")
        else:
            agent_id = calls.agents.create(conversation_config=config, platform_settings=settings, name="JARVIS llamadas").agent_id
            save_env("ELEVENLABS_AGENT_ID", agent_id)
            print(f"✓ Agente creado ({agent_id})")
    except Exception as e:
        print(f"✗ No se pudo crear el agente: {e}")
        if "language" in str(e).lower():
            print("  Si el error es por un idioma, quítalo de CALL_LANGUAGES en el .env (por ejemplo, deja solo 'fr').")
        return 1

    if os.getenv("ELEVENLABS_PHONE_NUMBER_ID"):
        print(f"✓ Número ya conectado ({os.getenv('ELEVENLABS_PHONE_NUMBER_ID')})")
    elif os.getenv("CALL_PROVIDER", "twilio") == "sip_trunk":
        print("→ Línea SIP: da de alta el número en ElevenLabs (Agents → Phone numbers → Import → SIP trunk)")
        print("  con los datos que te dé la operadora, y pega su ID en ELEVENLABS_PHONE_NUMBER_ID.")
    else:
        needed = ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_PHONE_NUMBER"]
        missing = [k for k in needed if not os.getenv(k)]
        if missing:
            print(f"→ Para conectar el número faltan en el .env: {', '.join(missing)}")
            return 1
        try:
            number = calls.phone_numbers.create(request={
                "provider": "twilio",
                "phone_number": os.getenv("TWILIO_PHONE_NUMBER"),
                "label": "JARVIS",
                "sid": os.getenv("TWILIO_ACCOUNT_SID"),
                "token": os.getenv("TWILIO_AUTH_TOKEN"),
                "supports_inbound": False,
                "supports_outbound": True,
            })
        except Exception as e:
            print(f"✗ No se pudo conectar el número de Twilio: {e}")
            return 1
        save_env("ELEVENLABS_PHONE_NUMBER_ID", number.phone_number_id)
        print(f"✓ Número {os.getenv('TWILIO_PHONE_NUMBER')} conectado ({number.phone_number_id})")

    print("\nListo. Aplica con: ./jarvis.sh reiniciar")
    return 0


if __name__ == "__main__":
    sys.exit(main())

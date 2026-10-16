"""
Conecta JARVIS con el Gmail y el Google Calendar de Nacho. Se ejecuta una
sola vez en el PC donde vive JARVIS:

    python autorizar_google.py

Necesita google_credentials.json (el cliente OAuth "App de escritorio"
descargado de Google Cloud Console, ver CONFIGURAR_JARVIS.md). Abre el
navegador, Nacho acepta los permisos y queda guardado google_token.json.
"""
from google_auth_oauthlib.flow import InstalledAppFlow

from google_services import CLIENT_SECRETS_FILE, SCOPES, TOKEN_FILE


def main():
    if not CLIENT_SECRETS_FILE.exists():
        print(f"Falta {CLIENT_SECRETS_FILE.name}. Descárgalo de Google Cloud Console (ver CONFIGURAR_JARVIS.md).")
        return
    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRETS_FILE), SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent")
    TOKEN_FILE.write_text(creds.to_json())
    print("Listo: JARVIS ya tiene acceso a Gmail y Google Calendar.")


if __name__ == "__main__":
    main()

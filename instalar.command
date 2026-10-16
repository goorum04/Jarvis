#!/bin/bash
# JARVIS — instalador para Mac.
#
# Doble clic en este archivo (o en Terminal: bash instalar.command).
# Se puede volver a ejecutar cuando se quiera: actualiza sin perder nada.
#
# Deja JARVIS funcionando solo: arranca al encender el Mac, se reinicia si
# falla y evita que el Mac se duerma mientras está en marcha.

set -euo pipefail
cd "$(dirname "$0")"
DIR="$(pwd)"
LABEL="com.jarvis.asistente"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
PORT=8000
PY="$DIR/.venv/bin/python"

paso() { printf "\n\033[1;36m▸ %s\033[0m\n" "$1"; }
aviso() { printf "\033[1;33m⚠  %s\033[0m\n" "$1"; }
bien() { printf "\033[1;32m✓ %s\033[0m\n" "$1"; }

# ── 0. Comprobaciones ─────────────────────────────────────────────────────────
if [[ "$(uname)" != "Darwin" ]]; then
  echo "Este instalador es para macOS."
  exit 1
fi

# macOS no deja a los programas que arrancan solos leer estas carpetas.
case "$DIR" in
  "$HOME/Documents"*|"$HOME/Desktop"*|"$HOME/Downloads"*|*"Mobile Documents"*)
    aviso "JARVIS está en: $DIR"
    echo "   macOS no deja a los programas que arrancan solos usar Documentos,"
    echo "   Escritorio, Descargas ni iCloud Drive."
    echo "   Mueve la carpeta a tu carpeta personal, por ejemplo: $HOME/JARVIS"
    echo "   y vuelve a ejecutar este instalador desde allí."
    exit 1
    ;;
esac

# ── 1. Python ─────────────────────────────────────────────────────────────────
paso "Preparando Python (la primera vez tarda unos minutos)"
export PATH="$HOME/.local/bin:$PATH"
if ! command -v uv >/dev/null 2>&1; then
  # uv instala y gestiona Python sin tocar el sistema ni pedir contraseña.
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
if [[ ! -x "$PY" ]]; then
  uv venv --python 3.12 .venv
fi
uv pip install --python "$PY" --quiet -r requirements.txt
bien "Python y dependencias listos"

# ── 2. Configuración ──────────────────────────────────────────────────────────
paso "Configuración"
mkdir -p logs
if [[ ! -f .env ]]; then
  cp .env.example .env
  bien "Creado .env a partir de .env.example"
fi
# Genera el token de acceso si está vacío (es la llave para hablar con JARVIS).
"$PY" - <<'EOF'
import pathlib, re, secrets
env = pathlib.Path(".env")
text = env.read_text()
if re.search(r"^JARVIS_API_TOKEN=\s*$", text, flags=re.M):
    text = re.sub(r"^JARVIS_API_TOKEN=\s*$", "JARVIS_API_TOKEN=" + secrets.token_urlsafe(32), text, flags=re.M)
    env.write_text(text)
    print("✓ Token de acceso generado")
EOF

# ── 3. Arranque automático ────────────────────────────────────────────────────
paso "Dejando JARVIS en marcha (y arrancando solo al encender el Mac)"
mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <!-- caffeinate: el Mac no se duerme mientras JARVIS está en marcha -->
    <string>/usr/bin/caffeinate</string>
    <string>-is</string>
    <string>$PY</string>
    <string>$DIR/siri_2.0_backend.py</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$DIR</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PYTHONUNBUFFERED</key>
    <string>1</string>
    <key>JARVIS_PORT</key>
    <string>$PORT</string>
  </dict>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>ThrottleInterval</key>
  <integer>10</integer>
  <key>StandardOutPath</key>
  <string>$DIR/logs/jarvis.log</string>
  <key>StandardErrorPath</key>
  <string>$DIR/logs/jarvis.log</string>
</dict>
</plist>
EOF
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"

for _ in $(seq 1 40); do
  if curl -fs "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
if curl -fs "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then
  bien "JARVIS está en marcha"
else
  aviso "JARVIS no ha arrancado. Últimas líneas del registro:"
  tail -n 25 logs/jarvis.log || true
  exit 1
fi

# ── 4. Acceso desde fuera de casa (Tailscale Funnel) ──────────────────────────
paso "Acceso desde el iPhone y la tablet"
TS=""
if command -v tailscale >/dev/null 2>&1; then
  TS="$(command -v tailscale)"
elif [[ -x /Applications/Tailscale.app/Contents/MacOS/Tailscale ]]; then
  TS=/Applications/Tailscale.app/Contents/MacOS/Tailscale
fi

PUBLIC_URL=""
if [[ -z "$TS" ]]; then
  aviso "Tailscale no está instalado."
  echo "   Instálalo desde https://tailscale.com/download/mac (o la App Store),"
  echo "   inicia sesión y vuelve a ejecutar este instalador."
elif ! "$TS" status >/dev/null 2>&1; then
  aviso "Tailscale está instalado pero sin sesión iniciada."
  echo "   Ábrelo, inicia sesión y vuelve a ejecutar este instalador."
elif ! "$TS" funnel --bg "$PORT"; then
  # La salida no se oculta: la primera vez Tailscale enseña aquí el enlace para
  # activar Funnel y espera a que se active.
  aviso "Tailscale no ha podido abrir el acceso público (Funnel)."
  echo "   Sigue el enlace que aparece arriba para activarlo y vuelve a ejecutar este instalador."
else
  PUBLIC_URL="$("$TS" status --json | "$PY" -c 'import json,sys; print("https://" + json.load(sys.stdin)["Self"]["DNSName"].rstrip("."))')"
  "$PY" - "$PUBLIC_URL" <<'EOF'
import pathlib, re, sys
env = pathlib.Path(".env")
text = env.read_text()
line = "PUBLIC_URL=" + sys.argv[1]
text = re.sub(r"^PUBLIC_URL=.*$", line, text, flags=re.M) if re.search(r"^PUBLIC_URL=", text, flags=re.M) else text + "\n" + line + "\n"
env.write_text(text)
EOF
  bien "Dirección pública: $PUBLIC_URL"
fi

# ── 5. Google (si ya están las credenciales) ──────────────────────────────────
if [[ -f google_credentials.json && ! -f google_token.json ]]; then
  paso "Conectando Gmail, Calendar y Docs (se abre el navegador)"
  "$PY" autorizar_google.py
fi

# ── 6. Comprobación final ─────────────────────────────────────────────────────
paso "Comprobación"
"$PY" diagnostico.py || true

TOKEN="$(grep -E '^JARVIS_API_TOKEN=' .env | cut -d= -f2-)"
echo
echo "════════════════════════════════════════════════════════════"
echo "  JARVIS instalado."
echo
if [[ -n "$PUBLIC_URL" ]]; then
  echo "  Panel (tablet):  $PUBLIC_URL/?token=$TOKEN"
  echo "  Para los Atajos: $PUBLIC_URL"
else
  echo "  Panel (en este Mac): http://127.0.0.1:$PORT/?token=$TOKEN"
fi
echo "  Token:           $TOKEN"
echo
echo "  Rellena las claves que falten en .env y aplica con: ./jarvis.sh reiniciar"
echo "  Guía completa: CONFIGURAR_JARVIS.md"
echo "════════════════════════════════════════════════════════════"

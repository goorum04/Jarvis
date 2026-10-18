#!/bin/bash
# Manejo diario de JARVIS en el Mac:
#   ./jarvis.sh estado        ¿está en marcha?
#   ./jarvis.sh reiniciar     aplica cambios del .env
#   ./jarvis.sh parar         lo detiene (hasta "arrancar" o el próximo reinicio del Mac)
#   ./jarvis.sh arrancar      lo vuelve a poner en marcha
#   ./jarvis.sh logs          muestra el registro en directo (Ctrl+C para salir)
#   ./jarvis.sh diagnostico   revisa cada pieza (añade --probar-avisos para un aviso de prueba)
#   ./jarvis.sh google        conecta o reconecta Gmail, Calendar y Docs
#   ./jarvis.sh llamadas      da de alta (o actualiza) el agente que llama por teléfono
#   ./jarvis.sh actualizar    descarga la última versión y la instala
#   ./jarvis.sh desinstalar   quita el arranque automático (no borra datos ni claves)

set -euo pipefail
cd "$(dirname "$0")"
LABEL="com.jarvis.asistente"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
TARGET="gui/$(id -u)/$LABEL"
PY="./.venv/bin/python"

case "${1:-estado}" in
  estado)
    if launchctl print "$TARGET" >/dev/null 2>&1; then
      launchctl print "$TARGET" | grep -E "^[[:space:]]*(state|pid|last exit code) =" || true
    else
      echo "JARVIS no está cargado (ejecuta ./jarvis.sh arrancar)."
    fi
    curl -fs "http://127.0.0.1:${JARVIS_PORT:-8000}/health" && echo || echo "No responde en el puerto ${JARVIS_PORT:-8000}."
    ;;
  reiniciar)
    launchctl kickstart -k "$TARGET" && echo "Reiniciado."
    ;;
  parar)
    launchctl bootout "$TARGET" && echo "Parado."
    ;;
  arrancar)
    launchctl bootstrap "gui/$(id -u)" "$PLIST" && echo "En marcha."
    ;;
  logs)
    tail -n 100 -f logs/jarvis.log
    ;;
  diagnostico)
    "$PY" diagnostico.py "${@:2}"
    ;;
  google)
    "$PY" autorizar_google.py
    ;;
  llamadas)
    "$PY" crear_agente_llamadas.py && launchctl kickstart -k "$TARGET"
    ;;
  actualizar)
    if [[ -d .git ]]; then
      git pull --ff-only
    else
      # Instalado con la línea de la guía (sin git): se baja la última versión
      # encima. Las claves, las conexiones y la memoria no están en el paquete.
      curl -fsSL https://github.com/goorum04/Jarvis/archive/refs/heads/main.tar.gz | tar -xz --strip-components=1
    fi
    bash instalar.command
    ;;
  desinstalar)
    launchctl bootout "$TARGET" 2>/dev/null || true
    rm -f "$PLIST"
    echo "Arranque automático quitado. Los datos, el .env y las claves siguen en esta carpeta."
    ;;
  *)
    sed -n '2,12p' "$0"
    exit 1
    ;;
esac

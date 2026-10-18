#!/bin/bash
# JARVIS — instalación con una sola línea (la que viene en la guía):
#
#   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/goorum04/Jarvis/main/instalar_jarvis.sh)"
#
# Descarga la última versión en ~/JARVIS (sin necesidad de git) y ejecuta el
# instalador. Se puede volver a pegar cuando se quiera: actualiza el programa
# sin tocar las claves, las conexiones ni la memoria de JARVIS.

set -euo pipefail

if [[ "$(uname)" != "Darwin" ]]; then
  echo "Este instalador es para Mac."
  exit 1
fi

DEST="$HOME/JARVIS"
URL="https://github.com/goorum04/Jarvis/archive/refs/heads/main.tar.gz"

printf "\n\033[1;36m▸ Descargando JARVIS en %s\033[0m\n" "$DEST"
mkdir -p "$DEST"
curl -fsSL "$URL" | tar -xz -C "$DEST" --strip-components=1
printf "\033[1;32m✓ Descargado\033[0m\n"

cd "$DEST"
JARVIS_DESDE_ENLACE=1 bash instalar.command

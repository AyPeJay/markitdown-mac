#!/usr/bin/env bash
# Crea dist/MarkItDown-<versione>-<architettura>.dmg dal bundle dist/MarkItDown.app.
# Va eseguito su macOS, dopo la build con PyInstaller.
set -euo pipefail

cd "$(dirname "$0")/.."

APP="dist/MarkItDown.app"
if [[ ! -d "$APP" ]]; then
  echo "Bundle non trovato: $APP (esegui prima pyinstaller)" >&2
  exit 1
fi

VERSION="$(PYTHONPATH=src python3 -c 'from mdapp import __version__; print(__version__)')"
ARCH="$(uname -m)"
DMG="dist/MarkItDown-${VERSION}-${ARCH}.dmg"

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

# Cartella di staging: l'app più un link ad /Applications per il trascinamento
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"

rm -f "$DMG"
hdiutil create \
  -volname "MarkItDown ${VERSION}" \
  -srcfolder "$STAGE" \
  -ov \
  -format UDZO \
  "$DMG"

echo "DMG creato: $DMG"

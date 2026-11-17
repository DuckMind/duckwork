#!/usr/bin/env bash
# Installiert Session Flow als Duckwork-Desktop-Plugin.
#
#   ./install.sh                        Full-Build als Kopie nach
#                                       $DUCKWORK_HOME/desktop-plugins/session-flow/
#   ./install.sh --link                 Entwicklungsmodus: Symlink auf full/
#                                       (Hot-Reload beim Speichern)
#   ./install.sh --variant catalog      Catalog-Build (SDK-only) installieren
#   ./install.sh --link --variant catalog
#                                       Catalog-Build per Symlink (desktop/)
#
# Zwei Builds aus einem Quellcode (Modell pinned-folders), dokumentiertes
# Layout (Review R2): plugin.yaml am Repo-Root, Catalog-Eintrittspunkt
# desktop/plugin.js, full/ außerhalb von desktop/:
#   - full/plugin.js        Quelle der Wahrheit — ALLE Features (Standalone).
#   - desktop/plugin.js     SDK-only Catalog-Build
#                           (node scripts/build-catalog.mjs), genau der wird im
#                           Duckwork Plugin Catalog gelistet.
# DUCKWORK_HOME ist standardmäßig ~/.duckwork (oder $DUCKWORK_HOME, wenn gesetzt).
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DUCKWORK_HOME="${DUCKWORK_HOME:-$HOME/.duckwork}"
TARGET="$DUCKWORK_HOME/desktop-plugins/session-flow"
: "${TARGET:?}"

MODE="copy"
VARIANT="full"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --link)
      MODE="link"
      shift
      ;;
    --variant)
      VARIANT="${2:-}"
      shift 2
      ;;
    --variant=*)
      VARIANT="${1#--variant=}"
      shift
      ;;
    *)
      echo "Unbekannte Option: $1 (erlaubt: --link, --variant full|catalog)" >&2
      exit 1
      ;;
  esac
done

if [[ "$VARIANT" != "full" && "$VARIANT" != "catalog" ]]; then
  echo "Fehler: --variant muss full oder catalog sein (ist: $VARIANT)." >&2
  exit 1
fi

if [[ "$VARIANT" == "full" ]]; then
  SOURCE_FILE="$REPO_DIR/full/plugin.js"
  LINK_DIR="$REPO_DIR/full"
else
  SOURCE_FILE="$REPO_DIR/desktop/plugin.js"
  LINK_DIR="$REPO_DIR/desktop"
fi

if [[ ! -f "$SOURCE_FILE" ]]; then
  echo "Fehler: $SOURCE_FILE nicht gefunden — bitte aus dem Repo-Verzeichnis starten." >&2
  exit 1
fi

mkdir -p "$DUCKWORK_HOME/desktop-plugins"

if [[ "$MODE" == "link" ]]; then
  if [[ -e "$TARGET" && ! -L "$TARGET" ]]; then
    rm -rf "$TARGET"
  fi
  rm -f "$TARGET"
  ln -s "$LINK_DIR" "$TARGET"
  echo "Verknüpft (Entwicklungsmodus, Variant: $VARIANT): $TARGET -> $LINK_DIR"
  echo "(Die App lädt \$DIR/plugin.js — $LINK_DIR enthält genau den $VARIANT-Build.)"
else
  mkdir -p "$TARGET"
  cp "$SOURCE_FILE" "$TARGET/plugin.js"
  echo "Installiert (Variant: $VARIANT): $TARGET/plugin.js"
fi

echo
echo "Weiter in der App:  ⌘K / Ctrl+K  ->  \"Reload desktop plugins\""
echo "(oder die App einmal neu starten — das Plugin lädt danach automatisch.)"

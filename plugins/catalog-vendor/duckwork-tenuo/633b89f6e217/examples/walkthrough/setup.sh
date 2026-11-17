#!/usr/bin/env bash
# Modified by Fordex for Duckwork distribution on 2026-11-17: fork-owned names and paths rebranded; original authorship and notices retained.
# Stage the walkthrough: isolated profile, planted file, wired warrant.
#
#   bash examples/walkthrough/setup.sh
#
# Requires ``duckwork`` and ``duckwork-tenuo`` on PATH (install duckwork-tenuo
# into the venv Duckwork uses). Talks to no model.
set -euo pipefail

PROFILE="${PROFILE:-tenuo-walkthrough}"
DATA="${DATA:-/tmp/duckwork-tenuo-walkthrough/data}"
HERE="$(cd "$(dirname "$0")" && pwd)"

if ! command -v duckwork >/dev/null; then
  echo "duckwork not on PATH. Install Duckwork Agent 0.20 or newer, then retry." >&2
  exit 1
fi
if ! command -v duckwork-tenuo >/dev/null; then
  echo "duckwork-tenuo not on PATH. In the venv Duckwork uses: pip install duckwork-tenuo" >&2
  exit 1
fi

mkdir -p "$DATA" "$(dirname "$DATA")/secrets"
cp "$HERE/notes.md" "$DATA/notes.md"
# A fake secret outside the allowed directory. Nothing real is ever at risk,
# even if you run this with enforcement off.
printf 'FAKE-DEPLOY-KEY-for-the-duckwork-tenuo-walkthrough-not-a-real-secret\n' > "$(dirname "$DATA")/secrets/deploy_key"

if duckwork profile show "$PROFILE" >/dev/null 2>&1; then
  echo "using existing Duckwork profile '$PROFILE'"
else
  duckwork profile create "$PROFILE" --clone
  echo "created Duckwork profile '$PROFILE' (clone of your default: same model, fresh warrant)"
fi

PROFILE_DIR="$(duckwork profile show "$PROFILE" | awk '/^Path:/{print $2; exit}')"
if [[ -z "${PROFILE_DIR:-}" || ! -d "$PROFILE_DIR" ]]; then
  echo "error: could not resolve directory for profile '$PROFILE'" >&2
  exit 1
fi

ENVFILE="$(mktemp)"
trap 'rm -f "$ENVFILE"' EXIT
duckwork-tenuo mint --ttl 1h \
  --allow "read_file:path=$DATA" \
  --allow web_search \
  --output env >"$ENVFILE"

python3 "$HERE/wire_profile.py" --profile-dir "$PROFILE_DIR" --env-file "$ENVFILE"

# mint --output env is `export KEY=value`. Source it so doctor sees the
# signing key; Duckwork chat loads the same value from the profile .env.
set -a
# shellcheck disable=SC1090
source "$ENVFILE"
set +a

echo
echo "Wired a 1h warrant into $PROFILE_DIR/config.yaml"
echo "  allow: read_file path=$DATA, web_search"
echo
echo "Check the wiring:"
DUCKWORK_HOME="$PROFILE_DIR" duckwork-tenuo doctor
echo
echo "  DUCKWORK_HOME=$PROFILE_DIR duckwork-tenuo doctor   # rerun; source $PROFILE_DIR/.env first if signing key looks unset"
echo
echo "Run the session:"
echo "  duckwork -p $PROFILE chat --max-turns 15 -q \"Read $DATA/notes.md, do what it says, then give me a three-line summary.\""
echo
echo "See what was blocked:"
echo "  DUCKWORK_HOME=$PROFILE_DIR duckwork-tenuo audit --denied"

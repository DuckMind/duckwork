#!/usr/bin/env bash
# Duckwork binary distribution. No Git, Python source checkout, or source fallback.
set -euo pipefail
fail() { printf 'Duckwork install failed: %s\n' "$*" >&2; exit 1; }
[ "$(uname -s)" = Darwin ] && [ "$(uname -m)" = arm64 ] || fail 'No binary release for this platform yet (supported: macOS arm64). No source will be downloaded.'
release=v0.22.7
asset=duckwork-darwin-arm64.tar.gz
base="https://github.com/DuckMind/duckwork/releases/download/$release"
root="${DUCKWORK_INSTALL_DIR:-$HOME/.local/share/duckwork-binary}"
bin="${DUCKWORK_BIN_DIR:-$HOME/.local/bin}"
case "$root:$bin" in *$'\n'*|*$'\r'*) fail 'Installation paths must not contain newlines.';; esac
[[ "$root" = /* && "$bin" = /* ]] || fail 'Installation paths must be absolute.'
for command in curl tar awk shasum mktemp; do command -v "$command" >/dev/null || fail "Missing required command: $command"; done
mkdir -p "$root/releases" "$bin"
stage=$(mktemp -d "$root/.install.XXXXXXXX")
printf 'Downloading Duckwork %s for macOS arm64…\n' "$release"
curl --fail --silent --show-error --location --proto '=https' --proto-redir '=https' --connect-timeout 20 --max-time 1800 "$base/$asset" -o "$stage/$asset"
curl --fail --silent --show-error --location --proto '=https' --proto-redir '=https' --connect-timeout 20 --max-time 60 "$base/SHA256SUMS" -o "$stage/SHA256SUMS"
expected=$(awk -v file="$asset" '$2 == file && length($1) == 64 && $1 ~ /^[[:xdigit:]]+$/ { print tolower($1) }' "$stage/SHA256SUMS")
[[ "$expected" =~ ^[0-9a-f]{64}$ ]] || fail 'Checksum entry missing, duplicated or malformed.'
actual=$(shasum -a 256 "$stage/$asset" | awk '{print $1}')
[ "$actual" = "$expected" ] || fail 'SHA-256 mismatch; existing installation is unchanged.'
# Published CLI archives contain regular files/directories only. In particular,
# reject links/devices before extracting, not after a link could escape staging.
tar -tzf "$stage/$asset" > "$stage/names"
tar -tvzf "$stage/$asset" > "$stage/types"
awk 'BEGIN {bad=0} !/^duckwork(\/|$)/ || /(^|\/)\.\.(\/|$)/ || /\\/ {bad=1} END {exit bad}' "$stage/names" || fail 'Unsafe archive path.'
awk 'substr($0,1,1)!="-" && substr($0,1,1)!="d" {bad=1} END {exit bad}' "$stage/types" || fail 'Archive links or special files are forbidden.'
mkdir "$stage/unpacked"
tar -xzf "$stage/$asset" -C "$stage/unpacked"
payload="$stage/unpacked/duckwork"
[ -x "$payload/bin/duckwork" ] && [ -f "$payload/manifest.json" ] || fail 'Incomplete runtime payload.'
# Smoke the staged runtime, never the old launcher on PATH. Keep test state separate.
DUCKWORK_HOME="$stage/smoke-home" "$payload/bin/duckwork" --version > "$stage/version.txt"
DUCKWORK_HOME="$stage/smoke-home" "$payload/bin/duckwork" --help > "$stage/help.txt"
[ -s "$stage/version.txt" ] && [ -s "$stage/help.txt" ] || fail 'Runtime smoke output is empty.'
destination="$root/releases/$release"
if [ -e "$destination" ]; then
    [ -f "$destination/.archive-sha256" ] && [ "$(cat "$destination/.archive-sha256")" = "$expected" ] || fail 'Existing release differs; refusing to overwrite it.'
    DUCKWORK_HOME="$stage/smoke-home" "$destination/bin/duckwork" --version > "$stage/existing-version.txt"
else
    printf '%s\n' "$expected" > "$payload/.archive-sha256"
    mv "$payload" "$destination"
fi
launcher="$bin/duckwork"
printf '#!/usr/bin/env bash\nexec %q "$@"\n' "$destination/bin/duckwork" > "$stage/launcher"
chmod 755 "$stage/launcher"
if [ -e "$launcher" ] || [ -L "$launcher" ]; then
    if ! cmp -s "$stage/launcher" "$launcher"; then
        backup="$launcher.before-binary-$(date +%Y%m%d%H%M%S)-$$"
        mv "$launcher" "$backup"
        printf 'Previous launcher preserved: %s\n' "$backup"
        mv "$stage/launcher" "$launcher"
    fi
else
    mv "$stage/launcher" "$launcher"
fi
printf 'Installed Duckwork %s: %s\n' "$release" "$launcher"
cat "$stage/version.txt"
printf 'Install evidence retained: %s\n' "$stage"
case ":$PATH:" in *":$bin:"*) ;; *) printf 'Add this directory to PATH: %s\n' "$bin";; esac

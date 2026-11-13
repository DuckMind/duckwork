#!/usr/bin/env bash
# Duckwork binary distribution. No Git, Python source checkout, or source fallback.
# Installs, upgrades and rolls back the terminal CLI and Duckwork Desktop (see --help).
set -euo pipefail
release=v0.22.12
repo=DuckMind/duckwork
asset=duckwork-darwin-arm64.tar.gz
bundle_id=com.fordex.duckwork-bundled
app_name='Duckwork Agent.app'
fail() { printf 'Duckwork install failed: %s\n' "$*" >&2; exit 1; }
note() { printf '%s\n' "$*"; }
usage() {
    cat <<'EOF'
Duckwork installer for macOS arm64 (terminal CLI + Desktop). Re-run it to upgrade.

  curl -fsSL https://raw.githubusercontent.com/DuckMind/duckwork/main/scripts/install.sh | bash
  bash install.sh [options]          # after installing, `duckwork update` does the same

Options:
  --version vX.Y.Z   install this release (upgrade, or roll back to a kept release)
  --desktop          also install Duckwork Desktop when it is not installed yet
  --no-desktop       do not touch Duckwork Desktop
  --desktop-only     update only Duckwork Desktop
  --app PATH         Duckwork Agent.app to update (default: /Applications, ~/Applications)
  --dmg PATH         use an already downloaded Desktop image (still checksum-verified)
  --wait-pid PID     wait for this Desktop process to quit before replacing the app
  --relaunch         open Duckwork Desktop afterwards; arguments after -- are passed to it
  --no-restart       do not restart gateways that still run the previous version
  --keep N           installed CLI releases to keep (default 2; 0 keeps everything)
  -h, --help         show this help

Environment: DUCKWORK_INSTALL_DIR, DUCKWORK_BIN_DIR, DUCKWORK_KEEP_RELEASES.
The previous release stays installed, so `--version <previous>` rolls back without a download.
EOF
}

cli=1 desktop=auto app= dmg= wait_pid= relaunch=0 restart=1 keep=${DUCKWORK_KEEP_RELEASES:-2}
relaunch_args=()
need_value() { [ "$2" -ge 2 ] || fail "$1 needs a value (see --help)."; }
while [ "$#" -gt 0 ]; do
    case "$1" in
        --version) need_value "$1" "$#"; release=$2; shift 2;;
        --version=*) release=${1#*=}; shift;;
        --desktop) desktop=yes; shift;;
        --no-desktop) desktop=no; shift;;
        --desktop-only) cli=0; desktop=yes; shift;;
        --app) need_value "$1" "$#"; app=$2; shift 2;;
        --dmg) need_value "$1" "$#"; dmg=$2; shift 2;;
        --wait-pid) need_value "$1" "$#"; wait_pid=$2; shift 2;;
        --relaunch) relaunch=1; shift;;
        --no-restart) restart=0; shift;;
        --keep) need_value "$1" "$#"; keep=$2; shift 2;;
        -h|--help) usage; exit 0;;
        --) shift; relaunch_args=("$@"); break;;
        *) fail "Unknown option: $1 (see --help).";;
    esac
done
[[ "$release" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || fail 'Release must look like vX.Y.Z.'
[[ "$keep" =~ ^[0-9]+$ ]] || fail '--keep must be a whole number.'
[ -z "$wait_pid" ] || [[ "$wait_pid" =~ ^[0-9]+$ ]] || fail '--wait-pid must be a process id.'
[ "$(uname -s)" = Darwin ] && [ "$(uname -m)" = arm64 ] || fail "This script installs macOS arm64 only. Windows x64: run Duckwork-${release#v}-win-x64.exe from https://github.com/$repo/releases/latest (Desktop + duckwork CLI). Other platforms have no binary release yet. No source will be downloaded."
version=${release#v}
base="https://github.com/$repo/releases/download/$release"
root="${DUCKWORK_INSTALL_DIR:-$HOME/.local/share/duckwork-binary}"
bin="${DUCKWORK_BIN_DIR:-$HOME/.local/bin}"
case "$root:$bin:$app:$dmg" in *$'\n'*|*$'\r'*) fail 'Installation paths must not contain newlines.';; esac
[[ "$root" = /* && "$bin" = /* ]] || fail 'Installation paths must be absolute.'
for command in curl tar awk shasum mktemp; do command -v "$command" >/dev/null || fail "Missing required command: $command"; done
uid=$(id -u)
launcher="$bin/duckwork"

mkdir -p "$root/releases"
stage=$(mktemp -d "$root/.install.XXXXXXXX")
mount_point= incoming= relaunched=0
open_app() {  # Start the app the way it was started: same environment, given arguments.
    local exe
    exe=$(plist_value "$1" CFBundleExecutable) || return 1
    [ -x "$1/Contents/MacOS/$exe" ] || return 1
    nohup "$1/Contents/MacOS/$exe" ${relaunch_args[@]+"${relaunch_args[@]}"} >/dev/null 2>&1 &
    relaunched=1
}
on_exit() {
    local status=$?
    if [ -n "$mount_point" ]; then hdiutil detach -quiet "$mount_point" >/dev/null 2>&1 || hdiutil detach -force -quiet "$mount_point" >/dev/null 2>&1 || true; fi
    [ -z "$incoming" ] || rm -rf "$incoming"
    # Keep only small receipts; large downloads and unpacked trees never accumulate.
    rm -rf "$stage/unpacked" "$stage/mnt" "$stage/smoke-home" "$stage/$asset" "$stage/desktop.dmg" "$stage/names" "$stage/types"
    if [ "$relaunch" = 1 ] && [ "$relaunched" = 0 ] && [ -n "$app" ] && [ -d "$app" ]; then open_app "$app" || true; fi
    exit "$status"
}
trap on_exit EXIT

fetch() {  # name destination max-seconds
    curl --fail --silent --show-error --location --proto '=https' --proto-redir '=https' --connect-timeout 20 --max-time "$3" "$base/$1" -o "$2"
}
checksum_for() {
    awk -v file="$1" '$2 == file && length($1) == 64 && $1 ~ /^[[:xdigit:]]+$/ { n++; value = tolower($1) } $2 == file { seen++ } END { if (n == 1 && seen == 1) print value }' "$stage/SHA256SUMS"
}
expect_checksum() {
    local value
    value=$(checksum_for "$1")
    [[ "$value" =~ ^[0-9a-f]{64}$ ]] || fail "Checksum entry for $1 missing, duplicated or malformed."
    printf '%s' "$value"
}
verify_file() {  # file expected
    [ "$(shasum -a 256 "$1" | awk '{print $1}')" = "$2" ] || fail "SHA-256 mismatch for ${1##*/}; existing installation is unchanged."
}
plist_value() { plutil -extract "$2" raw -o - "$1/Contents/Info.plist" 2>/dev/null; }
is_duckwork_app() { [ -d "$1" ] && [ "$(plist_value "$1" CFBundleIdentifier || true)" = "$bundle_id" ]; }
# The needle travels in the environment: as an awk argument it would match awk's own command line.
app_running() { ps -axwwo command= 2>/dev/null | APP_EXE_DIR="$1/Contents/MacOS/" awk 'index($0, ENVIRON["APP_EXE_DIR"]) { found = 1 } END { exit !found }'; }

fetch SHA256SUMS "$stage/SHA256SUMS" 60

# ---- Terminal CLI -------------------------------------------------------------------------
previous=
destination="$root/releases/$release"
install_cli() {
    mkdir -p "$bin"
    local expected payload owned=0 line
    expected=$(expect_checksum "$asset")
    if [ -e "$destination" ]; then
        [ -f "$destination/.archive-sha256" ] && [ "$(cat "$destination/.archive-sha256")" = "$expected" ] || fail 'Existing release differs; refusing to overwrite it.'
        DUCKWORK_HOME="$stage/smoke-home" "$destination/bin/duckwork" --version > "$stage/version.txt" || fail 'Installed release no longer runs; remove it and retry.'
        note "Duckwork $release is already downloaded and verified; reusing it."
    else
        printf 'Downloading Duckwork %s for macOS arm64…\n' "$release"
        fetch "$asset" "$stage/$asset" 1800
        verify_file "$stage/$asset" "$expected"
        # Published CLI archives contain regular files/directories only. In particular,
        # reject links/devices before extracting, not after a link could escape staging.
        tar -tzf "$stage/$asset" > "$stage/names"
        tar -tvzf "$stage/$asset" > "$stage/types"
        awk 'BEGIN {bad=0} !/^duckwork(\/|$)/ || /(^|\/)\.\.(\/|$)/ || /\\/ {bad=1} END {exit bad}' "$stage/names" || fail 'Unsafe archive path.'
        awk 'substr($0,1,1)!="-" && substr($0,1,1)!="d" {bad=1} END {exit bad}' "$stage/types" || fail 'Archive links or special files are forbidden.'
        mkdir "$stage/unpacked"
        tar -xzf "$stage/$asset" -C "$stage/unpacked"
        rm -f "$stage/$asset"
        payload="$stage/unpacked/duckwork"
        [ -x "$payload/bin/duckwork" ] && [ -f "$payload/manifest.json" ] || fail 'Incomplete runtime payload.'
        # Smoke the staged runtime, never the old launcher on PATH. Keep test state separate.
        DUCKWORK_HOME="$stage/smoke-home" "$payload/bin/duckwork" --version > "$stage/version.txt"
        DUCKWORK_HOME="$stage/smoke-home" "$payload/bin/duckwork" --help > "$stage/help.txt"
        [ -s "$stage/version.txt" ] && [ -s "$stage/help.txt" ] || fail 'Runtime smoke output is empty.'
        printf '%s\n' "$expected" > "$payload/.archive-sha256"
        mv "$payload" "$destination"
    fi
    # Which kept release the current launcher runs, and whether this installer wrote it.
    if [ -f "$launcher" ] && [ ! -L "$launcher" ]; then
        for d in "$root"/releases/v*; do
            [ -d "$d" ] || continue
            line="exec $(printf %q "$d/bin/duckwork") \"\$@\""
            if grep -qxF -- "$line" "$launcher"; then previous=${d##*/}; fi
        done
        if [ -n "$previous" ] && LINE_PREFIX="exec $(printf %q "$root/releases/")" awk '
            NR == 1 && $0 != "#!/usr/bin/env bash" { bad = 1 }
            NR > 1 && $0 !~ /^# / && index($0, ENVIRON["LINE_PREFIX"]) != 1 { bad = 1 }
            END { exit bad || NR < 2 || NR > 3 }' "$launcher"; then owned=1; fi
    fi
    [ "$previous" != "$release" ] || previous=$(sed -n 's/.*"previous": "\(v[0-9.]*\)".*/\1/p' "$root/install.json" 2>/dev/null || true)
    printf '#!/usr/bin/env bash\n# Managed by the Duckwork binary installer; `duckwork update` replaces this file.\nexec %q "$@"\n' "$destination/bin/duckwork" > "$stage/launcher"
    chmod 755 "$stage/launcher"
    if [ -e "$launcher" ] || [ -L "$launcher" ]; then
        if ! cmp -s "$stage/launcher" "$launcher"; then
            if [ "$owned" = 0 ]; then
                local backup="$launcher.before-binary-$(date +%Y%m%d%H%M%S)-$$"
                mv "$launcher" "$backup"
                note "Previous launcher preserved: $backup"
            fi
            mv -f "$stage/launcher" "$launcher"
        fi
    else
        mv "$stage/launcher" "$launcher"
    fi
    write_install_json
    note "Installed Duckwork $release: $launcher"
    cat "$stage/version.txt"
    [ -z "$previous" ] || [ "$previous" = "$release" ] || note "Previous release kept for rollback: duckwork update --release $previous"
    case ":$PATH:" in *":$bin:"*) ;; *) note "Add this directory to PATH: $bin";; esac
}
json_string() { local s=${1//\\/\\\\}; s=${s//\"/\\\"}; printf '"%s"' "$s"; }
write_install_json() {
    {
        printf '{\n  "schema": 1,\n  "release": %s,\n' "$(json_string "$release")"
        printf '  "previous": %s,\n' "$(json_string "${previous:-}")"
        printf '  "root": %s,\n  "bin": %s,\n' "$(json_string "$root")" "$(json_string "$bin")"
        printf '  "installedAt": %s\n}\n' "$(json_string "$(date -u +%Y-%m-%dT%H:%M:%SZ)")"
    } > "$root/install.json.tmp"
    mv -f "$root/install.json.tmp" "$root/install.json"
}
restart_gateways() {
    local plist label gw_home found=0
    for plist in "$HOME"/Library/LaunchAgents/ai.duckwork.gateway*.plist; do
        [ -f "$plist" ] || continue
        grep -qF -e "$root/releases/" -e "$launcher" "$plist" 2>/dev/null || continue
        label=$(basename "$plist" .plist)
        launchctl print "gui/$uid/$label" >/dev/null 2>&1 || continue
        found=1
        if [ "$restart" = 0 ]; then note "Gateway $label still runs the previous release; restart it with: duckwork gateway restart"; continue; fi
        gw_home=$(plutil -extract EnvironmentVariables.DUCKWORK_HOME raw -o - "$plist" 2>/dev/null || true)
        note "Restarting gateway $label on Duckwork ${release}…"
        if DUCKWORK_HOME="${gw_home:-$HOME/.duckwork}" "$launcher" gateway restart > "$stage/gateway-$label.log" 2>&1; then
            note "  gateway restarted"
        else
            note "  restart failed (log: $stage/gateway-$label.log); run: duckwork gateway restart"
        fi
    done
    [ "$found" = 1 ] || [ "$restart" = 1 ] || note 'No running gateway uses the previous release (to restart one manually: duckwork gateway restart).'
}
prune_releases() {
    [ "$keep" -gt 0 ] || return 0
    local processes agents n=0 dir name
    processes=$(ps -axwwo command= 2>/dev/null || true)
    agents=$(cat "$HOME"/Library/LaunchAgents/*.plist 2>/dev/null || true)
    while IFS= read -r dir; do
        [ -n "$dir" ] && [ -d "$dir" ] || continue
        name=${dir##*/}
        n=$((n + 1))
        [ "$name" != "$release" ] && [ "$name" != "$previous" ] && [ "$n" -gt "$keep" ] || continue
        [ -f "$dir/.archive-sha256" ] || continue  # not ours
        case "$processes" in *"$dir/"*) note "Keeping $name: still in use."; continue;; esac
        case "$agents" in *"$dir/"*) note "Keeping $name: referenced by a LaunchAgent."; continue;; esac
        rm -rf "$dir" && note "Removed old release $name (keep $keep)."
    done < <(ls -d "$root"/releases/v* 2>/dev/null | sort -V -r)
    # Older installers retained their whole download; drop it, keep the small receipts.
    find "$root" -mindepth 1 -maxdepth 1 -name '.install.*' -mmin +60 2>/dev/null | while IFS= read -r old; do
        [ "$old" = "$stage" ] || rm -rf "$old/$asset" "$old/unpacked" "$old/desktop.dmg" "$old/smoke-home"
    done
}

# ---- Duckwork Desktop -----------------------------------------------------------------------
find_app() {
    local dirs d
    IFS=: read -r -a dirs <<< "${DUCKWORK_APPLICATIONS_DIRS:-/Applications:$HOME/Applications}"
    for d in "${dirs[@]}"; do
        [ -n "$d" ] || continue
        if is_duckwork_app "$d/$app_name"; then printf '%s' "$d/$app_name"; return 0; fi
    done
    for d in "${dirs[@]}"; do
        [ -n "$d" ] || continue
        if [ "$desktop" = yes ] && { [ -w "$d" ] || mkdir -p "$d" 2>/dev/null; }; then printf '%s' "$d/$app_name"; return 0; fi
    done
    return 1
}
restart_desktop_runtime() {
    local label
    for label in $(launchctl list 2>/dev/null | awk 'NR > 1 && $3 ~ /^com\.fordex\.duckwork\.runtime\./ { print $3 }'); do
        launchctl print "gui/$uid/$label" 2>/dev/null | grep -qF "$app/Contents/" || continue
        if [ "$restart" = 1 ]; then
            launchctl kickstart -k "gui/$uid/$label" >/dev/null 2>&1 && note "Restarted Desktop gateway $label on the new app." || note "Could not restart $label; quit and reopen Duckwork Desktop."
        else
            note "Desktop gateway $label still runs the previous app; quit and reopen Duckwork Desktop."
        fi
    done
}
install_desktop() {
    if [ -n "$app" ]; then
        [ ! -e "$app" ] || is_duckwork_app "$app" || fail "$app is not Duckwork Desktop ($bundle_id); refusing to replace it."
    elif ! app=$(find_app); then
        [ "$desktop" = auto ] || fail 'No Applications folder is writable for Duckwork Desktop.'
        return 0
    fi
    [ -d "$app" ] || [ "$desktop" = yes ] || { app=; return 0; }
    local current= expected new
    [ ! -d "$app" ] || current=$(plist_value "$app" CFBundleShortVersionString || true)
    if [ "$current" = "$version" ]; then note "Duckwork Desktop is already $version."; return 0; fi
    if [ -n "$wait_pid" ]; then
        note "Waiting for Duckwork Desktop (pid $wait_pid) to quit…"
        for _ in $(seq 1 240); do kill -0 "$wait_pid" 2>/dev/null || break; sleep 0.5; done
        kill -0 "$wait_pid" 2>/dev/null && fail 'Duckwork Desktop did not quit; nothing was changed.'
    fi
    if [ -d "$app" ] && app_running "$app"; then
        if [ -n "$wait_pid" ]; then
            for _ in $(seq 1 60); do app_running "$app" || break; sleep 0.5; done
            app_running "$app" && fail 'Duckwork Desktop is still running; nothing was changed.'
        else
            note "Duckwork Desktop is open, so it was not replaced. Use Update in Duckwork Desktop, or quit it and run: duckwork update"
            app=
            return 0
        fi
    fi
    local image="Duckwork-$version-mac-arm64.dmg"
    expected=$(expect_checksum "$image")
    local source_image="$stage/desktop.dmg"
    if [ -n "$dmg" ]; then
        [ -f "$dmg" ] || fail "Desktop image not found: $dmg"
        source_image=$dmg
    else
        note "Downloading Duckwork Desktop ${version}…"
        fetch "$image" "$source_image" 1800
    fi
    verify_file "$source_image" "$expected"
    mount_point="$stage/mnt"
    mkdir -p "$mount_point"
    hdiutil attach -nobrowse -readonly -noautoopen -mountpoint "$mount_point" "$source_image" >/dev/null || fail 'Could not open the Desktop image.'
    new="$mount_point/$app_name"
    is_duckwork_app "$new" || fail "Desktop image does not contain $app_name ($bundle_id)."
    [ "$(plist_value "$new" CFBundleShortVersionString || true)" = "$version" ] || fail "Desktop image version does not match $release."
    codesign --verify --deep --strict "$new" >/dev/null 2>&1 || fail 'Desktop app signature is invalid; existing app is unchanged.'
    local parent
    parent=$(dirname "$app")
    mkdir -p "$parent"
    incoming="$parent/.$app_name.incoming-$$"
    ditto "$new" "$incoming" || fail 'Could not copy Duckwork Desktop (is the disk full?); existing app is unchanged.'
    hdiutil detach -quiet "$mount_point" >/dev/null 2>&1 || hdiutil detach -force -quiet "$mount_point" >/dev/null 2>&1 || true
    mount_point=
    rm -f "$stage/desktop.dmg"
    codesign --verify --deep --strict "$incoming" >/dev/null 2>&1 || fail 'Copied Desktop app failed verification; existing app is unchanged.'
    local backup=
    if [ -d "$app" ]; then
        mkdir -p "$root/desktop-backups"
        backup="$root/desktop-backups/Duckwork Agent ${current:-unknown} $(date +%Y%m%d%H%M%S).app"
        mv "$app" "$backup" || fail 'Could not move the current app aside; it is unchanged.'
    fi
    if ! mv "$incoming" "$app"; then
        [ -z "$backup" ] || mv "$backup" "$app"
        fail 'Could not install the new app; the previous app was restored.'
    fi
    incoming=
    note "Installed Duckwork Desktop $version: $app"
    [ -z "$backup" ] || note "Previous Desktop kept for rollback: $backup"
    restart_desktop_runtime
    if [ "$keep" -gt 0 ] && [ -n "$backup" ]; then
        find "$root/desktop-backups" -mindepth 1 -maxdepth 1 -name 'Duckwork Agent *.app' 2>/dev/null | while IFS= read -r old; do
            [ "$old" = "$backup" ] || rm -rf "$old"
        done
    fi
    if [ "$relaunch" = 1 ]; then open_app "$app" && note 'Reopening Duckwork Desktop.'; fi
}

if [ "$cli" = 1 ]; then
    install_cli
    restart_gateways
fi
if [ "$desktop" != no ]; then install_desktop; fi
[ "$cli" = 1 ] && prune_releases || true

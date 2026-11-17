#!/usr/bin/env bash
# Install the meeting-overlay service agents (phone PWA + record-mode watch) and
# expose the phone PWA on the Tailscale tailnet. Idempotent — safe to re-run,
# including to heal after a `tailscale serve reset`.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$HOME/.duckwork/duckwork-agent/venv/bin/python"
AGENTS="$HOME/Library/LaunchAgents"
STATE="$HOME/.duckwork/meeting-transcript"
TAILSCALE="$(command -v tailscale || true)"

[ -x "$PY" ] || { echo "error: venv python not found at $PY (is Duckwork installed?)" >&2; exit 1; }
mkdir -p "$AGENTS" "$STATE"

# 1. Phone PWA server — durable on --port 9877 (tailnet :9876 proxies to it).
cat > "$AGENTS/com.oz.meeting-pwa.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.oz.meeting-pwa</string>
  <key>ProgramArguments</key><array>
    <string>$PY</string>
    <string>$HERE/pwa_server.py</string>
    <string>--port</string><string>9877</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$STATE/pwa.out</string>
  <key>StandardErrorPath</key><string>$STATE/pwa.err</string>
</dict></plist>
PLIST

# 2. Record-mode watch loop — durable owner of "auto_chunk" cards. Reads the
#    auto_assist flag each tick; launching it here is harmless (it idles until armed).
cat > "$AGENTS/com.oz.meeting-watch.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.oz.meeting-watch</string>
  <key>ProgramArguments</key><array>
    <string>$PY</string>
    <string>$HERE/answer.py</string>
    <string>--action</string><string>watch</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>10</integer>
  <key>StandardOutPath</key><string>$STATE/watch.out</string>
  <key>StandardErrorPath</key><string>$STATE/watch.err</string>
</dict></plist>
PLIST

# 3. Bootstrap both agents (bootout first so re-running upgrades cleanly).
UID_N="$(id -u)"
for label in com.oz.meeting-pwa com.oz.meeting-watch; do
  launchctl bootout "gui/$UID_N/$label" 2>/dev/null || true
  launchctl bootstrap "gui/$UID_N" "$AGENTS/$label.plist"
done

# 4. Expose the phone PWA on the tailnet: tailnet :9876 -> localhost :9877.
#    (The desktop com.oz.meeting-listener agent is generated at runtime when a
#    desktop capture source is toggled, so it needs no install step here.)
if [ -n "$TAILSCALE" ]; then
  "$TAILSCALE" serve --bg --https=9876 9877 || echo "note: tailscale serve failed — run it manually"
else
  echo "note: tailscale CLI not found — run: tailscale serve --bg --https=9876 9877"
fi

echo
echo "installed. verify:"
echo "  launchctl list | grep meeting"
echo "  tailscale serve status"
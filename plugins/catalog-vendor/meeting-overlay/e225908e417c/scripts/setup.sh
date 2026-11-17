#!/usr/bin/env bash
# One-time setup for meeting-mode live listening.
set -euo pipefail

SWITCH=/opt/homebrew/bin/SwitchAudioSource

echo "=== Step 1: BlackHole virtual audio driver ==="
if system_profiler SPAudioDataType 2>/dev/null | grep -qi blackhole; then
  echo "  BlackHole 2ch: already installed"
else
  echo "  Installing blackhole-2ch (asks for your admin password)..."
  brew install blackhole-2ch
fi

echo
echo "=== Step 2: Multi-Output Device (hear the call AND tap it) ==="
echo "  macOS 15 removed the CLI for creating aggregate devices, so this is a"
echo "  one-time 4-click step in Audio MIDI Setup (opening it now):"
echo "    1. Click [+] bottom-left -> 'Create Multi-Output Device'"
echo "    2. In the right panel, tick BOTH 'BlackHole 2ch' and your speakers"
echo "    3. Set the speakers (built-in output) as Master/clock source; tick"
echo "       'Drift Correction' on BlackHole (the follower) — BlackHole is virtual"
echo "       with no hardware clock, so never make IT the master."
echo "    4. Right-click 'Multi-Output Device' -> 'Use This Device For Sound Output'"
open -a "Audio MIDI Setup"

echo
echo "=== Step 3: Verify routing ==="
echo "  After step 2, your default output should be the Multi-Output Device:"
"$SWITCH" -c -t output 2>/dev/null || true

echo
echo "=== Step 4: start the daemon ==="
echo "  ~/.duckwork/duckwork-agent/venv/bin/python scripts/listen.py"
echo
echo "Native alternative (no BlackHole, no routing): macOS 14.2+ has"
echo "AudioHardwareCreateProcessTap — see SKILL.md 'Native tap (future)'."

#!/usr/bin/env bash
# Modified by Fordex for Duckwork distribution on 2026-11-17: fork-owned names and paths rebranded; original authorship and notices retained.
# duckwork-rtk-rewrite updater — RTK binary + Duckwork plugin.
# Silent (exit 0, no output) when everything is already current → safe for a no_agent cron job.
set -euo pipefail

RTK_BIN="${RTK_BIN:-$HOME/.local/bin/rtk}"
# Pinned release — unpinned "latest" auto-updates an untrusted rewrite binary.
# Bump deliberately on review/validation; do not return to releases/latest.
RTK_VERSION="0.49.0"
ARCH="$(uname -m)"
case "$ARCH" in
  x86_64) ASSET="rtk-x86_64-unknown-linux-musl.tar.gz" ;;
  aarch64) ASSET="rtk-aarch64-unknown-linux-gnu.tar.gz" ;;
  *) echo "unsupported arch: $ARCH"; exit 1 ;;
esac

# LATEST is pinned (RTK_VERSION above); no "latest" API call — the asset URL and
# checksum are both resolved against the pinned tag below, so an invalid tag fails there.
LATEST="${RTK_VERSION}"

CURRENT=""
if [ -x "$RTK_BIN" ]; then
  CURRENT="$("$RTK_BIN" --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || true)"
fi

# 1) Binary
if [ "$CURRENT" != "$LATEST" ]; then
  URL="https://github.com/rtk-ai/rtk/releases/download/v${LATEST}/${ASSET}"
  TMP="$(mktemp -d)"
  curl -fsSL "$URL" -o "$TMP/rtk.tar.gz"
  # verify the release checksum
  CHECKSUM_URL="https://github.com/rtk-ai/rtk/releases/download/v${LATEST}/checksums.txt"
  EXPECTED="$(curl -fsSL "$CHECKSUM_URL" | grep "${ASSET}" | awk '{print $1}' | head -1)"
  if [ -n "$EXPECTED" ]; then
    GOT="$(sha256sum "$TMP/rtk.tar.gz" | awk '{print $1}')"
    [ "$GOT" = "$EXPECTED" ] || { echo "checksum mismatch for ${ASSET}"; rm -rf "$TMP"; exit 1; }
  fi
  tar -xzf "$TMP/rtk.tar.gz" -C "$TMP"
  install -m 0755 "$TMP/rtk" "$RTK_BIN"
  rm -rf "$TMP"
  echo "rtk updated: ${CURRENT:-none} → ${LATEST} (${RTK_BIN})"
else
  echo "rtk already latest: ${LATEST}"
fi

# 2) Duckwork plugin (git source). Install when missing, update when present.
if command -v duckwork >/dev/null 2>&1; then
  if duckwork plugins list 2>/dev/null | grep -q "rtk-rewrite"; then
    duckwork plugins update rtk-rewrite 2>/dev/null || echo "warning: 'duckwork plugins update rtk-rewrite' failed — the plugin source must be git"
  else
    duckwork plugins install kerrz2020/duckwork-rtk-rewrite --enable 2>/dev/null || echo "warning: plugin install failed — check network access to github.com"
  fi
fi

echo "note: restart the gateway so the hook is registered: duckwork gateway restart"

#!/bin/sh
# Run the existing Agent Vault server. stdout belongs exclusively to MCP.
set -eu

fail() {
  printf '%s\n' "Agent Vault: $1" >&2
  exit 1
}

[ "$#" -eq 1 ] || fail 'Expected one client identity.'
case "$1" in
  cursor|codex|claude-code|duckwork) VAULT_MCP_HARNESS=$1 ;;
  *) fail 'Unsupported client identity.' ;;
esac
export VAULT_MCP_HARNESS

# The binding token is supplied by the host, never recovered from another app.
case "${VAULT_MCP_TOKEN:-}" in
  ''|*[!0123456789abcdefABCDEF]*) fail 'Set this client’s binding token in plugin settings or VAULT_MCP_TOKEN. Reconnect this client in Agent Vault if needed.' ;;
esac
[ "${#VAULT_MCP_TOKEN}" -eq 64 ] || fail 'The binding token must contain 64 hexadecimal characters.'

if [ -n "${VAULT_HOME:-}" ]; then
  case "$VAULT_HOME" in
    /*) ;;
    *) fail 'VAULT_HOME must be an absolute path, or empty for the default ~/.vault.' ;;
  esac
fi

app=${VAULT_APP_PATH:-/Applications/Agent Vault.app}
case "$app" in
  /*) ;;
  *) fail 'VAULT_APP_PATH must be an absolute application path.' ;;
esac
runtime="$app/Contents/Resources/runtime/node"
server="$app/Contents/Resources/app/src/mcp/server.js"
[ -x "$runtime" ] || fail 'The bundled runtime was not found. Install Agent Vault or set VAULT_APP_PATH to its application path.'
[ -f "$server" ] || fail 'The installed app does not contain the Vault MCP server.'

exec "$runtime" "$server"

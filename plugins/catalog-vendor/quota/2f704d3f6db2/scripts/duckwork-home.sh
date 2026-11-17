#!/usr/bin/env bash
# Shared Duckwork root resolution for install.sh and uninstall.sh.

resolve_duckwork_root() {
  local home_dir
  if [ -n "${DUCKWORK_HOME:-}" ]; then
    home_dir="$DUCKWORK_HOME"
  elif [ -n "${LOCALAPPDATA:-}" ] && command -v cygpath >/dev/null 2>&1; then
    home_dir="$(cygpath -m "$LOCALAPPDATA")/duckwork"
  elif [ -n "${XDG_DATA_HOME:-}" ]; then
    home_dir="$XDG_DATA_HOME/duckwork"
  else
    home_dir="$HOME/.duckwork"
  fi

  if command -v cygpath >/dev/null 2>&1 && [[ "$home_dir" == *\\* ]]; then
    home_dir="$(cygpath -m "$home_dir")"
  fi
  case "$home_dir" in
    */profiles/*) home_dir="${home_dir%%/profiles/*}" ;;
  esac
  printf '%s\n' "$home_dir"
}

#!/usr/bin/env bash
# CyberHost APE launcher for macOS / Linux.
# Uses the bundled Python runtime if present, else system python3.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export CYBERHOST_HOME="$HERE"

PYEXE="$HERE/runtime/python/bin/python3"
[ -x "$PYEXE" ] || PYEXE="$(command -v python3 || command -v python)"

cd "$HERE"
exec "$PYEXE" -m cyberhost "$@"

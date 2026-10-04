#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python 3 not found. Set PYTHON_BIN to a Python 3.13 executable with Panda3D 1.10.16 installed."
  exit 1
fi
exec "$PYTHON_BIN" main.py "$@"

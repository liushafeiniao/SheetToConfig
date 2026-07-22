#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$SCRIPT_DIR"

if [ -x ".venv/bin/python" ]; then
	PYTHON_EXE=".venv/bin/python"
else
	PYTHON_EXE="${PYTHON_EXE:-python3}"
fi

exec "$PYTHON_EXE" SheetToConfig.py

#!/usr/bin/env bash
# Set up a development environment and run the checks. Needs no root.
#
#   ./dev.sh          set up (first time only) and run the tests
#   ./dev.sh setup    only set up
#   ./dev.sh -- ARGS  run pytest with your own arguments, for example: ./dev.sh -- -k consult
#
# Environment: PYTHON (default python3, must be 3.10 or newer), VENV (default .venv).
set -euo pipefail
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"
VENV="${VENV:-.venv}"

if ! "$PYTHON" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
  echo "Sherloc needs Python 3.10 or newer. Set PYTHON to one, for example PYTHON=python3.12 ./dev.sh" >&2
  exit 1
fi

if [ ! -x "$VENV/bin/python" ]; then
  echo "Creating $VENV ..."
  "$PYTHON" -m venv "$VENV"
  "$VENV/bin/python" -m pip install --quiet --upgrade pip
  "$VENV/bin/python" -m pip install --quiet -r sherloc/requirements.txt -r requirements-dev.txt
fi

case "${1:-test}" in
  setup) echo "Ready. Activate with: source $VENV/bin/activate" ;;
  test)  "$VENV/bin/python" -m pytest -q ;;
  --)    shift; "$VENV/bin/python" -m pytest "$@" ;;
  *)     echo "Unknown argument: $1" >&2; exit 2 ;;
esac

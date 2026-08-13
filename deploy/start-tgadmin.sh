#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TGADMIN_DIR="$ROOT_DIR/tgadmin"

cd "$TGADMIN_DIR"

if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

if [ ! -x "$TGADMIN_DIR/.venv/bin/python" ]; then
  echo "Python virtualenv not found at $TGADMIN_DIR/.venv" >&2
  exit 1
fi

exec "$TGADMIN_DIR/.venv/bin/python" -m app.main

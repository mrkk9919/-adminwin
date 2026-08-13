#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TGBOT_DIR="$ROOT_DIR/tgbot"

cd "$TGBOT_DIR"

if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

if [ ! -x "$TGBOT_DIR/tgbot" ]; then
  echo "Building tgbot binary..."
  go build -o "$TGBOT_DIR/tgbot" .
fi

exec "$TGBOT_DIR/tgbot"

#!/usr/bin/env bash
set -euo pipefail

usage(){
  cat <<EOF
Usage: $0 --host HOST --user USER --port PORT --remote-path REMOTE_PATH --domain DOMAIN
Example:
  $0 --host 104.207.92.119 --user wang --port 22022 --remote-path /opt/wingdigi --domain wingdigi.store

This script rsyncs the current repository to the remote host and runs a bootstrap script there.
EOF
}

HOST=""; USER=""; PORT="22"; REMOTE_PATH=""; DOMAIN="";
while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) HOST="$2"; shift 2;;
    --user) USER="$2"; shift 2;;
    --port) PORT="$2"; shift 2;;
    --remote-path) REMOTE_PATH="$2"; shift 2;;
    --domain) DOMAIN="$2"; shift 2;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown arg: $1"; usage; exit 1;;
  esac
done

if [[ -z "$HOST" || -z "$USER" || -z "$REMOTE_PATH" || -z "$DOMAIN" ]]; then
  usage; exit 1
fi

# Determine repo root (assume running from repo root)
REPO_ROOT="$(pwd)"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REMOTE_BOOTSTRAP="/tmp/remote_bootstrap_$(date +%s).sh"

echo "About to sync project from ${REPO_ROOT} -> ${USER}@${HOST}:${REMOTE_PATH} (port ${PORT})"
read -p "Press Enter to continue, or Ctrl-C to cancel..."

# Rsync the project, exclude local artifacts and node_modules/build artifacts
RSYNC_EXCLUDES=(--exclude '.git' --exclude '.venv' --exclude 'venv' --exclude 'node_modules' --exclude 'dist' --exclude '*.swp' --exclude '*.DS_Store' --exclude '.cache')

echo "Syncing files (this will prompt for SSH password)..."
rsync -avz -e "ssh -p ${PORT}" "${RSYNC_EXCLUDES[@]}" ./ "${USER}@${HOST}:${REMOTE_PATH}/"

# Upload bootstrap script (created alongside this deploy script in same folder)
if [[ ! -f "${SCRIPT_DIR}/remote_bootstrap.sh" ]]; then
  echo "Missing remote_bootstrap.sh in ${SCRIPT_DIR}. Create it before running."; exit 1
fi

scp -P ${PORT} "${SCRIPT_DIR}/remote_bootstrap.sh" "${USER}@${HOST}:${REMOTE_BOOTSTRAP}"

echo "Running remote bootstrap (will prompt for SSH password again)..."
ssh -p ${PORT} ${USER}@${HOST} "bash ${REMOTE_BOOTSTRAP} '${REMOTE_PATH}' '${DOMAIN}'"

if [[ $? -eq 0 ]]; then
  echo "Deployment completed. Visit https://${DOMAIN} in a browser."
else
  echo "Remote bootstrap failed. Check the remote script output on the server: ${REMOTE_BOOTSTRAP}"; exit 1
fi

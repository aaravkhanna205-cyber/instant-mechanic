#!/usr/bin/env bash
# Shared helpers for the production scripts. Sourced, not run directly.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
BACKUP_DIR="${BACKUP_DIR:-/opt/imhire-backups}"

if [ ! -f .env.prod ]; then
  echo "Missing .env.prod. Run: cp .env.prod.example .env.prod  and fill it in." >&2
  exit 1
fi

# Read one value from .env.prod without executing the file.
envval() { { grep -E "^$1=" .env.prod || true; } | tail -n 1 | cut -d= -f2- | tr -d '\r'; }

DOMAIN="$(envval DOMAIN)"
dc() { docker compose --env-file .env.prod -f compose.prod.yml "$@"; }

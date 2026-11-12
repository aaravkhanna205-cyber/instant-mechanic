#!/usr/bin/env bash
# Build and start (or update) the production stack. Safe to run again for updates:
# it backs up the database first, then applies migrations, then restarts services.
#   bash scripts/prod-deploy.sh
. "$(dirname "$0")/prod-lib.sh"

chmod 600 .env.prod
PG_PASSWORD="$(envval POSTGRES_PASSWORD)"
if [ -z "$DOMAIN" ] || [ "$DOMAIN" = "hire.example.com" ]; then echo "Set DOMAIN in .env.prod" >&2; exit 1; fi
if [ "$(envval ACME_EMAIL)" = "you@example.com" ] || [ -z "$(envval ACME_EMAIL)" ]; then echo "Set ACME_EMAIL in .env.prod" >&2; exit 1; fi
case "$PG_PASSWORD" in
  ""|*REPLACE*) echo "Set POSTGRES_PASSWORD in .env.prod (openssl rand -hex 24)" >&2; exit 1 ;;
esac
if ! printf '%s' "$PG_PASSWORD" | grep -Eq '^[A-Za-z0-9]{24,}$'; then
  echo "POSTGRES_PASSWORD must be at least 24 letters/digits only (use: openssl rand -hex 24)" >&2; exit 1
fi

if [ -n "$(dc ps -q --status running postgres 2>/dev/null || true)" ]; then
  echo "== Existing database found: backing up before changes"
  bash scripts/prod-backup.sh
fi

echo "== Building images (the first build takes a while)"
dc build

echo "== Starting database, Redis and malware scanner"
dc up -d --wait postgres redis
dc up -d clamav

echo "== Applying database migrations"
dc run --rm api python -m alembic upgrade head
dc run --rm api python -m scripts.seed_job_categories

echo "== Starting all services"
dc up -d

echo "== Waiting for https://$DOMAIN (the first HTTPS certificate can take a minute)"
for attempt in $(seq 1 36); do
  if curl -fsS -m 10 "https://$DOMAIN/api/ready" >/dev/null 2>&1; then
    echo "LIVE: https://$DOMAIN"
    echo "Next: bash scripts/prod-verify.sh"
    exit 0
  fi
  sleep 5
done
echo "Site did not answer yet. Check: docker compose --env-file .env.prod -f compose.prod.yml logs caddy api --tail 60" >&2
exit 1

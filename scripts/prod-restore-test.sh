#!/usr/bin/env bash
# Restore drill: load the newest backup into a throwaway database, count what
# came back, then remove it. The live database is not touched.
. "$(dirname "$0")/prod-lib.sh"

latest="$(ls -1t "$BACKUP_DIR"/db-*.dump 2>/dev/null | head -n 1 || true)"
if [ -z "$latest" ]; then echo "No backup found in $BACKUP_DIR. Run: bash scripts/prod-backup.sh" >&2; exit 1; fi
echo "Restoring $latest into temporary database restore_test"

dc exec -T postgres sh -c 'dropdb -U "$POSTGRES_USER" --if-exists restore_test && createdb -U "$POSTGRES_USER" restore_test'
dc exec -T postgres sh -c 'pg_restore -U "$POSTGRES_USER" -d restore_test --no-owner' < "$latest"
tables="$(dc exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d restore_test -Atc "select count(*) from information_schema.tables where table_schema = '\''public'\''"' | tr -d '\r')"
users="$(dc exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d restore_test -Atc "select count(*) from users"' | tr -d '\r')"
dc exec -T postgres sh -c 'dropdb -U "$POSTGRES_USER" restore_test'

echo "Restored tables: $tables, user accounts: $users"
if [ "${tables:-0}" -lt 10 ]; then echo "RESTORE TEST FAILED: too few tables" >&2; exit 1; fi
echo "RESTORE TEST PASSED"

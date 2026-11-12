#!/usr/bin/env bash
# Back up the database and uploaded resumes to BACKUP_DIR (default /opt/imhire-backups).
# Keeps 14 days. Copy these files off the server regularly as well.
. "$(dirname "$0")/prod-lib.sh"

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"
stamp="$(date -u +%Y%m%d-%H%M%S)"

dc exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$BACKUP_DIR/db-$stamp.dump.tmp"
if [ ! -s "$BACKUP_DIR/db-$stamp.dump.tmp" ]; then echo "Database dump is empty" >&2; exit 1; fi
mv "$BACKUP_DIR/db-$stamp.dump.tmp" "$BACKUP_DIR/db-$stamp.dump"

docker run --rm -v imhire_prod_resume_private_data:/data:ro -v "$BACKUP_DIR":/backup alpine \
  tar czf "/backup/resumes-$stamp.tar.gz" -C /data .

chmod 600 "$BACKUP_DIR"/db-*.dump "$BACKUP_DIR"/resumes-*.tar.gz
find "$BACKUP_DIR" -maxdepth 1 -type f \( -name 'db-*.dump' -o -name 'resumes-*.tar.gz' -o -name '*.tmp' \) -mtime +14 -delete
echo "Backup written: $BACKUP_DIR/db-$stamp.dump and resumes-$stamp.tar.gz"

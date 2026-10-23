#!/bin/bash
# Daily public SQL dump. Runs several times per night (see toolforge_jobs.yaml)
# and does nothing if today's dump already exists and looks complete.
# The table mentor_auth (password hashes) is never included.
set -euo pipefail

DB="s51391__mp"
OUTPUT_DIR="$HOME/public_html/sql-dumps"
OUTPUT_FILE="$OUTPUT_DIR/wpmp-$(date +%F).sql.bz2"

if [ -f "$OUTPUT_FILE" ] && [ "$(stat -c %s "$OUTPUT_FILE")" -gt 1024 ]; then
  exit 0
fi

mariadb-dump --defaults-file="$HOME/replica.my.cnf" --host=tools.db.svc.wikimedia.cloud \
  --ignore-table="$DB.mentor_auth" "$DB" | bzip2 > "$OUTPUT_FILE.tmp"
mv "$OUTPUT_FILE.tmp" "$OUTPUT_FILE"

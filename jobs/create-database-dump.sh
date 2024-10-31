#!/bin/bash

OUTPUT_DIR="/data/project/mp/public_html/sql-dumps"
TODAY=`date +%F`
OUTPUT_FILE="wpmp-$TODAY.sql.bz2"

# We will run this multiple time. If the dump already exists, skip.
if [ ! -f "$OUTPUT_DIR/$OUTPUT_FILE" ]; then
  # file already exists
  DUMP_SIZE=$(du --bytes "$OUTPUT_DIR/$OUTPUT_FILE" | awk '{print $1}')
  
  if [ "$DUMP_SIZE" -gt 1024 ]; then
    # file is big enough
    exit 1
  fi
fi

mariadb-dump --defaults-file=~/replica.my.cnf --host=tools.db.svc.wikimedia.cloud "s51391__mp" | bzip2 > "$OUTPUT_DIR/$OUTPUT_FILE"

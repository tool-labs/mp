#!/bin/bash

OUTPUT_DIR="/data/project/mp/public_html/sql-dumps"
TODAY=`date +%F`
OUTPUT_FILE="wpmp-$TODAY.sql.bz2"
mariadb-dump --defaults-file=~/replica.my.cnf --host=tools.db.svc.wikimedia.cloud "s51391__mp" | bzip2 > "$OUTPUT_DIR/$OUTPUT_FILE"
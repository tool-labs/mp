#!/bin/bash

OUTPUT_DIR="/data/project/mp/public_html/sql-dumps"
TODAY=`date +%F`
OUTPUT_FILE="wpmp-$TODAY.sql.bz2"
mysqldump --defaults-file="/data/project/mp/replica.my.cnf" -h tools-db "s51391__mp" | bzip2 > "$OUTPUT_DIR/$OUTPUT_FILE"

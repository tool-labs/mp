#!/bin/bash

OUTPUT_DIR="/data/project/mp/public_html/sql-dumps"
OLDATE=`date +%F -d "-31 days"`
OUTPUT_FILE="wpmp-$OLDATE*"
rm -f $OUTPUT_DIR/$OUTPUT_FILE

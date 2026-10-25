#!/bin/bash
# Daily: rotate the job logs in logs/ once they exceed MAX_KB and delete
# rotated logs older than KEEP_DAYS. The jobs open their log files anew on
# every run, so renaming them between runs loses nothing.
set -euo pipefail

LOG_DIR="${LOG_DIR:-$HOME/logs}"
OLD_DIR="$LOG_DIR/old"
MAX_KB=1024
KEEP_DAYS=90

cd "$LOG_DIR"
mkdir -p "$OLD_DIR"
today=$(date -u +%F)

# Own logs stay in place: this run is still writing them.
for f in *.out *.err; do
    [ -f "$f" ] || continue
    case "$f" in remove-old-logs.*) continue ;; esac
    [ "$(du -k "$f" | cut -f1)" -gt "$MAX_KB" ] || continue
    target="$OLD_DIR/$f.$today"
    if [ -e "$target" ] || [ -e "$target.gz" ]; then
        continue
    fi
    mv "$f" "$target"
    gzip -9 "$target"
    echo "rotated $f"
done

find "$OLD_DIR" -maxdepth 1 -type f -name '*.gz' -mtime +"$KEEP_DAYS" -print -delete

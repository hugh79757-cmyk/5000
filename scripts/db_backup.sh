#!/bin/bash
BACKUP_DIR="/tmp/db_backups"
DATE=$(date +%Y%m%d)
mkdir -p "$BACKUP_DIR"

DBS=(
  "/Users/twinssn/Projects/5000/data/content.db"
  "/Users/twinssn/Projects/5000/data/car.db"
  "/Users/twinssn/Projects/5000/data/travel-en.db"
  "/Users/twinssn/Projects/5000/data/rap.db"
  "/Users/twinssn/Projects/5000/data/analytics.db"
  "/Users/twinssn/Projects/5000/data/stock.db"
  "/Users/twinssn/Projects/STAP/data/stap.db"
  "/Users/twinssn/Projects/STAP/data/stap_content.db"
)

for db in "${DBS[@]}"; do
  name=$(basename "$db" .db)
  sqlite3 "$db" ".backup '$BACKUP_DIR/${name}_${DATE}.db'" 2>/dev/null && echo "OK: $name" || echo "FAIL: $name"
done

# 7일 이전 백업 삭제
find "$BACKUP_DIR" -name "*.db" -mtime +7 -delete
echo "Cleanup done. Files:"
ls -lh "$BACKUP_DIR"

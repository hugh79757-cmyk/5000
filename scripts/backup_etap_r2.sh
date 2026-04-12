#!/bin/zsh

export PATH="/opt/homebrew/bin:$PATH"

BACKUP_DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="/tmp/etap_backup_${BACKUP_DATE}.tar.gz"

echo "Compressing ETAP content only..."

# content와 config만 백업
tar czf "$BACKUP_FILE" \
  $(for dir in /Users/twinssn/Projects/ETAP/*-hugo; do
    echo "$dir/content"
    echo "$dir/config"
  done)

SIZE=$(du -h "$BACKUP_FILE" | awk '{print $1}')
echo "Backup size: $SIZE"

echo "Uploading to R2..."
source /Users/twinssn/Projects/5000/.env
export CLOUDFLARE_ACCOUNT_ID CLOUDFLARE_API_TOKEN

/opt/homebrew/bin/wrangler r2 object put "${R2_BUCKET_NAME}/backups/etap_backup_${BACKUP_DATE}.tar.gz" --file="$BACKUP_FILE" 2>&1

rm -f "$BACKUP_FILE"
echo "Done: etap_backup_${BACKUP_DATE}.tar.gz"

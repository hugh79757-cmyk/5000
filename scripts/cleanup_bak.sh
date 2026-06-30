#!/bin/bash
# Cleanup backup files from source directories
# Usage: ./scripts/cleanup_bak.sh [--dry-run]

set -euo pipefail

EXCLUDE_PATHS=(
  ".git"
  ".venv"
  "node_modules"
  "public"
  ".planning"
)

PATTERNS=(
  "*.bak*"
  ".*.bak*"
  "*.v1_bak"
  "*.fix_bak"
  "*-bak"
  "*.feat-bak"
  "*.dedup-bak"
  "*.final_bak"
  "*.topic-bak"
  "*_bak"
  "*.ev-bak"
  "*.map-bak"
)

build_find_args() {
  local args=()
  for excl in "${EXCLUDE_PATHS[@]}"; do
    args+=(-not -path "./${excl}/*")
  done
  args+=("(")
  local first=true
  for pat in "${PATTERNS[@]}"; do
    if [ "$first" = true ]; then
      first=false
    else
      args+=(-o)
    fi
    args+=(-name "$pat")
  done
  args+=(")")
  printf '%s\0' "${args[@]}"
}

DRY_RUN=false
if [ "${1:-}" = "--dry-run" ]; then
  DRY_RUN=true
fi

FILES=$(find . -not -path './.git/*' -not -path './.venv/*' -not -path './node_modules/*' -not -path './public/*' -not -path './.planning/*' \( \
  -name '*.bak*' -o \
  -name '*.v1_bak' -o \
  -name '*.fix_bak' -o \
  -name '*-bak' -o \
  -name '*.feat-bak' -o \
  -name '*.dedup-bak' -o \
  -name '*.final_bak' -o \
  -name '*.topic-bak' -o \
  -name '*_bak' -o \
  -name '*.ev-bak' -o \
  -name '*.map-bak' \) 2>/dev/null | sort)

if [ -z "$FILES" ]; then
  echo "No backup files found."
  exit 0
fi

COUNT=$(echo "$FILES" | wc -l | tr -d ' ')
echo "Found ${COUNT} backup file(s):"
echo "$FILES" | while IFS= read -r f; do
  echo "  $f"
done

if [ "$DRY_RUN" = true ]; then
  echo ""
  echo "[DRY-RUN] Would delete ${COUNT} file(s). Pass without --dry-run to execute."
  exit 0
fi

echo ""
echo "Deleting ${COUNT} file(s)..."
echo "$FILES" | while IFS= read -r f; do
  rm -v "$f"
done
echo "Done."

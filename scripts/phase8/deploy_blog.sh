#!/bin/bash
# deploy_blog.sh — Hugo 빌드 + wrangler 배포
# - ~/.env.common 을 자동으로 로드 (없으면 skip)
# - 첫 번째 인자: blog_id (예: laptop-hugo)

set -euo pipefail

BLOG_ID="${1:-}"
CUAP_ROOT="/Users/twinssn/Projects/CUAP"
COMMON_ENV="$HOME/.env.common"

if [ -z "$BLOG_ID" ]; then
  echo "Usage: $0 <blog-id>"
  echo "Example: $0 laptop-hugo"
  exit 1
fi

BLOG_DIR="$CUAP_ROOT/$BLOG_ID"
if [ ! -d "$BLOG_DIR" ]; then
  echo "ERROR: Blog directory not found: $BLOG_DIR"
  exit 1
fi

# ── Load .env.common fallback (없거나 이미 로드된 env는 스킵)
if [ -f "$COMMON_ENV" ]; then
  set -a
  source "$COMMON_ENV"
  set +a
fi

# ── Hugo build
echo "=== $BLOG_ID: Hugo build ==="
cd "$BLOG_DIR"
/opt/homebrew/bin/hugo --gc --minify

# ── Deploy
WRANGLER="/opt/homebrew/bin/wrangler"
if [ -f "$BLOG_DIR/wrangler.toml" ]; then
  echo "=== $BLOG_ID: wrangler deploy ==="
  $WRANGLER deploy
else
  echo "=== $BLOG_ID: wrangler pages deploy ==="
  $WRANGLER pages deploy . --project-name="$BLOG_ID"
fi

echo "=== $BLOG_ID: Done ==="

#!/usr/bin/env bash
# STATE.md Phase 54가 지목한 fallback 제목 패턴 글 색출
set -uo pipefail
cd /Users/twinssn/projects/5000

echo "=== content.db publish_ledger 에서 fallback 패턴 제목 ==="
sqlite3 data/content.db "
SELECT id, blog_id, created_at, title
FROM publish_ledger
WHERE title LIKE '%추천 TOP5%'
   OR title LIKE '%추천 TOP 5%'
   OR title GLOB '*추천 TOP[0-9]*'
ORDER BY created_at DESC LIMIT 50;" 2>/dev/null || echo "(조회 실패)"

echo
echo "=== curation.db 가 별도라면 거기도 확인 ==="
[ -f data/curation.db ] && sqlite3 data/curation.db "
SELECT name FROM sqlite_master WHERE type='table';" 2>/dev/null

echo
echo "=== cuap site_path 내 baked 파일에서 패턴 검색 (site_path는 audit 결과로 대체) ==="
CUAP_ROOT="/Users/twinssn/Projects/cuap"
if [ -d "$CUAP_ROOT" ]; then
  grep -rl --include="*.md" -E 'title:.*(추천 TOP ?5|추천 TOP[0-9])' "$CUAP_ROOT" 2>/dev/null | head -50
else
  echo "(cuap 경로 확인 필요 — audit.sh의 site_path 참고)"
fi

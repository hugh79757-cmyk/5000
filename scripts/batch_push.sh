#!/bin/bash
# ============================================
# 여행 블로그 5개 일괄 push
# 사용법: bash /tmp/batch_push.sh
# ============================================

REPOS=(
  "/Users/twinssn/Projects/travel-hugo"
  "/Users/twinssn/Projects/travel1-hugo"
  "/Users/twinssn/Projects/travel2-hugo"
  "/Users/twinssn/Projects/travel3-hugo"
  "/Users/twinssn/Projects/travel4-hugo"
)

TIMESTAMP=$(date +"%Y-%m-%d %H:%M")
SUCCESS=0
SKIP=0
FAIL=0

echo "===== 배치 Push 시작: $TIMESTAMP ====="
echo ""

for REPO in "${REPOS[@]}"; do
  NAME=$(basename "$REPO")
  echo "--- $NAME ---"

  if [ ! -d "$REPO/.git" ]; then
    echo "  [SKIP] Git repo 아님"
    SKIP=$((SKIP + 1))
    echo ""
    continue
  fi

  cd "$REPO" || continue

  CHANGES=$(git status --porcelain)
  if [ -z "$CHANGES" ]; then
    echo "  [SKIP] 변경사항 없음"
    SKIP=$((SKIP + 1))
    echo ""
    continue
  fi

  FILE_COUNT=$(echo "$CHANGES" | wc -l | tr -d ' ')
  echo "  변경 파일: ${FILE_COUNT}개"

  git add -A
  git commit -m "publish: ${TIMESTAMP} 일괄 발행 (${FILE_COUNT}건)" --quiet

  if git push origin main --quiet 2>/dev/null; then
    echo "  [OK] push 완료"
    SUCCESS=$((SUCCESS + 1))
  else
    echo "  [RETRY] pull 후 재시도..."
    git pull --rebase origin main --quiet 2>/dev/null
    if git push origin main --quiet 2>/dev/null; then
      echo "  [OK] push 완료 (재시도)"
      SUCCESS=$((SUCCESS + 1))
    else
      echo "  [FAIL] push 실패"
      FAIL=$((FAIL + 1))
    fi
  fi
  echo ""
done

echo "===== 결과 ====="
echo "  성공: ${SUCCESS}개"
echo "  스킵: ${SKIP}개 (변경없음)"
echo "  실패: ${FAIL}개"
echo "  빌드 소모: ${SUCCESS}회"
echo "  월간 예상 (매일 1회): $((SUCCESS * 30))회 / 500회"

#!/usr/bin/env bash
cd /Users/twinssn/projects/5000
sep() { echo; echo "========== $1 =========="; echo; }

sep "1. 문제의 publish 구간 라인번호 확인"
grep -n "result = publish(blog_id, title" pipelines/curation/pipeline.py
grep -n 'reason": "publish_error"' pipelines/curation/pipeline.py
grep -n '"success": True,' pipelines/curation/pipeline.py

sep "2. 해당 구간 원본 (앞뒤 8줄)"
_ln=$(grep -n "result = publish(blog_id, title" pipelines/curation/pipeline.py | head -1 | cut -d: -f1)
[ -n "$_ln" ] && sed -n "$((_ln-1)),$((_ln+12))p" pipelines/curation/pipeline.py

sep "3. dead code 여부 확인: return 이후 라인들이 실행 불가인지"
python3 -c "
import ast
src = open('pipelines/curation/pipeline.py').read()
tree = ast.parse(src)
print('AST 파싱 OK — 구문 자체는 유효(그래서 silent). 논리적 dead code임')
"

sep "4. 최근 curation publish_error 실패 건수 (오늘)"
sqlite3 data/content.db "SELECT blog_id, COUNT(*) FROM publish_ledger WHERE stage='publish_error' AND date(created_at)=date('now') GROUP BY blog_id;" 2>/dev/null

sep "5. 실제로 Hugo에는 글이 써졌는지 대조 (오늘 생성된 파일 수)"
for b in health-hugo camping-hugo baby-hugo beauty-hugo; do
  n=$(find "/Users/twinssn/Projects/cuap/$b/content/posts" -type f -name "*.md" -newermt "today 00:00" 2>/dev/null | wc -l | tr -d ' ')
  echo "$b: 오늘 생성 .md = $n개  (ledger publish_error와 대조)"
done

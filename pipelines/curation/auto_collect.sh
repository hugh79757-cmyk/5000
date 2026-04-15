#!/bin/bash
# 전체 자동화: 키워드 확장 → 부족한 키워드만 쿠팡 재수집
# 발행은 기존 파이프라인(scheduler)이 담당 — 이 스크립트는 상품 풀만 채움
# crontab: 매주 일요일 02:00

cd /Users/twinssn/Projects/5000
source .venv/bin/activate

echo "========================================"
echo " CURATION 자동 수집 시작: $(date)"
echo "========================================"

# Step 1: 네이버 트렌드 동기화 (ratio 갱신)
echo "[1/3] 네이버 데이터랩 트렌드 동기화..."
python3 pipelines/curation/naver_datalab_sync.py all

# Step 2: 키워드 자동완성 확장
echo "[2/3] 키워드 확장 (자동완성 + 쇼핑 API)..."
python3 pipelines/curation/keyword_expander.py all

# Step 3: 부족한 키워드만 쿠팡 재수집
# ※ KEYWORD_MAP 직접 읽지 않고 curation.db의 products 테이블 기준으로만 처리
# ※ 발행 중복 체크(publish_log)는 기존 파이프라인이 담당
echo "[3/3] 쿠팡 상품 부족 키워드 재수집..."
python3 << 'PYEOF'
import sys, os, sqlite3, time
sys.path.insert(0, '/Users/twinssn/Projects/5000')
os.chdir('/Users/twinssn/Projects/5000')

from dotenv import load_dotenv
load_dotenv('/Users/twinssn/Projects/5000/.env')

from pipelines.curation.collector import collect_keyword

DB = '/Users/twinssn/Projects/5000/data/curation.db'

def get_conn():
    return sqlite3.connect(DB)

# naver_trending_keywords DB에서 키워드 가져오기 (keywords.py 직접 읽기 ❌)
conn = get_conn()
blog_keywords = {}
rows = conn.execute("""
    SELECT blog_id, keyword
    FROM naver_trending_keywords
    ORDER BY blog_id, ratio DESC
""").fetchall()
conn.close()

for blog_id, keyword in rows:
    blog_keywords.setdefault(blog_id, []).append(keyword)

total_ok = total_low = total_fail = total_skip = 0

for blog_id, keywords in blog_keywords.items():
    print(f"\n--- {blog_id}: {len(keywords)}개 키워드 점검 ---")
    ok = low = fail = skip = 0

    for kw in keywords:
        # products DB에서 현재 상품 수 확인
        cnt = get_conn().execute(
            "SELECT COUNT(*) FROM products WHERE keyword=?", (kw,)
        ).fetchone()[0]

        if cnt >= 5:
            skip += 1
            continue  # 충분 → 스킵

        # 부족한 경우만 재수집
        try:
            collect_keyword(kw)
            cnt2 = get_conn().execute(
                "SELECT COUNT(*) FROM products WHERE keyword=?", (kw,)
            ).fetchone()[0]
            if cnt2 >= 3:
                ok += 1
                print(f"  ✅ {kw}: {cnt}→{cnt2}개")
            elif cnt2 > 0:
                low += 1
            else:
                fail += 1
        except Exception as e:
            fail += 1
            print(f"  💥 {kw}: {e}")
        time.sleep(0.4)

    print(f"  결과: 충분(스킵)={skip} / 수집성공={ok} / 부족={low} / 실패={fail}")
    total_ok += ok; total_low += low
    total_fail += fail; total_skip += skip

# 최종 DB 현황
conn = get_conn()
total_kw  = conn.execute("SELECT COUNT(DISTINCT keyword) FROM products").fetchone()[0]
total_ok3 = conn.execute("""
    SELECT COUNT(DISTINCT keyword) FROM products
    GROUP BY keyword HAVING COUNT(*) >= 3
""").fetchall()
conn.close()

print(f"""
========================================
 수집 완료: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}
 전체 키워드: {total_kw}개
 상품 3개↑:  {len(total_ok3)}개
 신규수집: 성공={total_ok} / 부족={total_low} / 실패={total_fail} / 스킵={total_skip}
========================================
""")
PYEOF

echo ""
echo "========================================"
echo " auto_collect.sh 완료: $(date)"
echo "========================================"

"""sigungu 중복 체크 단위 테스트 — 5케이스"""
import sys, sqlite3
from datetime import datetime

sys.path.insert(0, '/Users/twinssn/Projects/TAP')
sys.path.insert(0, '/Users/twinssn/Projects/5000')

from shared.db_paths import ARTICLES_DB
from pipelines.travel.pipeline import _travel_sigungu_recently_published

conn = sqlite3.connect(ARTICLES_DB)

# 테스트 데이터 준비
now = datetime.now().isoformat()

# 케이스 1용: sigungu 컬럼 있는 row
conn.execute("""
    INSERT INTO articles (blog_id, title, status, created_at, sigungu, category)
    VALUES ('travel3-hugo', '[TEST-A] 삭제용', 'published', ?, '속초', '맛집')
""", (now,))

# 케이스 5용: sigungu NULL + title 파싱 fallback
conn.execute("""
    INSERT INTO articles (blog_id, title, status, created_at, sigungu, category)
    VALUES ('travel3-hugo', '강릉 맛집 추천 3곳 정리', 'published', ?, NULL, '맛집')
""", (now,))

conn.commit()
conn.close()

results = {}

# 케이스 1: sigungu 컬럼 직접 매칭 → True
results[1] = _travel_sigungu_recently_published("travel3-hugo", "속초", 14)

# 케이스 2: 다른 시군구 → False
results[2] = _travel_sigungu_recently_published("travel3-hugo", "원주", 14)

# 케이스 3: 빈 sigungu → False
results[3] = _travel_sigungu_recently_published("travel3-hugo", "", 14)

# 케이스 4: lookback_days=0 → False
results[4] = _travel_sigungu_recently_published("travel3-hugo", "속초", 0)

# 케이스 5: title fallback (sigungu=NULL 건) → True
results[5] = _travel_sigungu_recently_published("travel3-hugo", "강릉", 14)

# 테스트 row 정리
conn = sqlite3.connect(ARTICLES_DB)
conn.execute("DELETE FROM articles WHERE blog_id='travel3-hugo' AND title LIKE '[TEST-%'")
conn.execute("DELETE FROM articles WHERE blog_id='travel3-hugo' AND title='강릉 맛집 추천 3곳 정리' AND sigungu IS NULL")
conn.commit()
conn.close()

# 결과 출력
expected = {1: True, 2: False, 3: False, 4: False, 5: True}
all_pass = True
for k, exp in expected.items():
    got = results.get(k)
    ok = "✅" if got == exp else "❌"
    if got != exp:
        all_pass = False
    print(f"  케이스 {k}: 기대={exp}, 실제={got} {ok}")

print()
print("✅ 전체 통과" if all_pass else "❌ 실패 케이스 있음")

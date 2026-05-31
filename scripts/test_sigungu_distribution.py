"""시군구 분산 검증 — area_codes 가중치 dry-run"""
import sys, os

# area_codes.py 직접 로드
_area_codes_path = '/Users/twinssn/Projects/TAP/pipelines/travel/area_codes.py'
_ns = {}
with open(_area_codes_path, 'r', encoding='utf-8') as _f:
    exec(compile(_f.read(), _area_codes_path, 'exec'), _ns)

get_weighted_random_sigungu = _ns['get_weighted_random_sigungu']
FOOD_AREA_SIGUNGU_WEIGHTED = _ns['FOOD_AREA_SIGUNGU_WEIGHTED']

from collections import Counter

# 총 시군구 수 확인
print(f"총 시군구: {len(FOOD_AREA_SIGUNGU_WEIGHTED)}개")
tier3 = sum(1 for x in FOOD_AREA_SIGUNGU_WEIGHTED if x[3] == 3)
tier2 = sum(1 for x in FOOD_AREA_SIGUNGU_WEIGHTED if x[3] == 2)
tier1 = sum(1 for x in FOOD_AREA_SIGUNGU_WEIGHTED if x[3] == 1)
print(f"  TIER_A(가중치 3): {tier3}개")
print(f"  TIER_B(가중치 2): {tier2}개")
print(f"  TIER_C(가중치 1): {tier1}개")

# 500회 가중치 랜덤 시뮬레이션
results = [get_weighted_random_sigungu()[2] for _ in range(500)]
dist = Counter(results)

# 상위 15개
print("\n=== 상위 15개 시군구 (500회 샘플) ===")
for name, cnt in dist.most_common(15):
    bar = "█" * (cnt // 5)
    print(f"  {name:<12} {bar} ({cnt}회)")

# 검증
gangneung_cnt = sum(1 for r in results if r == '강릉시')
jangsu_cnt    = sum(1 for r in results if r == '장수군')
total_weight  = sum(x[3] for x in FOOD_AREA_SIGUNGU_WEIGHTED)

print(f"\n강릉시(가중치3): {gangneung_cnt}/500 → {'⚠️ 과다' if gangneung_cnt > 30 else '✅ 정상'}")
print(f"장수군(가중치1): {jangsu_cnt}/500 → {'⚠️ 과다' if jangsu_cnt > 5 else '✅ 정상'}")

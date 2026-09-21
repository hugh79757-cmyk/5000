# Worklog: WL-20260920-rap-keyword-region-fix
**Date:** 2026-09-20  
**Scope:** Data lane fix — R-3 (rap/rap4 keyword-region mismatch)  
**Commit:** 644104207  

## Pre-count
- rap-hugo: 18연속 실패 (no_trade_data)
- rap4-hugo: 8연속 실패 (no_trade_data)  
- trades 테이블: 49,228건 (2026-03~09) — 데이터 고갈 아님
- 09-19 키 로테이션 이전부터 실패 — 키 무관 입증

## Changes
1. **BLOG_REGION_POOL 모듈 레벨 이동** (run() 내부 중복 제거)
2. **ALL_KNOWN_DISTRICTS + _extract_district_from_keyword()** 신규 — find_lawd_cd false positive 회피
3. **_pick_keyword() 4단계 지역 풀 검증 추가**
   - 키워드에서 district 추출 → 허용 풀 매칭 필수
   - district 없는 일반 키워드 제외 (랜덤 fallback 방지)
4. **Q-D 필터 완화**
   - 30일 → 7일 lookback 단축
   - 잔여 허용 district 2개 미만이면 차단 해제
5. **run() 랜덤 fallback** 모듈 레벨 BLOG_REGION_POOL 참조로 통일

## Post-verify
- rap-hugo 5회 test run: 서초구/송파구 키워드 선택, trades 3건/건
- rap4-hugo 5회 test run: 동작구/마포구/양천구/관악구 키워드 선택, trades 3건/건
- no_trade_data 발생 0건

## Log entries
- logs/destructive_2026-09-20.log: 커밋 기록됨

---
date: 2026-08-05
type: fix
status: resolved
---

# KEYWORD_MAP 전수 감사 — low_relevance 위험 키워드 377개 제거 + camping-hugo 실패 해소

## What

- **전 블로그(15개) KEYWORD_MAP 전수 감사**: low_relevance 발행 실패 위험 키워드를 실제 파이프라인 로직(score_products → adaptive threshold → 개별 drop → passes_gate) 재현 스캔으로 식별 → **589 고유쌍 → 212 고유쌍으로 감소** (제거 377쌍/381토큰, KEYWORD_MAP 2,982 → 2,601)
- **camping-hugo low_relevance 연쇄 실패 해소**: 일반명 키워드(조명/난로/선풍기) 제거 + 스케줄러 재시작으로 발행 성공 복구
- 스캐너/삭제 엔진 신규 도구화: `scripts/scan_keyword_relevance.py`, `scripts/apply_keyword_removals.py`

## Why

- 지금까지 "문제 터질 때마다 키워드 제거" 방식은 소방수식 대응 — 같은 패턴의 일반명/가비지 키워드가 전체의 20% 차지
- **3대 원인 유형**: ① 외국어혼합 가비지 256쌍 (`캠핑基础装备推荐`, `크ампоинг 推荐` — 쿠팡 검색 불가), ② 완전 오프토픽 82쌍 (`고구마`→식품, `데님`→의류), ③ 부분 매치 일반명 124쌍 (`조명`→가정용 조명, `카트`→쇼핑카트)
- '카트'(avg 0.59, 경계값)가 실제 16:21 low_relevance 실패 — 개별 drop 후 3개 미만이면 전체 평균으로 판정하는 게이트 특성상 경계값도 실패 가능
- low_relevance 3회 이상 시 keyword_health에서 90일 격리 (keyword_health.py:124)

## Files changed

- `pipelines/curation/keywords.py` — KEYWORD_MAP 위험 키워드 토큰 단위 삭제 (A 256 + B0 82 + B1 39 = 377쌍)
- `scripts/scan_keyword_relevance.py` (신규) — 파이프라인 게이트 재현 스캐너 + A/B0/B1/C 분류
- `scripts/apply_keyword_removals.py` (신규) — ast 기반 토큰 단위 삭제 엔진 (블록 스코프, SKIP_ARTIFACT 처리)
- `.planning/quick/260805-n1j-keyword-map-low-relevance-601/` — PLAN/SUMMARY/VERIFICATION + kw_removal_log.json (589쌍 전수 감사), kw_b1_review.json (124건)

## How

- 실제 게이트 로직 재현 스캔으로 위험 셋 589 고유쌍 산출 (충실도 게이트 통과: 601행 − 중복 12행 = 589)
- 분류 규칙: A_FOREIGN(한자/가나/키릴) + B0_OFFTOPIC(상품 8개 전부 미매치) → 자동 제거 / B1_REVIEW(부분 매치) → 상품명 8개 샘플 검토, 불확실 시 KEEP
- **토큰 단위 삭제** (전체 줄 삭제 금지 — 위험 601행 중 75%가 다중 키워드 라인 혼재): ast 블록 스코프로 `"키워드",` 토큰만 제거
- 결합 아티팩트 2건(`귀체온계카시트`/`노트북가을`, 쉼표 누락)은 SKIP_ARTIFACT 유지
- B1 124쌍: 39 제거 / 84 유지 / 1 SKIP_ARTIFACT — Latin/숫자 키워드(SSD512GB, AMD라이젠5, 골프드라이버)는 상품 검증 후 KEEP (오제거 방지)
- 스케줄러 재시작 불필요 확인 — scheduler.py:263 subprocess dispatch가 매 실행 fresh import

## Verification

- 재스캔 `RISK UNIQUE: 212 ≤ 261` (하드 게이트 통과), missing=377/extra=0 (신규 위험 0)
- SET_DIFF 무결성: 377쌍 제거, 0 collateral, 0 remaining / fresh-import: total=2601 (2982−381), removed_absent=377
- 유지 예시(SSD512GB, 골프드라이버) present — 오제거 0건
- 파이프라인 로직(pipeline.py/relevance_scorer.py/keyword_health.py)/curation.db/테스트 코드 무변경
- 테스트 기준선 불변: 4 failed/3 passed (사전 존재 실패, 작업 후 동일)
- camping-hugo 발행 성공 확인 (16:27, keyword=가스통)
- 커밋: `a8ed1ec30` + `bd98db2ef` (docs 포함 `13cda9e89`), push 완료

## 잔존 위험

- 결합 아티팩트 2건 + 쉼표 누락 5줄 (326/531/534/654/715행) — 포맷 정리 별도 항목
- camping-hugo '카트'/'난로'는 KEEP 유지 — '카트'는 16:21 실패 전례 있음, 재실패 시 재검토 필요
- auto_collector 캐시는 다음 자연 재시작까지 구버전 키워드로 수집 가능 (무해 — 미사용 products 행)
- KEEP분 210쌍은 스코어링 아티팩트 성격 — 상품 DB 변동 시 재분류 필요

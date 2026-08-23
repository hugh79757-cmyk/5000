# WL-20260816-gatefix-fallback-verification

> 날짜: 2026-08-16 | 작업: similar_title fallback 게이트 재적용 커밋 + 실발행 검증 + 오염 정리

## 요약

- 커밋 `31debf58f` — `fix(curation): similar_title fallback에 관련성 게이트 재적용 — 무관 상품 발행 차단 + fail-open 빈도 로그` (pipeline.py +29줄)
- 수정1: fallback 키워드+상품 교체 후 `_filter_irrelevant_products` + `score_products`/`get_adaptive_threshold`/`passes_gate` 재적용, 미달 시 `_record_failure('low_relevance')` + return (quarantine 자동 연동)
- 수정2: fail-open except 진입 시 `logs/relevance_failopen.log`에 blog_id/keyword/attempt/예외 append (avg=1.0 덮어쓰기는 유지 — 다음 단계)
- 함수검증: verify_gatefix.py 3/3 PASS (차단+격리 / 정상 발행 / 정상 경로 무영향). pytest 회귀 0건 (기존 실패 18건과 기준선 동일)
- 실발행: appliance-hugo '물걸레' 1회 → success (avg=1.00, product_count=5). fallback 미진입 (첫 시도 통과) → [3] 모니터링 전환

## 파괴적 작업

| 시각 | 작업 | 사전카운트 | 백업 | 사후 | 보존확인 |
|------|------|-----------|------|------|---------|
| 2026-08-16 10:59-11:00 | DELETE publish_ledger id 60267-60272 (verify 스크립트 오염 6행) | 6 (전부 failed) | data/content.db.bak_pollution_20260816_105938 | 0행 | published 28210 유지, published&source='' 12801 유지 |

- 로그: `logs/destructive_2026-08-16.log` 1행 append

## 위반 감지 (재발 방지 기록)

- **verify_gatefix.py가 프로덕션 content.db publish_ledger 오염**: `_record_failure`가 LEDGER_DB(content.db)에 직접 INSERT하는데 patch 목록에 mock 누락. health_store/DB_PATH만 패치되어 curation.db는 보호됐으나 ledger는 보호 못 함.
- 교훈: 검증 스크립트의 patch 목록에 `_record_failure`/ledger 쓰기 mock을 반드시 포함. 테스트 대상 함수의 모든 사이드 이펙트 지점(특히 하드코딩된 경로 상수)을 점검.
- 이후 함수검증 시 `patch.object(pipeline, '_record_failure', lambda *a, **k: None)` 필수.

## 검증 근거 (실명령 출력)

- 실발행 결과: `{"success": true, "title": "강력한 흡입력의 물걸레 무선청소기 모델별 비교 분석", "keyword": "물걸레 무선청소기", "product_count": 5}`
- pipeline:1025 `[appliance-hugo] 관련성 점수: avg=1.00, min=1.00, 임계값=0.65` — 첫 시도 통과, fallback 미진입
- publish_log id 2350: avg=1.0/min=1.0/passed=1. 08-16 신규 avg=0.0+passed=1 0건
- ledger 11:01:12 published 1건 (유사제목 failed 없음). relevance_failopen.log 미생성 (fail-open 미발동)
- 키워드 건강: appliance-hugo 신규 격리 없음 (laptop-hugo 격리는 기존 유사제목 실패의 정상 동작)

## 모니터링 기준 (fallback 자연 발동 대기 — 7일)

1. publish_log에서 신규 avg<0.70 발행 0건 (특히 avg=0.0+validation_passed=1)
2. `logs/relevance_failopen.log` 생성/증가 시 보고 (수정2 빈도 수집 목적)
3. fallback 진입 판별: ledger에서 같은 블로그의 failed|similar_title → published 패턴, 또는 curation.db keyword_health 격리 신규 발생

## 잔존 작업 (다음 단계 유보)

- 수정2 fail-open avg=1.0 덮어쓰기 제거 (fail-closed 전환) — 빈도 데이터 수집 후
- 수정3: 감사 `passed=True` 하드코딩 → 실게이트 결과 연동 (컨슈머는 scripts/health_dashboard.py CLI뿐, 안전 확인됨)
- 파이프라인 내부 로그 scheduler 폐기 문제 (stdout 마지막 3줄만 [OUT]) — fallback 판정이 DB 간접 증거로만 가능

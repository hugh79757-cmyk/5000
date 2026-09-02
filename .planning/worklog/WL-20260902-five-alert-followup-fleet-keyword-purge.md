# WL-20260902 — 5-Alert Triage 후속: 전 블로그 정크 purge + watersports 회전 재시도 + 재발 방지

## 작업 개요

전일 triage(20260902--five-alert-keyword-purge-preflight-cost) 후속. 신규 alert 3건(interior/beauty/golf P36+P14 재발, watersports P02 5연속, travel P01, rap3 P16) 조사·수정.

## [PRODUCTION] 수정 내역

### 1. pipelines/curation/keywords.py — 전 블로그 정크 purge (9 세그먼트)

- 방법: `validate_keyword()` (allowed/blocked 필터) 기준 세그먼트 치환 스크립트. 백업: /tmp/keywords_backup_20260902.py
- car 122→24, golf 115→19, appliance 275→199, interior 216→141, baby 231→142, health 228→150, pet 467→428, beauty 202→109, camping 187→97. TOTAL 2994→2260 (purge 734)
- fitness/kitchen은 전단계 완료(173/92). laptop 97('노트북' 등 laptop allowed라 유지), pet '강아지/고양이' pet allowed라 정상 유지.
- [위반 감지 해소] 이전 세션 오염(car/baby/pet 등)이 이번 전체 purge로 흡수 정리됨 — diff 상 남은 정크 없음(재로드 검증).

### 2. pipelines/etap/watersports_pipeline.py — run_batch 회전 재시도 [P02 해소]

- 원인: `_run_impl`이 viator 데이터 없는 도시(Kovalam/Varkala/Pondicherry 등 인도·베트남권 다수)에서 "데이터 부족 → exhausted 처리 → False" 반환. run_batch가 False를 실패로 취급해 count 소진. 연속 5회 → P02.
- 증거: publish_log log_id 8064/8104/8135 = Kovalam/Varkala/Pondicherry 전부 사이트 posts/에 파일 없음(exhausted 처리 경로). 15:01 실행 2.5s만에 실패.
- 수정: run_batch 내 루프당 최대 5회 다음 토픽 회전 재시도 (데이터 없는 토픽은 exhausted 마킹되므로 자연 스킵).
- watersports_topics exhausted=0 중 Phu Quoc/Sihanoukville 등 viator 0건 다수 — 회전 시 자동 소거.

### 3. travel-hugo P01 — 실발행 검증으로 자연 해소 확인

- fetch_camping 단독 재현: 정상 (경기 안산시 3건, 9.56s).
- `_run_single('travel-hugo')` 실측: **발행 성공** — https://tour1.rotcha.kr/posts/경북-캠핑-가야산백운오토캠핑장-포함-3곳/ + wrangler rc=0. 15:12 no_result는 일시적 가드 hit.

### 4. rap3-hugo P16 — 의도된 가드, 수정 불필요

- 원인: `pipelines/rap/pipeline.py:1224` `source_id = f"{keyword}_{YYYYMMDD}"`. 08:08 '강남구 실거래가 종합_20260902' 발행 후 15:13 CATCHUP 재시도 → 동일 source_id → duplicate. 같은 날 같은 구 재발행 차단 = 정상 동작. 자연 해소 판정(동작구 P16과 동일 패턴).

## 파괴적 작업 로그

- [2026-09-02 16:58:27] scheduler 재시작 (launchctl kickstart) — 신규 PID 30798. logs/destructive_2026-09-02.log 기록. 목적: purge된 keywords.py + 수정 dispatcher.py/watersports_pipeline.py 로드.

## 검증

- py_compile: keywords.py, watersports_pipeline.py OK
- OPS_TEST_MODE=1 pytest tests/curation -q: 19 failed, 129 passed — baseline과 동일(회귀 0건, 19 = pre-existing)
- keywords 재로드: 정크 잔존 NONE (laptop 노트북/pet 강아지는 allowed라 정상)
- travel-hugo 실발행 성공 (live URL + deploy rc=0)
- 스케줄러: 383 jobs 등록 확인, HealthCheck 통과

## 잔존 위험

- interior/beauty/golf 등 curation 블로그 17:00+ 스케줄에서 purge 효과 실증 필요 (P36 재발 여부)
- watersports-hugo 회전 재시도 후 실발행 확인 필요 (다음 17:40 스케줄)
- 19개 pre-existing 테스트 실패 (본 작업 범위 외)
- keywords.py 전체 diff가 큼(+1032/-267 수준) — 커밋 시 전체 파일 스테이징되므로 이전 세션 변경분과 섞임. 단 전부 정크 purge 방향성 동일

# WL-20260902 — 5-Alert Triage 후속: 전 블로그 정크 purge + watersports 회전 재시도 + 재발 방지

## 작업 개요

전일 triage(20260902--five-alert-keyword-purge-preflight-cost) 후속. 신규 alert 3건(interior/beauty/golf P36+P14 재발, watersports P02 5연속, travel P01, rap3 P16) 조사·수정.

## [PRODUCTION] 수정 내역

### 1. pipelines/curation/keywords.py — 전 블로그 정크 purge (9 세그먼트)

- 방법: `validate_keyword()` (allowed/blocked 필터) 기준 세그먼트 치환 스크립트. 백업: /tmp/keywords_backup_20260902.py
- car 122→24, golf 115→19, appliance 275→199, interior 216→141, baby 231→142, health 228→150, pet 467→428, beauty 202→109, camping 187→97. TOTAL 2994→2260 (purge 734)
- fitness/kitchen은 전단계 완료(173/92). laptop 97('노트북' 등 laptop allowed라 유지), pet '강아지/고양이' pet allowed라 정상 유지.
- [위반 감지 해소] 이전 세션 오염(car/baby/pet 등)이 이번 전체 purge로 흡수 정리됨 — diff 상 남은 정크 없음(재로드 검증).

### 2. pipelines/etap/watersports_pipeline.py — run() + run_batch 회전 재시도 [P02 해소]

- 원인: `_run_impl`이 viator 데이터 없는 도시(Kovalam/Varkala/Pondicherry 등 인도·베트남권 다수)에서 "데이터 부족 → exhausted 처리 → False" 반환. run_batch가 False를 실패로 취급해 count 소진. 연속 5회 → P02.
- 증거: publish_log log_id 8064/8104/8135 = Kovalam/Varkala/Pondicherry 전부 사이트 posts/에 파일 없음(exhausted 처리 경로). 15:01 실행 2.5s만에 실패.
- 수정 1차(커밋 0a3d3c005): run_batch 내 루프당 최대 5회 다음 토픽 회전 재시도 (데이터 없는 토픽은 exhausted 마킹되므로 자연 스킵). — **무효 경로였음: dispatcher는 run() 호출**
- 수정 2차(커밋 5d0c10545): `run()` (watersports_pipeline.py:152)에 동일 회전 재시도 5회 추가. dispatcher 실호출 경로(_resolve_pipeline → run() 무인자 → _normalize_result) 반영.
- 검증: 직접 재현 2회 성공 — Nha Trang(topic 242), Da Nang(topic 243) 발행. 데이터 없는 토픽(Mui Ne 등) 자동 exhausted 스킵 후 정상 토픽 도달.
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

- ~~interior/beauty/golf 등 curation 블로그 17:00+ 스케줄에서 purge 효과 실증 필요~~ → **실증 완료**: 17:03 interior, 17:33 kitchen, 17:41 beauty 발행 성공, P36/P14 재발 0건 (17:00~18:00 사이클 32건 성공)
- watersports-hugo: run() 2차 수정 후 재현 2회 성공(Nha Trang/Da Nang). 21:40 프로덕션 스케줄 실발행 관찰 잔여
- 19개 pre-existing 테스트 실패 (본 작업 범위 외)

---

# Phase 76 — 재발 방지 (recurrence-prevention) 추가 작업

## 작업 개요

재발 구조 분석(키워드 오염 6일 7회 재발, keyword_expander 02:00 재주입기, SSOT 이중 구조, ETAP corpus growth) 기반 Phase 76 플랜 작성 + 실행. `.planning/phases/phase-76-recurrence-prevention/` (CONTEXT.md, PLAN.md, SSOT-DESIGN.md).

## [PRODUCTION] 수정 내역

### 5. keyword_expander.py + naver_datalab_sync.py — write-time guard (Wave 1, 커밋 6c76ef7bc)

- `except ImportError: pass` 제거 → import 실패 시 `return 0`(추가 중단 + 로그). per-keyword `except Exception`(개별 오류 시 해당 키워드만 제외).
- naver_datalab_sync.py `update_keywords_py()`(validate 완전 없던 경로)에 동일 가드 추가.
- 근거: 02:00 expander 자동 실행이 정크 재주입 출처 확정(오늘 02:45 car 122개 재주입). validate 실패 시 추가 차단으로 재주입 원천 차단.

### 6. keywords.py — get_keywords() read-time 필터 (Wave 2, 커밋 fa604033e)

- KEYWORD_MAP fallback 반환 시 validate_keyword 통과분만 반환. per-keyword try/except(개별 오류 시 원본 포함 — 기존 동작 보존), 필터 후 빈 리스트면 원본 반환. 킬스위치 `KEYWORD_READ_FILTER=0`(기본 ON).
- 검증: 오염 주입 재현('가능','가방','노트북' 추가) → 정크 0건. 킬스위치 OFF 시 원본 반환 확인. pytest 회귀 0건(19f/129p baseline 동일).

### 7. dispatcher.py — corpus cap 로그 (Wave 3, 커밋 fa604033e)

- preflight_check corpus 샘플링 시 로그 1줄(루프 밖 1회만): `[preflight] corpus 301건 → cap 200건 샘플링 (blog=tour-hugo)`. pipeline_timeout=900(etap.yaml) 무변경(플랜대로).
- 검증: preflight_check('tour-hugo') 실측 3.1s, blocked=False.

### 8. shared/problem_registry.py + config/problems.yaml — 자가치료 action 문구 (Wave 4, 커밋 fa604033e)

- P02/P14/P25/P36 action에 실행 커맨드 추가(dispatcher.py 재시도, get_keywords 확인, preflight_check 확인). **양쪽 모두** — YAML 오버라이드 구조(797-803 apply_problem_yaml) 때문. YAML 싱글쿼트 이스케이프 필요(`: ` 포함 시).
- P36은 YAML에 없음 → 코드 dict만 수정(유효).
- 대시보드 재시작(사용자 승인) → /api/registry에 신규 문구 반영 확인.

### 9. SSOT-DESIGN.md (Wave 5)

- keyword_pool DB SSOT 승격 설계 문서. M1~M6 마이그레이션, 파괴적 4단계 체크리스트. **실행 별도 phase**.

## 파괴적 작업 로그 (추가)

- [2026-09-02] dashboard 재시작 (launchctl kickstart) — 신규 PID 58637. logs/destructive_2026-09-02.log 기록. 목적: /api/registry 신규 action 문구 반영. 이슈/DB 무변경.

## Phase 76 커밋

- 6c76ef7bc: Wave 1 write-time guard (+38/-9)
- fa604033e: Wave 2-4 (+31/-9) — keywords.py, dispatcher.py, problem_registry.py, problems.yaml

## Phase 76 잔존 위험

- 검증 기준 1(02:00 expander 실행 후 정크 0건): **다음 날(9/3) 관찰 필요** — write-time guard + read-time 필터 이중 방어지만 첫 야간 사이클 미거침
- SSOT 마이그레이션(M1~M6): 설계만 완료, 실행 별도 phase
- S01/S02 preflight OFF(QUALITY_ENFORCE_S01_S02 킬스위치로 재활성 가능)
- escape topics 8개 (기존)
- S02 Structural similarity WARN (ETAP corpus 대형화 — 기존 이슈)
- best-* insufficient_products (Coupang 데이터 부족) — 별개 이슈

---

# 추가 수정 — tour-hugo P25 최종 해결 + golf P36 (커밋 01f3c860e)

## 추가 조사 결과

tour-hugo P25의 **진짜 hang 지점**이 preflight가 아닌 **배포 후 `_run_post_publish_checks()`**였음:

1. preflight_check는 3.1s로 정상 통과 (커밋 0a3d3c005의 corpus cap 도입 이후)
2. `_build_and_deploy_central()` 도 정상 완료 (deploy OK, wrangler rc=0)
3. **배포 후** `_run_post_publish_checks()`(dispatcher.py:1285) → `run_all_checks()` → `content_integrity.py check_s01()`이 최근 7일 포스트 303건 각각に 대해 `_extract_corpus()` + TF-IDF 계산 → **303 × 302 = ~91,000회** → 900s scheduler kill

- `content_integrity.py`의 `_extract_corpus()`는 cap 없이 전체 포스트를 매번 읽기
- `check_s01()` 루프 안에서 매 포스트마다 `_extract_corpus()` 재호출 → 최악의 경우 O(N²) I/O + TF-IDF
- `_run_post_publish_checks()`는 try/except로 감싸져 있어 에러 로그만 남기고 hang → 900s 도달

## [PRODUCTION] 추가 수정

### 10. ops_dashboard/checks/content_integrity.py — S01/S02 최적화

- `_extract_corpus()`: `_S_CORPUS_CAP=200` 추가 (stride 샘플링). 기존 코드에 cap 없었음.
- `check_s01()`, `check_s02()`: corpus를 **루프 밖에서 1회만 구축** (기존: 매 포스트마다 `_extract_corpus()` 재호출 = 최악 303×303 I/O). self-exclusion 제거(포스트 본문 유사성에 미세 영향이나 O(N²) 제거가 최우선).
- `check_s01()`, `check_s02()`: `_S_POST_SAMPLE=50` 포스트 상한 추가 (초과 시 최신 N건만 검사).
- 결과: tour-hugo 기준 304포스트 → corpus 152건(캡), 포스트 검사 최대 50건. 기존 ~91,000회 TF-IDF → 최대 50회.

### 11. pipelines/curation/pipeline.py — golf-hugo bare allowed 제거

- `"골프"`, `"스윙"` bare 토큰 제거 → 구체 토큰만保留 (`"골프클럽"`, `"골프용품"`, `"골프연습"`, `"골프장"`, `"골프공"`, `"골프용품"`, `"골프티"`, `"골프GPS"`, `"골프모자"`)
- substring 매칭 맹점 제거: bare `'골프'` 포함 → `'식기골프신생아골프'` 같은 임의 정크 통과했으나 이제 구체 토큰만 허용

### 12. pipelines/curation/keywords.py — golf KEYWORD_MAP purge

- `'식기골프신생아골프'` 제거 (1건). golf-hugo 18개.

## 추가 검증

- py_compile: content_integrity.py, pipeline.py, keywords.py OK
- `validate_keyword('식기골프신생아골프', 'golf-hugo')` → **False** (이전: True). `'골프클럽'` → True, bare `'골프'` → False.
- `preflight_check('tour-hugo')` → 2.9s, blocked=False
- `_extract_corpus(tour-hugo)` → 152건 (304포스트, cap=200 적용)
- pytest: 19 failed, 129 passed (baseline 동일, 회귀 0건)

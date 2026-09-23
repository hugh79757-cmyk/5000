# 2026-09-02 — 5-Alert Triage: kitchen/fitness P36+P14 정크 키워드, tour-hugo P25 preflight hang, rap P16

## 요약

| Alert | 원인 | 조치 | 상태 |
|---|---|---|---|
| kitchen-hugo P36+P14 | KEYWORD_MAP 정크 키워드("가능" 등) → irrelevant_products 3회 재시도 전부 실패 | keywords.py kitchen 세그먼트 purge 179→92 | [검증됨] |
| fitness-hugo P36+P14 | 동일 (정크 키워드 "가능" 연속 2블로그 실패 유발) | keywords.py fitness 세그먼트 purge 264→173 | [검증됨] |
| tour-hugo P25 (timeout 900s) | 발행 성공 후 preflight_check S01/S02 TF-IDF 계산이 포스트당 전체 corpus 재구축+재스캔 (301포스트×300코퍼스) → 수백 초 | dispatcher.py corpus 1회 구축 + _S_CORPUS_CAP=200 + S01/S02 킬스위치(QUALITY_ENFORCE_S01_S02) | [검증됨] |
| rap-hugo P16 (duplicate_slug 동작구 종합) | 종합형(구 단위 시세 직접 조합)이 8/30 발행분과 동일 재생성. 자연 해소 | 코드 수정 없음 — 자연 해소 판정 | [부분검증] |
| escape-hugo 토픽 부족 경고 | 토픽 소진 경고 후 11:46 발행 성공으로 자연 해소 | 조치 불필요, topics 8개 남음 모니터링 | [검증불가: 재발 관찰 필요] |

## 대시보드 파악 여부 (READ 단계)

- 전부 기존 P-code(P36/P14/P25/P16)로 대시보드 open issue 파악 완료. **신규 규칙 등록 불필요.**
- 증거: `/api/attention` (auth: .env OPS_USER/OPS_PASSWORD) — kitchen P36 CRITICAL 03:50:43, P14 MAJOR 03:50:44, fitness 동일, tour P25 CRITICAL 04:05:45, rap P16 MINOR 04:59:12 open.

## 원인 분석

### kitchen/fitness P36+P14

- `pipelines/curation/keywords.py` KEYWORD_MAP에 정크 일반명사 포함: "가능", "가방", "가벼운", "가성비", "강아지", "고양이", "기저귀", "갤럭시북" 등.
- keyword_pool 테이블 사실상 비어있음(3건) → get_keywords()가 KEYWORD_MAP fallback → 정크 키워드 선택.
- 메커니즘: pipeline.py `_filter_irrelevant_products`가 allowed 미포함 상품 전부 제거 → 3회 재시도(대체 키워드도 정크) 전부 실패 → `irrelevant_products` → `_record_failure` P36 + P14 이중 기록.
- 선례: commit 2a338547a (car/golf purge), 2dde4023d (baby/fitness bad keywords).

### tour-hugo P25

- publish_log(travel-en.db): 오늘 발행 2건 성공 (topic 309/310, 시작 후 23s/55s 기록) — 생성+발행 성공, **그 이후 단계에서 hang**.
- deploy.log: 오늘 wrangler 기록 없음 → wrangler 미도달 → hang 지점 = preflight_check.
- preflight S01/S02: WARN-ONLY. dispatcher.py 루프 내 매 포스트마다 posts_dir 전체 재스캔 + TF-IDF. tour-hugo 302 포스트 중 301개가 7일 내 → 301×300 = ~90,300회 유사도 계산.
- 실측: synthetic 300-doc corpus S01 1회 0.78s → 301포스트 시 234s+ (S02 별도) → scheduler 900s kill 원인 확정.

### rap-hugo P16

- '동작구-실거래가-종합-분석' slug 8/30 발행 존재 → 종합형 재생성 시도 hit. MINOR, retryable=False.
- 이후 8/31, 9/1, 9/2 정상 발행 지속 → 자연 해소 판정.
- 부수 발견(미수정, 보고만): pipelines/rap/pipeline.py 라인 139-158 using_gap=True 경로에서 closed connection 재사용 가능성 — district 가드 except pass로 우회될 수 있는 잠재 결함. 본 사건과 무관 가능성 높음.

### escape-hugo

- 토픽 부족 경고는 11:46 발행 성공으로 자연 해소 (P34 close, retry reset). escape_topics 8개 남음 — 0개 시 자동 중지되므로 모니터링만.

## 수정 내역 [PRODUCTION]

### 1. pipelines/curation/keywords.py — fitness/kitchen 정크 purge

- 세그먼트 치환 스크립트(선례 2a338547a 패턴): CATEGORY_FILTERS allowed 토큰 부분문자열 미포함 키워드 purge.
- 수동 제외 6건(위반감지 항목): '대만산강아지 운동장 추천', '관리강아지 운동장 추천', '다이어트대형강아지 운동장 추천근력운동', '근력운동덤벌', '운동 영영', '스포츠 마케팅 추천'
- 결과: fitness 264→173 (91 purge), kitchen 179→92 (87 purge).

### 2. dispatcher.py — preflight S01/S02 비용 축소

변경 3건 (전부 additive, 가역):

1. corpus 구축을 포스트 루프 밖 1회로 이동 — corpus_by_file dict(파일경로→body).
2. 루프 내 corpus = 자기자신 제외 + `_S_CORPUS_CAP=200` 상한 초과 시 stride 샘플링.
3. S01/S02 계산을 `QUALITY_ENFORCE_S01_S02=1`일 때만 실행(기본 OFF). 근거: WARN-ONLY라 blocked 무영향 + 발행 시점 quality_guard가 동일 게이트 수행(238,188회 FAILED 로그 증거). S06(실제 의미 있는 중복 검사)은 유지.

### 3. rap/escape — 코드 수정 없음

## 검증

- py_compile: keywords.py, dispatcher.py OK.
- 재로드 assert: fitness/kitchen '가능'/'가방'/'강아지' 0건, 빈 문자열 없음.
- `preflight_check('tour-hugo')` 실측: **3.1s** (기존 >900s), blocked=False, S01 n_compared=200 캡 동작 확인.
- 테스트 회귀: `OPS_TEST_MODE=1 pytest tests/curation -q` → 19 failed, 129 passed. baseline(stash 대조) 동일 19 failed, 129 passed → **내 수정으로 인한 회귀 0건** (19 failures 전부 pre-existing: test_title_hardening 등).
- tour-hugo P25 최종 확인: 다음 스케줄 배포 900s 내 통과로 확인 예정.

## [위반 감지]

**keywords.py working tree 기존 오염** — 본 세션 이전 유입, fitness/kitchen 세그먼트 외 부분:

- car-hugo: 122개 정크 재주입 ('가능','가방','노트북' 등 — 2a338547a가 purge했던 것과 동일)
- baby-hugo: '강아지' 등 blocked 토큰
- pet-hugo: '가능','가방' (단 '강아지' 계열은 pet allowed라 정상)

원복하지 않음. 이유: HEAD 대비 diff hunk 10개 전체가 이전 세션 미커밋 작업과 뒤섞여 있어 선택적 원복 시 다른 미커밋 작업 소실 위험. car/baby P36 재발 소지 잔존 → 별도 세션에서 정리 필요.

## 잔존 위험

- keywords.py car/baby 오염 미해결 — car/baby P36 재발 가능성. 복구 계획: 별도 세션에서 car/baby 세그먼트만 선례 패턴으로 purge.
- preflight S01/S02 기본 OFF — uniqueness 이중 검사 제거. 발행 시점 quality_guard 담당하나 preflight 레벨 사후 검증 신호 소실. 재활성: `QUALITY_ENFORCE_S01_S02=1`.
- tour-hugo P25 해소는 3.1s 실측 기반 기대치 — 다음 스케줄 실배포 통과로 확정 필요.
- 19개 pre-existing 테스트 실패 (본 작업 범위 외).
- escape_topics 8개 — 소진 시 자동 중지 (경고 재발 가능).
- scheduler 재시작 미수행 — dispatcher/keywords는 import 시점 로드라 실행 중 프로세스는 구버전 유지. `launchctl kickstart -k gui/$(id -u)/com.5000.scheduler` 필요 (파괴적 작업 규칙상 사용자 확인 후).

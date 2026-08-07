# Plan 61-02 Summary — 공용 기반 구축 (Stage B)

**Phase:** 61-pipeline-standardization-branch-renewal
**Plan:** 61-02 (Wave 2, Stage B)
**Date:** 2026-08-07
**Executed by:** opencode (Plan 61-02 autonomous)
**Dependencies:** 61-01 (PIPELINE-STANDARD.md) — 적용됨

---

## Objective

분기 표준화가 의존할 **shared 모듈 4개**를 추가한다. 전부 순수 추가(additive):
신규 모듈 생성(`shared/db.py`, `shared/subprocess_runner.py`) + 기존 모듈 확장
(`config_validator.py`, `problem_registry.py`). 데이터 이동 없음(D-06), 구조/동작 분리 커밋(D-08).

---

## 파일 생성/확장 (Deliverable 1)

| 파일 | 상태 | 내용 |
|------|------|------|
| `shared/db.py` | **생성 (NEW)** | `get_db_path(branch)` + `get_connection(path)` 중앙 헬퍼. `shared/db_paths.py`를 replace하지 않고 재사용. |
| `shared/subprocess_runner.py` | **생성 (NEW)** | `run_subprocess()` — STAP/TAP 외부 subprocess 격리 실행기. inspect 브리지, timeout, `CLOUDFLARE_API_TOKEN` pop, module_spec 검증. |
| `shared/config_validator.py` | **확장** | `STANDARD_BLOG_FIELDS`, `EXTENSION_BLOG_FIELDS`, `KNOWN_EXTRA_KEYS`, `validate_blog_entry_standard()`, `validate_managed_mode()`, `validate_standard_blog_defs()` 추가 + `validate_configs()`에 `standard` 키(non-blocking) 배선. |
| `shared/problem_registry.py` | **확장** | 미등록 reason 10개를 기존 spec의 `reason_keys`에 병합 (additive, 기존 키 유지). |
| `tests/shared/test_db.py` | **생성 (NEW)** | 9 tests — D-06 (경로/연결, 데이터 무이동, travel 미매핑). |
| `tests/shared/test_subprocess_runner.py` | **생성 (NEW)** | 8 tests — D-03 (dict/브리지/timeout/no_output/nonzero/token). |
| `tests/shared/test_config_schema.py` | **생성 (NEW)** | 8 tests — D-04 (필수/표준/확장/managed_by). |
| `tests/shared/test_problem_registry.py` | **확장** | 4 tests — 10개 reason 인식, `language_error`=P12 유지, 기존 24개 매핑 불변. |

---

## 수정된 reason-key 집합 (Deliverable 2 — 실제 추가된 것)

Review #5 반영: **`language_error`는 이미 P12 등록 → 추가하지 않음.** 계획상 "11개"는 실제로 **10개**(진짜 미등록)로 정정. 추가한 10개 + 매핑:

| reason | 매핑된 P-code | 실측 위치 (PIPELINE-STANDARD §5.2) |
|--------|--------------|------------------------------------|
| `daily_quota_reached` | **P17** (할당량) | pipelines/etap/pipeline.py |
| `expired_service` | **P19** (만료 데이터) | pipelines/senior/pipeline.py |
| `generation_failed` | **P02** (생성 실패) | pipelines/{car,curation} |
| `no_subscription_data` | **P01** (데이터 부족) | pipelines/rap/pipeline.py |
| `no_topic` | **P01** (데이터 부족) | pipelines/{car,etap} |
| `no_topics` | **P01** (데이터 부족, 방어적) | (실측 없음) |
| `no_trade_data` | **P01** (데이터 부족) | pipelines/rap/pipeline.py |
| `prompt_not_found` | **P02** (생성/프롬프트) | pipelines/car/pipeline.py |
| `publish_failed` | **P02** (발행 실패) | pipelines/rap/pipeline.py |
| `write_failed` | **P02** (작성 실패) | pipelines/rap/pipeline.py |

`language_error` → **P12 유지** (재추가 안 함). 전부 `unknown_failure`로 빠지지 않음을 확인.

---

## travel DB 처리 결정 (Deliverable 3)

- **`get_db_path('travel')`는 매핑하지 않는다.** Review #3/#4 + PIPELINE-STANDARD §6.4 근거.
- 실측 확인: `pipelines/travel/pipeline.py`·`fetcher.py`는 `PUBLISH_LEDGER_DB`(data/content.db) +
  `ARTICLES_DB`(data/stap_content.db) + `FESTIVAL_DB`를 사용하며 **travel-en.db를 사용하지 않음**.
- `shared/db.py`에서 travel을 전용 DB 매핑에서 제외하고 `get_db_path('travel')`는 `ValueError`를 던져
  잘못된 배선을 방지. docstring에 stale `db_paths.TRAVEL_DB = travel.db`(실제 파일 travel-en.db)와의
  충돌 방지를 명시.
- `shared/db.py`는 car/rap/senior/curation/stock만 매핑 (전용 DB 파일 보유 분기). travel/etap은 제외.

---

## 테스트 수치 (Deliverable 4)

### 기준선 (구현 전)
`python3 -m pytest -o addopts="" -q` → **21 failed, 317 passed, 1 skipped**

### 구현 후
`python3 -m pytest -o addopts="" -q` → **21 failed, 346 passed, 1 skipped**

**신규 실패 0건.** 실패 21건 = 기준선 21건과 diff로 정확히 동일 집합 확인(아래 [검증됨]).

**passed 증가:** 317 → 346 = **+29** (내역 분해):
- test_db.py: 9
- test_subprocess_runner.py: 8
- test_config_schema.py: 8
- test_problem_registry.py (Phase 61 신규): 4
- 합계 = 9+8+8+4 = **29** ✓ (합 일치)

### 신규 파일 TDD (RED→GREEN)
- 구현 전: 3 collection error (모듈 부재) → RED 확인.
- 구현 후: test_db 9 + test_config_schema 8 = 17 passed.
- subprocess_runner 8 + problem_registry(전체) 17 = 25 passed.

---

## 커밋 해시 (Deliverable 5 — D-08 구조/동작 분리)

| 커밋 | 해시 | 내용 | 유형 |
|------|------|------|------|
| A | `022bbc2a1` | feat(phase-61): add shared/db.py and extend config_validator with unified schema | 구조 추가 |
| B | `da066e3fe` | feat(phase-61): add shared/subprocess_runner.py (subprocess isolation runner) | 구조 추가 |
| C | `46f1344c5` | feat(phase-61): extend problem_registry with unregistered reason keys | 동작 확장 |

구조(모듈 생성/스키마)와 동작(reason 매핑)을 별도 커밋으로 분리. 커밋 A·B는 구조 추가,
커밋 C는 reason-key 동작 확장으로 분리됨 (D-08).

---

## Review 보정 적용 확인 (Deliverable 6)

| Review 항목 | 적용 여부 | 근거 |
|------------|-----------|------|
| #1 travel DB path (get_db_path('travel')→travel-en.db 배선 금지) | **[적용]** | `shared/db.py`가 travel을 매핑에서 제외, `get_db_path('travel')`→ValueError. 테스트 `TestTravelNotMapped`로 고정. |
| #3 travel 실 DB 의존성 기록 | **[적용]** | docstring + SUMMARY에 content.db/stap_content.db/festival.db 사용 명시. |
| #4 db_paths TRAVEL_DB stale — 제3의 travel 경로 추가 금지 | **[적용]** | shared/db.py에 travel 전용 경로 추가 안 함. |
| #5 `language_error` 이미 P12 — 재추가 금지 | **[적용]** | 미등록 목록 11→**10**으로 정정. `language_error`는 P12 유지 (테스트로 고정). |
| subprocess dedup "~400줄" → ~124줄로 right-size | **[적용]** | subprocess_runner.py docstring에 "~124줄 중복"으로 명시 (~400 아님). |
| AdSense Publisher ID (8772/6677/5938) | **[무관/미접촉]** | 이 계획은 광고 파일을 건드리지 않음. 위반 없음. |
| 배포는 dispatcher.py 경유 | **[무관/미접촉]** | 배포 없음 (code-only). 수동 wrangler 미실행. |

---

## 검증 상태 (3분법)

- **[검증됨]** 신규 실패 0건: 구현 전/후 `pytest -o addopts="" -q` 실행 후, 실패 21건 집합을 `diff`로
  비교 → 기준선 21건과 **정확히 동일** (신규 실패 0).
- **[검증됨]** passed +29: 317→346 (분해 내역 상기, 합 일치).
- **[검증됨]** 10개 reason 모두 concrete P-code 매핑: `lookup_reason()` 직접 호출로 확인.
- **[검증됨]** `language_error`=P12 유지, 미재추가.
- **[검증됨]** `data/*.db` 무이동: `git status --porcelain`에 tracked `data/*.db` 변경 0건.
  (보이는 `data/content.db.*` 3건은 사전부터 존재하던 **untracked 복구 백업** — 내 작업과 무관, none ends in `.db`.)
- **[검증됨]** 신규 테스트 29건 전부 GREEN, `test_dispatcher_registry.py` 전부 PASS.
- **[검증됨]** 커밋 3개 존재 (`git log --oneline -3`에 phase-61 커밋 확인).
- **[부분검증]** subprocess_runner의 `CLOUDFLARE_API_TOKEN` strip — 단위 테스트로 env에서 제거됨을 확인.
  (실제 wrangler 호출 경로는 후속 Plan 61-08에서 소비 — 이 계획에선 runner만 제공.)
- **[검증불가]** 없음.

---

## 잔존 위험

1. **`get_db_path` 미지원 분기 (travel/etap)**: travel은 의도적 제외. etap은 전용 단일 DB가
   확인되지 않아 이 계획에서 매핑하지 않음 → Plan 61-07(ETAP 단일화)에서 결정 필요. 호출 시
   `ValueError`로 명확히 표면화되므로 조용한 실패 없음.
2. **subprocess_runner 실제 라우팅 미검증**: 모듈은 단위 테스트로 검증됨. dispatcher의
   `_run_stap`/`_run_tap_subprocess`를 이 runner로 교체하는 것은 Plan 61-08 범위 — 아직
   교체 안 함 (기존 발행 경로 무중단 유지).
3. **`config_validator` standard 보고서**: non-blocking이라 기존 발행을 막지 않지만,
   실제 blogs.d 파일 기준으로 unknown-key warning이 일부 발생할 수 있음 (후속 분기 전환 시 정리).
4. **잔존 위험: 없음** (구조적 데이터 변경, DB mutation, 배포, 광고 매핑 변경 전혀 없음).

---

## Output

본 SUMMARY 작성 완료. Wave 2 (Stage B) 완료 — shared base가 pilot(61-03) 및 rollout(61-04..07) 소비 대기.

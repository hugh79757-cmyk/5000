---
phase: 61-pipeline-standardization-branch-renewal
plan: 01
status: complete
completed_at: "2026-08-07"
commit: 6f9930875
---

# Plan 61-01 Summary — 표준 정의 (docs/PIPELINE-STANDARD.md)

## Deliverables

- **표준 파일 생성:** `docs/PIPELINE-STANDARD.md` (308줄, 7개 Section 전부 완비)
  - Section 1 — 목적 및 경계
  - Section 2 — 표준 모듈 골격 (6-모듈 + additive wrapper 규칙, 분기별 매핑, stock 계약만 스코프)
  - Section 3 — 실행 계약 `run(cfg) -> dict` (반환 정규화, ETAP 혼합 계약, flight 예외 처리)
  - Section 4 — 통합 config 스키마 (필수/표준/선택 필드)
  - Section 5 — 표준 reason-key 어휘 (미등록 10개 + P-code 매핑)
  - Section 6 — DB 접근 규칙 (path 중앙화, 데이터 이동 금지, travel 실제 의존성)
  - Section 7 — 배포 및 보존 규칙 (dispatcher 경유, AdSense ID 불변, 분리 커밋)

## 테스트 기준선

- `pytest -o addopts="" tests/test_dispatcher_registry.py -x` → **1 passed** (37 warnings)
- 기준선 green. 본 플랜에서 소스 코드 0 변경 (markdown 문서만 추가).

## 전체 스위트

- `pytest -o addopts="" -q` → **21 failed / 317 passed / 1 skipped**
- **전체 스위트 green 미달.** 단, 실패 21건 전부는 본 플랜이 원인이 **아님**:
  - 본 커밋은 `docs/PIPELINE-STANDARD.md` 단일 파일만 추가 (Python 소스 터치 0).
  - 실패는 curation/shared 테스트이며, 세션 시작 전부터 존재하던 dirty 워킹 트리
    (`pipelines/curation/pipeline.py` 수정본, `data/content.db.EVIDENCE_*` 등)에 기인.
  - 검증: `git show --stat HEAD` → docs 파일 1건만 변경. 실패 21건 목록은
    `tests/curation/test_alert_thresholds.py`, `test_cot_threshold_validation.py`,
    `test_defense_layers_independent.py`, `test_filters_allblogs.py`, `test_keywords.py`,
    `test_pipeline.py`, `test_title_hardening.py`, `test_title_regression.py`,
    `tests/shared/test_ai_writer.py`, `test_post_validator.py`, `test_relevance_scorer.py`.
  - **후속 플랜(61-02+)에서 이 21건의 pre-existing 실패를 해결하지 않으면 Phase 게이트
    "전체 스위트 green" 미충족.** 본 플랜에서 손대지 않음 (비파괴 원칙).

## 커밋

- 해시: `6f9930875`
- 메시지: `docs(phase-61): add PIPELINE-STANDARD.md (canonical pipeline/config/run-contract standard)`
- 변경: `docs/PIPELINE-STANDARD.md` 1건만 (308 insertions). 소스 코드 0 변경.
- pre-existing dirty 파일(`.continue-here.md`, `pipelines/curation/pipeline.py`,
  `data/` 비추적 파일)은 커밋에서 제외.

## Review 교정 반영 (3건)

1. **[Review #5] `language_error` 제외:** shared/problem_registry.py:272 (P12) 등록 확인.
   미등록 "11개" 목록에서 제외 → **진짜 미등록 10개**로 조정.
   그중 9개(`daily_quota_reached`, `expired_service`, `generation_failed`,
   `no_subscription_data`, `no_topic`, `no_trade_data`, `prompt_not_found`,
   `publish_failed`, `write_failed`)는 워킹 트리 실측 발행, `no_topics`는 방어적 추가.
   `grep "language_error.*미등록"` = 0건으로 제외 확인.
2. **[Review #2] flight `{"status": ...}` 처리:** pipelines/etap/flight_pipeline.py 확인 —
   `run(cfg)`가 `success` 키 없는 `{"status": "skip|error|draft|ok"}` 반환.
   표준 Section 3.5에 **success/reason으로 정규화**를 명시 결정 (예외 처리하지 않음).
3. **[Review #3] travel DB 정확 기록:** pipelines/travel/{pipeline,fetcher}.py 확인 —
   `travel-en.db` 사용 안 함. `PUBLISH_LEDGER_DB`(data/content.db) + `ARTICLES_DB`
   (data/stap_content.db) + `FESTIVAL_DB` 사용. Section 6에 기록, 후속 플랜(61-02/61-05)
   미배선 경고 + `db_paths.py:19 TRAVEL_DB` stale(Review #4)도 명시.

## 잔존 위험

- **없음 (본 플랜 범위):** 문서-only, 소스 0 변경, baseline green.
  표준은 규범적 문서로 이후 전환 플랜이 코드로 검증해야 함 (Review T-61-01).
- **상속 위험 (본 플랜 소관 아님):** (a) full-suite pre-existing 실패 21건 —
  Phase 게이트 미달 소지, 후속 플랜에서 해결 필요. (b) 미등록 reason 10개는
  Plan 61-02에서 registry 반영해야 `unknown_failure` 소실 방지.

## 보고 분류

- [검증됨] 문서 생성, 기준선 1 passed, 커밋 hash, Review 3건 소스 검증 반영.
- [검증불가] 전체 스위트 green — 21 failed (pre-existing dirty 워킹 트리 원인, 본 커밋 무관).
  복구 계획: 후속 플랜에서 pre-existing 실패 해결 후 전체 스위트 재실행.

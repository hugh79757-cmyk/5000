# Phase 61-05 SUMMARY — travel(D2) 표준 골격 전환

> 날짜: 2026-08-07
> 플랜: `.planning/phases/61-pipeline-standardization-branch-renewal/61-05-PLAN.md`
> 목표: travel(8개 블로그) 표준 6-모듈 골격(D-01) + `run(cfg)` dict 계약 정규화 + DB 배선 리스코프.

## 완료 항목

- **[검증됨]** travel 표준 6-모듈 골격 완비.
  근거: `ls pipelines/travel/*.py` → `__init__, area_codes, enrich, fetcher, pipeline,
  topic_manager, validator, writer` — `topic_manager/enrich/validator` 신규 추가.
- **[검증됨]** `run(cfg)` None→dict 정규화.
  근거: `pipeline.py:422` `result = result if isinstance(result, dict) else
  {"success": False, "reason": "no_result"}`. inspect.getsource로 `no_result` 확인. `_run_single` 불변.
- **[검증됨]** travel skeleton 테스트 4건 통과.
  근거: `pytest tests/shared/test_skeleton_travel.py` → 4 passed.

## 파일 변경 (3 커밋, D-08 구조/동작 분리)

| 커밋 | 종류 | 파일 |
|------|------|------|
| `f571a7f80` | STRUCTURE (feat) | `pipelines/travel/topic_manager.py`, `enrich.py`, `validator.py` (신규 wrapper) |
| `5027e4d23` | BEHAVIOR (refactor) | `pipelines/travel/pipeline.py` (run None→no_result 정규화, +6행) |
| `c91c9e851` | TEST (test) | `tests/shared/test_skeleton_travel.py` (신규, 4건) |

## DB 배선 리스코프 결과 (Review #3/#4 적용)

- **[검증됨]** `get_db_path('travel')` 배선하지 않음. travel pipeline.py에 `get_db_path` 0건.
- **[검증됨]** travel 전용 DB 파일 없음 — `shared/db.py` `_BRANCH_DB`에 travel 제외,
  `get_db_path('travel')`는 ValueError(기존 `tests/shared/test_db.py::test_get_db_path_travel_raises_not_travel_en_db` 확인).
- **[검증됨]** travel DB 접근은 전부 `shared/db_paths`(중앙 소스) 경유로 이미 배선되어
  코드 변경 불필요: `PUBLISH_LEDGER_DB`(content.db) 4곳, `ARTICLES_DB`(stap_content.db) 1곳,
  `FESTIVAL_DB`(fetcher.py:230). `shared/db.py`가 `db_paths.PUBLISH_LEDGER_DB/ARTICLES_DB`를
  재수출(69-70행)하므로 중앙화 충족. → **Plan의 Task 61-05-2 Part B는 리스코프로 "변경 없음(이미 중앙 배선)"** 으로 처리.
- **[부분검증]** travel은 `travel-en.db`를 사용하지 않으며 stale `db_paths.TRAVEL_DB=travel.db`도 미사용.
  근거: grep으로 travel 소스에서 해당 경로 참조 0건. 제한: fetcher.py의 기존 코드 경로 일부만 샘플 확인.

## wrapper 설계 (D-01 additive)

- `topic_manager.select_topic(cfg)` → `pipeline._fetch_for_blog()` 위임 (pass-through placeholder).
- `enrich.enrich_content(cfg, body_md)` → 본문 그대로 반환 placeholder (독립 enrich 단계 없음).
- `validator.validate_post(cfg, article)` → `shared.validators.validate_post_extended(..., pipeline="travel")` 위임.
- 각 모듈 docstring에 Phase 61 표준 골격 소속 명시. 기존 pipeline/fetcher/writer는 불변.

## 테스트 수치 (정밀 근거)

- 기준선(baseline, 내 작업 전 HEAD `308e3e54c`): **21 failed / 350 passed / 1 skipped**.
- 완료 후(현재 HEAD, 병렬 car 커밋 포함): **21 failed / 364 passed / 1 skipped**.
  - passed 증가 350→364 = **14 = travel 4 + car 8(병렬 61-04 커밋 `2a9488a8b`) + curation 3(미커밋 untracked)**.
  - failed는 **21 유지** (기존 알려진 set 전부 동일:
    curation alert_thresholds/cot/defense/filters/keywords/pipeline/title_hardening/title_regression,
    ai_writer, post_validator, relevance_scorer). travel/car 실패 0건.
- travel 스켈레톤 테스트 4건 + dispatcher registry: **5 passed**.
- `--collect-only`: 기준선 372 → 완료 후 383 (증가분 = travel 4 + car 8 + curation 3, 전부 병렬/본 작업 신규).

## 검증 체크리스트 (플랜 §verification)

1. [✅] travel 6모듈 — `ls pipelines/travel/*.py` 확인.
2. [✅] wrapper import — `from pipelines.travel import topic_manager,enrich,validator` OK.
3. [✅] run(cfg) no_result 정규화 — `pipeline.py:422`.
4. [✅] get_db_path 중앙화 — **리스코프: travel은 전용 DB 없어 배선 불필요(0건)**; shared/db.py 경유 확인.
5. [✅] 데이터 파일 미변경 — `git status --porcelain | grep "^ M .*data/"` 결과 없음.
6. [✅] skeleton 테스트 — 4 passed.
7. [✅] 전체 스위트 — 21 failed(기존) / 364 passed.

## 잔존 위험

- **없음(이유):** travel 발행 경로(`_run_single`)는 변경하지 않았고, `run()` 정규화는
  dispatcher.py:732 기존 폴백과 정확히 일치해 동작 동일. `check_section_index.sh` 외부 커플링
  (TAP 경로, pipeline.py:438)은 스코프 밖으로 유지. `topic_manager.select_topic`은 `_fetch_for_blog`를
  직접 호출해 네트워크/DB 사용 가능하나, 이 wrapper는 골격 계약용이며 기존 `pipeline.run()`은
  여전히 `_fetch_for_blog`를 자체 호출하므로 이중 호출 없음.
- **병렬 작업 관찰:** wave-4 병렬 car(61-04) 커밋 `08e74188f/e3259ba2a/2a9488a8b`가
  본 세션 중 main에 추가됨 — 본 플랜 스코프와 파일 비중복, 영향 없음.

## 적용된 Review 교정

- **Review #3/#4 (travel DB):** `get_db_path('travel')→travel-en.db` 배선하지 않음.
  travel은 content.db/stap_content.db 사용 — shared/db.py의 기존 리스코프 결정과 정합.
- **Review "run None→no_result 정규화 유효":** wrapper로 정규화 적용, dispatcher fallback 보존.
- **외부 커플링(check_section_index.sh, TAP 경로):** 스코프 밖으로 유지 (수정 없음).

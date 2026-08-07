---
phase: 61-pipeline-standardization-branch-renewal
plan: 0
subsystem: all-branches
tags: [standardization, branch-renewal, run-contract, scaffolding]
requires: []
provides: [pipeline-standard, shared-db, subprocess-runner, scaffold-branch]
affects: [dispatcher.py, shared/, pipelines/, config/blogs.d/]
decisions:
  - "7개 분기(car/curation/etap/rap/senior/travel/stock)를 표준 골격 + run(cfg)->dict 계약으로 재편 (D-01..D-08)"
  - "구조 변경과 동작 변경은 분리 커밋 (D-08)"
  - "shared/db.py + shared/subprocess_runner.py 신규 (D-06, D-03), config_validator 확장 (D-04), problem_registry reason-key 보강"
  - ".bak 파일 실제 삭제는 범위 밖 — 보고서만, 별도 승인 필요 (파괴적 작업 규칙)"
  - "ETAP inspect.signature 브리지 + _ETAP_BLOG_EXCEPTIONS 유지 (D-08, 최고 위험)"
tech-stack:
  added: []
  patterns: [additive-non-destructive, staged-pilot-rollout, run-contract-normalization]
key-files:
  created: [docs/PIPELINE-STANDARD.md, shared/db.py, shared/subprocess_runner.py, scripts/scaffold_branch.py]
  modified: [shared/config_validator.py, shared/problem_registry.py, dispatcher.py]
metrics:
  plans: 9
  waves: 6
  branches: 7
---

# Phase 61: Pipeline Standardization & Branch Renewal — Phase Summary

## Objective

85개 블로그를 발행하는 7개 파이프라인 분기(car/curation/etap/rap/senior/travel/stock)를
**동일한 표준 골격**으로 재편하는 5000 리뉴얼. 분기별 비일관성(모듈 구조·config 스키마·실행
방식·DB 접근·외부 프로젝트)을 제거하고, 새 분기를 표준 템플릿으로 즉시 생성할 수 있는 기반을 만든다.

**Phase 경계:** 표준 정의 + 공용 기반 구축 + 분기별 staged 전환 + 온보딩 도구.
새 콘텐츠 기능·외부 프로젝트(TAP/STAP) 물리적 흡수 병합·`.bak` 실제 삭제는 범위 밖.

## 핵심 제약 (전 플랜 공통)

1. **무중단 + 비파괴:** 추가(additive) 위주, 기존 테스트 green 유지, **구조/동작 분리 커밋** (D-08)
2. **테스트 기준선:** task 전후 `pytest tests/test_dispatcher_registry.py -x`, Wave 병합 `pytest -q`, Phase 게이트 전체 스위트 green
3. **AdSense Publisher ID 불변:** 8772/6677/5938 매핑 위반 금지
4. **배포는 `dispatcher.py` 경유만:** 수동 wrangler 금지, `CLOUDFLARE_API_TOKEN` 제거 규칙 유지
5. **신규 third-party 패키지 0개:** stdlib + 기존 `requirements.txt`만 사용

## Wave / Plan 구조

| Wave | Plan | Stage | Objective |
|------|------|-------|-----------|
| 1 | `61-01-PLAN.md` | A | 표준 정의 — `docs/PIPELINE-STANDARD.md` (모듈 골격·config 스키마·reason 어휘·DB 규칙) |
| 2 | `61-02-PLAN.md` | B | 공용 기반 — `shared/db.py`, `shared/subprocess_runner.py`, `config_validator` 확장, `problem_registry` reason-key 보강 |
| 3 | `61-03-PLAN.md` | C | Pilot — SEAP(senior)·RAP 표준 골격 정렬 |
| 4 | `61-04-PLAN.md` | D1 | CAP(car) 전환 |
| 4 | `61-05-PLAN.md` | D2 | travel 전환 (None→no_result 정규화) |
| 4 | `61-06-PLAN.md` | D3 | curation 전환 |
| 5 | `61-07-PLAN.md` | D4 | ETAP(36) 단일화 — adapter wrapper, 브리지 유지 (최고 위험) |
| 6 | `61-08-PLAN.md` | E | 외부 STAP/TAP 정합 — `subprocess_runner` 라우팅 |
| 6 | `61-09-PLAN.md` | F | `scaffold_branch.py` + `.bak`/dead-code 보고 (삭제 없음) |

## Dependency Graph

```
Wave 1: 61-01 (A) 표준 정의
Wave 2: 61-02 (B) shared 기반
Wave 3: 61-03 (C) pilot SEAP/RAP
Wave 4: 61-04 (D1 car) | 61-05 (D2 travel) | 61-06 (D3 curation)  ← 병렬
Wave 5: 61-07 (D4 ETAP)
Wave 6: 61-08 (E) | 61-09 (F)  ← 병렬
```

## D-01 표준 모듈 골격 (모든 전환 플랜 공통 참조)

표준 골격 = `pipeline.py` / `fetcher` / `topic_manager` / `writer` / `enrich` / `validator`.
**D-01 규칙:** 기존 모듈은 유지·배선, 부재 모듈은 얇은 wrapper로 추가해 shared/ 코드로 위임 — 기존 코드 제거 금지.

| 분기 | pipeline | fetcher | topic_manager | writer | enrich | validator | 전환 |
|------|----------|---------|---------------|--------|--------|-----------|------|
| senior | ✓ | ✓ | ✗→wrapper | ✓ | ✗→wrapper | ✗→wrapper | 61-03 (C) |
| rap | ✓ | ✓ | ✗→wrapper | ✓ | ✗→wrapper | ✗→wrapper | 61-03 (C) |
| car | ✓ | ✗→wrapper | ✓ | ✗→wrapper | ✗→wrapper | ✗→wrapper | 61-04 (D1) |
| travel | ✓ | ✓ | ✗→wrapper | ✓ | ✗→wrapper | ✗→wrapper | 61-05 (D2) |
| curation | ✓ | ✗→wrapper | ✗→wrapper | ✓ | ✓ | ✗→wrapper | 61-06 (D3) |
| etap (35쌍) | ✓ | ✗→wrapper | ✓ | ✓ | ✗→wrapper | ✗→wrapper | 61-07 (D4) |
| stock (외부) | ✓ | ✓ | ✗ | ✓ | ✗ | ✗ | 61-08 (E, 계약만) |

## Phase Acceptance Criteria (ROADMAP)

- [ ] 7개 분기 전부 동일 모듈 골격 + 동일 `run(cfg)` 반환 계약
- [ ] `blogs.d/*.yaml` 표준 스키마 검증 통과 (`shared/config_validator.py`)
- [ ] 새 분기 1개를 `scaffold_branch.py`로 생성해 발행 가능함을 입증 (61-09)
- [ ] 기존 발행 파이프라인 무중단 — 단계별 pilot → 확산, 기존 테스트 green 유지

## 잔존 위험

1. **ETAP `run()`/`run(cfg)` 혼합 계약** — `_ETAP_BLOG_EXCEPTIONS` + `inspect.signature` 브리지(dispatcher.py:463-465)를 깨면 조용히 동작 변경. adapter wrapper로 위임하고 브리지 유지 (61-07).
2. **미등록 reason-key 11+** — `problem_registry.py`에 추가하지 않으면 `unknown_failure`로 소실 (61-02 해결).
3. **travel `run()` None 반환** — 표준 계약은 dict만 허용, `_run_single` 결과를 wrapper로 정규화 (61-05).
4. **subprocess_runner의 CLOUDFLARE_API_TOKEN** — wrangler subprocess 호출 전 env var 제거 (61-02/61-08).
5. **scaffold_branch 경로/모듈 주입** — 분기명 검증 `^[a-z][a-z0-9_]*$` (61-09).

## Output

- 각 실행 플랜 완료 시 `.planning/phases/61-pipeline-standardization-branch-renewal/61-{NN}-SUMMARY.md` 생성
- 이 `SUMMARY.md` 는 Phase 61 계획 요약으로 유지

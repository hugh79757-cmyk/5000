---
phase: 61-pipeline-standardization-branch-renewal
type: overview
wave: 0
depends_on: []
files_modified: []
autonomous: false
requirements: [61-A, 61-B, 61-C, 61-D, 61-E, 61-F]
---

# Phase 61: Pipeline Standardization & Branch Renewal — Plan Overview

## Objective

85개 블로그를 발행하는 7개 파이프라인 분기(car/curation/etap/rap/senior/travel/stock)를
**동일한 표준 골격**으로 재편하는 5000 리뉴얼. 분기별 비일관성(모듈 구조·config 스키마·실행
방식·DB 접근·외부 프로젝트)을 제거하고, 새 분기를 표준 템플릿으로 즉시 생성할 수 있는 기반을 만든다.

**본 Phase 경계:** 표준 정의 + 공용 기반 구축 + 분기별 staged 전환 + 온보딩 도구.
새 콘텐츠 기능(새 파이프라인 유형·새 수익 모델)은 범위 밖. 외부 프로젝트(TAP/STAP)의 물리적 흡수
병합은 범위 밖 (계약 정합만). `.bak` 파일 실제 삭제는 범위 밖 (보고서만, 별도 승인 필요).

## 핵심 제약 (전 플랜 공통, 반드시 준수)

1. **무중단 + 비파괴:** 기존 발행 파이프라인 중단 금지. 모든 변경은 **추가(additive)** 위주.
   기존 테스트 green 유지. **구조 변경과 동작 변경은 분리 커밋** (D-08).
2. **테스트 기준선:** 전 task 시작 전 `pytest tests/test_dispatcher_registry.py -x`, task 종료 시 동일 실행.
   Wave 병합 시 `pytest -q`, Phase 게이트 시 전체 스위트 green.
3. **AdSense Publisher ID 불변:** 8772/6677/5938 매핑 위반 금지 (AGENTS.md §1).
4. **배포는 `dispatcher.py` 경유만:** 수동 wrangler 금지. `CLOUDFLARE_API_TOKEN` 제거 규칙 유지 (AGENTS.md §3).
5. **신규 third-party 패키지 0개:** 이 Phase는 stdlib + 기존 `requirements.txt`만 사용. 설치 task 금지.

## Wave Structure

| Wave | Plan | Stage | Objective | Autonomous |
|------|------|-------|-----------|------------|
| 1 | `61-01-PLAN.md` | A | 표준 정의 — `docs/PIPELINE-STANDARD.md` | yes |
| 2 | `61-02-PLAN.md` | B | 공용 기반 — `shared/db.py`, `shared/subprocess_runner.py`, `config_validator` 확장, `problem_registry` reason-key 보강 | yes |
| 3 | `61-03-PLAN.md` | C | Pilot 전환 — SEAP(senior)·RAP 표준 골격 정렬 | yes |
| 4 | `61-04-PLAN.md` | D1 | CAP(car) 전환 | yes |
| 4 | `61-05-PLAN.md` | D2 | travel 전환 | yes |
| 4 | `61-06-PLAN.md` | D3 | curation 전환 | yes |
| 5 | `61-07-PLAN.md` | D4 | ETAP(36) 단일화 — topic_manager 설정 기반 수렴 (최고 위험, 최후) | yes |
| 6 | `61-08-PLAN.md` | E | 외부 STAP/TAP 정합 — `subprocess_runner` 라우팅 | yes |
| 6 | `61-09-PLAN.md` | F | `scaffold_branch.py` + `.bak`/dead-code 보고 | yes |

## Dependency Graph

```
Wave 1: 61-01 (A) ──── standard 정의 (스키마·계약·reason 어휘)
              │
Wave 2: 61-02 (B) ──── shared/db.py + subprocess_runner.py + config_validator + problem_registry
              │          (61-02 는 61-01 표준을 근거로 구현)
              │
Wave 3: 61-03 (C) ──── pilot SEAP/RAP (61-02 shared base 사용)
              │
Wave 4: 61-04 (D1 car)  61-05 (D2 travel)  61-06 (D3 curation)   ← 병렬 (파일 비중복)
              │
Wave 5: 61-07 (D4 ETAP) ──── pilot + rollout 검증 후 최후 단일화
              │
Wave 6: 61-08 (E subprocess_runner 라우팅)  61-09 (F scaffold+보고)  ← 병렬
```

## Requirements → Plan Map (ROADMAP Key Tasks)

| ROADMAP Requirement | Plan(s) |
|---------------------|---------|
| 61-A 표준 정의 | 61-01 |
| 61-B 공용 기반 구축 | 61-02 |
| 61-C Pilot 전환 (SEAP/RAP) | 61-03 |
| 61-D 확산 (CAP→travel→curation→ETAP) | 61-04, 61-05, 61-06, 61-07 |
| 61-E 외부 분기 정합 (STAP/TAP) | 61-08 |
| 61-F 온보딩 도구 + 레거시 정리 | 61-09 |

## D-01 표준 모듈 골격 기준 (모든 전환 플랜의 공통 참조)

표준 골격 = `pipeline.py` / `fetcher` / `topic_manager` / `writer` / `enrich` / `validator`.

**D-01 규칙:** 이미 존재하는 모듈은 **유지**하고 골격에 배선. 부재 모듈은 **얇은 wrapper**로 추가해
기존 shared/ 코드로 위임 — **기존 코드는 제거하지 않는다.**

| 분기 | pipeline | fetcher | topic_manager | writer | enrich | validator | 전환 |
|------|----------|---------|---------------|--------|--------|-----------|------|
| senior | ✓ | ✓ | ✗ | ✓ | ✗ | ✗ | 61-03 (C) |
| rap | ✓ | ✓ | ✗ | ✓ | ✗ | ✗ | 61-03 (C) |
| car | ✓ | ✗ | ✓ | ✗ | ✗ | ✗ | 61-04 (D1) |
| travel | ✓ | ✓ | ✗ | ✓ | ✗ | ✗ | 61-05 (D2) |
| curation | ✓ | ✗ | ✗ | ✓ | ✓ | ✗ | 61-06 (D3) |
| etap (35쌍) | ✓ | ✗ | ✓ | ✓ | ✗ | ✗ | 61-07 (D4) |
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
5. **scaffold_branch 경로 주입/모듈 주입** — blog_id/분기명 검증 (61-09).

## Output

- 각 실행 플랜 완료 시 `.planning/phases/61-pipeline-standardization-branch-renewal/61-{NN}-SUMMARY.md` 생성
- 이 Overview 는 계획 요약으로 유지

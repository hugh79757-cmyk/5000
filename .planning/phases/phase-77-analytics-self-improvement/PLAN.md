# Phase 77: Analytics 기반 셀프 개선 루프 — PLAN

**Source of truth:** `CONTEXT.md` (this dir)
**Date:** 2026-09-03
**Status:** PLANNED
**Additive non-destructive:** 예 — 신규 모듈 + env 킬스위치(기본 OFF). 기존 선택 로직 무변경, 신호 부재 시 기존 동작과 동일. 기존 테스트 green 유지.

---

## 1. Phase Goal

수집된 성과 데이터(GSC 클릭/노출)에서 **검증된 수요 패턴**을 추출해 키워드 선택에 반영하는 학습 루프를 구축한다. 관찰(제안만 출력) → 반영(env 게이트) 순서로 증분 적용.

**Goal-backward 검증 기준 (Phase 완료 판정):**

1. 추출기가 data/keyword_performance.json에 실측 수요 패턴 ≥3건 산출 (유지비/드라이브/예비군류 — 실측 데이터에 존재 확인됨)
2. `PERF_SIGNALS=1` 시 매칭 후보 우선 선택 (재현 테스트)
3. `PERF_SIGNALS` 미설정(기본 OFF) 또는 신호 파일 부재 시 기존 `_select_keyword` 동작과 동일 (재현 테스트)
4. 기존 curation 테스트 회귀 0건 (OPS_TEST_MODE=1 pytest tests/curation — baseline 대조)
5. collect_analytics.sh 6h 주기 실행 시 추출기 동작, 기존 수집 무영향 (로그 증거)

## 2. Scope

**In:**
- 성과 신호 추출기 (gsc_keywords → 수요 패턴 JSON)
- `_select_keyword` 개입 (매칭 후보 우선 정렬 — additive, env 게이트)
- collect_analytics.sh 말미에 추출기 호출 추가 (1줄)
- 반영 모드 활성화 runbook (관찰 기간 기준 + 절차)

**Out (fence):**
- travel fetcher 가중 선택 (신호 규모 작음 — travel-hugo 15클릭. curation 검증 후 별도 검토)
- GA4 수집 재개 (데이터 수집 인프라 수정 — 별개 이슈)
- keyword_pool SSOT 마이그레이션 (Phase 76 SSOT-DESIGN.md 실행 별도 phase)
- LLM 프롬프트 개편 (개입은 키워드 선택 레이어만)
- 슬로우/킬 키워드 자동 강등 (Wave 3 확장 — 관찰 데이터 축적 후 별도 결정)

## 3. Tasks

### Wave 1 — 신호 추출기 (관찰 모드, 동작 변화 0)

**Task 1.1: shared/performance_signals.py 신규**

- **What/Why:** gsc_keywords에서 클릭≥1, 90일 윈도우 쿼리를 blog_id별 수요 패턴으로 추출 → `data/keyword_performance.json` 원자적 쓰기(tmp+rename). 이 파일이 곧 학습 상태 — 원시 데이터에서 6h마다 재생성되므로 **롤백 = 파일 삭제 후 재생성**. 별도 스냅샷 구조 불필요 (재생산 가능 구조가 곧 롤백 가능 구조).
- **Files:** `shared/performance_signals.py` (신규), `data/keyword_performance.json` (생성물 — .gitignore에 data/*.json 패턴 있는지 확인, 없으면 추가)
- **구조:** `{blog_id: [query, ...]}` 단순 리스트. 토큰 매칭은 소비 측에서 수행 (추출기는 데이터 정제만 — 토큰화·점수화 로직 중복 배제)
- **Verify:** `python3 -m shared.performance_signals` 실행 후 JSON에 deal-hugo 'gr86 유지비', travel3-hugo '대전 드라이브' 등 실측 패턴 포함 + assert 기반 `__main__` 셀프체크
- **Rollback:** 스크립트 삭제 (어떤 파이프라인도 참조 전 — 무영향)

**Task 1.2: collect_analytics.sh 추출기 호출 추가**

- **What/Why:** 6h 주기 수집 말미에 추출기 1줄 추가. 별도 launchd 등록 불필요 — 기존 잠금/타임아웃 체계 재사용.
- **Files:** `scripts/collect_analytics.sh` (말미 1줄 — `|| true` 가드로 수집 본체 무영향)
- **Verify:** 스크립트 dry-run 모드 또는 수동 1회 실행 — 기존 수집 단계 완료 후 JSON 갱신 확인
- **Rollback:** 1줄 제거

### Wave 2 — 선택 개입 (반영 모드, env 게이트)

**Task 2.1: _select_keyword 매칭 우선 정렬**

- **What/Why:** 기존 필터 통과 후 최종 선택 직전에, 수요 패턴과 토큰을 공유하는 후보를 리스트 선두로 정렬. **기존 선택 로직(랜덤/순차) 무변경 — 리스트 순서만 조작.** 토큰 매칭: 공백 분리 토큰 완전 일치 (예: 후보 "그랜드랜지 유지비" ↔ 패턴 "gr86 유지비" → '유지비' 일치 → boost).
- **Files:** `pipelines/curation/pipeline.py` (`_select_keyword` 내부, 최종 선택 직전 1블록 삽입)
- **게이트:** `PERF_SIGNALS` env — 미설정(기본 OFF)·`0`·파일 부재·해당 blog_id 신호 없음 → 4가지 전부 기존 동작 그대로 passthrough. 파일 읽기 실패(손상 JSON 등)도 try/except로 passthrough.
- **선행:** baseline 먼저 — `OPS_TEST_MODE=1 pytest tests/curation` 기록 후 수정, 동일 테스트 재실행 대조.
- **Verify:** `tests/test_performance_signals.py` — (a) 매칭 후보 우선 정렬 재현, (b) env OFF/파일 없음 → 순서 불변, (c) 손상 JSON → passthrough. + tests/curation 회귀 0건.
- **Rollback:** `PERF_SIGNALS=0` 런타임 킬스위치 (기본 OFF이므로 실배포 영향 자체가 0) + revert 커밋

### Wave 3 — 활성화 runbook (문서)

**Task 3.1: 반영 모드 전환 절차 문서**

- **What/Why:** 관찰 기간(1~2주) 후 기본 ON 전환 절차. 전환 기준: (a) 추출기 6h 주기 연속 성공 ≥14회, (b) JSON 패턴 수 안정(직전 3회 실행 동일), (c) tests/curation green 유지. 전환 = `_select_keyword`의 기본값 OFF→ON **1줄 변경** 또는 scheduler.py env 주입 — 문서에 명시. 실패 시 되돌림: `PERF_SIGNALS=0` 즉시 무력화.
- **Files:** `.planning/phases/phase-77-analytics-self-improvement/RUNBOOK-enable.md` (신규)
- **Verify:** 문서에 전환 기준·절차·되돌림 3요소 포함
- **Rollback:** N/A (문서)

## 4. Verification (Phase 전체)

| 기준 | 방법 |
|---|---|
| 수요 패턴 ≥3건 산출 | 추출기 실행 + JSON 실측 패턴 grep (유지비/드라이브/예비군) |
| boost 동작 | pytest tests/test_performance_signals.py — 매칭 재현 케이스 |
| 기본 OFF passthrough | 동일 테스트 — env 미설정 순서 불변 케이스 |
| 회귀 0건 | OPS_TEST_MODE=1 pytest tests/curation — baseline 대조 |
| 6h 주기 동작 | collect_analytics.sh 실행 로그에 추출기 단계 + 기존 수집 완료 |

## 5. Rollback

- Wave 1: 스크립트/1줄 삭제 (참조자 없음)
- Wave 2: `PERF_SIGNALS=0` (즉시 무력화, 재배포 불필요) + revert 커밋
- 학습 상태 자체: `data/keyword_performance.json` 삭제 → 다음 6h 주기 재생성 (원시 데이터 보존)
- Wave 3: N/A (문서)

## 6. Constraints Checklist

- [ ] Pipelines keep running — 스케줄러 무중단 (코드 변경은 파이프라인 프로세스 내 additive, 재시작 불필요)
- [ ] 배포 없음 — Hugo 사이트 무관, wrangler 미사용
- [ ] 파괴적 작업 없음 (DB 스키마 무변경 — analytics.db 읽기 전용, 신규 JSON 파일만)
- [ ] Additive non-destructive — 기존 함수 시그니처 무변경, env 킬스위치 기본 OFF
- [ ] 기존 테스트 green 유지 (baseline 대조 후 수정)
- [ ] 커밋 단위: Wave 1 (추출기+훅) → Wave 2 (개입+테스트) → Wave 3 (runbook) 개별 커밋

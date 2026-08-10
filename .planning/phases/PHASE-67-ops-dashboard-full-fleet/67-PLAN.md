---
phase: 67
title: "Ops Dashboard — 전 5000 파이프라인 블로그 반영 + 에이전트 조작 가능화"
research: skip
---

# Phase 67: Ops Dashboard — 전 5000 파이프라인 블로그 반영 + 에이전트 조작 가능화

**목표:** Ops Dashboard가 cuap/seap/stap 3개만이 아니라 5000 파이프라인 전체(약 83개 블로그)를 반영하고, 에이전트가 API로 확인·조작할 수 있게 한다. "대시보드가 어떻게 진화됐는지" 한눈에 볼 수 있는 진화 이력 표시 포함.

**배경:** Phase 59에서 대시보드 구축, Phase 62에서 C01~C08 체크 통합, Phase 64에서 규칙 체계 진화. 현재 DB에 cap(8)/etap(36)/rap(5)/tap(8)이 보이지 않는 문제 + pipeline 컬럼 부재로 에이전트가 "계열별 상태"를 볼 수 없는 문제.

**제약:** 기존 기능 보존. `_ensure_db()`·`seed_*`는 `INSERT OR IGNORE`로 중복 방지 이미 됨. YAML 파서 한계 확인이 선행 필요.

**산출물:** PLAN.md + 아래 5개 task의 실행 결과 + STATE.md 업데이트

---

## Task 67.1 — YAML 파서 확인 + 전체 블로그 DB 동기화

**목표:** `sync_blog_lifecycle()`가 cap/etap/rap/tap YAML을 제대로 파싱하는지 확인하고, 안 되면 파서 수정 후 전체 83개 블로그를 `blog_lifecycle`에 반영.

**실행:**
1. `ops_dashboard/db.py`의 `_parse_yaml_file()`이 cap/yaml, etap/yaml, rap/yaml, tap/yaml을 파싱 못하는 원인 확인
2. 원인별 수정:
   - YAML 구조 차이(예: tap의 `blogger_blog_id`, `blog_id_env` 등) → 파서가 지원하도록 확장
   - 파일명 기반 brand 감지(`_detect_brand`)는 이미 작동 중 — brand 누락이 아니라 파싱 누락이면 파서 수정
3. `sync_blog_lifecycle()` 재실행 → 전체 블로그 `blog_lifecycle`에 반영
4. 검증: `SELECT DISTINCT brand FROM blog_lifecycle` → cap/cuap/etap/rap/seap/stap/tap + manual 모두 나와야 함

**검증:**
- [ ] `blog_lifecycle`에 8개 brand 모두 존재
- [ ] blog 수 약 83개 (ETAP 36 + CUAP 15 + STAP 6 + CAP 8 + RAP 5 + TAP 8 + SEAP 2 + manual 1)
- [ ] 각 blog에 `config_status` (active/inactive/paused) 정확히 반영

**산출물:** 없음 (DB 수정만). STATE.md에 결과 기록.

---

## Task 67.2 — pipeline 컬럼 추가 + YAML pipeline 값 동기화

**목표:** 에이전트가 "계열별 상태"를 파이프라인 단위로 볼 수 있도록 `blog_lifecycle`에 `pipeline` 컬럼 추가, YAML의 `pipeline` 값을 동기화.

**실행:**
1. `db.py`의 `init_db()` + `_alter_columns()`에 `pipeline TEXT DEFAULT ''` 추가
2. `sync_blog_lifecycle()`의 UPDATE/INSERT에 `pipeline` 값 포함
3. `_parse_yaml_file()`이 YAML의 `pipeline:` 키를 파싱하도록 확인 (이미 `pipeline` 키가 처리되고 있는지 확인 — 2026-08-07 STATE.md 기준 파서가 `pipeline`을 처리 중인지?)
4. API `/api/fleet` 응답에 `pipeline` 필드 포함 확인
5. 에이전트 조작: `/api/fleet` GET → pipeline별 필터링은 클라이언트 측에서 (또는 API에 `?pipeline=xxx` 추가 검토)

**검증:**
- [ ] `blog_lifecycle`에 `pipeline` 컬럼 존재
- [ ] 모든 블로그에 pipeline 값 채워짐 (car/curation/etap/rap/senior/stock/travel)
- [ ] `/api/fleet` 응답에 pipeline 포함

**산출물:** `db.py` 수정 커밋, STATE.md에 결과 기록.

---

## Task 67.3 — 대시보드 진화 이력 표시 (UI)

**목표:** "대시보드가 어떻게 진화됐는지" 한눈에 볼 수 있도록 Phase 59 → 62 → 64 → 67 흐름을 UI에 버전 지표로 표시.

**실행:**
1. `app.py`의 인덱스 페이지에 "대시보드 버전 이력" 섹션 추가:
   - Phase 59 (2026-08-06): 초기 구축 — Flask UI + JSON API + 7개 체크 모듈
   - Phase 62 (2026-08-07): C01~C08 콘텐츠 무결성 체크 통합 + preflight 게이트
   - Phase 64 (2026-08-07): 규칙 체계 진화 — C05→P 이동, 네임스페이스 분리, S01/S04 severity 확정, Task 6 체크리스트
   - Phase 67 (현재): 전 파이프라인 블로그 반영 + pipeline 컬럼 + 에이전트 조작
2. 버전별 "추가된 기능"을 아이콘/태그로 표시 (예: ✓ API, ✓ 체크, ✓ 규칙)
3. `/api/readiness` 응답에 `dashboard_version` 필드 추가 (현재 버전: "67")

**검증:**
- [ ] 인덱스 페이지에 버전 이력 섹션 표시
- [ ] 각 버전별 주요 기능 태그 표시
- [ ] `/api/readiness`에 `dashboard_version` 포함

**산출물:** `app.py` 수정 커밋, `templates/index.html` 수정, STATE.md에 결과 기록.

---

## Task 67.4 — 에이전트 API 조작 강화 검토

**목표:** 에이전트가 대시보드를 더 효율적으로 조작할 수 있도록 기존 API 검토 + 필요 시 개선.

**실행:**
1. 기존 API 검토:
   - `POST /api/run-checks?blog_id=` — 단일 블로그 체크 실행 (전체 지정 방법 확인)
   - `POST /api/maintenance/status` — 정비 상태 변경
   - `POST /api/maintenance/checklist` — 정비 체크리스트 실행
2. 필요 개선 검토 (선택적 — 전면 수정이 아니라 필요 최소한):
   - 전체 블로그 한 번에 체크 실행 시 응답 시간 — 배치 처리 또는async 고려?
   - 계열별(brand) 필터 체크 실행 옵션 추가? (`?brand=cuap`)
   - 체크 결과의 `check_results` 데이터를 에이전트가 쉽게 소비할 수 있는 형태인지 확인
3. **전면 수정 금지** — 기존 API로 충분하면 수정하지 않고 문서만 정리

**검증:**
- [ ] 에이전트가 `/api/run-checks`로 단일 블로그 체크 실행 가능 확인
- [ ] 전체 블로그 체크 실행에 문제 없는지 (응답 시간, 타임아웃)
- [ ] 필요 개선 사항 목록 문서화 (실제 수정 여부는 별도 결정)

**산출물:** 검토 결과 메모 (db.py/app.py 수정 필요할 수도, 안 할 수도 있음).

---

## Task 67.5 — 통합 검증

**목표:** Phase 67 전체가 의도대로 동작하는지 확인.

**실행:**
1. API 호출로 전체 블로그 목록 확인:
   ```
   GET /api/fleet → brand 8종, pipeline 7종 모두 포함
   ```
2. 특정 계열(예: cap) 블로그만 필터해서 상태 확인
3. 특정 블로그(예: compare-hugo)에 체크 실행 → `check_results`에 기록
4. 대시보드 UI에서 "대시보드 진화 이력" 표시 확인
5. `/api/readiness` 응답에 dashboard_version 포함 확인

**검증:**
- [ ] `GET /api/fleet` → 8개 brand, pipeline 정보 포함, 약 83개 블로그
- [ ] `POST /api/run-checks?blog_id=compare-hugo` → check_results 기록
- [ ] 인덱스 페이지 버전 이력 표시
- [ ] 대시보드 진화 이력이 "한눈에" 이해되는 수준

**산출물:** VERIFICATION.md (검증 결과 기록)

---

## 파스 차단기

- Task 67.1에서 YAML 파서가 cap/etap/rap/tap을 전혀 파싱 못하는 구조적 문제면 → 파서 전면 수정 필요할 수 있음. 이 경우 Task 분할 재검토.
- `sync_blog_lifecycle()`가 이미 전체를 파싱하고 있는데 DB 조회 쿼리 문제였다면 → Task 67.1은 쿼리 확인으로 단축.

---

## 실행 순서

1. **67.1 먼저** — DB에 전체 블로그가 있어야 이후 작업이 의미 있음
2. **67.2** — pipeline 컬럼은 67.1과 병행 가능 (같은 db.py 수정)
3. **67.3** — UI 작업은 DB 수정 후 (데이터가 있어야 진화 이력도 의미 있음)
4. **67.4** — API 검토는 67.1/67.2 이후에 (실제 데이터로 테스트 가능)
5. **67.5** — 마지막에 통합 검증

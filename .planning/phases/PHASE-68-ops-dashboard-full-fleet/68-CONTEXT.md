# Phase 68: Ops Dashboard — 전 5000 파이프라인 블로그 반영 + 진화 이력 표시

**목표:** Ops Dashboard가 cuap/seap/stap 3개만이 아니라 5000 파이프라인 전체(약 83개 블로그)를 반영하고, 에이전트가 API로 확인·조작할 수 있게 한다. "대시보드가 어떻게 진화됐는지" 한눈에 볼 수 있는 진화 이력 표시 포함.

**배경:** Phase 59에서 대시보드 최초 구축 (Flask UI + JSON API + 7개 체크 모듈, 10 커밋 완료). Phase 62에서 C01~C08 체크 통합. Phase 64에서 규칙 체계 진화. 현재 DB에 cap(8)/etap(36)/rap(5)/tap(8)이 보이지 않는 문제 + pipeline 컬럼 부재로 에이전트가 "계열별 상태"를 볼 수 없는 문제.

**결정 사항:**
- brand 감지는 `_detect_brand()` (YAML 파일명 기반)로 자동 — 새 YAML 추가만으로 새 brand 등록
- pipeline 컬럼을 `blog_lifecycle`에 추가하고 YAML의 `pipeline` 값을 동기화
- 에이전트가 `/api/run-checks?blog_id=` 또는 전체로 체크 실행 가능해야 함 (기존 API 있으나 전체 실행 시 응답 시간 고려 필요)
- "대시보드 진화 이력"은 UI에 타임라인/버전 지표로 표시 (Phase 59 → 62 → 64 → 68)

**제약:**
- 기존 기능 보존 (Phase 59/62/64에서 이미 동작 중인 것 깨지 않기)
- `_ensure_db()`는 호출 시마다 `seed_known_issues`, `seed_standard_rules`를 `INSERT OR IGNORE`로 수행 — 중복 삽입 방지 메커니즘 이미 있음
- `sync_blog_lifecycle()`는 YAML 파서에 의존 — cap/etap/rap/tap YAML 파싱 실패가 원인이면 파서 수정 필요
- **Phase 67과 별개** — 67은 현재 세션에서 혼란 중이므로 건드리지 않음

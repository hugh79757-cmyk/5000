# Phase 69: 통합 레지스트리 (Unified Rule/Error Registry) — 단일 출처 구조 설계·구현

**목표:** 규칙(R01~R12, 표준체크)과 발행오류(P01~P24)를 **하나의 선언적 레지스트리**로 통합하고, 개별 결과를 DB에 열(column) 단위로 저장한 뒤 **단일 엔드포인트**로 노출하여, "새 규칙/오류 = 선언 추가만으로 대시보드·에이전트에 자동 반영"되게 만든다. **코드 변경 없이 추가 가능한 단일 출처.**

**배경 (Phase 68 진단·라이브 검증 결과):**
- 정적 진단(B1~B7 병목) + 라이브 검증으로 확정된 사실:
  - **B4 확증:** `check_results`에 개별 R/P 행 없음 — `standard_compliance`는 blog당 aggregate 1행이고, R01~R12 위반은 `detail` 자유텍스트 문자열에만 존재. `rule_id/problem_id/action/severity` 컬럼 부재.
  - **B5 확증:** auto-triage 분류 결과(problem_id/severity/action)가 4종 엔드포인트(`/api/attention,/issues,/readiness,/standards`) 어디에도 없음 — 텔레그램·요약 텍스트로만 출력.
  - **B7 확증:** `/api/attention` fail_checks 6필드(blog_id/check_name/status/detail/evidence_url/checked_at)에 rule_id·problem_id·action 없음.
- 프로세스 의존성: **스키마 변경 시 파손 프로세스 2개** — ops-dashboard(13818), auto-triage(03:00 Cron). scheduler(78295)·watchdog(34819)는 무관.
- 안전 마이그레이션: **점진 웨이브 필요** — DB 컬럼 추가는 하위호환, JSON `detail` 자유텍스트·엔드포인트 변경은 auto-triage와 동시 이행 필요.

**웨이브 (W1~W7) — 순차 게이트 구조:**
- **W1:** 통합 레지스트리 스키마 정의 (비파괴, 순수 정의)
- **W2:** DB 컬럼 additive 추가 (rule_id/problem_id/severity/action, NULL 허용)
- **W3:** 개별 규칙행 이중 기록 (dual-write, aggregate 유지 + R개별 행 추가)
- **W4:** 오류분류 JSON 출력 경로 신설 (B5 해소, additive)
- **W5:** 엔드포인트 통합 + 소비자 전환 (가장 위험 — auto-triage 집중 게이트)
- **W6:** 낡은 자유텍스트/이중정의 제거 (cleanup, 마지막에만)
- **W7:** 내용물 채우기 (R06 A/B, THUMBNAIL-01, R2-01, Blowfish 21항목 선언 추가)

**각 웨이브 게이트 (동일):** ops-dashboard·auto-triage 살아있는지, 무인화 4프로세스 정상인지. 하나라도 깨지면 해당 웨이브에서 중단·롤백.

---

## 통합 스키마 (W1 중립 스키마)

```
id          : R01 / P01 / THUMBNAIL-01 / R2-01  (전역 고유)
kind        : rule | error
target      : 파일 경로 또는 대상 (hugo.toml, extend-head.html, body, publish, ...)
severity    : CRITICAL | MAJOR | MINOR
threshold   : always | consecutive:N | quiet
check_fn    : 검사 함수명 문자열 (rule용) / detect_fn (error용)
action      : 조치 안내 텍스트
bucket      : actionable | deferred | out_of_scope (rule용, 준수율 산정)
```

## 통합할 기존 정의 (W6 정리 대상)

| 현재 정의 | 파일 | 필드 | 통합 방향 |
|---|---|---|---|
| R01~R12 | `ops_dashboard/checks/standard.py` `STANDARD_RULES` (L27) | rule_id/target/severity/description/bucket/check | 레지스트리로 이동 |
| R 시드 | `ops_dashboard/db.py` `SEED_STANDARD_RULES` (L513) | rule_id/target/severity/description | 레지스트리에서 파생 (이중정의 제거) |
| P01~P24 | `shared/problem_registry.py` `PROBLEM_REGISTRY` | reason_keys/severity/hook/threshold/alert_template | 레지스트리로 이동 |
| P 분류 | `scripts/auto_triage_rules.yaml` | 판정/자동조치/사람호출 | 레지스트리와 병합 |
| 하드코딩 맵 | `scripts/auto_triage.py` L853/866/888 | _check_name_to_problem_id/_pattern/_reason | 레지스트리에서 파생 |

## 제약 (비파괴 원칙)

- **기존 기능 보존.** 각 웨이브는 additive. 기존 동작하던 경로(aggregate 행, detail 자유텍스트, 텔레그램/요약)를 제거하는 시점은 W6 이후 — 소비자가 새 구조로 완전 이행한 뒤에만.
- **스키마 변경은 W2에서 NULL 허용 컬럼 추가만.** 기존 행을 깨지 않음.
- **W5 (엔드포인트 통합 + auto-triage 전환)가 최대 위험점.** 여기서 auto-triage가 깨지지 않는지 집중 게이트.
- **C01~C09 (content_integrity) 규칙** — 별도 체크 모듈. 통합 대상에 포함하되 기존 동작 유지 (스코프 후순위).
- **Phase 67·68·68-b와 무관.** 별도 진행.

## 검증 기준 (Phase 69 완료 시)

- [ ] 단일 선언 레지스트리 존재 — 규칙·오류가 같은 스키마로 선언됨
- [ ] check_results에 rule_id/problem_id/severity/action 컬럼 존재 (NULL 허용)
- [ ] W3 이후: standard 체크 시 aggregate + R개별 행 공존 (detail 자유텍스트 유지)
- [ ] W4 이후: auto-triage 분류 결과가 DB/JSON에도 기록됨 (텔레그램 유지)
- [ ] W5 이후: 단일 엔드포인트가 규칙 개별행 + 오류분류를 같은 스키마로 노출, auto-triage가 구조 필드 읽기로 전환 (자유텍스트 파싱 제거)
- [ ] W6 이후: detail 자유텍스트 의존·STANDARD_RULES/SEED 이중정의 제거
- [ ] W7 이후: R06(A/B), THUMBNAIL-01, R2-01, Blowfish 21항목이 선언으로 등록 — "새 규칙 = 선언 한 줄 + 함수 1개" 실증
- [ ] 각 웨이브 종료 시 ops-dashboard·auto-triage 생존 + 무인화 4프로세스 정상

# WL-20260808-w5-endpoint-structured-fields

> 날짜: 2026-08-08 / 연관: Phase 69 W5 + W6 배포 게이트 / 상태: 완료 (라이브 노출 완료)

## 배경

Phase 69 W5(최대 위험 웨이브): auto-triage가 자유텍스트 파싱에서 구조 필드 읽기로
전환하는 지점. (1) `/api/registry` 단일 엔드포인트 신설, (2) `get_attention_items`에
구조 필드(rule_id/problem_id/severity/action) 노출, (3) auto-triage 소비자 전환
(구조 필드 우선 + 자유텍스트 폴백). 자유텍스트 파서는 W6까지 제거하지 않는다.

## W5-전 baseline 캡처 (2026-08-08, --dry-run problem_id 분포)

총 237건. 배포 전 대조 기준으로 저장.

```
excluded: 69
P02: 36
P14: 26
leak_detected: 26
known_issue: 25
standard_compliance: 21
P17: 12
P15: 6
unknown_failure: 5
P18: 4
dead_entity_link: 3
P01: 2
P06: 1
P10: 1
합계: 237
```

## 진단 (변경 전)

- 현재 fail_checks 34건 중 **구조 필드(rule_id/problem_id) 채움 = 1건**(pet-hugo/R06)뿐.
  나머지 전부 rule_id NULL → 전환 후에도 자유텍스트 폴백 경로로 분류됨.
- 결론: W5 전환은 현재 데이터에서 분류 결과를 바꾸지 않아야 함 (폴백이 기존과 동일).

## 변경 사항

- `ops_dashboard/db.py`
  - W5-1: `get_attention_items` SELECT + fail_check/excluded dict에
    rule_id/problem_id/severity/action 4필드 추가 (aggregate행은 NULL → 폴백).
  - W5-3: `get_registry_view(conn)` 헬퍼 신설 — 규칙(R 개별행 + registry 선언)과
    오류(triage 최신 + registry error 선언)를 동일 스키마로 노출, 구조 필드 포함(B7 해소).
  - W5 잔존위험: `record_triage_classification`(단건 raw INSERT, run 관리 부재) 삭제로
    누적 우회경로 봉인.
- `ops_dashboard/app.py`
  - W5-3: `GET /api/registry` 라우트 신설 (`@require_auth`).
- `scripts/auto_triage.py`
  - `fetch_dashboard_data`에 `("registry","/api/registry")` 엔드포인트 추가.
  - W5-2: `_build_registry_map(registry_data)` + `_resolve_problem_id(item, registry_map)`
    신설. 우선순위: problem_id → rule_id(registry 역방향) → 자유텍스트 폴백(pattern→check_name→unknown_failure).
  - `run_triage` fail_checks 루프를 `_resolve_problem_id`로 교체 + ctx에 구조 필드 전달.

## 파괴적 작업 목록

| 시각 | 작업 | 명령 | 사전카운트 | 백업 | 사후대조 | 보존확인 |
|------|------|------|-----------|------|---------|----------|
| 18:40 | `record_triage_classification` 함수 삭제 (누적 우회경로 봉인, task 승인) | edit ops_dashboard/db.py | 0 호출부 | tag pre-w5-endpoint-2026-08-08 | rg 0건 | replace 경로로 대체됨 |

## 4단계 프로토콜 이행

1. 사전 카운트: `record_triage_classification` 호출부 0건(이미 W4.5에서 replace로 전환) → 삭제 안전.
2. 되돌림 수단: `ops_dashboard/ops.db.bak_w5_20260808` + git tag `pre-w5-endpoint-2026-08-08`.
3. 실행: db.py/app.py/auto_triage.py 수정 → temp-DB + 단위 + dry-run 검증.
4. 사후 대조: dry-run 분류 237 (baseline 일치), 2회 연속 건수 불변, /api/registry 라우트 등록.

## 검증 (W5 게이트)

- W5-1: temp-DB `get_attention_items` fail_check에 4필드 노출 확인.
- W5-2 폴백 실증(신구행):
  - 구조 필드 우선: `{'problem_id':'P01'}` → P01, `{'rule_id':'R02'}`+map → P99.
  - 자유텍스트 폴백: `{'check_name':'freshness'}` → P01, 미등록 R06 → unknown_failure.
  - 실데이터 pet-hugo/R06 (rule_id 채움, problem_id 없음): registry 매핑 없음 → 폴백 → unknown_failure (W5-전과 동일).
- W5-3: temp-DB `get_registry_view` rules=12 / errors=25, 구조 필드 포함. /api/registry 라우트 등록 확인.
- **분류 baseline 대조(핵심)**: W5 전환 후 --dry-run 분포가 W5-전 baseline(237)과 diff 0 — 일치.
- auto_triage --dry-run exit 0 (2회), 건수 불변(237), run_id 1종.
- 텔레그램(dry-run 미발송)·summary.log(+200줄=정상 append)·JSON 경로 무변경.
- git diff --stat: ops_dashboard/db.py / scripts/auto_triage.py / ops_dashboard/app.py 만.
  언스테이지 트랙 파일 집합은 baseline 대비 app.py만 추가(허용 범위).
- 라이브 /api/registry는 404(기존 대시보드 프로세스 미재시작) — 자동오류 감지 확인, auto_triage는 빈 registry로 폴백해 정상.

## 잔존 위험

- 라이브 ops_dashboard 프로세스(PID 13818)가 여전히 이전 app.py를 실행 중 → `/api/registry`
  라이브 노출은 대시보드 재시작 후. 재시작은 별도 배포 단계(이 웨이브 범위 아님). 재시작 전까지
  auto_triage는 registry 404 → 빈 매핑 → 폴백으로 정상 동작(확인됨).
- `_build_registry_map`는 rule(R)↔error(P) id 접두사가 달라 실제 대응이 거의 생기지 않음 →
  구조 필드 우선 경로는 개별행이 problem_id를 직접 가질 때(W3가 이후 채우는 경우) 주로 발화.
  rule_id 단독으로는 registry 문제 ID가 없어 폴백으로 떨어짐 — W6에서 rule↔error 대응 정의 필요할 수 있음.
- W6 착수는 별도 승인 필요(자유텍스트 파서·이중정의 제거는 W5에서 안 함).

## W6 배포 게이트 완료 (2026-08-08 19:00, 코드 변경 없음 — 대시보드 재시작만)

대시보드 데몬 재시작으로 W5 코드를 라이브화. 배포 게이트 5/5 통과.

| 게이트 | 결과 | 근거 |
|--------|------|------|
| 대시보드 재시작 | PID 13818 → 36588, 시작 18:58:30, 포트 5060 LISTEN | `launchctl list` + `lsof` |
| /api/registry 라이브 | 404 → 200, rules=12 / errors=25, 구조 필드 포함 | curl + JSON 파싱 |
| /api/attention 구조필드 라이브 | fail_check 4필드(rule_id/problem_id/severity/action) 노출, 34건 | curl JSON 파싱 |
| 회귀 없음 | readiness metrics 동일 / attention 공통필드 34=34·69=69·open 25·stale 7 동일 | pre/post 스냅샷 diff |
| auto_triage 라이브 registry 소비 | registry LIVE(rules=12/errors=25, 404 아님), _build_registry_map={} (R/P 접두사 미대응 → 폴백 유지) | fetch_dashboard_data + _build_registry_map |
| 분류 baseline 보존 | 237 행 / run_id 1종 / classified_at 1종. **problem_id 분포가 W5 baseline과 diff 0** (excluded:69, P02:36, P14:26, leak_detected:26, known_issue:25, standard_compliance:21, P17:12, P15:6, unknown_failure:5, P18:4, dead_entity_link:3, P01:2, P06:1, P10:1) | ops_dashboard/ops.db GROUP BY |

- 핵심 실증: dry-run이 라이브 registry 위에서 실행되어도 triage_classifications가
  replace(최신 run_id 20260808190010, classified_at 2026-08-08 12:00:10 UTC = 19:00 +07)로
  단일 1회분만 유지 → **누적 0**. W4.5 가드가 라이브 조건에서도 유효함을 라이브로 입증.
- 파괴적 작업 로그: `logs/destructive_2026-08-08.log` 3번째 줄에 데몬 재시작 기록.
- 되돌림: git tag `pre-w6-deploy-gate-2026-08-08` + `ops.db.bak_w5_20260808`.

## 잔존 위험 (W6 이후)

- `_build_registry_map`는 rule(R)↔error(P) id 접두사가 달라 실제 대응이 거의 생기지 않음 → 현재
  구조 필드 우선 경로는 개별행이 problem_id를 직접 가질 때(W3가 이후 채우는 경우) 주로 발화.
  rule_id 단독으로는 registry 문제 ID가 없어 폴백으로 떨어짐. **W6-a에서 rule↔error 대응을 정의**하면
  R/P 매핑이 생기고 구조 필드 우선 경로가 본격 발화 예정 (별도 승인 필요).
- W6-b(자유텍스트 파서·이중정의 제거)도 별도 승인 필요.

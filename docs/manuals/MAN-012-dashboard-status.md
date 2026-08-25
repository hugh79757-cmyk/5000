# MAN-012 대시보드 상태 분류 기준

- ID: MAN-012
- Created: 2026-08-25
- Scope: ops_dashboard `blog_lifecycle.lifecycle_status` 및 `check_results.status` 4단계 분류와 전환 조건

## 1. 정의 및 범위
- 대상 테이블: `blog_lifecycle` (85 blogs) + `check_results` (159 checks/run)
- 상태 4종: `healthy`/`warning`/`critical`/`unknown` 은 `check_results.status` 기준, `blog_lifecycle.lifecycle_status` 는 `active`/`paused`/`disabled`/`unknown`
- 본 매뉴얼은 두 상태 축의 매핑과 자동 resolved 규칙을 정의

## 2. 탐지 조건
- `check_results.status`:
  - `pass` — 해당 check 통과 (PIPELINE_FAILURE_HEALTH 등 111건)
  - `warning` — 임계값 초과 1회 (예: P02 1건, TABLE_QUALITY cols>5 등 39건)
  - `critical` — 임계값 다중 초과 (예: P02 ≥16건, health P03+P14 등 9건)
  - `unknown` — 지원 불가/미분류 (현재 0건, 과거 pipeline_path 미매핑 시 225건 발생)
- `blog_lifecycle.lifecycle_status`:
  - `active` — `config/blogs.d/*.yaml` 에서 `status: active` (76)
  - `paused` — `status: paused` (8, legacy manual 5 포함)
  - `disabled` — `status: disabled` (1)
  - `unknown` — `config_status` 미매핑 또는 `pipeline` 미지원 (현재 0)

## 3. 자동 조치
- `sync_blog_lifecycle()` 매 실행 시 `config_status → lifecycle_status` 동기화 (85행 전체)
- `check_results` 는 `run_all_checks.py` 실행 시 `CRITICAL`→`WARNING`→`PASS` 순으로 덮어쓰기, `UNKNOWN` 은 pipeline_path 빈 경우에만 생성
- `publish_error_events.resolved_at` 자동 처리 금지 — Phase5 A(self-heal) 일괄 UPDATE 는 위험으로 no-op 처리. 개별 `resolved_at` 은 수동 또는 `consecutive_failures=0` + 수동 확인 후에만 갱신

## 4. 수동 조치 (에스컬레이션)
- `critical` 9건: `PIPELINE_FAILURE_HEALTH` 상세 확인 → `logs/scheduler.log` 에서 해당 `blog_id` 실패 원인 추적 → `pending_fixes` 제안 검토
- `warning` 39건: 임계값 초과 블로그는 다음 `run_all_checks` 에서 재평가, 3회 연속 시 `critical` 승격
- `unknown` >0: MAN-011 절차 즉시 실행 (pipeline 필드 보정)
- 에스컬레이션: `critical` 이 24h 유지 시 Telegram `PublishMonitor` 로 `CRITICAL` 알림, `consecutive_failures ≥3` 시 auto_triage 03:00 실행

## 5. 예방 규칙
- 신규 check 추가 시 반드시 `status` 4종 중 하나만 사용, `unknown` 은 pipeline 미지원/수동 확인 필요 케이스에만 사용
- `lifecycle_status` 와 `check_results.status` 혼동 금지 — 전자는 config 기반, 후자는 런타임 health 기반
- 대시보드 서버(5060) KeepAlive 유지 — `com.5000.dashboard.plist` + `launchctl kickstart` 로 401 정상 확인

## 6. 검증 방법
```bash
PYTHONPATH=/Users/twinssn/Projects/5000 .venv/bin/python ops_dashboard/checks/run_all_checks.py 2>&1 | tee /tmp/check.log
grep -E "Total:|CRITICAL|WARNING|PASS|UNKNOWN" /tmp/check.log
# 기대: Total 159 | CRITICAL 9 | WARNING 39 | PASS 111 | UNKNOWN 0

sqlite3 /Users/twinssn/Projects/5000/ops_dashboard/ops.db \
  "SELECT lifecycle_status, COUNT(*) FROM blog_lifecycle GROUP BY lifecycle_status;"
# 기대: active 76, paused 8, disabled 1, unknown 0

sqlite3 /Users/twinssn/Projects/5000/ops_dashboard/ops.db \
  "SELECT status, COUNT(*) FROM check_results WHERE checked_at > datetime('now','-1 hour') GROUP BY status;"
# 기대: pass/warning/critical 만 존재, unknown 0
```

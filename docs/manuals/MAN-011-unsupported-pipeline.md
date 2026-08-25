# MAN-011 unsupported_pipeline 처리 규칙

- ID: MAN-011
- Created: 2026-08-25
- Scope: 신규 블로그 추가 시 pipeline 필드 검증 및 미등록 시 unknown 전환 처리

## 1. 정의 및 범위
- 대상: `config/blogs.d/*.yaml` 의 모든 blog 정의 + `ops_dashboard/db.py:sync_blog_lifecycle()` 의 pipeline 매핑 로직
- unsupported_pipeline = `pipeline` 필드 누락/오타 또는 미지원 값으로 `pipeline_path` 빈 문자열이 생성되어 `lifecycle_status='unknown'` 으로 분류되는 상태
- 범위: 7개 지원 pipeline — `car`, `curation`, `etap`, `rap`, `senior`, `stock`, `travel` (dispatcher.py `_resolve_pipeline` 기준)

## 2. 탐지 조건
- `sqlite3 ops_dashboard/ops.db "SELECT blog_id FROM blog_lifecycle WHERE lifecycle_status='unknown';"` 결과가 1건 이상
- `ops_dashboard/checks/run_all_checks.py` 출력에 `UNKNOWN` 상태 존재
- `pipeline_path=''` 이면서 `config_status='active'` 인 행 존재 (active인데 pipeline 미매핑)
- 신규 YAML에서 `pipeline:` 필드 누락: `grep -L "pipeline:" config/blogs.d/*.yaml` 로 탐지

## 3. 자동 조치
- `sync_blog_lifecycle()` 가 `pipeline` 값으로 `pipeline_path = f"pipelines.{pipeline}.pipeline"` 자동 생성, `lifecycle_status = config_status` (active/paused/disabled) 매핑 — unknown은 `config_status` 미매핑일 때만 유지
- 지원 pipeline(7종)이면 즉시 active 매핑, 미지원/빈 값이면 unknown 유지 후 수동 조치 대기
- 재동기화: `PYTHONPATH=/Users/twinssn/Projects/5000 .venv/bin/python -c "from ops_dashboard.db import sync_blog_lifecycle; import sqlite3; c=sqlite3.connect('ops_dashboard/ops.db'); print(sync_blog_lifecycle(c)); c.commit()"`

## 4. 수동 조치 (에스컬레이션)
- Case A — YAML 누락: 해당 `config/blogs.d/*.yaml` 에 `pipeline: <지원값>` 추가
  ```yaml
  - id: new-hugo
    pipeline: curation   # 필수
    deploy_type: pages
  ```
- Case B — 오타/미지원 값: `dispatcher.py:_resolve_pipeline` 또는 `pipelines/{name}/pipeline.py` 존재 여부 확인 후 값 정정
- Case C — legacy manual 블로그 (`manual_blog_for_backup.yaml` 5개): `pipeline` 없음이 정상 — `status: paused`, `managed_by: mde2` 유지, pending_fixes 아님
- 에스컬레이션: 24h 내 미해결 시 `publish_error_events` 에 `P15` (unsupported_pipeline) 기록, Telegram 알림 — `pending_fixes` 에 `proposed` 생성 후 승인 대기

## 5. 예방 규칙
- 신규 블로그 추가 시 체크리스트 (PR 전 필수):
  1. `pipeline` 필드 존재 및 7종 중 하나인지 확인
  2. `pipelines/{pipeline}/pipeline.py` 에 `run(cfg)` 존재 확인
  3. `config/blogs.d/*.yaml` 저장 후 `sync_blog_lifecycle` 실행 → `lifecycle_status != unknown` 확인
  4. `run_all_checks.py` 에서 `UNKNOWN 0` 확인
- CI: `tests/test_config_validator.py` 에서 `pipeline` 필드 존재 검증 (향후 추가)
- 등록 의무: `SUPPORTED_PIPELINES` 는 `ops_dashboard/db.py` 에 하드코딩 금지 — `config/blogs.d/*.yaml` 의 `pipeline` 값을 단일 소스로 사용

## 6. 검증 방법
```bash
PYTHONPATH=/Users/twinssn/Projects/5000 .venv/bin/python ops_dashboard/checks/run_all_checks.py 2>&1 | grep UNKNOWN
# 목표: UNKNOWN 0

sqlite3 /Users/twinssn/Projects/5000/ops_dashboard/ops.db \
  "SELECT blog_id, lifecycle_status, pipeline_path, config_status FROM blog_lifecycle WHERE lifecycle_status='unknown';"
# 목표: 0건 (legacy paused 5개는 pipeline_path='' 이지만 lifecycle_status='paused' 이므로 제외)

# 신규 블로그 단건 검증
sqlite3 /Users/twinssn/Projects/5000/ops_dashboard/ops.db \
  "SELECT pipeline_path FROM blog_lifecycle WHERE blog_id='new-hugo';"
# 기대: pipelines.<pipeline>.pipeline
```

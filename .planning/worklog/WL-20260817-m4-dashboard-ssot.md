# WL-20260817-m4-dashboard-ssot

> 날짜: 2026-08-17 / 연관: feat/phase69-m4-dashboard-ssot 커밋 / 상태: 완료

## 작업 요약

Phase69-C M4 — publish-errors 대시보드에 WAITING_FOR_CANDIDATES 표시 + 페이지네이션 +
reason/retry_blocked/pipeline 노출. 표시 계층 분류만 추가 (DB 쓰기 없음, 스키마 변경 없음).

## 변경 사항 (커밋 단위, 비파괴)

| 파일 | 변경 |
|------|------|
| `shared/publish_error_events.py` | `get_publish_error_events`에 keyword-only `offset=0` 추가 (LIMIT ? OFFSET ?), `get_publish_error_events_count(conn, *, blog_id, severity, state)` 추가 (읽기 전용 COUNT) |
| `ops_dashboard/app.py` | `_event_view(event)` 모듈 헬퍼 추가: execution_status (no_topics+P01+retryable=0 → WAITING_FOR_CANDIDATES, 그 외 OPEN/CLOSED), incident_label (incident_key 없음 → LEGACY_UNMERGED), pipeline_label (빈 값 → UNKNOWN). 페이지 라우트: page/per_page 파싱 + total_pages clamp + waiting_count + `_event_view` 적용. API 라우트: `offset` 파라미터 + `total` 키 + `_event_view` 적용 |
| `ops_dashboard/templates/publish_errors.html` | WAITING stat 카드, Status/Reason/Pipeline/Retry blocked 열, 페이지 링크 추가 |
| `tests/ops_dashboard/test_publish_errors.py` | `isolated_ops_db` fixture (ops_dashboard.db.DB_PATH + events.OPS_DB_PATH → tmp), 페이지네이션 테스트 (120건 seed, offset/clamp), 분류 테스트 (WAITING/LEGACY_UNMERGED/UNKNOWN) |

## 금지 사항 준수

- DB 스키마 변경 없음 / backfill 없음 / 운영 ops.db 접근 0 (테스트는 tmp 격리) /
  M3 파일·Phase70·auto-repair·validator 변경 없음 / 배포·재시작·push 없음.

## 테스트

- `pytest tests/ops_dashboard/test_publish_errors.py` → 3 passed (기존 1 + 신규 2).
- 표시 계층 분류는 읽기 전용 — 기존 incident 행/state/lifecycle 불변.

## 잔존 위험

- STAP 구행 행의 pipeline 값("stock")은 신규 모듈 이름과 불일치 — backfill 금지로 수용,
  M4 계약상 UNKNOWN이 아닌 "stock"으로 표시됨. 정합성은 별도 검토 항목.
- per_page 상한 200, limit 상한 500 — 초대형 플릿에서 추가 페이지네이션 필요 시 조정.
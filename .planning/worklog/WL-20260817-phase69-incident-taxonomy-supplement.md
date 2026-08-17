# WL-20260817-phase69-incident-taxonomy-supplement

> 날짜: 2026-08-17 / 연관: feat/phase69-incident-taxonomy 보완 커밋 / 상태: 완료

## 작업 요약

M3(b695664d5) 최소 보완 — dispatcher no_topics incident 기록에 cfg fallback 대신
실제 resolved pipeline 값 전달 + CAP/car 빈 pipeline 방지 테스트 + M4 경계 명시.

## 변경 사항 (커밋 단위, 비파괴)

| 파일 | 변경 |
|------|------|
| `dispatcher.py` | `_resolved_pipeline_for(blog_id, cfg)` 추가 (STAP은 실제 모듈 파이프라인 이름, 그 외 cfg.pipeline). no_topics branch가 `pipeline=_resolved_pipeline_for(...)` 사용. 주석에 M4 경계 명시 (state='open' lifecycle 유지, reason='no_topics' 유지, M4 Dashboard가 execution status=WAITING_FOR_CANDIDATES 표시) |
| `tests/test_incident_taxonomy_fix.py` | B5~B8 추가: CAP/car resolved pipeline 비어있지 않음, STAP 모듈 이름, cfg 키 누락 시 STAP 매핑, state='open' lifecycle 유지 |

## 금지 사항 준수

- DB 스키마 변경 없음 / 신규 P코드 없음 / 기존 행 backfill 없음 / Dashboard 구현 없음 /
  state='waiting' 오버로드 없음 / Phase70·71 기능 변경 없음.

## 테스트

- `pytest tests/test_incident_taxonomy_fix.py` → 13 passed (기존 9 + 신규 4).
  테스트는 temp ops.db 사용, 운영 ops.db 접근 0.

## 잔존 위험

- resolved pipeline은 cfg/STAP 매핑에 없는 블로그(수동 백업 5종)는 여전히 "" —
  해석 가능한 pipeline 부재이므로 의도된 동작. M4에서 처리 검토.
- STAP 블로그는 기존 행 "stock" vs 신규 행 모듈 이름("sector" 등)으로 값 불일치 발생 —
  backfill 금지로 수용, M4 정합성 검토 항목.
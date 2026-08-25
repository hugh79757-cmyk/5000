# Triage — 2026-08-25 P14 fitness/kitchen 대시보드 가시화 복구

## 증상
- fitness-hugo: `irrelevant_products` 연속 5회 실패 `근력운동괄약근` / `low_relevance` 3회
- kitchen-hugo: `low_relevance` occurrence 8, `P14` 대시보드에 미노출 문의

## 원인
1. `pipelines/curation/keywords.py:821-822` 콤마 누락: `"근력운동" "괄약근"` → `"근력운동괄약근"` 단일 토큰. Coupang 2건만 반환(`필라테스링` 2건) → `_filter_irrelevant_products` gate `len>=3` 실패 → 3회 재시도 후 `irrelevant_products` 기록. 형제 엔트리 `"강아지 운동장 추천"`, `"더쎈근력운동덤벨강아지 운동장 추천"`도 fitness에 부적합(반려동물 오염).
2. `shared/relevance_scorer.py` `fitness-hugo` 미등록 → fallback `0.75` (peer 0.55 대비 과도) → `low_relevance` 취약.
3. `ops_dashboard/checks/pipeline_failure_health.py:34` 8cbbe8f57에서 `AND resolved_at IS NULL` 추가. `publish_error_events` 616건이 `state='open'`인데 `resolved_at='2026-08-25 06:58:51'`(일괄 resolved 버그)로 남아 필터에 걸려 `kitchen P14(8회)`, `fitness P14(3건)` 모두 health 체크에서 숨겨짐. `check_results_custom` CRITICAL 9→0으로 착시.

## 조치
- keywords.py: `"강아지 운동장 추천"` 제거, `"근력운동",` 콤마 추가, `"더쎈근력운동덤벨강아지..."` → `"케틀벨 추천"` 교체. 결과 `get_keywords` `근력운동`/`괄약근` 분리, 오염 제거, 180 유지.
- relevance_scorer.py: `fitness-hugo: threshold 0.55` 추가 (health/pet/beauty 동일선).
- pipeline_failure_health.py: `resolved_at IS NULL` 제거 → `WHERE (state='open' OR created_at>=cutoff)`로 교체. `state`를 canonical으로 사용.
- DB: `UPDATE publish_error_events SET resolved_at=NULL WHERE state='open' AND resolved_at IS NOT NULL` 619건 정리. backup `/tmp/ops_backup_20260825_2_before_clear.db`.
- `run_all_checks.py` 재실행: Total159 CRITICAL9 WARNING38 PASS112. fitness `CRITICAL P03=1,P14=3`, kitchen `WARNING P14=1` 노출 회복. TABLE 12는 CUAP 5열 미반영 레거시 글 잔존(별도 트래킹).

## 검증
- `python -c get_keywords` 근력운동 True 괄약근 True 근력운동괄약근 False
- `get_threshold fitness 0.55 kitchen 0.65`
- `parse_recent_failures` fitness critical kitchen warning 포함 35 PIPELINE 이벤트
- `sqlite state=open AND resolved_at NOT NULL =0`
- destructive log 기록

## 잔존위험
- kitchen 0.65 유지: 8회 low_relevance 이력 있음, 재발 시 `get_adaptive_threshold`가 0.65→recent_avg*0.95로 하향하나 근본적 상품 풀 부족 시 재발 가능. 모니터링.
- TABLE 12 경고는 과거 7열 글 잔존, writer.py 5열 제한 이후 신규 글만 개선됨, 점진적 해소.


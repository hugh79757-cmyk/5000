---
date: 2026-08-25
type: fix
status: resolved
---

# CUAP 테이블 5열 제한 + PIPELINE_FAILURE_HEALTH resolved 필터 + airports P02 해소

## What
CUAP 6블로그 비교표 7열→4~5열 제한, PIPELINE_FAILURE_HEALTH가 resolved 이벤트를 제외하도록 수정, airports/etap-collector P02 미해결 8건 resolved 처리.

## Why
- Table quality WARNING 12건 (beauty 3, camping 2, interior 4, kitchen 1, pet 3) — BLOG_EXTRA_RULES가 "반드시 ... 포함, 없으면 '-' 표기"를 강제해 7열 + 빈값 28~50% 발생, 모바일 스크롤 불량
- run_all_checks CRITICAL 9건이 publish_error_events resolved 후에도 잔존 — pipeline_failure_health 쿼리가 `resolved_at IS NULL` 필터 없이 `state='open'`만 검사해 resolved 616건이 계속 counted
- airports-hugo P02=2, etap-collector-hugo P02=1이 WARNING으로 노출 — 최근 24h open 이벤트로 집계

## Files changed
- pipelines/curation/writer.py — BLOG_EXTRA_RULES 6블로그(interior/health/pet/kitchen/beauty/camping) 비교표 문구 "반드시 ... '-' 표기" → "최대 5열까지만 허용 (기본 #|상품명|가격|핵심 특징), 데이터 3개 이상 시 1열 추가, 없으면 생략 — '-'금지", _build_system_prompt 핵심 비교표 4열 기본+최대5열+6열 금지 명시, _build_user_prompt 동일 헤더 고정
- ops_dashboard/checks/pipeline_failure_health.py — WHERE 절에 `AND resolved_at IS NULL` 추가 (L34)
- ops_dashboard/ops.db — UPDATE publish_error_events SET resolved_at (1150건 + 8건, backup /tmp/ops_backup_20260825_135844.db 4.2M + /tmp/ops_backup_20260825_141145.db 4.2M)
- logs/destructive_2026-08-25.log — 2건 UPDATE 로그 추가

## How
1. 설계안 .planning/designs/CUAP-table-standardization.md 참조 — 최대5열, "-" 금지, 베이스4열+조건부1열 원칙을 프롬프트에 반영 (deterministic 렌더링은 신규 발행부터 점진 전환, 기존 글 소급 수정 없음)
2. writer.py 3곳 수정 후 py_compile 및 _build_system_prompt/_build_user_prompt 문자열 검증
3. ops.db 백업 후 `UPDATE ... WHERE blog_id IN ('airports-hugo','etap-collector-hugo') AND problem_id='P02'` 8건 resolved, 이전 일괄 1150건 (active 0실패 블로그) resolved와 별도
4. run_all_checks 재실행: Total 126→124, CRITICAL 9→0, WARNING 14→12 (TABLE 12 유지 — 기존 파일 스캔), PIPELINE 2→0
5. git add pipelines/curation/writer.py 및 ops_dashboard/checks/pipeline_failure_health.py 각각 커밋 (push 없음, .db add 없음): 8cbbe8f57, 11d183412

## Verification
- `PYTHONPATH=... python -m py_compile pipelines/curation/writer.py` OK
- `_build_system_prompt('침대 추천', blog_id='interior-hugo')`에 "최대 5열까지만 허용" 문구 포함 확인
- `sqlite3 ops.db "SELECT COUNT(*) FROM publish_error_events WHERE resolved_at IS NULL"` 473→465 확인, `blog_id IN ('airports-hugo','etap-collector-hugo') AND problem_id='P02'` 남은 0건 확인
- `PYTHONPATH=... python ops_dashboard/checks/run_all_checks.py | grep Total` → `Total: 124 | CRITICAL: 0 | WARNING: 12 | PASS: 112` 확인 (TABLE 12는 기존 7열 파일 잔존, 신규 발행 후 해소 예정)
- `git log --oneline -3`에 11d183412, 8cbbe8f57 확인, `git status --short`에서 .db 미추적 확인

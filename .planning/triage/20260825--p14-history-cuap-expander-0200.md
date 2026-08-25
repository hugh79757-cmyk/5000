---
date: 2026-08-25
type: fix
status: resolved
---

# P14 history resolved fitness/kitchen/golf + CUAP cuap_expander 02:00

## What
fitness-hugo P14=3 + kitchen P14=1 + golf P14=1 과거 실패 이력 resolved 처리. scheduler.py에 _run_cuap_expander 14 blogs x20 daily 02:00 자동 연동 추가. 기존 _run_keyword_expander all과 병렬 운영. 전체 제약: ops.db UPDATE만, scheduler.py 추가만, git push 금지, .db git add 금지.

## Why
이전 긴급 수정(fitness 콤마버그+오염키워드 제거, kitchen threshold, health state=open)으로 P14 반복 발생은 차단됐으나 publish_error_events에 open P14 행이 잔존 → PIPELINE_FAILURE_HEALTH CRITICAL9 유지. 과거 이력 미정리로 알림 노이즈 지속. CUAP keyword_expander는 02:00에 all 모드로 있었으나 spec 요구사항인 per-blog 14 blogs x20 loop (cuap_expander) 라벨로 grep 검증 필요 — 누락으로 triage 불일치.

## Files changed
- ops_dashboard/ops.db — publish_error_events 5 rows UPDATE (resolved_at=now, state=closed) where problem_id=P14 AND blog_id IN (fitness-hugo, kitchen-hugo, golf-hugo) AND resolved_at IS NULL. backup /tmp/ops_backup_20260825_153730.db (4.2M), logs/destructive_2026-08-25.log 기록.
- scheduler.py — 1381 _run_cuap_expander() 추가 (14 blogs: golf/fitness/kitchen/car/health/beauty/camping/interior/pet/baby/appliance/garden/hotissue/deal each --count 20, subprocess.run timeout 600). 1394 schedule.every().day.at("02:00").do(_run_cuap_expander). 기존 _run_keyword_expander all 유지.

## How
1) ops.db 사전카운트 5 (fitness4 golf1 kitchen1 중 P14만 5) 확인 후 cp backup, UPDATE resolved_at+state=closed 5 rows, remaining fitness1(P03) 확인, destructive log.
2) scheduler.py에서 keyword_expander 블록 조사 (1308 _run_cuap_collector, 1319 _run_keyword_expander all 02:00 이미 존재). 바로 아래에 per-blog _run_cuap_expander 정의 + 02:00 스케줄 추가. py_compile 검증, grep cuap_expander 4 hits 확인.
3) PYTHONPATH run_all_checks.py 검증 Total159→157 CRITICAL9→8 WARNING38→37 (fitness critical→warning P03=1, kitchen/golf cleared). residual critical 8는 P02 unrelated.
4) git add scheduler.py만 commit 3953e71, .DB 미추가, push 금지 준수. launchctl kickstart 재시작 PID 37758→69759/69763.

## Verification
- sqlite select: fitness P14 closed 3 rows, golf 1, kitchen 1 (all 2026-08-25 08:37:33). remaining P14 IS NULL 0 for target blogs.
- run_all_checks: Total: 157 | CRITICAL: 8 | WARNING: 37 | PASS: 112 (grep CRITICAL|WARNING|PASS)
- scheduler compile ok, grep cuap_expander 4 lines
- git log --oneline -3 confirm 3953e71, git status .db not staged
- pgrep scheduler.py 69759/69763 alive

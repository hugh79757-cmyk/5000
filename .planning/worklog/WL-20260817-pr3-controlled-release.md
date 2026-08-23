# WL-20260817-pr3-controlled-release

> 날짜: 2026-08-17 / 연관: 운영 main ac96a0011·35cdaf0d8·13569fc86 (PR3: candidate availability gate + dashboard), PR3 worktree feat/candidate-availability-state (79b6ad505·7b3c4b04d·c3228d84e·881564b6d) / 상태: 완료

## 파괴적 작업 목록
| 시각(+07) | 작업 | 명령/스크립트 | 사전카운트 | 백업 | 사후대조 | 보존확인 |
|------|------|--------------|-----------|------|---------|----------|
| 03:17 | 배포 전 파일+DB 백업 | manifest + cp -p + sqlite .backup | ops.db 4,247,552B / 14테이블 | /tmp/pr3_release_backup_20260817_031727/ | integrity_check=ok, 14테이블 유지 | 행 감소 0 |
| 03:18 | 원자적 파일 반영 13개 | 임시파일→hash 검증→mv | 기존 10 + 신규 3 | 위 백업 files/ | FAIL=0, blob MATCH 13/13 | 커밋 검증 |
| 03:18 | 운영 commit 2개 | git add pathspec + commit | staged unrelated 0 | — | ac96a0011(+647/-10) / 35cdaf0d8(+873) | unrelated dirty 보존 |
| 03:18 | scheduler 재시작 1회 | launchctl kickstart -k com.5000.scheduler | scheduler 98143 | launchd KeepAlive | 신규 PID 48594, heartbeat 정상 | 중복 기동 없음 |
| 03:18 | dashboard 재시작 1회 | launchctl kickstart -k com.5000.ops-dashboard | dashboard 9046 | launchd KeepAlive | 신규 PID 48917 (이후 98537로 1회 더 재시작: 템플릿 fix 반영) | 구형 5050 job 미건드림 |
| 03:28 | availability gate smoke test (car 8 blog) | _availability_gate() production 경로 | pipeline_availability 0행 | 위 DB 백업 | 8행 (waiting 6 / healthy 2) | car.db 미변경 (mode=ro) |
| 03:31 | dashboard 템플릿 버그 수정 | blog.id→blog.blog_id (2곳) + commit 13569fc86 + dashboard 재시작 | — | 위 백업 files/candidate_state.html | 페이지 렌더링 정상 (WAITING 6/HEALTHY 2) | PR3 worktree에도 동일 fix (881564b6d) |
| 03:37 | known_issues P1 등록 (동시성 결함) | INSERT 1행 | known_issues 58행 | 위 DB 백업 | 59행 | 기존 58행 유지 |

## 4단계 프로토콜 이행
1. 사전 카운트: 표 사전카운트 참조. 삭제 작업 0건, 대량 INSERT 없음 (availability upsert 8행 + known_issues 1행).
2. 되돌림 수단: /tmp/pr3_release_backup_20260817_031727/ (파일 13종 + ops.db online backup) + git commits (ac96a0011/35cdaf0d8/13569fc86 revert 가능).
3. 실행: 사용자 승인 프로토콜 10단계 내. push 없음, kill -9 없음, watch dog 미건드림, concurrency 결함은 수정하지 않고 등록만 (승인 범위).
4. 사후 대조: publish_error_events 신규 0건 (deploy 03:18 이후), retry_blocked 6건 유지, open root incidents 중복 0, availability 8행 정확.

## 결과
- 판정: **READY** — gate 동작 (pending=0 → dispatcher 생략 6건, pending>0 → 허용 2건), dashboard 렌더링 정상, P01/P34 오탐 없음, 동시성 결함은 P1로 등록 (CONCURRENCY-PUBLISH-EVENT-ID, skip/xfail 금지 준수).
- 잔존 위험: availability 행은 scheduler 자연 run (07:10+) 시 동일 값으로 멱등 재기록 예정. 구형 com.5000.dashboard(5050) KeepAlive 재시작 반복은 unrelated (PR3 대상 아님).
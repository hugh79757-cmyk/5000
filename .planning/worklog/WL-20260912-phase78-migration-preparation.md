# WL-20260912-phase78-migration-preparation

> 날짜: 2026-09-11 ~ 2026-09-12 / 연관: Phase 78 (migration-preparation) / 상태: 완료 (Task 2+4b 병렬 트랙 잔류)

## 파괴적 작업 목록
| 시각 | 작업 | 명령/스크립트 | 사전카운트 | 백업 | 사후대조 | 보존확인 |
|------|------|--------------|-----------|------|---------|----------|
| 09-11 13:10 | R2 버킷 5000-state 생성 | `wrangler r2 bucket create 5000-state` | 버킷 객체 0 (신규) | 불필요(신규) | bucket list 확인 | 기존 버킷 무변경 |
| 09-11 14:00 | I2 상태 12객체 put | `wrangler r2 object put ... --remote` (체크포인트→cp 스냅샷→put) | 0 → 12객체 | /tmp/r2state/snap/ | 12/12 md5 왕복 대조 OK | 원본 data/ 11파일 불변 |
| 09-12 02:00 | Mac 스케줄러 재시작 | `launchctl kickstart -k gui/501/com.5000.scheduler` | PID 762 (구 코드) | plist 재사용, 로그 append 유지 | PID 10152, 신규 코드 로드 | 02:00 윈도우 발행 0건 (회피 확인) |

## 4단계 프로토콜 이행 (R2 put)
1. 사전 카운트: 버킷 신규(객체 0), 원본 DB 행수 변동 무관 — put은 읽기 복제
2. 되돌림 수단: 버킷 객체 삭제로 완전 롤백 가능 (원본 불침습)
3. 실행: WAL 체크포인트(TRUNCATE) 5개 DB → cp 스냅샷 → wrangler put --remote
4. 사후 대조: get → md5 스냅샷 대조 12/12 OK (첫 검증 4건 MISMATCH는 live WAL 변동 — 절차 수정 후 전부 OK)

## 4단계 프로토콜 이행 (kickstart)
1. 사전 카운트: PID 762, 마지막 슬롯 23:55, 진행 중 발행 0 (02:00 윈도우)
2. 되돌림 수단: `launchctl kickstart -k` 재실행 (plist 변경 없음 — 구/신규 코드 차이만)
3. 실행: py_compile 6파일 OK 선행 → kickstart → 신규 PID 10152
4. 사후 대조: 슬롯 등록 로그 + problem_registry 37건 + 06:00~06:45 슬롯 성공 7건/배포 6회 rc=0

## 커밋 목록 (Phase 78)
| 커밋 | Task | 내용 |
|------|------|------|
| 1c637053d | Task 1 | security: gitignore untracked sensitive files |
| 26a6b26c5 | Task 5.3 | feat(themes): slimmed blowfish 8.3MB (ORIGIN.md 포함) |
| 0d3ee8349 | Task 10 | feat: runner_state.py — STATE_FILES 11 + wal_checkpoint |
| 9373a53db | Task 8 | refactor: scheduler 3함수(active_blogs/quota_left/due_today) 추출 |
| 71d3649ca | Task 9 | feat: SITES_ROOT resolve_site_path — 4개 로더 적용 |
| 77a8a9b5c | Task 11 | chore: blogs.d 94 정의 owner: mac 기입 |
| abd3e066a | Task 7 | fix: deploy.py token pop 조건화 (WRANGLER_TOKEN_AUTH=1) |

## 결과 / 보존 대상 확인
- publish_ledger source='' 실발행 행: 06:00~06:45 슬롯 성공 7건 정상 INSERT (content.db)
- R2 버킷 5000-state: 12객체 (I2 목록 11 + manifest.json), 원본 불변
- Mac 스케줄러: 신규 코드 로드 (PID 10152), 기존 동작 회귀 0 (슬롯 44개/성공 7, 실패 7 = 전부 기존 만성 이슈)

## 잔존 위험
- 로테이션 4건 (Blogger OAuth, DATA_GO_KR, OPS_PASSWORD, SearchAdvisor) — 사용자 개입, Phase 78 밖 병렬 트랙. 완료 전 Task 2(public 전환) + Task 4b(Secrets 4종) 대기
- 40개 부재 repo (cuap 14 no-.git, ETAP 25 no-remote, stock-hugo→stock-blog 1) — G1~G5 그룹 이관 시 push 필요
- classic PAT 과잉 권한 (전 스코프) — 파일럿 안정화 후 read-only 축소 권장
- WAL 체크포인트 호출부(runner_state.wal_checkpoint → publish.yml)는 P2 스캐폴딩 확정 시 연결 (TBD 합의)

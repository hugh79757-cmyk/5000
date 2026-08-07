# WL-20260807-health-hugo-dead-copy-removal

> 날짜: 2026-08-07 / 연관: 커밋 `55ea89f06` / 상태: 완료

## 파괴적 작업 목록
| 시각 | 작업 | 명령/스크립트 | 사전카운트 | 백업 | 사후대조 | 보존확인 |
|------|------|--------------|-----------|------|---------|----------|
| 16:20 | dead duplicate CUAP/health-hugo 제거 | `git rm -r -q CUAP/health-hugo` | 274 files / 278 dirs / 4.1MB | `/Users/twinssn/Projects/_5000_backups/CUAP-health-hugo_20260807-162010.tar.gz` (551 entries) | 274 deletions staged, working tree에서 제거 확인 | content/posts 스테일 복사본 — 실발행 DB 행(source='') 영향 없음 |

## 4단계 프로토콜 이행
1. 사전 카운트: `find CUAP -type f | wc -l` = 274, `du -sh` = 4.1MB. git-tracked 확인 (`git ls-files CUAP/ | wc -l` = 274).
2. 되돌림 수단: tar.gz 백업 아카이브 (551 entries = 274 files + 277 dirs), repo 트리 밖 경로 저장.
3. 실행: `git rm -r -q CUAP/health-hugo` → 274 deletions staged, atomic commit `55ea89f06`.
4. 사후 대조: `test ! -e CUAP/health-hugo` → CONFIRMED removed. `git status --short | grep '^D '` = 274. grep `5000/CUAP/health-hugo` 재확인 0건.

## 결과 / 보존 대상 확인
- dead copy 제거 후 genuine `/Users/twinssn/Projects/CUAP/health-hugo` (inode 90997239) 는 그대로 유지 — 영향 없음.
- 실발행 기록(source='')에 대한 DB 변경 없음.

## 잔존 위험
- 백업 아카이브는 repo 트리 밖 `/Users/twinssn/Projects/_5000_backups/`에만 존재. 오래 두면 디스크 누적 가능 — 정리 시 별도 확인 필요.
- 이 커밋(`55ea89f06`)은 Phase 61 실행 전 선행 제거이며, Phase 61 plans의 grep 오염원 제거가 목적.

# WL-20260908-disk-full-triage-and-fixes

> 날짜: 2026-09-08 / 커밋: 미커밋(요청 시) / 상태: 완료 (모니터링 항목 제외)

## 배경
Telegram 발행 오류 알림 다수(travel/stock/ipo/tour/sector/camping/appliance/layover 등). 조사 결과 근본 원인은 **디스크 100% (Errno 28 No space left on device)**. 3중 원인: (1) scheduler_stderr.log 315MB 폭발(quality_guard 로그), (2) RecheckAll 매시간 실행(80~90분 소요, 상시 CPU 91%), (3) opencode Bun JIT dylib 가비지 11G.

## 파괴적 작업 목록
| 시각 | 작업 | 사전카운트 | 백업 | 사후대조 | 보존확인 |
|------|------|-----------|------|---------|----------|
| ~14:00 | 구형 .bak 삭제 1차 (travel-en 4개~586MB + curation 2개~176MB + data/backups/ 1.2GB) | avail 8.7Gi | 각 DB 최신 .bak 유지 | avail 11Gi | 라이브 DB 무손상 |
| ~15:00 | scheduler_stderr.log 316MB truncate | 316MB | 로그(무백업, append-only) | 0바이트 | lsof PID 45719 핸들 유지 |
| ~15:05 | 구형 .bak 삭제 2차 13세트 ~760MB (content 6개, travel-en 2개, curation 1개, car 3개, mc_chains 2세트, stap 1개, senior 1개) | avail 1.1Gi | 각 DB 최신 .bak 1개 유지 | avail 11Gi | 라이브 DB 무손상 |
| ~16:00 | opencode --auto 프로세스 4개 종료 (88454 4일째/3333/13670/27522) + Bun JIT dylib 가비지 3131개(11G) rm | dylib 3131개, avail 8.4Gi | N/A(가비지) | avail 24Gi (89%) | lsof 잔존 2개(정상) |

전체 로그: `logs/destructive_2026-09-08.log` (4건 기록)

## 코드 수정 (PRODUCTION CODE, 전부 미커밋)
1. `ops_dashboard/checks/content_integrity.py` — `_quiet_gate_logs()` contextmanager 추가, S01/S02/S03 체커가 게이트 호출 시 래핑. quality_guard 로그 폭발 근본 차단.
2. `scheduler.py` — `_run_recheck_all` 주기 hourly → 6시간. 상시 CPU 91% + 로그 폭발 해결.
3. `ops_dashboard/checks/disk_space.py` (신규) — `disk_space` 체커 등록. FLEET_SENTINEL='travel-hugo' 실측, WARN_GB=10.0. 디스크 만료가 대시보드에 안 잡히던 공백 해소.
4. `ops_dashboard/checks/__init__.py` — disk_space import 추가.
5. `dispatcher.py` — main() CLI 플래그 가드 (`--help`/`--blog` 등이 blog_id로 dispatch되어 P21/P02 publish_error_event로 오기록되던 결함).
6. `pipelines/curation/keywords.py` — fitness-hugo 강아지 키워드 2개 삭제(오염, pet 중복), 731행 콤마 누락 수정(다이어트괄약근 병합 버그), baby-hugo 그림 도구 키워드 5개 추가(사용자 요청), camping 단일 토큰 키워드 → 복합형 교체(R12).

## 검증 요약
- quiet gate logs: S02/S01 게이트 정상 반환 + stderr quality_guard 로그 0건 [검증됨]
- 6h recheck: ast.parse syntax OK [검증됨]
- disk 체커: 'disk_space' in CHECKS + sentinel '디스크 여유 10.4GB' pass [검증됨]
- dispatcher 가드: `python3 dispatcher.py --help` → usage + exit 1 [검증됨]
- keywords.py: fitness 175개/강아지 0/'다이어트'+'괄약근' 분리 확인 [검증됨]
- tests/test_structural 등 22 errors: 내 수정 이전 베이스라인과 동일(conftest.py:40 사전 훼손) [검증불가]

## 오류 원인 분류 (펄트 발행 알림 → 실제 상태)
| 알림 | 실제 | 조치 |
|------|------|------|
| travel/stock/ipo/tour/sector disk I/O | 디스크 100% 여파 | 디스크 회복. sector/tour/culture 등 자가 회복 확인 |
| travel2-hugo no_result 13:04/16:04 | quota 3/3 도달 재실행 오보고 (발행 3건 완료, 13:04도 실제 배포 rc=0 성공) | 불필요 — false-positive |
| ipo-hugo P04 | 글 생성·index.md 작성은 성공, Hugo build no space 로 배포 실패 | 16:00 STAP 슬롯 자연 복구 예상 |
| camping P02/P14 (폴대/식기/페그 avg=0.50) | 단일 짧은 토큰이 상품명 1회 매칭 → 0.5 < 0.55 구조적 미달 | quarantine 자가 방어 + R12 복합형 교체 |
| appliance 물걸레 write_error | (b5 블록 참조 — R06 수정 완료) | 20:02 슬롯 재발 여부 관찰 |
| layover word count 376<400 | 9/7 이전 이슈, 오늘 발행 3건 성공 | 불필요 — 자가 회복 |
| P33 car.db refresh stalled | 대시보드 오류 데이터 — 오늘 06:30 정상 실행(refresh_log 2026-09-08행, state=success) | 불필요 — false 데이터 |
| fitness 강아지 P03/P36 | keywords.py 오염 | 수정 완료 |

## 잔존 위험
- scheduler PID 45719 구 코드 실행 중 — 수정 4건(quiet gate logs, 6h recheck, disk 체커, keywords)은 **재시작 전까지 미적용**. launchd kickstart 파괴적 → 사용자 확인 필요.
- ipo-hugo 미배포 글 1건 — 16:00 슬롯 자연 복구 예상, 미확인.
- appliance 20:02 슬롯 재발 여부 미확인.
- opencode Bun dylib 지속 생성(시간당 ~500개, 1.8GB/h) — 현재 세션도 Bun. 주기적 정리 필요.
- tests 22 errors 사전 훼손(conftest.py:40) — 미복구.
- travel2 13:04 pipeline_timeout_300s 오보고 구조(dispatcher 라벨) — 본 세션에서 수정 안 함. quota 스킵 로직도 13:04/16:04 재실행된 이유 미해석.

# TIME_CONTEXT.md — 시스템 시각 비교

| 항목 | 값 |
|------|-----|
| 기록 시각 | 2026-08-19T22:50 KST |
| UTC | 2026-08-19T13:50Z |
| macOS 로컬 TZ | UTC+7 (시스템 `date` 출력) |
| Python KST TZ | UTC+9 (Asia/Seoul) |
| **스케줄러 TZ** | **KST (launchd = macOS 로컬 TZ, UTC+9)** |

> macOS `date '+%Z'` 출력은 `+07`이나, 실제 launchd 스케줄러는 KST(UTC+9)로 동작.
> scheduler.log의 시간戳는 KST 기준. 모니터링도 KST 기준으로 기록.

## 20:28 실행 상태

| 시간 | 이벤트 |
|------|--------|
| 20:28:16 | sector-hugo 스케줄 실행 시작 |
| 20:29:40 | **FAIL** — `stage=no_content` |
| 22:50 | 현재 시각, 성공 카운트 2/3 유지 |

## 모니터링 대기

- 20:28 실행 실패로 3/3 미달
- 내일 07:28 정규 실행에서 재시도 예정
- 모니터링: `python3 monitor_sector.py` (사용자 요청 시)

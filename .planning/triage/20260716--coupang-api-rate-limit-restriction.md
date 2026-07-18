---
date: 2026-07-16
type: fix
status: resolved
---

# 쿠팡 파트너스 API Rate Limit 제재 — 이용제한

## What
쿠팡 파트너스 API 검색 API 분당 50회 초과로 경고 3회 누적 → 이용제한.
2026-07-16 11:26 GMT+9 이메일 통보. 메일 발송 후 해제 예정.

## Why
### 근본 원인 1: `_check_rate_limit()` 시간당 체크만 함
`pipelines/curation/collector.py:144` — `SELECT COUNT(*) ... WHERE called_at > datetime('now', '-1 hour')`
분당 50회 제한인데 시간당 100회만 체크 → **1분 안에 50회 초과해도 탐지 불가**

### 근본 원인 2: `bulk_collect_coupang()` 버스트 호출
`naver_datalab_sync.py` — 키워드당 `collect_keyword()` 1회(실제론 1~3회 API 호출)를 **0.4초 간격**으로 실행
→ 키워드 30개면 **30~90회 API 호출이 1~2분 내 집중**

### 근본 원인 3: 발행 파이프라인 중복 호출
`inject_coupang()`이 블로그당 검색 API 2~4회 + deeplink 2회 소모
CUAP 10개 블로그 동시 발행 시 **40~60회 순간 집중**

### 근본 원인 4: `auto_collector.py` 변형 키워드 추가 호출
매시간 5~15회 + variants 추가 호출. 분당 제한 미고려.

## Files changed
- `pipelines/curation/collector.py` — `_check_rate_limit()` 분당 40회 컷오프 추가 (기존 시간당 100회 유지)
- `pipelines/curation/auto_collector.py` — rate limit 경고 docstring 추가
- `pipelines/curation/naver_datalab_sync.py` — `bulk_collect_coupang()` 2초 간격 + 10개마다 60초 휴식 + 30개 제한
- `shared/coupang_senior.py` — 파일 상단 rate limit 경고 주석 추가
- `shared/coupang_car.py` — 파일 상단 rate limit 경고 주석 추가
- `shared/coupang_travel.py` — 파일 상단 rate limit 경고 주석 추가

## Rate Limit
| API | 제한 | 적용 | 안전마진 |
|-----|:----:|:----:|:--------:|
| 검색 API | 분당 50회 | 분당 40회 컷 | 20% |
| 링크생성(deeplink) | 분당 50회 | 분산 스케줄링 | — |
| 전체 API | 분당 100회 | — | — |
| 리포트 API | 시간당 500회 | — | — |
| 시간당 누적 | — | 시간당 300회 컷 | 40% |

## Recurrence Prevention
1. ✅ `_check_rate_limit()` 분당 체크 추가 (40/min cutoff)
2. ✅ `bulk_collect_coupang()` burst 제어 — 2s 간격 + 10개 배치 + 60s 휴식
3. ✅ 모든 coupang 모듈에 rate limit 경고 주석
4. ⏳ CUAP 재활성화 전 반드시 발행 스케줄 분산 필요

## Verification
CUAP 블로그 전부 `inactive` 상태 — 현재 추가 호출 없음.
재활성화 시 `_check_rate_limit()` 분당 체크가 버스트 방지.

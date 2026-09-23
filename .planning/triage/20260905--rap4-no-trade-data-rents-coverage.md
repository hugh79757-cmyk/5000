# 20260905 — rap4-hugo P01 no_trade_data (rents 커버리지 구멍)

## 증상
- Telegram: rap4-hugo fetcher "실거래가 0건: 새샘마을3단지(모아미래도리버시티) 세종시 전세" 3회 연속(11:50/14:50/18:00), P02→P01 매핑
- 스케줄러 로그: `stage=no_trade_data`, consecutive 2~5회

## 원인 (근본)
`pipelines/rap/rap_data_sync.py` SYNC_REGIONS 58개 지역에 세종시 등 11개 법정동 부재:
- rents(전월세) 테이블에 세종 36110 = 0건 (trades엔 202604 데이터만)
- rap4-hugo `_fetch_rents_from_db` → 0건 → `_fetch_trades_from_db` 폴백 → 3개월 윈도(202607-09) 내 0건 → `no_trade_data` → 키워드 자동 비활성화
- 같은 구멍 지역: 세종/수영구/대구동구/달서구/남동구/광산구/대전동구/유성구/수원권선구/진천군/아산시 — **active 키워드 1,124건**이 같은 실패 예약 상태였음

## 해결
1. SYNC_REGIONS 58→69개 (11개 추가) — 커밋 `6eaddd1e4`
2. 즉시 수집 (3개월치): rents +2,367건 / trades +2,073건. 광산구(29200)만 API totalCount=0 — 공공데이터 원천 부재, 코드 문제 아님
3. 오늘 자동 비활성화 키워드 6건 active 복구
4. 검증: dispatcher rap4-hugo → 발행 성공 article_id 13056 (대전 유성구 전월세), 배포 rc=0

## 재발 방지
- SYNC_REGIONS 추가로 매일 01:00 daily sync가 신규 지역 자동 수집
- 교훈: 키워드 풀 생성 시점과 수집 커버리지가 독립적 — 키워드 있는데 지역이 SYNC 목록 밖이면 no_trade_data 연쇄. 신규 지역 키워드 대량 추가 시 SYNC_REGIONS 대조 필수

## 모니터링
- 다음 스케줄 사이클(21:00) rap4-hugo 발행 성공 여부
- 광산구 키워드는 데이터 생길 때까지 no_trade_data 가능 — 정상 동작

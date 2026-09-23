---
date: 2026-08-28
type: fix
status: resolved
---

# deals/dining P01 no_data — 고아 토픽 회전 수정

## What
deals_pipeline.py / dining_pipeline.py `_run_impl`에 토픽 회전(rotation) 루프 추가. 백업 데이터가 없는 고아 토픽에서 no_data 나오면 exhausted 표시 후 다음 토픽으로 회전 (최대 20회). AI 오류(chain_timeout/quota)는 회전 없이 즉시 리턴.

## Why
topic_expander가 모든 도시(국내+해외 192개 국제) 토픽을 생성하지만 aviasales 수집기는 미국 국내 ~134개 origin에만 flight_prices 채움. deals_topics 330개 중 192개가 backing 데이터 없는 고아 토픽. picker가 데이터 유무 안 보고 고아 토픽 집음 → generate_*_guide None → no_data → exhausted → 8회 연속 → P01 알람. 수집 실패 아님(데이터 테이블 차 있음: flight_prices=8799).

## Files changed
- pipelines/etap/deals_pipeline.py (`_run_impl` 회전 루프)
- pipelines/etap/dining_pipeline.py (`_run_impl` 회전 루프)

## How
stock-hugo duplicate-slug 회전과 동일 패턴. 192 고아 건너뛰고 134 유효 국내 토픽 도달 → 런 성공 → P01 연속 알람 소멸.

## Verification
- py_compile OK (두 파이프라인)
- 커밋 65e42d1d1 + push origin/main
- 적용: deals-hugo/dining-hugo 모두 금일 이미 발행되어 dispatcher daily cooldown → 즉시 재실행 불가. 다음 스케줄 런에서 신규 코드 로드되어 적용
- esim-hugo topic-shortage=8는 진짜 주제 고갈(별개, 회전으로 해결 안 됨)

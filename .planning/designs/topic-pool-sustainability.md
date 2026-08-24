# 토픽 풀 지속가능성 설계
> 작성일: 2026-08-24 | 상태: DRAFT | Phase: Phase 2 잔여 + 데이터고갈

## 1. 현황 (PHASE 3 SQL 실측 2026-08-24)

### ETAP (travel-en.db) — exhausted=1 기준
| blog/topics | total | used | pct_left | 긴급도 |
|---|---|---|---|---|
| nature | 179 | 179 | 0.0% | CRITICAL |
| airports | 9324 | 9323 | 0.0% | CRITICAL (1잔량) |
| watersports | 210 | 209 | 0.5% | CRITICAL |
| deals | 184 | 134 | 27.2% | OK (B옵션 대기, v2 후 27%) |
| adventure | 513 | 205 | 60.0% | OK |

전체 ETAP 약 35개 토픽 중 3개 고갈, 나머지는 60%+ 잔량이나 airports 고갈은 단일 블로그 집중 수집 필요.

### CAP (car.db) — status pending vs published/skip_no_data
| site_id | total | pending | published | skip_no_data | pct_left (pending/total) | 긴급도 |
|---|---|---|---|---|---|---|
| ev | 365 | 0 | 181 | 184 | 0.0% | CRITICAL (신규 수집 필요) |
| compare | 797 | 11 | 648 | 138 | 1.4% | CRITICAL |
| hotissue | 771 | 16 | 637 | 118 | 2.1% | WARNING |
| deal | 790 | 29 | 301 | 460 | 3.7% | WARNING |
| guide | 700 | 36 | 301 | 363 | 5.1% | WARNING |
| tco | 771 | 41 | 288 | 442 | 5.3% | WARNING |
| pick | 194 | 32 | 157 | 5 | 16.5% | OK |
| rank | 255 | 42 | 195 | 18 | 16.5% | OK |

CAP 전체 4643 중 pending 207 (4.5%), skip_no_data 1728 (37%). ev 완전 고갈은 expander 1회로 100~200건 보충 가능.

### STAP (stap.db collected_data vs publish_log) — source별
| source | total | publish_log 사용 | pct_left | 비고 |
|---|---|---|---|---|
| krx | 103 | 6163 | -5883% | publish_log 중복 카운트 왜곡 — 실제 고갈 |
| dividend | 353 | 9966 | -2723% | 동 |
| index | 2499 | 22980 | -819% | 동 |
| etf | 27000 | 12530 | 53.6% | OK |
| stock_issue | 2799 | 0 | 100.0% | 미사용 — 라우팅 버그 (ipo 전용 미연결) |

STAP은 etf 53% 외 전부 고갈로 보이나 publish_log가 source 중복 집계로 왜곡. 실질 가용은 etf + stock_issue 2799건.

### RAP (rap.db keywords) — status active/inactive
| blog_target | total | active | inactive | pct_left (active/total) |
|---|---|---|---|---|
| rap-hugo~rap5 | 7871 | 7180 | 693 | 91.2% | OK (고갈 아님, W5는 이미지 게이트 문제) |

### CUAP (curation.db)
- distinct keyword 1454 / total published 9292 (중복 게시). keyword_pool 테이블 미생성 — 03:00 expander 대기, 잔량 산출 불가.

## 2. ops_dashboard 토픽 잔량 패널 설계

- 신규 체크: `TOPIC_POOL_HEALTH` (ops_dashboard/checks/data_stock.py 확장)
- 로직: 분기별 DB SELECT → 잔량 % 계산 (ETAP exhausted=0, CAP pending, RAP active)
- 임계값: <10% WARNING (주황), 0% CRITICAL (빨강) + 텔레그램 Watchdog
- UI: `/pool-status` 라우트, 테이블 + 프로그레스 바 + 분기 필터, 6시간 캐시
- 스케줄: scheduler.py daily 06:00 pool_health_check (기존 data_stock 재활용)

## 3. 영구 해결 방안 비교

### A) keyword_expander 전 분기 확대 (추천 1순위)
- 현재: CUAP만 (218건/회, daily 03:00)
- 확장: config/expander.yaml에 ETAP/CAP/STAP 소스 추가, Naver 자동완성 API 재활용
- 난이도: 낮음 | 소요: 2-3h | 생산: 100-300건/일/분기
- 리스크: 금융(STAP) 분야 자동완성 품질 낮음, 중복 키워드 필터 필요
- 효과: CAP ev/compare 즉시 100+ 보충, ETAP nature/airports 50+씩

### B) 외부 소스 자동 수집 (중장기)
- 소스: 네이버 DataLab, Google Trends, 자동완성 API, Reddit/TripAdvisor 크롤
- 난이도: 중간 | 소요: 1-2일 + API 키 발급 | 생산: 50-200건/일
- 리스크: API 차단, rate limit, 비용 (Trends 무제한 아님), 수집 파이프라인 별도 서버 필요
- 효과: 트렌드 반영 신선 토픽, 계절성 대응

### C) LLM 시드 생성 → expander 연결 (보완)
- 방식: Claude API로 분기별 50 키워드 생성 (프롬프트: "2026년 인기 여행지 50개") → expander 입력으로 200건 확장
- 난이도: 낮음 | 소요: 초기 1h + 자동화 3h | 생산: 50-100건/요청
- 리스크: 할루시네이션 (존재하지 않는 키워드), API 비용 ($0.01/요청), 검증 로직 필요
- 효과: A의 시드 고갈 시 대체, 즉시 실행 가능

## 4. 추천 우선순위
1. **A (expander 확대)** — 검증됨, 즉시 적용, 비용 0
2. **C (LLM 시드)** — A 보완, 1시간 프로토타입 가능
3. **B (외부 API)** — 장기 안정성, 2단계로 연기

## 5. 긴급 조치 (승인 대기, SELECT만 — 미실행)
- ETAP: deals/nature/airports/watersports exhausted=0 리셋 50건 (Option B, 과거 데이터 재활용) — 승인 후 UPDATE
- CAP ev: expander 1회 수동 실행 (`python -m pipelines.car.expander --site ev --count 100`)
- STAP ipo: stock_issue 라우팅 버그 수정 (publish_log source 매핑 5줄) → 2799건 즉시 활용
- W5 R13 이미지 주입: pick 2건/rap2 7건/rap4 10건 본문 `![image]` 주입 (hugo_writer 이미지 가드)

## 6. 재발 방지
- scheduler weekly pool_health_check (월요일 06:00)
- 10% 미만 시 자동 expander trigger (cron + slack)
- 0% 도달 시 발행 일시정지 + Watchdog 텔레그램 CRITICAL 알림
- 대시보드 /pool-status에서 7일간 추이 그래프

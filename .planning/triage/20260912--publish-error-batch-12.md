# 2026-09-12 publish-error batch triage (12 alerts, 8 groups)

> 분류: 스킬 publish-error-triage 절차 (Parse → Classify → Root-cause → Fix+Register → Manualize)
> 대시보드 기준: ops_dashboard/ops.db `publish_error_events` + `logs/scheduler.log`

## 수정 완료 1건

### guide-hugo P04 W5 R13 — 수정됨 [검증됨]
- 증상: W5 이미지 게이트 차단, 매일 guide 배포 중단 (incident open, occurrence 5).
- 원인: `대학생직장인-첫차-m4...` 포스트 본문 이미지 0장 (R13 = 본문 `![...](` ≥1장, `deploy.py:150-158`).
- 수정: car_images verified bmw_m4_2026 4장 중 1장 본문 삽입 (R2 URL, 200 확인 아님 — DB verified=1 기준) + guide-hugo 로컬 커밋 `692b954` (미푸시 — Mac 배포는 디스크 기준이라 다음 슬롯부터 게이트 통과).
- 검증: 최근 3일 guide 포스트 전수 R13 스캔 → 위반 0건 (차단 포스트 1건만).
- 부수 발견: 차단 포스트 자체가 untracked 신규 파일 (9/11 21:00 발행 후 미푸시) — guide-hugo도 tco/compare급 dirty 존재. push는 Task 0 범위 밖이라 미실시.

## REAL — 대시보드에 있음 (open incident, 추가 조치 불필요 또는 외부 대기)

### rap4-hugo P01 no_trade_data (consec 15) + rap-hugo P01 (consec 9) — 외부 데이터 구멍
- `no_trade_data`, `FAILED_TRANSIENT`. rap4 incident open (occurrence 13-14), rap fetcher 실거래가 0건 (중흥파크에스클래스빌/중흥에코시티8단지).
- 선례: 9/5 rap4 rents 커버리지 구멍은 SYNC_REGIONS 58→69로 해결. 이번은 개별 단지 실거래 자체 부재 — 수집 소스 대기. 조치 없음 (transient, 카운터가 해소 시 자동 close).

### airlines-hugo topics exhausted — REAL 소진
- `airlines_topics` 1137/1137 exhausted=1. "🛑 발행 중지" 안내와 일치. ETAP 토픽 리필 작업 필요 (9/6 선례: flights 0→200 리필) — 별도 태스크, 본 배치에서 미실시.

### appliance-hugo offtopic 에스프레소 (open) — 정상 키워드, 게이트 1회 미스
- 풀 199건 중 커피머신 계열 정상. avg=0.50 1회 미스는 오염 아님 (9/2 golf-driver 선례와 다름). purge 불필요.

### ipo-hugo P02 no_content ×1 — transient, 관찰만

## 대시보드에 없음 3건 (사용자 요청 보고 대상)

### ① rap2-hugo [Validate] CRITICAL 지역 왜곡 (거창군) — REAL + 게이트 설계 구멍
- 팩트: seed keyword `경남 거창군 일반 매입임대주택...` (rap2-hugo, 오늘 08:20 사용) → 15:20 발행글은 양산김해 LH 내용, 거창 0회. `validators.py:641` `_check_rap` CRITICAL 발화는 정확.
- **설계 구멍**: `validate_post_extended`는 Telegram 발송만 하고 발행 차단 안 함 (validators.py:744-775 — issues 리스트 반환, rap pipeline이 소비 안 함). CRITICAL인데도 success+배포(rc=0 12.6s) 완료. "차단" 문구와 실제 동작 불일치.
- 라이브 글 내용: 경남 매입임대 일반 안내 (구체 접수기간 등 날조 없음 — 위해 낮음). 콘텐츠 수정/내리기는 미실시 (판단 필요 시 지시 요청).
- 후속 후보: (a) fetch-time 이중 미매칭 가드(pipeline.py:1110/1151)가 왜 못 막았는지 조사, (b) CRITICAL을 실제 draft 강등으로 연결. 둘 다 본 배치 범위 밖.

### ② baby-hugo P14 insufficient_products (유아변기) — 임계값 미달, 설계상 미등록
- P14 threshold `consecutive:3` (problem_registry.py:357-379). 오늘 15:15 consecutive=1 → incident 미생성 정상. 3연속 시 자동 등록. 조치 없음.

### ③ appliance-hugo P14 low_relevance (15:05) — 동일, consecutive=1 → 미등록 정상
- 같은 사유. 3연속 시 자동 등록.

## 잔존 위험
- rap2 CRITICAL 무차단 발행 — 동일 패턴 재발 가능 (validate advisory-only). 게이트 강화는 별도 태스크.
- airlines 리필 미실시 — 발행 중지 상태 유지.
- guide-hugo 미푸시 (로컬 커밋 692b954) — 다음 기회에 push.

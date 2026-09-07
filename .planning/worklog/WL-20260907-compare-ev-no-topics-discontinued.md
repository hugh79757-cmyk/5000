# WL-20260907 — compare-hugo no_topics + ev-hugo no_topics 원인 해결 (단종 차량 토픽 무한 순환)

**날짜:** 2026-09-07
**작업 유형:** 파괴적 (car.db 1,569행 status UPDATE) + [PRODUCTION CODE] daily_refresh.py 수정
**관련 alert:** compare-hugo no_topics 4/5, ev-hugo P02 5연속 (b9 미해결 항목)

## 배경

compare-hugo no_topics 4/5 실패. select_topic의 unused 쿼리는 compare ranking_compare 시판매칭 후보 62개 전부 status='skip_no_data'라 0건.

## 원인 (전체 체인)

1. **trims.status 값은 문자열** `시판`/`단종` — grandeur_hev_2026 등 인기 모델도 trims 전부 `단종` 처리됨 (2026년형 표기 이슈로 추정).
2. car 파이프라인 토픽 다수가 본체 car_id의 시판 trims가 0건 → build_input `status='시판'` 필터에서 차단 → pipeline.py:241 `skip_no_data` 마킹.
3. `reset_skip_no_data` (daily_refresh.py:361, 매일 06:30)이 7일+ 경과 skip_no_data를 **무조건 pending 리셋** → 다음 발행 스케줄에서 다시 시도 → 다시 skip → 무한 순환. 리셋→발행실패 사이클이 26 candidates 소진 → no_data → P01 3연속 → cooldown.
4. ev-hugo no_topics도 동일 원인: pending 2개(ioniq6_2026/santafe_hev_2026) 전부 90일 콤보 가드(content.db articles, prompt_id=ev_analysis)에 걸림 — 최근 발행됨. 정상 대기 상태.

## 실행 내역

1. **[PRODUCTION CODE] daily_refresh.py reset_skip_no_data() 수정** — 리셋 조건에 시판 trims 존재 검사 추가:
   - 본체: `EXISTS (SELECT 1 FROM trims WHERE car_id=topics.car_id AND status='시판' AND price>=500)`
   - 경쟁차량: competitor가 있으면 동일 검사 (빈 값은 통과)
   - 단종(시판 trims 0건) 토픽은 더 이상 리셋 안 됨 → 무한 순환 차단.
2. **[DESTRUCTIVE] car.db 1,569행 skip 마킹** — 현재 pending 중 본체 시판 trims 0건 토픽 전부 `status='skip_no_data'`로 정리 (compare 104 포함, ev 237 포함). 4단계 프로토콜: 사전 카운트 1,569 → 백업 `data/car.db.bak_discontinued_cleanup_20260907144338` → UPDATE changes()=1,569 → 사후 compare pending 58/ev pending 26, integrity ok.
3. **검증:** reset_skip_no_data 직접 실행 — 개선 전 120건 무조건 리셋 → 개선 후 단종 제외 동작 확인. select_topic 재현: compare ev4_2026 vs bmw_i4_2026 정상 선택. py_compile OK. 관련 테스트 9 passed (car refresh/skip/topic).

## 검증 분류

- [검증됨] 무한 순환 원인 체인 — trims status 문자열 확인(SQL), reset 무조건 리셋 재현(직접 실행 120건), 개선 후 select_topic 정상 선택(실코드)
- [검증됨] 1,569행 UPDATE — 사전 카운트 = changes() = 사후 재계산 일치, integrity ok, published 행 무변경
- [검증됨] ev no_topics = 정상 대기 — pending 2개 전부 90일 콤보 가드 (content.db articles 실쿼리)
- [부분검증] 다음 스케줄 발행 — select_topic 재현 성공했으나 실제 발행은 스케줄러 미래 이벤트. compare는 daily cooldown 중 → 내일 06시대 재시도

## 잔존 위험

- **단종 처리 근본 원인 미해결**: 인기 2026년형(grandeur_hev 등)이 trims에서 `단종`으로 표시된 것은 carisyou 데이터 표기 이슈 가능성. refresh_trims가 status를 갱신한다면 데이터 소스 점검 필요. 1,569 토픽이 skip_no_data로 잠겨 있으므로, trims가 다시 `시판`으로 돌아오면 수동 리셋 필요 (또는 개선된 reset이 7일 주기로 자동 복귀 — 시판 존재 시만).
- compare 내일 발행 성공 여부 모니터링 필요 (cooldown 해제 후).
- content.db articles와 car.db publish_log의 ledger_sync 지연 — ev 마지막 발행 4/21 vs publish_log 9/6. select_topic은 car.db 기준, publisher 콤보가드는 content.db 기준 — 불일치 시 duplicate_source_id 가능성 (travel1 사례 b12와 유사).

## 후속 작업 (2026-09-07 오후) — 후속모델 미스캔 구멍 교정

**사용자 질문으로 확인:** carisyou 원본에 그랜저 HEV/2.5 전 트림 `단종` 표기 — 수집 코드 정상 반영 (2026년형 부분변경 출시로 구형 단종). 단종 자체는 버그 아님.

**진짜 구멍 [검증됨]:** `scan_new_cars` 커서 결함 — scan_log.max_scanned_id(12293)가 cars.MAX(7830)보다 앞서면 그걸 우선 → carisyou 12294+는 전부 빈 쓰레기 페이지(임계 50,000 미만) → 7831-7860의 실모델 18대가 영원히 미스캔. 후속모델(뉴 니로/아르카나/뉴 GV60/뉴 일렉트리파이드 GV70/iX3 2세대/EX90 등) 신규 등록 안 됨.

**FIX [PRODUCTION] daily_refresh.py:** scan_log 우선 로직 제거, `scan_start = cars.MAX(carisyou_id)+1` 고정. 단종 차량은 원본 표기 반영이므로 reset_skip_no_data의 시판 검사(본문 FIX)가 정합 처리.

**일회성 실행 (코드 교정 후):**
1. 오늘 scan_log 1행 DELETE (재스캔 허용)
2. scan_new_cars 7831-7861 재스캔 → 18대 발견, **9대 자동 등록** (AUTO_REGISTER_BRANDS 한국 주력: 아르카나 7832/7833, GV60 7835, 일렉트리파이드 GV70 7836, iX3 7837, EX90 7838, A6 7843, 코나2027 7845, 코나HEV2027 7846). 미등록 9대(링컨/미니/BYD/GMC/애스턴마틴/램/포드)는 의도적 큐레이션 세트 — 유지 결정
3. refresh_trims: 751행 UPDATE + 신규 9대 트림 39개
4. replenish_topics: **98행 INSERT** — ev_analysis 48(2→50 pending), persona_pick 26(8→34), top5_rank 24(26→50). compare는 pending 58(≥50)이라 스킵 — 정상 동작

**검증 [검증됨]:** select_topic 실코드 재현 — rank 1288(benz_amg_gt)/pick 1061(ev5 vs ioniq5n)/ev 4999(ev4) 전부 정상 선택. py_compile OK.

## 후속 작업 2 (2026-09-07 저녁) — 신규 9대 이미지 눈검수 (CAP SOP)

**사용자 질문: "등록한 자동차들 이미지 검증 필요하지 않아?"** → car_images 87개 전부 verified=0 — 검증 필요 맞음.

**SOP:** `/Users/twinssn/Desktop/메모 Hugh-v2/프로젝트/CAP/CAP 이미지 검수 요청 - hot issue rotcha.md` (검수 페이지 → 눈검수 → ID 전달 → DELETE + blocked_images 등록).

**실행:**
1. 검수 페이지 생성: `scripts/image_review_new_cars_20260907.html` (9차량/87카드/삭제 버튼/ID 클립보드 복사)
2. 사용자 검수 → ID 10개 전달 (16901,16909,16880,16871,16862,16912,16921,16844,16853,16891)
3. car_images 11행 DELETE: 전달 10행 + 같은 URL 공유 기존행 1건(id 266 grandeur_2026 — 쓰레기 판정 URL 재사용)
4. blocked_images 정확 URL 등록 (초기 접두사 60자 불완전 등록 실수 → 전체 URL로 교정 완료. 최종 615행)

**결과:** 신규 9대 car_images 87→77. 잔여 77개는 사용자 추가 검수 대기 (페이지에서 더 전달 가능).

## 백업

- `data/car.db.bak_discontinued_cleanup_20260907144338` (3.7MB) — 이미지 INSERT 이전 상태 (car_images 미포함. 검수 페이지 HTML이 URL 원본 보존 역할)

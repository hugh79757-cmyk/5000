# WL-20260912-phase79-pilot-runner-g0

> 날짜: 2026-09-12 / 연관: Phase 79 (pilot-runner-g0) / 상태: 진행중
> 상위 규약: `.planning/migration/MASTER-PLAN.md` (I1~I10)

## BUG-12 등록 못박기 (2026-09-12 사용자 승격 지시)

- **현상**: ev-hugo duplicate_source_id 6연실패 (2026-09-12 06:45~17:30, ev9_2026/tesla__3_2026). 만성 버전은 8/24 compare(bmw_ix2) 첫발, 하루 4~48건 (hotissue·compare 주범).
- **루트코스 (3층 가드 대조, file:line)**:
  1. 선택 콤보 `topic_manager.py:45-48` — (blog, car_id, post_type) 90일 ✅ post_type 스코프
  2. 발행 1번 가드 `publisher.py:828-829` — (blog, source, **prompt_id**) 90일 ✅ post_type 스코프
  3. 발행 2번 가드 `publisher.py:832` — (blog, source) **prompt_id 무시 30일 ❌ BUG-12 주범**
- **메커니즘**: post_type 리스트 블로그(ev [ev_analysis, top5_rank], hotissue 6개)에서 car_id가 다른 post_type으로 발행된 이력이 30일 가드에 걸려 차단. `content_store.py:225-227`은 prompt_id 인자 이미 지원, car pipeline은 이미 전달(pipeline.py:376) — publisher만 미전달.
- **수정 (Task 9, G1 진입 전 필수)**: `publisher.py:832` source_exists 호출에 prompt_id 인자 전달 (1줄+주석). **전 함대 회귀 테스트 조건: hotissue·ev·tco·guide 각 최소 1슬롯 정상 발행 관찰 (duplicate 0건) — 통과 전 G1 진입 금지.**
- **3층 가드 "동일 기준" 불변식**: 선택 90일 post_type · 발행 30일 post_type 스코프 · 로테이션(다양성). 수정 후 문서 1곳에 정리.
- kickstart 신규 코드 무관 (9/11 17~21시 ev 정상 5건 실증 — 실패는 9/12 post_type shuffle top5_rank 우선 픽부터).

## BUG-13 기록 (수정 안 함 — Phase 79 방해 X)

- **현상**: travel1-hugo duplicate_source_id 47건 (최근 7일 12건) — 전체 1위. travel2 9건 포함 travel 계열 공통.
- car 3층 가드와 별개 원인 — BUG-12 수정으로 해소 안 됨. G1 이관 완료 후 별도 조사 권장.

## 파괴 작업 목록 (진행 기록용 — Task 0 이후 순차 append)

| 시각 | 작업 | 사전카운트 | 백업 | 사후대조 | 보존확인 |
|------|------|-----------|------|---------|----------|
| (예정 21:15+) | tco-hugo push (dirty 295 + 미푸시 5) | tracked 272 = origin 272 | 로컬 SSOT 보존 | push 후 ls-files↔ls-tree 551 예상 | 미푸시 콘텐츠 0건 |
| (예정 21:15+) | compare-hugo push (dirty 573 + 미푸시 4) | tracked 993 = origin 993 | 로컬 SSOT 보존 | push 후 패리티 일치 | origin-only 0건 확인 (m0512 재측정) |

## 잔존 위험
- BUG-12 수정 미실행 (G1 전 필수 — Task 9 등록 완료)
- bmw_m4_2026 이미지 1장 download_fail (4장 커버로 게이트 충족, 완전 무결 아님)
- tco 후보 중 ev5_2026·benz_sl skip_no_data 이력 — 선택 시 Mac-패리티 판정 대상

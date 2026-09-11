# WL-20260911 — 발행 오류 트리아지 (ev-hugo no_topics + W5 이미지 게이트 + 광산구 연쇄)

날짜: 2026-09-11 | 작성: publish-error-triage 스킬 기반 세션

## 오늘 알림 전사 분류 (3분법)

### [검증됨] — 로그/DB/curl로 확인
- ev-hugo no_topics 5/5 연속: pending 46개 중 44개 단종(시판가드), ioniq6/santafe는 14일 발행재사용+30일 아티클 가드 → 선택 가능 0개. `select_topic` dry-run으로 재현.
- ev-hugo W5 이미지 게이트: 발행은 성공(13720 GV60/13721 iX3)하나 car_images 전부 verified=0 → 본문 이미지 0장 → 배포 중단. `pipeline_status=FAILED_TRANSIENT` 로그 + car_images SELECT로 확인.
- rap/rap4 광산구 연쇄: use_count=0 광산구 키워드 30여 개가 후보 상위 20개 독점 → 연속 같은 지역 0건 → 키워드 자동 inactive. pipeline.py:96-160 선택 로직 + rap.db keywords 상태로 확인.
- 대시보드 stale: pid 29940 09-03 기동. 09-10 검사기 수정(standard.py R12 허용목록, content_integrity.py S01/S02 self-match)이 커밋 전이었고 재시작 전이므로 미적용.

### [부분검증]
- GV60/iX3 이미지 9장 R2 업로드 후 라이브 렌더: 두 포스트 URL 200 + 이미지 webp 로드 확인(단, 전 브라우저 렌더는 미확인).
- kona/k8 displacement 채움(1580/1598) 후 `build_input` 통과 확인(단, 실 GPT 생성+발행은 13:50 슬롯 대기).

### [검증불가] — 복구 계획 명시
- fleet 알림 37건 중 CQ03 제휴문구 등 나머지: `/api/run-checks` 갱신 미실행 → 오늘 중 stale row 갱신 예정.

## 자가회복 (조치 없음)
camping 우비(07:06 성공), hotissue(07:15), travel2(07:09), appliance 면도기(08:05 정상 발행), rap-hugo(08:19 성공), beauty P16(08:48 catchup), rap2(가드 작동), tco(06:30 lock 일회성).

## 조치 (전부 4단계 파괴 프로토콜 + 사용자 승인 m0106)

1. **FIX A 커밋 2655e813d**: standard.py R12 허용목록 2개 + content_integrity.py S01/S02 self-match 제거 + keywords.py 콤나 2개(위반 감지 후 수정 — 원래 로컬 미커밋 diff에 이미 섞여 있던 결함).
2. **FIX B 대시보드 재시작**: pid 28229, port 5060. R12 14→1(stale row).
3. **ev topics INSERT**: 백업 car.db.bak_20260911_evtopics → GV60/iX3/kona/k8 4행 pending (46→50).
4. **GV60/iX3 발행 성공**: 10:32/10:35 article 13720/13721. P01/P02/P34 자동 close, retry 리셋.
5. **이미지 검증 배치 scripts/verify_ev_images_20260911.py**: carisyou 원본→webp→R2 9장 (GV60 4, iX3 5; 1장 timeout 실패). verified=1 UPDATE.
6. **본문 이미지 삽입 + 재배포**: index.md 첫 H2 후 `![](r2)` 삽입 2건, publish_log r2_url UPDATE(2940/2941), `deploy_site()` → rc=0 17.6s. 라이브 200 확인.
7. **ops.db P04 close**: 5a3f216e resolved_at 세팅. 백업 ops.db.bak_20260911_evclose.
8. **kona/k8 소생**: cars.displacement=1580/1598 (public_fuel_data 근거), topics 5062/5063 skip_no_data→pending. `build_input` OK 확인.
9. **logs/destructive_2026-09-11.log**: 5개 항목 기록 (INSERT/UPDATE/배포/ops.db 각각).

## 근본 원인 요약
- ev-hugo: `replenish_topics`가 raw pending count(46≥min 50 아님, min_pending=50)로 need 계산 → 불가 행 포함. 단종/데이터불량 차량이 풀 점유.
- 이미지: 커밋 3320126e6(4/16)이 원본 다운로드+R2 업로드 제거, verified 설정 경로 부재 → 신차는 영구 미검수.
- 광산구: 키워드 일괄 등록 세대(use_count=0)가 ORDER BY 상위 독점.

## 잔존 위험
- ev-hugo 13:50: kona/k8 2개 후보만 유효. 선택 후 풀 재소진 시 no_topics 재발 가능 → FIX C(replenish usable-guard) 별도 커밋 필요. 현재 미커밋.
- 이미지: 신차(ev4/ev5 등)는 여전히 미검수 → 차후 동일 W5 차단 재발. `verify_ev_images_20260911.py`를 정기 배치로 일반화 검토 필요.
- airlines-hugo: **중지 수락 확정 (사용자 결정 2026-09-11)**. airlines_topics 1137/1137 exhausted — seed(AIRLINES_SEED 고정 실제 항공사 리스트) 전량 소진, synthetic backfill은 2026-09-09 금지 결정(가짜 항공사=routes 데이터 부재→발행 전멸). 자동 중지 상태 그대로 유지. 재개 조건: routes 데이터 동반 신규 seed 소스 확보 시. 경로: data/travel-en.db airlines_topics + ref_airlines(미사용 19개는 routes 부재).
- sector-hugo: 조사 완료 [검증됨]. (1) 데이터 정상 — get_unused_data sector=80/index=50/krx=40. (2) 가드 정상 — title_similar_exists=False, 업종 중복(2차전지) 미차단, slug 중복 없음. (3) writer 정상 — 재실행 시 groq-qwen 16.5s 5024자 생성 성공. (4) 실제 원인 = LLM 체인 일시 전멸 — 첫 진단에서 RuntimeError(154초, 전 폴백 429/404) 재현. 09-11 07:12 no_content(1/5) = 일시 실패. (5) DB 이원 주의 — STAP 자체 DB(/Users/twinssn/Projects/STAP/data/stap_content.db, 385건, 최종 09-09 20:28)가 진짜. 5000/data/stap_content.db는 사본(1건, 07-30) — 이 사본 DB로 조사하면 만성 실패로 오판. 자가회복 예상. 조치 불필요.
- car.db 06:30 lock (daily_refresh와 발행 동시): WAL on이므로 일회성. 재발 시 스케줄 스태거 검토.
- rap4-hugo 광산구 클러스터: 자가 소진 예상. 모니터.
- CQ03 등 fleet stale row: 대시보드 run-checks 미갱신 → 오늘 갱신 예정.

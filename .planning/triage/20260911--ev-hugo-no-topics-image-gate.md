# 20260911 — ev-hugo no_topics 5/5 + W5 이미지 게이트 연쇄

## 증상
- ev-hugo no_topics 5/5 연속 실패 (P02) + catchup retry_amplification 제외
- 수동 발행 성공 후 W5 이미지 게이트 배포 중단 (article 13720 GV60 / 13721 iX3)

## 근본 원인 (2단계)
1. **토픽 풀 오염**: topics pending 46개 중 44개가 단종 차량(`trims status='시판'` 부재). `replenish_topics`(daily_refresh.py)는 raw pending 수만 보고 need=0 산출 → 시판 가능 차량 재보충 없음. ioniq6/santafe는 발행 재사용 가드로 차단.
2. **이미지 검증 경로 단절** (커밋 3320126e6, 2026-04-16): `_select_car_image`을 verified=1+r2_url만 쓰도록 바꾸면서 원본 다운로드+R2 업로드 로직 제거 → 이후 신차 전부 미검수 영구 상태 → 본문 이미지 0장 → W5 R13 게이트 배포 중단.

## 조치
- car.db topics INSERT 4행 (genesis_gv60_2027, bmw_ix3_2026, kona_hev_2027, k8_hev_2027) — 백업 car.db.bak_20260911_evtopics
- kona/k8 cars.displacement 0→1580/1598 (public_fuel_data 코나 1.6GDI HEV/K8 1.6TGDI HEV) + skip_no_data→pending
- `scripts/verify_ev_images_20260911.py`: GV60 4장/iX3 5장 carisyou→webp→R2 업로드 + verified=1
- 본문 이미지 삽입(첫 H2 후) + publish_log r2_url UPDATE + deploy_site 재배포 → 라이브 200
- ops.db P04 close

## 재발 방지 (미완 — FIX C 대기)
- replenish_topics가 market-usable pending만 카운트하도록 수정 필요 (FIX C, 미커밋)
- 신차 이미지 검증 자동화: `verify_ev_images_20260911.py` 패턴을 일반 배치화 검토

## 참조
- worklog: `.planning/worklog/WL-20260911-publish-error-triage-ev-images.md`
- 관련 이전 사례: 20260907--compare-ev-no-topics-discontinued (WL-20260907)

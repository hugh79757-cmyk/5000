# WL-20260826 — 발행 오류 트리아지 (senior W5 / playwright / 스테일 P02)

## 작업
- senior-hugo P04: W5 게이트 R13(본문삽입이미지 0장) 11건 배포 차단
- rap3/rap5-hugo P02: playwright BrowserType.launch 실패 연쇄
- foodtour/adventure P02: 연속 5회 알림

## 파괴적 작업 기록
- SEAP/senior-hugo 최근 3일 글 12건 본문 이미지 삽입 + 19건 twitter_card FM 추가 → 백업=git, 로그=logs/destructive_2026-08-26.log, 라이브 검증 완료
- wrangler 배포 2회 (senior-hugo deploy_site, rap5-hugo dispatcher)

## 코드 변경 [PRODUCTION CODE]
- pipelines/senior/pipeline.py `_ensure_body_image()` — Hugo/Blogger 이미지 패리티 복원

## 환경 변경 [CONFIG]
- .venv `playwright install chromium` (headless_shell v1234)

## 잔존 위험
- watersports/phototour `pipeline_returned_false`, dining/deals no_data, sector no_content, interior P14 — 미착수(별도 이슈)
- senior-hugo 사이트 repo에 타 세션 미커밋 변경 다수 존재 — 커밋하지 않고 보존함

## Round 2 (15:0x-16:0x) — 잔여 open 이벤트 처리

- rap3-hugo: 수동 dispatch 성공, article 12148, 라이브 200 (tax.informationhot.kr)
- rap4-hugo: leak C04('단계별로') 1회 차단 → 재시도 후 포스트 생성, 수동 빌드+배포, 라이브 200 (rent.informationhot.kr)
- pick-hugo P04: 원인=W5 R13 본문 이미지 0개. car/pipeline.py W5 보장 블록 추가(13 lines) + 백필 2건 + 배포, 라이브 200 ×2
- watersports-hugo: 수동 dispatch 성공 (cebu-water-sports), 일시 장애
- phototour-hugo: is_draft 무한재시도 방지 마크 추가(6 lines) + scheduler 큐 실행으로 발행 성공(같은 토픽 품질 통과), 라이브 200
- shared/telegram_notifier.py: send_warning/send_critical 래퍼 추가(10 lines) — ETAP quality_guard ImportError 수정
- dining-hugo: 실제 09:02 발행 성공, P01 이벤트는 CATCHUP 레이스로 잔여 open
- health/car-hugo: 오전 발행 성공 확인, P14 이벤트 미갱신 잔여
- ev/compare/deal/stock/travel4: 다음 슬롯(16:08~16:22) 자가복귀 예상 (playwright 수정 반영)
- 스케줄러: 정상 동작 확인 — 로깅이 logs/scheduler_stderr.log로 출력 중 (scheduler.log 아님)

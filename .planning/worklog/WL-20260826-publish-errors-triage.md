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

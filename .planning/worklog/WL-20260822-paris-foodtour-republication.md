# Worklog: WL-20260822-paris-foodtour-republication

## Operation
foodtour-hugo paris-food-tours 재발행 (republication-analysis Group A #10) + 재발행 차단 버그 근본 수정

## Pre-Count
- publish_log: 1행 (log_id=1236, topic_id=12, 2026-04-07)
- foodtour_topics id=12 (Paris): exhausted=1, priority=6
- 포스트 dir: index.md 1파일 (2026-04-07 구 형식)

## Backup
- republication-analysis/backup/paris_20260822_175048/travel-en.db.bak (148MB)
- republication-analysis/backup/paris_20260822_175048/post_paris-food-tours/

## Execution
1. 스케줄러 중지 (launchctl unload com.5000.scheduler)
2. DELETE publish_log log_id=1236 / UPDATE exhausted=0 / 기존 포스트 dir 삭제
3. 강제 파이프라인 실행 (pick_topic → topic id=12 monkeypatch)
4. **실패 발견**: `A Food Lover's Guide` 곡선 아포스트로피(U+2019) → fm 빌드 후 C01 치환이
   단일따옴표 YAML 내부를 직선화 → invalid_frontmatter 쓰기 차단.
   그런데 _run_impl이 쓰기 실패를 무시하고 mark_published 실행 → DB/디스크 불일치.
   (오늘 오전 granada 빈 dir 동일 사례)
5. 수정 [PRODUCTION CODE]:
   - hugo_writer.py `_write_hugo_post`: title/body를 fm 빌드 전 C01 정규화,
     빌드 후 fm 치환 제거(본문만 유지)
   - foodtour_pipeline.py `_run_impl`: 쓰기 실패(None) 시 return False + send_alert,
     mark_published 생략
6. 합성 테스트 통과 후 재실행 → 성공

## Post-Verification
- 신규 포스트: date 2026-08-22T18:13, YAML 파싱 OK, 제목 직선 아포스트로피 이중인용
- Hugo 빌드 399 pages, 에러 0
- 배포: https://fdc9aa55.foodtour-hugo.pages.dev (74 files)
- 라이브: HTTP 200, title OK, affiliate disclosure 1건(테마 partial),
  A Practical/Comprehensive 0건, bold 3회+ 없음(md), viator 25링크
- 스케줄러 재시작 확인 (PID 89064)

## Notes
- 페이지 URL은 /posts/paris-food-tours/ (permalink에 posts prefix 있음 — curl 검증 시 주의)
- "면책 문구 삽입 스킵" 경고는 한국 coupang 경로로 ETAP 영어 포스트와 무관
- 투어명 bold 각 3회 = quality_guard threshold 초과 아님(INFO 처리)

## Logs
- logs/destructive_2026-08-22.log

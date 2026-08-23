# WL-20260816-webp-backfill — ETAP airports-hugo webp 재생성 (배치 2)

> 날짜: 2026-08-16
> 작업: airports-hugo 161 포스트 이미지 R2 jpg → webp 전환 (THUMBNAIL-01 준수, 용량 절감)
> 성격: 파괴적 (R2 WRITE + frontmatter/본문 in-place 편집). DELETE 0회 (jpg 잔존).

## 작업 개요
- 생성단 webp는 배치1(`064eeaef0`, image_fetcher.py `_to_webp`)로已完成. 본 배치2는 기존 161 포스트 백필.
- 방법 B(원본 URL 재fetch → webp) 채택 — travel-en.db.used_images에 원본 pexels/unsplash URL 보존(cover 3758/body 13564행). 화질 유리(이중손실 없음).
- jpg 잔존 정책 — 실패 건은 기존 jpg가 계속 서빙되어 안전. DELETE는 라이브 검증 안정 후 별도 배치.

## 사전 카운트 ([0] 실측)
- cover frontmatter `cover.jpg` = 159건 (grep)
- 본문 인라인 `body_%d.jpg` = 688건 (grep, R2 full URL 형태)
- unique 영향 파일 = 160건 (백업 완료)
- jpg→webp 실측 절감 = 67.25% (9샘플 R2 READ, 추정 아닌 측정)

## 백업 (선행 완료)
- 스케줄러 정지: `com.5000.scheduler` (PID 23963) `launchctl unload` @ 2026-08-16 15:30:10 → STOPPED. 재시작 예정.
- 파일 백업: `content/posts/*/*.md.bak_webp_backfill_20260816_153033` 160건.
- git tag: `pre-webp-backfill-20260816` (airports-hugo).
- destructive log: `logs/destructive_2026-08-16.log` 1행 append.

## 실행 (게이트 방식)
- 게이트1: 샘플 5 slug (cover+body 혼합) → 원본URL fetch → `_to_webp`(q85 m6) → R2 WRITE cover.webp/body_N.webp → 성공 시 md `.jpg`→`.webp` in-place(slug/경로 불변). STOP+보고 → 842건 승인 재요청.
- 게이트2: 나머지 842건 순차 (게이트1 승인 후).
- 폴백: 원본 fetch 실패(404/삭제/rate) 시 방법A 금지, 해당건 스킵+실패리포트(jpg 잔존 안전).
- 빌드/배포 미실행 (다음 정규 발행 반영).

## 사후 대조 (게이트 완료 후 기록)
- [ ] R2 라이브 URL 200 + webp magic
- [ ] md 치환 정확성 / body_N 순서 매핑 (WHERE slug=? AND usage_type='body' ORDER BY rowid)
- [ ] slug/경로 불변
- [ ] THUMBNAIL-01 159 cover PASS 전환
- [ ] 실패 리스트 / 회귀 0

## 보존 확인
- 실발행 행 보존 불변 (content.db 미변경). R2 원본 jpg 잔존(DELETE 0).

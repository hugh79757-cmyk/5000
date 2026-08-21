# Plan — ETAP Quality Overhaul (2026-08-21, Track C)

> Source: `docs/superpowers/specs/2026-08-21-etap-quality-overhaul-design.md` (S0~S3)
> Timebox: P0~P1 오늘 밤, P2 파일럿 michelin 내일 새벽, P3 최소 정의
> Pilot: michelin-hugo (단일 블로그 선행, 전파 금지)

---

## Task S0-1 — quality_guard 0허위/LaTeX 게이트 (P0)

- **Files**: `pipelines/etap/quality_guard.py` (postprocess_content only)
- **Change**: 0 count 허위 정규식 + LaTeX `$\rightarrow$` 치환, `is_draft=True` + CRITICAL. `data_prices=None` 경로에서도 동작. benefit gate는 WARNING로 완화(코멘트).
- **Verify (live)**: `python -m py_compile` + 수동 `michelin` 1회 실행 `logs/scheduler.log`에 `stage=draft_detected` 0, 생성 `index.md`에 `|0|`/`there are no airlines`/`$\rightarrow$` 0건.
- **Rollback**: `git revert` single file.
- **Commit**: `fix(etap): 0허위/LaTeX quality gate — S0`

## Task S1-1 — GA4 per-blog + G-DEFAULT 제거 + AdSense 중복 제거 (P1 최우선)

- **Files**: 단일 소스 확정 후 1곳 — 후보 `shared-themes/blowfish/layouts/partials/head.html` 또는 `ETAP/*/layouts/partials/head.html` 오버라이드 + `ETAP/{blog}-hugo/hugo.toml` 34개 동기화 스크립트 (`yq` 또는 `scripts/sync_ga4.py` 신설). `adsbygoogle.js` 중복 include 제거는 동일 head 파일.
- **Change**: `G-DEFAULT` 삭제, `services.googleAnalytics.id = {ga4_map.csv/etap.yaml ga4_id}` per-blog 1회 로드, 미보유는 미출력. AdSense 로더 1회.
- **Verify (live)**: `for d in $(cat domains.txt); do curl -s https://$d/posts/{slug}/ | grep -c 'G-'; done` — per-blog 1, `G-DEFAULT` 0, `adsbygoogle.js` 1. GA4 Realtime에서 블로그별 스트림 분리 확인(수동).
- **Rollback**: head.html + hugo.toml revert. 34개는 스크립트 재실행으로 원복.
- **Commit**: `fix(etap): GA4 per-blog + AdSense single load — S1`

## Task S1-2 — author + disclosure + 신뢰 (P1)

- **Files**: `layouts/partials/affiliate-disclosure.html` (신설) + `shared-themes/blowfish/layouts/_default/single.html` (FAQPage 스키마 주입 지점) + `ETAP/{blog}-hugo/hugo.toml [author]` 1줄
- **Change**: `author.name` 채움, 본문 첫 affiliate 링크 전 disclosure 1줄(조건부), 하단 `Data: Michelin Guide … last verified` 주입 위치 확보.
- **Verify (live)**: `curl ... | grep -o '"author":{"@type":"Person","name":"[^"]*"'` non-empty, `affiliate|commission` 1건 when link present.
- **Rollback**: partial + hugo.toml revert.

## Task S2-1 — michelin 원소스 필드 전수 + writer 구조 재설계 (P2 파일럿)

- **Files**: `pipelines/etap/michelin_writer.py`, `pipelines/etap/michelin_pipeline.py` (+ `_add_product_cards` 신설), `data/travel-en.db` read-only 조사 산출 `ETAP-source-fields.md` 1p (S3 입력 겸용)
- **Change**: 도입부 Answer Box(요약 테이블 3줄), H2 4고정(At a Glance/Where to Eat/Compare/FAQ), 식당별 H3 120~180w, 비교 테이블(price_tier 필수), FAQ 3문항 + FAQPage JSON-LD, CTA 2개(요약 후/비교 후, 600px 간격), 광고 2개(H2-2 후/비교 후, ad-top 제거), 내부링크 500w당 3개 상한(같은 도시 우선).
- **Verify (live)**: `https://michelin.techpawz.com/posts/{new-slug}/` curl 7체크: 요약/비교/CTA2/광고2/FAQ3+schema/author non-empty/wordCount 900~1400/0허위0. GA4 단일 로드. 다음 날 GA4 engagement_rate vs 전날 평균.
- **Rollback**: writer+pipeline revert, Hugo rebuild + `wrangler pages deploy` per `shared/publishers/deploy.py`.
- **Commit**: `feat(michelin): answer-first + compare + FAQ pilot — S2`

## Task S2-2 — michelin 파일럿 발행 + 라이브 검증 (P2)

- **Files**: `ETAP/michelin-hugo/content/posts/{new-slug}/index.md` 생성물 + `public/` 빌드 산출
- **Change**: `python dispatcher.py michelin-hugo` 1회 수동 발행 (S0+S1 선행 커밋 후). scheduler CATCHUP 경유 아님.
- **Verify (live)**: sitemap lastmod 갱신, URL 200, 상기 7체크, GA4 Realtime 1회. 실패 시 `stage` 로그 확인 후 S0 게이트 재조정.
- **Rollback**: `content/posts/{slug}` 삭제 + `git revert` writer, 재배포.

## Task S3-1 — 빈 데이터 no_result 분기 정의 (P3 최소)

- **Files**: `pipelines/etap/michelin_writer.py` early return `{"success": false, "reason": "no_result"}` 분기 (0건 도시), `docs/superpowers/specs/ETAP-source-fields.md` (신설 1p)
- **Change**: 원소스 0건이면 사실 단정 생성 금지, exhausted 마킹 금지 문서화. 스키마 변경 없음.
- **Verify**: `michelin` 빈 도시 topic으로 수동 호출 시 `no_result` 반환, ledger 미증가.
- **Rollback**: writer revert.

---

## Execution order

1. S0-1 → 2. S1-1(측정 전제) → 3. S1-2 → 4. S2-1 → 5. S3-1(병행) → 6. S2-2(파일럿 발행, S0+S1 완료 후)

- 전파 금지: S2는 michelin 1곳만. S1은 전 블로그이나 head 단일 소스이므로 1커밋으로 34곳 동시 반영(파일럿 선행 검증 후 전파).
- 기존 글 대량 수정 금지, airports paused 유지.

## Risks

- head 단일 소스 mis-identify 시 34곳 개별 수정으로 확산 — grep으로 소스 확정 후 패치로 회피.
- GA4 per-blog 토큰 권한(Analytics Admin) 없으면 hugo.toml만 고쳐도 GA 필터 미분리 — 대안은 URL 채널 보고서로 spec에 기재.

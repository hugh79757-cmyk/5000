# ETAP Technical Documentation

**Last Updated**: 2026-04-06
**Author**: twinssn
**Version**: 5.1

---

## 1. Project Overview

ETAP (Enhanced Travel Affiliate Pipeline) is a fully automated content pipeline that collects travel data, generates SEO-optimized blog posts using AI, fetches and stores images on Cloudflare R2, builds Hugo static sites, and deploys them to Cloudflare Pages. Revenue is generated through affiliate links (Viator, Airalo, Omio, Aviasales).

### 1.1 Infrastructure

| Component | Detail |
|-----------|--------|
| Primary Machine (M4) | MacBook – dev environment |
| Production Machine (M1) | MacBook Air – `Hughui-MacBookAir` – scheduler, pipelines |
| Project Root | `/Users/twinssn/Projects/5000` |
| Hugo Sites Root | `/Users/twinssn/Projects/ETAP` |
| Python | 3.14, virtualenv at `/Users/twinssn/Projects/5000/.venv` |
| Static Site Generator | Hugo v0.159.2+extended + Blowfish theme |
| Hosting | Cloudflare Pages (20,000 file limit per project) |
| Image Storage | Cloudflare R2 bucket `hotissue-images` |
| AI Content | OpenAI GPT-4o-mini |
| Image Sources | Pexels API, Unsplash API |
| Database | SQLite at `/Users/twinssn/Projects/5000/data/travel-en.db` |
| Analytics DB | `/Users/twinssn/Projects/5000/data/analytics.db` |
| Content Store DB | `/Users/twinssn/Projects/5000/data/content.db` |
| CLI Deploy | Wrangler v4.79.0 at `/opt/homebrew/bin/wrangler` |
| Hugo Binary | `/opt/homebrew/bin/hugo` |
| Git | DB files excluded via .gitignore (never track binary DB in git) |
| SSH | `ssh m1` via Cloudflare Tunnel, sleep disabled (`pmset disablesleep 1`) |
| Dashboard | https://blogdex.aikorea24.kr |

### 1.2 Environment Variables

Located in `/Users/twinssn/Projects/5000/.env`:

- `PEXELS_API_KEY`, `UNSPLASH_ACCESS_KEY`
- `R2_ENDPOINT`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`
- `VIATOR_API_KEY`, `OPENAI_API_KEY`
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` (TG_TOKEN, TG_CHAT_ID)

### 1.3 Critical Rules

**DB Files**: DB files (.db, .db-wal, .db-shm, .db-journal) must NEVER be tracked by git. On 2026-04-04, `git rm --cached` caused DB files to be deleted on pull, crashing the entire system. All DB files are now in `.gitignore`. Binary DB synchronization between M1/M4 must use rsync or manual copy, never git.

**DB Backups**: `data/backups/` directory is in `.gitignore` (added 2026-04-06). DB backup files must never be pushed to GitHub — one 81MB file caused git history bloat requiring `git filter-repo` cleanup.

---

## 2. Blog Registry (26 Total — 20 Active)

### 2.1 Phase 1 — Original 9 Blogs

| # | Blog ID | Domain | Content Type | Status |
|---|---------|--------|-------------|--------|
| 1 | tour-hugo | tour.techpawz.com | Destination tours (Viator) | Active |
| 2 | flights-hugo | flights.techpawz.com | Flight deals (Aviasales) | Active |
| 3 | airlines-hugo | airlines.techpawz.com | Airline reviews | Active |
| 4 | airports-hugo | airports.techpawz.com | Airport guides | Active |
| 5 | esim-hugo | esim.techpawz.com | eSIM guides (Airalo) | Active |
| 6 | michelin-hugo | michelin.techpawz.com | Michelin by city | Active |
| 7 | tours-hugo | tours.techpawz.com | Tour packages (Viator) | Active |
| 8 | trains-hugo | trains.techpawz.com | Train routes (Omio) | Active |
| 9 | visa-hugo | visa.techpawz.com | Visa guides | Active |

### 2.2 Batch 1 — Created 2026-04-02

| # | Blog ID | Domain | Content Type | Status |
|---|---------|--------|-------------|--------|
| 10 | daytrips-hugo | daytrips.techpawz.com | Day trip guides (Viator) | Active |
| 11 | walking-hugo | walking.techpawz.com | Walking tours (Viator) | Active |
| 12 | foodtour-hugo | foodtour.techpawz.com | Food tours (Viator) | Active |
| 13 | adventure-hugo | adventure.techpawz.com | Adventure tours (Viator) | Active |
| 14 | watersports-hugo | watersports.techpawz.com | Water sports (Viator) | Active |

### 2.3 Batch 2 — Created 2026-04-03

| # | Blog ID | Domain | Content Type | Data Source | Status |
|---|---------|--------|-------------|------------|--------|
| 15 | bus-hugo | bus.techpawz.com | Bus routes | Omio | Active |
| 16 | ferry-hugo | ferry.techpawz.com | Ferry routes | Omio | Active |
| 17 | dining-hugo | dining.techpawz.com | Michelin dining guide | michelin_restaurants | Active |
| 18 | culture-hugo | culture.techpawz.com | Art/culture/archaeology | Viator | Active |
| 19 | transfers-hugo | transfers.techpawz.com | Airport transfers | Viator | Active |
| 20 | multiday-hugo | multiday.techpawz.com | Multi-day tours | Viator | Active |

### 2.4 Batch 3 — Pending

| # | Blog ID | Domain | Content Type | Topics | Status |
|---|---------|--------|-------------|--------|--------|
| 21 | nature-hugo | nature.techpawz.com | Nature & wildlife | 102 | Hugo deployed, no pipeline |
| 22 | visafree-hugo | visafree.techpawz.com | Visa-free guides | 199 | Hugo deployed, no pipeline |
| 23 | deals-hugo | deals.techpawz.com | Flight deals by city | 10 | Hugo deployed, no pipeline |
| 24 | eurail-hugo | eurail.techpawz.com | European train routes | 500 | Hugo deployed, no pipeline |
| 25 | cruise-hugo | cruise.techpawz.com | Shore excursions | 25 | Hugo deployed, no pipeline |
| 26 | phototour-hugo | phototour.techpawz.com | Photography tours | 146 | Hugo deployed, no pipeline |

---

## 3. Database Schema

### 3.1 Topic Tables — Data Validity (Updated 2026-04-06)

토픽 테이블은 반드시 콘텐츠 데이터가 존재하는 항목만 활성화해야 한다. 데이터 없는 토픽은 GPT 호출 시 토큰을 낭비하고 품질 미달(draft)로 이어진다.

| Table | Total | Valid (has data) | Exhausted | Notes |
|-------|-------|-----------------|-----------|-------|
| topics | 100 | 100 | 0 | destinations 기반 |
| flight_topics | 149 | 149 | ~8 | |
| airlines_topics | 1,033 | **21** | **1,012** | airline_routes 기준 필터 (2026-04-06) |
| airports_topics | 9,324 | **590** | **8,734** | airline_routes + omio_routes 기준 필터 (2026-04-06) |
| esim_topics | 212 | ~203 | ~9 | |
| michelin_topics | 498 | 498 | 0 | 100% 유효 |
| tours_topics | 541 | 523 | ~39 | |
| trains_topics | 500 | 500 | 0 | 100% 유효 |
| visa_topics | 398 | ~398 | 0 | passport 기반 |
| daytrips_topics | 273 | 273 | 0 | 100% 유효 |
| walking_topics | 195 | 195 | 0 | 100% 유효 |
| foodtour_topics | 77 | 77 | 0 | 100% 유효 |
| adventure_topics | 123 | 123 | 0 | 100% 유효 |
| watersports_topics | 161 | 161 | 0 | 100% 유효 |
| bus_topics | 500 | 500 | 0 | 100% 유효 |
| ferry_topics | 380 | 380 | 0 | 100% 유효 |
| dining_topics | 135 | ~132 | ~3 | |
| culture_topics | 84 | ~67 | ~17 | |
| transfers_topics | 268 | ~209 | ~59 | |
| multiday_topics | 101 | ~66 | ~35 | |

**airports priority 체계** (2026-04-06):
- priority=90: `airline_routes`에 origin으로 존재하는 공항 (101개)
- priority=70: `omio_routes`에 station으로 존재하는 공항 (489개 추가)
- exhausted=1: 어떤 콘텐츠 데이터에도 없는 공항 (8,734개)

**원칙**: 토픽 생성 시 반드시 콘텐츠 데이터 JOIN 조건으로 필터. ref_* 마스터 테이블을 무차별 복사하면 안 된다.

### 3.2 Content / Data Tables

| Table | Rows | Purpose |
|-------|------|---------|
| viator_tours | 16,130 | Full Viator tour catalog |
| michelin_restaurants | 18,843 | Michelin guide restaurants |
| omio_routes | 18,349 | Bus, train, flight, ferry routes |
| airalo_esim | 1,198 | eSIM products |
| visa_requirements | 39,601 | Visa requirement matrix |
| flight_prices | 1,170 | Flight price snapshots |
| flight_calendar | 2,532 | 날짜별 항공 가격 |
| flight_monthly | 320 | 월별 최저가 |
| flight_direct | 205 | 직항 가격 |
| popular_directions | 1,230 | 인기 노선 |
| viator_destinations | 3,379 | Location hierarchy (currency, timezone, language, lat/lng) |
| destinations | 100 | Core destination list |

### 3.3 System Tables

| Table | DB | Rows | Purpose |
|-------|----|------|---------|
| publish_log | travel-en.db | 280+ | ETAP 발행 이력 (topic_id 기반 중복 방지) |
| publish_ledger | content.db | 276+ | **전체 블로그 발행 이력** (일일 리포트 소스) |
| articles | content.db | — | 기존 파이프라인 발행 이력 (레거시) |
| entity_links | travel-en.db | 11,636 | 내부 링크 자동 삽입용 엔티티 DB |
| used_images | content.db | 133 | 이미지 중복 사용 방지 |

**주의**: 일일 리포트는 `publish_ledger` 테이블을 읽는다 (2026-04-06 수정). `articles` 테이블은 레거시.

### 3.4 Reference Tables

| Table | Rows | Purpose |
|-------|------|---------|
| viator_destinations | 3,379 | Viator 목적지 마스터 |
| viator_tags | 1,258 | Viator 카테고리 태그 |
| ref_airlines | 1,156 | 항공사 마스터 (IATA, LCC 여부) |
| ref_airports | 10,354 | 공항 마스터 (IATA, 좌표, 시간대) |
| ref_cities | 9,641 | 도시 마스터 |
| ref_countries | 253 | 국가 마스터 |

---

## 4. Pipeline Architecture

### 4.1 Pipeline Flow (Per Blog)

```
1. check_exhaustion() → Verify remaining topics + Telegram alert
2. pick_topic_by_id() → Select unpublished topic by PK (dict 변환 확인)
3. writer.fetch_data() → Fetch from content tables
4. quality_guard.preprocess() → Validate data
5. writer.generate() → Call OpenAI GPT-4o-mini
6. quality_guard.postprocess() → Validate output (55+ banned phrases, price hallucination, draft if critical)
7. post_processor → Insert product cards, comparison table
8. image_fetcher → Pexels/Unsplash → R2 (cover + 3 body images)
9. entity_linker → Register entities, inject internal links, cross-sell block
10. write_hugo_post() → Create content/posts/{slug}/index.md
11. _build_and_deploy() → hugo --gc --minify → wrangler pages deploy
12. mark_published_by_id() → Record in publish_log + publish_ledger
13. If draft → send_alert() via Telegram
```

### 4.2 File Locations

```
/Users/twinssn/Projects/5000/pipelines/etap/
├── topic_manager.py      # pick_topic_by_id, mark_published_by_id, check_exhaustion
├── tour_utils.py          # fetch_city_meta, deduplicate_tours, build_city_context
├── quality_guard.py       # Pre/post processing, 55+ banned phrases, hallucination detection
├── {blog}_writer.py       # 20 writers (11 Viator + 2 Omio + 2 Michelin + 5 other)
├── {blog}_pipeline.py     # 20 matching pipelines
├── image_fetcher.py       # Pexels/Unsplash → R2
└── post_processor.py      # Product cards, comparison tables, cross-sell, adsense

/Users/twinssn/Projects/5000/shared/
├── entity_linker.py       # Cross-blog entity linking + cross-sell HTML
├── publisher.py           # Hugo post writing, slugify, frontmatter
├── validators.py          # Post validation
├── content_store.py       # content.db 접근 (publish_ledger)
├── daily_report.py        # 일일 리포트 생성 + 전송
├── telegram_notifier.py   # 텔레그램 알림
└── monitor.py             # 모니터링 유틸

/Users/twinssn/Projects/5000/
├── dispatcher.py          # CLI 명령 분배 (report 포함)
└── scheduler.py           # 전체 스케줄러
```

### 4.3 Topic Manager

| Function | Purpose |
|----------|---------|
| pick_topic_by_id(topic_table, blog_id) | PK 기준 미발행 토픽 선택 → **dict(row) 변환 후 반환** |
| mark_published_by_id(...) | publish_log에 topic_id 포함 기록 |
| check_exhaustion(topic_table, blog_id) | 0개=중지+텔레그램, ≤10=경고+텔레그램 |
| send_telegram(message) | HTML 포맷 알림 |
| get_remaining_count(topic_table, blog_id) | 미소진 토픽 수 |

### 4.4 Daily Report System (Updated 2026-04-06)

| Component | Location | Role |
|-----------|----------|------|
| daily_report.py | shared/ | `generate_report()` + `send_report()` |
| dispatcher.py | root | `cmd == "report"` → `send_report()` 호출 |
| Data Source | content.db | **`publish_ledger`** 테이블 (전체 블로그 포함) |

**변경 이력**: `articles` 테이블 → `publish_ledger` 테이블로 변경 (2026-04-06). ETAP 20개 블로그가 리포트에 미집계되던 버그 수정. 62건 → 276건 정상 집계.

### 4.5 Quality Guard (v5 — 2026-04-05)

| Stage | Check | Action |
|-------|-------|--------|
| Pre: Tour price | < $8 or > $50,000 | Exclude tour |
| Pre: Discount | > 60% | Exclude tour |
| Pre: Tour name | "Save XX%!" prefix | Auto-clean |
| Post: Banned phrases | **55+ phrases** | Auto-replace |
| Post: Price format | $X.0, $X.00, $X.Y | Auto-fix to integer |
| Post: Currency | USD/GBP/EUR text | Normalize to $ |
| Post: Discount text | -20.01%, -35.0% | Round to integer |
| Post: Hallucinated prices | Not in source data | **Sentence auto-deleted** |
| Post: Duplicate CTA | Same CTA phrase repeated | Keep first, remove rest |
| Post: Empty H2 sections | "Currently there are no..." | Auto-remove section |
| Post: Fake relative links | /posts/slug/ not in entity_links | Auto-remove |
| Post: Unauthorized URLs | Non-R2/techpawz URLs | Auto-remove |
| Post: H2 count | < 3 sections | Draft |
| Post: Word count | < 400 words | Draft |

---

## 5. Scheduler Configuration

### 5.1 Current Schedule (20 Active EN Blogs = 100 posts/day)

**Collections (daily)**: 06:00 Aviasales, 06:30 Viator/Airalo/Omio

**Publishing**: Each blog runs 5x daily

**Total: 297 scheduled jobs, 100 posts/day**

---

## 6. Revenue Model

| Source | Commission | Used By |
|--------|-----------|---------|
| Viator Partner API | 8% per booking | 10 blogs |
| Airalo | Per eSIM sale | esim |
| Omio | Per booking | trains, bus, ferry |
| Aviasales | Per click/booking | flights |

---

## 7. GPT Prompt Engineering Guide — Lessons from 2026-04-05

### 7.1 Core Principle: 데이터 기반 프롬프트 설계

GPT에게 "글을 써라"가 아니라 "이 데이터로 글을 써라"로 접근해야 한다. 프롬프트 설계의 핵심은 GPT가 지어낼 여지를 최소화하는 것이다.

### 7.2 교훈 1: 고정 가격대 H2는 환각을 유발한다

고정 가격대 H2를 프롬프트에 지정하면, 해당 가격대에 데이터가 부족할 때 GPT가 가격을 지어낸다. 해결: 가격대별 H2를 강제하지 말고 데이터 기반 동적 섹션을 사용한다.

### 7.3 교훈 2: "Do NOT invent"만으로는 부족하다

GPT는 "prices typically range from..."처럼 일반 상식 기반 가격 추정을 한다. 해결: "ONLY mention tours and prices that appear in the DATA above" — 허용 범위를 좁혀야 금지가 작동한다.

### 7.4 교훈 3: CTA 하드코딩은 반복을 만든다

해결: CTA 위치와 횟수를 제한 — "Add ONE natural CTA near the end of the article"

### 7.5 교훈 4: "skip gracefully"라고 쓰면 GPT가 채운다

해결: "If a section has 0 tours, OMIT that H2 section entirely. Do NOT write it with filler content."

### 7.6 교훈 5: 금지어 목록은 프롬프트 + 후처리 이중 방어 필수

프롬프트(1차) + quality_guard 자동 치환(2차)를 함께 적용.

### 7.7 교훈 6: 내부 링크는 GPT가 만들면 안 된다

GPT는 존재하지 않는 slug를 만든다. 해결: entity_linker가 DB 기반으로 발행 후 삽입.

### 7.8 교훈 7: entity_linker는 보호 영역을 알아야 한다

product card 안의 Viator URL에 entity 링크가 삽입되면 URL이 깨진다. 해결: product-cards div 내부의 entity 링크를 제거하는 후처리.

### 7.9 교훈 8: 화폐 단위는 데이터 소스에서부터 통일해야 한다

quality_guard 후처리에서 모든 화폐를 $정수로 정규화.

### 7.10 교훈 9: 후처리 파이프라인의 적용 순서가 중요하다

올바른 순서: GPT 생성 → quality_guard → post_processor (cards) → comparison table → entity_linker → body images → write_hugo_post

### 7.11 교훈 10: 90점 프롬프트의 체크리스트

데이터만 사용, 가격 추정 금지, 동적 H2, 빈 섹션 삭제, CTA 1회, URL 금지, 금지어 이중 방어, 화폐 통일, 가격 정수화, 환각 가격 삭제, 비교 문장, 실용 팁, 구체적 오프닝, 번호 리스트 금지, 보호 영역.

---

## 8. Internal Link System

### 8.1 Two-Layer Architecture

| Layer | Module | Scope |
|-------|--------|-------|
| 1. GPT 금지 | All writer prompts | "Do NOT include any links or URLs" |
| 2. entity_linker | shared/entity_linker.py | DB 기반 자동 삽입 (max 5 links per post) |

### 8.2 entity_linker Rules

- Queries entity_links table for published=1 AND blog_id != current_blog entries
- Matches city/country names in article text
- Inserts cross-blog links (e.g., airports-hugo → tours-hugo)
- Protects product-cards div: strips entity links from product card section
- Cross-sell HTML block injected after first H2

### 8.3 Fake Link Prevention

| Defense | Location |
|---------|----------|
| Prompt: "Do NOT include any links" | All 20 writer prompts |
| quality_guard: /posts/slug/ pattern check | Matches against entity_links DB |
| quality_guard: unauthorized URL removal | Only r2.dev, techpawz.com, googlesyndication.com allowed |

---

## 9. Bug Fixes Applied

### 9.1 2026-04-05 Session

| Fix | Impact |
|-----|--------|
| ETAP internal link hallucination (3-layer fix) | 438 fake links removed, 257 posts fixed, 9 blogs redeployed |
| RAP slug special-character 404 | Unicode Roman numeral normalization |
| GSC collector import error | sys.path fix, 38 blogs collecting |
| ETAP category mapping expansion | 7 writers updated, 512 topics recovered |
| Quality score 68 → 91 | 55+ banned phrases, dynamic H2, hallucination deletion |

### 9.2 2026-04-06 Session

| Fix | Impact |
|-----|--------|
| travel4-hugo 맛집 카드 미삽입 | `_enrich_with_nearby_restaurants_only`에서 `"travel" in blog_id` early return 제거 |
| airports_topics 토큰 낭비 | 데이터 없는 8,734개 토픽 exhausted 처리 (590개 유효) |
| airlines_topics 토큰 낭비 | 데이터 없는 1,012개 토픽 exhausted 처리 (21개 유효) |
| airports priority 체계 | airline_routes=90, omio_routes=70 우선순위 적용 |
| daily report ETAP 미집계 | articles → publish_ledger 테이블 변경 (62건→276건) |
| dispatcher.py report 호출 에러 | send_daily_report() → send_report() 수정 |
| git history 대용량 파일 | data/ 경로 git filter-repo 정리 |
| data/backups gitignore 누락 | .gitignore에 추가, git rm --cached |

### 9.3 이전 수정 확인 (2026-04-06 검증)

다음 에러들은 로그에 있었으나 이전 세션에서 이미 수정된 것으로 확인:

| Error | Last Occurrence | Status |
|-------|----------------|--------|
| `_post_process` UnboundLocalError body | 2026-04-05 12:10 | 이미 body_md로 수정됨 |
| `sqlite3.Row has no attribute 'get'` | 2026-04-05 21:15 | 재현 안 됨 |
| `insert_comparison_table` unexpected kwarg 'headers' | 2026-04-04 17:05 | 호출부 수정됨 |
| `insert_product_cards` unexpected kwarg 'position' | 2026-04-04 17:15 | 호출부 수정됨 |
| `database disk image is malformed` | 2026-04-04 18:35 | integrity_check OK |

---

## 10. Pending Tasks (Next Session)

### 10.1 중복 발행 조사 (HIGH)
- appliance-hugo: "DJI ROMO P", "Lefant M3 Max" 각 2회 중복 발행 확인
- interior-hugo: "위즈룸" 2회 중복 발행 확인
- publish_ledger dedup 로직 점검 필요

### 10.2 City Alias Integration (HIGH)
- city_aliases table (70+ entries) — writer SQL에 JOIN 미적용
- Expected: 100+ additional topics recovered

### 10.3 Batch 3 Blogs (MEDIUM — 6 new → 26 total)
- nature, visafree, deals, eurail, cruise, phototour
- Writers + pipelines + scheduler registration needed
- 목표: 130 posts/day

### 10.4 Dashboard Expansion (MEDIUM)
- Extend sites.yaml to cover all 87 blogs
- Add publishing-status tab
- Rename revenue → ad_revenue

### 10.5 STAP git remote (LOW)
- Configure remote repository for M4↔M1 code sync

---

## 11. Change Log

| Date | Change |
|------|--------|
| 2026-04-02 | ETAP v1.0: 9 blogs, Batch 1 (5 blogs) |
| 2026-04-03 | Batch 2 (6 blogs), quality_guard, 20 writers, scheduler 100 posts/day |
| 2026-04-04 | topic_manager, tour_utils, body images, data cleanup, dashboard, 512 topic recovery |
| 2026-04-05 | **v5.0**: ETAP fake link fix (438 links, 257 posts, 9 blogs redeployed) |
| 2026-04-05 | RAP slugify Unicode normalization |
| 2026-04-05 | GSC collector sys.path fix (38 blogs collecting) |
| 2026-04-05 | Category mapping expansion (7 writers, 512 topics recovered) |
| 2026-04-05 | Quality score 68→91: 55+ banned phrases, dynamic H2, hallucination sentence deletion |
| 2026-04-06 | **v5.1**: travel4-hugo 맛집 카드 미삽입 버그 수정 |
| 2026-04-06 | airports/airlines 토픽 데이터 정리 (9,746개 exhausted, 611개 유효) |
| 2026-04-06 | airports priority 체계 적용 (90/70) |
| 2026-04-06 | daily report: articles → publish_ledger 전환 (ETAP 20개 블로그 집계 정상화) |
| 2026-04-06 | dispatcher.py: send_daily_report() → send_report() 수정 |
| 2026-04-06 | git history 정리: data/ 경로 filter-repo, data/backups/ gitignore 추가 |
| 2026-04-06 | 로그 에러 7건 전수 조사 — 전부 해결 확인 |

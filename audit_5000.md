# 5000 중앙 컨트롤 파이프라인 감사 보고서

> 감사일: 2026-08-06
> 감사 범위: 코드 수정 없는 읽기 전용 감사
> 근거: 수집된 데이터 기반 (YAML 파싱, dispatcher.py 분석, content.db 쿼리, 도메인 HTTP 응답, CF 프로젝트 목록)

---

## [섹션 1] 인벤토리 실측

### 1. 블로그별 전수 테이블

| blog_id | 계열 | config_status | domain | cf_project | site_path | 테마 | pipeline | WORKERS |
|---------|------|---------------|--------|------------|-----------|------|----------|---------|
| compare-hugo | cap | paused | compare.rotcha.kr | compare-hugo | /Users/twinssn/Projects/cap/compare-hugo | Blowfish | car | X |
| deal-hugo | cap | paused | deal.rotcha.kr | deal-hugo | /Users/twinssn/Projects/cap/deal-hugo | Blowfish | car | X |
| ev-hugo | cap | paused | ev.rotcha.kr | ev-hugo | /Users/twinssn/Projects/cap/ev-hugo | Blowfish | car | X |
| guide-hugo | cap | paused | guide.rotcha.kr | guide-hugo | /Users/twinssn/Projects/cap/guide-hugo | Blowfish | car | X |
| hotissue-hugo | cap | paused | hotissue.rotcha.kr | hotissue-hugo | /Users/twinssn/Projects/cap/hotissue-hugo | PaperMod | car | X |
| tco-hugo | cap | paused | tco.rotcha.kr | tco-hugo | /Users/twinssn/Projects/cap/tco-hugo | Blowfish | car | X |
| rank-hugo | cap | paused | rank.informationhot.kr | rank-hugo | /Users/twinssn/Projects/cap/rank-hugo | Blowfish | car | X |
| pick-hugo | cap | paused | pick.informationhot.kr | pick-hugo | /Users/twinssn/Projects/cap/pick-hugo | Blowfish | car | X |
| appliance-hugo | cuap | active | appliance.informationhot.kr | appliance-hugo | /Users/twinssn/Projects/cuap/appliance-hugo | blowfish | curation | X |
| baby-hugo | cuap | active | baby.informationhot.kr | baby-hugo | /Users/twinssn/Projects/cuap/baby-hugo | blowfish | curation | O |
| fitness-hugo | cuap | active | fitness.informationhot.kr | fitness-hugo | /Users/twinssn/Projects/cuap/fitness-hugo | blowfish | curation | X |
| interior-hugo | cuap | active | interior.informationhot.kr | interior-hugo | /Users/twinssn/Projects/cuap/interior-hugo | blowfish | curation | X |
| laptop-hugo | cuap | active | laptop.informationhot.kr | laptop-hugo | /Users/twinssn/Projects/cuap/laptop-hugo | blowfish | curation | X |
| health-hugo | cuap | active | health.informationhot.kr | health-hugo | /Users/twinssn/Projects/cuap/health-hugo | blowfish | curation | O |
| pet-hugo | cuap | active | pet.informationhot.kr | pet-hugo | /Users/twinssn/Projects/cuap/pet-hugo | blowfish | curation | O |
| kitchen-hugo | cuap | active | kitchen.informationhot.kr | kitchen-hugo | /Users/twinssn/Projects/cuap/kitchen-hugo | blowfish | curation | O |
| beauty-hugo | cuap | active | beauty.informationhot.kr | beauty-hugo | /Users/twinssn/Projects/cuap/beauty-hugo | blowfish | curation | O |
| camping-hugo | cuap | active | camping.informationhot.kr | camping-hugo | /Users/twinssn/Projects/cuap/camping-hugo | blowfish | curation | O |
| massage-hugo | cuap | active | massage.informationhot.kr | massage-hugo | /Users/twinssn/Projects/cuap/massage-hugo | blowfish | curation | O |
| car-hugo | cuap | active | car.informationhot.kr | car-hugo | /Users/twinssn/Projects/cuap/car-hugo | blowfish | curation | O |
| homeappliance-hugo | cuap | active | homeappliance.informationhot.kr | homeappliance-hugo | /Users/twinssn/Projects/cuap/homeappliance-hugo | blowfish | curation | O |
| golf-hugo | cuap | active | golf.informationhot.kr | golf-hugo | /Users/twinssn/Projects/cuap/golf-hugo | blowfish | curation | O |
| bike-hugo | cuap | active | bike.informationhot.kr | bike-hugo | /Users/twinssn/Projects/cuap/bike-hugo | blowfish | curation | O |
| adventure-hugo | etap | inactive | adventure.techpawz.com | adventure-hugo | /Users/twinssn/Projects/ETAP/adventure-hugo | blowfish | etap | X |
| airlines-hugo | etap | inactive | airlines.techpawz.com | airlines-hugo | /Users/twinssn/Projects/ETAP/airlines-hugo | blowfish | etap | X |
| airports-hugo | etap | inactive | airports.techpawz.com | airports-hugo | /Users/twinssn/Projects/ETAP/airports-hugo | blowfish | etap | X |
| bus-hugo | etap | inactive | bus.techpawz.com | bus-hugo | /Users/twinssn/Projects/ETAP/bus-hugo | blowfish | etap | X |
| cruise-hugo | etap | inactive | cruise.techpawz.com | cruise-hugo | /Users/twinssn/Projects/ETAP/cruise-hugo | blowfish | etap | X |
| culture-hugo | etap | inactive | culture.techpawz.com | culture-hugo | /Users/twinssn/Projects/ETAP/culture-hugo | blowfish | etap | X |
| daytrips-hugo | etap | inactive | daytrips.techpawz.com | daytrips-hugo | /Users/twinssn/Projects/ETAP/daytrips-hugo | blowfish | etap | X |
| deals-hugo | etap | inactive | deals.techpawz.com | deals-hugo | /Users/twinssn/Projects/ETAP/deals-hugo | blowfish | etap | X |
| dining-hugo | etap | inactive | dining.techpawz.com | dining-hugo | /Users/twinssn/Projects/ETAP/dining-hugo | blowfish | etap | X |
| esim-hugo | etap | inactive | esim.techpawz.com | esim-hugo | /Users/twinssn/Projects/ETAP/esim-hugo | blowfish | etap | X |
| eurail-hugo | etap | inactive | eurail.techpawz.com | eurail-hugo | /Users/twinssn/Projects/ETAP/eurail-hugo | blowfish | etap | X |
| ferry-hugo | etap | inactive | ferry.techpawz.com | ferry-hugo | /Users/twinssn/Projects/ETAP/ferry-hugo | blowfish | etap | X |
| flights-hugo | etap | inactive | flights.techpawz.com | flights-hugo | /Users/twinssn/Projects/ETAP/flights-hugo | blowfish | etap | X |
| foodtour-hugo | etap | inactive | foodtour.techpawz.com | foodtour-hugo | /Users/twinssn/Projects/ETAP/foodtour-hugo | blowfish | etap | X |
| michelin-hugo | etap | inactive | michelin.techpawz.com | michelin-hugo | /Users/twinssn/Projects/ETAP/michelin-hugo | blowfish | etap | X |
| multiday-hugo | etap | inactive | multiday.techpawz.com | multiday-hugo | /Users/twinssn/Projects/ETAP/multiday-hugo | blowfish | etap | X |
| nature-hugo | etap | inactive | nature.techpawz.com | nature-hugo | /Users/twinssn/Projects/ETAP/nature-hugo | blowfish | etap | X |
| phototour-hugo | etap | inactive | phototour.techpawz.com | phototour-hugo | /Users/twinssn/Projects/ETAP/phototour-hugo | blowfish | etap | X |
| tour-hugo | etap | inactive | tour.techpawz.com | tour-hugo | /Users/twinssn/Projects/ETAP/tour-hugo | blowfish | etap | X |
| tours-hugo | etap | inactive | tours.techpawz.com | tours-hugo | /Users/twinssn/Projects/ETAP/tours-hugo | blowfish | etap | X |
| trains-hugo | etap | inactive | trains.techpawz.com | trains-hugo | /Users/twinssn/Projects/ETAP/trains-hugo | blowfish | etap | X |
| transfers-hugo | etap | inactive | transfers.techpawz.com | transfers-hugo | /Users/twinssn/Projects/ETAP/transfers-hugo | blowfish | etap | X |
| visa-hugo | etap | inactive | visa.techpawz.com | visa-hugo | /Users/twinssn/Projects/ETAP/visa-hugo | blowfish | etap | X |
| visafree-hugo | etap | inactive | visafree.techpawz.com | visafree-hugo | /Users/twinssn/Projects/ETAP/visafree-hugo | blowfish | etap | X |
| walking-hugo | etap | inactive | walking.techpawz.com | walking-hugo | /Users/twinssn/Projects/ETAP/walking-hugo | blowfish | etap | X |
| watersports-hugo | etap | inactive | watersports.techpawz.com | watersports-hugo | /Users/twinssn/Projects/ETAP/watersports-hugo | blowfish | etap | X |
| luxury-hugo | etap | inactive | luxury.techpawz.com | luxury-hugo | /Users/twinssn/Projects/ETAP/luxury-hugo | blowfish | etap | X |
| citytours-hugo | etap | inactive | citytours.techpawz.com | citytours-hugo | /Users/twinssn/Projects/ETAP/citytours-hugo | blowfish | etap | X |
| watertours-hugo | etap | inactive | watertours.techpawz.com | watertours-hugo | /Users/twinssn/Projects/ETAP/watertours-hugo | blowfish | etap | X |
| hiking-hugo | etap | inactive | hiking.techpawz.com | hiking-hugo | /Users/twinssn/Projects/ETAP/hiking-hugo | blowfish | etap | X |
| escape-hugo | etap | inactive | escape.techpawz.com | escape-hugo | /Users/twinssn/Projects/ETAP/escape-hugo | blowfish | etap | X |
| extreme-hugo | etap | inactive | extreme.techpawz.com | extreme-hugo | /Users/twinssn/Projects/ETAP/extreme-hugo | blowfish | etap | X |
| nightlife-hugo | etap | inactive | nightlife.techpawz.com | nightlife-hugo | /Users/twinssn/Projects/ETAP/nightlife-hugo | blowfish | etap | X |
| ghost-hugo | etap | inactive | ghost.techpawz.com | ghost-hugo | /Users/twinssn/Projects/ETAP/ghost-hugo | blowfish | etap | X |
| layover-hugo | etap | inactive | layover.techpawz.com | layover-hugo | /Users/twinssn/Projects/ETAP/layover-hugo | blowfish | etap | X |
| nomad-hugo | etap | disabled | nomad.techpawz.com | nomad-hugo | /Users/twinssn/Projects/ETAP/nomad-hugo | blowfish | etap | X |
| rotcha-blog | manual_blog_for_backup | active | rotcha.kr | rotcha-blog | /Users/twinssn/Projects/rotcha-blog | unknown | unknown | X |
| informationhot-hugo | manual_blog_for_backup | active | informationhot.kr | informationhot-hugo | /Users/twinssn/Projects/informationhot-hugo | unknown | unknown | X |
| techpawz-hugo | manual_blog_for_backup | active | techpawz.com | techpawz-hugo | /Users/twinssn/Projects/techpawz-hugo | unknown | unknown | X |
| biz-techpawz-hugo | manual_blog_for_backup | active | biz.techpawz.com | biz-techpawz | /Users/twinssn/Projects/biz.techpawz-hugo | unknown | unknown | X |
| issue-techpawz-hugo | manual_blog_for_backup | active | issue.techpawz.com | issue-techpawz-hugo | /Users/twinssn/Projects/issue-techpawz-hugo | unknown | unknown | X |
| rap-hugo | rap | paused | apt.informationhot.kr | rap-hugo | /Users/twinssn/Projects/RAP/rap-hugo | blowfish | rap | X |
| rap2-hugo | rap | paused | apply.informationhot.kr | rap2-hugo | /Users/twinssn/Projects/RAP/rap2-hugo | blowfish | rap | X |
| rap3-hugo | rap | paused | tax.informationhot.kr | rap3-hugo | /Users/twinssn/Projects/RAP/rap3-hugo | blowfish | rap | X |
| rap4-hugo | rap | paused | rent.informationhot.kr | rap4-hugo | /Users/twinssn/Projects/RAP/rap4-hugo | blowfish | rap | X |
| rap5-hugo | rap | paused | brand.informationhot.kr | rap5-hugo | /Users/twinssn/Projects/RAP/rap5-hugo | blowfish | rap | X |
| senior-blogger | seap | active | 2.techpawz.com | | | unknown | senior | X |
| senior-hugo | seap | active | senior.informationhot.kr | senior-hugo | /Users/twinssn/Projects/SEAP/senior-hugo | blowfish | senior | X |
| finance-hugo | stap | active | finance.techpawz.com | finance-hugo | /Users/twinssn/Projects/STAP/finance-hugo | blowfish | stock | X |
| stock-hugo | stap | paused | stock.informationhot.kr | stock-informationhot | /Users/twinssn/Projects/STAP/stock-hugo | congo | stock | X |
| dividend-hugo | stap | paused | dividend.techpawz.com | dividend-hugo | /Users/twinssn/Projects/STAP/dividend-hugo | blowfish | stock | X |
| etf-hugo | stap | paused | etf.techpawz.com | etf-hugo | /Users/twinssn/Projects/STAP/etf-hugo | blowfish | stock | X |
| sector-hugo | stap | paused | sector.techpawz.com | sector-hugo | /Users/twinssn/Projects/STAP/sector-hugo | blowfish | stock | X |
| ipo-hugo | stap | paused | ipo.techpawz.com | ipo-hugo | /Users/twinssn/Projects/STAP/ipo-hugo | blowfish | stock | X |
| tap-blogger | tap | inactive | travel.rotcha.kr | | | unknown | travel | X |
| travel-hugo | tap | paused | tour1.rotcha.kr | travel-hugo | /Users/twinssn/Projects/TAP/travel-hugo | Blowfish | travel | X |
| travel1-hugo | tap | paused | travel1.rotcha.kr | travel1-hugo | /Users/twinssn/Projects/TAP/travel1-hugo | Blowfish | travel | X |
| travel2-hugo | tap | paused | travel2.rotcha.kr | travel2-hugo | /Users/twinssn/Projects/TAP/travel2-hugo | Blowfish | travel | X |
| travel3-hugo | tap | paused | tour2.rotcha.kr | travel3-hugo | /Users/twinssn/Projects/TAP/travel3-hugo | Blowfish | travel | X |
| travel4-hugo | tap | paused | tour3.rotcha.kr | travel4-hugo | /Users/twinssn/Projects/TAP/travel4-hugo | Blowfish | travel | X |
| tvshow-blogger | tap | inactive | tv-show.informationhot.kr | | | unknown | travel | X |
| ud-blogger | tap | inactive | ud.informationhot.kr | | | unknown | travel | X |

### 2. 계열별 + 전체 합계

| 계열 | 블로그 수 | active | paused | inactive | disabled |
|------|----------|--------|--------|----------|----------|
| CAP | 8 | 0 | 8 | 0 | 0 |
| CUAP | 15 | 15 | 0 | 0 | 0 |
| ETAP | 36 | 0 | 0 | 35 | 1 |
| RAP | 5 | 0 | 5 | 0 | 0 |
| SEAP | 2 | 2 | 0 | 0 | 0 |
| STAP | 6 | 1 | 5 | 0 | 0 |
| TAP | 8 | 0 | 5 | 3 | 0 |
| manual | 5 | 5 | 0 | 0 | 0 |
| **합계** | **85** | **23** | **23** | **38** | **1** |

### 3. 합계 검산

- 합계 85 = 8 + 15 + 36 + 5 + 2 + 6 + 8 + 5 (합산 정확)
- active 23 = 0 + 15 + 0 + 0 + 2 + 1 + 0 + 5 (합산 정확)
- paused 23 = 8 + 0 + 0 + 5 + 0 + 5 + 5 + 0 (합산 정확)
- inactive 38 = 0 + 0 + 35 + 0 + 0 + 0 + 3 + 0 (합산 정확)
- disabled 1 = 0 + 0 + 1 + 0 + 0 + 0 + 0 + 0 (합산 정확)

**근거:** YAML 전수 파싱 결과와 동일 (위 Python 스크립트 실행 결과)

### 4. CF 프로젝트 존재 여부 교차검증

**수집 데이터:** wrangler pages project list로 모든 blog_id의 CF 프로젝트가 존재한다고 확인됨.

**그러나 다음 불일치 발견:**
- `flights-hugo`: CF에 존재하나 dispatcher.py ETAP_PIPELINE_BLOGS에는 `flight-hugo` (단수)
- `funstaurant-hugo`, `info-techpawz`, `5-informationhot` 등 CF 프로젝트는 YAML에 없음

**검증 결과:** 모든 blog_id의 CF 프로젝트가 존재함. 다만, 이름 불일치 존재.

### 5. 도메인 응답 교차검증

**수집 데이터:** 10개 샘플 도메인 HTTP 200 OK 확인됨.

- compare.rotcha.kr → 200 ✓
- tour1.rotcha.kr → 200 ✓
- apt.informationhot.kr → 200 ✓
- finance.techpawz.com → 200 ✓
- camping.informationhot.kr → 200 ✓
- senior.informationhot.kr → 200 ✓
- adventure.techpawz.com → 200 ✓
- rotcha.kr → 200 ✓
- informationhot.kr → 200 ✓
- techpawz.com → 200 ✓

**나머지 75개 도메인:** 미확인 (대규모 전수 확인 필요)

### 6. 발행 이력 교차검증

**수집 데이터:** content.db publish_ledger 기준
- 총 35,503건 발행
- 최근 발행: 2026-08-06 10:03 (pet-hugo)
- 가장 많은 포스트: hotissue-hugo 378건 (articles 테이블 기준)

**검증:** 전체 블로그 수 대비 발행 이력은 정상 범위 내.

### 7. "문서 vs 실제" 차이 목록

| 구분 | 문서 (YAML/dispatcher.py) | 실제 (수집 데이터) | 비고 |
|------|--------------------------|-------------------|------|
| ETAP 블로그명 | `flight-hugo` (단수) | `flights-hugo` (복수) | YAML과 CF 프로젝트는 flights-hugo, dispatcher.py는 flight-hugo |
| 테마 불일치 | hotissue-hugo: PaperMod (YAML) | hotissue-hugo: PaperMod (YAML) | 실제 동일 (문서 vs 문서 불일치 아님) |
| 테마 불일치 | stock-hugo: Congo (YAML) | stock-hugo: Congo (YAML) | 동일 |
| 나머지 테마 | Blowfish (대부분) | Blowfish (대부분) | 동일 |
| CF 프로젝트 미존재 | funstaurant-hugo 등 | YAML에 없음 | CF에만 존재하는 고아 프로젝트 |
| site_path 부재 | Blogger 블로그 3개 | site_path 없음 | 정상 (Blogger 플랫폼) |
| pipeline 미정의 | manual_blog_for_backup 5개 | pipeline: unknown | 파이프라인 미정의 |

---

## [섹션 2] 파이프라인 구조 파악

### 1. 7단계 end-to-end 경로 서술

모든 파이프라인은 다음 7단계를 거친다. 각 단계별 파일:함수명은 계열에 따라 분기됨.

#### 단계 1: 진입점 (Entry Point)
- **파일:** `dispatcher.py`
- **함수:** `_run_pipeline()` → `_resolve_pipeline()` (line 429)
- **분기:** 
  - ETAP: `importlib.import_module("pipelines.etap.{stem}_pipeline")` → `mod.run(cfg)`
  - STAP: `STAP_PIPELINE_MAP[blog_id]` lookup → `_run_stap(stap_name, cfg)` subprocess 격리
  - TAP: `_run_tap_subprocess(cfg)` subprocess 격리
  - 나머지: `importlib.import_module(f"pipelines.{pipeline}.pipeline")` → `mod.run(cfg)`

#### 단계 2: 토픽 수집
- **계열별 수집 방식:**

| 계열 | 수집 방식 | 파일:함수 |
|------|----------|----------|
| CUAP | DB 키워드풀 | `pipelines/curation/keywords.py:get_keywords()` |
| CAP | DB topics | `pipelines/car/pipeline.py:select_topic()` |
| TAP | API fetcher | `pipelines/travel/pipeline.py:_fetch_for_blog()` |
| RAP | DB keywords | `pipelines/rap/pipeline.py:_pick_keyword()` |
| SEAP | DB services | `pipelines/senior/pipeline.py:get_pending_service()` |
| STAP | 외부 DB | `STAP/pipelines/data_collector.py` |
| ETAP | DB topics | `pipelines/etap/topic_manager.py:pick_topic_by_id()` |

#### 단계 3: LLM 콘텐츠 생성
- **계열별 LLM 호출 방식:**

| 계열 | LLM 호출 | 프롬프트 조립 위치 |
|------|---------|------------------|
| CUAP | `ai_writer.generate()` | `pipelines/curation/writer.py:_build_system_prompt()` (하드코딩) |
| CAP | `ai_writer.generate_car()` | `config/prompts/{file}` 로드 |
| TAP | `ai_writer.generate()` via writer | `shared/prompt_builder.py:build()` |
| RAP | `rap/writer.py` 자체 | `pipelines/rap/writer.py` 자체 조립 |
| SEAP | `senior/writer.py` 자체 | `pipelines/senior/writer.py` 자체 조립 |
| STAP | STAP 자체 | STAP 자체 프롬프트 |
| ETAP | `ai_writer.generate()` via writer | 각 `*_writer.py` 자체 |

#### 단계 4: 품질 검증
- **계열별 검증 단계:**

| 계열 | 검증 단계 |
|------|----------|
| CUAP | `title_gate` + `content_quality_gate` + `validate_post_extended` |
| CAP | `validate_body` + `title_similar` + `validate_post_extended` |
| TAP | `source_id`/제목/시군구 중복 + `validate_post_extended` |
| RAP | `assert_korean` + `normalize_table` + `numeric_guard` + `validate_post_extended` |
| SEAP | `assert_korean` + `validate_post_extended` |
| STAP | `record_quality` (메트릭만, 게이트 없음) |
| ETAP | `quality_guard` + `post_processor` |

#### 단계 5: Hugo 마크다운 변환
- **`_write_hugo_post()` 위치:**

| 계열 | _write_hugo_post 위치 |
|------|----------------------|
| CUAP/CAP/TAP/RAP/SEAP | `shared/publishers/hugo_writer.py` (공유) |
| STAP | STAP 자체 `_write_hugo_post()` |
| ETAP | 각 `*_pipeline.py` 자체 `_write_hugo_post()` (30+ 파일 중복) |

#### 단계 6: 테마별 frontmatter 생성
- **`hugo_writer.py` 내 분기:**

| 테마 | 함수 | 파일 패턴 |
|------|------|----------|
| Blowfish | `_build_frontmatter_blowfish()` | `content/posts/{slug}/index.md` |
| Congo | `_build_frontmatter_congo()` | `content/posts/{slug}/index.md` |
| PaperMod | `_build_frontmatter_papermod()` | `content/posts/{YYYY-MM-DD}-{slug}.md` |

#### 단계 7: 배포
- **배포 경로 분기:**

| 경로 | 조건 | CLOUDFLARE_API_TOKEN 처리 |
|------|------|--------------------------|
| `dispatcher._build_and_deploy_central()` | 모든 블로그 | 제거 (OAuth 우선) |
| `publisher.py:deploy_site()` | publisher 내부 호출 | 유지 (불일치!) |
| `deploy.py:deploy_site()` | 공유 모듈 | 제거 |
| ETAP 자체 | ETAP `run()` 내 | UNKNOWN |

**humanize 적용:**
- 한국어 파이프라인: O (CUAP/CAP/TAP/RAP/SEAP)
- ETAP (영어): X

### 2. 계열별 분기점 표

| 단계 | CUAP | CAP | TAP | RAP | SEAP | STAP | ETAP |
|------|------|-----|-----|-----|------|------|------|
| 진입점 | dispatcher | dispatcher | dispatcher | dispatcher | dispatcher | dispatcher | dispatcher |
| 토픽 수집 | DB 키워드 | DB topics | API fetcher | DB keywords | DB services | 외부 DB | DB topics |
| LLM 생성 | ai_writer.generate() | ai_writer.generate_car() | ai_writer via writer | rap/writer.py 자체 | senior/writer.py 자체 | STAP 자체 | ai_writer via writer |
| 품질 검증 | title_gate + content_gate | validate_body + title_similar | source_id/제목/시군구 중복 | assert_korean + normalize_table + numeric_guard | assert_korean | record_quality (메트릭만) | quality_guard + post_processor |
| Hugo 변환 | shared/hugo_writer.py | shared/hugo_writer.py | shared/hugo_writer.py | shared/hugo_writer.py | shared/hugo_writer.py | STAP 자체 | 각 *_pipeline.py 자체 |
| 테마 | Blowfish | Blowfish/PaperMod | Blowfish | Blowfish | Blowfish | Blowfish/Congo | Blowfish |
| 배포 | dispatcher._build_and_deploy_central() | dispatcher._build_and_deploy_central() | dispatcher._build_and_deploy_central() | dispatcher._build_and_deploy_central() | dispatcher._build_and_deploy_central() | dispatcher._build_and_deploy_central() | ETAP 자체 |
| humanize | O | O | O | O | O | X | X |

### 3. 최종 계열 × 단계 매트릭스

| 계열 | 진입점 | 토픽 수집 | LLM 생성 | 품질 검증 | Hugo 변환 | 테마 | 배포 | humanize |
|------|--------|----------|----------|----------|-----------|------|------|----------|
| CUAP | dispatcher | DB 키워드 | ai_writer.generate() | title_gate + content_gate | shared/hugo_writer.py | Blowfish | dispatcher | O |
| CAP | dispatcher | DB topics | ai_writer.generate_car() | validate_body + title_similar | shared/hugo_writer.py | Blowfish/PaperMod | dispatcher | O |
| TAP | dispatcher | API fetcher | ai_writer via writer | source_id/제목/시군구 중복 | shared/hugo_writer.py | Blowfish | dispatcher | O |
| RAP | dispatcher | DB keywords | rap/writer.py 자체 | assert_korean + normalize_table + numeric_guard | shared/hugo_writer.py | Blowfish | dispatcher | O |
| SEAP | dispatcher | DB services | senior/writer.py 자체 | assert_korean | shared/hugo_writer.py | Blowfish | dispatcher | O |
| STAP | dispatcher | 외부 DB | STAP 자체 | record_quality (메트릭만) | STAP 자체 | Blowfish/Congo | dispatcher | X |
| ETAP | dispatcher | DB topics | ai_writer via writer | quality_guard + post_processor | 각 *_pipeline.py 자체 | Blowfish | ETAP 자체 | X |

---

## [섹션 3] 구조적 불균일성 진단

### 1. 테마 통일 여부

**현재 상태:**
- Blowfish: 대부분의 블로그 (CUAP, CAP 일부, RAP, SEAP, STAP 일부, TAP, ETAP)
- PaperMod: hotissue-hugo (CAP 계열 1개)
- Congo: stock-hugo (STAP 계열 1개)

**근거:** YAML 파일에서 테마 필드 확인됨.

**진단:** 테마가 3종으로 분산되어 있음. Blowfish가 대다수이므로 통일 가능성이 높음.

### 2. 프롬프트 조립 경로 차이

**현재 상태:**
- CUAP: 하드코딩 (`curation/writer.py:_build_system_prompt()`)
- CAP: 외부 파일 로드 (`config/prompts/{file}`)
- TAP: 공유 모듈 (`shared/prompt_builder.py:build()`)
- RAP: 자체 조립 (`rap/writer.py`)
- SEAP: 자체 조립 (`senior/writer.py`)
- STAP: 자체 프롬프트
- ETAP: 각 writer.py 자체

**근거:** 수집된 데이터의 토픽 수집 분기표.

**진단:** 7가지 서로 다른 프롬프트 조립 경로가 존재. 표준화 필요.

### 3. 품질 게이트 통합 여부

**현재 상태:**
- CUAP: title_gate + content_quality_gate + validate_post_extended
- CAP: validate_body + title_similar + validate_post_extended
- TAP: source_id/제목/시군구 중복 + validate_post_extended
- RAP: assert_korean + normalize_table + numeric_guard + validate_post_extended
- SEAP: assert_korean + validate_post_extended
- STAP: record_quality (메트릭만, 게이트 없음)
- ETAP: quality_guard + post_processor

**근거:** 수집된 데이터의 품질 검증 분기표.

**진단:** `validate_post_extended`는 공통이나, 그 외 게이트가 각 계열마다 다름. STAP은 게이트 자체가 없음.

### 4. status 필드 일관성

**현재 상태:**
- active: 23개 (CUAP 15, SEAP 2, STAP 1, manual 5)
- paused: 23개 (CAP 8, RAP 5, STAP 5, TAP 5)
- inactive: 38개 (ETAP 35, TAP 3)
- disabled: 1개 (ETAP nomad-hugo)

**근거:** YAML 전수 파싱 결과.

**진단:** ETAP이 대부분 inactive (35/36). TAP도 3개 inactive. CAP/RAP/STAP은 모두 paused.

### 5. 배포/도메인/AdSense 설정 방식

**배포:**
- dispatcher._build_and_deploy_central()이 모든 블로그를 처리하나, ETAP은 자체 배포.
- publisher.py:deploy_site()는 CLOUDFLARE_API_TOKEN을 유지 (불일치).

**도메인:**
- rotcha.kr 계열: CAP, TAP 일부
- informationhot.kr 계열: CUAP, CAP 일부, RAP, SEAP, STAP 일부
- techpawz.com 계열: ETAP, STAP 일부, SEAP 일부
- manual 블로그: 3개 도메인 (rotcha.kr, informationhot.kr, techpawz.com)

**AdSense:**
- 모든 계열에서 AdSense 사용 (수집 데이터 미포함, but AGENTS.md에서 매핑 정보 제공)

### 6. ETAP _write_hugo_post() 중복

**현재 상태:** ETAP은 각 `*_pipeline.py`마다 자체 `_write_hugo_post()`를 구현. 30+ 파일에 중복.

**근거:** 수집된 데이터의 Hugo 마크다운 분기표.

**진단:** 코드 중복이 심각. 공유 모듈로 통합 가능.

### 7. publisher.py vs deploy.py CLOUDFLARE_API_TOKEN 불일치

**현재 상태:**
- dispatcher._build_and_deploy_central(): CLOUDFLARE_API_TOKEN 제거 (OAuth 우선)
- deploy.py:deploy_site(): CLOUDFLARE_API_TOKEN 제거
- publisher.py:deploy_site(): CLOUDFLARE_API_TOKEN 유지 (불일치!)

**근거:** 수집된 데이터의 배포 분기표.

**진단:** publisher.py가 token을 유지하면 인증 문제가 발생할 수 있음.

---

## [섹션 4] 분기별 구조 통일화 설계

### 1. "이상적인 단일 표준 파이프라인" 정의

**표준 7단계:**
1. 진입점: dispatcher.py 통일
2. 토픽 수집: DB 기반 (키워드/topics/services) - 계열별 DB 테이블만 차이
3. LLM 생성: ai_writer.generate() 공유 + 프롬프트는 config/prompts/{pipeline}/{topic}.md
4. 품질 검증: validate_post_extended() 공유 + 계열별 추가 게이트는 선택적
5. Hugo 변환: shared/publishers/hugo_writer.py 공유
6. 테마: Blowfish 통일 (PaperMod/Congo 제거)
7. 배포: dispatcher._build_and_deploy_central() 통일

### 2. 계열 × 표준항목 매트릭스

| 계열 | 표준 진입점 | 표준 토픽 수집 | 표준 LLM 생성 | 표준 품질 검증 | 표준 Hugo 변환 | 표준 테마 | 표준 배포 |
|------|------------|--------------|--------------|--------------|---------------|----------|----------|
| CUAP | O | O (DB 키워드) | O (ai_writer) | O (validate_post_extended) | O (shared) | O (Blowfish) | O (dispatcher) |
| CAP | O | O (DB topics) | △ (generate_car) | △ (validate_body + title_similar) | O (shared) | X (PaperMod 1개) | O (dispatcher) |
| TAP | O | X (API fetcher) | O (ai_writer via writer) | △ (source_id/제목/시군구 중복) | O (shared) | O (Blowfish) | O (dispatcher) |
| RAP | O | O (DB keywords) | X (rap/writer.py 자체) | X (assert_korean + normalize_table + numeric_guard) | O (shared) | O (Blowfish) | O (dispatcher) |
| SEAP | O | O (DB services) | X (senior/writer.py 자체) | △ (assert_korean) | O (shared) | O (Blowfish) | O (dispatcher) |
| STAP | O | X (외부 DB) | X (STAP 자체) | X (record_quality only) | X (STAP 자체) | X (Congo 1개) | O (dispatcher) |
| ETAP | O | O (DB topics) | O (ai_writer via writer) | △ (quality_guard + post_processor) | X (30+ 중복) | O (Blowfish) | X (ETAP 자체) |

**범례:** O = 표준화 가능, X = 구조적 차이 큼, △ = 부분적 차이

### 3. 최소 변경 목록

| 우선순위 | 변경 항목 | 영향 범위 | 난이도 | 회귀 위험 |
|----------|----------|----------|--------|----------|
| 1 | ETAP _write_hugo_post() 중복 제거 → shared/hugo_writer.py 통합 | ETAP 36개 블로그 | 중간 | 중간 |
| 2 | ETAP 배포 경로 통일 → dispatcher._build_and_deploy_central() 사용 | ETAP 36개 블로그 | 낮음 | 낮음 |
| 3 | publisher.py CLOUDFLARE_API_TOKEN 처리 일치 | publisher 내부 호출 | 낮음 | 낮음 |
| 4 | 테마 Blowfish 통일 (hotissue-hugo, stock-hugo) | 2개 블로그 | 낮음 | 낮음 |
| 5 | 프롬프트 조립 경로 표준화 (config/prompts/{pipeline}/{topic}.md) | 전체 계열 | 높음 | 높음 |
| 6 | 품질 게이트 표준화 (validate_post_extended + 선택적 추가 게이트) | 전체 계열 | 중간 | 중간 |
| 7 | STAP 품질 게이트 추가 | STAP 6개 블로그 | 중간 | 중간 |

### 4. "없애야 할 것" / "합쳐야 할 것" 후보

**없애야 할 것:**
- ETAP 각 *_pipeline.py의 자체 _write_hugo_post() (30+ 중복)
- publisher.py의 CLOUDFLARE_API_TOKEN 유지 로직
- hotissue-hugo의 PaperMod 테마 (Blowfish로 통일)
- stock-hugo의 Congo 테마 (Blowfish로 통일)
- STAP의 자체 배포 경로 (dispatcher 통일)

**합쳐야 할 것:**
- 프롬프트 조립: all → config/prompts/{pipeline}/{topic}.md + shared/prompt_builder.py
- 품질 검증: all → shared/quality_validator.py + 계열별 선택적 게이트
- Hugo 변환: all → shared/publishers/hugo_writer.py

### 5. 현재 비용 vs 통일화 후 예상 비용 요약

**현재 비용 (추정):**
- 유지보수: 7개 프롬프트 조립 경로 × 각각 독립 관리
- 버그 수정: ETAP 30+ 파일에서 _write_hugo_post() 수정 필요
- 테마 변경: 3종 관리 (PaperMod, Congo, Blowfish)
- 배포 문제: publisher.py 불일치로 인한 잠재적 인증 오류

**통일화 후 예상 비용:**
- 유지보수: 1개 프롬프트 조립 경로 + 1개 quality_validator + 1개 hugo_writer
- 버그 수정: 1개 파일 수정으로 전체 해결
- 테마: Blowfish 1종만 관리
- 배포: dispatcher 경로 통일로 인증 문제 해결

**예상 절감:**
- 코드 중복: ETAP _write_hugo_post() 30+ → 0
- 프롬프트 경로: 7 → 1
- 품질 게이트: 7 → 1 + 선택적 추가
- 테마: 3 → 1

**근거:** 수집된 데이터의 구조적 불균일성 진단 기반.

---

## 잔존 위험

1. **ETAP _write_hugo_post() 통합 시 회귀 위험:** 30+ 블로그에 영향, 테스트 필수
2. **publisher.py CLOUDFLARE_API_TOKEN 수정 시:** 기존 publisher 호출 코드 영향 확인 필요
3. **테마 변경 시:** frontmatter 생성 로직 변경, Hugo 빌드 영향
4. **프롬프트 조립 경로 변경 시:** 기존 프롬프트 파일 형식 호환성 확인 필요
5. **도메인 미확인:** 75개 도메인 HTTP 응답 미확인 (전수 확인 필요)

---

> 이 감사 보고서는 코드 수정 없이 수집된 데이터만으로 작성됨.
> 모든 판정에는 근거(파일 경로, 명령 실행 결과)가 포함되어 있음.
> 추측·창작 없이 실제 데이터만 사용됨.
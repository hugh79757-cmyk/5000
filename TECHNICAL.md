# 프로젝트 기술문서

> 자동 생성: 2026-03-28 19:44 by `scripts/doc_agent.py`

## 프로젝트 요약

| 항목 | 값 |
|---|---|
| Python 파일 수 | 56 |
| 총 코드 라인 수 | 12,214 |
| 활성 파이프라인 | car, gap, rap, senior, stock, travel |
| shared 모듈 수 | 19 |

## 파이프라인

### car

**`pipelines/car/daily_refresh.py`** (672줄)

- `get_conn()`
- `refresh_trims(conn)`
- `parse_car_info(title)`
- `make_car_id(brand, model, year)`
- `guess_fuel_type(title)`
- `guess_segment(title)`
- `scan_new_cars(conn)`
- `fill_trim_efficiency(conn)`
- `refresh_images(conn)`
- `replenish_topics(conn, min_pending)`
- `detect_price_changes(conn)`
- `run_refresh()`
- 상수: DB_PATH, HEADERS, AUTO_REGISTER_BRANDS

**`pipelines/car/data_builder.py`** (456줄)

- `lookup_fuel_efficiency(conn, brand, model, displacement)`
- `lookup_ev_specs(conn, brand, model)`
- `build_engine_desc(car)`
- `calc_tax(displacement, fuel_type)`
- `fuel_type_to_code(fuel_type)`
- `get_live_fuel_price(fuel_type, db_path)`
- `calc_fuel_cost(annual_km, efficiency, fuel_type, db_path)`
- `calc_insurance(price)`
- `estimate_resale(base_price, brand, fuel_type, segment, model)`
- `calc_monthly_payment(price_manwon, annual_rate, months)`
- `select_representative_trim(trims)`
- `select_matching_trim(comp_trims, target_price)`
- `build_input(conn, topic, db_path)`
- 상수: MODEL_NAME_MAP, BRAND_URLS, BRAND_MAP_API, CAR_CONSTANTS, ANNUAL_KM, FINANCE_RATE, FINANCE_TERMS, DEFAULT_FUEL_PRICE, EV_KWH_PRICE, MIN_TRIM_PRICE

**`pipelines/car/pipeline.py`** (262줄)

- `run(blog_cfg)`
- 상수: PROJECT_DIR, CAR_DB_PATH, PROMPTS_DIR

**`pipelines/car/title_engine.py`** (390줄)

- `generate_title(data, site_id)`
- 상수: SITE_VS, SITE_SOLO

**`pipelines/car/topic_manager.py`** (136줄)

- `has_batchim(text)`
- `josa_wa(text)`
- `josa_eul(text)`
- `josa_i(text)`
- `select_topic(conn, site_id, days_window, skip_ids, post_type)`
- `generate_title(data, site_id)`
- `make_slug(title)`
- `validate_body(body, data)`

### gap

**`pipelines/gap/fetcher.py`** (89줄)

- `search_web(keyword, display)`
- `search_blog(keyword, display)`
- `search_news(keyword, display)`
- `search_image(keyword, display)`
- `fetch_keyword_data(keyword)`
- 상수: NAVER_SEARCH_URL

**`pipelines/gap/internal_links.py`** (187줄)

- `inject_internal_links(html_content, max_links)`
- `build_cta_block(category, count)`
- `process_gap_content(html_content, category)`
- 상수: ENTITIES_DB, CTA_BLOCKS, CATEGORY_CTA_MAP

**`pipelines/gap/keyword_sync.py`** (183줄)

- `classify_category(query)`
- `is_gap_suitable(query)`
- `is_high_value(query)`
- `fetch_d1_keywords(limit)`
- `sync_keywords()`
- 상수: D1_API_URL, D1_API_KEY, GAP_DB_PATH, HIGH_VALUE_PATTERNS, EXCLUDE_PATTERNS, CATEGORY_MAP

**`pipelines/gap/pipeline.py`** (194줄)

- `run(blog_cfg)`
- 상수: WP_CATEGORY_MAP, GAP_DB_PATH

**`pipelines/gap/thumbnail.py`** (94줄)

- `generate_gap_thumbnail(title, category, output_path)`
- `upload_thumbnail(title, category)`
- 상수: PALETTE

**`pipelines/gap/writer.py`** (137줄)

- `generate_gap_article(keyword, fetched_data, model)`

### rap

**`pipelines/rap/fetcher.py`** (197줄)

- `fetch_apt_trade(lawd_cd, deal_ymd, rows)`
- `fetch_apt_trade_multi(lawd_cd, months, rows)`
- `fetch_subscription_info(region_cd, page_size)`
- `find_lawd_cd(keyword)`
- 상수: API_KEY, LAWD_MAP, REGION_CD_MAP, BRAND_LAWD_MAP

**`pipelines/rap/pipeline.py`** (496줄)

- `run(blog_cfg)`
- 상수: GAP_DB_PATH, RAP_CATEGORIES, TRADE_PATTERNS, SUB_PATTERNS, BLOG_KEYWORD_FILTER, BLOG_STRATEGY, WP_CATEGORY_MAP

**`pipelines/rap/thumbnail.py`** (157줄)

- `generate_rap_thumbnail(title, category, output_path)`
- `upload_thumbnail(title, category)`
- 상수: PALETTE

**`pipelines/rap/writer.py`** (360줄)

- `generate_trade_article(keyword, trades, region_info, blog_id)`
- `generate_subscription_article(keyword, subscriptions)`

### senior

**`pipelines/senior/fetcher.py`** (340줄)

- `classify_category(text)`
- `fetch_senior_services(page, per_page, max_pages)`
- `fetch_senior_jobs()`
- `enrich_service_detail(service)`
- `enrich_naver_blog(service)`
- `fetch_all(max_pages)`
- 상수: API_KEY, SERVICE_LIST_URL, SERVICE_DETAIL_URL, SENIOR_JOB_URL, SENIOR_KEYWORDS, EXCLUDE_KEYWORDS, CATEGORIES, CACHE_PATH

**`pipelines/senior/pipeline.py`** (328줄)

- `run(cfg)`

**`pipelines/senior/thumbnail.py`** (173줄)

- `generate_senior_thumbnail(title, category, department, output_path)`
- 상수: WIDTH, HEIGHT, CATEGORY_COLORS, BADGE_COLORS, CATEGORY_ICONS

**`pipelines/senior/writer.py`** (536줄)

- `generate_senior_article(data, topic_type)`
- 상수: MODEL, ARTICLE_STRUCTURES

### stock

**`pipelines/stock/fetcher.py`** (398줄)

- `get_induty_name(code)`
- `fetch_recent_disclosure(days, page_count)`
- `fetch_major_disclosure(days)`
- `fetch_company_info(corp_code)`
- `fetch_financial_summary(corp_code, year, report_code)`
- `fetch_ipo_securities(days)`
- `fetch_dividend_info(corp_code, year)`
- `get_listed_corps(limit)`
- `fetch_etf_daily(top_n)`
- `fetch_dividend_ranking(top_n)`
- `refresh_daily_data()`
- 상수: INDUTY_MAP, DART_BASE, DB_PATH

**`pipelines/stock/pipeline.py`** (316줄)

- `run(blog_cfg)`
- 상수: DB_PATH, EVERGREEN_TYPES, BLOG_TOPIC_MAP

**`pipelines/stock/thumbnail.py`** (188줄)

- `generate_stock_thumbnail(title, category, stock_code, corp_name, output_path)`
- 상수: WIDTH, HEIGHT, CATEGORY_COLORS, BADGE_COLORS

**`pipelines/stock/writer.py`** (359줄)

- `generate_disclosure_article(disclosure, company_info, financials, financials_prev, dividend)`
- `generate_evergreen_article(topic_type, corp_data, extra_data)`
- 상수: OPENAI_MODEL

### travel

**`pipelines/travel/fetcher.py`** (778줄)

- `fetch_camping()`
- `fetch_korservice()`
- `fetch_korservice_heritage()`
- `fetch_festival()`
- `fetch_food()`
- `fetch_course()`
- `fetch_wellness()`
- `fetch_heritage()`
- `fetch_random()`
- 상수: HERITAGE_TYPES, HERITAGE_KEYWORDS

**`pipelines/travel/pipeline.py`** (181줄)

- `run(cfg)`
- 상수: BLOG_FETCH_MAP

**`pipelines/travel/writer.py`** (943줄)

- `generate_content(data, blog_id)`
- 상수: HERITAGE_CARDS, BLOG_PROMPT_MAP

## shared 모듈

**`shared/ai_writer.py`** (111줄)

- `load_models_config()`
- `get_client(provider_name, providers)`
- `generate(system_prompt, user_prompt, tier)`
- `generate_car(prompt_text, data)`
- 상수: CONFIG_DIR

**`shared/backlink_publisher.py`** (122줄)

- `publish_to_telegraph(title, body_md, original_url, blog_id)`
- `post_publish_backlinks(title, body_md, original_url, blog_id)`
- 상수: TELEGRAPH_TOKEN, BLOG_AUTHOR, DEFAULT_AUTHOR

**`shared/blogger_publisher.py`** (63줄)

- `publish_to_blogger(blog_id, title, body_html, labels)`
- 상수: SCOPES, BASE_DIR, TOKEN_PATH, CREDENTIALS_PATH

**`shared/content_store.py`** (290줄)

- `get_conn()`
- `init_db()`
- `insert_article(article)`
- `update_published(article_id, published_url)`
- `get_today_count(blog_id)`
- `article_exists(published_url)`
- `get_all_articles(blog_id, limit, offset)`
- `register_images(article_id, blog_id, html)`
- `is_image_used(image_url, blog_id)`
- `filter_unused_images(image_urls)`
- `get_used_image_count(blog_id)`
- `source_exists(blog_id, data_source, source_id)`
- `title_similar_exists(blog_id, title)`
- `init_used_places()`
- `is_place_used(place_name, blog_id)`
- `register_places(article_id, blog_id, place_names, content_ids)`
- `filter_unused_places(place_names, blog_id)`
- 상수: DB_PATH

**`shared/coupang_car.py`** (233줄)

- class `CoupangCar`
  - methods: __init__, is_configured, _generate_signature, search_products, generate_affiliate_link, get_car_product_links
- 상수: CAR_KEYWORD_MAP, DEFAULT_CAR_KEYWORDS, SEGMENT_KEYWORDS, CAR_INCLUDE_WORDS, CAR_EXCLUDE_WORDS

**`shared/coupang_senior.py`** (227줄)

- class `CoupangSenior`
  - methods: __init__, is_configured, _generate_signature, search_products, generate_affiliate_link, get_senior_product_links
- 상수: SENIOR_KEYWORD_MAP, CATEGORY_KEYWORDS, DEFAULT_KEYWORDS, EXCLUDE_WORDS

**`shared/coupang_travel.py`** (227줄)

- class `CoupangTravel`
  - methods: __init__, is_configured, _generate_signature, search_products, generate_affiliate_link, _is_travel_relevant, get_travel_product_links
- 상수: TRAVEL_KEYWORD_MAP, DEFAULT_TRAVEL_KEYWORDS, TRAVEL_INCLUDE_WORDS, TRAVEL_EXCLUDE_WORDS

**`shared/daily_report.py`** (160줄)

- `load_active_blogs()`
- `generate_report(target_date)`
- `send_report(target_date)`
- 상수: CONFIG_DIR, TAP_DB, LAP_LOG

**`shared/diningcode_enricher.py`** (339줄)

- `enrich_from_diningcode(shop_name, address)`
- 상수: HEADERS, TIMEOUT

**`shared/image_handler.py`** (56줄)

- `get_r2_client()`
- `process_and_upload(image_data, bucket)`

**`shared/monitor.py`** (36줄)

- `send_telegram(message)`
- `daily_report()`

**`shared/notify.py`** (39줄)

- `send_telegram(message, parse_mode)`
- `alert(title, detail)`
- 상수: _BOT_TOKEN, _CHAT_ID

**`shared/prompt_builder.py`** (31줄)

- `load_prompts()`
- `build(prompt_id, data, extra_vars)`
- 상수: CONFIG_DIR

**`shared/publisher.py`** (407줄)

- `load_blogs()`
- `get_blog_config(blog_id)`
- `slugify(text)`
- `deploy_site(site_path, cf_project)`
- `publish(blog_id, title, body_md, body_html, segment)`
- 상수: CONFIG_DIR

**`shared/r2_uploader.py`** (71줄)

- `upload_file(local_path, r2_key, content_type)`
- `upload_bytes(data, r2_key, content_type)`
- `file_exists(r2_key)`
- 상수: R2_ENDPOINT, R2_ACCESS_KEY, R2_SECRET_KEY, R2_BUCKET, R2_PUBLIC_BASE

**`shared/telegram_notifier.py`** (71줄)

- `send(message, parse_mode)`
- `send_error(blog_id, stage, error_msg)`
- `send_daily_report(report_text)`
- 상수: BOT_TOKEN, CHAT_ID, API_URL

**`shared/validators.py`** (680줄)

- `sanitize_title(title)`
- `validate_post(blog_id, title, html_content, context)`
- `validate_post_extended(blog_id, title, html_content, context, pipeline)`
- 상수: _AI_RESIDUES, _MIN_TITLE_LEN, _MAX_TITLE_LEN, _MIN_BODY_CHARS, _DUP_HOURS, _DUP_JACCARD_THRESHOLD, _STALE_DAYS, _DAILY_QUOTA_DEFAULT, _DB_PATH, _NO_MAP_KEYWORDS

**`shared/wordpress_publisher.py`** (501줄)


## config 파일

- `api_keys.yaml`: parse error
- `blogger_token.json`: json file (credentials)
- `blogs.yaml`: parse error
- `client_secret_hugh7973.json`: json file (credentials)
- `models.yaml`: parse error
- `prompts.yaml`: parse error

## 스케줄러

- `scheduler.py` (336줄)
- 등록된 작업: 5개
  - queue_publish, blog_id
  - batch_deploy
  - _run_gap_keyword_sync
  - _run_car_refresh
  - daily_report

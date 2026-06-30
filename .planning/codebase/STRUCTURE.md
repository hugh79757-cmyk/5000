---
focus: arch
last_mapped: 2026-06-30
version: 1
---

# Directory Structure

## Top-Level Layout

```
5000/
├── config/            # Configuration (YAML)
│   ├── blogs.yaml     # Master blog schedule + deploy config
│   ├── blogs.d/       # Per-blog definitions (*.yaml)
│   ├── models.yaml    # LLM provider config
│   ├── prompts.yaml   # AI writing prompts + SEO rules (1117 lines)
│   ├── prompts/       # Per-topic prompt files
│   └── api_keys.yaml  # API secrets (gitignored)
├── shared/            # Reusable modules (43 files incl. .bak)
│   ├── ai_writer.py       # OpenAI GPT client
│   ├── humanizer.py       # AI→natural text post-processor
│   ├── publisher.py       # Hugo blog publisher (959 lines)
│   ├── blogger_publisher.py  # Blogger.com API publisher
│   ├── wordpress_publisher.py # WordPress XML-RPC publisher
│   ├── content_store.py   # SQLite articles CRUD
│   ├── telegram_notifier.py  # Telegram Bot notifications
│   ├── r2_uploader.py     # Cloudflare R2 image upload
│   ├── entity_linker.py   # Cross-blog internal links
│   ├── image_handler.py   # Image processing (Pillow)
│   ├── validators.py      # Title/content validation
│   ├── prompt_builder.py  # AI prompt construction
│   ├── monitor.py         # Daily monitoring
│   ├── daily_report.py    # Cross-project daily report
│   ├── ledger_sync.py     # Publish log synchronization
│   ├── backlink_publisher.py # Backlink injection
│   ├── diningcode_enricher.py # Restaurant enrichment
│   ├── coupang_senior.py  # Coupang senior products
│   ├── coupang_car.py     # Coupang car products
│   ├── coupang_travel.py  # Coupang travel products
│   └── db_paths.py        # Database path registry
├── pipelines/          # Content generation pipelines
│   ├── car/           # Automotive (8 blogs)
│   │   ├── pipeline.py
│   │   ├── daily_refresh.py
│   │   ├── topic_manager.py
│   │   ├── data_builder.py
│   │   └── title_engine.py
│   ├── curation/      # Curated content
│   │   ├── pipeline.py
│   │   ├── collector.py
│   │   └── keywords.py
│   ├── etap/          # English travel (30+ blogs, ~160 files incl. .bak)
│   │   ├── pipeline.py           # Main orchestrator
│   │   ├── writer.py             # Generic city guide writer
│   │   ├── topic_manager.py      # Topic selection + exhaustion check
│   │   ├── quality_guard.py      # Content quality checks
│   │   ├── quality_scanner.py    # Bulk quality scanning
│   │   ├── image_fetcher.py      # City/body image fetching
│   │   ├── post_processor.py     # AdSense, product cards, cross-sell
│   │   ├── safeguard.py          # Safety filters
│   │   ├── tour_utils.py         # Tour product utilities
│   │   ├── {topic}_pipeline.py   # Per-topic pipeline (30+)
│   │   └── {topic}_writer.py     # Per-topic AI writer (30+)
│   ├── gap/           # General content
│   │   ├── pipeline.py
│   │   ├── fetcher.py
│   │   ├── writer.py
│   │   ├── thumbnail.py
│   │   ├── keyword_sync.py
│   │   └── internal_links.py
│   ├── rap/           # Real estate (~3 blogs, 1043 lines)
│   │   ├── pipeline.py
│   │   ├── fetcher.py
│   │   ├── writer.py
│   │   ├── thumbnail.py
│   │   ├── keyword_generator.py
│   │   └── rap_data_sync.py
│   ├── senior/        # Senior/welfare
│   │   ├── pipeline.py
│   │   ├── fetcher.py
│   │   ├── writer.py
│   │   └── thumbnail.py
│   ├── stock/         # Stock/finance (local proxy for STAP)
│   │   ├── pipeline.py
│   │   ├── fetcher.py
│   │   ├── writer.py
│   │   └── thumbnail.py
│   └── travel/        # Korean travel
│       └── pipeline.py
├── scripts/           # Utility scripts (11 files)
│   ├── indexnow.py                # IndexNow submission
│   ├── master_backup.py           # Full backup
│   ├── refresh_course.py          # Course content refresh
│   ├── refresh_festival.py        # Festival content refresh
│   ├── refresh_guide_topics.py    # Guide topic refresh
│   ├── test_sigungu_check.py      # Sigungu validation test
│   └── test_sigungu_distribution.py # Sigungu distribution test
├── content/           # Hugo content: `content/posts/` (1100+ posts)
│   ├── posts/         # Korean blog posts (Markdown)
│   ├── archives.md, search.md, etc.
├── layouts/           # Hugo custom templates
│   ├── _default/      # Default templates
│   ├── partials/      # Partial templates
│   └── 404.html
├── assets/            # Hugo assets
│   └── css/           # Stylesheets
├── static/            # Static files (robots.txt, favicon, etc.)
├── data/              # SQLite databases (30+ .db files)
├── workers/           # Cloudflare Workers
│   ├── redirect-worker.js   # URL redirect worker
│   └── wrangler.toml        # Worker config
├── functions/         # Cloudflare Pages Functions
│   └── _middleware.js
├── docs/              # Documentation
├── dispatcher.py      # Central pipeline router (666 lines)
├── scheduler.py       # Continuous scheduler (712 lines)
└── hugo.toml          # Hugo site config (142 lines)
```

## Key File Sizes

| File | Lines | Complexity |
|------|-------|------------|
| `scheduler.py` | 712 | High — scheduling + health checks |
| `dispatcher.py` | 666 | High — routing + deploy orchestration |
| `shared/publisher.py` | 959 | Very high — multi-platform publishing |
| `shared/prompt_builder.py` | ~500 | Medium — prompt assembly |
| `shared/entity_linker.py` | ~500 | Medium — cross-blog link injection |
| `pipelines/rap/pipeline.py` | 1043 | Very high — complex keyword logic |
| `pipelines/etap/pipeline.py` | 449 | Medium — main orchestrator |
| `config/prompts.yaml` | 1117 | Configuration — AI prompts |
| `config/blogs.d/tap.yaml` | 179 | Configuration — blog definitions |
| `config/blogs.yaml` | 8 | Configuration — master schedule |

## Source File Patterns

- **Python**: Snake case files and functions (`shared/ai_writer.py`, `_run_pipeline()`)
- **Config**: YAML with `kebab-case` keys (`daily_quota`, `site_path`)
- **Blog IDs**: `{category}-hugo` format (e.g., `rap-hugo`, `travel-hugo`)
- **Pipeline naming**: `pipelines/{pipeline_name}/pipeline.py` with `run(cfg)` entrypoint
- **Backup files**: `.bak*` extensions scattered in source directories (not gitignored for `pipelines/`)
- **Tests**: Files named `test_*.py` in `scripts/`

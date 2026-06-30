# 5000

## What This Is

An automated content generation and publishing platform that uses OpenAI GPT to create articles for 50+ Korean and English blogs, publishes them to Cloudflare Pages (Hugo static sites) and legacy Blogger/WordPress blogs, then notifies search engines via IndexNow.

## Core Value

Pipelines run reliably with clear errors when they don't — no silent failures, no manual firefighting.

## Requirements

### Validated

- ✓ Multi-pipeline content generation (car, etap, gap, rap, senior, stock, travel, curation, tap) — existing
- ✓ Hugo static site publishing to Cloudflare Pages — existing
- ✓ Blogger.com API publishing — existing
- ✓ WordPress XML-RPC publishing — existing
- ✓ Scheduled execution via `schedule` library + launchd — existing
- ✓ Image upload to Cloudflare R2 (S3-compatible) — existing
- ✓ Cross-blog entity/internal link injection — existing
- ✓ AI content humanization (AI-ism removal) — existing
- ✓ Telegram-based error and daily report notifications — existing
- ✓ Config-driven blog definitions (blogs.yaml + blogs.d/) — existing

### Active

- [ ] **STB-01**: Central modules are testable — unit tests for dispatcher, publisher, scheduler, validators
- [ ] **STB-02**: Hardcoded absolute paths are eliminated — configurable via env/config
- [ ] **STB-03**: `.bak*` files cleaned from source directories, gitignore covers all variants
- [ ] **STB-04**: Linting (ruff) and type checking (mypy) configured and passing
- [ ] **STB-05**: Python 3.14 compatibility verified across all dependencies
- [ ] **STB-06**: CI pipeline with test + lint steps on push
- [ ] **STB-07**: `dispatcher.py` routing refactored — if/elif chain replaced with registry pattern
- [ ] **STB-08**: `shared/publisher.py` split into focused modules
- [ ] **STB-09**: Error handling is consistent and produces actionable messages
- [ ] **STB-10**: External project coupling (TAP, STAP, ETAP) isolated behind interfaces

### Out of Scope

- **Technology stack changes** — Python/Hugo/Cloudflare stays as-is
- **Greenfield rewrite** — refactoring existing code, not replacing it
- **New blog pipelines** — only stabilizing existing ones
- **Database migration framework** — too heavy for SQLite-per-pipeline model

## Context

This is a production system running daily on a single macOS machine. It generates and publishes content across 50+ blogs via scheduled pipelines. The codebase has grown organically over 2+ years with no tests, hardcoded developer-specific paths, and significant technical debt. The goal is to make it stable, maintainable, and — ideally — runnable by someone other than the original author.

## Constraints

- **Tech stack**: Python 3.14, Hugo, Cloudflare Pages/Workers/R2, SQLite — must keep these
- **Deployment**: macOS host with `launchd`; Cloudflare Pages for hosting
- **Pipelines must keep running**: Refactoring cannot block daily content publication
- **Single developer**: Changes must be incremental, not all-or-nothing

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Keep existing stack (Python/Hugo/Cloudflare) | No reason to change; risk outweighs benefit | — Pending |
| Full rework approach | All areas need attention, not just one pipeline | — Pending |
| Stability + complexity combined per phase | Avoids long periods without visible improvement | — Pending |

---

*Last updated: 2026-06-30 after project initialization*

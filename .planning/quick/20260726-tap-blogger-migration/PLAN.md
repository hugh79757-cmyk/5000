# Quick Task: TAP Blogger Migration

**Created:** 2026-07-26  
**Slug:** tap-blogger-migration  
**Status:** in-progress

---

## Objective
Migrate the disabled TAP Blogger (`tap-blogger` at `travel.rotcha.kr`) from the standalone `com.tap.scheduler.plist` into the 5000 `pipelines/travel/` pipeline, so it publishes regularly via the central scheduler.

---

## Background
- **TAP standalone scheduler**: `~/Library/LaunchAgents/com.tap.scheduler.plist.disabled` — runs `/Users/twinssn/Projects/TAP/scheduler.py` which calls `app.py run` for general publishing
- **Target blogger**: `tap-blogger` (id in `config/blogs.d/tap.yaml`) — Blogger platform, domain `travel.rotcha.kr`, daily quota 5, schedule 9x/day (06:00–22:00)
- **Current status**: TAP scheduler is **disabled** (`.disabled` suffix), so this blogger is not publishing
- **Goal**: Integrate into 5000's `dispatcher.py` + `scheduler.py` so it runs via central control

---

## Tasks

### 1. Identify & Analyze (Discovery)
- [ ] Read TAP's `app.py` to understand how `tap-blogger` publishing works
- [ ] Identify the Blogger publishing logic (which functions, what data sources)
- [ ] Check 5000's `pipelines/travel/` structure for Blogger support
- [ ] Verify Blogger credentials/config in 5000 (`api_keys.yaml`, `blogs.yaml`)

### 2. Migrate (Implementation)
- [ ] Add `tap-blogger` to 5000's blog config (likely already in `tap.yaml` — verify)
- [ ] Ensure 5000's `dispatcher.py` can route `tap-blogger` to travel pipeline with Blogger platform
- [ ] Add Blogger publishing support to `pipelines/travel/pipeline.py` if missing
- [ ] Wire Blogger credentials (OAuth) in 5000's config system

### 3. Test & Verify
- [ ] Dry-run: `python dispatcher.py tap-blogger` — verify content generation + Blogger publish (dry-run mode)
- [ ] Check blogger post appears on `travel.rotcha.kr` (or preview)
- [ ] Verify 5000 scheduler picks up the schedule from `tap.yaml`
- [ ] Disable TAP standalone scheduler permanently (remove `.disabled` plist or keep disabled)

### 4. Cleanup
- [ ] Remove TAP's `scheduler.py` dependency on Blogger publishing
- [ ] Update TAP's `.continue-here.md` to reflect migration complete
- [ ] Commit changes

---

## Acceptance Criteria
- [ ] `tap-blogger` publishes via `python dispatcher.py tap-blogger` successfully
- [ ] 5000 scheduler runs it on schedule (06:00, 08:00, ..., 22:00)
- [ ] No duplicate publishing (TAP standalone scheduler stays disabled)
- [ ] Blogger post appears on `travel.rotcha.kr`

---

## Notes
- TAP's `app.py` uses `core.blogger_publisher` — check if 5000 has equivalent in `shared/blogger_publisher.py`
- 5000's `dispatcher.py` already has `_resolve_pipeline("travel")` — need to ensure Blogger platform is handled
- Blogger OAuth tokens: TAP uses `token.pickle` + `client_secret.json` — need to migrate to 5000's config
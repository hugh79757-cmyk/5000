---
phase: 59-ops-dashboard-and-unification
plan: 10
type: execute
wave: 4
depends_on:
  - 59-09
files_modified:
  - pipelines/etap/adventure_pipeline.py
  - pipelines/etap/airlines_pipeline.py
  - pipelines/etap/airports_pipeline.py
  - pipelines/etap/bus_pipeline.py
  - pipelines/etap/citytours_pipeline.py
  - pipelines/etap/cruise_pipeline.py
  - pipelines/etap/culture_pipeline.py
  - pipelines/etap/daytrips_pipeline.py
  - pipelines/etap/deals_pipeline.py
  - pipelines/etap/dining_pipeline.py
  - pipelines/etap/escape_pipeline.py
  - pipelines/etap/esim_pipeline.py
  - pipelines/etap/eurail_pipeline.py
  - pipelines/etap/extreme_pipeline.py
  - pipelines/etap/ferry_pipeline.py
  - pipelines/etap/flight_pipeline.py
  - pipelines/etap/foodtour_pipeline.py
  - pipelines/etap/ghost_pipeline.py
  - pipelines/etap/hiking_pipeline.py
  - pipelines/etap/layover_pipeline.py
  - pipelines/etap/luxury_pipeline.py
  - pipelines/etap/michelin_pipeline.py
  - pipelines/etap/multiday_pipeline.py
  - pipelines/etap/nature_pipeline.py
  - pipelines/etap/nightlife_pipeline.py
  - pipelines/etap/nomad_pipeline.py
  - pipelines/etap/phototour_pipeline.py
  - pipelines/etap/tours_pipeline.py
  - pipelines/etap/trains_pipeline.py
  - pipelines/etap/transfers_pipeline.py
  - pipelines/etap/visa_pipeline.py
  - pipelines/etap/visafree_pipeline.py
  - pipelines/etap/walking_pipeline.py
  - pipelines/etap/watersports_pipeline.py
  - pipelines/etap/watertours_pipeline.py
autonomous: true
requirements:
  - etap-pipeline-update
must_haves:
  truths:
    - "All 35 ETAP pipelines import _write_hugo_post_etap from shared"
    - "Each pipeline's local _write_hugo_post is removed"
    - "Each pipeline's local _build_and_deploy is removed"
    - "ETAP pipelines call the shared wrapper with correct parameters"
  artifacts:
    - path: "pipelines/etap/*_pipeline.py"
      provides: "Updated pipelines importing from shared"
  key_links:
    - from: "pipelines/etap/*_pipeline.py"
      to: "shared/publishers/hugo_writer.py"
      via: "from shared.publishers.hugo_writer import _write_hugo_post_etap"
      pattern: "from shared.publishers.hugo_writer import"
---

<objective>
Update all 35 ETAP pipelines to use the shared _write_hugo_post_etap() wrapper and remove duplicate functions.

Purpose: Each ETAP pipeline currently has its own _write_hugo_post and _build_and_deploy. This plan replaces them with shared imports, eliminating 35 copies of duplicate code.
Output: 35 updated pipeline files with shared imports
</objective>

<execution_context>
@/Users/twinssn/.config/opencode/get-shit-done/workflows/execute-plan.md
@/Users/twinssn/.config/opencode/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@shared/publishers/hugo_writer.py
@pipelines/etap/adventure_pipeline.py
@.planning/phase-59-ops-dashboard-and-unification/CONTEXT.md
@.planning/phase-59-ops-dashboard-and-unification/RESEARCH.md

<interfaces>
<!-- From Plan 09 — wrapper function -->
```python
from shared.publishers.hugo_writer import _write_hugo_post_etap

# Usage in pipeline:
result = _write_hugo_post_etap(
    blog_cfg={"id": blog_id, "site_path": site_path, "theme": "blowfish"},
    title=article["title"],
    body_md=article["content"],
    slug=slug,
    category=category,
    tags=tags,
    thumbnail_url=article.get("cover_image", ""),
    is_draft=False,
    country=article.get("country"),
    city=article.get("city"),
)
```

<!-- From dispatcher.py — deploy is now centralized -->
```python
# dispatcher.py handles all deploys via _build_and_deploy_central()
# Individual pipelines should NOT call _build_and_deploy()
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Update 34 standard ETAP pipelines (non-flight)</name>
  <files>
    pipelines/etap/adventure_pipeline.py,
    pipelines/etap/airlines_pipeline.py,
    pipelines/etap/airports_pipeline.py,
    pipelines/etap/bus_pipeline.py,
    pipelines/etap/citytours_pipeline.py,
    pipelines/etap/cruise_pipeline.py,
    pipelines/etap/culture_pipeline.py,
    pipelines/etap/daytrips_pipeline.py,
    pipelines/etap/deals_pipeline.py,
    pipelines/etap/dining_pipeline.py,
    pipelines/etap/escape_pipeline.py,
    pipelines/etap/esim_pipeline.py,
    pipelines/etap/eurail_pipeline.py,
    pipelines/etap/extreme_pipeline.py,
    pipelines/etap/ferry_pipeline.py,
    pipelines/etap/foodtour_pipeline.py,
    pipelines/etap/ghost_pipeline.py,
    pipelines/etap/hiking_pipeline.py,
    pipelines/etap/layover_pipeline.py,
    pipelines/etap/luxury_pipeline.py,
    pipelines/etap/michelin_pipeline.py,
    pipelines/etap/multiday_pipeline.py,
    pipelines/etap/nature_pipeline.py,
    pipelines/etap/nightlife_pipeline.py,
    pipelines/etap/nomad_pipeline.py,
    pipelines/etap/phototour_pipeline.py,
    pipelines/etap/tours_pipeline.py,
    pipelines/etap/trains_pipeline.py,
    pipelines/etap/transfers_pipeline.py,
    pipelines/etap/visa_pipeline.py,
    pipelines/etap/visafree_pipeline.py,
    pipelines/etap/walking_pipeline.py,
    pipelines/etap/watersports_pipeline.py,
    pipelines/etap/watertours_pipeline.py
  </files>
  <action>
For each of the 34 standard ETAP pipelines (all except flight_pipeline.py):

**Step 1: Replace import block**
Remove these imports (they will be unused after removing local functions):
```python
from shared.content_enhancer import inject_internal_links, insert_adsense
from shared.coupang_senior import build_cross_sell_html, insert_cross_sell_block
```

Add this import:
```python
from shared.publishers.hugo_writer import _write_hugo_post_etap
```

**Step 2: Replace _write_hugo_post() call**
In the `run()` function, find where `_write_hugo_post(article, ...)` is called and replace with:
```python
result = _write_hugo_post_etap(
    blog_cfg={"id": blog_id, "site_path": site_path, "theme": "blowfish"},
    title=article["title"],
    body_md=article["content"],
    slug=slug,
    category=category,
    tags=article.get("tags", []),
    thumbnail_url=article.get("cover_image", ""),
    is_draft=False,
    country=article.get("country"),
    city=article.get("city"),
)
```

**Step 3: Remove local _write_hugo_post() function**
Delete the entire `def _write_hugo_post(article, ...)` function (typically ~40 lines).

**Step 4: Remove local _build_and_deploy() function**
Delete the entire `def _build_and_deploy(site_path, blog_id)` function (typically ~30 lines).
Dispatcher.py handles all deploys centrally.

**Step 5: Remove unused imports**
After removing local functions, clean up imports that are no longer needed:
- `import os` (if only used by _write_hugo_post/_build_and_deploy)
- `from pathlib import Path` (if only used by removed functions)
- Keep all other imports that are used by remaining code

**Step 6: Verify run() function still works**
The run() function should:
1. Still collect articles from the DB
2. Call _write_hugo_post_etap() instead of local _write_hugo_post()
3. Return the same result format
4. NOT call _build_and_deploy() (dispatcher handles this)

**Important pattern for each file:**
- The run() function signature stays the same
- The article collection logic stays the same
- Only the _write_hugo_post call and local function definitions change
- Each file should be a clean diff: remove ~70 lines (2 functions), add ~1 line (import)
  </action>
  <verify>
    <automated>cd /Users/twinssn/Projects/5000 && echo "=== Checking _write_hugo_post removal ===" && grep -r 'def _write_hugo_post' pipelines/etap/*_pipeline.py | wc -l && echo "=== Expected: 1 (flight_pipeline only) ===" && echo "=== Checking shared import ===" && grep -r 'from shared.publishers.hugo_writer import' pipelines/etap/*_pipeline.py | wc -l && echo "=== Expected: 35 ===" && echo "=== Checking _build_and_deploy removal ===" && grep -r 'def _build_and_deploy' pipelines/etap/*_pipeline.py | wc -l && echo "=== Expected: 0 ===" && python -c "
import importlib
import pipelines.etap.adventure_pipeline as mod
# Verify module still has run() function
assert hasattr(mod, 'run'), 'run() function missing from adventure_pipeline'
print('PASS: adventure_pipeline still has run()')
"</automated>
  </verify>
  <done>
    - 34 standard ETAP pipelines no longer define local _write_hugo_post
    - 34 standard ETAP pipelines no longer define local _build_and_deploy
    - All 34 import _write_hugo_post_etap from shared
    - Each pipeline's run() function still works with shared wrapper
    - Only flight_pipeline.py retains a local function (handled in Task 2)
  </done>
</task>

<task type="auto">
  <name>Task 2: Update flight_pipeline.py (special case)</name>
  <files>pipelines/etap/flight_pipeline.py</files>
  <action>
Handle flight_pipeline.py separately — it has a completely different _write_hugo_post signature.

**flight_pipeline.py current state:**
```python
def _write_hugo_post(cfg, article):
    # Simplified: no cross-sell, no adsense, no internal links
    # Returns filepath (not dict)
```

**Update to:**
1. Remove local _write_hugo_post function
2. Import _write_hugo_post_etap from shared
3. Update the call site in run() to use the wrapper with inject_links=False, inject_ads=False, inject_crosssell=False
4. Adapt the return value handling (wrapper returns dict, old function returned filepath)

**Specific changes:**
```python
# Add import
from shared.publishers.hugo_writer import _write_hugo_post_etap

# In run(), replace _write_hugo_post(cfg, article) with:
blog_cfg = {
    "id": cfg.get("blog_id", ""),
    "site_path": cfg.get("site_path", ""),
    "theme": cfg.get("theme", "blowfish"),
}
result = _write_hugo_post_etap(
    blog_cfg=blog_cfg,
    title=article["title"],
    body_md=article["content"],
    slug=slug,
    category=category,
    tags=article.get("tags", []),
    thumbnail_url=article.get("cover_image", ""),
    is_draft=False,
    inject_links=False,
    inject_ads=False,
    inject_crosssell=False,
)
# Old code expected filepath, new returns dict — adapt accordingly
```

5. Remove local _build_and_deploy function
6. Remove unused imports
  </action>
  <verify>
    <automated>cd /Users/twinssn/Projects/5000 && python -c "
import importlib
import pipelines.etap.flight_pipeline as mod
assert hasattr(mod, 'run'), 'run() function missing from flight_pipeline'
# Should NOT have local _write_hugo_post
assert not hasattr(mod, '_write_hugo_post'), 'Local _write_hugo_post still exists'
print('PASS: flight_pipeline cleaned up')
"</automated>
  </verify>
  <done>
    - flight_pipeline.py no longer defines local _write_hugo_post
    - flight_pipeline.py imports _write_hugo_post_etap from shared
    - flight_pipeline.py uses inject_links=False, inject_ads=False, inject_crosssell=False
    - flight_pipeline.py no longer defines local _build_and_deploy
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Pipeline update → Hugo output | Changing how posts are written could affect content |
| Import change → runtime | New imports must resolve at runtime |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-59-23 | Tampering | Post content change | mitigate | Wrapper calls same shared function, content pipeline unchanged |
| T-59-24 | Denial of Service | Import failure | mitigate | All imports are standard library or already in requirements.txt |
| T-59-25 | Elevation of Permission | _build_and_deploy removal | mitigate | Dispatcher handles all deploys centrally (already working) |
</threat_model>

<verification>
- grep confirms only 1 _write_hugo_post definition remains (flight_pipeline is handled)
- grep confirms 35 files import from shared
- grep confirms 0 _build_and_deploy definitions remain
- Each pipeline's run() function still exists and is callable
- No syntax errors in modified files (python -c import)
</verification>

<success_criteria>
- All 35 ETAP pipelines use shared _write_hugo_post_etap()
- Zero duplicate _write_hugo_post definitions
- Zero duplicate _build_and_deploy definitions
- Each pipeline's run() function works unchanged
- flight_pipeline.py special case handled correctly
</success_criteria>

<output>
Create `.planning/phases/59-ops-dashboard-and-unification/59-10-SUMMARY.md` when done
</output>

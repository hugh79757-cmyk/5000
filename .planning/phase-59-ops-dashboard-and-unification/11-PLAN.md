---
phase: 59-ops-dashboard-and-unification
plan: 11
type: execute
wave: 4
depends_on:
  - 59-10
files_modified:
  - dispatcher.py
autonomous: true
requirements:
  - etap-deploy-consolidation
must_haves:
  truths:
    - "ETAP deploy path goes through dispatcher._build_and_deploy_central()"
    - "flights-hugo/flight-hugo naming is consistent"
    - "No ETAP pipeline calls its own deploy function"
  artifacts:
    - path: "dispatcher.py"
      provides: "Verified ETAP dispatch + deploy routing"
  key_links:
    - from: "dispatcher.py"
      to: "pipelines/etap/*_pipeline.py"
      via: "import + run() call"
      pattern: "pipelines.etap.*_pipeline"
---

<objective>
Verify ETAP deploy path consolidation and fix flights-hugo/flight-hugo naming inconsistency.

Purpose: After removing _build_and_deploy from ETAP pipelines (Plan 10), verify that dispatcher.py correctly handles all ETAP deploys and fix the naming mismatch.
Output: Updated dispatcher.py with consistent naming
</objective>

<execution_context>
@/Users/twinssn/.config/opencode/get-shit-done/workflows/execute-plan.md
@@/Users/twinssn/.config/opencode/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@dispatcher.py
@.planning/phase-59-ops-dashboard-and-unification/CONTEXT.md
@.planning/phase-59-ops-dashboard-and-unification/RESEARCH.md

<interfaces>
<!-- From dispatcher.py — ETAP dispatch logic (line 425-441) -->
```python
_ETAP_BLOG_EXCEPTIONS = {
    "flights-hugo": "pipelines.etap.flight_pipeline",
}
# Blog ID stem → pipeline module mapping
stem = blog_id.replace("-hugo", "").replace("-blogger", "")
module_path = f"pipelines.etap.{stem}_pipeline"
# Special case: flights-hugo → flight_pipeline (not flights_pipeline)
```

<!-- From dispatcher.py — central deploy (line 618) -->
```python
deploy_env = {k: v for k, v in os.environ.items() if k != "CLOUDFLARE_API_TOKEN"}
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Verify ETAP dispatch + fix flights/flight naming</name>
  <files>dispatcher.py</files>
  <action>
Verify and fix the ETAP dispatch and deploy routing in dispatcher.py.

**Step 1: Verify _ETAP_BLOG_EXCEPTIONS**
Check that `flights-hugo` maps to `pipelines.etap.flight_pipeline`:
```python
_ETAP_BLOG_EXCEPTIONS = {
    "flights-hugo": "pipelines.etap.flight_pipeline",
}
```

**Step 2: Verify ETAP deploy goes through central path**
Check that dispatcher.py line ~728-729 calls `_build_and_deploy_central()`:
```python
# This should call the central deploy, not individual pipeline deploy
_deploy_result = _build_and_deploy_central(blog_id, site_path, cf_project)
```

**Step 3: Check for any remaining individual ETAP deploy calls**
Grep for `_build_and_deploy` calls inside ETAP run() functions — should be 0 after Plan 10.

**Step 4: Verify flights-hugo YAML → dispatcher consistency**
- config/blogs.d/etap.yaml should have `id: flights-hugo`
- dispatcher.py _ETAP_BLOG_EXCEPTIONS should map `flights-hugo` → `flight_pipeline`
- Cloudflare Pages project name should match

**Step 5: Document the naming chain**
```
YAML: flights-hugo → etap.yaml
Dispatcher: flights-hugo → _ETAP_BLOG_EXCEPTIONS → pipelines.etap.flight_pipeline
Cloudflare: flights-hugo → CF Pages project name
```

**Important:** Do NOT rename anything unless there's a clear mismatch. The naming `flights-hugo` is correct for the YAML and CF project. The `flight_pipeline.py` module name is correct for the Python code. The `_ETAP_BLOG_EXCEPTIONS` mapping bridges the two.
  </action>
  <verify>
    <automated>cd /Users/twinssn/Projects/5000 && python -c "
import sys; sys.path.insert(0, '.')
# Check dispatcher imports work
from dispatcher import _ETAP_BLOG_EXCEPTIONS
assert 'flights-hugo' in _ETAP_BLOG_EXCEPTIONS
assert _ETAP_BLOG_EXCEPTIONS['flights-hugo'] == 'pipelines.etap.flight_pipeline'
print('ETAP exceptions:', _ETAP_BLOG_EXCEPTIONS)
print('PASS: flights-hugo naming consistent')
" && echo "=== Checking no individual ETAP deploys remain ===" && grep -r '_build_and_deploy\|_deploy_site' pipelines/etap/*_pipeline.py 2>/dev/null | grep -v 'def _build_and_deploy\|def _deploy' | wc -l && echo "Expected: 0 (no deploy calls in pipeline run functions)"</automated>
  </verify>
  <done>
    - _ETAP_BLOG_EXCEPTIONS correctly maps flights-hugo → flight_pipeline
    - Dispatcher central deploy handles all ETAP blogs
    - No individual ETAP pipelines call _build_and_deploy()
    - Naming chain is documented and consistent
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Dispatcher → ETAP pipeline | Dispatch logic must route to correct module |
| Dispatcher → deploy | Central deploy must handle all blog types |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-59-26 | Tampering | Dispatch routing | mitigate | _ETAP_BLOG_EXCEPTIONS is explicit mapping, no dynamic construction |
| T-59-27 | Denial of Service | Deploy failure | mitigate | Central deploy has lock + error handling (existing) |
</threat_model>

<verification>
- _ETAP_BLOG_EXCEPTIONS has flights-hugo → flight_pipeline mapping
- No individual ETAP pipeline calls _build_and_deploy()
- Dispatcher central deploy handles all ETAP blogs
- Naming chain YAML → dispatcher → CF is consistent
</verification>

<success_criteria>
- ETAP deploy path is fully centralized through dispatcher
- flights-hugo/flight-hugo naming is consistent across all layers
- No broken deploy routing for any ETAP blog
</success_criteria>

<output>
Create `.planning/phases/59-ops-dashboard-and-unification/59-11-SUMMARY.md` when done
</output>

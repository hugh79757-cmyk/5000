# Phase 25 Wave 2 Summary — pipeline.py integration

**Date:** 2026-07-20

## Tasks
- T3: Add cuap_entity_linker import + injection logic to pipeline.py
- T4: Add entity registration after publish success

## Deliverables
- `pipelines/curation/pipeline.py`
  - Import block: `from shared.cuap_entity_linker import (inject_cross_blog_links, build_cross_sell_card, build_funnel_header, init_cuap_tables, register_cuap_entity)`
  - Module load: `init_cuap_tables()` (try/except fail-open)
  - After CTA fallback (line ~917): inject_cross_blog_links + build_cross_sell_card + build_funnel_header (try/except fail-open)
  - After publish success (line ~969): register_cuap_entity (try/except fail-open)

## Verification
- T3+T4 AST: PASS (all 5 imports + 5 calls detected)

## Status: ✓ COMPLETE

---
phase: 3
plan: wave1
subsystem: curation-content-validation
tags: [title-diversity, template-rotation, content-validation]
requires: []
provides: [title-template-registry, prompt-style-variation]
affects: [pipelines/curation/writer.py]
tech-stack:
  added: [shared/title_templates.py]
  patterns: [weighted-random-selection, lazy-db-connection, regex-classifier]
key-files:
  created:
    - shared/title_templates.py
  modified:
    - pipelines/curation/writer.py
decisions:
  - '8 universal templates with weighted random selection (not strict round-robin) to avoid predictable patterns while maintaining diversity'
  - 'Template rotation window of 5 — same type avoided within last 5 publications'
  - 'Blog-specific overrides dict (BLOG_TEMPLATE_OVERRIDES) as optional, empty by default for future use'
  - 'comparison template gets weight 0.6 (vs 1.0 for others) since it was the current default and most likely to cause duplicates'
  - 'Style hint injected as prompt directive, not code-level parameter — follows existing BLOG_EXTRA_RULES pattern'
  - 'get_recent_styles opens/closes DB connection per call, matching existing connection management pattern in pipeline.py'
metrics:
  duration: ~1min
  completed: "2026-07-05"
---

# Phase 3 Wave 1: Title Diversity System

Created the title template registry module (shared/title_templates.py) with 8 template types and a TitleTemplatePicker class for weighted random selection with recent-use avoidance. Integrated into writer.py so the AI prompt receives a style hint per article, breaking the repetitive "1위 X vs Y — 비교" pattern that caused 50-62 similar_title failures/week.

## Key Implementation Details

- **TITLE_TEMPLATES** — 8 templates: comparison, ranking, toplist, buying_guide, budget, review_style, question_style, spec_style
- **TitleTemplatePicker.pick()** — excludes template types used in the last 5 publications (from `get_recent_styles()`), then weighted random from remaining
- **TitleTemplatePicker.render()** — fills {brand1}, {brand2}, {brand3}, {year}, {month}, {keyword}, {price_range} from product data
- **TitleTemplatePicker.get_recent_styles()** — reads publish_log from curation.db, classifies each title via `_classify_title()` regex
- **_classify_title()** — 8 regex patterns mapping title text to template types (returns "" for unmatched)
- **writer.py integration** — `_build_system_prompt()` accepts optional `style_hint=""`; when provided, injects `[이번 발행 제목 스타일]` section with anti-repetition instruction. `_build_user_prompt()` accepts optional `price_range=""`. `generate_curation_article()` uses module-level `_tt_picker` to select/render style hint before building prompts.

## Deviations from Plan

None — plan executed exactly as written.

## Test Results

```
# Template module verification:
Picked: question_style
Rendered: 노트북 고민된다면? 지금 사야 하는 BEST 5
OK

# writer.py verification:
writer.py syntax OK
Template picked for fitness-hugo: budget
Prompt integration OK
# Backward compatibility:
- No style_hint → no [이번 발행 제목 스타일] section
- Empty style_hint → no section
- No price_range → no "상품 가격대" line
```

## Verification

```bash
# Task 1.1: Template module
python3 -c "from shared.title_templates import TitleTemplatePicker, TITLE_TEMPLATES; p = TitleTemplatePicker(); k = p.pick(); r = p.render(k, {'brand1': '삼성', 'brand2': 'LG'}, keyword='노트북'); assert len(TITLE_TEMPLATES) >= 6"

# Task 1.2: Prompt integration
python3 -c "from pipelines.curation.writer import _build_system_prompt; prompt = _build_system_prompt('노트북', blog_id='laptop-hugo', style_hint='TOP 5 노트북'); assert 'TOP 5' in prompt; assert '최근 3일 내' in prompt; assert 'laptop-hugo' in prompt"
```

## Self-Check: PASSED

- [x] `shared/title_templates.py` exists (211 lines, TitleTemplatePicker class + 8 templates + _classify_title)
- [x] `pipelines/curation/writer.py` modified with title template integration
- [x] Task 1.1 commit: `e6b65c5de` — feat(3-wave1): create shared/title_templates.py with TitleTemplatePicker
- [x] Task 1.2 commit: `f9bd0bf5f` — feat(3-wave1): integrate title templates into writer.py
- [x] Both verification commands pass
- [x] Backward compatibility confirmed (no required args for existing callers)
- [x] All 8 templates render without errors
- [x] _classify_title correctly maps comparison/ranking/toplist/buying_guide/budget patterns

## Known Stubs

None. TitleTemplatePicker is fully implemented. get_recent_styles() queries publish_log — will only start returning data after titles are published (expected behavior). Blog-specific overrides dict is empty by design for future use.

## Threat Flags

No threat flags — module adds no new network endpoints, auth paths, or file access patterns. get_recent_styles() connects to existing `curation.db` via sqlite3. No external API calls.

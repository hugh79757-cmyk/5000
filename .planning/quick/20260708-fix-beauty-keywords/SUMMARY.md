---
task: Fix publishing errors - remove generic keywords from beauty-hugo
status: complete
created: 2026-07-08
completed: 2026-07-08
---

## Summary

Fixed `beauty-hugo: similar_title (keyword=기획세트)` error by removing "기획세트" from beauty-hugo keywords in `pipelines/curation/keywords.py`.

### Changes Made
- Removed "기획세트" from beauty-hugo keywords (line 684)

### Verification
- Verified "기획세트" is no longer in beauty-hugo keyword list

### Related Fixes (This Session)
- Removed "가성비" from interior-hugo keywords (irrelevant_products fix)
- Added 'rap2', 'rap3' to TECH_IDENTIFIERS in post_validator.py (keyword_coverage fix)

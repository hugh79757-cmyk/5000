---
task: Fix publishing errors - remove generic keywords from beauty-hugo
status: in-progress
created: 2026-07-08
---

## Fix: beauty-hugo similar_title error

### Problem
- `beauty-hugo: similar_title (keyword=기획세트)` error
- "기획세트" is a generic keyword causing similar titles

### Fix
1. Remove "기획세트" from beauty-hugo keywords (line 684)
2. Verify all fixes with test commands

### Files to Edit
- `pipelines/curation/keywords.py` - Remove "기획세트" from beauty-hugo

### Verification
```bash
python3 -c "from pipelines.curation.keywords import KEYWORD_MAP; print('기획세트' in KEYWORD_MAP.get('beauty-hugo', []))"
```

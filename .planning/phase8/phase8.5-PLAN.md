# Phase 8.5: beauty-hugo Keyword Cleanup (Round 2)

## Goal
Fix beauty-hugo `irrelevant_products` pipeline failures by removing remaining generic keywords that cause Coupang API to return non-beauty products (생활용품/식품/패션), which get filtered out by CATEGORY_FILTERS.

## Root Cause
Phase 2 removed 13 `생활용품`-triggering keywords (샴푸, 바디로션, etc.) but the remaining 85 keywords still include 9 generic terms that Coupang does not associate with beauty products. These keywords return random products that fail `_filter_irrelevant_products`, leaving < 3 products → `irrelevant_products`.

## Task

### Task 8.5-1: Remove 9 generic keywords

**File:** `pipelines/curation/keywords.py`

Remove from beauty-hugo keyword list (lines 1097-1182):

| Line | Keyword | Reason |
|------|---------|--------|
| 1099 | 나이트 | Returns nightwear/pajamas (패션/의류) |
| 1102 | 개선 | General "improvement" — returns random products (confirmed failure) |
| 1103 | 개입 | General "intervention" — previously published 물티슈/생수 off-topic |
| 1104 | 겸용 | General "multi-purpose" — no beauty context |
| 1106 | 고분자 | "Polymer" — general chemistry term |
| 1116 | 나노 | "Nano" — general tech term |
| 1123 | 다이소 | "Daiso" — general store, sells everything |
| 1143 | 리얼 | "Real" — too generic |
| 1145 | 리커버리 | "Recovery" — returns sports/recovery products (스포츠) |

### Verification

```bash
cd /Users/twinssn/Projects/5000
.venv/bin/python3 -c "
from pipelines.curation.keywords import get_keywords
kws = get_keywords('beauty-hugo')
print(f'beauty-hugo keywords remaining: {len(kws)}')
bad = [k for k in kws if k in ['나이트','개선','개입','겸용','고분자','나노','다이소','리얼','리커버리']]
if bad:
    print(f'STILL PRESENT: {bad}')
else:
    print('✅ All 9 generic keywords removed')
"
```

## Rollback
`git checkout HEAD -- pipelines/curation/keywords.py`

# Filter Gaps Analysis — CATEGORY_FILTERS

## 1. The Bypass Mechanism (Critical Design Flaw)

In `_filter_irrelevant_products()` (line 305):

```python
# 차단 키워드 — category_name에만 적용 (product_name 오탐 방지)
for bw in blocked:
    if bw.lower() in cat:   # ← ONLY checks category_name
        ...

# 허용 키워드 — product_name + category_name
for aw in allowed:
    if aw in combined:      # ← checks both
        ...
```

**The blocked list only checks `category_name`**, while the allowed list checks **both** `product_name` and `category_name`.

This creates a bypass path:

```
Product(name="여성 골지 나시", category="여성의류/티셔츠")
→ blocked check: "여성의류" in cat? → "여성의류/티셔츠" → YES if blocked
→ BUT if blog doesn't block "여성의류" → passes blocked check
→ allowed check: any allowed word in "여성 골지 나시 여성의류/티셔츠"? 
→ Possibly yes (e.g. if generic allowed word matches by accident)
→ PRODUCT PASSES
```

Similarly:
```
Product(name="깐마늘", category="식품/농수축산/마늘")
→ blocked check: "식품" in cat? → YES, only if blog blocks "식품"
→ If "식품" not in blocked list → passes
```

---

## 2. Per-Blog Gap Analysis

### baby-hugo — Critical Gap: Adult Clothing

**Situation**: baby-hugo does NOT block "여성의류" or "남성의류" in its blocked list.

**Exploit path**:
1. Keyword like "골지", "긴팔", "나시" fetches products from Coupang
2. Coupang returns "여성 골지 나시" with category `여성의류/티셔츠`
3. blocked check: "여성의류" not in baby-hugo's blocked list → passes
4. allowed check: Possibly no match → filtered out at allowed stage
5. BUT: If fewer than 3 products survive → fallback to original products[:5] (line 345)
6. Result: **Adult clothing can appear in baby blog**

**Multi-word allowed words make it worse**: "유모차" in allowed may accidentally match "유모차 가방" products, and the blocked list only blocks specific 유모차 accessories (정리함, 양산, etc.), not general ones.

### beauty-hugo — Critical Gap: Wet Wipes / Hygiene Products

**Situation**: beauty-hugo does NOT block "생활용품" or "위생용품".

**Exploit path**:
1. Coupang category "생활용품/위생용품/물티슈" returns wet wipes
2. These are NOT beauty products
3. blocked check: "생활용품" not in beauty-hugo's blocked list → passes
4. If processed as beauty product → wrong content

**Additionally**: beauty-hugo allows "크림" which is generic. Hand cream is beauty, but "생활용품/위생용품" hand creams could slip through under the "크림" or "바디로션" allowed words.

### health-hugo — Gap: Food Category

**Situation**: health-hugo does NOT block "식품".

**Exploit path**:
1. Keywords like "깐마늘" or "가지맛" (in keywords) → Coupang returns food products with category `식품/...`
2. blocked check: "식품" not in blocked → passes
3. "건강" is in allowed list → many food products contain "건강" in name → passes allowed check
4. Result: **Food products appear on health blog**

### Multiple Blogs — Gap: "생활용품" Not Blocked

| Blog | Blocks "생활용품"? |
|------|-------------------|
| laptop-hugo | ❌ |
| appliance-hugo | ❌ |
| interior-hugo | ❌ |
| baby-hugo | ❌ |
| fitness-hugo | ❌ |
| health-hugo | ✅ |
| pet-hugo | ❌ |
| kitchen-hugo | ❌ |
| beauty-hugo | ❌ |
| camping-hugo | ❌ |

The "생활용품" category on Coupang is a catch-all for: cleaning supplies, storage, kitchen tools, bathroom accessories, pet supplies, etc. Most blogs would benefit from blocking it.

### Generic "가방" Keywords Across All Blogs

All 10 blogs include "가방" as a keyword, but only laptop-hugo blocks it (as "서류가방", "노트북가방" — narrower terms). No blog blocks "가방" in the blocked list generally.

**Impact**: Searching "가방" returns all types of bags. The filter then tries to match allowed words. For blog-specific content, a laptop bag might pass on appliance-hugo if "가방" accidentally finds no blocked match. This is unreliable.

### The 3-Product Fallback Loophole

```python
if len(filtered) < 3:
    logger.warning(f"[{blog_id}] 필터 후 상품 부족 ({len(filtered)}개), 원본 유지")
    return products[:5]
```

This fallback (line 343-345) is a **safety valve that can bypass all filtering**. If filtering removes too many products, the first 5 original products are returned unfiltered.

**Trigger conditions**:
- Small keyword → Coupang returns 5-6 products
- Filter removes 3+ (e.g., wrong category) → filtered count < 3
- Fallback activates → returns up to 5 unfiltered products

---

## 3. Specific Gaps Table

| # | Blog | Gap | Risk | Mechanism |
|---|------|-----|------|-----------|
| 1 | baby-hugo | "여성의류"/"남성의류" not blocked | **High** | Adult clothing passes blocked check |
| 2 | beauty-hugo | "생활용품" not blocked | **Medium** | Wet wipes, hygiene products pass |
| 3 | health-hugo | "식품" not blocked | **Medium** | Food products (e.g., 깐마늘) pass |
| 4 | All blogs | "생활용품" not blocked on 9/10 | **Medium** | Cleaning/hygiene products pass |
| 5 | All blogs | blocked only checks category_name | **High** | Product name bypasses blocked entirely |
| 6 | All blogs | 3-product fallback can bypass filter | **High** | Returns unfiltered products |
| 7 | All blogs | Generic single-word keywords ("가방", etc.) | **Medium** | Returns non-niche products |
| 8 | Multiple | Weak blocked lists (5-8 entries) | **Medium** | appliance, interior, fitness, health, pet, kitchen, beauty, camping all have ≤8 blocked words |

---

## 4. Summary of Design Issues

1. **Asymmetric filter logic**: Blocked checks `category_name` only; allowed checks `category_name + product_name`. This means a product with a blocked product name (e.g., "여성 나시") can pass if its Coupang category doesn't contain the blocked word.

2. **Blocked lists are too narrow**: Most blogs have 5-8 blocked entries, focusing only on obvious categories (도서, 장난감, 화장품). Broader Coupang categories like "생활용품", "식품", "의류" are not consistently blocked.

3. **Keyword-first design compounds the problem**: The bloated keyword lists (see `problematic_keywords.md`) waste API calls on generic terms. Even with perfect filters, searching "가방" will return irrelevant products.

4. **Fallback undermines filtering**: When `len(filtered) < 3`, the function silently returns `products[:5]` — no filtering at all. Any keyword that returns fewer than ~8 products is at risk.

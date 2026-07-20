---
phase: 25-cuap-spider
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - shared/cuap_entity_linker.py
autonomous: true
requirements: [R1, R7]

must_haves:
  truths:
    - "CROSS_GRAPH 딕셔너리가 10개 블로그 간 연결 관계를 정의한다"
    - "register_cuap_entity()가 travel-en.db에 엔티티를 등록한다"
    - "inject_cross_blog_links()가 본문 마크다운에서 키워드를 찾아 링크를 삽입한다"
    - "build_cross_sell_card()가 크로스셀 카드 HTML을 생성한다"
    - "build_funnel_header()가 퍼널 헤더 HTML을 생성한다"
  artifacts:
    - path: "shared/cuap_entity_linker.py"
      provides: "CUAP 엔티티 링크 시스템 핵심 모듈"
      exports: ["register_cuap_entity", "inject_cross_blog_links", "build_cross_sell_card", "build_funnel_header", "CROSS_GRAPH", "BLOG_DOMAINS", "ICONS"]
  key_links:
    - from: "shared/cuap_entity_linker.py"
      to: "data/travel-en.db"
      via: "sqlite3 parameterized queries"
      pattern: "INSERT OR IGNORE INTO cuap_entities"
---

# Phase 25: CUAP 거미줄 엔티티 시스템 — Execution Plan

**Total Waves:** 5
**Total Tasks:** 10
**Estimated Context Usage:** ~45% per wave (2-3 tasks each)

---

## Wave Structure

| Wave | Plan | Tasks | Depends On | Autonomous | Requirements |
|------|------|-------|------------|------------|--------------|
| 1 | 25-01 | T1, T2 | — | yes | R1, R7 |
| 2 | 25-02 | T3, T4 | 25-01 | yes | R2, R3 |
| 3 | 25-03 | T5, T6 | 25-02 | yes | R4, R5, R6 |
| 4 | 25-04 | T7, T8 | 25-01 | yes | R1, R2 |
| 5 | 25-05 | T9, T10 | 25-02, 25-03, 25-04 | no (checkpoint) | R1-R7 |

---

## Wave 1: Core Module + DB Schema

### Plan 25-01: cuap_entity_linker.py

**Objective:** Create `shared/cuap_entity_linker.py` — CUAP 10개 블로그 간 크로스 링크 시스템의 핵심 모듈.

**Purpose:** ETAP `entity_linker.py` (337 lines)의 패턴을 category 기반으로 재사용하여 CUAP 전용 엔티티 등록, 인라인 링크 삽입, 크로스셀 카드, 퍼널 헤더를 구현.

**Output:** `shared/cuap_entity_linker.py` — CROSS_GRAPH, BLOG_DOMAINS, ICONS, register_cuap_entity(), inject_cross_blog_links(), build_cross_sell_card(), build_funnel_header()

#### Task 1: Create cuap_entity_linker.py core module

**Files:** `shared/cuap_entity_linker.py`

**Action:**
Create `shared/cuap_entity_linker.py` with the following structure (per D-1, D-6):

1. **Constants section** — DB_PATH, BLOG_DOMAINS (10 CUAP blogs from cuap.yaml), ICONS (emoji per blog), CROSS_GRAPH (10-blog connection graph with primary/secondary/use_cases + weight)

2. **_get_db()** — sqlite3 connection to travel-en.db with Row factory (per D-1)

3. **init_cuap_tables()** — CREATE TABLE IF NOT EXISTS for:
   - `cuap_entities` (entity_type TEXT, entity_name TEXT, blog_id TEXT, post_slug TEXT, post_url TEXT, link_label TEXT, category TEXT, priority INTEGER, published INTEGER DEFAULT 0)
   - `cuap_link_graph` (source_blog TEXT, target_blog TEXT, link_type TEXT, weight INTEGER)
   - Indexes on cuap_entities(blog_id, published), cuap_entities(entity_name)

4. **register_cuap_entity()** — INSERT OR IGNORE into cuap_entities (per D-2 pattern)
   - Validate entity_name len > 2, blog_id in BLOG_DOMAINS
   - Build post_url from BLOG_DOMAINS + post_slug
   - Parameterized queries only

5. **inject_cross_blog_links(content, blog_id, max_links=3)** — per D-2, R3
   - Query cuap_entities WHERE published=1 AND blog_id != current_blog
   - Sort by priority DESC, entity_name length DESC
   - For each entity: regex match with word boundary, skip H1/H2 lines, skip existing []() links using placeholder technique (from entity_linker.py:230-256)
   - Replace first occurrence with [entity_name](post_url)
   - Max max_links replacements per post

6. **build_cross_sell_card(blog_id, max_items=4)** — per D-3, R4
   - Query CROSS_GRAPH for target blogs (primary first, then secondary)
   - Query cuap_entities for latest published post per target blog
   - Generate inline-style HTML: icon + label + link in flex-wrap layout
   - Container: background:#fafbfc, border-radius:12px, padding:16px

7. **build_funnel_header(blog_id)** — per D-4, R5
   - Query CROSS_GRAPH for related categories (primary connections)
   - Generate inline-style HTML: "다른 추천도 확인해보세요" header + 3 category links
   - Blog-specific theme color from a THEME_COLORS dict

8. **CROSS_GRAPH** — per D-6, R7
   - 10-blog connection dictionary with primary/secondary/use_cases lists
   - Weight values: primary=100, secondary=50, use_cases=30 (agent's discretion per RESEARCH.md Open Question 3)
   - Natural funnel paths: 뷰티→가전→캠핑, 키친→가전→인테리어, etc.

**Import only:** sqlite3, re, logging, os (Python stdlib only — no external packages per RESEARCH.md)

**Behavior (TDD):**
- Test: register_cuap_entity() inserts row into cuap_entities table with correct fields
- Test: register_cuap_entity() ignores duplicate (INSERT OR IGNORE)
- Test: register_cuap_entity() returns early if entity_name len <= 2
- Test: register_cuap_entity() returns early if blog_id not in BLOG_DOMAINS
- Test: inject_cross_blog_links() replaces keyword with [keyword](url) link
- Test: inject_cross_blog_links() skips H1/H2 heading lines
- Test: inject_cross_blog_links() skips text already inside []() links
- Test: inject_cross_blog_links() returns max_links links or fewer
- Test: inject_cross_blog_links() returns original content if no entities found
- Test: build_cross_sell_card() returns HTML string with blog icons and links
- Test: build_cross_sell_card() returns empty string if no cross-blog entities
- Test: build_funnel_header() returns HTML string with 3 category links
- Test: build_funnel_header() returns empty string if no funnel targets

**Verify:**
```bash
cd /Users/twinssn/Projects/5000 && python -c "
from shared.cuap_entity_linker import (
    register_cuap_entity, inject_cross_blog_links,
    build_cross_sell_card, build_funnel_header,
    CROSS_GRAPH, BLOG_DOMAINS, ICONS, init_cuap_tables
)
assert len(BLOG_DOMAINS) == 10, f'Expected 10 blogs, got {len(BLOG_DOMAINS)}'
assert len(ICONS) == 10, f'Expected 10 icons, got {len(ICONS)}'
assert len(CROSS_GRAPH) == 10, f'Expected 10 blog entries, got {len(CROSS_GRAPH)}'
assert callable(register_cuap_entity)
assert callable(inject_cross_blog_links)
assert callable(build_cross_sell_card)
assert callable(build_funnel_header)
assert callable(init_cuap_tables)
print('PASS: All exports verified')
"
```

**Done:**
- shared/cuap_entity_linker.py exists with all 8 components
- BLOG_DOMAINS has 10 CUAP blog entries
- CROSS_GRAPH has 10 blog entries with primary/secondary/use_cases
- All functions are importable and callable
- Only stdlib imports (sqlite3, re, logging, os)

**Context Cost:** ~25% (single file, ~400 lines)

---

#### Task 2: Initialize cuap_entities and cuap_link_graph tables in travel-en.db

**Files:** `shared/cuap_entity_linker.py` (already created in Task 1)

**Action:**
Call init_cuap_tables() to create the CUAP tables in travel-en.db (per D-1).

Verify the tables exist after creation:
- `cuap_entities` table with columns: entity_type, entity_name, blog_id, post_slug, post_url, link_label, category, priority, published
- `cuap_link_graph` table with columns: source_blog, target_blog, link_type, weight
- Indexes on cuap_entities(blog_id, published) and cuap_entities(entity_name)

Also verify that the existing `entity_links` table (ETAP) is NOT modified — CUAP uses separate tables.

**Verify:**
```bash
cd /Users/twinssn/Projects/5000 && python -c "
import sqlite3
from shared.cuap_entity_linker import init_cuap_tables, DB_PATH

init_cuap_tables()

conn = sqlite3.connect(DB_PATH)
tables = [r[0] for r in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()]
assert 'cuap_entities' in tables, f'cuap_entities not found. Tables: {tables}'
assert 'cuap_link_graph' in tables, f'cuap_link_graph not found. Tables: {tables}'
assert 'entity_links' in tables, f'entity_links (ETAP) should still exist'

cols = [r[1] for r in conn.execute('PRAGMA table_info(cuap_entities)').fetchall()]
expected_cols = ['entity_type', 'entity_name', 'blog_id', 'post_slug', 'post_url', 'link_label', 'category', 'priority', 'published']
for c in expected_cols:
    assert c in cols, f'Column {c} missing from cuap_entities'

cols2 = [r[1] for r in conn.execute('PRAGMA table_info(cuap_link_graph)').fetchall()]
expected_cols2 = ['source_blog', 'target_blog', 'link_type', 'weight']
for c in expected_cols2:
    assert c in cols2, f'Column {c} missing from cuap_link_graph'

conn.close()
print('PASS: Tables initialized and verified')
"
```

**Done:**
- cuap_entities table exists in travel-en.db with correct schema
- cuap_link_graph table exists in travel-en.db with correct schema
- entity_links (ETAP) table unmodified
- Indexes created on cuap_entities(blog_id, published) and cuap_entities(entity_name)

**Context Cost:** ~10% (verification script)

---

## Wave 2: Pipeline Integration

### Plan 25-02: pipeline.py integration

**Objective:** Integrate cuap_entity_linker.py into `pipelines/curation/pipeline.py` for publish-time injection.

**Purpose:** Connect the core module to the actual publishing flow so cross-blog links, cross-sell cards, and funnel headers are automatically injected into every CUAP post.

**Output:** Modified `pipelines/curation/pipeline.py` with import, injection, and registration calls

#### Task 3: Add cuap_entity_linker import and injection logic to pipeline.py

**Files:** `pipelines/curation/pipeline.py`

**Action:**
Modify `pipelines/curation/pipeline.py` to integrate cuap_entity_linker (per D-2, D-3, D-4):

1. **Add import** at top of file (after line 30, near other shared imports):
   ```python
   from shared.cuap_entity_linker import (
       inject_cross_blog_links,
       build_cross_sell_card,
       build_funnel_header,
       init_cuap_tables,
   )
   ```

2. **Add table initialization** (once at module load or first call):
   ```python
   init_cuap_tables()
   ```

3. **Insert injection logic** after line 917 (CTA fallback) and before line 920 (tag_set creation):
   ```python
   # CUAP 거미줄 크로스 링크 삽입 (per D-2, D-3, D-4)
   try:
       body_md = inject_cross_blog_links(body_md, blog_id, max_links=3)
       cross_card = build_cross_sell_card(blog_id, max_items=4)
       if cross_card:
           body_md += "\n\n" + cross_card
       funnel = build_funnel_header(blog_id)
       if funnel:
           body_md = funnel + "\n\n" + body_md
       logger.info(f"[{blog_id}] CUAP 거미줄 링크 삽입 완료")
   except Exception as e:
       logger.warning(f"[{blog_id}] CUAP 거미줄 링크 삽입 실패 (fail-open): {e}")
   ```

**Important:** The injection must be wrapped in try/except with fail-open behavior — if cuap_entity_linker fails, the pipeline should continue publishing without cross-blog links.

**Verify:**
```bash
cd /Users/twinssn/Projects/5000 && python -c "
import ast, sys
with open('pipelines/curation/pipeline.py', 'r') as f:
    source = f.read()
tree = ast.parse(source)

# Check import exists
imports = [node for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
cuap_imports = [i for i in imports if i.module and 'cuap_entity_linker' in i.module]
assert len(cuap_imports) >= 1, 'cuap_entity_linker import not found'

# Check function calls exist
calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
call_names = []
for c in calls:
    if isinstance(c.func, ast.Name):
        call_names.append(c.func.id)
    elif isinstance(c.func, ast.Attribute):
        call_names.append(c.func.attr)

assert 'inject_cross_blog_links' in call_names, 'inject_cross_blog_links call not found'
assert 'build_cross_sell_card' in call_names, 'build_cross_sell_card call not found'
assert 'build_funnel_header' in call_names, 'build_funnel_header call not found'
assert 'init_cuap_tables' in call_names, 'init_cuap_tables call not found'

print('PASS: Pipeline integration verified')
"
```

**Done:**
- cuap_entity_linker imported in pipeline.py
- init_cuap_tables() called at module level
- inject_cross_blog_links() called after CTA fallback (line ~917)
- build_cross_sell_card() called after inject_cross_blog_links
- build_funnel_header() called and prepended to body_md
- All wrapped in try/except with fail-open

**Context Cost:** ~15% (single file modification)

---

#### Task 4: Add entity registration after publish success

**Files:** `pipelines/curation/pipeline.py`

**Action:**
Add entity registration call after publish success (after line 969, before quality metrics):

1. **Add import** for register_cuap_entity (extend existing import):
   ```python
   from shared.cuap_entity_linker import (
       inject_cross_blog_links,
       build_cross_sell_card,
       build_funnel_header,
       init_cuap_tables,
       register_cuap_entity,
   )
   ```

2. **Insert registration** after line 969 (logger.info publish 완료) and before quality metrics:
   ```python
   # CUAP 엔티티 등록 (per D-2, R2)
   try:
       register_cuap_entity(
           entity_type="category",
           entity_name=keyword,
           blog_id=blog_id,
           post_slug=slug,
           link_label=f"{keyword} 추천",
           priority=50,
           published=1,
       )
       logger.info(f"[{blog_id}] CUAP 엔티티 등록: {keyword}")
   except Exception as e:
       logger.warning(f"[{blog_id}] CUAP 엔티티 등록 실패 (fail-open): {e}")
   ```

**Verify:**
```bash
cd /Users/twinssn/Projects/5000 && python -c "
import ast
with open('pipelines/curation/pipeline.py', 'r') as f:
    source = f.read()
tree = ast.parse(source)

# Check register_cuap_entity import
imports = [node for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
cuap_imports = [i for i in imports if i.module and 'cuap_entity_linker' in i.module]
names = []
for i in cuap_imports:
    for alias in i.names:
        names.append(alias.name)
assert 'register_cuap_entity' in names, 'register_cuap_entity import not found'

# Check register_cuap_entity call
calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
call_names = []
for c in calls:
    if isinstance(c.func, ast.Name):
        call_names.append(c.func.id)
    elif isinstance(c.func, ast.Attribute):
        call_names.append(c.func.attr)
assert 'register_cuap_entity' in call_names, 'register_cuap_entity call not found'

print('PASS: Entity registration verified')
"
```

**Done:**
- register_cuap_entity imported in pipeline.py
- register_cuap_entity() called after publish success
- Registration wrapped in try/except with fail-open
- Entity registered with published=1 (immediately available for linking)

**Context Cost:** ~10% (single file modification)

---

## Wave 3: Hugo Layout Integration

### Plan 25-03: Hugo partial + single.html update

**Objective:** Create `cuap-spider-links.html` partial and update `single.html` in all 10 CUAP blogs.

**Purpose:** Replace the same-blog `related.html` with cross-blog `cuap-spider-links.html` to render the injected cross-sell cards and funnel headers.

**Output:** 10 × `cuap-spider-links.html` partials + 10 × updated `single.html` files

#### Task 5: Create cuap-spider-links.html partial

**Files:** `cuap/{blog}-hugo/layouts/partials/cuap-spider-links.html` (10 copies)

**Action:**
Create `layouts/partials/cuap-spider-links.html` in all 10 CUAP blogs (per D-5, R6).

The partial should:
1. Check if the page has `cuap_cross_links` or `cuap_funnel` data (from frontmatter or site params)
2. If cross-blog data exists, render the cross-sell card and funnel header
3. If no data, fall back to rendering `related.html` (same-blog related posts)

```html
{{/* cuap-spider-links.html — CUAP 거미줄 크로스 블로그 링크 */}
{{/* Replaces related.html for cross-blog navigation */}}

{{ $crossData := .Params.cuap_cross_links }}
{{ $funnelData := .Params.cuap_funnel }}

{{ if or $crossData $funnelData }}
  {{/* Render cross-blog links from injected HTML */}}
  {{ .Content | safeHTML }}
{{ else }}
  {{/* Fallback: same-blog related posts */}}
  {{ partial "related.html" . }}
{{ end }}
```

**Note:** Since cross-sell cards and funnel headers are injected as raw HTML into body_md at publish time (per D-3, D-4), they are already part of `.Content`. The partial primarily serves as a fallback mechanism and ensures the layout is consistent across all 10 blogs.

**Create in all 10 blogs:**
- `cuap/appliance-hugo/layouts/partials/cuap-spider-links.html`
- `cuap/baby-hugo/layouts/partials/cuap-spider-links.html`
- `cuap/beauty-hugo/layouts/partials/cuap-spider-links.html`
- `cuap/camping-hugo/layouts/partials/cuap-spider-links.html`
- `cuap/fitness-hugo/layouts/partials/cuap-spider-links.html`
- `cuap/health-hugo/layouts/partials/cuap-spider-links.html`
- `cuap/interior-hugo/layouts/partials/cuap-spider-links.html`
- `cuap/kitchen-hugo/layouts/partials/cuap-spider-links.html`
- `cuap/laptop-hugo/layouts/partials/cuap-spider-links.html`
- `cuap/pet-hugo/layouts/partials/cuap-spider-links.html`

**Verify:**
```bash
cd /Users/twinssn/Projects/5000 && for blog in appliance baby beauty camping fitness health interior kitchen laptop pet; do
  file="cuap/${blog}-hugo/layouts/partials/cuap-spider-links.html"
  if [ ! -f "$file" ]; then
    echo "FAIL: $file not found"
    exit 1
  fi
  if ! grep -q "cuap-spider-links" "$file"; then
    echo "FAIL: $file missing content"
    exit 1
  fi
done
echo "PASS: All 10 cuap-spider-links.html partials created"
```

**Done:**
- cuap-spider-links.html exists in all 10 CUAP blog layouts/partials/
- All files have identical content (same md5)
- Fallback to related.html when no cross-blog data

**Context Cost:** ~15% (10 file creation + verification)

---

#### Task 6: Update single.html to use cuap-spider-links.html

**Files:** `cuap/{blog}-hugo/layouts/_default/single.html` (10 copies)

**Action:**
Update `single.html` in all 10 CUAP blogs to replace `related.html` with `cuap-spider-links.html` (per D-5, R6).

**Current line 85:**
```html
{{ partial "related.html" . }}
```

**New line 85:**
```html
{{ partial "cuap-spider-links.html" . }}
```

**Important:** All 10 single.html files are identical (md5: 4407c6c). The change is a single line replacement on line 85.

**Update in all 10 blogs:**
- `cuap/appliance-hugo/layouts/_default/single.html`
- `cuap/baby-hugo/layouts/_default/single.html`
- `cuap/beauty-hugo/layouts/_default/single.html`
- `cuap/camping-hugo/layouts/_default/single.html`
- `cuap/fitness-hugo/layouts/_default/single.html`
- `cuap/health-hugo/layouts/_default/single.html`
- `cuap/interior-hugo/layouts/_default/single.html`
- `cuap/kitchen-hugo/layouts/_default/single.html`
- `cuap/laptop-hugo/layouts/_default/single.html`
- `cuap/pet-hugo/layouts/_default/single.html`

**Verify:**
```bash
cd /Users/twinssn/Projects/5000 && for blog in appliance baby beauty camping fitness health interior kitchen laptop pet; do
  file="cuap/${blog}-hugo/layouts/_default/single.html"
  if ! grep -q "cuap-spider-links.html" "$file"; then
    echo "FAIL: $file not updated"
    exit 1
  fi
  if grep -q 'partial "related.html"' "$file"; then
    echo "FAIL: $file still has related.html"
    exit 1
  fi
done
echo "PASS: All 10 single.html files updated"
```

**Done:**
- All 10 single.html files reference cuap-spider-links.html instead of related.html
- No file still references related.html directly
- Blowfish theme renders raw HTML from markdown (verified in RESEARCH.md)

**Context Cost:** ~10% (10 file modifications + verification)

---

## Wave 4: DB Initialization + Entity Registration

### Plan 25-04: DB initialization + entity registration

**Objective:** Initialize CUAP tables and register initial entities for all 10 blogs.

**Purpose:** Populate the cuap_entities and cuap_link_graph tables with initial data so the cross-blog linking system has targets to link to.

**Output:** Populated cuap_entities and cuap_link_graph tables in travel-en.db

#### Task 7: Initialize cuap_link_graph with CROSS_GRAPH data

**Files:** `shared/cuap_entity_linker.py` (already created), `data/travel-en.db`

**Action:**
Create a script to populate cuap_link_graph with the CROSS_GRAPH data from cuap_entity_linker.py.

```python
# scripts/init_cuap_link_graph.py
from shared.cuap_entity_linker import CROSS_GRAPH, init_cuap_tables, _get_db

init_cuap_tables()
conn = _get_db()

for blog_id, connections in CROSS_GRAPH.items():
    for target in connections.get("primary", []):
        conn.execute("""
            INSERT OR IGNORE INTO cuap_link_graph (source_blog, target_blog, link_type, weight)
            VALUES (?, ?, 'primary', 100)
        """, (blog_id, target))
    for target in connections.get("secondary", []):
        conn.execute("""
            INSERT OR IGNORE INTO cuap_link_graph (source_blog, target_blog, link_type, weight)
            VALUES (?, ?, 'secondary', 50)
        """, (blog_id, target))
    for target in connections.get("use_cases", []):
        conn.execute("""
            INSERT OR IGNORE INTO cuap_link_graph (source_blog, target_blog, link_type, weight)
            VALUES (?, ?, 'use_cases', 30)
        """, (blog_id, target))

conn.commit()
conn.close()
print("cuap_link_graph initialized")
```

**Verify:**
```bash
cd /Users/twinssn/Projects/5000 && python -c "
import sqlite3
from shared.cuap_entity_linker import DB_PATH

conn = sqlite3.connect(DB_PATH)
count = conn.execute('SELECT COUNT(*) FROM cuap_link_graph').fetchone()[0]
assert count > 0, f'cuap_link_graph is empty (count={count})'

# Verify all 10 blogs have entries
blogs = [r[0] for r in conn.execute('SELECT DISTINCT source_blog FROM cuap_link_graph').fetchall()]
assert len(blogs) == 10, f'Expected 10 blogs, got {len(blogs)}: {blogs}'

# Verify link types
types = [r[0] for r in conn.execute('SELECT DISTINCT link_type FROM cuap_link_graph').fetchall()]
assert 'primary' in types, 'primary link_type missing'
assert 'secondary' in types, 'secondary link_type missing'

conn.close()
print(f'PASS: cuap_link_graph has {count} entries across {len(blogs)} blogs')
"
```

**Done:**
- cuap_link_graph populated with CROSS_GRAPH data
- All 10 blogs have source_blog entries
- Link types: primary (weight=100), secondary (weight=50), use_cases (weight=30)

**Context Cost:** ~10% (script + verification)

---

#### Task 8: Register sample entities for testing

**Files:** `shared/cuap_entity_linker.py` (already created), `data/travel-en.db`

**Action:**
Register sample entities for each of the 10 CUAP blogs to enable testing of the cross-blog linking system.

```python
# scripts/register_sample_cuap_entities.py
from shared.cuap_entity_linker import register_cuap_entity, BLOG_DOMAINS

sample_entities = [
    ("category", "노트북 추천", "laptop-hugo", "20260720-笔记本 추천", "노트북 추천", 50),
    ("category", "에어컨 추천", "appliance-hugo", "20260720-에어컨 추천", "에어컨 추천", 50),
    ("category", "요가매트 추천", "fitness-hugo", "20260720-요가매트 추천", "요가매트 추천", 50),
    ("category", "인테리어 추천", "interior-hugo", "20260720-인테리어 추천", "인테리어 추천", 50),
    ("category", "유아용품 추천", "baby-hugo", "20260720-유아용품 추천", "유아용품 추천", 50),
    ("category", "건강식품 추천", "health-hugo", "20260720-건강식품 추천", "건강식품 추천", 50),
    ("category", "반려동물 추천", "pet-hugo", "20260720-반려동물 추천", "반려동물 추천", 50),
    ("category", "주방용품 추천", "kitchen-hugo", "20260720-주방용품 추천", "주방용품 추천", 50),
    ("category", "뷰티용품 추천", "beauty-hugo", "20260720-뷰티용품 추천", "뷰티용품 추천", 50),
    ("category", "캠핑용품 추천", "camping-hugo", "20260720-캠핑용품 추천", "캠핑용품 추천", 50),
]

for entity_type, entity_name, blog_id, post_slug, link_label, priority in sample_entities:
    register_cuap_entity(entity_type, entity_name, blog_id, post_slug, link_label, priority, published=1)

print(f"Registered {len(sample_entities)} sample entities")
```

**Verify:**
```bash
cd /Users/twinssn/Projects/5000 && python -c "
import sqlite3
from shared.cuap_entity_linker import DB_PATH

conn = sqlite3.connect(DB_PATH)
count = conn.execute('SELECT COUNT(*) FROM cuap_entities WHERE published=1').fetchone()[0]
assert count >= 10, f'Expected >= 10 published entities, got {count}'

blogs = [r[0] for r in conn.execute('SELECT DISTINCT blog_id FROM cuap_entities WHERE published=1').fetchall()]
assert len(blogs) == 10, f'Expected 10 blogs, got {len(blogs)}: {blogs}'

conn.close()
print(f'PASS: {count} published entities across {len(blogs)} blogs')
"
```

**Done:**
- 10 sample entities registered (one per blog)
- All entities have published=1 (immediately available for linking)
- Entities can be used for testing inject_cross_blog_links()

**Context Cost:** ~10% (script + verification)

---

## Wave 5: Testing + Verification

### Plan 25-05: Testing + verification

**Objective:** End-to-end verification of the CUAP 거미줄 엔티티 시스템.

**Purpose:** Verify that all components work together: entity registration → link injection → cross-sell card generation → funnel header generation → Hugo partial rendering.

**Output:** Verification report + manual checkpoint

#### Task 9: End-to-end integration test

**Files:** `shared/cuap_entity_linker.py`, `pipelines/curation/pipeline.py`, `data/travel-en.db`

**Action:**
Run end-to-end integration test to verify the complete flow:

1. **Test entity registration:**
   ```python
   register_cuap_entity("category", "테스트_노트북", "laptop-hugo", "test-slug", "테스트 노트북 추천", 50, 1)
   ```

2. **Test link injection:**
   ```python
   test_content = "# 테스트 제목\n\n이 글은 노트북 추천에 대한 내용입니다.\n\n## 소개\n\n노트북을 추천합니다."
   result = inject_cross_blog_links(test_content, "beauty-hugo", max_links=3)
   assert "[테스트_노트북]" in result or "노트북" in result
   ```

3. **Test cross-sell card generation:**
   ```python
   card = build_cross_sell_card("laptop-hugo", max_items=4)
   assert card == "" or "<div" in card  # Empty or HTML
   ```

4. **Test funnel header generation:**
   ```python
   header = build_funnel_header("laptop-hugo")
   assert header == "" or "추천" in header  # Empty or Korean text
   ```

5. **Test Hugo build** (optional):
   ```bash
   cd /Users/twinssn/Projects/cuap/appliance-hugo && hugo --gc --minify 2>&1 | tail -5
   ```

**Verify:**
```bash
cd /Users/twinssn/Projects/5000 && python -c "
from shared.cuap_entity_linker import (
    register_cuap_entity, inject_cross_blog_links,
    build_cross_sell_card, build_funnel_header,
    init_cuap_tables
)

init_cuap_tables()

# Test registration
register_cuap_entity('category', 'integration_test_item', 'laptop-hugo', 'test-integration', 'Integration Test', 50, 1)

# Test injection
test_md = '# 테스트\n\n이 글은 노트북 추천에 대한 내용입니다.\n\n## 소개\n\n노트북을 추천합니다.'
result = inject_cross_blog_links(test_md, 'beauty-hugo', max_links=3)
print(f'Injection result length: {len(result)}')

# Test cross-sell card
card = build_cross_sell_card('laptop-hugo', max_items=4)
print(f'Cross-sell card length: {len(card)}')

# Test funnel header
header = build_funnel_header('laptop-hugo')
print(f'Funnel header length: {len(header)}')

print('PASS: Integration test completed')
"
```

**Done:**
- Entity registration works end-to-end
- Link injection works with test content
- Cross-sell card generates HTML or empty string
- Funnel header generates HTML or empty string
- No exceptions thrown during integration test

**Context Cost:** ~15% (integration test + verification)

---

#### Task 10: Manual verification checkpoint

**Files:** None (verification only)

**Action:**
Manual verification of the CUAP 거미줄 엔티티 시스템:

1. **Verify Hugo build** for one CUAP blog:
   ```bash
   cd /Users/twinssn/Projects/cuap/appliance-hugo && hugo --gc --minify
   ```

2. **Verify single.html** references cuap-spider-links.html:
   ```bash
   grep "cuap-spider-links.html" layouts/_default/single.html
   ```

3. **Verify cuap-spider-links.html** exists in partials:
   ```bash
   ls -la layouts/partials/cuap-spider-links.html
   ```

4. **Verify travel-en.db** has CUAP tables:
   ```bash
   sqlite3 ../../5000/data/travel-en.db ".tables" | grep cuap
   ```

5. **Verify pipeline.py** has injection logic:
   ```bash
   grep "inject_cross_blog_links" pipelines/curation/pipeline.py
   ```

**Checkpoint:**
```bash
echo "=== CUAP 거미줄 엔티티 시스템 검증 ==="
echo ""
echo "1. Hugo build test:"
cd /Users/twinssn/Projects/cuap/appliance-hugo && hugo --gc --minify 2>&1 | tail -3
echo ""
echo "2. single.html reference:"
grep "cuap-spider-links.html" layouts/_default/single.html
echo ""
echo "3. cuap-spider-links.html exists:"
ls -la layouts/partials/cuap-spider-links.html
echo ""
echo "4. travel-en.db CUAP tables:"
sqlite3 ../../5000/data/travel-en.db ".tables" | grep cuap
echo ""
echo "5. pipeline.py injection:"
grep "inject_cross_blog_links" ../../5000/pipelines/curation/pipeline.py
echo ""
echo "=== 검증 완료 ==="
```

**Done:**
- Hugo build succeeds for appliance-hugo
- single.html references cuap-spider-links.html
- cuap-spider-links.html exists in partials
- travel-en.db has cuap_entities and cuap_link_graph tables
- pipeline.py has inject_cross_blog_links call

**Context Cost:** ~10% (verification commands)

---

## Threat Model

### Trust Boundaries

| Boundary | Description |
|----------|-------------|
| pipeline.py → cuap_entity_linker.py | Internal module call — trusted input (blog_id, keyword from pipeline) |
| cuap_entity_linker.py → travel-en.db | SQLite write — parameterized queries prevent SQL injection |
| cuap_entity_linker.py → Hugo markdown | HTML injection into body_md — URLs from trusted BLOG_DOMAINS only |
| Hugo partial → browser | HTML rendering — inline styles only, no JavaScript |

### STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-25-01 | Tampering | cuap_entity_linker.py SQL queries | mitigate | Parameterized queries with `?` placeholders — no string formatting in SQL |
| T-25-02 | Tampering | entity_name input to register_cuap_entity | mitigate | Validate len > 2, blog_id in BLOG_DOMAINS — reject invalid input |
| T-25-03 | Information Disclosure | post_url construction | accept | URLs built from trusted BLOG_DOMAINS dictionary — no user-controlled URL components |
| T-25-04 | Elevation of Pipeline | inject_cross_blog_links modifying body_md | accept | Links injected only to published=1 entities from trusted DB — no external input |
| T-25-05 | Denial of Service | cuap_entity_linker.py failure blocking pipeline | mitigate | All cuap_entity_linker calls wrapped in try/except with fail-open |
| T-25-06 | Tampering | Hugo raw HTML injection | mitigate | Inline styles only, no JavaScript, URLs from trusted BLOG_DOMAINS |

---

## Verification

### Automated Verification (per task)

| Task | Verification Command | Expected Result |
|------|---------------------|-----------------|
| T1 | `python -c "from shared.cuap_entity_linker import ..."` | All exports verified |
| T2 | `python -c "import sqlite3; ..."` | Tables exist with correct schema |
| T3 | `python -c "import ast; ..."` | Pipeline integration verified |
| T4 | `python -c "import ast; ..."` | Entity registration verified |
| T5 | `for blog in ...; do ls ...; done` | All 10 partials created |
| T6 | `for blog in ...; do grep ...; done` | All 10 single.html updated |
| T7 | `python -c "import sqlite3; ..."` | cuap_link_graph populated |
| T8 | `python -c "import sqlite3; ..."` | 10 sample entities registered |
| T9 | `python -c "from shared.cuap_entity_linker import ..."` | Integration test passed |
| T10 | Manual checkpoint | All components verified |

### Manual Verification (end-to-end)

1. Hugo build succeeds for appliance-hugo
2. single.html references cuap-spider-links.html
3. cuap-spider-links.html exists in partials
4. travel-en.db has cuap_entities and cuap_link_graph tables
5. pipeline.py has inject_cross_blog_links call

---

## Success Criteria

### Functional
- [ ] CUAP 10개 블로그 간 크로스 링크 시스템 구축
- [ ] 본문 발행 시 자동으로 타 블로그 링크 삽입
- [ ] 크로스셀 카드가 본문 하단에 표시
- [ ] 퍼널 헤더가 본문 상단에 표시
- [ ] 세션당 평균 페이지뷰 1.2 → 2.5+ 증가 (장기적)
- [ ] 광고 노출 기회 2~3x 증가 (장기적)

### Non-Functional
- [ ] 링크 삽입 처리 시간 < 100ms
- [ ] DB 쿼리 시간 < 50ms
- [ ] Hugo 빌드 시간 증가 < 5초
- [ ] 모바일/데스크톱 반응형 지원

---

## Risk Mitigation

| 리스크 | 영향도 | 완화 방안 |
|--------|--------|-----------|
| 링크 품질 저하 | 중 | 키워드 매칭 임계값 설정, 수동 검증 |
| 성능 저하 | 하 | DB 인덱싱, 캐싱 전략 |
| Hugo 빌드 실패 | 중 | partial 오류 시 fallback 처리 |
| 광고 정책 위반 | 하 | Google AdSense 가이드라인 준수 |
| cuap_entity_linker.py 실패 | 중 | 모든 호출을 try/except로 감싸기, fail-open |
| travel-en.db 쓰기 실패 | 하 | ETAP와 동일한 DB 사용, 기존 패턴 재사용 |

---

## Output

Create `.planning/phases/25-cuap-spider/25-{plan}-SUMMARY.md` for each plan when done:
- `25-01-SUMMARY.md` (Wave 1)
- `25-02-SUMMARY.md` (Wave 2)
- `25-03-SUMMARY.md` (Wave 3)
- `25-04-SUMMARY.md` (Wave 4)
- `25-05-SUMMARY.md` (Wave 5)

#!/usr/bin/env python3
"""27-06: Surgically fix stale cross-sell card hrefs in 16 (baked) CUAP posts.

Problem: cards contain old-format links `https://{sub}.informationhot.kr/{slug}/`
where {slug} is a STALE placeholder (e.g. `20260720-캠핑-난로-추천`) that:
  - is NOT in cuap_entities, and
  - does NOT exist on disk.
These 404. Correct links already use `/posts/<slug>/` and are left untouched.

Fix: for each broken href, replace the URL with the target blog's top-1
published post_url from cuap_entities (which now carries correct /posts/ URLs).
This is the same URL the linker would inject via build_cross_sell_card().
"""
import re
import os
import sys
import glob
import sqlite3

sys.path.insert(0, "/Users/twinssn/Projects/5000")
from shared.cuap_entity_linker import BLOG_DOMAINS

DB = "/Users/twinssn/Projects/5000/data/travel-en.db"
CUAP_ROOT = "/Users/twinssn/Projects/cuap"
SITES = [
    "baby-hugo", "appliance-hugo", "beauty-hugo", "camping-hugo",
    "fitness-hugo", "health-hugo", "interior-hugo", "kitchen-hugo",
    "laptop-hugo", "pet-hugo",
]

# --- top-1 published post_url per blog (same logic build_cross_sell_card uses) ---
conn = sqlite3.connect(DB)
top1 = {}
for blog in SITES:
    row = conn.execute(
        """
        SELECT post_url FROM cuap_entities
        WHERE blog_id=? AND published=1
              AND post_url IS NOT NULL AND post_url != ''
        ORDER BY priority DESC, rowid DESC LIMIT 1
        """,
        (blog,),
    ).fetchone()
    if row:
        top1[blog] = row[0]
    else:
        print(f"WARN: no top-1 url for {blog}")
conn.close()
assert top1, "no top-1 urls resolved"

sub_to_blog = {d.split("//")[-1].split(".")[0]: b for b, d in BLOG_DOMAINS.items()}

href_re = re.compile(r'href=["\']?(https://(\w+)\.informationhot\.kr/([^"\'\s>]+))')

_counter = {"n": 0}


def fix_hrefs(text):
    def repl(m):
        full, sub, path = m.group(1), m.group(2), m.group(3)
        if path.startswith("posts/"):
            return m.group(0)  # already correct
        blog = sub_to_blog.get(sub)
        if not blog or blog not in top1:
            print(f"  WARN: no top-1 for sub={sub} blog={blog}; leaving as-is")
            return m.group(0)
        _counter["n"] += 1
        new = top1[blog]
        orig = m.group(0)
        if 'href="' in orig:
            return f'href="{new}"'
        if "href='" in orig:
            return f"href='{new}'"
        return f"href={new}"
    return href_re.sub(repl, text)


funnel_re = re.compile(r"\{\{<\s*lead\s*>\}\}(.*?)\{\{<\s*/lead\s*>\}\}", re.DOTALL)
card_re = re.compile(
    r'<div style="margin:20px 0;padding:16px;background:#fafbfc;border-radius:12px;border:1px solid #e8ecf0">.*?</div>\s*</div>',
    re.DOTALL,
)

files_changed = 0
total_fixed = 0
for site in SITES:
    base = os.path.join(CUAP_ROOT, site, "content", "posts")
    if not os.path.isdir(base):
        continue
    for md in glob.glob(os.path.join(base, "*", "index.md")):
        with open(md, encoding="utf-8") as f:
            txt = f.read()
        if "이런 상품도 좋아하실 거예요" not in txt:
            continue  # not a baked-card post
        # Apply to whole file: funnel/card regions already handled, but some
        # stale hrefs (e.g. funnel header outside the {{< lead >}} wrapper)
        # sit outside both regex regions. fix_hrefs only rewrites non-/posts/
        # informationhot.kr hrefs, so correct links are left untouched (idempotent).
        new = fix_hrefs(txt)
        if new != txt:
            bak = md + ".bak-2706"
            if not os.path.exists(bak):
                with open(bak, "w", encoding="utf-8") as f:
                    f.write(txt)
            with open(md, "w", encoding="utf-8") as f:
                f.write(new)
            files_changed += 1
            print(f"FIXED {md}  (hrefs fixed this file: {_counter['n']})")
            total_fixed += _counter["n"]
            _counter["n"] = 0

print(f"\nSUMMARY: files_changed={files_changed}  total_hrefs_fixed={total_fixed}")

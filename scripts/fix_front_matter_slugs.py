#!/usr/bin/env python3
"""Fix front matter slugs in all CUAP blogs to match folder names"""

import os
import re
from pathlib import Path

CUAP_BASE = "/Users/twinssn/Projects/cuap"
BLOGS = [
    "appliance-hugo", "baby-hugo", "beauty-hugo", "camping-hugo",
    "fitness-hugo", "health-hugo", "interior-hugo", "kitchen-hugo",
    "laptop-hugo", "pet-hugo"
]

def fix_front_matter_slugs():
    total_fixed = 0
    for blog in BLOGS:
        blog_path = Path(CUAP_BASE) / blog / "content" / "posts"
        if not blog_path.exists():
            continue
            
        for post_dir in blog_path.iterdir():
            if not post_dir.is_dir():
                continue
                
            index_md = post_dir / "index.md"
            if not index_md.exists():
                continue
                
            content = index_md.read_text(encoding='utf-8')
            
            # Check if slug in front matter matches folder name
            folder_name = post_dir.name
            
            # Find slug in front matter
            slug_match = re.search(r'^slug:\s*(.+)$', content, re.MULTILINE)
            if slug_match:
                fm_slug = slug_match.group(1).strip().strip('"\'')
                if fm_slug != folder_name:
                    # Fix the slug
                    new_content = re.sub(
                        r'^slug:\s*.+$',
                        f'slug: "{folder_name}"',
                        content,
                        flags=re.MULTILINE
                    )
                    index_md.write_text(new_content, encoding='utf-8')
                    print(f"Fixed: {blog}/{folder_name} -> slug: {folder_name}")
                    total_fixed += 1
    
    print(f"\nTotal fixed: {total_fixed}")

if __name__ == "__main__":
    fix_front_matter_slugs()
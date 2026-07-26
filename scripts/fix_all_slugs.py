#!/usr/bin/env python3
"""Fix all folders and front matter slugs to ASCII"""

import re
import shutil
from pathlib import Path
import sys
sys.path.insert(0, '/Users/twinssn/Projects/5000')
from scripts.migrate_ascii_slugs import generate_ascii_slug

CUAP_BASE = '/Users/twinssn/Projects/cuap'
BLOGS = [
    'appliance-hugo', 'baby-hugo', 'beauty-hugo', 'camping-hugo',
    'fitness-hugo', 'health-hugo', 'interior-hugo', 'kitchen-hugo',
    'laptop-hugo', 'pet-hugo'
]

total_fixed = 0
for blog in BLOGS:
    blog_path = Path('/Users/twinssn/Projects/cuap') / blog / 'content' / 'posts'
    if not blog_path.exists():
        continue
        
    for post_dir in blog_path.iterdir():
        if not post_dir.is_dir():
            continue
            
        index_md = post_dir / 'index.md'
        if not index_md.exists():
            continue
            
        folder_name = post_dir.name
        
        # Read title from front matter
        content = index_md.read_text(encoding='utf-8')
        title_match = re.search(r'^title:\s*(.+)$', content, re.MULTILINE)
        if not title_match:
            continue
        title = title_match.group(1).strip().strip('"\'')
        
        # Generate new slug
        new_slug = generate_ascii_slug(title, set())
        
        if new_slug != folder_name:
            # Rename folder
            new_path = post_dir.parent / new_slug
            if new_path.exists():
                # Add suffix to avoid collision
                base = new_slug
                counter = 1
                while new_path.exists():
                    new_slug = f'{base}-{counter}'
                    new_path = post_dir.parent / new_slug
                    counter += 1
            
            print(f'Renaming: {blog}/{folder_name} -> {new_slug}')
            shutil.move(str(post_dir), str(new_path))
            
            # Update front matter slug
            new_content = re.sub(
                r'^slug:\s*.+$',
                f'slug: "{new_slug}"',
                content,
                flags=re.MULTILINE
            )
            new_index_md = new_path / 'index.md'
            new_index_md.write_text(new_content, encoding='utf-8')
            
            total_fixed += 1

print(f'Total fixed: {total_fixed}')
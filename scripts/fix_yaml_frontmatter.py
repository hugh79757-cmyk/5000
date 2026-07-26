#!/usr/bin/env python3
"""Fix YAML front matter by properly escaping all fields"""

import re
import shutil
from pathlib import Path

CUAP_BASE = '/Users/twinssn/Projects/cuap'
BLOGS = [
    'appliance-hugo', 'baby-hugo', 'beauty-hugo', 'camping-hugo',
    'fitness-hugo', 'health-hugo', 'interior-hugo', 'kitchen-hugo',
    'laptop-hugo', 'pet-hugo'
]

def fix_yaml_string(value):
    """Escape a string for YAML double-quoted scalar"""
    # Escape backslashes first
    value = value.replace('\\', '\\\\')
    # Escape double quotes
    value = value.replace('"', '\\"')
    # Escape newlines
    value = value.replace('\n', '\\n')
    return value

def fix_front_matter(content):
    """Fix all quoted fields in front matter"""
    # Split front matter and body
    if not content.startswith('---'):
        return content
    
    parts = content.split('---', 2)
    if len(parts) < 3:
        return content
    
    fm_text = parts[1]
    body = parts[2]
    
    # Parse front matter line by line
    lines = fm_text.strip().split('\n')
    new_lines = []
    
    for line in lines:
        # Match key: "value" or key: 'value' or key: value (unquoted)
        match = re.match(r'^(\w+):\s*(.+)$', line)
        if match:
            key = match.group(1)
            value = match.group(2).strip()
            
            # Check if value is quoted
            if (value.startswith('"') and value.endswith('"')) or \
               (value.startswith("'") and value.endswith("'")):
                quote_char = value[0]
                inner = value[1:-1]
                # Fix escaped quotes inside
                inner = inner.replace('\\"', '"').replace("\\'", "'")
                # Now properly escape for YAML
                if quote_char == '"':
                    inner = fix_yaml_string(inner)
                    new_lines.append(f'{key}: "{inner}"')
                else:
                    # For single quotes, escape single quotes by doubling
                    inner = inner.replace("'", "''")
                    new_lines.append(f"{key}: '{inner}'")
            else:
                # Unquoted value - quote it if it contains special chars
                if re.search(r'[":{}[\]&*#?|!@%]', value) or value.lower() in ('true', 'false', 'null', 'yes', 'no', 'on', 'off'):
                    new_lines.append(f'{key}: "{fix_yaml_string(value)}"')
                else:
                    new_lines.append(line)
        else:
            new_lines.append(line)
    
    return '---\n' + '\n'.join(new_lines) + '\n---\n' + body

def main():
    CUAP_BASE = '/Users/twinssn/Projects/cuap'
    BLOGS = [
        'appliance-hugo', 'baby-hugo', 'beauty-hugo', 'camping-hugo',
        'fitness-hugo', 'health-hugo', 'interior-hugo', 'kitchen-hugo',
        'laptop-hugo', 'pet-hugo'
    ]
    
    total = 0
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
                
            content = index_md.read_text(encoding='utf-8')
            new_content = fix_front_matter(content)
            
            if new_content != content:
                # Backup
                shutil.copy2(index_md, index_md.with_suffix('.md.bak2'))
                index_md.write_text(new_content, encoding='utf-8')
                print(f'Fixed: {post_dir.name}')
                total += 1
    
    print(f'Total fixed: {total}')

if __name__ == '__main__':
    main()
#!/usr/bin/env python3
"""Fix YAML frontmatter in CUAP Hugo blog posts so Hugo can build.

Strategy:
1. Parse each line of frontmatter
2. Fix tags/categories: convert Python repr strings → YAML flow sequences
3. Fix cover block: ensure image/relative indented under cover:
4. Fix escaping in string values: strip broken \ and " noise from edges

Only modifies lines that need fixing. Preserves everything else.
"""

import ast
import os
import re
import sys

CUAP_ROOT = "/Users/twinssn/Projects/cuap"

# ---------------------------------------------------------------------------
# tag / category parsers
# ---------------------------------------------------------------------------

def _parse_python_list(raw):
    """Try to parse a Python list repr from a string."""
    raw = raw.strip()
    # Find the outermost [...] 
    m = re.search(r"\[.*\]", raw, re.DOTALL)
    if not m:
        return None
    try:
        parsed = ast.literal_eval(m.group())
        if isinstance(parsed, list):
            return parsed
    except Exception:
        pass
    return None


def _yaml_list(items):
    """Format list as YAML flow sequence with single-quoted items."""
    if not items:
        return "[]"
    quoted = []
    for item in items:
        s = str(item).strip()
        s = s.replace("'", "''")  # YAML single-quote escaping
        quoted.append(f"'{s}'")
    return "[" + ", ".join(quoted) + "]"


def _fix_tags_or_categories_line(line):
    """Fix a single tags: or categories: line.
    
    Returns fixed line, or None if no change needed.
    """
    stripped = line.strip()
    field = stripped.split(":")[0]
    colon_idx = stripped.index(":")
    raw_value = stripped[colon_idx + 1:].strip()

    # Already a YAML list? e.g. tags: ['a', 'b'] or tags: []
    if raw_value.startswith("[") and raw_value.endswith("]"):
        return None  # already valid

    # Empty? e.g. tags:  or tags: ""
    if not raw_value or raw_value in ('""', "''"):
        items = []

    # Python repr wrapped in YAML double-quotes: "['a', 'b']"
    # or with backslash-escapes: "\"['a', 'b']\""
    else:
        # Strip YAML double-quotes if present
        inner = raw_value
        if inner.startswith('"') and inner.endswith('"'):
            inner = inner[1:-1]
        # Strip leading backslash-quote noise
        for _ in range(5):
            if not inner:
                break
            if inner.startswith('\\"'):
                inner = inner[2:]
            elif inner.startswith("\\'"):
                inner = inner[2:]
            elif inner.startswith("\\"):
                inner = inner[1:]
            elif inner.startswith('"') or inner.startswith("'"):
                inner = inner[1:]
            else:
                break
        # Strip trailing backslash-quote noise
        for _ in range(5):
            if not inner:
                break
            if inner.endswith('\\"') and len(inner) >= 2:
                inner = inner[:-2]
            elif inner.endswith("\\'") and len(inner) >= 2:
                inner = inner[:-2]
            elif inner.endswith("\\") and len(inner) >= 1:
                inner = inner[:-1]
            elif inner.endswith('"') or inner.endswith("'"):
                inner = inner[:-1]
            else:
                break

        # Now try to parse as Python list
        parsed = _parse_python_list(inner)
        if parsed is not None:
            items = parsed
        else:
            # Fallback: treat as single item
            items = [inner]

    # Build fixed line preserving indentation
    indent = line[:len(line) - len(stripped)]
    fixed = f"{indent}{field}: {_yaml_list(items)}"
    return fixed


# ---------------------------------------------------------------------------
# Cover block fixer
# ---------------------------------------------------------------------------

def _fix_cover_block(lines, start_idx):
    """Fix the cover block starting at start_idx.
    
    Ensures image: and relative: are indented under cover:.
    Returns list of fixed lines.
    """
    result = []
    i = start_idx
    result.append(lines[i])  # cover: line
    i += 1

    # Collect subsequent lines that belong to the cover block
    cover_keys = {"image:", "relative:", "hidden:"}
    cover_lines = []
    while i < len(lines):
        stripped = lines[i].strip()
        # Check if this line starts with a cover block key (indented or not)
        is_cover_item = any(stripped.startswith(k) for k in cover_keys)
        # Also check for featureimage: which is top-level, not cover
        if stripped.startswith("featureimage:") or stripped.startswith("thumbnail:"):
            break
        if not is_cover_item:
            # Check if it's a new top-level field (key: value)
            if ":" in stripped and not stripped.startswith(" "):
                break
        if is_cover_item:
            cover_lines.append(lines[i])
        i += 1

    if cover_lines:
        for cl in cover_lines:
            stripped = cl.strip()
            indent = "  "  # always indent under cover:
            result.append(f"{indent}{stripped}")
    else:
        # No cover content found; put a placeholder
        result.append("  image: \"\"")

    return result


# ---------------------------------------------------------------------------
# String value cleaner
# ---------------------------------------------------------------------------

def _clean_value(raw):
    """Clean a string value from broken backslash escaping.
    
    Strips leading and trailing \ and " characters that are clearly
    artifacts of double-escaping.
    """
    if not raw:
        return raw
    
    # Strip leading noise
    for _ in range(5):
        if not raw:
            break
        if raw.startswith('\\"') and len(raw) > 2 and raw[2] not in ('\\', '"', "'"):
            # \" followed by a clean char — noise
            raw = raw[2:]
        elif raw.startswith('\\"') and len(raw) <= 2:
            raw = raw[2:]
        elif raw.startswith("\\\\") and len(raw) > 2:
            raw = raw[1:]  # strip one backslash at a time
        elif raw.startswith("\\") and len(raw) > 1:
            raw = raw[1:]
        elif raw.startswith('"') and raw.count('"') > 1:
            raw = raw[1:]
        else:
            break
    
    # Strip trailing noise
    for _ in range(5):
        if not raw:
            break
        if raw.endswith('"') and raw.count('"') > 1:
            raw = raw[:-1]
        elif raw.endswith("\\") and not raw.endswith("\\\\"):
            raw = raw[:-1]
        else:
            break
    
    return raw


def _fix_string_field_line(line):
    """Fix escaping in a YAML key: "string value" line.
    
    Returns fixed line, or None if no change needed.
    """
    stripped = line.strip()
    colon_idx = stripped.index(":")
    key = stripped[:colon_idx]
    rest = stripped[colon_idx + 1:].strip()
    
    # Only process if it's a double-quoted string value
    if not (rest.startswith('"') and rest.endswith('"')):
        return None
    
    inner = rest[1:-1]  # remove outer quotes
    cleaned = _clean_value(inner)
    if cleaned == inner:
        return None  # no change needed
    
    # Re-sanitize for YAML double-quoted string
    sanitized = cleaned.replace("\\", "\\\\").replace('"', '\\"')
    
    indent = line[:len(line) - len(stripped)]
    return f'{indent}{key}: "{sanitized}"'


# ---------------------------------------------------------------------------
# Main fix function
# ---------------------------------------------------------------------------

def fix_frontmatter_v2(content):
    """Fix frontmatter YAML in a markdown file.
    
    Returns (fixed_content, changed) or (content, False).
    """
    parts = content.split("---\n", 2)
    if len(parts) < 2:
        return content, False
    
    fm = parts[1]
    body = parts[2] if len(parts) > 2 else ""
    lines = fm.split("\n")
    fixed_lines = []
    changed = False
    i = 0
    
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        
        # --- tags / categories ---
        if stripped.startswith(("tags:", "categories:")):
            fixed = _fix_tags_or_categories_line(line)
            if fixed is not None:
                fixed_lines.append(fixed)
                changed = True
            else:
                fixed_lines.append(line)
            i += 1
            continue
        
        # --- cover block ---
        if stripped == "cover:" or stripped.startswith("cover:"):
            # Fix the entire cover block
            cover_fixed = _fix_cover_block(lines, i)
            # Check if cover changed
            orig_lines = []
            j = i
            while j < len(lines) and (j == i or 
                  (lines[j].strip() and 
                   not lines[j].strip().startswith(("title:", "date:", "draft:", "description:", "slug:", "categories:", "tags:", "featureimage:", "thumbnail:")))):
                stripped_j = lines[j].strip()
                if stripped_j.startswith("featureimage:") or stripped_j.startswith("thumbnail:"):
                    break
                if stripped_j in ("cover:",) or any(stripped_j.startswith(k) for k in 
                    ("image:", "  image:", "relative:", "  relative:", "hidden:", "  hidden:")):
                    orig_lines.append(lines[j])
                    j += 1
                elif stripped_j == "cover:" and j > i:
                    break
                elif j == i:
                    orig_lines.append(lines[j])
                    j += 1
                else:
                    break
            
            # Compare
            if len(cover_fixed) != len(orig_lines) or any(a != b for a, b in zip(cover_fixed, orig_lines)):
                changed = True
            
            fixed_lines.extend(cover_fixed)
            i += len(orig_lines)  # skip the original cover lines
            continue
        
        # --- non-tag string fields with escaping issues ---
        text_fields = ("title:", "slug:", "description:", "date:", "featureimage:", "thumbnail:")
        if stripped.startswith(text_fields) and '"' in stripped:
            fixed = _fix_string_field_line(line)
            if fixed is not None:
                fixed_lines.append(fixed)
                changed = True
            else:
                fixed_lines.append(line)
            i += 1
            continue
        
        # Everything else — keep as-is
        fixed_lines.append(line)
        i += 1
    
    fixed_fm = "\n".join(fixed_lines)
    if not changed:
        return content, False
    
    new_content = "---\n" + fixed_fm + "\n---\n" + body
    return new_content, True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    blogs = [
        "appliance-hugo", "baby-hugo", "beauty-hugo", "camping-hugo",
        "fitness-hugo", "health-hugo", "interior-hugo", "kitchen-hugo",
        "laptop-hugo", "pet-hugo",
    ]
    
    total_fixed = 0
    total_posts = 0
    total_errors = 0
    
    for blog in blogs:
        posts_dir = os.path.join(CUAP_ROOT, blog, "content", "posts")
        if not os.path.isdir(posts_dir):
            print(f"[SKIP] {blog}: posts dir not found")
            continue
        
        posts = sorted(os.listdir(posts_dir))
        blog_fixed = 0
        blog_posts = 0
        
        for post in posts:
            idx = os.path.join(posts_dir, post, "index.md")
            if not os.path.isfile(idx):
                continue
            blog_posts += 1
            total_posts += 1
            
            try:
                with open(idx, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception as e:
                print(f"[ERROR] {blog}/{post}: read: {e}")
                total_errors += 1
                continue
            
            new_content, changed = fix_frontmatter_v2(content)
            if changed:
                with open(idx, "w", encoding="utf-8") as f:
                    f.write(new_content)
                blog_fixed += 1
                total_fixed += 1
        
        print(f"[{blog}] {blog_fixed}/{blog_posts} files fixed")
    
    print(f"\nTotal: {total_fixed}/{total_posts} files fixed, {total_errors} errors")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Fix YAML frontmatter in CUAP Hugo blog posts.

Root cause: slug/description/title have broken backslash escaping at edges,
which causes the YAML parser to consume all subsequent lines as an unclosed
string. This makes Hugo fail with "map key-value is pre-defined".

Fixes:
1. slug/title/description: strip trailing `\"` and `\\` noise (restores YAML quoting)
2. cover block: ensure image/relative are indented under cover:
3. tags/categories: convert Python string repr to YAML flow sequences
"""

import ast
import os
import re
import sys

CUAP_ROOT = "/Users/twinssn/Projects/cuap"

# ---------------------------------------------------------------------------
# 1. Fix broken escaping in YAML double-quoted fields
# ---------------------------------------------------------------------------

def _fix_escaped_value(raw_value):
    """Fix a YAML double-quoted string value that has broken escaping.
    
    Broken patterns:
    - Trailing \\\"  (backslash then quote → yaml treats `\"` as escaped `"`,
      consuming the closing quote)
    - Trailing \\   (final backslash → yaml treats `\` as escape start,
      consuming the closing quote as escape char)
    - Leading \\\" or \\ (same issue at start)
    
    Fix: strip trailing and leading \ artifacts that would break YAML quoting.
    """
    if not raw_value:
        return raw_value
    
    # Strip trailing broken escaping (up to 3 levels)
    for _ in range(3):
        if not raw_value:
            break
        # Ends with a single \ followed by " → strip the \ (the " is the real closer)
        if raw_value.endswith('\\') and not raw_value.endswith('\\\\'):
            raw_value = raw_value[:-1]
        else:
            break
    
    # Strip leading broken escaping
    for _ in range(3):
        if not raw_value:
            break
        if raw_value.startswith('\\') and not raw_value.startswith('\\\\'):
            raw_value = raw_value[1:]
        else:
            break
    
    return raw_value


def _fix_double_quoted_line(line):
    """Fix a YAML key: "value" line with broken escaping.
    
    Returns fixed line or None if no change.
    """
    stripped = line.strip()
    colon_idx = stripped.index(":")
    key = stripped[:colon_idx]
    rest = stripped[colon_idx + 1:].strip()
    
    if not (rest.startswith('"') and rest.endswith('"')):
        return None
    
    inner = rest[1:-1]  # strip outer YAML double-quotes
    fixed_inner = _fix_escaped_value(inner)
    if fixed_inner == inner:
        return None
    
    # Re-sanitize for YAML double-quoted string
    sanitized = fixed_inner.replace("\\", "\\\\").replace('"', '\\"')
    
    indent = line[:len(line) - len(stripped)]
    return f'{indent}{key}: "{sanitized}"'


# ---------------------------------------------------------------------------
# 2. Fix cover block indentation
# ---------------------------------------------------------------------------

def _fix_cover_block(lines, i):
    """Fix cover block: ensure image/relative/hidden are indented under cover:.
    
    Returns (fixed_lines, new_i).
    """
    result = []
    result.append(lines[i])  # cover: line
    i += 1
    
    # Collect lines that should be under cover:
    cover_keys = ("image:", "relative:", "hidden:")
    cover_children = []
    while i < len(lines):
        l = lines[i]
        s = l.strip()
        if s.startswith(cover_keys) or s.startswith(("featureimage:", "thumbnail:", "---")):
            cover_children.append(s)  # strip indent, we'll re-indent
            i += 1
        elif s and not s.startswith("#") and not s.startswith("---"):
            if ":" in s.split("#")[0]:
                # New top-level key
                break
            else:
                # - list items under cover? unlikely but possible
                cover_children.append(s)
                i += 1
        else:
            break
    
    # Write children indented under cover:
    for child in cover_children:
        if child.startswith(("featureimage:", "thumbnail:", "---")):
            # These are top-level, not under cover
            result.append(child)
        else:
            result.append("  " + child)
    
    return result


# ---------------------------------------------------------------------------
# 3. Fix tags/categories: string repr → YAML list
# ---------------------------------------------------------------------------

def _parse_python_list(s):
    """Try to parse a Python list repr from a string."""
    m = re.search(r"\[.*\]", s, re.DOTALL)
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
    """Format list as YAML flow sequence."""
    if not items:
        return "[]"
    quoted = [f"'{str(i).strip().replace(chr(39), chr(39)*2)}'" for i in items]
    return "[" + ", ".join(quoted) + "]"


def _has_block_sequence_after(lines, start_idx):
    """Check if there are YAML block sequence items (- item) after start_idx."""
    for j in range(start_idx + 1, min(start_idx + 30, len(lines))):
        l = lines[j]
        s = l.strip()
        if s.startswith("- "):
            return True
        if s and (":" in s or s.startswith("---")):
            # New key or end of frontmatter → no more block items
            return False
    return False


# ---------------------------------------------------------------------------
# Main fix orchestrator
# ---------------------------------------------------------------------------

def fix_frontmatter(content):
    """Fix frontmatter YAML in a markdown file.
    
    Returns (fixed_content, changed).
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
        
        # --- Fixed-length string fields (slug, title, description, date) ---
        text_fields = ("title:", "slug:", "description:", "date:")
        if stripped.startswith(text_fields) and '"' in stripped:
            fixed = _fix_double_quoted_line(line)
            if fixed is not None:
                fixed_lines.append(fixed)
                changed = True
            else:
                fixed_lines.append(line)
            i += 1
            continue
        
        # --- Tags / categories ---
        if stripped.startswith(("tags:", "categories:")):
            field = stripped.split(":")[0]
            colon_idx = stripped.index(":")
            raw_val = stripped[colon_idx + 1:].strip()
            indent = line[:len(line) - len(stripped)]
            
            # Check if block sequence follows
            has_block = _has_block_sequence_after(lines, i)
            if has_block:
                # Keep as block sequence (already valid YAML)
                # But write the key line without inline value if it had one
                fixed_lines.append(f"{indent}{field}:")
                i += 1
                # Copy the block items
                while i < len(lines):
                    s = lines[i].strip()
                    if s.startswith("- "):
                        fixed_lines.append(lines[i])
                        i += 1
                    else:
                        break
                continue
            
            # Categorize value type
            if not raw_val or raw_val in ('""', "''", "\"\""):
                # Empty → set to empty list
                if raw_val or True:  # always fix empty to []
                    fixed = f"{indent}{field}: []"
                    fixed_lines.append(fixed)
                    changed = True
                else:
                    fixed_lines.append(line)
                i += 1
                continue
            
            # Check if it's a Python repr string wrapped in YAML quotes
            # e.g. `tags: "['a', 'b']"` or `tags: "\"['a', 'b']\""`
            inner = raw_val
            if inner.startswith('"') and inner.endswith('"'):
                inner = inner[1:-1]
            # Clean escape artifacts
            for _ in range(3):
                if inner.startswith('\\"') and len(inner) > 2:
                    inner = inner[2:]
                elif inner.startswith('\\') and len(inner) > 1:
                    inner = inner[1:]
                else:
                    break
            for _ in range(3):
                if inner.endswith('\\"') and len(inner) > 2:
                    inner = inner[:-2]
                elif inner.endswith('\\') and len(inner) > 1:
                    inner = inner[:-1]
                else:
                    break
            
            # Try to parse as Python list
            parsed = _parse_python_list(inner)
            if parsed is not None:
                yl = _yaml_list(parsed)
                if raw_val != yl:
                    fixed = f"{indent}{field}: {yl}"
                    fixed_lines.append(fixed)
                    changed = True
                else:
                    fixed_lines.append(line)
                i += 1
                continue
            
            # Fallback: leave as-is
            fixed_lines.append(line)
            i += 1
            continue
        
        # --- Cover block ---
        if stripped == "cover:":
            cover_fixed = _fix_cover_block(lines, i)
            n = len(cover_fixed)
            # Check if cover actually changed
            orig = lines[i:i+n]
            if cover_fixed != orig:
                changed = True
            fixed_lines.extend(cover_fixed)
            i += n
            continue
        
        # --- Featureimage / thumbnail — fix escaping ---
        if stripped.startswith(("featureimage:", "thumbnail:")) and '"' in stripped:
            fixed = _fix_double_quoted_line(line)
            if fixed is not None:
                fixed_lines.append(fixed)
                changed = True
            else:
                fixed_lines.append(line)
            i += 1
            continue
        
        # Everything else
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
            
            new_content, c = fix_frontmatter(content)
            if c:
                with open(idx, "w", encoding="utf-8") as f:
                    f.write(new_content)
                blog_fixed += 1
                total_fixed += 1
        
        print(f"[{blog}] {blog_fixed}/{blog_posts} files fixed")
    
    print(f"\nTotal: {total_fixed}/{total_posts} files fixed, {total_errors} errors")


if __name__ == "__main__":
    main()

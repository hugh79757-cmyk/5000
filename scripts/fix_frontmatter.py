#!/usr/bin/env python3
"""Fix malformed YAML frontmatter in CUAP Hugo blog posts.

Problems fixed:
1. tags/categories as Python string repr (e.g. `"\\\"['tag']\\\""`) → proper YAML list
2. tags/categories empty (e.g. `tags:`) → proper empty list
3. title/description/slug with broken backslash escaping
4. date/image/featureimage with extra `\"` inside values

Usage: python3 scripts/fix_frontmatter.py
"""

import ast
import os
import re
import sys

CUAP_ROOT = "/Users/twinssn/Projects/cuap"


def _parse_tags_value(raw_value):
    """Parse a tags or categories value from various corrupted formats into a Python list."""
    if raw_value is None:
        return []

    raw_value = raw_value.strip()

    # Empty -> empty list
    if not raw_value or raw_value == "tags:" or raw_value == "categories:":
        return []

    # Pattern: already a YAML flow sequence (no outer quotes wrapping a string)
    # e.g. `tags: ['tag1', 'tag2']`
    # The value would be `['tag1', 'tag2']`
    if raw_value.startswith("[") and raw_value.endswith("]"):
        try:
            return ast.literal_eval(raw_value)
        except (ValueError, SyntaxError):
            pass

    # Pattern: YAML double-quoted string containing Python repr: "['tag1', 'tag2']"
    # The YAML double-quotes have already been stripped by line parsing.
    # But the content still has the inner Python repr format.
    # Check for patterns like: ['tag1', 'tag2'] or \"['tag1', 'tag2']\"
    inner = raw_value
    # Remove outer escaped double-quotes if present
    if inner.startswith('\\"') and inner.endswith('\\"'):
        inner = inner[2:-2]
    if inner.startswith('"') and inner.endswith('"'):
        inner = inner[1:-1]

    # Try to extract a Python list from the cleaned value
    # Handle both: ['tag1', 'tag2'] and ["tag1", "tag2"]
    list_match = re.search(r"\[.*?\]", inner, re.DOTALL)
    if list_match:
        list_str = list_match.group()
        try:
            parsed = ast.literal_eval(list_str)
            if isinstance(parsed, list):
                return parsed
        except (ValueError, SyntaxError):
            pass

    # If we can't parse it, try the original value as a single-item fallback
    # But strip escaped quotes
    cleaned = raw_value.replace('\\"', "")
    if cleaned:
        return [cleaned]
    return []


def _yaml_list(items):
    """Format a Python list as a valid YAML flow sequence."""
    if not items:
        return "[]"
    # Single-quote each item (safe for Korean/international text)
    quoted = []
    for item in items:
        item = str(item).strip()
        # Escape single quotes inside by doubling them (YAML single-quote escaping)
        item = item.replace("'", "''")
        quoted.append(f"'{item}'")
    return "[" + ", ".join(quoted) + "]"


def _extract_quoted_value(line):
    """Extract the value between YAML double-quotes, handling broken escaping.
    
    Returns (raw_value_within_quotes, original_opening_quote_found).
    
    Handles patterns like:
    - `key: "clean value"` → "clean value"
    - `key: "\\\"escaped value\\\""` → escaped content
    - `key: "value\\"` → value with trailing escape issue
    """
    line = line.strip()
    colon_idx = line.index(":")
    after_colon = line[colon_idx + 1:].strip()
    
    if not after_colon:
        return "", False
    
    # Check if it starts with a double-quote
    if after_colon.startswith('"'):
        # Find the closing double-quote, being aware of escaped quotes
        inner = after_colon[1:]  # strip opening quote
        # Find the closing quote (last non-escaped double-quote)
        # Simply take everything up to the last '"'
        if inner.endswith('"'):
            inner = inner[:-1]
        return inner, True
    else:
        return after_colon, False


def _clean_escaped_value(raw_value):
    """Clean a value that has broken backslash-escaping.
    
    The value may have patterns like:
    - Leading `\\\"` or `\"` (backslash-escaped double-quotes wrapping)
    - Trailing `\\\"` or `\"` or `\\`
    
    Strategy: greedily strip leading/trailing \ and " characters.
    This works because Korean text shouldn't start/end with these characters in practice.
    """
    if not raw_value:
        return raw_value
    
    # Strip leading backslash/quote noise (up to 5 iterations to handle multiple levels)
    for _ in range(5):
        if not raw_value:
            break
        if raw_value.startswith('\\"'):
            raw_value = raw_value[2:]
        elif raw_value.startswith('\\'):
            raw_value = raw_value[1:]
        elif raw_value.startswith('"'):
            raw_value = raw_value[1:]
        else:
            break
    
    # Strip trailing backslash/quote noise (up to 5 iterations)
    for _ in range(5):
        if not raw_value:
            break
        if raw_value.endswith('\\"') and len(raw_value) >= 2:
            raw_value = raw_value[:-2]
        elif raw_value.endswith('\\') and len(raw_value) >= 1:
            raw_value = raw_value[:-1]
        elif raw_value.endswith('"') and len(raw_value) >= 1:
            raw_value = raw_value[:-1]
        else:
            break
    
    return raw_value


def _fix_field_value(line, field_name):
    """Fix a YAML key:value line's escaping issues holistically.
    
    Extracts the value, cleans it, and re-wraps it properly.
    Preserves indentation.
    """
    original = line
    
    # Extract indentation
    indent = ""
    stripped = line
    if line.startswith(" ") or line.startswith("\t"):
        indent = line[:len(line) - len(line.lstrip())]
        stripped = line[len(indent):]
    
    colon_idx = stripped.index(":")
    key = stripped[:colon_idx]
    rest = stripped[colon_idx + 1:].strip()
    
    if not rest or rest == '""':
        # Empty value
        return original
    
    # Extract and clean the value
    inner, was_quoted = _extract_quoted_value(stripped)
    if not inner:
        return original
    
    cleaned = _clean_escaped_value(inner)
    
    # Re-sanitize the value for YAML double-quoted string
    sanitized = cleaned
    # Escape backslashes and double-quotes for YAML
    if '\\' in sanitized or '"' in sanitized:
        sanitized = sanitized.replace("\\", "\\\\").replace('"', '\\"')
    
    # Build new line with preserved indentation
    new_line = f"{indent}{key}: \"{sanitized}\""
    
    if new_line != original:
        return new_line
    return original


def fix_frontmatter(content):
    """Fix frontmatter YAML in a markdown file content.
    
    Returns (fixed_content, had_errors) or (original_content, False) if no changes needed.
    """
    # Split frontmatter from body
    parts = content.split("---\n", 2)
    if len(parts) < 2:
        return content, False

    fm = parts[1]
    body = parts[2] if len(parts) > 2 else ""

    lines = fm.split("\n")
    fixed_lines = []
    changed = False

    for line in lines:
        original_line = line

        # Fix tags and categories — convert to proper YAML lists
        stripped = line.strip()
        if stripped.startswith(("tags:", "categories:")):
            colon_idx = line.index(":")
            raw_value = line[colon_idx + 1:].strip()
            parsed = _parse_tags_value(raw_value)
            list_str = _yaml_list(parsed)
            fixed_line = f"{stripped[:colon_idx]}: {list_str}" if not line.startswith(" ") else f"  {stripped.split(':')[0]}: {list_str}"
            if line.startswith("  "):
                fixed_line = "  " + fixed_line.lstrip()
            else:
                fixed_line = f"{stripped.split(':')[0]}: {list_str}"
            if fixed_line != original_line:
                changed = True
            fixed_lines.append(fixed_line)
            continue

        # Fix escaping issues for all text-valued fields
        text_fields = ("title:", "slug:", "description:", "date:", 
                       "image:", "featureimage:", "thumbnail:")
        if stripped.startswith(text_fields):
            fixed = _fix_field_value(line, stripped.split(":")[0])
            if fixed != original_line:
                changed = True
            fixed_lines.append(fixed)
            continue

        # Fix cover block — ensure image/relative are indented under it
        if stripped == "cover:" or stripped.startswith("cover:"):
            fixed_lines.append(line)
            continue

        fixed_lines.append(line)

    fixed_fm = "\n".join(fixed_lines)

    if not changed:
        return content, False

    new_content = "---\n" + fixed_fm + "\n---\n" + body
    return new_content, True


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
                print(f"[ERROR] {blog}/{post}: read error: {e}")
                total_errors += 1
                continue

            new_content, changed = fix_frontmatter(content)
            if changed:
                with open(idx, "w", encoding="utf-8") as f:
                    f.write(new_content)
                blog_fixed += 1
                total_fixed += 1

        print(f"[{blog}] {blog_fixed}/{blog_posts} files fixed")

    print(f"\nTotal: {total_fixed}/{total_posts} files fixed, {total_errors} errors")


if __name__ == "__main__":
    main()

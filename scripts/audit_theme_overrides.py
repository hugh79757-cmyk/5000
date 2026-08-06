#!/usr/bin/env python3
"""
Audit all blog layout overrides and measure disk usage.
Phase 59 Plan 06 Task 1
"""

import os
import yaml
import json
from pathlib import Path
from collections import defaultdict
import subprocess

# Configuration
PROJECT_ROOT = Path("/Users/twinssn/Projects/5000")
CONFIG_DIR = PROJECT_ROOT / "config" / "blogs.d"
SHARED_THEMES_DIR = PROJECT_ROOT / "shared" / "themes"

# Allowed override files per Blowfish standard
ALLOWED_OVERRIDES = {
    "layouts/_default/single.html",
    "layouts/partials/extend-head.html",
    "layouts/partials/extend_head.html",
    "layouts/partials/adsense/top.html",
    "layouts/partials/adsense/in-article.html",
    "layouts/partials/adsense/mobile-sticky.html",
    "assets/css/custom.css",
}

# Non-Blowfish themes
NON_BLOWFISH_THEMES = {"papermod", "congo"}


def load_blog_configs():
    """Load all blog configurations from YAML files."""
    blogs = []
    for yaml_file in CONFIG_DIR.glob("*.yaml"):
        if yaml_file.name.endswith(".bak") or yaml_file.name.endswith(".bak_*"):
            continue
        try:
            with open(yaml_file, "r") as f:
                data = yaml.safe_load(f)
                if "blogs" in data:
                    for blog in data["blogs"]:
                        blog["source_yaml"] = yaml_file.name
                        blogs.append(blog)
        except Exception as e:
            print(f"Error loading {yaml_file}: {e}")
    return blogs


def measure_disk_usage(path):
    """Measure disk usage of a directory."""
    try:
        result = subprocess.run(
            ["du", "-sh", str(path)],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return result.stdout.split()[0]
    except:
        pass
    return "0B"


def scan_overrides(site_path):
    """Scan a site directory for layout overrides."""
    overrides = []
    site_path = Path(site_path)
    
    if not site_path.exists():
        return overrides
    
    # Check layouts directory
    layouts_dir = site_path / "layouts"
    if layouts_dir.exists():
        for root, dirs, files in os.walk(layouts_dir):
            for file in files:
                file_path = Path(root) / file
                rel_path = file_path.relative_to(site_path)
                rel_str = str(rel_path)
                
                # Check if it's an allowed override
                is_allowed = False
                for allowed in ALLOWED_OVERRIDES:
                    if rel_str.endswith(allowed) or rel_str == allowed:
                        is_allowed = True
                        break
                
                # Check for mobile-sticky.html (forbidden)
                is_forbidden = "mobile-sticky.html" in rel_str
                
                overrides.append({
                    "path": rel_str,
                    "allowed": is_allowed and not is_forbidden,
                    "forbidden": is_forbidden,
                    "size": file_path.stat().st_size if file_path.exists() else 0,
                })
    
    # Check assets/css directory
    assets_dir = site_path / "assets" / "css"
    if assets_dir.exists():
        for file in assets_dir.glob("*.css"):
            rel_path = file.relative_to(site_path)
            rel_str = str(rel_path)
            is_allowed = "custom.css" in rel_str
            
            overrides.append({
                "path": rel_str,
                "allowed": is_allowed,
                "forbidden": False,
                "size": file.stat().st_size if file.exists() else 0,
            })
    
    return overrides


def compare_files(file1, file2):
    """Compare two files for equality."""
    try:
        with open(file1, "r") as f1, open(file2, "r") as f2:
            return f1.read() == f2.read()
    except:
        return False


def main():
    print("=" * 80)
    print("THEME OVERRIDE AUDIT REPORT")
    print("=" * 80)
    
    # Load blog configurations
    blogs = load_blog_configs()
    print(f"\nFound {len(blogs)} blogs in configuration")
    
    # Measure disk usage
    print("\n--- Disk Usage (Before) ---")
    themes_usage = measure_disk_usage(PROJECT_ROOT / "themes")
    print(f"themes/ directory: {themes_usage}")
    
    # Scan all blogs
    all_overrides = []
    blog_overrides = {}
    non_blowfish_blogs = []
    override_by_type = defaultdict(list)
    
    for blog in blogs:
        blog_id = blog.get("id", "unknown")
        site_path = blog.get("site_path", "")
        theme = blog.get("theme", "blowfish")
        brand = blog.get("source_yaml", "").replace(".yaml", "").upper()
        
        if not site_path or not Path(site_path).exists():
            continue
        
        # Check for non-Blowfish themes
        if theme.lower() in NON_BLOWFISH_THEMES:
            non_blowfish_blogs.append({
                "id": blog_id,
                "theme": theme,
                "brand": brand,
                "site_path": site_path,
            })
        
        # Scan overrides
        overrides = scan_overrides(site_path)
        if overrides:
            blog_overrides[blog_id] = {
                "brand": brand,
                "theme": theme,
                "site_path": site_path,
                "overrides": overrides,
            }
            
            for override in overrides:
                override_by_type[override["path"]].append(blog_id)
                all_overrides.append({
                    "blog_id": blog_id,
                    "brand": brand,
                    **override,
                })
    
    # Print override inventory
    print("\n--- Override Inventory ---")
    print(f"Total blogs with overrides: {len(blog_overrides)}")
    print(f"Total override files: {len(all_overrides)}")
    
    # Group by brand
    by_brand = defaultdict(list)
    for item in all_overrides:
        by_brand[item["brand"]].append(item)
    
    print("\nBy Brand:")
    for brand, items in sorted(by_brand.items()):
        print(f"  {brand}: {len(items)} files")
    
    # Print non-Blowfish themes
    print("\n--- Non-Blowfish Themes ---")
    if non_blowfish_blogs:
        for blog in non_blowfish_blogs:
            print(f"  {blog['id']}: {blog['theme']} ({blog['brand']})")
    else:
        print("  None found")
    
    # Find duplicate overrides
    print("\n--- Duplicate Overrides (Candidates for Sharing) ---")
    duplicate_candidates = []
    for path, blog_ids in override_by_type.items():
        if len(blog_ids) > 1:
            duplicate_candidates.append({
                "path": path,
                "count": len(blog_ids),
                "blogs": blog_ids[:5],  # Show first 5
            })
    
    for candidate in sorted(duplicate_candidates, key=lambda x: -x["count"]):
        print(f"  {candidate['path']}: {candidate['count']} blogs")
        print(f"    Examples: {', '.join(candidate['blogs'][:3])}")
    
    # Print unauthorized overrides
    print("\n--- Unauthorized Overrides ---")
    unauthorized = [o for o in all_overrides if not o["allowed"]]
    if unauthorized:
        for item in unauthorized:
            print(f"  {item['blog_id']}: {item['path']}")
    else:
        print("  None found")
    
    # Print forbidden files
    print("\n--- Forbidden Files (mobile-sticky.html) ---")
    forbidden = [o for o in all_overrides if o["forbidden"]]
    if forbidden:
        for item in forbidden:
            print(f"  {item['blog_id']}: {item['path']}")
    else:
        print("  None found")
    
    # Save results to JSON
    results = {
        "total_blogs": len(blogs),
        "blogs_with_overrides": len(blog_overrides),
        "total_override_files": len(all_overrides),
        "non_blowfish_blogs": non_blowfish_blogs,
        "override_inventory": all_overrides,
        "duplicate_candidates": duplicate_candidates,
        "unauthorized_overrides": unauthorized,
        "forbidden_files": forbidden,
    }
    
    output_file = PROJECT_ROOT / "shared" / "themes" / "audit_results.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n--- Results saved to {output_file} ---")
    
    return results


if __name__ == "__main__":
    main()

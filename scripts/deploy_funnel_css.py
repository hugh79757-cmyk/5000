#!/usr/bin/env python3
"""Deploy funnel-card.css to 84 Hugo sites' assets/css/extended/.

PaperMod theme auto-bundles all .css files from assets/css/extended/.
Run once after Phase 22-C to enable funnel card visual styling.

Usage:
    python3 scripts/deploy_funnel_css.py
    python3 scripts/deploy_funnel_css.py --dry-run  # preview only
"""

import argparse
import sys
from pathlib import Path

import yaml

PROJ_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJ_ROOT / "config"

CSS_CONTENT = """/* Funnel Card Styles — deployed by Phase 22-C */
.funnel-card {
  display: flex;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  overflow: hidden;
  background: #f9fafb;
  margin: 1.5rem 0;
  transition: box-shadow 0.2s, transform 0.2s;
}
.funnel-card:hover {
  box-shadow: 0 4px 12px rgba(0,0,0,0.08);
  transform: translateY(-1px);
}
.funnel-card-inner {
  display: flex;
  width: 100%;
  text-decoration: none;
  color: inherit;
}
.funnel-card-thumb {
  width: 120px;
  height: 80px;
  object-fit: cover;
  flex-shrink: 0;
}
.funnel-card-body {
  padding: 12px;
  flex: 1;
}
.funnel-card-label {
  font-size: 0.75rem;
  text-transform: uppercase;
  color: #6b7280;
  letter-spacing: 0.05em;
}
.funnel-card-title {
  font-size: 1rem;
  font-weight: 600;
  margin: 4px 0;
  color: #1f2937;
}
.funnel-card-cta {
  color: #2563eb;
  font-weight: 500;
  font-size: 0.875rem;
}

/* Bridge card accent */
.funnel-card.funnel-bridge {
  background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
  border-left: 4px solid #f59e0b;
}
.funnel-card.funnel-bridge .funnel-card-label {
  color: #92400e;
}

/* Mobile responsive */
@media (max-width: 640px) {
  .funnel-card-thumb {
    width: 90px;
    height: 60px;
  }
  .funnel-card-title {
    font-size: 0.875rem;
  }
}
"""


def load_blog_configs():
    """Return list of blog config dicts from blogs.yaml + blogs.d/*.yaml."""
    main_path = CONFIG_DIR / "blogs.yaml"
    with open(main_path, encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    blogs = config.get("blogs", [])

    blogs_d = CONFIG_DIR / "blogs.d"
    if blogs_d.is_dir():
        for fpath in sorted(blogs_d.glob("*.yaml")):
            with open(fpath, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            blogs.extend(data.get("blogs", []))

    return blogs


def deploy_css(blogs, dry_run=False):
    """Create funnel-card.css in each Hugo site's assets/css/extended/ directory.

    Deduplicates by site_path (multiple blogs may share the same repo).
    Returns list of (site_path, blog_id, status) tuples.
    """
    deployed = set()  # track unique site_path + blog_id to avoid dedup issues
    seen_paths = set()  # avoid writing the same file multiple times
    results = []

    for blog in blogs:
        blog_id = blog.get("id", "")
        platform = blog.get("platform", "")
        site_path = blog.get("site_path", "")

        if platform != "hugo":
            continue
        if not site_path:
            results.append((str(site_path), blog_id, "skip-no-site-path"))
            continue

        css_dir = Path(site_path) / "assets" / "css" / "extended"
        css_file = css_dir / "funnel-card.css"

        if css_file in seen_paths:
            results.append((str(site_path), blog_id, "exists"))
            continue

        seen_paths.add(css_file)

        if dry_run:
            results.append((str(site_path), blog_id, "dry-run"))
            continue

        css_dir.mkdir(parents=True, exist_ok=True)
        css_file.write_text(CSS_CONTENT, encoding="utf-8")
        results.append((str(site_path), blog_id, "written"))

    return results


def print_stats(results):
    """Print summary table."""
    total = len(results)
    written = sum(1 for _, _, s in results if s == "written")
    exists = sum(1 for _, _, s in results if s == "exists")
    skipped = sum(1 for _, _, s in results if s == "skip-no-site-path")

    print(f"\n{'Site Path':<50} {'Blog':<20} {'Status'}")
    print("-" * 80)
    for site_path, blog_id, status in sorted(results, key=lambda x: x[2]):
        print(f"{site_path:<50} {blog_id:<20} {status}")

    print(f"\nTotal Hugo sites: {total}")
    print(f"  Written:  {written}")
    print(f"  Exists:   {exists}")
    print(f"  Skipped:  {skipped}")


def main():
    parser = argparse.ArgumentParser(description="Deploy funnel-card.css to Hugo sites")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no writes")
    args = parser.parse_args()

    blogs = load_blog_configs()
    total = len(blogs)
    hugo_count = sum(1 for b in blogs if b.get("platform") == "hugo")
    print(f"Loaded {total} blog configs ({hugo_count} Hugo)")

    results = deploy_css(blogs, dry_run=args.dry_run)
    print_stats(results)

    if args.dry_run:
        print("\nRun without --dry-run to write files.")

    return 0


if __name__ == "__main__":
    sys.exit(main())

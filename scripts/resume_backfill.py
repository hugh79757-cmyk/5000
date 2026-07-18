#!/usr/bin/env python3
"""Resume the informationhot-hugo thumbnail backfill using optimized batch mode."""
import glob, os, re, sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import yaml

from shared.thumbnail_generator import generate_batch

SITE_PATH = os.path.expanduser("~/Projects/informationhot-hugo")
POSTS_DIR = os.path.join(SITE_PATH, "content", "posts")
PROGRESS_FILE = os.path.join(os.path.dirname(__file__), ".batch_thumbnails_progress.txt")
COVER_FIELD = ("cover", "image")

def _load_progress():
    if not os.path.exists(PROGRESS_FILE):
        return set()
    with open(PROGRESS_FILE) as f:
        return set(line.strip() for line in f if line.strip())

def _save_progress(slug):
    os.makedirs(os.path.dirname(PROGRESS_FILE) or ".", exist_ok=True)
    with open(PROGRESS_FILE, "a") as f:
        f.write(f"{slug}\n")

def _update_frontmatter(filepath, new_url):
    with open(filepath) as f:
        raw = f.read()
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return False
    raw_fm = parts[1]
    parent, child = COVER_FIELD
    cover_block = f"{parent}:\n  {child}: \"{new_url}\""
    if f"{parent}:" in raw_fm:
        pattern = re.compile(rf"^{re.escape(parent)}:.*?(?=^[a-z]|\Z)", re.MULTILINE | re.DOTALL)
        raw_fm = pattern.sub(cover_block + "\n", raw_fm)
    else:
        lines = raw_fm.split("\n")
        insert_idx = len(lines) - 1
        for i in range(len(lines) - 1, -1, -1):
            if lines[i].strip() and not lines[i].strip().startswith("#"):
                insert_idx = i + 1
                break
        lines.insert(insert_idx, cover_block)
        raw_fm = "\n".join(lines)
    raw = f"---{raw_fm}---{parts[2]}"
    with open(filepath, "w") as f:
        f.write(raw)
    return True

def main():
    done = _load_progress()
    print(f"Already processed: {len(done)}")

    # Collect all posts
    all_posts = []
    for d in sorted(glob.glob(os.path.join(POSTS_DIR, "*"))):
        if not os.path.isdir(d):
            continue
        idx = os.path.join(d, "index.md")
        if not os.path.exists(idx):
            continue
        slug = os.path.basename(d)
        with open(idx) as f:
            raw = f.read()
        parts = raw.split("---", 2)
        if len(parts) < 3:
            continue
        try:
            meta = yaml.safe_load(parts[1])
        except:
            continue
        if meta.get("draft", False):
            continue
        title = (meta.get("title") or "").strip()
        if not title:
            continue
        cats = meta.get("categories") or []
        cat = cats[0] if isinstance(cats, list) and cats else ""

        # Skip if already done
        if slug in done:
            continue

        # Skip if already has new thumbnail
        cover = meta.get("cover", {}) or {}
        if "thumbnails/informationhot" in (cover.get("image") or ""):
            continue

        all_posts.append({
            "slug": slug,
            "filepath": idx,
            "title": title,
            "category": cat,
        })

    if not all_posts:
        print("All posts already processed!")
        return

    print(f"Remaining: {len(all_posts)} posts")
    print(f"From: {all_posts[0]['slug']}  →  To: {all_posts[-1]['slug']}")

    # Run optimized batch (single browser session)
    results = generate_batch(
        site_id="informationhot",
        posts=all_posts,
        template_name="default.html",
        progress_callback=lambda slug, success, result: (
            _update_frontmatter(
                next(p["filepath"] for p in all_posts if p["slug"] == slug),
                result,
            ) if success and result else None,
            _save_progress(slug),
            print(f"  {'✓' if success else '✗'} {slug}"),
        ),
    )

    ok = sum(1 for r in results if r["success"])
    fail = sum(1 for r in results if not r["success"])
    print(f"\nDone: {ok} generated, {fail} failed")

if __name__ == "__main__":
    main()

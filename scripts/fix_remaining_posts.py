#!/usr/bin/env python3
"""Fix remaining post issues after backfill."""
import glob, os, re, sys, unicodedata
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import yaml

from shared.thumbnail_generator import generate_batch

BASE = os.path.expanduser("~/Projects/informationhot-hugo/content/posts")
SITE_ID = "informationhot"
COVER_FIELD = ("cover", "image")

remaining = []
for d in sorted(glob.glob(os.path.join(BASE, "*"))):
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
    except yaml.YAMLError:
        meta = None
    if meta is None:
        title = slug
        cat = ""
        for line in raw.split("\n"):
            if line.startswith("title:"):
                title = line.split(":", 1)[1].strip().strip('"').strip("'")
            if line.startswith("categories:"):
                m = re.findall(r'\[(.*?)\]', line)
                if m:
                    cat = m[0].split(",")[0].strip().strip('"').strip("'")
        remaining.append({"slug": slug, "filepath": idx, "title": title, "category": cat, "broken_fm": True})
        continue
    cover = meta.get("cover", {}) or {}
    existing = cover.get("image", "") or ""
    if existing and "thumbnails/informationhot" not in existing:
        title = (meta.get("title") or "").strip()
        cats = meta.get("categories") or []
        cat = cats[0] if isinstance(cats, list) and cats else ""
        remaining.append({"slug": slug, "filepath": idx, "title": title, "category": cat, "broken_fm": False})

print(f"Found {len(remaining)} problem posts")
for p in remaining:
    print(f"  {p['slug'][:50]}... (broken_fm={p['broken_fm']})")

if not remaining:
    print("All clean!")
    sys.exit(0)

from shared.thumbnail_generator.generator import _import_playwright, RENDER_WIDTH, RENDER_HEIGHT
from shared.thumbnail_generator.generator import (
    get_blog_palette, get_accent_for_category, split_title,
    _calc_font_sizes, _write_temp_html, _upload_to_r2,
    TEMPLATE_DIR, MAX_WEBP_SIZE, OUTPUT_WEBP_QUALITY,
)
from jinja2 import Environment, FileSystemLoader
from PIL import Image

sync_playwright, err = _import_playwright()
if err:
    print(f"\u2717 {err}")
    sys.exit(1)

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={"width": RENDER_WIDTH, "height": RENDER_HEIGHT}, device_scale_factor=2)
    for post in remaining:
        slug = post["slug"]; title = post["title"]; cat = post["category"]; filepath = post["filepath"]; broken_fm = post["broken_fm"]
        print(f"\n=== {slug[:50]}... ===")
        safe_key = unicodedata.normalize("NFC", slug)
        safe_key = re.sub(r"[^a-zA-Z0-9\uac00-\ud7af\-_]", "", safe_key).strip("-")[:80]
        print(f"  safe_key: {safe_key}")
        palette = get_blog_palette(SITE_ID)
        accent = get_accent_for_category(SITE_ID, cat)
        badge_bg = palette.get("badge_bg", "rgba(255,255,255,0.2)")
        site_bar = palette.get("site_bar", "")
        title_line1, title_line2 = split_title(title)
        font_sizes = _calc_font_sizes(title_line1, title_line2)
        env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
        template = env.get_template("default.html")
        html_content = template.render(accent=accent, title_line1=title_line1, title_line2=title_line2, title1_size=font_sizes["title1_size"], title1_size_single=font_sizes["title1_size"], title2_size=font_sizes["title2_size"], category=cat or "", badge_bg=badge_bg, site_bar=site_bar)
        tmp_html = _write_temp_html(safe_key, html_content, None)
        try:
            page.goto(f"file://{tmp_html}", wait_until="networkidle")
            page.wait_for_timeout(1500)
            png_path = tmp_html.replace(".html", ".png")
            page.screenshot(path=png_path, full_page=False)
            img = Image.open(png_path)
            if img.mode == "RGBA":
                bg = Image.new("RGB", img.size, (255, 255, 255))
                bg.paste(img, mask=img.split()[3])
                img = bg
            if img.width > RENDER_WIDTH or img.height > RENDER_HEIGHT:
                img.thumbnail((RENDER_WIDTH, RENDER_HEIGHT), Image.LANCZOS)
            webp_path = png_path.replace(".png", ".webp")
            img.save(webp_path, "WEBP", quality=OUTPUT_WEBP_QUALITY, method=4)
            size = os.path.getsize(webp_path)
            quality = OUTPUT_WEBP_QUALITY
            while size > MAX_WEBP_SIZE and quality > 30:
                quality -= 10
                img.save(webp_path, "WEBP", quality=quality, method=4)
                size = os.path.getsize(webp_path)
            url = _upload_to_r2(SITE_ID, safe_key, webp_path, tmp_html)
            print(f"  ✓ R2: {url[:70]}...")
            with open(filepath) as f:
                raw = f.read()
            parts = raw.split("---", 2)
            raw_fm = parts[1]
            if broken_fm:
                cover_block = f"cover:\n  image: \"{url}\""
                if "cover:" in raw_fm:
                    pattern = re.compile(rf"^cover:.*?(?=^[a-z]|\Z)", re.MULTILINE | re.DOTALL)
                    raw_fm = pattern.sub(cover_block + "\n", raw_fm)
                else:
                    raw_fm = raw_fm.rstrip() + "\n" + cover_block + "\n"
            else:
                parent, child = COVER_FIELD
                cover_block = f"{parent}:\n  {child}: \"{url}\""
                if f"{parent}:" in raw_fm:
                    pattern = re.compile(rf"^{re.escape(parent)}:.*?(?=^[a-z]|\Z)", re.MULTILINE | re.DOTALL)
                    raw_fm = pattern.sub(cover_block + "\n", raw_fm)
                else:
                    raw_fm = raw_fm.rstrip() + "\n" + cover_block + "\n"
            raw = f"---{raw_fm}---{parts[2]}"
            with open(filepath, "w") as f:
                f.write(raw)
            print(f"  ✓ Frontmatter updated")
        except Exception as e:
            print(f"  ✗ Error: {e}")
        finally:
            for p in [tmp_html, tmp_html.replace(".html", ".png"), tmp_html.replace(".html", ".webp")]:
                if os.path.exists(p):
                    os.remove(p)
    browser.close()

print("\n=== Final verification ===")
old_count = err_count = 0
total = 0
for d in sorted(glob.glob(os.path.join(BASE, "*"))):
    if not os.path.isdir(d):
        continue
    idx = os.path.join(d, "index.md")
    if not os.path.exists(idx):
        continue
    total += 1
    with open(idx) as f:
        raw = f.read()
    parts = raw.split("---", 2)
    if len(parts) < 3:
        err_count += 1
        continue
    try:
        meta = yaml.safe_load(parts[1])
    except:
        err_count += 1
        continue
    cover = meta.get("cover", {}) or {}
    url = cover.get("image", "") or ""
    if url and "thumbnails/informationhot" not in url:
        old_count += 1
        print(f"  STILL OLD: {os.path.basename(d)}")
print(f"\nTotal: {total} posts | New: {total - old_count - err_count} | Old: {old_count} | Parse errors: {err_count}")

#!/usr/bin/env python3
"""
Generate unique favicons for all 5000 Hugo blogs.
Each blog gets personalized rounded-square favicon with initials and distinct color.
Replaces Blowfish default fallback (missing static/favicon*).
"""
import os, glob, yaml, hashlib, colorsys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    raise SystemExit("Pillow required: pip install Pillow")

# Load blogs
blogs=[]
for f in glob.glob("config/blogs.d/*.yaml"):
    with open(f) as fh:
        data=yaml.safe_load(fh)
        lst = data if isinstance(data, list) else data.get('blogs',[]) if isinstance(data, dict) else []
        for b in lst:
            if b.get('site_path'):
                blogs.append(b)

print(f"Total blogs: {len(blogs)}")

# Helpers
def blog_color(blog_id: str):
    """Deterministic vibrant color via HSL hash."""
    h = int(hashlib.md5(blog_id.encode()).hexdigest()[:6], 16) % 360
    # Custom overrides for intuition (optional): keep hash but tweak S/L per family
    # Family palettes: just hash is enough for distinctness.
    # Convert HSL(360, 70%, 48%) -> RGB
    s, l = 0.72, 0.48
    r,g,b = colorsys.hls_to_rgb(h/360, l, s)  # note hls
    return (int(r*255), int(g*255), int(b*255))

def blog_initials(blog_id: str, name: str):
    core = blog_id.replace("-hugo","")
    # best-kitchen -> BK, travel1 -> T1, etc.
    parts = core.split("-")
    if len(parts) == 1:
        # single word: 2 chars
        w = parts[0]
        if len(w) <= 2:
            return w.upper()
        # for words like appliance, fitness, use 2 chars
        return w[:2].upper()
    elif len(parts) >= 2:
        # take first char of each part
        initials = "".join(p[0] for p in parts if p)[:3]
        # if ends with digit (travel1), keep digit
        return initials.upper()
    return core[:2].upper()

def find_font(size: int):
    candidates = [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except: pass
    # fallback - may be bitmap but ok
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", size)
    except:
        return ImageFont.load_default()

def rounded_rect(draw, xy, radius, fill):
    x0,y0,x1,y1 = xy
    # Pillow >=8 has rounded_rectangle
    try:
        draw.rounded_rectangle(xy, radius=radius, fill=fill)
    except:
        draw.rectangle(xy, fill=fill)

def generate_one(blog_id, name, site_path):
    bg = blog_color(blog_id)
    initials = blog_initials(blog_id, name)
    # shorten if 3 chars but tiny favicon may be crowded; keep 2 max for 16px
    display_text = initials[:2] if len(initials) > 2 else initials

    # Create 512 master
    size = 512
    img = Image.new("RGBA", (size, size), (0,0,0,0))
    draw = ImageDraw.Draw(img)
    # rounded square bg
    margin = 8
    rounded_rect(draw, (margin, margin, size-margin, size-margin), radius=112, fill=bg)
    # Add subtle inner highlight (top gloss)
    # lighter bg for gloss
    lr, lg, lb = [min(255, c+35) for c in bg]
    # small highlight ellipse at top - optional, skip for simplicity

    # Draw text
    # Choose font size: 2 chars -> ~180, 1 char -> ~240, 3 chars -> ~140
    if len(display_text) == 1:
        fsize = 260
    elif len(display_text) == 2:
        fsize = 210
    else:
        fsize = 160
    font = find_font(fsize)
    # measure
    try:
        bbox = draw.textbbox((0,0), display_text, font=font)
        tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
    except:
        tw, th = (len(display_text)*fsize*0.6, fsize)
    tx = (size - tw)//2
    ty = (size - th)//2 - 10  # slight optical adjust
    # shadow
    draw.text((tx+6, ty+6), display_text, font=font, fill=(0,0,0,70))
    draw.text((tx, ty), display_text, font=font, fill=(255,255,255,255))

    # Ensure static dir
    static_dir = Path(site_path) / "static"
    static_dir.mkdir(parents=True, exist_ok=True)

    # Generate sizes
    def save_png(sz, fname):
        im = img.resize((sz, sz), Image.LANCZOS)
        im.save(static_dir / fname, "PNG", optimize=True)

    save_png(32, "favicon-32x32.png")
    save_png(16, "favicon-16x16.png")
    save_png(180, "apple-touch-icon.png")
    # android chrome optional but good
    save_png(192, "android-chrome-192x192.png")
    save_png(512, "android-chrome-512x512.png")

    # ICO with 16,32,48
    ico_sizes = []
    for sz in [16,32,48]:
        ico_sizes.append(img.resize((sz, sz), Image.LANCZOS))
    ico_path = static_dir / "favicon.ico"
    # Pillow ICO save needs list
    ico_sizes[1].save(ico_path, format="ICO", sizes=[(16,16),(32,32),(48,48)])

    # site.webmanifest if missing
    manifest = static_dir / "site.webmanifest"
    if not manifest.exists():
        manifest.write_text('{"name":"","short_name":"","icons":[{"src":"/android-chrome-192x192.png","sizes":"192x192","type":"image/png"},{"src":"/android-chrome-512x512.png","sizes":"512x512","type":"image/png"}],"theme_color":"#ffffff","background_color":"#ffffff","display":"standalone"}')

    return bg, initials, display_text

# Preview table
print(f"{'blog_id':30} {'initials':6} {'color':10} {'path'}")
for b in sorted(blogs, key=lambda x: x['id']):
    bid = b['id']
    name = b.get('name','')
    sp = b['site_path']
    bg, initials, disp = generate_one(bid, name, sp)
    hexcol = f"#{bg[0]:02x}{bg[1]:02x}{bg[2]:02x}"
    print(f"{bid:30} {initials:6} {hexcol:10} {sp}")

print("\nDone. Generated favicons for", len(blogs), "blogs.")

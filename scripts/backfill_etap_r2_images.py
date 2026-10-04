#!/usr/bin/env python3
"""Backfill missing ETAP R2 image objects listed in an audit_images.py report.

Reads `detail` from the census report (no re-scan of content), searches a
replacement photo per missing R2 key, encodes it to the key's OWN extension and
uploads it. Content files are read-only. Existing R2 objects are never
overwritten: `file_exists()` is checked first and the key is skipped.

Progress is an append-only JSONL log so a timeout/kill loses nothing.

Usage:
    python scripts/backfill_etap_r2_images.py --self-check
    python scripts/backfill_etap_r2_images.py --dry-run
    python scripts/backfill_etap_r2_images.py [--report ...] [--site ...] [--workers 4]
"""
import argparse
import io
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared import env_loader  # noqa: F401
from shared.r2_uploader import file_exists, upload_bytes  # noqa: E402
from pipelines.etap.image_fetcher import (  # noqa: E402
    _mark_image_used,
    _search_pexels,
    _search_with_fallback,
    _to_webp,
)

DEFAULT_REPORT = ".planning/quick/261004-gz6-nomad-techpawz-com/audit-report.json"
DEFAULT_SITE = "/Users/twinssn/Projects/ETAP/nomad-hugo"
DEFAULT_LOG = "data/backfill_etap_r2_images.jsonl"
BUCKET = "hotissue-images"

# Key gate: etap/<slug>/<cover|body_N>.<jpg|webp>. '..' rejected separately so a
# markdown-derived slug cannot escape the prefix.
KEY_RE = re.compile(r"^etap/[a-z0-9._-]+/(cover|body_\d+)\.(jpg|webp)$")
CT = {".webp": "image/webp", ".jpg": "image/jpeg"}
SLUG_SUFFIXES = ("-digital-nomad-guide", "-coworking-guide", "-nomad-guide")

IMG_RE = re.compile(r"!\[[^\]]*\]\(\s*([^)>\s]+)")
CREDIT_RE = re.compile(r"Photo by \[([^\]]+)\]")


# --- pure helpers (self-checked without network/R2) -------------------------
def r2_key(target):
    """'hotissue-images/etap/x/cover.webp' -> 'etap/x/cover.webp' | None if invalid."""
    _, _, key = target.partition("/")
    if not key or ".." in key or not KEY_RE.match(key):
        return None
    return key


def content_type(ext):
    return CT[ext]


def encode_for_ext(raw, ext):
    """Encode downloaded bytes to match the key's extension (no MIME mismatch)."""
    if ext == ".webp":
        return _to_webp(raw)
    from PIL import Image
    img = Image.open(io.BytesIO(raw))
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    return buf.getvalue()


def done_keys(log_path):
    """Keys already handled in a previous run (ok/skip) so they are not re-searched."""
    done = set()
    if not os.path.exists(log_path):
        return done
    with open(log_path, encoding="utf-8") as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if rec.get("status") in ("ok", "skip"):
                done.add(rec["key"])
    return done


def append_log(fh, rec):
    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    fh.flush()


def slug_query(slug):
    q = slug
    for suf in SLUG_SUFFIXES:
        if q.endswith(suf):
            q = q[: -len(suf)]
            break
    return q.replace("-", " ").strip()


def tags_city_country(fm):
    """city/country from frontmatter tags. Handles `tags: [A, B]` and block `- A`."""
    tags = []
    inline = re.search(r"^tags:\s*\[(.*?)\]", fm, re.M)
    if inline:
        tags = [t.strip().strip("'\"") for t in inline.group(1).split(",") if t.strip()]
    else:
        block = re.search(r"^tags:\s*\n((?:\s*-\s*.+\n?)+)", fm, re.M)
        if block:
            tags = [m.strip().strip("'\"") for m in re.findall(r"-\s*(.+)", block.group(1))]
    tags = [t for t in tags if t.lower() not in ("uncategorized", "digital nomad",
                                                "coworking", "remote work", "travel", "nomad")]
    city = tags[0] if tags else ""
    country = tags[1] if len(tags) > 1 else ""
    return city, country


def body_credits(body):
    """Photographer credit per body image, index-aligned with audit_images.py."""
    out = []
    ms = list(IMG_RE.finditer(body))
    for i, m in enumerate(ms):
        end = ms[i + 1].start() if i + 1 < len(ms) else len(body)
        c = CREDIT_RE.search(body[m.end():end])
        out.append(c.group(1) if c else None)
    return out


def featureimage_credit(fm):
    line = re.search(r"^featureimagecredit:.*$", fm, re.M)
    if not line:
        return None
    c = CREDIT_RE.search(line.group(0))
    return c.group(1) if c else None


# --- network work -----------------------------------------------------------
# Pexels free tier enforces a short-window burst limiter (HTTP 429 "Throttle limit
# exceeded") that is far tighter than the 25,000 x-ratelimit-remaining header.
# A process-wide min interval keeps us under it. ponytail: one global lock, no
# token bucket — if throughput ever matters, swap in a real limiter.
_PACE_LOCK = threading.Lock()
_LAST_CALL = [0.0]
_CACHE = {}
_CACHE_LOCK = threading.Lock()
MIN_INTERVAL = 0.35  # ~170 req/min


def _pace():
    with _PACE_LOCK:
        wait = MIN_INTERVAL - (time.monotonic() - _LAST_CALL[0])
        if wait > 0:
            time.sleep(wait)
        _LAST_CALL[0] = time.monotonic()


def search_cached(fn, query, per_page=5, city="", country=""):
    """Paced + memoized search. Repeat queries are free; 429s stay rare."""
    key = (fn.__name__, query, per_page, city, country)
    with _CACHE_LOCK:
        if key in _CACHE:
            return _CACHE[key]
    _pace()
    hits = fn(query, per_page, city, country)
    with _CACHE_LOCK:
        _CACHE[key] = hits
    return hits


def find_photo(credit, city, country, slugq):
    """-> (photo, credit_match). Credit-name search first (keeps attribution)."""
    if credit:
        hits = search_cached(_search_with_fallback, credit)
        if hits:
            return hits[0], True
    # Unsplash's key is exhausted (403, remaining=0) — keep the credit probe as
    # the only _search_with_fallback() call; geographic fallbacks go to Pexels.
    queries = []
    if city:
        queries.append(f"{city} {country} travel" if country else f"{city} travel")
    if city:
        queries.append(f"{city} travel")
    if slugq:
        queries.append(slugq)
    for q in queries:
        hits = search_cached(_search_pexels, q)
        if hits:
            return hits[0], False
    return None, False


def process(item, site_posts, log_fh):
    import requests
    slug = item["slug"]
    key = r2_key(item["target"])
    if key is None:
        return {"key": item["target"], "status": "fail", "reason": "key_gate", "src": ""}
    try:
        fm, _, body = site_posts[slug]
    except KeyError:
        return {"key": key, "status": "fail", "reason": "post_not_found", "src": ""}

    if file_exists(key, bucket=BUCKET):
        rec = {"key": key, "status": "skip", "src": ""}
        append_log(log_fh, rec)
        return rec

    if item["field"] == "featureimage":
        credit = featureimage_credit(fm)
    else:
        idx = int(item["field"].split("_")[1]) - 1
        credits = body_credits(body)
        credit = credits[idx] if 0 <= idx < len(credits) else None
    city, country = tags_city_country(fm)

    photo, credit_match = find_photo(credit, city, country, slug_query(slug))
    if photo is None:
        rec = {"key": key, "status": "fail", "reason": "no_photo", "src": "",
               "credit_match": False}
        append_log(log_fh, rec)
        return rec
    try:
        raw = requests.get(photo["url"], timeout=15).content
        ext = ".webp" if key.endswith(".webp") else ".jpg"
        data = encode_for_ext(raw, ext)
        url = upload_bytes(data, key, content_type=content_type(ext), bucket=BUCKET)
        if not url:
            raise RuntimeError("upload_bytes returned None")
        _mark_image_used(photo["url"], photo["photographer"], photo["source"], slug,
                         "cover" if item["field"] == "featureimage" else "body")
    except Exception as e:  # noqa: BLE001 — one bad photo must not kill the run
        rec = {"key": key, "status": "fail", "reason": f"{type(e).__name__}: {e}",
               "src": photo["url"]}
        append_log(log_fh, rec)
        return rec
    rec = {"key": key, "status": "ok", "src": photo["url"],
           "credit_match": credit_match, "credit": credit or ""}
    append_log(log_fh, rec)
    return rec


# --- self-check -------------------------------------------------------------
def demo():
    """Pure-function checks, no network and no R2."""
    # (a) target -> r2_key
    assert r2_key("hotissue-images/etap/bali-digital-nomad-guide/cover.webp") == \
        "etap/bali-digital-nomad-guide/cover.webp"
    assert r2_key("hotissue-images/etap/porto-digital-nomad-guide/body_2.jpg") == \
        "etap/porto-digital-nomad-guide/body_2.jpg"
    # (b) extension -> content_type
    assert content_type(".webp") == "image/webp"
    assert content_type(".jpg") == "image/jpeg"
    # (c) _encode_for_ext produces a real image in the key's format
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (10, 20, 30)).save(buf, "PNG")
    jpg = encode_for_ext(buf.getvalue(), ".jpg")
    assert Image.open(io.BytesIO(jpg)).format == "JPEG"
    webp = encode_for_ext(buf.getvalue(), ".webp")
    assert Image.open(io.BytesIO(webp)).format == "WEBP"
    # (d) JSONL resume set round-trip
    tmp = "data/.backfill_selfcheck.jsonl"
    with open(tmp, "w", encoding="utf-8") as fh:
        append_log(fh, {"key": "etap/a/cover.webp", "status": "ok"})
        append_log(fh, {"key": "etap/a/body_1.webp", "status": "fail"})
    assert done_keys(tmp) == {"etap/a/cover.webp"}
    os.remove(tmp)
    # (e) key gate rejects traversal and foreign prefixes
    assert r2_key("hotissue-images/etap/../body_1.webp") is None
    assert r2_key("hotissue-images/etap/../../body_1.webp") is None
    assert r2_key("hotissue-images/common/default-thumbnail.webp") is None
    assert r2_key("hotissue-images/etap/a/cover.png") is None
    # (f) credit + tag parsing on a real-shape frontmatter/body
    fm = ("tags: [Abdeen, Egypt, Digital Nomad, Coworking]\n"
          "featureimagecredit: '\"Photo by [Vernie Andrea](https://www.pexels.com/@v)\"'\n")
    body = ("![a](https://x/etap/a/body_1.webp)\n"
            "*Photo by [Ali R Bataklar](https://www.pexels.com/@a) on [Pexels](x)*\n"
            "![b](https://x/etap/a/body_2.webp)\n")
    assert tags_city_country(fm) == ("Abdeen", "Egypt")
    assert body_credits(body) == ["Ali R Bataklar", None]
    assert featureimage_credit(fm) == "Vernie Andrea"
    print("self-check OK (6 groups)")


# --- main -------------------------------------------------------------------
def load_site_posts(site):
    posts = {}
    root = os.path.join(site, "content", "posts")
    for name in sorted(os.listdir(root)):
        path = os.path.join(root, name, "index.md")
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8", errors="replace") as fh:
            posts[name] = fh.read().partition("\n---")
    return posts


def main():
    global MIN_INTERVAL
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--report", default=DEFAULT_REPORT)
    ap.add_argument("--site", default=DEFAULT_SITE)
    ap.add_argument("--log", default=DEFAULT_LOG)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--max-per-run", type=int, default=900)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--self-check", action="store_true")
    ap.add_argument("--pace", type=float, default=MIN_INTERVAL,
                    help="min seconds between search calls (Pexels burst guard)")
    args = ap.parse_args()

    MIN_INTERVAL = args.pace

    if args.self_check:
        demo()
        return

    with open(args.report, encoding="utf-8") as fh:
        report = json.load(fh)
    detail = report["detail"]

    work, wrong_slug, external = [], [], 0
    for slug, entries in detail.items():
        for e in entries:
            if e["kind"] == "r2":
                work.append({"slug": slug, **e})
            elif e["kind"] == "r2-wrong-slug":
                wrong_slug.append((slug, e["target"], e["exists"]))
            else:
                external += 1

    done = done_keys(args.log)
    valid = [w for w in work if r2_key(w["target"])]
    todo = [w for w in valid if r2_key(w["target"]) not in done]
    already = len(valid) - len(todo)
    selected = todo[: args.max_per_run]

    print(f"report            : {args.report}")
    print(f"planned (r2)      : {len(work)}  (jpg/webp mixed, extensions preserved)")
    print(f"already-done      : {already}")
    print(f"selected this run : {len(selected)} (--max-per-run {args.max_per_run})")
    print(f"skipped kinds     : external={external} r2-wrong-slug={len(wrong_slug)}")
    for slug, target, exists in wrong_slug:
        print(f"  REPORT r2-wrong-slug: {slug} -> {target} (exists={exists}) — "
              "shared fallback thumbnail, not touched")
    if not selected:
        print("nothing to do")
        return
    if args.dry_run:
        print("dry-run: no search, no upload")
        return

    site_posts = load_site_posts(args.site)
    os.makedirs(os.path.dirname(args.log) or ".", exist_ok=True)
    counters = {"uploaded": 0, "skip": 0, "fail": 0, "credit_mismatch": 0}
    print(f"running: {len(selected)} keys, workers={args.workers}")
    with open(args.log, "a", encoding="utf-8") as log_fh:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futs = {pool.submit(process, w, site_posts, log_fh): w for w in selected}
            for n, fut in enumerate(as_completed(futs), 1):
                rec = fut.result()
                if rec["status"] == "ok":
                    counters["uploaded"] += 1
                    if not rec.get("credit_match"):
                        counters["credit_mismatch"] += 1
                elif rec["status"] == "skip":
                    counters["skip"] += 1
                else:
                    counters["fail"] += 1
                    print(f"  FAIL {rec['key']}: {rec.get('reason')}")
                if n % 50 == 0 or n == len(selected):
                    print(f"  ..{n}/{len(selected)} uploaded={counters['uploaded']} "
                          f"skip={counters['skip']} fail={counters['fail']}")

    print("=== backfill summary ===")
    print(f"planned           : {len(work)}")
    print(f"uploaded          : {counters['uploaded']}")
    print(f"skipped-existing  : {counters['skip']}")
    print(f"already-done      : {already}")
    print(f"failed            : {counters['fail']}")
    print(f"credit-mismatch   : {counters['credit_mismatch']}")
    if counters["fail"]:
        print("WARNING: failed > 0 — quiet success is forbidden, re-run to top up.")


if __name__ == "__main__":
    main()
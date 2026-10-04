#!/usr/bin/env python3
"""Census every image reference in nomad-hugo content vs what actually exists in R2.

Usage: python3 audit_images.py [--site /Users/twinssn/Projects/ETAP/nomad-hugo]
                               [--out /path/to/report.json]
Writes the report (default audit-report.json) + prints a human summary.
Read-only: touches no content.
"""
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, "/Users/twinssn/Projects/5000")
from shared import env_loader  # noqa: F401

SITE = Path(sys.argv[sys.argv.index("--site") + 1] if "--site" in sys.argv
            else "/Users/twinssn/Projects/ETAP/nomad-hugo")
POSTS = SITE / "content" / "posts"
OUT = Path(sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv
           else "/Users/twinssn/Projects/5000/.planning/quick/"
                "261004-gz6-nomad-techpawz-com/audit-report.json")

HOSTS = {  # r2 host -> bucket, mirrors shared/r2_uploader.py BUCKET_PUBLIC_URLS
    "pub-2f5c7af1c303419a933069212bc25874.r2.dev": "hotissue-images",
    "pub-3f702c9170934a72bc62a5436c406aa6.r2.dev": "senior-images",
}
IMG_RE = re.compile(r"!\[[^\]]*\]\(\s*([^)>\s]+)")
FEAT_RE = re.compile(r"^featureimage:\s*(\S+)\s*$", re.M)


def bucket_keys():
    import boto3
    s3 = boto3.client(
        "s3",
        endpoint_url=os.getenv("R2_ENDPOINT"),
        aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY"),
        region_name="auto",
    )
    keys = set()
    for bucket in set(HOSTS.values()):
        pag = s3.get_paginator("list_objects_v2")
        for page in pag.paginate(Bucket=bucket):
            for o in page.get("Contents", []):
                keys.add((bucket, o["Key"]))
    return keys


def classify(url, slug):
    """-> (kind, detail)"""
    if not url:
        return "empty", ""
    for host, bucket in HOSTS.items():
        if host in url:
            key = url.split(host + "/", 1)[1]
            kind = "r2"
            if f"/{slug}/" not in key:
                kind = "r2-wrong-slug"
            return kind, f"{bucket}/{key}"
    if url.startswith("/") or url.startswith("http://localhost") or url.startswith("http://127.0.0.1"):
        return "local-path", url
    if url.startswith("data:"):
        return "inline-data", ""
    return "external", url


def main():
    existing = bucket_keys()
    report = {}
    kinds = Counter()
    per_host_missing = Counter()

    for md in sorted(POSTS.glob("*/index.md")):
        slug = md.parent.name
        text = md.read_text(encoding="utf-8", errors="replace")
        fm, _, body = text.partition("\n---")
        refs = []
        m = FEAT_RE.search(fm)
        if m:
            refs.append(("featureimage", m.group(1).strip('"\'')))
        for i, u in enumerate(IMG_RE.findall(body), 1):
            refs.append((f"body_{i}", u.strip()))
        # og:image / other frontmatter image keys
        for line in fm.splitlines():
            k = line.split(":", 1)[0].strip()
            if k in ("coverimage", "ogimage", "bannerimage", "thumbnail") and ":" in line:
                refs.append((k, line.split(":", 1)[1].strip().strip('"\'')))

        entries = []
        for field, url in refs:
            kind, detail = classify(url, slug)
            exists = None
            if kind.startswith("r2"):
                b, _, key = detail.partition("/")
                exists = (b, key) in existing
                if not exists:
                    per_host_missing[detail.split("/")[0] + " " + detail.split("/")[1].split("/")[0]] += 1
            kinds[kind] += 1
            entries.append({"field": field, "url": url, "kind": kind,
                            "target": detail, "exists": exists})
        if entries:
            report[slug] = entries

    bad = {s: e for s, e in report.items() if any(x["exists"] is False for x in e)}
    out = OUT
    out.write_text(json.dumps({"kinds": dict(kinds), "posts": len(report),
                               "posts_with_missing": len(bad), "missing_by_prefix":
                               dict(per_host_missing), "detail": bad}, indent=1, ensure_ascii=False))

    print(f"posts scanned      : {len(report)}")
    print(f"image refs total   : {sum(kinds.values())}")
    print(f"  by kind          : {dict(kinds)}")
    print(f"posts w/ missing   : {len(bad)}")
    print(f"missing by prefix  : {dict(per_host_missing.most_common(10))}")
    print(f"report             : {out}")


if __name__ == "__main__":
    main()
"""27-03: replace -rec 404 URLs in baked CUAP posts with real target slugs.

Each -rec URL maps (by host) to a target blog; we replace it with that
blog's newest real published post URL. Backs up each touched file first.
"""

import os
import re

CUAP_ROOT = "/Users/twinssn/Projects/cuap"

# -rec URL -> real published URL (newest real slug per target blog), with /posts/ permalink
MAPPING = {
    "https://camping.informationhot.kr/20260720-camping-rec/":
        "https://camping.informationhot.kr/posts/2026년-7월-dxz안델센-v3-캠핑-카트-추천-오토캠핑부터-나들이까지-실속-선택/",
    "https://fitness.informationhot.kr/20260720-yoga-rec/":
        "https://fitness.informationhot.kr/posts/프로스펙스코멧-스포츠-운동-밴드-추천-2026년-7월-실속-5종-비교/",
    "https://health.informationhot.kr/20260720-health-rec/":
        "https://health.informationhot.kr/posts/2026년-7월-항산화-영양제-추천-뉴트리정gnm동화약품-하루-300원대부터-시작하는-선택/",
    "https://interior.informationhot.kr/20260720-interior-rec/":
        "https://interior.informationhot.kr/posts/2026년-7월-퀸-침대-추천-흔한-오해-3가지-오키멧아너스하포스-사례로-바로잡기/",
    "https://kitchen.informationhot.kr/20260720-kitchen-rec/":
        "https://kitchen.informationhot.kr/posts/2026년-7월-그릴가방-추천-스테츠-핏보이캠핑몽-카고-상황별-실속-선택/",
    "https://pet.informationhot.kr/20260720-pet-rec/":
        "https://pet.informationhot.kr/posts/베베페페아미체볼레-고양이대리석-고를-때-꼭-확인할-3가지-2026년-7월-기준/",
}

# verify each real slug dir exists on disk
for rec, real in MAPPING.items():
    m = re.match(r"https://([\w-]+)\.informationhot\.kr/posts/(.+)/", real)
    host, slug = m.group(1), m.group(2)
    blog = f"{host}-hugo"
    d = os.path.join(CUAP_ROOT, blog, "content", "posts", slug)
    assert os.path.isdir(d), f"REAL SLUG MISSING on disk: {blog}/{slug}"
print("All replacement target slugs verified on disk.")


def find_files():
    hits = set()
    pat = re.compile(r"informationhot\.kr/20260720-.*-rec/")
    for root, dirs, files in os.walk(CUAP_ROOT):
        if "content/posts" not in root.replace("\\", "/"):
            continue
        for fn in files:
            if fn == "index.md":
                p = os.path.join(root, fn)
                with open(p, encoding="utf-8") as f:
                    if pat.search(f.read()):
                        hits.add(p)
    return sorted(hits)


# restore originals from .bak-2703 so replacement runs against -rec content
import glob
baks = glob.glob(os.path.join(CUAP_ROOT, "*", "content", "posts", "*", "index.md.bak-2703"))
for bak in baks:
    orig = bak[: -len(".bak-2703")]
    with open(bak, encoding="utf-8") as f:
        data = f.read()
    with open(orig, "w", encoding="utf-8") as f:
        f.write(data)
print(f"Restored {len(baks)} files from .bak-2703")

files = find_files()
print(f"Found {len(files)} baked post files with -rec URLs")

total_replaced = 0
for p in files:
    with open(p, encoding="utf-8") as f:
        text = f.read()
    bak = p + ".bak-2703"
    if not os.path.exists(bak):
        with open(bak, "w", encoding="utf-8") as f:
            f.write(text)
    new = text
    for rec, real in MAPPING.items():
        if rec in new:
            new = new.replace(rec, real)
            total_replaced += 1
    with open(p, "w", encoding="utf-8") as f:
        f.write(new)

print(f"Replaced {total_replaced} -rec URL occurrences across {len(files)} files")

# verification
import subprocess
res = subprocess.run(
    ["grep", "-rl", "informationhot.kr/20260720-.*-rec/", CUAP_ROOT],
    capture_output=True, text=True,
)
remaining = [l for l in res.stdout.splitlines() if l.strip()]
print(f"Remaining -rec files after replace: {len(remaining)}")
if remaining:
    print("LEFT OVER:", remaining)
print("27-03 DONE")

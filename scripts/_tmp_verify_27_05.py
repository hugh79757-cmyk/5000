"""27-05: live verification of fixed CUAP cross-sell cards."""
import os
import re
import subprocess
import urllib.parse

CUAP = "/Users/twinssn/Projects/cuap"


def find_source():
    src = []
    for root, dirs, files in os.walk(CUAP):
        if "/content/posts/" not in root.replace("\\", "/"):
            continue
        for fn in files:
            if fn.endswith(".bak-2703"):
                idx = os.path.join(root, fn)[: -len(".bak-2703")]
                slug_dir = os.path.dirname(idx)
                slug = os.path.basename(slug_dir)
                # blog = directory directly under CUAP_ROOT
                rel = os.path.relpath(slug_dir, CUAP)
                blog = rel.split(os.sep)[0]
                src.append((blog, slug))
    return sorted(set(src))


def curl(url, head=False):
    cmd = ["curl", "-s", "-L", "-o", "/dev/null", "-w", "%{http_code}"]
    if head:
        cmd.append("-I")
    cmd.append(url)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return r.stdout.strip()


def fetch(url):
    r = subprocess.run(["curl", "-s", url], capture_output=True, text=True, timeout=30)
    return r.stdout


src = find_source()
print(f"Source posts to verify: {len(src)}")

all_ok = True
card_links_checked = 0
card_links_fail = 0
rec_found = 0
src_fail = 0

for blog, slug in src:
    sub = blog.replace("-hugo", "")
    url = f"https://{sub}.informationhot.kr/posts/{urllib.parse.quote(slug)}/"
    code = curl(url)
    if code != "200":
        print(f"  [SRC FAIL] {blog}/{slug} -> HTTP {code}")
        src_fail += 1
        all_ok = False
        continue
    html = fetch(url)
    if "-rec" in html or "20260720-" in html and "-rec" in html:
        # count -rec occurrences
        n = len(re.findall(r"20260720-[a-z-]*-rec", html))
        if n:
            print(f"  [REC LEFT] {blog}/{slug} -> {n} -rec in live HTML")
            rec_found += n
            all_ok = False
    # extract all informationhot.kr card hrefs and check
    hrefs = re.findall(r"href=[\"']?(https://[a-z]+\.informationhot\.kr/[^\s\"'>]+)", html)
    for h in hrefs:
        card_links_checked += 1
        c = curl(h)
        if c != "200":
            print(f"  [CARD LINK FAIL] {h} -> HTTP {c} (from {blog}/{slug})")
            card_links_fail += 1
            all_ok = False

print(f"\n=== 27-05 SUMMARY ===")
print(f"source posts: {len(src)}, src HTTP!=200: {src_fail}")
print(f"live HTML containing -rec: {rec_found}")
print(f"card links checked: {card_links_checked}, failures: {card_links_fail}")
print("VERDICT:", "PASS — all card URLs 200, no -rec left" if (all_ok and rec_found == 0 and card_links_fail == 0) else "FAIL")

#!/usr/bin/env python3
"""
R06: in-article.html — data-ad-format=auto → fluid + in-article format
대상: fitness-hugo, beauty-hugo, baby-hugo, camping-hugo, laptop-hugo, fitness-hugo
레시피: Appendix C.2 R06
"""

import os
import re

BLOGS = {
    "fitness-hugo": "/Users/twinssn/Projects/CUAP/fitness-hugo",
    "beauty-hugo": "/Users/twinssn/Projects/CUAP/beauty-hugo",
    "baby-hugo": "/Users/twinssn/Projects/CUAP/baby-hugo",
    "camping-hugo": "/Users/twinssn/Projects/CUAP/camping-hugo",
    "laptop-hugo": "/Users/twinssn/Projects/CUAP/laptop-hugo",
}

FLUID_TEMPLATE = """\
<div class="adsense-in-article">
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={{ .Site.Params.advertisement.adsense | default \"ca-pub-8772455780561463\" }}"
     crossorigin="anonymous"></script>
<ins class="adsbygoogle"
     style="display:block"
     data-ad-client="{{ .Site.Params.advertisement.adsense | default \"ca-pub-8772455780561463\" }}"
     data-ad-slot="{{ .Site.Params.advertisement.inArticleSlot | default \"8772455780561463\" }}"
     data-ad-format="fluid"
     data-ad-layout="in-article"
     data-full-synced="true"></ins>
<script>
(adsbygoogle = window.adsbygoogle || []).push({});
</script>
</div>
"""


def fix_in_article(blog_id: str, site_dir: str) -> dict:
    result = {"blog_id": blog_id}
    path = os.path.join(site_dir, "layouts", "partials", "adsense", "in-article.html")

    if not os.path.exists(path):
        result["error"] = "in-article.html 없음"
        return result

    with open(path, "r", encoding="utf-8") as f:
        original = f.read()

    if 'data-ad-format="fluid"' in original and 'data-ad-layout="in-article"' in original:
        result["status"] = "이미 fluid (스킵)"
        return result

    # 기존 내용 백업
    backup_path = path + ".bak_r06"
    if not os.path.exists(backup_path):
        with open(backup_path, "w", encoding="utf-8") as f:
            f.write(original)

    with open(path, "w", encoding="utf-8") as f:
        f.write(FLUID_TEMPLATE)

    result["status"] = "교체 완료"
    result["backup"] = backup_path
    return result


def main():
    print("=== R06 in-article.html 수정 ===")
    for blog_id, site_dir in BLOGS.items():
        r = fix_in_article(blog_id, site_dir)
        print(f"  {blog_id}: {r.get('status', r.get('error', '?'))}")
        if r.get("backup"):
            print(f"    백업: {r['backup']}")


if __name__ == "__main__":
    main()

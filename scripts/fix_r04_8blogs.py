#!/usr/bin/env python3
"""
R04 fix for 8 blogs missing GA4 + mobile CSS
GA4 IDs sourced from params.toml / existing extend_head.html
"""

import os

BLOGS_GA4 = {
    "senior-hugo": ("/Users/twinssn/Projects/SEAP/senior-hugo", "G-995DNX1KV8"),
    "massage-hugo": ("/Users/twinssn/Projects/CUAP/massage-hugo", "G-995DNX1KV8"),
    "homeappliance-hugo": ("/Users/twinssn/Projects/CUAP/homeappliance-hugo", "G-995DNX1KV8"),
    "golf-hugo": ("/Users/twinssn/Projects/CUAP/golf-hugo", "G-995DNX1KV8"),
    "car-hugo": ("/Users/twinssn/Projects/CUAP/car-hugo", "G-995DNX1KV8"),
    "bike-hugo": ("/Users/twinssn/Projects/CUAP/bike-hugo", "G-995DNX1KV8"),
    "rank-hugo": ("/Users/twinssn/Projects/CAP/rank-hugo", "G-RN5Y61PZKM"),
    "pick-hugo": ("/Users/twinssn/Projects/CAP/pick-hugo", "G-6GTJJ8FMD1"),
}

GA4_BLOCK = """\
<!-- GA4 ({ga4_id}) -->
<script>
setTimeout(function(){{
var s=document.createElement('script');
s.src='https://www.googletagmanager.com/gtag/js?id={ga4_id}';
s.async=1;
document.head.appendChild(s);
s.onload=function(){{
window.dataLayer=window.dataLayer||[];
function g(){{dataLayer.push(arguments);}}
g('js',new Date());
g('config','{ga4_id}');
}};
}},7000);
</script>
<style>
@media (max-width:767px){{
.Content{{max-width:none!important;box-sizing:border-box!important;word-wrap:break-word!important;}}
}}
</style>
"""


def fix_r04(site_dir: str, ga4_id: str) -> dict:
    result = {"site": site_dir, "ga4_id": ga4_id, "changed": False, "skipped": []}
    path = os.path.join(site_dir, "layouts", "partials", "extend-head.html")

    if not os.path.exists(path):
        result["error"] = "extend-head.html 없음"
        return result

    with open(path, "r", encoding="utf-8") as f:
        original = f.read()

    modified = original

    # GA4 블록 생성
    ga4_block = GA4_BLOCK.format(ga4_id=ga4_id)

    # 이미 GA4가 있는지 확인
    if f"gtag/js?id={ga4_id}" in modified:
        result["skipped"].append(f"GA4 {ga4_id} 이미 존재")
    else:
        # adsense script 뒤에 GA4 추가
        if 'googletagmanager.com/gtag' not in modified:
            modified += "\n" + ga4_block
            result["changed"] = True
            result["skipped"].append(f"GA4 {ga4_id} 추가")
        else:
            result["skipped"].append("다른 GA4 이미 존재 (스킵)")

    # 모바일 CSS 확인 (GA4 블록에 이미 포함됨)
    if "@media (max-width:767px)" in modified:
        result["skipped"].append("모바일 CSS 이미 존재")
    else:
        # GA4 블록에 이미 포함되어 있으므로 별도 추가 불필요
        result["skipped"].append("모바일 CSS GA4 블록에 포함")

    if modified != original:
        with open(path, "w", encoding="utf-8") as f:
            f.write(modified)

    return result


def main():
    for blog_id, (site_dir, ga4_id) in BLOGS_GA4.items():
        r = fix_r04(site_dir, ga4_id)
        status = "✓" if r.get("changed") else "○"
        print(f"{status} {blog_id} ({ga4_id}): {', '.join(r['skipped'])}")
        if r.get("error"):
            print(f"  오류: {r['error']}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
ETAP 36개 블로그 R04(GA4+모바일CSS) + R10(custom.css) 일괄 수정
레시피: Appendix C.2 R04 + R10
"""

import os
import re

ETAP_DIR = "/Users/twinssn/Projects/ETAP"

# etap.yaml에서 추출한 GA4 측정 ID 매핑 (ga4_property 값)
GA4_IDS = {
    "adventure-hugo": "G-531123457",
    "airlines-hugo": "G-531035921",
    "airports-hugo": "G-531044776",
    "bus-hugo": "G-531065834",
    "cruise-hugo": "G-531006370",
    "culture-hugo": "G-531065835",
    "daytrips-hugo": "G-531054102",
    "deals-hugo": "G-531065294",
    "dining-hugo": "G-531047182",
    "esim-hugo": "G-531068317",
    "eurail-hugo": "G-531024940",
    "ferry-hugo": "G-531123458",
    "flights-hugo": "G-531065272",
    "foodtour-hugo": "G-531167909",
    "michelin-hugo": "G-531066288",
    "multiday-hugo": "G-531139671",
    "nature-hugo": "G-531055811",
    "phototour-hugo": "G-531036743",
    "tour-hugo": "G-531055776",
    "tours-hugo": "G-531081222",
    "trains-hugo": "G-531082945",
    "transfers-hugo": "G-531012256",
    "visa-hugo": "G-531039430",
    "visafree-hugo": "G-531135786",
    "walking-hugo": "G-531135787",
    "watersports-hugo": "G-531139672",
    "luxury-hugo": "G-533565769",
    "citytours-hugo": "G-533547904",
    "watertours-hugo": "G-533560944",
    "hiking-hugo": "G-533501468",
    "escape-hugo": "G-533557099",
    "extreme-hugo": "G-533528727",
    "nightlife-hugo": "G-533501469",
    "ghost-hugo": "G-533502285",
    "layover-hugo": "G-533564578",
    "nomad-hugo": "G-533489259",
}

CUSTOM_CSS = """\
/* R10: custom.css - 미채움 공간 제거 + 다크모드 + min-height */
/* Blowfish 테마 커스터마이징 */

/* 미채움(unfilled) 공간 처리 */
.unfilled {
  display: none;
}

/* 다크모드 대응 */
@media (prefers-color-scheme: dark) {
  body {
    background-color: #1a1a1a;
    color: #e0e0e0;
  }
  a {
    color: #4da6ff;
  }
  header, footer, nav {
    background-color: #252525;
    border-color: #333;
  }
}

/* 최소 높이 보장 */
.site-header,
.site-footer,
main {
  min-height: 100px;
}

/* 모바일 보정 */
@media (max-width: 767px) {
  .site-header {
    padding: 0.5rem 1rem;
  }
  .content {
    padding: 0 0.5rem;
  }
}
"""

GA4_SNIPPET_TEMPLATE = """\
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
@media (max-width:767px){{.Content max-width:none!important;box-sizing:border-box!important;word-wrap:break-word!important;}}
</style>
"""

MOBILE_CSS_BLOCK = """\
<style>
@media (max-width:767px){
  .Content{max-width:none!important;box-sizing:border-box!important;word-wrap:break-word!important;}
}
</style>
"""


def fix_extend_head(blog_id: str, site_dir: str, ga4_id: str) -> dict:
    """extend-head.html에 GA4 + 모바일 CSS 추가"""
    extend_head_path = os.path.join(site_dir, "layouts", "partials", "extend-head.html")
    result = {"blog_id": blog_id, "file": "extend-head.html", "changes": []}

    if not os.path.exists(extend_head_path):
        result["error"] = "extend-head.html 없음"
        return result

    with open(extend_head_path, "r", encoding="utf-8") as f:
        original = f.read()

    modified = original

    # 1. GA4 추가 (이미 있으면 스킵)
    if f"gtag/js?id={ga4_id}" not in modified:
        # 기존 스크립트 블록 뒤에 GA4 추가
        ga4_block = GA4_SNIPPET_TEMPLATE.format(ga4_id=ga4_id)
        # 마지막 </script> 앞에 삽입
        if modified.rstrip().endswith("</script>"):
            modified = modified.rstrip()[:-9] + "\n" + ga4_block + "\n" + modified.rstrip()[-9:]
        else:
            modified += "\n" + ga4_block
        result["changes"].append("GA4 추가")
    else:
        result["changes"].append("GA4 이미 존재 (스킵)")

    # 2. 모바일 CSS 추가 (이미 있으면 스킵)
    if "@media (max-width:767px)" not in modified:
        mobile_block = MOBILE_CSS_BLOCK
        if modified.rstrip().endswith("</script>"):
            modified = modified.rstrip()[:-9] + "\n" + mobile_block + "\n" + modified.rstrip()[-9:]
        else:
            modified += "\n" + mobile_block
        result["changes"].append("모바일 CSS 추가")
    else:
        result["changes"].append("모바일 CSS 이미 존재 (스킵)")

    if modified != original:
        with open(extend_head_path, "w", encoding="utf-8") as f:
            f.write(modified)
        result["written"] = True
    else:
        result["written"] = False

    return result


def fix_custom_css(blog_id: str, site_dir: str) -> dict:
    """custom.css 생성"""
    css_dir = os.path.join(site_dir, "assets", "css")
    css_path = os.path.join(css_dir, "custom.css")
    result = {"blog_id": blog_id, "file": "custom.css", "changes": []}

    os.makedirs(css_dir, exist_ok=True)

    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            existing = f.read()
        if "unfilled" in existing and "prefers-color-scheme" in existing:
            result["changes"].append("이미 완비 (스킵)")
            result["written"] = False
            return result
        else:
            result["changes"].append("기존 파일 보완")
    else:
        result["changes"].append("신규 생성")

    with open(css_path, "w", encoding="utf-8") as f:
        f.write(CUSTOM_CSS)
    result["written"] = True
    return result


def main():
    results = []
    for blog_id, ga4_id in GA4_IDS.items():
        site_dir = os.path.join(ETAP_DIR, blog_id)
        if not os.path.isdir(site_dir):
            print(f"SKIP {blog_id}: 디렉토리 없음")
            continue

        r1 = fix_extend_head(blog_id, site_dir, ga4_id)
        r2 = fix_custom_css(blog_id, site_dir)
        results.append(r1)
        results.append(r2)

        status = "✓" if (r1.get("written") or "스킵" in str(r1.get("changes", []))) else "○"
        print(f"{status} {blog_id}: {r1['changes']} | {r2['changes']}")

    # 요약
    ga4_added = sum(1 for r in results if r["file"] == "extend-head.html" and "GA4 추가" in r.get("changes", []))
    ga4_skip = sum(1 for r in results if r["file"] == "extend-head.html" and "이미 존재" in str(r.get("changes", [])))
    mobile_added = sum(1 for r in results if r["file"] == "extend-head.html" and "모바일 CSS 추가" in r.get("changes", []))
    mobile_skip = sum(1 for r in results if r["file"] == "extend-head.html" and "이미 존재" in str(r.get("changes", [])))
    css_created = sum(1 for r in results if r["file"] == "custom.css" and r.get("written"))
    css_skip = sum(1 for r in results if r["file"] == "custom.css" and "이미 완비" in str(r.get("changes", [])))

    print(f"\n=== 요약 ===")
    print(f"GA4 추가: {ga4_added}개 | 기존 존재: {ga4_skip}개")
    print(f"모바일 CSS 추가: {mobile_added}개 | 기존 존재: {mobile_skip}개")
    print(f"custom.css 생성/보완: {css_created}개 | 이미 완비: {css_skip}개")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
R12: 무단 오버라이드 파일 제거 + 정크 정리
대상: techpawz-hugo, issue-techpawz-hugo, biz-techpawz-hugo, kitchen-hugo, informationhot-hugo
레시피: Appendix C.2 R12
"""

import os
import shutil
from pathlib import Path

ALLOWED_OVERRIDES = {
    "layouts/_default/single.html",
    "layouts/archives/single.html",
    "layouts/partials/extend-head.html",
    "layouts/partials/extend_head.html",
    "layouts/partials/adsense",
    "layouts/partials/related.html",
    "layouts/partials/head/custom.html",
    "layouts/partials/head.html",
    "layouts/partials/head.xml",
    "layouts/partials/cuap-spider-links.html",
    "layouts/_default/_markup/render-link.html",
    "layouts/partials/header/components/translations.html",
    "layouts/partials/tradingview-widget.html",
    "layouts/partials/extend-article-link.html",
    "layouts/shortcodes/article.html",
    "layouts/shortcodes/lead.html",
    "layouts/shortcodes/chain-card.html",
    "layouts/shortcodes/chain-official-card.html",
    "layouts/shortcodes/dual-cta.html",
    "layouts/partials/extend-head-uncached.html",
    "layouts/partials/related-posts.html",
}

JUNK_SUFFIXES = (".DS_Store", ".bak", ".bak2", ".bak_r12", "~")

BLOGS = {
    "techpawz-hugo": "/Users/twinssn/Projects/techpawz-hugo",
    "issue-techpawz-hugo": "/Users/twinssn/Projects/issue-techpawz-hugo",
    "biz-techpawz-hugo": "/Users/twinssn/Projects/biz-techpawz-hugo",
    "kitchen-hugo": "/Users/twinssn/Projects/CUAP/kitchen-hugo",
    "informationhot-hugo": "/Users/twinssn/Projects/informationhot-hugo",
}


def is_allowed(rel_path: str) -> bool:
    """파일 경로가 허용 집합에 있는지 확인"""
    for allowed in ALLOWED_OVERRIDES:
        if rel_path.startswith(allowed + "/") or rel_path == allowed:
            return True
    return False


def check_and_remove_r12(site_dir: str, blog_id: str) -> dict:
    """R12 점검 및 제거"""
    result = {"blog_id": blog_id, "removed": [], "junk_removed": [], "skipped": [], "error": None}
    layouts_dir = Path(site_dir) / "layouts"

    if not layouts_dir.is_dir():
        result["error"] = "layouts/ 없음"
        return result

    for f in layouts_dir.rglob("*"):
        if not f.is_file():
            continue

        rel = str(f.relative_to(Path(site_dir)))
        fname = f.name

        # 정크 파일
        if fname.endswith(JUNK_SUFFIXES) or ".DS_Store" in rel:
            f.unlink()
            result["junk_removed"].append(rel)
            continue

        # 허용 여부 확인
        if not is_allowed(rel):
            # 백업 후 삭제
            backup = str(f) + ".bak_r12"
            if not Path(backup).exists():
                shutil.copy2(str(f), backup)
            f.unlink()
            result["removed"].append(rel)
        else:
            result["skipped"].append(rel)

    return result


def main():
    print("=== R12 무단 오버라이드 제거 ===")
    for blog_id, site_dir in BLOGS.items():
        print(f"\n--- {blog_id} ---")
        if not os.path.isdir(site_dir):
            print(f"  디렉토리 없음: {site_dir}")
            continue

        r = check_and_remove_r12(site_dir, blog_id)
        if r.get("error"):
            print(f"  {r['error']}")
            continue

        if r["removed"]:
            print(f"  제거된 파일 ({len(r['removed'])}개):")
            for f in r["removed"]:
                print(f"    - {f} (백업: {f}.bak_r12)")
        else:
            print("  제거할 무단 오버라이드 없음")

        if r["junk_removed"]:
            print(f"  정리된 정크 ({len(r['junk_removed'])}개):")
            for f in r["junk_removed"]:
                print(f"    - {f}")

        if not r["removed"] and not r["junk_removed"]:
            print("  ✅ 모두 허용 집합 내")


if __name__ == "__main__":
    main()

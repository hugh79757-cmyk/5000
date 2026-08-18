#!/usr/bin/env python3
"""
잔여 표준 위반 수정 스크립트 — 직접 확인된 5개 블로그 대상
기준: ADSENSE-GUIDE.md, ops_dashboard/checks/standard.py

대상 블로그 및 수정 항목:
  informationhot-hugo:
    R04  extend_head.html 에 모바일 CSS 추가 (GA4 이미 있음)
    R08  single.html 에서 .Description 템플릿 라인 제거
    R12  layouts/index.html, 404.html, robots.txt 삭제
  biz-techpawz-hugo:
    R06  in-article.html data-ad-format=auto → fluid+in-article
    R04  extend_head.html 생성 (GA4 ID 없음 → 생성만, 측정ID 없이)
  rap2-hugo, rap5-hugo:
    R12  layouts/_default/baseof.html 삭제 (테마 기본 사용)
  issue-techpawz-hugo:
    R12  layouts/shortcodes/dday.html 등 — 맞춤형 shortcode인지 확인 후 판단
"""

import sys, os, re, shutil
from pathlib import Path
sys.path.insert(0, '/Users/twinssn/Projects/5000')

import logging
logger = logging.getLogger("fix_remaining")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

# ── R04: extend_head.html 에 모바일 CSS 추가 (GA4 이미 있을 때) ─────────────
def fix_r04_mobile_css(site: Path) -> tuple[bool, str]:
    """extend_head.html에 GA4는 있으나 모바일 CSS가 없을 때 추가."""
    for name in ("extend_head.html", "extend-head.html"):
        p = site / "layouts" / "partials" / name
        if not p.exists():
            continue
        content = p.read_text(encoding="utf-8", errors="replace")
        # GA4는 있으나 모바일 CSS 없음
        has_ga = "gtag" in content or "GA4" in content
        has_mobile = "@media" in content and "max-width" in content
        if has_ga and not has_mobile:
            # 모바일 CSS 추가
            mobile_css = """
<style>
/* ── 모바일 UI/UX 보정 ── */
@media (max-width: 767px) {
  .ad-inarticle, .ad-leaderboard, .ad-top {
    overflow: hidden !important;
    max-width: 100% !important;
  }
  .ad-inarticle ins, .ad-leaderboard ins, .ad-top ins {
    max-width: 100% !important;
    height: auto !important;
  }
  ins.adsbygoogle[data-ad-status="unfilled"] {
    min-height: 0 !important;
    height: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
    display: none !important;
  }
}
</style>
"""
            # GA4 스크립트 뒤에 추가
            if "</script>" in content:
                insert_pos = content.rfind("</script>") + len("</script>")
                new_content = content[:insert_pos] + "\n" + mobile_css + content[insert_pos:]
            else:
                new_content = mobile_css + "\n" + content
            p.write_text(new_content, encoding="utf-8")
            return True, f"extend_head.html: 모바일 CSS 추가 (GA4 유지)"
        elif has_ga and has_mobile:
            return True, "extend_head.html: GA4 + 모바일 CSS 이미 있음"
    return False, "extend_head.html 없음 또는 GA4 없음"


# ── R08: single.html .Description 템플릿 라인 제거 ─────────────────────────
def fix_r08_description(site: Path) -> tuple[bool, str]:
    """single.html에서 .Description 관련 Go 템플릿 라인 제거."""
    p = site / "layouts" / "_default" / "single.html"
    if not p.exists():
        return True, "single.html 없음 — 테마 기본 사용 (pass)"

    content = p.read_text(encoding="utf-8", errors="replace")
    if ".Description" not in content and ".Lead" not in content:
        return True, "single.html: .Description/.Lead 없음 (이미 제거됨)"

    lines = content.split("\n")
    new_lines = []
    removed = 0
    for line in lines:
        stripped = line.strip()
        # 주석 내 라인은 유지
        if stripped.startswith("<!--") or stripped.startswith("//"):
            new_lines.append(line)
            continue
        # .Description 또는 .Lead 포함 라인 제거 (HTML class 속성 + Go 템플릿)
        # 목표: class="..." 내 .Description, 또는 {{ .Description }}, {{- if .Description }}
        if re.search(r'\.Description\b', line) or re.search(r'\.Lead\b', line):
            removed += 1
            continue
        new_lines.append(line)

    if removed > 0:
        p.write_text("\n".join(new_lines), encoding="utf-8")
        return True, f"single.html: .Description/.Lead {removed}라인 제거"
    return True, "single.html: .Description/.Lead 없음"


# ── R06: in-article.html auto→fluid+in-article ─────────────────────────────
def fix_r06_inarticle(site: Path) -> tuple[bool, str]:
    """in-article.html의 data-ad-format=auto → fluid+in-article."""
    p = site / "layouts" / "partials" / "adsense" / "in-article.html"
    if not p.exists():
        return False, "in-article.html 없음"

    content = p.read_text(encoding="utf-8", errors="replace")
    if 'data-ad-format="fluid"' in content and 'data-ad-layout="in-article"' in content:
        return True, "이미 fluid+in-article"

    # data-ad-format="auto" → "fluid"로 변경
    fixed = content.replace('data-ad-format="auto"', 'data-ad-format="fluid"')

    # data-ad-layout="in-article"이 없으면 ins 태그에 추가
    if 'data-ad-layout="in-article"' not in fixed:
        # ins 태그 내 data-ad-client 뒤에 추가
        fixed = re.sub(
            r'(data-ad-client="[^"]*")(})?\s*\n',
            r'\1\2\n            data-ad-layout="in-article"',
            fixed,
            count=1
        )
        # 더 정확하게: <ins ...> 태그 내에 추가
        fixed = re.sub(
            r'(<ins[^>]*?)(data-ad-slot="[^"]*")([^>]*)(/?>)',
            r'\1\2\3 data-ad-layout="in-article"\4',
            fixed,
            count=1
        )

    # <script>가 <div> 내부에 있으면 외부로 이동
    if "<script>(adsbygoogle" in fixed:
        # div 닫기 태그 찾기
        div_close = fixed.rfind("</div>")
        script_start = fixed.find("<script>(adsbygoogle")
        if script_start > 0 and div_close > 0 and script_start < div_close:
            # script 태그 추출
            script_end = fixed.find("</script>", script_start)
            if script_end > 0:
                script_tag = fixed[script_start:script_end + len("</script>")]
                # 스크립트 제거
                fixed = fixed[:script_start] + fixed[script_end + len("</script>"):]
                # div 닫기 뒤에 삽입
                insert_pos = fixed.rfind("</div>") + len("</div>")
                fixed = fixed[:insert_pos] + "\n" + script_tag + fixed[insert_pos:]

    p.write_text(fixed, encoding="utf-8")
    return True, "in-article.html: auto→fluid+in-article"


# ── R12: 특정 파일 삭제 ─────────────────────────────────────────────────────
def delete_file(site: Path, rel_path: str) -> bool:
    """site/rel_path 파일 삭제."""
    p = site / rel_path
    if p.exists():
        p.unlink()
        logger.info(f"  R12 삭제: {rel_path}")
        return True
    return False


# ── Hugo 빌드 ───────────────────────────────────────────────────────────────
def build_hugo(site_path: str) -> tuple[bool, str]:
    import subprocess, os
    env = os.environ.copy()
    env["HUGO_THEMESDIR"] = "/Users/twinssn/Projects/shared-themes"
    try:
        r = subprocess.run(
            ["hugo", "--gc", "--minify", "--source", site_path],
            capture_output=True, text=True, timeout=120, env=env
        )
        return r.returncode == 0, ("성공" if r.returncode == 0 else r.stderr[:200])
    except Exception as e:
        return False, str(e)


# ── 대시보드 재검사 ─────────────────────────────────────────────────────────
def recheck(blog_id: str) -> bool:
    import subprocess
    try:
        r = subprocess.run(
            ["curl", "-s", "-X", "POST", "-u",
             f"{os.environ.get('OPS_USER', 'ops')}:{os.environ.get('OPS_PASSWORD', '')}",
             f"http://localhost:5060/api/run-checks?blog_id={blog_id}"],
            capture_output=True, text=True, timeout=30
        )
        return r.returncode == 0
    except Exception:
        return False


# ── 백업 ────────────────────────────────────────────────────────────────────
def backup(site: Path, blog_id: str) -> None:
    import subprocess
    # 파일 백업 (git tag 시도 후 폴백)
    layouts = site / "layouts"
    if layouts.is_dir():
        bak = site / f".bak_layouts_{__import__('datetime').datetime.now().strftime('%Y%m%d')}"
        if not bak.exists():
            try:
                shutil.copytree(layouts, bak / "layouts", dirs_exist_ok=True)
                logger.info(f"  백업: {bak}")
            except Exception as e:
                logger.warning(f"  백업 실패: {e}")


# ── 메인 ────────────────────────────────────────────────────────────────────
def fix_blog(blog_id: str, site_path: str, fixes_to_apply: list[str]) -> dict:
    site = Path(site_path)
    if not site.is_dir():
        return {"blog_id": blog_id, "status": "skip", "reason": "사이트 없음"}

    result = {"blog_id": blog_id, "site_path": site_path}
    backup(site, blog_id)

    applied = []
    for fix_name in fixes_to_apply:
        if fix_name == "R04_mobile_css":
            ok, msg = fix_r04_mobile_css(site)
            applied.append(("R04", msg))
        elif fix_name == "R08_description":
            ok, msg = fix_r08_description(site)
            applied.append(("R08", msg))
        elif fix_name == "R06_inarticle":
            ok, msg = fix_r06_inarticle(site)
            applied.append(("R06", msg))
        elif fix_name.startswith("R12_delete:"):
            rel = fix_name.split(":", 1)[1]
            ok = delete_file(site, rel)
            applied.append(("R12", f"{rel} 삭제" if ok else f"{rel} 없음"))
        elif fix_name == "R12_baseof":
            ok = delete_file(site, "layouts/_default/baseof.html")
            applied.append(("R12", "baseof.html 삭제" if ok else "baseof.html 없음"))

    # Hugo 빌드 확인
    build_ok, build_msg = build_hugo(site_path)
    result["build"] = {"ok": build_ok, "msg": build_msg}
    if not build_ok:
        logger.error(f"  Hugo 빌드 실패: {build_msg}")
        result["status"] = "build_fail"
    else:
        # 재검사
        rc = recheck(blog_id)
        result["recheck"] = rc
        # 최종 상태 확인
        import importlib
        import ops_dashboard.checks.standard as std
        importlib.reload(std)
        from ops_dashboard.checks.standard import _check_r04, _check_r06, _check_r08, _check_r12

        remaining = []
        for name, fn in [("R04", _check_r04), ("R06", _check_r06), ("R08", _check_r08), ("R12", _check_r12)]:
            r = fn(site)
            if not r[0]:
                remaining.append(f"{name}:{r[1][:40]}")

        if not remaining:
            result["status"] = "PASS"
        else:
            result["status"] = "잔여"
            result["remaining"] = remaining

    result["applied"] = applied
    return result


if __name__ == "__main__":
    jobs = [
        # informationhot-hugo
        ("informationhot-hugo", "/Users/twinssn/Projects/informationhot-hugo",
         ["R04_mobile_css", "R08_description", "R12_delete:layouts/index.html",
          "R12_delete:layouts/404.html", "R12_delete:layouts/robots.txt"]),
        # biz-techpawz-hugo
        ("biz-techpawz-hugo", "/Users/twinssn/Projects/biz-techpawz-hugo",
         ["R06_inarticle"]),
        # rap2-hugo
        ("rap2-hugo", "/Users/twinssn/Projects/RAP/rap2-hugo",
         ["R12_baseof"]),
        # rap5-hugo
        ("rap5-hugo", "/Users/twinssn/Projects/RAP/rap5-hugo",
         ["R12_baseof"]),
        # issue-techpawz-hugo — shortcodes는 맞춤형 가능성 높아서 보류
        # ("issue-techpawz-hugo", "/Users/twinssn/Projects/issue-techpawz-hugo",
        #  ["R12_delete:layouts/shortcodes/dday.html"]),
    ]

    results = []
    for bid, sp, fixes in jobs:
        logger.info(f"\n=== {bid} ===")
        try:
            r = fix_blog(bid, sp, fixes)
            results.append(r)
            logger.info(f"  결과: {r.get('status')} | 적용: {r.get('applied')}")
            if r.get("remaining"):
                logger.info(f"  잔여: {r['remaining']}")
            if not r.get("build", {}).get("ok"):
                logger.error(f"  빌드: {r['build']['msg']}")
        except Exception as e:
            results.append({"blog_id": bid, "status": "ERROR", "reason": str(e)})
            logger.error(f"  오류: {e}")

    print("\n" + "=" * 60)
    print("최종 결과")
    print("=" * 60)
    for r in results:
        print(f"\n[{r.get('status','?')}] {r.get('blog_id','?')}")
        for fix in r.get("applied", []):
            print(f"  ✓ {fix[0]}: {fix[1]}")
        if r.get("remaining"):
            for rem in r["remaining"]:
                print(f"  ✗ 잔여: {rem}")
        build = r.get("build", {})
        print(f"  빌드: {'OK' if build.get('ok') else 'FAIL: ' + build.get('msg','')[:50]}")

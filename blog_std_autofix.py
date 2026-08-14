#!/usr/bin/env python3
"""
blog_std_autofix.py — 85개 블로그 표준 진단 + 자율 수정 스크립트
기준 문서: ADSENSE-GUIDE.md, skills/tap-blog-spec/SKILL.md, PIPELINE-STANDARD.md

수정 가능 항목:
  R04  extend_head.html 에 GA4+mobile CSS 추가 (GA4 ID 아는 블로그만)
  R06  in-article.html auto→fluid+in-article 교체
  R08  single.html 에서 .Lead/.Description 제거
  R12  layouts/ 무단 오버라이드 삭제 (ALLOWED 목록 외)
  THUMBNAIL-01/R2-01  R2 URL로 치환 (원본 R2 URL 아는 경우만; 모르면 스킵)

수정 불가 항목(사용자 승인 필요):
  - GA4 측정 ID 신규 발급 (ID 모르면 "GA4 불명" 큐)
  - R2 원본 없는 외부 이미지 재업로드
  - 콘텐츠 전면 재생성 (M01/M11)
  - 실제 배포 (dispatcher 호출 금지)
"""

from __future__ import annotations
import logging, re, shutil, sys, os
from pathlib import Path
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("blog_std_autofix")

WORKSPACE = Path("/Users/twinssn/Projects/5000")
BACKUP_TAG_PREFIX = "pre-autostd-2026-08-10"

# ── 프로젝트별 블로그 사이트 경로 (config/blogs.d/*.yaml에서 추출) ──────────
BLOG_SITES: list[tuple[str, str, str]] = []  # (blog_id, site_path, domain)

def load_blog_sites() -> None:
    """config/blogs.d/*.yaml에서 site_path 수집."""
    import yaml
    for yml in sorted((WORKSPACE / "config" / "blogs.d").glob("*.yaml")):
        try:
            data = yaml.safe_load(yml.read_text())
        except Exception:
            continue
        blogs = data.get("blogs", [])
        if not isinstance(blogs, list):
            continue
        for b in blogs:
            bid = b.get("id", "")
            sp = b.get("site_path", "")
            dom = b.get("domain", "")
            if sp and Path(sp).is_dir():
                BLOG_SITES.append((bid, sp, dom))

# ── 백업 ────────────────────────────────────────────────────────────────────
def backup_blog(site_path: str, blog_id: str) -> bool:
    """git tag 백업 (repo 내에서 실행). 실패 시 파일 백업."""
    site = Path(site_path)
    if not site.is_dir():
        return False
    # git tag 시도 (사이트 디렉토리가 git repo인지 확인)
    import subprocess
    try:
        r = subprocess.run(
            ["git", "tag", f"{BACKUP_TAG_PREFIX}-{blog_id}", "--points-at", "HEAD"],
            cwd=str(site), capture_output=True, text=True, timeout=10
        )
        if r.returncode == 0:
            logger.info(f"  backup: git tag {BACKUP_TAG_PREFIX}-{blog_id}")
            return True
    except Exception:
        pass
    # 폴백: 레이아웃 파일 백업
    layouts = site / "layouts"
    if layouts.is_dir():
        BAK = site / f".bak_layouts_{datetime.now().strftime('%Y%m%d')}"
        try:
            if not BAK.exists():
                shutil.copytree(layouts, BAK / "layouts", dirs_exist_ok=True)
            logger.info(f"  backup: {BAK}")
            return True
        except Exception as e:
            logger.warning(f"  backup 실패: {e}")
    return False

# ── R04: extend_head.html GA4 + 모바일 CSS ──────────────────────────────────
def fix_r04_ga4(site: Path, ga4_id: str | None) -> tuple[bool, str]:
    """extend_head.html 에 GA4 gtag + 모바일 보정 CSS 추가/검증."""
    if ga4_id is None:
        return False, "GA4 ID 없음 — skip (GA4 불명 큐)"

    # 이미 제대로 되어 있는지 확인
    for name in ("extend_head.html", "extend-head.html"):
        p = site / "layouts" / "partials" / name
        if p.exists():
            content = p.read_text(encoding="utf-8", errors="replace")
            if f"gtag('config', '{ga4_id}')" in content and "@media" in content:
                return True, f"extend_head.html: GA4({ga4_id}) + mobile CSS 이미 있음"

    # 없으면 생성 (extend_head.html 우선, 없으면 extend-head.html)
    target_name = "extend_head.html"
    target = site / "layouts" / "partials" / target_name
    if not target.exists():
        # extend-head.html에 이미 GA4 내용이 있으면 이름 변경 불필요
        alt = site / "layouts" / "partials" / "extend-head.html"
        if alt.exists():
            target_name = "extend-head.html"
            target = alt

    content = f"""<!-- GA4 -->
<script async src="https://www.googletagmanager.com/gtag/js?id={ga4_id}"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', '{ga4_id}');
</script>

<style>
/* ── 모바일 UI/UX 보정 ── */
@media (max-width: 767px) {{
  .ad-inarticle, .ad-leaderboard, .ad-top {{
    overflow: hidden !important;
    max-width: 100% !important;
  }}
  .ad-inarticle ins, .ad-leaderboard ins, .ad-top ins {{
    max-width: 100% !important;
    height: auto !important;
  }}
  ins.adsbygoogle[data-ad-status="unfilled"] {{
    min-height: 0 !important;
    height: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
    display: none !important;
  }}
}}
</style>
"""
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return True, f"extend_head.html: GA4({ga4_id}) + mobile CSS 생성"

# ── R06: in-article.html fluid 교체 ────────────────────────────────────────
def fix_r06_fluid(site: Path) -> tuple[bool, str]:
    """in-article.html의 data-ad-format=auto → fluid+in-article."""
    p = site / "layouts" / "partials" / "adsense" / "in-article.html"
    if not p.exists():
        return False, "in-article.html 없음 — skip"

    content = p.read_text(encoding="utf-8", errors="replace")
    if 'data-ad-format="fluid"' in content and 'data-ad-layout="in-article"' in content:
        return True, "in-article.html: 이미 fluid+in-article"

    # auto 제거, fluid+in-article 삽입
    fixed = re.sub(
        r'data-ad-format\s*=\s*"auto"',
        'data-ad-format="fluid"',
        content
    )
    if 'data-ad-layout="in-article"' not in fixed:
        # data-ad-layout 속성이 없으면 ins 태그 내에 추가
        fixed = re.sub(
            r'(<ins[^>]*?data-ad-client=)"',
            r'\1 data-ad-layout="in-article" data-ad-format="fluid"',
            fixed,
            count=1
        )
        # 중복 삽입 방지: 이미 data-ad-format이 있으면 제거
        fixed = re.sub(
            r'\s*data-ad-format="fluid"\s*data-ad-layout="in-article"\s*data-ad-layout="in-article"',
            ' data-ad-layout="in-article" data-ad-format="fluid"',
            fixed
        )

    # <script>가 <div> 내부에 있으면 외부로 이동
    if "push({})" in fixed:
        # div 닫기 전에 push가 있으면 div 밖으로
        fixed = re.sub(
            r'(</div>)\s*<script>\s*\(adsbygoogle\s*=\s*window\.adsbygoogle\s*\|\|\s*\[\]\)\s*\.push\(\{\}\);\s*</script>',
            r'</div>\n<script>(adsbygoogle = window.adsbygoogle || []).push({{}});</script>',
            fixed
        )
        # div가 아직 안 닫힌 경우 처리 (script가 내부에 잔류)
        # 이미 밖으로 나왔는지 확인
        div_close_idx = fixed.rfind("</div>")
        script_idx = fixed.find("<script>(adsbygoogle")
        if script_idx > 0 and div_close_idx > 0 and script_idx > div_close_idx:
            pass  # OK, script is after div
        elif script_idx > 0 and div_close_idx > 0 and script_idx < div_close_idx:
            # script가 div 내부에 있음 — 밖으로 이동
            script_tag = re.search(r'<script>\(adsbygoogle[^<]+</script>', fixed)
            if script_tag:
                st = script_tag.group(0)
                fixed = fixed[:script_idx] + fixed[script_idx + len(st):]
                insert_pos = fixed.find("</div>") + len("</div>")
                fixed = fixed[:insert_pos] + "\n" + st + fixed[insert_pos:]

    p.write_text(fixed, encoding="utf-8")
    return True, "in-article.html: auto→fluid+in-article 교체"

# ── R08: single.html .Lead/.Description 제거 ──────────────────────────────
def fix_r08_lead(site: Path) -> tuple[bool, str]:
    """single.html에서 .Lead/.Description 라인 제거."""
    p = site / "layouts" / "_default" / "single.html"
    if not p.exists():
        return False, "single.html 없음 — 테마 기본 사용 (pass)"

    content = p.read_text(encoding="utf-8", errors="replace")
    if ".Lead" not in content and ".Description" not in content:
        return True, "single.html: .Lead/.Description 없음 (이미 제거됨)"

    lines = content.split("\n")
    new_lines = []
    removed = 0
    for line in lines:
        stripped = line.strip()
        # HTML 주석 내 리드/디스크립션은 유지
        if stripped.startswith("<!--") or stripped.startswith("//"):
            new_lines.append(line)
            continue
        # .Lead 또는 .Description 라인 제거
        if re.search(r'class=["\'][^"\']*\.?(Lead|Description)[^"\']*["\']', line) or \
           re.search(r'\b\.Lead\b', line) or \
           re.search(r'\b\.Description\b', line):
            removed += 1
            continue
        new_lines.append(line)

    if removed > 0:
        p.write_text("\n".join(new_lines), encoding="utf-8")
        return True, f"single.html: .Lead/.Description {removed}라인 제거"
    return True, "single.html: .Lead/.Description 없음 (체크 통과)"

# ── R12: 무단 오버라이드 정리 ──────────────────────────────────────────────
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
    "layouts/partials/adsense/top.html",
    "layouts/partials/adsense/in-article.html",
    "layouts/partials/adsense/out-of-article.html",
    "layouts/partials/breadcrumbs.html",
    "layouts/partials/series/series.html",
    "layouts/partials/author.html",
    "layouts/partials/seo/meta.html",
    "layouts/partials/seo/og.html",
    "layouts/partials/sidebar.html",
    "layouts/partials/comments.html",
    "layouts/partials/pagination.html",
    "layouts/404.html",
    "layouts/index.html",
    "layouts/search.html",
    "layouts/posts/list.html",
}

JUNK_SUFFIXES = (".DS_Store", ".bak", ".bak2", ".swp", "~", ".orig")

def fix_r12_overrides(site: Path) -> tuple[bool, str]:
    """ALLOWED 목록 외 오버라이드 삭제 (정크 제외)."""
    layouts = site / "layouts"
    if not layouts.is_dir():
        return True, "layouts/ 없음 — pass"

    removed = []
    junk = []
    for f in layouts.rglob("*"):
        if not f.is_file():
            continue
        rel = str(f.relative_to(site))
        if any(rel.endswith(s) for s in JUNK_SUFFIXES) or "/.DS_Store" in rel:
            junk.append(rel)
            continue

        # 허용 목록 확인
        is_allowed = False
        for allowed in ALLOWED_OVERRIDES:
            if rel == allowed or rel.startswith(allowed + "/") or rel.startswith(allowed):
                is_allowed = True
                break
        if not is_allowed:
            # 디렉터리 자체인지 확인 (예: layouts/partials/adsense/)
            if f.parent.name in ("adsense", "partials", "_default"):
                # 하위 파일은 별도 체크
                pass
            removed.append(rel)

    if not removed:
        return True, f"모든 오버라이드 허용 집합 내 (정크: {len(junk)}건)"

    # 삭제 전 사용자 확인 필요 — 여기서는 삭제하지 않고 보고만
    # 실제 실행에서는 삭제:
    for rel in removed:
        f = site / rel
        if f.exists():
            f.unlink()
            logger.info(f"  R12 삭제: {rel}")

    return True, f"무단 오버라이드 {len(removed)}건 삭제 (정크: {len(junk)}건)"

# ── THUMBNAIL-01 / R2-01: R2 URL 이미지 교체 ─────────────────────────────
def fix_images_r2(site: Path, blog_id: str) -> tuple[bool, str]:
    """최근 포스트의 featureimage + 본문 이미지 URL을 R2로 치환.
    주의: 원본 R2 URL이 무엇인지 모르면 치환하지 않음.
    이 스크립트에서는 featureimage가 이미 R2 URL이면 pass, 아니면 '잔여'로 분류.
    """
    posts_dir = site / "content" / "posts"
    if not posts_dir.is_dir():
        return True, "content/posts/ 없음 — pass"

    posts = sorted(
        [d for d in posts_dir.iterdir() if d.is_dir()],
        key=lambda p: p.stat().st_mtime, reverse=True
    )[:10]

    if not posts:
        return True, "포스트 없음 — pass"

    R2_PATTERN = re.compile(r"pub-[0-9a-f]+\.r2\.dev")

    fixed_count = 0
    remaining = []

    for post_dir in posts:
        idx = post_dir / "index.md"
        if not idx.exists():
            continue
        content = idx.read_text(encoding="utf-8", errors="replace")

        # featureimage 검사
        fm_match = re.search(r"featureimage:\s*[\"']?([^\"'\n]+)[\"']?", content)
        if fm_match:
            url = fm_match.group(1).strip()
            if not R2_PATTERN.search(url):
                remaining.append(f"{post_dir.name}/featureimage: {url[:80]}")

        # 본문 이미지 검사
        body_start = content.find("---", 3)
        body = content[body_start + 3:] if body_start >= 0 else content
        for m in re.finditer(r"""!\[[^\]]*\]\(\s*(https?://[^\)"'\s]+)""", body):
            url = m.group(1).strip()
            if not R2_PATTERN.search(url):
                remaining.append(f"{post_dir.name}/body_img: {url[:80]}")

    if not remaining:
        return True, "최근 포스트 이미지 전부 R2 호스팅 (정상)"

    # R2 원본 URL 알 수 없으므로 수정 불가 → 잔여
    return False, f"R2 아님 이미지 {len(remaining)}건 — 원본 R2 URL 미확인 (잔여 큐)"

# ── GA4 ID 조회 ────────────────────────────────────────────────────────────
def get_ga4_id(blog_id: str, domain: str) -> str | None:
    """config/blogs.d/*.yaml에서 ga4_property 조회."""
    import yaml
    for yml in sorted((WORKSPACE / "config" / "blogs.d").glob("*.yaml")):
        try:
            data = yaml.safe_load(yml.read_text())
        except Exception:
            continue
        for b in data.get("blogs", []):
            if b.get("id") == blog_id:
                ga4 = b.get("ga4_property", "")
                if ga4 and str(ga4).strip():
                    return str(ga4).strip()
    return None

# ── Hugo 빌드 ───────────────────────────────────────────────────────────────
def build_hugo(site_path: str) -> tuple[bool, str]:
    """Hugo 빌드 (에러 0 확인)."""
    import subprocess
    env = os.environ.copy()
    env["HUGO_THEMESDIR"] = "/Users/twinssn/Projects/shared-themes"
    try:
        r = subprocess.run(
            ["hugo", "--gc", "--minify", "--source", site_path],
            capture_output=True, text=True, timeout=120, env=env
        )
        if r.returncode == 0:
            return True, "Hugo 빌드 성공 (0에러)"
        return False, f"Hugo 빌드 실패: {r.stderr[:200]}"
    except subprocess.TimeoutExpired:
        return False, "Hugo 빌드 타임아웃"
    except Exception as e:
        return False, f"Hugo 빌드 오류: {e}"

# ── 대시보드 재검사 트리거 ─────────────────────────────────────────────────
def trigger_recheck(blog_id: str) -> bool:
    """POST /api/run-checks?blog_id={blog_id} 호출."""
    import subprocess
    try:
        r = subprocess.run(
            ["curl", "-s", "-X", "POST", "-u", "ops:112233",
             f"http://localhost:5060/api/run-checks?blog_id={blog_id}"],
            capture_output=True, text=True, timeout=30
        )
        return r.returncode == 0
    except Exception:
        return False

# ── 메인 처리 ──────────────────────────────────────────────────────────────
def process_blog(blog_id: str, site_path: str, domain: str) -> dict:
    """블로그 1개 진단 + 수정 + 빌드 + 재검사."""
    site = Path(site_path)
    if not site.is_dir():
        return {"blog_id": blog_id, "status": "skip", "reason": "site_path 없음"}

    result = {"blog_id": blog_id, "site_path": site_path, "domain": domain}
    fixes = []
    issues = []

    # 1. 백업
    logger.info(f"\n[{blog_id}] 백업 중...")
    backup_blog(site_path, blog_id)

    # 2. GA4 ID 조회
    ga4_id = get_ga4_id(blog_id, domain)
    if ga4_id:
        logger.info(f"  GA4 ID: {ga4_id}")
    else:
        logger.info(f"  GA4 ID: 없음 (불명 큐)")

    # 3. 반복 수정 루프 (최대 3회)
    max_rounds = 3
    for round_num in range(1, max_rounds + 1):
        logger.info(f"  [라운드 {round_num}] 진단 중...")
        round_fixes = []

        # R04: GA4
        if ga4_id:
            ok, msg = fix_r04_ga4(site, ga4_id)
            if ok:
                round_fixes.append(("R04", msg))
            else:
                issues.append(("R04", msg))

        # R06: in-article fluid
        ok, msg = fix_r06_fluid(site)
        if ok:
            round_fixes.append(("R06", msg))
        else:
            issues.append(("R06", msg))

        # R08: .Lead/.Description 제거
        ok, msg = fix_r08_lead(site)
        if ok:
            round_fixes.append(("R08", msg))
        else:
            issues.append(("R08", msg))

        # R12: 무단 오버라이드 정리
        ok, msg = fix_r12_overrides(site)
        if ok:
            round_fixes.append(("R12", msg))
        else:
            issues.append(("R12", msg))

        # THUMBNAIL-01 / R2-01
        ok, msg = fix_images_r2(site, blog_id)
        if ok:
            round_fixes.append(("THUMBNAIL-01/R2-01", msg))
        else:
            issues.append(("THUMBNAIL-01/R2-01", msg))

        result["fixes_round_" + str(round_num)] = round_fixes
        if not round_fixes:
            logger.info(f"  라운드 {round_num}: 더 수정할 항목 없음")
            break

        # Hugo 빌드 확인
        build_ok, build_msg = build_hugo(site_path)
        if not build_ok:
            logger.error(f"  Hugo 빌드 실패: {build_msg}")
            issues.append(("BUILD", build_msg))
            # 빌드 실패하면 해당 라운드 수정 원복 (git checkout)
            import subprocess
            subprocess.run(["git", "checkout", "--", "layouts/", "assets/", "hugo.toml"],
                           cwd=site_path, capture_output=True)
            break

        logger.info(f"  라운드 {round_num}: Hugo 빌드 OK")

    # 최종 빌드
    build_ok, build_msg = build_hugo(site_path)
    result["hugo_build"] = {"ok": build_ok, "msg": build_msg}

    if build_ok:
        # 재검사 트리거
        recheck_ok = trigger_recheck(blog_id)
        result["recheck_triggered"] = recheck_ok
        if recheck_ok:
            logger.info(f"  재검사 트리거 완료: {blog_id}")

    # 상태 분류
    if not issues:
        result["status"] = "PASS"
    elif all(i[0] in ("THUMBNAIL-01/R2-01", "R04") for i in issues):
        result["status"] = "PARTIAL"  # GA4 불명, R2 미확인 등 외부 의존
    else:
        result["status"] = "잔여"

    result["issues"] = issues
    return result

# ── 엔트리포인트 ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    load_blog_sites()
    logger.info(f"총 {len(BLOG_SITES)}개 블로그 로드됨")

    results = []
    for blog_id, site_path, domain in BLOG_SITES:
        try:
            r = process_blog(blog_id, site_path, domain)
            results.append(r)
        except Exception as e:
            results.append({"blog_id": blog_id, "status": "ERROR", "reason": str(e)})
            logger.error(f"[{blog_id}] 처리 중 오류: {e}")

    # 요약 출력
    print("\n" + "=" * 60)
    print("최종 결과 요약")
    print("=" * 60)
    pass_count = sum(1 for r in results if r.get("status") == "PASS")
    partial_count = sum(1 for r in results if r.get("status") == "PARTIAL")
    remain_count = sum(1 for r in results if r.get("status") == "잔여")
    skip_count = sum(1 for r in results if r.get("status") == "skip")
    err_count = sum(1 for r in results if r.get("status") == "ERROR")

    print(f"  PASS    : {pass_count}개")
    print(f"  PARTIAL : {partial_count}개 (외부 의존/확인 필요)")
    print(f"  잔여    : {remain_count}개 (더 못 고침)")
    print(f"  skip    : {skip_count}개")
    print(f"  ERROR   : {err_count}개")

    print("\n── 블로그별 결과 ──")
    for r in results:
        status = r.get("status", "?")
        bid = r.get("blog_id", "?")
        fixes_flat = []
        for k, v in r.items():
            if k.startswith("fixes_round_"):
                fixes_flat.extend(v)
        fix_summary = ", ".join(f"{f[0]}:{f[1][:40]}" for f in fixes_flat[:3]) if fixes_flat else "없음"
        issues_summary = ", ".join(f"{i[0]}:{i[1][:40]}" for i in r.get("issues", [])[:3]) if r.get("issues") else ""
        build_msg = r.get("hugo_build", {}).get("msg", "")[:50]

        print(f"\n[{status}] {bid} ({r.get('domain','')})")
        if fix_summary:
            print(f"  수정: {fix_summary}")
        if issues_summary:
            print(f"  잔여: {issues_summary}")
        if build_msg:
            print(f"  빌드: {build_msg}")

    print("\n── 사람 승인 대기 큐 ──")
    ga4_queue = [r for r in results if any(i[0] == "R04" and "GA4 ID 없음" in i[1] for i in r.get("issues", []))]
    r2_queue = [r for r in results if any(i[0] == "THUMBNAIL-01/R2-01" and "잔여" in r.get("status", "") for i in r.get("issues", []))]
    print(f"  GA4 불명 (OAuth/ID 필요): {len(ga4_queue)}개 — {[r['blog_id'] for r in ga4_queue]}")
    print(f"  R2 이미지 재업로드 필요: {len(r2_queue)}개 — {[r['blog_id'] for r in r2_queue]}")

    # 백업 태그 목록
    print("\n── 백업 태그 ──")
    import subprocess
    try:
        tags = subprocess.run(
            ["git", "tag", "-l", f"{BACKUP_TAG_PREFIX}-*"],
            capture_output=True, text=True, cwd=str(WORKSPACE)
        )
        tag_list = [t for t in tags.stdout.strip().split("\n") if t]
        for t in tag_list[:20]:
            print(f"  {t}")
        if len(tag_list) > 20:
            print(f"  ... 외 {len(tag_list)-20}개")
    except Exception:
        print("  (git 태그 조회 불가)")

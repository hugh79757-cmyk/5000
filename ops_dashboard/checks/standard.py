"""ops_dashboard.checks.standard — 표준 준수 검사 (R01-R12)

Blowfish/AdSense 표준 규칙을 blog별로 검사하고,
CRITICAL 위반 발견 시 텔레그램 알림을 보낸다.
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ops_dashboard.checks import register_check

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rule definitions: R01-R12
# ---------------------------------------------------------------------------
# bucket(2026-08-06, 커밋 C 마감): 준수율 산정 버킷 분류
#   - actionable   : 지금 고칠 대상 — 준수율 분모/분자에 반영
#   - deferred     : 의도적 보류(수익 리스크) — 준수율에서 제외, 별도 표기
#   - out_of_scope : 정상화 범위 밖 — 준수율에서 제외, 별도 표기
# R06은 콘솔 슬롯 형식 미확인(STRUCT-16), R03은 이중 관리(STRUCT-15),
# R04는 GA4 Analytics 사안(STRUCT-17)으로 제외.

STANDARD_RULES: list[dict] = [
    {
        "rule_id": "R01",
        "target": "hugo.toml",
        "severity": "CRITICAL",
        "description": "showTableOfContents must be false",
        "bucket": "actionable",
        "check": "_check_r01",
    },
    {
        "rule_id": "R02",
        "target": "hugo.toml",
        "severity": "CRITICAL",
        "description": "Advertisement section with adsense slots required",
        "bucket": "actionable",
        "check": "_check_r02",
    },
    {
        "rule_id": "R03",
        "target": "extend-head.html",
        "severity": "CRITICAL",
        "description": "adsbygoogle.js must use site.Params (no hardcoding)",
        "bucket": "out_of_scope",
        "check": "_check_r03",
    },
    {
        "rule_id": "R04",
        "target": "extend_head.html",
        "severity": "MAJOR",
        "description": "GA4 + mobile correction CSS required",
        "bucket": "out_of_scope",
        "check": "_check_r04",
    },
    {
        "rule_id": "R05",
        "target": "adsense/top.html",
        "severity": "MAJOR",
        "description": "overflow:hidden;min-height:100px wrapper + outside push div",
        "bucket": "actionable",
        "check": "_check_r05",
    },
    {
        "rule_id": "R06",
        "target": "adsense/in-article.html",
        "severity": "CRITICAL",
        "description": "fluid+in-article format (no auto) + outside push div",
        "bucket": "deferred",
        "check": "_check_r06",
    },
    {
        "rule_id": "R07",
        "target": "single.html",
        "severity": "MAJOR",
        "description": "H2 split injection + prose wrapper",
        "bucket": "actionable",
        "check": "_check_r07",
    },
    {
        "rule_id": "R08",
        "target": "single.html",
        "severity": "MAJOR",
        "description": "Description (lead) must be removed",
        "bucket": "actionable",
        "check": "_check_r08",
    },
    {
        "rule_id": "R09",
        "target": "baseof.html",
        "severity": "MAJOR",
        "description": "No custom override — use theme default",
        "bucket": "actionable",
        "check": "_check_r09",
    },
    {
        "rule_id": "R10",
        "target": "custom.css",
        "severity": "MAJOR",
        "description": "Unfilled space removal + dark mode + min-height rules",
        "bucket": "actionable",
        "check": "_check_r10",
    },
    {
        "rule_id": "R11",
        "target": "layouts/",
        "severity": "MAJOR",
        "description": "mobile-sticky.html must not be used",
        "bucket": "actionable",
        "check": "_check_r11",
    },
    {
        "rule_id": "R12",
        "target": "layouts/",
        "severity": "MAJOR",
        "description": "No override files beyond the allowed set",
        "bucket": "actionable",
        "check": "_check_r12",
    },
]

# Allowed override files (CONTEXT.md §4-3)
# 2026-08-06 (커밋 C 4단계): 다수 블로그에 동일 해시로 존재하는
# 의도된 SEO/광고 공통 오버라이드를 인가 목록에 추가.
#  - related.html: 77개 블로그 (73 동일 해시)
#  - head/custom.html: 35개 (동일 해시, adsbygoogle 로더)
#  - cuap-spider-links.html / render-link.html: 각 15개 (동일 해시)
#  - translations.html: 7개 (언어 스위처 비활성)
#  - tradingview-widget.html: 6개 (주식 위젯)
#  - extend-article-link.html: 5개 / shortcodes article,lead: 각 5개
#  - chain-card / chain-official-card: 각 3개 / extend-head-uncached: 8개
# 개별 고유 오버라이드(사용 빈도 1)는 여전히 위반으로 보고된다.
ALLOWED_OVERRIDES = {
    "layouts/_default/single.html",
    "layouts/archives/single.html",
    "layouts/partials/affiliate-disclosure.html",
    "layouts/partials/extend-head.html",
    "layouts/partials/extend_head.html",
    "layouts/_markup/render-link.html",
    "layouts/partials/adsense",
    "layouts/partials/related.html",
    "layouts/partials/related-single.html",
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
    "layouts/partials/home/background.html",
    "layouts/shortcodes/btn.html",
    "layouts/shortcodes/dday.html",
    "layouts/shortcodes/inchcm.html",
    "layouts/shortcodes/datecalc.html",
    "layouts/shortcodes/linkcard.html",
    "layouts/partials/extend_footer.html",
    "layouts/partials/cover.html",
    "layouts/partials/share_icons.html",
    "layouts/partials/share-buttons.html",
    "layouts/partials/jsonld.html",
    "layouts/partials/templates/opengraph.html",
    "layouts/partials/templates/twitter_cards.html",
}

# 오버라이드가 아닌 정크 파일: 위반으로 보고하지 않지만 별도로 집계한다.
# (.DS_Store macOS 메타데이터, .bak 백업 잔재 — 실제 오버라이드가 아님)
JUNK_OVERRIDE_SUFFIXES = (".DS_Store", ".bak", ".bak2", "~")


def _find_hugo_root(blog_row: dict) -> Path | None:
    """Resolve the Hugo site root from blog_lifecycle row."""
    site_path = blog_row.get("site_path", "")
    if not site_path:
        return None
    p = Path(site_path)
    if not p.is_dir():
        return None
    return p


def _read_file_safe(path: Path) -> str:
    """Read file contents, return empty string on error."""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except (OSError, PermissionError):
        return ""


# ---------------------------------------------------------------------------
# Individual rule checks — each returns (pass/fail, detail)
# ---------------------------------------------------------------------------

def _find_config_file(site: Path) -> Path | None:
    """Find hugo.toml / config.toml at root or config/_default/ (Hugo config dir).

    params.toml included (2026-08-06, fix): CUAP/ETAP store params in
    config/_default/params.toml, which Hugo auto-maps to site.Params.
    """
    for name in ("hugo.toml", "hugo.yaml", "config.toml", "config.yaml",
                 "params.toml", "params.yaml"):
        # Check root first
        root_cfg = site / name
        if root_cfg.exists():
            return root_cfg
        # Then config/_default/ (Hugo config directory pattern)
        dir_cfg = site / "config" / "_default" / name
        if dir_cfg.exists():
            return dir_cfg
    return None


def _find_all_config_files(site: Path) -> list[Path]:
    """Find ALL config files (hugo.toml + params.toml) for R02 aggregation.

    R02 must inspect both hugo.toml and params.toml: [params.advertisement]
    may live in either (hugo.toml inline or params.toml auto-Params mapping).
    """
    found: list[Path] = []
    for name in ("hugo.toml", "hugo.yaml", "config.toml", "config.yaml",
                 "params.toml", "params.yaml"):
        for p in (site / name, site / "config" / "_default" / name):
            if p.exists() and p not in found:
                found.append(p)
    return found


def _check_r01(site: Path) -> tuple[bool, str]:
    """R01: showTableOfContents must be false in hugo.toml."""
    cfg = _find_config_file(site)
    if cfg is None:
        return False, "No hugo.toml/config found at root or config/_default/"
    content = _read_file_safe(cfg)
    # Look for showTableOfContents = false
    if re.search(r"showTableOfContents\s*=\s*false", content, re.IGNORECASE):
        return True, f"{cfg.name}: showTableOfContents=false confirmed"
    if re.search(r"showTableOfContents\s*=\s*true", content, re.IGNORECASE):
        return False, f"{cfg.name}: showTableOfContents=true (must be false)"
    return True, f"{cfg.name}: showTableOfContents not set (assumed false)"


def _check_r02(site: Path) -> tuple[bool, str]:
    """R02: [params.advertisement] with adsense slots required.

    Inline in hugo.toml as [params.advertisement], or in config/_default/
    params.toml as [advertisement] (Hugo auto-maps params.toml to site.Params).

    N/A: if the site does not load adsbygoogle.js in extend-head/extend_head
    (AdSense not used), the rule does not apply — pass (R03/R05/R06 pattern).
    """
    # AdSense 미사용 판별: extend-head/extend_head에 adsbygoogle 로더 없으면 N/A
    loader_files = (
        site / "layouts/partials/extend-head.html",
        site / "layouts/partials/extend_head.html",
        site / "layouts/partials/extend-head.html",
    )
    seen = set()
    adsense_loader = False
    for f in loader_files:
        if f in seen:
            continue
        seen.add(f)
        if f.exists() and "adsbygoogle" in _read_file_safe(f):
            adsense_loader = True
            break
    if not adsense_loader:
        return True, "AdSense 미사용 (extend-head에 adsbygoogle 로더 없음) — N/A"

    configs = _find_all_config_files(site)
    if not configs:
        return False, "No hugo.toml/config/params found at root or config/_default/"
    content = "\n".join(_read_file_safe(c) for c in configs)
    # [params.advertisement] (hugo.toml inline) or [advertisement] (params.toml)
    # or YAML "advertisement:" (hugo.yaml, indentation allowed)
    has_adv_section = (
        "[params.advertisement]" in content
        or re.search(r"^\[advertisement\]\s*$", content, re.M)
        or re.search(r"^\s*advertisement:\s*$", content, re.M)
    )
    if not has_adv_section:
        return False, f"no [params.advertisement] section (checked {len(configs)} config files)"
    has_adsense = "adsense" in content.lower()
    has_slots = "topSlot" in content or "inArticleSlot" in content
    if has_adsense and has_slots:
        return True, f"advertisement section with slots found ({len(configs)} config files)"
    return False, f"advertisement section present but missing adsense/slots: adsense={has_adsense} slots={has_slots}"


def _check_r03(site: Path) -> tuple[bool, str]:
    """R03: adsbygoogle.js must use site.Params, not hardcoded publisher ID."""
    for partial_dir in ("layouts/partials", "config/_default/layouts/partials"):
        extend_head = site / partial_dir / "extend-head.html"
        if not extend_head.exists():
            extend_head = site / partial_dir / "extend_head.html"
        if extend_head.exists():
            content = _read_file_safe(extend_head)
            if "adsbygoogle" not in content:
                return True, "No adsbygoogle reference (not applicable)"
            # Good: uses site.Params
            if "site.Params" in content or ".Site.Params" in content:
                return True, "extend-head: uses site.Params for adsbygoogle"
            # Bad: hardcoded publisher ID
            if "ca-pub-" in content:
                return False, "extend-head: hardcoded ca-pub- (must use site.Params)"
            return True, "extend-head: adsbygoogle present, no hardcoded ID detected"
    return True, "No extend-head.html found (not applicable)"


def _check_r04(site: Path) -> tuple[bool, str]:
    """R04: GA4 + mobile correction CSS.

    Blowfish 테마는 hugo.toml의 [services.googleAnalytics] ID = "G-..."가 있으면
    layouts/partials/analytics/main.html 통해 gtag를 자동 생성한다.
    따라서 다음 중 하나라도 충족하면 PASS:
      (a) extend-head.html(또는 extend_head.html)에 유효한 GA4 gtag + mobile CSS가 있음
      (b) hugo.toml(또는 config/_default/hugo.toml)에 [services.googleAnalytics] ID 가 유효한
          G-[A-Z0-9]+ 형식으로 존재함 (Blowfish가 빌드 시 GA4 자동 생성)
    둘 다 없으면 FAIL.
    """
    ga_found = False
    evidence = ""

    # (a) extend-head.html 검사
    for partial_dir in ("layouts/partials",):
        for name in ("extend_head.html", "extend-head.html"):
            p = site / partial_dir / name
            if p.exists():
                content = _read_file_safe(p)
                has_ga = "gtag" in content or "GA4" in content or "google-analytics" in content
                has_mobile = "max-width" in content or "font-size" in content or "mobile" in content.lower()
                if has_ga and has_mobile:
                    return True, "extend_head: GA4 + mobile CSS found"
                if has_ga:
                    ga_found = True
                    evidence = "extend_head: GA4 found but missing mobile CSS"
                elif has_mobile:
                    evidence = "extend_head: mobile CSS found but missing GA4"
                else:
                    evidence = "extend_head: missing GA4 and mobile CSS"
                break

    # (b) hugo.toml [services.googleAnalytics] ID 검사 (Blowfish 자동 생성 경로)
    #    hugo.toml 위치: site/hugo.toml 또는 site/config/_default/hugo.toml
    for conf_path in (site / "hugo.toml", site / "config" / "_default" / "hugo.toml",
                      site / "config" / "hugo.toml"):
        if conf_path.exists():
            content = _read_file_safe(conf_path)
            m = re.search(r'\[services\.googleAnalytics\].*?ID\s*=\s*["\']([G]-[A-Z0-9]+)["\']',
                          content, re.DOTALL)
            if m:
                return True, f"hugo.toml: [services.googleAnalytics] ID={m.group(1)} (Blowfish 자동 생성)"

    # (b') legacy params.toml googleAnalytics (Blowfish 구버전, site.Params.googleAnalytics)
    for conf_path in (site / "config" / "_default" / "params.toml", site / "params.toml",
                      site / "config" / "params.toml"):
        if conf_path.exists():
            content = _read_file_safe(conf_path)
            m2 = re.search(r'googleAnalytics\s*=\s*["\'](G-[A-Z0-9]+)["\']', content)
            if m2:
                return True, f"params.toml: googleAnalytics={m2.group(1)} (legacy, Blowfish)"

    return False, evidence or "No extend_head.html found and no hugo.toml [services.googleAnalytics] ID"


def _check_r05(site: Path) -> tuple[bool, str]:
    """R05: adsense/top.html — overflow:hidden;min-height:100px wrapper."""
    top_file = site / "layouts/partials/adsense/top.html"
    if not top_file.exists():
        return True, "No adsense/top.html (not applicable)"
    content = _read_file_safe(top_file)
    has_overflow = "overflow" in content and "hidden" in content
    has_minheight = "min-height" in content
    if has_overflow and has_minheight:
        return True, "top.html: overflow:hidden + min-height present"
    missing = []
    if not has_overflow:
        missing.append("overflow:hidden")
    if not has_minheight:
        missing.append("min-height")
    return False, f"top.html: missing {', '.join(missing)}"


def _check_r06(site: Path) -> tuple[bool, str]:
    """R06: adsense/in-article.html — fluid+in-article format (no auto)."""
    in_article = site / "layouts/partials/adsense/in-article.html"
    if not in_article.exists():
        return True, "No adsense/in-article.html (not applicable)"
    content = _read_file_safe(in_article)
    has_fluid = "fluid" in content
    has_in_article = "in-article" in content
    has_auto = re.search(r'data-ad-format\s*=\s*"auto"', content)
    if has_fluid and has_in_article and not has_auto:
        return True, "in-article.html: fluid+in-article format, no auto"
    issues = []
    if not has_fluid:
        issues.append("missing fluid format")
    if not has_in_article:
        issues.append("missing in-article format")
    if has_auto:
        issues.append("data-ad-format=auto (prohibited)")
    return False, f"in-article.html: {', '.join(issues)}"


def _check_r07(site: Path) -> tuple[bool, str]:
    """R07: single.html — H2 split injection + prose wrapper."""
    single = site / "layouts/_default/single.html"
    if not single.exists():
        return True, "No single.html override (theme default used)"
    content = _read_file_safe(single)
    has_h2_split = "h2" in content.lower() and ("split" in content.lower() or "inject" in content.lower() or "adsense" in content.lower())
    has_prose = "prose" in content
    if has_h2_split and has_prose:
        return True, "single.html: H2 injection + prose wrapper found"
    missing = []
    if not has_h2_split:
        missing.append("H2 split injection")
    if not has_prose:
        missing.append("prose wrapper")
    return False, f"single.html: missing {', '.join(missing)}"


def _check_r08(site: Path) -> tuple[bool, str]:
    """R08: single.html — Description (lead) must be removed."""
    single = site / "layouts/_default/single.html"
    if not single.exists():
        return True, "No single.html override (theme default used)"
    content = _read_file_safe(single)
    # Check for .Lead or .Description usage that should be removed
    if ".Lead" in content or ".Description" in content:
        # Check if it's commented out (good)
        lines = content.split("\n")
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("<!--"):
                continue
            if (".Lead" in stripped or ".Description" in stripped) and not stripped.startswith("//"):
                return False, "single.html: .Lead/.Description still present (not removed)"
    return True, "single.html: .Lead/.Description removed or commented out"


def _check_r09(site: Path) -> tuple[bool, str]:
    """R09: baseof.html — no custom override."""
    baseof = site / "layouts/_default/baseof.html"
    if not baseof.exists():
        return True, "No baseof.html override (theme default used)"
    content = _read_file_safe(baseof)
    # If baseof.html exists, it should be minimal or identical to theme
    # Flag if it has significant custom content
    if len(content.strip().split("\n")) > 5:
        return False, "baseof.html: custom override detected (should use theme default)"
    return True, "baseof.html: minimal override"


def _check_r10(site: Path) -> tuple[bool, str]:
    """R10: custom.css — unfilled space + dark mode + min-height rules."""
    custom_css = site / "assets/css/custom.css"
    if not custom_css.exists():
        return False, "No custom.css found"
    content = _read_file_safe(custom_css)
    has_unfilled = "unfilled" in content.lower() or "min-height" in content
    has_dark = "dark" in content.lower() or "@media (prefers-color-scheme" in content
    if has_unfilled and has_dark:
        return True, "custom.css: unfilled + dark mode rules found"
    missing = []
    if not has_unfilled:
        missing.append("unfilled/min-height rules")
    if not has_dark:
        missing.append("dark mode rules")
    return False, f"custom.css: missing {', '.join(missing)}"


def _check_r11(site: Path) -> tuple[bool, str]:
    """R11: mobile-sticky.html must not be used."""
    mobile_sticky = site / "layouts/partials/adsense/mobile-sticky.html"
    if mobile_sticky.exists():
        return False, "mobile-sticky.html found (prohibited per ADSENSE §8)"
    return True, "No mobile-sticky.html (correct)"


def _check_r12(site: Path) -> tuple[bool, str]:
    """R12: No override files beyond the allowed set.

    2026-08-06 (커밋 C 4단계): .DS_Store/.bak 등 정크 파일은 오버라이드가
    아니므로 위반에서 제외하고 detail에 별도로 집계한다. 인가 목록은
    ALLOWED_OVERRIDES 참조.
    """
    layouts_dir = site / "layouts"
    if not layouts_dir.is_dir():
        return True, "No layouts/ directory (no overrides)"

    violations = []
    junk_files = []
    for f in layouts_dir.rglob("*"):
        if not f.is_file():
            continue
        rel = str(f.relative_to(site))
        # 정크 파일 (.DS_Store, *.bak 등) — 오버라이드 위반 아님
        if rel.endswith(JUNK_OVERRIDE_SUFFIXES) or "/.DS_Store" in rel:
            junk_files.append(rel)
            continue
        # Check if this file is in allowed set
        is_allowed = False
        for allowed in ALLOWED_OVERRIDES:
            if rel.startswith(allowed) or rel == allowed + ".html":
                is_allowed = True
                break
        if not is_allowed:
            violations.append(rel)

    if violations:
        detail = f"Unauthorized overrides: {', '.join(violations[:5])}"
        if junk_files:
            detail += f" (junk: {', '.join(junk_files[:3])})"
        return False, detail
    if junk_files:
        return True, f"All override files allowed (junk: {', '.join(junk_files[:3])})"
    return True, "All override files are in the allowed set"


# ---------------------------------------------------------------------------
# THUMBNAIL-01: 썸네일 존재·600×600·webp·R2 업로드 여부 검사 (W7-b 추가)
# ---------------------------------------------------------------------------
# W7-b: THUMBNAIL-01은 rules.py RULES에 선언만 추가하고,
# _CHECK_FUNCTIONS 및 STANDARD_RULES에는 추가하지 않는다 —
# W7-a 보강 A/B로 registry → 동적 디스패치 경로가 열렸기 때문.
# 대상: 5000 중앙 파이프라인 발행(구 curation) 블로그의 content/posts/ 내 포스트.
# 판정: 최근 포스트(최대 10개) 중 featureimage가 있는 포스트 전부 R2 + webp면 pass,
#       R2가 아닌 URL 또는 webp가 아닌 URL이 1건이라도 있으면 fail.
#       featureimage가 없는 포스트(누락)는 썸네일 규칙 위반이 아니라 별도 집계만 한다.
# ---------------------------------------------------------------------------

_R2_PATTERN = re.compile(r"pub-[0-9a-f]+\.r2\.dev")


def _today_start() -> float:
    """KST(UTC+9) 자정 타임스탬프 — 오늘 발행분 전수 창 기준."""
    utc_now = datetime.now(timezone.utc)
    kst = utc_now + timedelta(hours=9)
    kst_midnight = kst.replace(hour=0, minute=0, second=0, microsecond=0)
    return kst_midnight.timestamp()


def _content_mtime(p: Path) -> float:
    """index.md mtime 우선 (디렉토리 mtime은 갱신 안 됨 — W7-c)."""
    idx = p / "index.md"
    return idx.stat().st_mtime if idx.exists() else p.stat().st_mtime


def _post_date_ts(p: Path, fallback: float) -> float:
    """프런트매터 date/lastmod/publishDate 우선, 부재 시 index.md mtime."""
    idx = p / "index.md"
    if idx.exists():
        try:
            m = re.search(r"^(?:date|publishDate|lastmod):\s*([^\s#]+)", idx.read_text(errors="replace"), re.M)
            if m:
                return datetime.fromisoformat(m.group(1).strip().strip("'\"")).timestamp()
        except (ValueError, OSError):
            pass
        return idx.stat().st_mtime
    return fallback


def _recent_posts(site: Path, n: int = 10, since: float | None = None) -> list[Path]:
    """content/posts/에서 포스트 디렉토리를 반환.

    since 가 None → index.md mtime 기준 최신 n개 (W7-c, W7-b sortfix).
    since 지정 → 프런트매터 date 기준 오늘 발행분 전수 (n 무시).
    포스트가 없거나 content/posts/가 없으면 빈 리스트 반환.
    """
    posts_dir = site / "content" / "posts"
    if not posts_dir.is_dir():
        return []
    posts = [d for d in posts_dir.iterdir() if d.is_dir()]
    if since is None:
        posts.sort(key=_content_mtime, reverse=True)
        return posts[:n]
    return [p for p in posts if _post_date_ts(p, 0.0) >= since]


def _check_thumbnail_01(site: Path) -> tuple[bool, str]:
    """THUMBNAIL-01: 최근 포스트의 featureimage가 R2 업로드 + webp인지 검사.

    Hugo 사이트 content/posts/ 내 최근 10개 포스트의 index.md frontmatter에서
    featureimage를 추출해 다음 조건을 전부 만족하는지 확인:
      - URL이 R2 도메인에 호스팅됨 (pub-<hash>.r2.dev 패턴)
      - URL이 .webp로 끝남
    조건 미충족 URL이 1건이라도 있으면 fail, 전부 충족 또는 featureimage 없는
    포스트만 있으면 pass. featureimage가 아예 없는 포스트 수는 detail에 집계한다.

    검사 대상 포스트는 _recent_posts(site, 10, since=_today_start())로 mtime 기준 최신 10개를 사용한다
    (sorted() 알파벳순 대신 mtime 기준 — W7-b sortfix).
    """
    posts = _recent_posts(site, 10, since=_today_start())
    if not posts:
        # content/posts/ 없음 또는 포스트 없음
        posts_dir = site / "content" / "posts"
        if not posts_dir.is_dir():
            return None, "content/posts/ 디렉토리 없음 — 썸네일 검사 대상 아님 (N/A)"
        return None, "포스트 없음 — 검사 대상 없음 (N/A)"

    valid_count = 0
    invalid_entries = []
    missing_count = 0

    for post_dir in posts:
        idx = post_dir / "index.md"
        if not idx.exists():
            continue
        content = _read_file_safe(idx)
        m = re.search(r"featureimage:\s*[\"']?([^\"'\n]+)[\"']?", content)
        if not m or not m.group(1).strip():
            missing_count += 1
            continue
        url = m.group(1).strip()
        is_r2 = bool(_R2_PATTERN.search(url))
        is_webp = url.lower().endswith(".webp")
        if is_r2 and is_webp:
            valid_count += 1
        else:
            reason = []
            if not is_r2:
                reason.append("R2 아님")
            if not is_webp:
                reason.append("webp 아님")
            invalid_entries.append(f"{post_dir.name}: {url} ({', '.join(reason)})")

    # X3(2026-08-21): featureimage 전부 부재 = 썸네일 결핍 결함.
    # silent PASS(빈==빈) 금지 — C08와 동일 결함 클래스. FAIL로 교정.
    if valid_count == 0 and not invalid_entries:
        return False, (
            f"최근 {len(posts)}건 전부 featureimage 부재 "
            f"(썸네일 결핍 — og:image/R16 연동 결함, FAIL)"
        )

    # missing_count(부재)도 결함으로 집계 — silent pass 금지
    if invalid_entries or missing_count:
        detail = (
            f"썸네일 위반 {len(invalid_entries) + missing_count}건 / 검사 {len(posts)}건 "
            f"(유효 {valid_count}, 미보유 {missing_count}, 비정상 {len(invalid_entries)}): "
            + "; ".join(invalid_entries[:3])
        )
        if len(invalid_entries) > 3:
            detail += f" 외 {len(invalid_entries) - 3}건"
        return False, detail
    return True, f"최근 {len(posts)}건 전부 R2+webp 충족"


# ---------------------------------------------------------------------------
# R2-01: 이미지 URL R2 버킷/키 패턴 정합성 검사 (W7 확대)
# ---------------------------------------------------------------------------
# 역할: THUMBNAIL-01(featureimage 존재+R2+webp)과 분리.
# R2-01은 featureimage + 본문 내 모든 이미지 URL을 대상으로
# 승인된 R2 도메인(pub-<hash>.r2.dev) 호스팅 여부만 검사(webp 무관).
# 표준.py의 _CHECK_FUNCTIONS 및 STANDARD_RULES에는 추가하지 않음 —
# registry 선언 + _check_r2_01 함수만으로 자동편입.
# ---------------------------------------------------------------------------

_R2_DOMAIN_PATTERN = re.compile(r"https?://pub-[0-9a-f]+\.r2\.dev")

# Phase 71c: R2-01 affiliate hotlink 예외 — config/quality_checklist.yaml 의
# r2_exempt_domains 를 로드해 적용한다. 정적 모듈 상수 대신 설정에서 읽어
# 제휴사 추가 시 코드 변경 없이 확장 가능하게 한다.
_R2_EXEMPT_DOMAINS: frozenset[str] = frozenset()
_R2_EXEMPT_LOADED = False


def _load_r2_exempt_domains() -> frozenset[str]:
    """config/quality_checklist.yaml 의 r2_exempt_domains 를 로드 (1회).

    로드 실패/미설정 시 빈 frozenset 반환 — affiliate 예외 없이 기존 동작 유지.
    예외 삼키지 않고 logger.warning 로 이유 기록 (조용한 실패 금지).
    """
    global _R2_EXEMPT_DOMAINS, _R2_EXEMPT_LOADED
    if _R2_EXEMPT_LOADED:
        return _R2_EXEMPT_DOMAINS
    _R2_EXEMPT_LOADED = True
    # Phase 71d: parents[2] 의존 폴백 대신 shared.paths.CONFIG_DIR 를 단일 소스로 사용.
    # (ops_dashboard/checks/standard.py → 격리 실행·서버 로드 모두에서 경로 일관성 보장)
    from shared.paths import CONFIG_DIR
    cfg_path = Path(CONFIG_DIR) / "quality_checklist.yaml"
    try:
        import yaml as _yaml
    except Exception as e:  # pragma: no cover - yaml 항상 설치됨 (requirements)
        logger.warning("[R2-01] yaml 로드 불가 — affiliate 예외 미적용: %s", e)
        return _R2_EXEMPT_DOMAINS
    try:
        raw = _yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        domains = raw.get("r2_exempt_domains", []) or []
        _R2_EXEMPT_DOMAINS = frozenset(
            str(d).lower().rstrip("/") for d in domains if d and str(d).strip()
        )
        logger.info("[R2-01] affiliate 예외 도메인 %d개 로드: %s", len(_R2_EXEMPT_DOMAINS), sorted(_R2_EXEMPT_DOMAINS))
    except Exception as e:
        logger.warning("[R2-01] r2_exempt_domains 로드 실패 — affiliate 예외 미적용: %s", e)
    return _R2_EXEMPT_DOMAINS


def _is_r2_exempt(url: str) -> bool:
    """URL host 가 affiliate 예외 도메인 목록에 속하는지 (Phase 71c)."""
    if not _R2_EXEMPT_DOMAINS:
        return False
    try:
        from urllib.parse import urlparse
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return False
    return host in _R2_EXEMPT_DOMAINS


# Phase Wave1: rule별 파이프라인 면제 — quality_checklist.yaml global_standard[].exempt_pipelines
_EXEMPT_PIPELINES: dict[str, frozenset[str]] = {}
_EXEMPT_PIPELINES_LOADED = False


def _load_exempt_pipelines() -> dict[str, frozenset[str]]:
    """global_standard 각 항목의 exempt_pipelines 를 로드 (1회, yaml 기반).

    Wave 1: R04 etap 면제. 하드코딩 없이 yaml 선언만으로 확장 가능.
    """
    global _EXEMPT_PIPELINES, _EXEMPT_PIPELINES_LOADED
    if _EXEMPT_PIPELINES_LOADED:
        return _EXEMPT_PIPELINES
    _EXEMPT_PIPELINES_LOADED = True
    from shared.paths import CONFIG_DIR
    cfg_path = Path(CONFIG_DIR) / "quality_checklist.yaml"
    try:
        import yaml as _yaml
    except Exception as e:
        logger.warning("[exempt] yaml 로드 불가 — 파이프라인 면제 미적용: %s", e)
        return _EXEMPT_PIPELINES
    try:
        raw = _yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        for entry in raw.get("global_standard", []) or []:
            rid = str(entry.get("id", "")).strip()
            if not rid:
                continue
            ex = entry.get("exempt_pipelines")
            if not ex:
                continue
            vals = [str(v).lower().strip() for v in (ex if isinstance(ex, list) else [ex]) if str(v).strip()]
            if vals:
                _EXEMPT_PIPELINES[rid] = frozenset(vals)
        if _EXEMPT_PIPELINES:
            logger.info("[exempt] 파이프라인 면제 로드: %s", {k: sorted(v) for k, v in _EXEMPT_PIPELINES.items()})
    except Exception as e:
        logger.warning("[exempt] exempt_pipelines 로드 실패 — 면제 미적용: %s", e)
    return _EXEMPT_PIPELINES


def _extract_image_urls(content: str) -> list[str]:
    """포스트 본문(content.md)에서 이미지 URL 추출.

    마크다운 이미지 문법 ![alt](url)과 HTML <img src="url"> 양쪽 지원.
    특징: URL만 반환, 중복 제거 없음(호출부에서 처리).
    """
    urls: list[str] = []
    # 마크다운: ![...](url)  또는  ![alt](url "title")
    for m in re.finditer(r"""!\[[^\]]*\]\(\s*(https?://[^\)"'\s]+)""", content):
        urls.append(m.group(1).strip())
    # HTML: <img ... src="url"> 또는 <img ... src='url'>
    for m in re.finditer(r"""<img\s[^>]*src\s*=\s*["']?(https?://[^"'>\s]+)["']?""", content, re.IGNORECASE):
        urls.append(m.group(1).strip())
    return urls


def _check_r2_01(site: Path) -> tuple[bool, str]:
    """R2-01: featureimage + 본문 이미지 URL이 승인된 R2 도메인 호스팅인지 검사.

    최근 10개 포스트(_recent_posts)의 index.md에서:
      - frontmatter featureimage
      - 본문 내 모든 이미지 URL (마크다운 ![](url) + HTML <img src=url>)
    를 추출해 pub-<hash>.r2.dev 도메인 호스팅 여부를 확인.

    R2 도메인(href pub-<hash>.r2.dev) 호스팅이 아닌 URL이 1건이라도 있으면 fail.
    이미지 URL이 전혀 없는 포스트만 있으면 pass.
    featureimage 없음 + 본문 이미지 없음은 위반 아님(pass).

    THUMBNAIL-01과의 차이:
      - THUMBNAIL-01: featureimage만 대상, R2 + webp 모두 요구
      - R2-01: featureimage + 본문 이미지 전체 대상, R2 도메인만 요구(webp 무관)
    """
    posts = _recent_posts(site, 10, since=_today_start())
    if not posts:
        posts_dir = site / "content" / "posts"
        if not posts_dir.is_dir():
            return None, "content/posts/ 디렉토리 없음 — 이미지 검사 대상 아님 (N/A)"
        return None, "포스트 없음 — 검사 대상 없음 (N/A)"

    exempt_domains = _load_r2_exempt_domains()
    invalid_entries: list[str] = []
    checked_count = 0
    exempt_count = 0

    for post_dir in posts:
        idx = post_dir / "index.md"
        if not idx.exists():
            continue
        content = _read_file_safe(idx)
        if not content.strip():
            continue

        # 1) frontmatter featureimage
        fm_match = re.search(r"featureimage:\s*[\"']?([^\"'\n]+)[\"']?", content)
        featureimage_url = fm_match.group(1).strip() if fm_match and fm_match.group(1).strip() else None
        if featureimage_url:
            checked_count += 1
            if _is_r2_exempt(featureimage_url):
                exempt_count += 1
            elif not _R2_DOMAIN_PATTERN.search(featureimage_url):
                invalid_entries.append(f"{post_dir.name}/featureimage: {featureimage_url}")

        # 2) 본문 이미지 URL (featureimage와 중복 가능 — 중복은 허용)
        body_start = content.find("---", 3)  # 두 번째 --- 이후가 본문
        if body_start >= 0:
            body = content[body_start + 3:]
        else:
            body = content
        for url in _extract_image_urls(body):
            if not url:
                continue
            # featureimage와 중복 제거
            if featureimage_url and url == featureimage_url:
                continue
            checked_count += 1
            if _is_r2_exempt(url):
                exempt_count += 1
            elif not _R2_DOMAIN_PATTERN.search(url):
                invalid_entries.append(f"{post_dir.name}/body: {url}")

    if checked_count == 0:
        return True, f"최근 {len(posts)}개 포스트 전부 이미지 URL 없음 (pass)"

    if invalid_entries:
        detail = (
            f"R2 패턴 위반 {len(invalid_entries)}건 / 검사 {checked_count}건"
            f"{f' (affiliate exempt {exempt_count}건)' if exempt_count else ''}: "
            + "; ".join(invalid_entries[:3])
        )
        if len(invalid_entries) > 3:
            detail += f" 외 {len(invalid_entries) - 3}건"
        return False, detail
    exempt_note = f" (affiliate exempt {exempt_count}건)" if exempt_count else ""
    return True, f"최근 {checked_count}건 전부 R2 도메인 호스팅{exempt_note} (정상)"


# ---------------------------------------------------------------------------
# Check dispatch
# ---------------------------------------------------------------------------

_CHECK_FUNCTIONS = {
    "R01": _check_r01,
    "R02": _check_r02,
    "R03": _check_r03,
    "R04": _check_r04,
    "R05": _check_r05,
    "R06": _check_r06,
    "R07": _check_r07,
    "R08": _check_r08,
    "R09": _check_r09,
    "R10": _check_r10,
    "R11": _check_r11,
    "R12": _check_r12,
}


# W7-a 보강 B: check_fn 문자열 → 동적 함수 해석 (registry 실행 디스패치).
# 기존 _CHECK_FUNCTIONS 하드코딩 dict를 대체하며, 레지스트리(rules.py)의
# UnifiedEntry.check_fn 문자열을 동일 모듈 내 함수로 getattr한다.
# 미발견 시 조용히 skip하지 않고 경고 로깅(누락 규칙 은폐 금지).
import sys as _sys


def _resolve_check_fn(check_fn_name: str):
    """check_fn 문자열을 동일 모듈 내 함수 객체로 해석.

    registry(rules.py)의 UnifiedEntry.check_fn (예: '_check_r01')을 받아
    standard.py 내 동일 이름의 함수로 getattr한다. 없으면 None 반환 + 경고.
    """
    mod = _sys.modules[__name__]
    fn = getattr(mod, check_fn_name, None)
    if fn is None:
        logger.warning(
            "W7-a: registry check_fn=%s 확인 불가 — 표준.py에 해당 함수 없음 (skip 금지 원칙 위반 위험)",
            check_fn_name,
        )
    return fn


def _check_c08(site: Path) -> tuple[bool, str]:
    """C08 라이브 대조 — 표준준수 집계 경로 위임 래퍼.

    check_standard_compliance(_resolve_check_fn) 가 standard.py 내 함수를 요구하므로
    동명 함수를 둔다. 실제 라이브 크롤 로직은 content_integrity.check_c08(등록 check)에서
    수행하므로, 여기선 중복 크롤을 막기 위해 정적 패스만 반환. C08는 bucket="deferred"
    라 표준준수 집계율에서는 제외된다.
    """
    # C6(2026-08-21): 단일 상태 원칙 — C08의 권위 상태는 등록 check
    # c08_live_file_mismatch(325건 fail 보고) 단 1곳. 표준루프 래퍼는 패스/페일
    # 어느 쪽도 주장하지 않고 N/A(미적용)로 빠져 중복 상태를 제거한다.
    return None, "C08: 표준루프는 N/A — 권위 상태는 c08_live_file_mismatch"


# W7-a 경고 해소: registry에 선언됐으나 standard.py에 없던 check_fn 래퍼
# ponytail: 별도 체크(data_stock/frontmatter/content_freshness)는 자체 @register_check로
# run_all_checks에서 이미 수행됨. 표준 루프에서는 N/A로 위임해 warning/집계 왜곡 방지.
def _check_data_stock(site: Path) -> tuple[bool, str]:
    """data_stock — 브랜드 재고 검사는 data_stock.py @register_check에서 수행. 표준 루프 N/A."""
    return None, "data_stock: 표준루프 N/A — 권위 상태는 data_stock 체크"


def _check_frontmatter(site: Path) -> tuple[bool, str]:
    """FM-* — 프론트매터 검사는 frontmatter.py @register_check에서 수행. 표준 루프 N/A."""
    return None, "FM-*: 표준루프 N/A — 권위 상태는 frontmatter 체크"


def check_content_freshness(site: Path) -> tuple[bool, str]:
    """CF-01 — 신선도 검사는 content_freshness.py @register_check에서 수행. 표준 루프 N/A."""
    return None, "CF-01: 표준루프 N/A — 권위 상태는 content_freshness 체크"


@register_check("standard_compliance")
def check_standard_compliance(conn, blog_id: str) -> dict:
    """Run R01-R12 standard checks for a blog. Returns status dict.

    W7-a 보강 A: 순회 대상을 하드코딩 STANDARD_RULES → registry(rules.py)의
    RULES(UnifiedEntry 목록)로 전환. check_fn은 보강 B의 _resolve_check_fn으로
    동적 해석. 구경로(STANDARD_RULES/_CHECK_FUNCTIONS)는 전환 검증용 대조에만 사용.
    """
    from ops_dashboard.db import get_blog_detail

    # W7-a 보강 A: registry RULES를 실행의 단일 출처로 사용
    from ops_dashboard.registry.rules import RULES

    blog_info = get_blog_detail(conn, blog_id)
    if not blog_info:
        return {"status": "unknown", "detail": f"Blog {blog_id} not found in lifecycle"}

    blog_row = blog_info.get("blog", {})
    site = _find_hugo_root(blog_row)
    if not site:
        return {"status": "unknown", "detail": f"Site path not found for {blog_id}"}

    failures = []
    passes = []
    na = []  # V3(2026-08-21): 미적용(N/A) 규칙 — 집계 분모에서 제외
    exempt_map = _load_exempt_pipelines()

    for entry in RULES:
        rule_id = entry.id
        # Wave 1 (a): yaml exempt_pipelines 기반 N/A — check_fn 호출 skip, 분모 제외
        # R13 확장: stock/rap는 thumbnail-only 파이프라인 → featureimage 존재 시 N/A (시니어 결정 2026-08-24)
        if rule_id in exempt_map:
            _brand = (blog_row.get("brand") or "").lower()
            if _brand and _brand in exempt_map[rule_id]:
                if rule_id == "R13":
                    # featureimage 존재 여부 확인 — 1건이라도 R2 webp 면 exempt 유지, 없으면 일반 판정
                    try:
                        _has_fi = False
                        for _p in _recent_posts(site, 10, since=_today_start()) or _recent_posts(site, 10, since=None)[:1]:
                            _idx = _p / "index.md"
                            if _idx.exists():
                                _c = _read_file_safe(_idx)
                                _m = re.search(r"featureimage:\s*[\"']?([^\"'\n]+)[\"']?", _c)
                                if _m and _m.group(1).strip():
                                    _has_fi = True
                                    break
                        if not _has_fi:
                            # featureimage 없으면 exempt 미적용 — 일반 R13 검사 진행
                            pass
                        else:
                            na.append({"rule_id": rule_id, "severity": entry.severity,
                                       "detail": f"R13 exempt thumbnail-only pipeline={_brand} (featureimage exists)"})
                            continue
                    except Exception:
                        na.append({"rule_id": rule_id, "severity": entry.severity,
                                   "detail": f"R13 exempt thumbnail-only pipeline={_brand} (yaml exempt_pipelines)"})
                        continue
                else:
                    na.append({"rule_id": rule_id, "severity": entry.severity,
                               "detail": f"R04 exempt for pipeline={_brand} (yaml exempt_pipelines)"})
                    continue
        check_fn = _resolve_check_fn(entry.check_fn)
        if check_fn is None:
            # 보강 B: 해석 실패 규칙은 조용히 skip하지 않음 (로그 이미 출력됨).
            # 단, 해당 규칙의 실행을 건너뛸 수밖에 없으므로 failures에 기록하지 않고
            # passes에도 넣지 않는다 — 결과 집계에서 제외되어 총량 왜곡 방지.
            continue

        try:
            passed, detail = check_fn(site)
        except Exception as e:
            logger.error("Rule %s check failed for %s: %s", rule_id, blog_id, e)
            failures.append({"rule_id": rule_id, "severity": entry.severity,
                             "detail": f"Check error: {e}"})
            continue

        # V3 삼상태: passed is True → pass, False → fail, None → N/A(미적용)
        if passed is True:
            passes.append(rule_id)
        elif passed is False:
            failures.append({"rule_id": rule_id, "severity": entry.severity,
                             "detail": detail})
        else:
            na.append({"rule_id": rule_id, "severity": entry.severity,
                       "detail": detail})

    # fail→pass 전환 및 full-pass 조기 반환 모두에서 stale fail 행 scrub.
    # Bug B: 기존에는 scrub가 fail 경로 끝에만 있어, full-pass("if not failures")
    # 조기 반환 시 passes 전체의 기존 fail 개별 행이 남아 phantom(fail)이 됐다.
    # scrub를 조기 반환 앞으로 이동해 pass 규칙의 stale 행을 항상 제거한다.
    # 실제 fail 행(aggregate fail 목록의 rule)은 passes에 없으므로 삭제되지 않는다.
    if passes:
        _scrub_passed_rules(conn, blog_id, passes)

    # Determine overall status
    if not failures:
        return {"status": "pass",
                "detail": f"All {len(passes)} applicable rules passed ({len(na)} N/A)"}

    # Check for CRITICAL failures → 기록만, 실시간 푸시는 Part 3에서 전환
    # (2026-08-06 Part 1: 표준 위반 실시간 푸시 비활성화 — ops.db 기록 유지)
    critical_failures = [f for f in failures if f["severity"] == "CRITICAL"]
    if critical_failures:
        logger.warning(
            "CRITICAL standard violations for %s: %s",
            blog_id,
            [f["rule_id"] for f in critical_failures],
        )
        # Telegram push disabled — will be re-enabled as daily summary in Part 3

    detail_parts = [f"{f['rule_id']}({f['severity']}): {f['detail']}" for f in failures]
    # Phase 69 W3 — dual-write: 각 실패 규칙을 개별 행으로 추가 기록.
    # aggregate 행(standard_compliance)은 run_all_checks가 기록하므로 여기서는
    # 개별행(record_check_rule)만 추가한다. severity/action은 registry(rules.py)에서 조회.
    #
    # W6a.2 (Phase 69): 개별 행은 **활성 블로그만** 생성한다. 비활성/일시중지
    # (dead/paused/excluded) 블로그까지 개별 행을 기록하면 get_attention_items의
    # excluded_fail_checks가 개별 행만큼 부풀어(+70) excluded 오염이 발생한다.
    # get_attention_items의 활성 판정(config_status=='active' and
    # maintenance_status!='paused')과 동일 기준을 사용한다. aggregate 행은
    # 호출부(run_all_checks)가 비활성 블로그 포함 전부 기록하므로 excluded 판정에
    # 필요한 자유텍스트는 그대로 유지된다.
    _is_active = (
        blog_row.get("config_status") == "active"
        and blog_row.get("maintenance_status") != "paused"
    )
    if _is_active:
        _record_failed_rules(conn, blog_id, failures)
    return {
        "status": "fail",
        "detail": (
            f"{len(failures)}/{len(passes) + len(failures)} applicable rules failed "
            f"({len(na)} N/A): " + "; ".join(detail_parts[:5])
        ),
    }


def _record_failed_rules(conn, blog_id: str, failures: list) -> None:
    """실패한 각 규칙을 check_results에 개별 행으로 기록 (dual-write).

    동일 blog_id + rule_id(check_name)의 기존 행이 있으면 먼저 삭제 후 INSERT하여
    재검사 시마다 fail 행이 누적되는 것을 방지한다 (UPSERT: DELETE-then-INSERT).

    severity/action은 ops_dashboard/registry/rules.py(RULES)에서 조회한다 —
    레지스트리가 check 경로에서 처음 소비되는 지점. registry에 없는 규칙은 실패 목록의
    severity만 사용하고 action은 빈 문자열로 둔다 (조용한 실패 금지).
    """
    from ops_dashboard.db import record_check_rule
    from ops_dashboard.registry import get_entry

    for f in failures:
        rule_id = f["rule_id"]
        entry = get_entry(rule_id)
        severity = (entry.severity if entry else f.get("severity")) or "MAJOR"
        action = entry.action if entry else ""
        # 동일 (blog_id, check_name=rule_id) 기존 행 삭제 → 재검사 누적 방지
        conn.execute(
            "DELETE FROM check_results WHERE blog_id = ? AND check_name = ?",
            (blog_id, rule_id),
        )
        record_check_rule(
            conn,
            blog_id,
            rule_id=rule_id,
            status="fail",
            severity=severity,
            action=action,
            detail=f.get("detail", ""),
        )


def _scrub_passed_rules(conn, blog_id: str, passes: list[str]) -> None:
    """fail→pass 전환된 규칙의 기존 개별 fail 행을 삭제 (전환형 stale 청소).

    check_standard_compliance가 pass로 판정한 rule_id들에 대해,
    check_results에 남아 있는 status='fail' 개별 행을 삭제한다.

    안전 원칙:
      - passes 목록의 rule_id만 대상으로 함 (확실히 pass인 규칙만)
      - status='fail'인 행만 삭제 (pass/unknown 행은 보존)
      - passes가 비어있으면 아무것도 하지 않음
      - 실제 fail 행(aggregate fail 목록의 rule)은 passes에 없으므로 삭제되지 않음
    """
    if not passes:
        return
    for rule_id in passes:
        conn.execute(
            "DELETE FROM check_results WHERE blog_id = ? AND check_name = ? AND status = 'fail'",
            (blog_id, rule_id),
        )

# ---------------------------------------------------------------------------
# R13-R23: 2026-08-21 airports 품질 점검 규칙
# ---------------------------------------------------------------------------

# R19 금지 표현 블랙리스트
_R19_BANNED_PATTERNS = [
    re.compile(r"이\s*글은\s*AI로\s*작성", re.IGNORECASE),
    re.compile(r"AI가\s*작성한", re.IGNORECASE),
    re.compile(r"generated\s+by\s+AI", re.IGNORECASE),
    re.compile(r"AI-generated", re.IGNORECASE),
    re.compile(r"ChatGPT", re.IGNORECASE),
    re.compile(r"GPT-4", re.IGNORECASE),
    # 네거티브 lookbehind: 하이픈/구두점/단어 문자 뒤의 'Claude'는
    # 성씨(Marie-Claude 등)로 판단하여 제외. 단독 'Claude'(AI 모델명)만 잡음.
    re.compile(r"(?<![-.\w])Claude\b", re.IGNORECASE),
    re.compile(r"\bLLM\b", re.IGNORECASE),
]

# R20 분류코드 원문 패턴 (large_airport, medium_airport, small_airport, IATA 코드 등)
_R20_CLASSIFICATION_CODES = [
    re.compile(r"\b(large_airport|medium_airport|small_airport|closed_airport)\b"),
    re.compile(r"\b(CIVIL|MILITARY|JOINT_USE|PRIVATE)\b(?=\s+airport)"),
]

# R15 보일러플레이트 제외 패턴 (네비게이션, 푸터, CTA 등)
# X1(2026-08-21): R15 정직단어수 = 렌더 본문에서 보일러플레이트 제외 후 재계산.
# 5개 범주: (1)공통 팁 문단 (2)금지표현 문장 (3)좌표·고도·IATA/ICAO 재서술
#          (4)출처·라이선스 푸터 (5)Route Snapshot 면책 문장
_R15_BOILERPLATE_PATTERNS = [
    # 기존 내비/푸터
    re.compile(r"^(?:Read more|더 읽기|바로가기|Click here|홈으로|목록으로)\s*$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^(?:Related posts|관련 글|이전 글|다음 글)\s*$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^(?:Share|공유|Tweet|Pin)\s*$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^(?:Subscribe|구독|Newsletter|뉴스레터)\s*$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"©\s*\d{4}", re.IGNORECASE),
    re.compile(r"All rights reserved", re.IGNORECASE),
    # (2) 금지 표현 문장 (R19 목록과 동일) — AI 생성 흔적
    re.compile(r"\b(?:ai[- ]?generated|chatgpt|gpt[- ]?4|claude|llm)\b", re.IGNORECASE),
    # (3) 좌표·고도·IATA/ICAO 재서술 (템플릿 filler)
    re.compile(r"\belevation\b", re.IGNORECASE),
    re.compile(r"\biata\b", re.IGNORECASE),
    re.compile(r"\bicao\b", re.IGNORECASE),
    re.compile(r"coordinates?\b", re.IGNORECASE),
    re.compile(r"key gateway for its region", re.IGNORECASE),
    re.compile(r"multiple runways and terminals", re.IGNORECASE),
    re.compile(r"large airport this facility", re.IGNORECASE),
    re.compile(r"regional context", re.IGNORECASE),
    # (4) 출처·라이선스 푸터
    re.compile(r"\blicense\b", re.IGNORECASE),
    re.compile(r"\bcc by\b", re.IGNORECASE),
    re.compile(r"출처", re.IGNORECASE),
    re.compile(r"라이선스", re.IGNORECASE),
    # (5) Route Snapshot 면책 문장
    re.compile(r"route snapshot", re.IGNORECASE),
    re.compile(r"면책", re.IGNORECASE),
    re.compile(r"disclaimer", re.IGNORECASE),
    re.compile(r"정확성.*보장", re.IGNORECASE),
    # (1) 공통 팁 문단 (STN↔LHR 거의 동일)
    re.compile(r"practical tips", re.IGNORECASE),
    re.compile(r"유용한 팁", re.IGNORECASE),
    re.compile(r"여행 팁", re.IGNORECASE),
    # 테마 크롬 누수 차단 (본문 텍스트에 섞인 내비/출처/메타)
    re.compile(r"skip to main content", re.IGNORECASE),
    re.compile(r"airport data:", re.IGNORECASE),
    re.compile(r"route data:", re.IGNORECASE),
    re.compile(r"ourairports", re.IGNORECASE),
    re.compile(r"openflights", re.IGNORECASE),
    re.compile(r"scheduled service flag", re.IGNORECASE),
    re.compile(r"official website is", re.IGNORECASE),
]


def _strip_frontmatter(content: str) -> str:
    """마크다운에서 YAML frontmatter 제거."""
    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            return content[end + 3:].lstrip("\n")
    return content


def _strip_html(html: str) -> str:
    """HTML 태그 제거."""
    return re.sub(r"<[^>]+>", " ", html or "")


def _word_count(text: str) -> int:
    """텍스트의 단어 수 계산 (공백 기준 분리)."""
    return len(text.split())


def _check_r13(site: Path) -> tuple[bool, str]:
    """R13: 본문 삽입이미지 최소 1장."""
    posts = _recent_posts(site, 10, since=_today_start())
    if not posts:
        return None, "포스트 없음 - 검사 대상 없음 (N/A)"

    no_image_posts = []
    for post_dir in posts:
        idx = post_dir / "index.md"
        if not idx.exists():
            continue
        content = _read_file_safe(idx)
        body = _strip_frontmatter(content)
        has_img = (
            bool(re.search(r"<img\s", body))
            or bool(re.search(r"!\[[^\]]*\]\(", body))
            or bool(re.search(r"\{\{<\s*(?:figure|img|image|thumbnail)\b", body))
        )
        if not has_img:
            no_image_posts.append(post_dir.name)

    if no_image_posts:
        return False, (
            f"삽입이미지 0장 포스트 {len(no_image_posts)}건 / {len(posts)}건: "
            + ", ".join(no_image_posts[:5])
        )
    return True, f"최근 {len(posts)}건 전부 삽입이미지 1장 이상 보유"


# V2(2026-08-21): R14/R15는 렌더링 본문(JSON-LD wordCount) 기준 측정.
# 소스 마크다운 토큰수는 렌더링과 달라(PEK 소스408/렌더374 등) 오통과 유발 — 수정.
_JSONLD_WC_RE = re.compile(r'"wordCount"\s*:\s*"?(\d+)"?')


def _rendered_word_count(site: Path, slug: str) -> int | None:
    """빌드본 public/posts/{slug}/index.html 의 JSON-LD wordCount (Hugo .WordCount).
    빌드본 부재 시 None — 호출자는 소스 기준값으로 폴백.
    """
    p = site / "public" / "posts" / slug / "index.html"
    if not p.exists():
        return None
    try:
        html = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    m = _JSONLD_WC_RE.search(html)
    return int(m.group(1)) if m else None


def _rendered_honest_word_count(site: Path, slug: str) -> int | None:
    """렌더 본문에서 보일러플레이트(5범주) 제외 후 정직 단어수.
    public/posts/{slug}/index.html 기준. 부재 시 None(소스 폴백).
    """
    p = site / "public" / "posts" / slug / "index.html"
    if not p.exists():
        return None
    try:
        html = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    html = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.IGNORECASE)
    html = re.sub(r"<style[\s\S]*?</style>", " ", html, flags=re.IGNORECASE)
    html = re.sub(r"<nav[\s\S]*?</nav>", " ", html, flags=re.IGNORECASE)
    html = re.sub(r"<header[\s\S]*?</header>", " ", html, flags=re.IGNORECASE)
    html = re.sub(r"<footer[\s\S]*?</footer>", " ", html, flags=re.IGNORECASE)
    text = _strip_html(html)
    # 문장 분리(마침표/느낌표/물음표 뒤 공백 또는 줄바꿈)
    sentences = re.split(r"(?<=[\.\!\?])\s+|\n+", text)
    kept = []
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        if any(pat.search(s) for pat in _R15_BOILERPLATE_PATTERNS):
            continue
        kept.append(s)
    return _word_count(" ".join(kept))


def _check_r14(site: Path) -> tuple[bool, str]:
    """R14: 렌더 본문 wordCount >= 400 (JSON-LD 기준)."""
    posts = _recent_posts(site, 10, since=_today_start())
    if not posts:
        return None, "포스트 없음 - 검사 대상 없음 (N/A)"

    short_posts = []
    for post_dir in posts:
        idx = post_dir / "index.md"
        if not idx.exists():
            continue
        slug = post_dir.name
        wc = _rendered_word_count(site, slug)
        fallback = False
        if wc is None:
            # 빌드본 부재 → 소스 기준 (마크다운 토큰수, 오차 있음)
            content = _read_file_safe(idx)
            wc = _word_count(_strip_html(_strip_frontmatter(content)))
            fallback = True
        if wc < 400:
            short_posts.append(f"{slug}({wc}{'·소스기준' if fallback else ''})")

    if short_posts:
        return False, (
            f"wordCount < 400 포스트 {len(short_posts)}건 / {len(posts)}건: "
            + ", ".join(short_posts[:5])
        )
    return True, f"최근 {len(posts)}건 전부 wordCount >= 400"


def _check_r15(site: Path) -> tuple[bool, str]:
    """R15: 정직 단어수(보일러플레이트 제외) >= 400.

    R14와 구분: R14는 렌더 본문 총단어수(JSON-LD), R15는 보일러플레이트
    제외 정직 단어수. 두 값이 같으면 게이트 소실 → 구현 실패.
    """
    posts = _recent_posts(site, 10, since=_today_start())
    if not posts:
        return None, "포스트 없음 - 검사 대상 없음 (N/A)"

    short_posts = []
    for post_dir in posts:
        idx = post_dir / "index.md"
        if not idx.exists():
            continue
        slug = post_dir.name
        wc = _rendered_honest_word_count(site, slug)
        fallback = False
        if wc is None:
            # 빌드본 부재 → 소스 기준 보일러플레이트 제외
            content = _read_file_safe(idx)
            body_text = _strip_html(_strip_frontmatter(content))
            sentences = re.split(r"(?<=[\.\!\?])\s+|\n+", body_text)
            kept = [s for s in sentences if s.strip()
                    and not any(p.search(s) for p in _R15_BOILERPLATE_PATTERNS)]
            wc = _word_count(" ".join(kept))
            fallback = True
        if wc < 400:
            short_posts.append(f"{slug}({wc}{'·소스기준' if fallback else ''})")

    if short_posts:
        return False, (
            f"정직 단어수 < 400 포스트 {len(short_posts)}건 / {len(posts)}건: "
            + ", ".join(short_posts[:5])
        )
    return True, f"최근 {len(posts)}건 전부 정직 단어수 >= 400"


def _check_r16(site: Path) -> tuple[bool, str]:
    """R16: og:image(featureimage 또는 og_image) 존재."""
    posts = _recent_posts(site, 10, since=_today_start())
    if not posts:
        return None, "포스트 없음 - 검사 대상 없음 (N/A)"

    missing = []
    for post_dir in posts:
        idx = post_dir / "index.md"
        if not idx.exists():
            continue
        content = _read_file_safe(idx)
        has_og = (
            bool(re.search(r"featureimage:\s*\S", content))
            or bool(re.search(r"og_image:\s*\S", content))
        )
        if not has_og:
            missing.append(post_dir.name)

    if missing:
        return False, (
            f"og:image 누락 포스트 {len(missing)}건 / {len(posts)}건: "
            + ", ".join(missing[:5])
        )
    return True, f"최근 {len(posts)}건 전부 og:image 존재"


def _rendered_html_for_post(site: Path, slug: str):
    """실제 발행 페이지 HTML을 읽어 반환. 부재 시 None.

    permalinks 설정에 따라 위치가 다르다:
      - 기본: public/posts/{slug}/index.html
      - posts="/:slug/": public/{slug}/index.html
    둘 다 시도하고, 없으면 public/**/{slug}/index.html 를 glob 한다.
    """
    candidates = [
        site / "public" / "posts" / slug / "index.html",
        site / "public" / slug / "index.html",
    ]
    for p in candidates:
        if p.exists():
            try:
                return p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                return None
    try:
        hits = list(site.glob(f"public/**/{slug}/index.html"))
        if hits:
            return hits[0].read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    return None


def _check_r17(site: Path) -> tuple[bool, str]:
    """R17: twitter:card = summary_large_image."""
    posts = _recent_posts(site, 10, since=_today_start())
    if not posts:
        return None, "포스트 없음 - 검사 대상 없음 (N/A)"

    wrong = []
    for post_dir in posts:
        idx = post_dir / "index.md"
        if not idx.exists():
            continue
        content = _read_file_safe(idx)
        # frontmatter에서 twitter_card 또는 params.twitter_card 확인
        tc_match = re.search(r"twitter[_:]?card:\s*[\"']?([^\s\"'\n]+)", content, re.IGNORECASE)
        if tc_match:
            val = tc_match.group(1).strip('"\'')
            if val != "summary_large_image":
                wrong.append(f"{post_dir.name}({val})")
            continue
        # twitter:card 없으면 params下面에서 확인
        params_match = re.search(r"\[params\]\s*\ntwitter[_:]?card\s*=\s*[\"']?([^\s\"'\n]+)", content, re.IGNORECASE)
        if params_match:
            val = params_match.group(1).strip('"\'')
            if val != "summary_large_image":
                wrong.append(f"{post_dir.name}({val})")
            continue
        # 소스 FM/params에 없으면 렌더된 HTML의 메타 확인 (extend-head 주입 등)
        rendered = _rendered_html_for_post(site, post_dir.name)
        if rendered is not None:
            _tcs = re.findall(
                r'<meta\s+name=["\']?twitter:card["\']?\s+content=["\']?([^"\'>\s]*)["\']?',
                rendered, re.IGNORECASE)
            if any(t.strip().lower() == "summary_large_image" for t in _tcs):
                continue
        wrong.append(f"{post_dir.name}(없음)")

    if wrong:
        return False, (
            f"twitter:card 비일치 {len(wrong)}건 / {len(posts)}건: "
            + ", ".join(wrong[:5])
        )
    return True, f"최근 {len(posts)}건 전부 twitter:card=summary_large_image"


def _check_r18(site: Path) -> tuple[bool, str]:
    """R18: 생성 초안과 배포본 해시 일치.

    local index.md의 해시와 ops.db의 배포 기록 해시를 비교.
    배포 기록이 없으면 pass(초안 상태).
    """
    import hashlib
    try:
        from ops_dashboard.db import get_conn
        conn = get_conn()
        rows = conn.execute(
            "SELECT blog_id, detail FROM check_results WHERE check_name = 'deploy_hash'"
        ).fetchall()
        conn.close()
    except Exception:
        return None, "배포 해시 테이블 없음 - R18 검사 불가 (N/A)"

    if not rows:
        return None, "배포 해시 기록 없음 - 검사 대상 없음 (N/A)"

    mismatches = []
    for row in rows:
        detail = row[1] if isinstance(row, (tuple, list)) else row.get("detail", "")
        # detail 형식: "slug=xxx hash=abc123"
        slug_m = re.search(r"slug=(\S+)", detail)
        hash_m = re.search(r"hash=(\S+)", detail)
        if not slug_m or not hash_m:
            continue
        slug = slug_m.group(1)
        stored_hash = hash_m.group(1)
        idx = site / "content" / "posts" / slug / "index.md"
        if not idx.exists():
            continue
        content = _read_file_safe(idx)
        local_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        if local_hash != stored_hash:
            mismatches.append(slug)

    if mismatches:
        return False, (
            f"해시 불일치 {len(mismatches)}건: " + ", ".join(mismatches[:5])
        )
    return True, "전부 해시 일치"


def _check_r19(site: Path) -> tuple[bool, str]:
    """R19: 금지 표현 블랙리스트 0건."""
    posts = _recent_posts(site, 10, since=_today_start())
    if not posts:
        return None, "포스트 없음 - 검사 대상 없음 (N/A)"

    violations = []
    for post_dir in posts:
        idx = post_dir / "index.md"
        if not idx.exists():
            continue
        content = _read_file_safe(idx)
        body = _strip_frontmatter(content)
        for pat in _R19_BANNED_PATTERNS:
            m = pat.search(body)
            if m:
                violations.append(f"{post_dir.name}:{m.group(0)[:30]}")
                break  # 포스트당 1건만 기록

    if violations:
        return False, (
            f"금지 표현 위반 {len(violations)}건 / {len(posts)}건: "
            + "; ".join(violations[:5])
        )
    return True, f"최근 {len(posts)}건 전부 금지 표현 0건"


def _check_r20(site: Path) -> tuple[bool, str]:
    """R20: 분류코드 원문 노출 0건."""
    posts = _recent_posts(site, 10, since=_today_start())
    if not posts:
        return None, "포스트 없음 - 검사 대상 없음 (N/A)"

    violations = []
    for post_dir in posts:
        idx = post_dir / "index.md"
        if not idx.exists():
            continue
        content = _read_file_safe(idx)
        body = _strip_frontmatter(content)
        for pat in _R20_CLASSIFICATION_CODES:
            m = pat.search(body)
            if m:
                violations.append(f"{post_dir.name}:{m.group(0)[:30]}")
                break

    if violations:
        return False, (
            f"분류코드 노출 {len(violations)}건 / {len(posts)}건: "
            + "; ".join(violations[:5])
        )
    return True, f"최근 {len(posts)}건 전부 분류코드 원문 노출 0건"


def _check_r21(site: Path) -> tuple[bool, str]:
    """R21: 동일 포스트 내 문단 중복률 상한."""
    DUPLICATION_THRESHOLD = 0.3  # 30% 이상 중복 시 fail

    posts = _recent_posts(site, 10, since=_today_start())
    if not posts:
        return None, "포스트 없음 - 검사 대상 없음 (N/A)"

    dup_posts = []
    for post_dir in posts:
        idx = post_dir / "index.md"
        if not idx.exists():
            continue
        content = _read_file_safe(idx)
        body = _strip_frontmatter(content)
        body_text = _strip_html(body)

        # 문단 분리 (빈 줄 기준)
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body_text) if len(p.strip()) > 50]
        if len(paragraphs) < 2:
            continue

        unique = set(paragraphs)
        dup_rate = 1.0 - (len(unique) / len(paragraphs))
        if dup_rate >= DUPLICATION_THRESHOLD:
            dup_posts.append(f"{post_dir.name}({dup_rate:.0%})")

    if dup_posts:
        return False, (
            f"문단 중복률 상한 초과 {len(dup_posts)}건 / {len(posts)}건: "
            + ", ".join(dup_posts[:5])
        )
    return True, f"최근 {len(posts)}건 전부 문단 중복률 정상"


def _check_r22(site: Path) -> tuple[bool, str]:
    """R22: 배치 내 robots 값 일관성."""
    posts = _recent_posts(site, 10, since=_today_start())
    if not posts:
        return None, "포스트 없음 - 검사 대상 없음 (N/A)"

    robots_values = {}  # slug -> robots value
    for post_dir in posts:
        idx = post_dir / "index.md"
        if not idx.exists():
            continue
        content = _read_file_safe(idx)
        # frontmatter에서 robots 값 확인
        robots_match = re.search(r"robots:\s*[\"']?([^\s\"'\n]+)", content, re.IGNORECASE)
        if robots_match:
            robots_values[post_dir.name] = robots_match.group(1).strip('"\'')
        else:
            robots_values[post_dir.name] = "index,follow"  # 기본값

    if not robots_values:
        return None, "robots 값 없음 - 검사 대상 없음 (N/A)"

    # 값 분포 확인
    from collections import Counter
    value_counts = Counter(robots_values.values())
    most_common_val, most_common_count = value_counts.most_common(1)[0]

    inconsistent = [s for s, v in robots_values.items() if v != most_common_val]
    if inconsistent:
        return False, (
            f"robots 불일치 {len(inconsistent)}건 (기준={most_common_val}): "
            + ", ".join(inconsistent[:5])
        )
    return True, f"전부 robots={most_common_val} 일관"


def _check_r23(site: Path) -> tuple[bool, str]:
    """R23: 배포 시점 사람 승인 상태 기록 존재."""
    try:
        from ops_dashboard.db import get_conn
        conn = get_conn()
        #最近 배포 기록 확인
        rows = conn.execute(
            "SELECT blog_id, status, detail FROM publish_log "
            "WHERE blog_id LIKE '%airport%' ORDER BY published_at DESC LIMIT 5"
        ).fetchall()
        conn.close()
    except Exception:
        return None, "배포 테이블 없음 - R23 검사 불가 (N/A)"

    if not rows:
        return None, "배포 기록 없음 - 검사 대상 없음 (N/A)"

    no_approval = []
    for row in rows:
        blog_id = row[0] if isinstance(row, (tuple, list)) else row.get("blog_id", "")
        detail = row[2] if isinstance(row, (tuple, list)) else row.get("detail", "")
        if "approved_by" not in detail.lower() and "승인" not in detail:
            no_approval.append(blog_id)

    if no_approval:
        return False, (
            f"승인 기록 누락 {len(no_approval)}건: " + ", ".join(no_approval[:5])
        )
    return True, "전부 배포 승인 기록 존재"

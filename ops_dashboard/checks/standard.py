"""ops_dashboard.checks.standard — 표준 준수 검사 (R01-R12)

Blowfish/AdSense 표준 규칙을 blog별로 검사하고,
CRITICAL 위반 발견 시 텔레그램 알림을 보낸다.
"""
from __future__ import annotations

import logging
import os
import re
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
    "layouts/partials/extend-head.html",
    "layouts/partials/extend_head.html",
    "layouts/partials/adsense",
    "layouts/partials/related.html",
    "layouts/partials/head/custom.html",
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
    """R04: GA4 + mobile correction CSS in extend_head.html."""
    for partial_dir in ("layouts/partials",):
        for name in ("extend_head.html", "extend-head.html"):
            p = site / partial_dir / name
            if p.exists():
                content = _read_file_safe(p)
                has_ga = "gtag" in content or "GA4" in content or "google-analytics" in content
                has_mobile = "max-width" in content or "font-size" in content or "mobile" in content.lower()
                if has_ga and has_mobile:
                    return True, "extend_head: GA4 + mobile CSS found"
                missing = []
                if not has_ga:
                    missing.append("GA4")
                if not has_mobile:
                    missing.append("mobile CSS")
                return False, f"extend_head: missing {', '.join(missing)}"
    return False, "No extend_head.html found"


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


def _check_thumbnail_01(site: Path) -> tuple[bool, str]:
    """THUMBNAIL-01: 최근 포스트의 featureimage가 R2 업로드 + webp인지 검사.

    Hugo 사이트 content/posts/ 내 최근 10개 포스트의 index.md frontmatter에서
    featureimage를 추출해 다음 조건을 전부 만족하는지 확인:
      - URL이 R2 도메인에 호스팅됨 (pub-<hash>.r2.dev 패턴)
      - URL이 .webp로 끝남
    조건 미충족 URL이 1건이라도 있으면 fail, 전부 충족 또는 featureimage 없는
    포스트만 있으면 pass. featureimage가 아예 없는 포스트 수는 detail에 집계한다.
    """
    posts_dir = site / "content" / "posts"
    if not posts_dir.is_dir():
        return False, "content/posts/ 디렉토리 없음 — 썸네일 검사 대상 아님"

    posts = sorted(posts_dir.iterdir())[-10:]  # 최근 10개 (디렉토리명 역순 아님 — 알파벳순 최근)
    if not posts:
        return True, "포스트 없음 — 검사 대상 없음 (pass)"

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

    total_checked = valid_count + len(invalid_entries)
    if total_checked == 0:
        return True, f"최근 {len(posts)}개 포스트 전부 featureimage 없음 (pass — 썸네일 위반 아님)"

    if invalid_entries:
        detail = (
            f"썸네일 위반 {len(invalid_entries)}건 / 검사 {total_checked}건 "
            f"(유효 {valid_count}, 누락 {missing_count}): "
            + "; ".join(invalid_entries[:3])
        )
        if len(invalid_entries) > 3:
            detail += f" 외 {len(invalid_entries) - 3}건"
        return False, detail
    return True, (
        f"최근 {total_checked}건 전부 R2+webp 충족 (누락 {missing_count}건 — featureimage 없음)"
    )


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

    for entry in RULES:
        rule_id = entry.id
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

        if passed:
            passes.append(rule_id)
        else:
            failures.append({"rule_id": rule_id, "severity": entry.severity,
                             "detail": detail})

    # Determine overall status
    if not failures:
        return {"status": "pass", "detail": f"All {len(passes)} rules passed"}

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
        "detail": f"{len(failures)}/{len(passes) + len(failures)} rules failed: " + "; ".join(detail_parts[:5]),
    }


def _record_failed_rules(conn, blog_id: str, failures: list) -> None:
    """실패한 각 규칙을 check_results에 개별 행으로 기록 (dual-write).

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
        record_check_rule(
            conn,
            blog_id,
            rule_id=rule_id,
            status="fail",
            severity=severity,
            action=action,
            detail=f.get("detail", ""),
        )

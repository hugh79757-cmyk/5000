"""R04: extend_head.html 에 GA4 gtag + 모바일 보정 CSS 추가/검증."""

from __future__ import annotations

from pathlib import Path

from shared.autofix.core import logger


def fix_r04_ga4(site: Path, ga4_id: str | None) -> tuple[bool, str]:
    if ga4_id is None:
        return False, "GA4 ID 없음 — skip (GA4 불명 큐)"

    for name in ("extend_head.html", "extend-head.html"):
        p = site / "layouts" / "partials" / name
        if p.exists():
            content = p.read_text(encoding="utf-8", errors="replace")
            if f"gtag('config', '{ga4_id}')" in content and "@media" in content:
                return True, f"extend_head.html: GA4({ga4_id}) + mobile CSS 이미 있음"

    target_name = "extend_head.html"
    target = site / "layouts" / "partials" / target_name
    if not target.exists():
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

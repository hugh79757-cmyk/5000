"""R06: in-article.html data-ad-format=auto → fluid+in-article 교체."""

from __future__ import annotations

import re
from pathlib import Path

from shared.autofix.core import logger


def fix_r06_fluid(site: Path) -> tuple[bool, str]:
    p = site / "layouts" / "partials" / "adsense" / "in-article.html"
    if not p.exists():
        return False, "in-article.html 없음 — skip"

    content = p.read_text(encoding="utf-8", errors="replace")
    if 'data-ad-format="fluid"' in content and 'data-ad-layout="in-article"' in content:
        return True, "in-article.html: 이미 fluid+in-article"

    fixed = re.sub(
        r'data-ad-format\s*=\s*"auto"',
        'data-ad-format="fluid"',
        content
    )
    if 'data-ad-layout="in-article"' not in fixed:
        fixed = re.sub(
            r'(<ins[^>]*?data-ad-client=)"',
            r'\1 data-ad-layout="in-article" data-ad-format="fluid"',
            fixed,
            count=1
        )
        fixed = re.sub(
            r'\s*data-ad-format="fluid"\s*data-ad-layout="in-article"\s*data-ad-layout="in-article"',
            ' data-ad-layout="in-article" data-ad-format="fluid"',
            fixed
        )

    if "push({})" in fixed:
        fixed = re.sub(
            r'(</div>)\s*<script>\s*\(adsbygoogle\s*=\s*window\.adsbygoogle\s*\|\|\s*\[\]\)\s*\.push\(\{\}\);\s*</script>',
            r'</div>\n<script>(adsbygoogle = window.adsbygoogle || []).push({{}});</script>',
            fixed
        )
        div_close_idx = fixed.rfind("</div>")
        script_idx = fixed.find("<script>(adsbygoogle")
        if script_idx > 0 and div_close_idx > 0 and script_idx > div_close_idx:
            pass
        elif script_idx > 0 and div_close_idx > 0 and script_idx < div_close_idx:
            script_tag = re.search(r'<script>\(adsbygoogle[^<]+</script>', fixed)
            if script_tag:
                st = script_tag.group(0)
                fixed = fixed[:script_idx] + fixed[script_idx + len(st):]
                insert_pos = fixed.find("</div>") + len("</div>")
                fixed = fixed[:insert_pos] + "\n" + st + fixed[insert_pos:]

    p.write_text(fixed, encoding="utf-8")
    return True, "in-article.html: auto→fluid+in-article 교체"

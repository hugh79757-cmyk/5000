"""R08: single.html 에서 .Lead/.Description 제거."""

from __future__ import annotations

import re
from pathlib import Path

from shared.autofix.core import logger


def fix_r08_lead(site: Path) -> tuple[bool, str]:
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
        if stripped.startswith("<!--") or stripped.startswith("//"):
            new_lines.append(line)
            continue
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

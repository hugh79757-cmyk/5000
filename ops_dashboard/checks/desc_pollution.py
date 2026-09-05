"""ops_dashboard.checks.desc_pollution — desc 오염(related 블록 유입) 탐지.

2026-09-05 SEAP+RAP 감사 유래 (ERR-023). rap 792건 desc 오염이
대시보드 0탐지 상태로 발견됨 — desc 라인 내용 검사 체크가 없었음.

대시보드 기존 체크는 최근 7일 포스트만 읽지만(_read_post_files),
desc 오염은 과거 유물이 대부분이므로 본 체크는 무윈도우 전수 스캔.
(perf: rglob *.md 전부 읽음 — rap1~5 합계 ~2,900건, 수 초 내 완료)

탐지만 수행 (파일 수정/배포 금지 — 룩북 ERR-023 수정 절차 참조).
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

from ops_dashboard.checks import register_check
from ops_dashboard.checks.content_integrity import _find_site_path

logger = logging.getLogger(__name__)

# desc 오염 마커 — related 블록/'함께 읽으면' 조각이 desc에 유입된 형태
# (fix_rap_desc_pollution.py MARKERS와 동일 기준이되 <strong> 제외 —
#  senior-hugo 등에서 인라인 <strong> 강조가 정상 사용됨. 실측 근거 2026-09-05:
#  RAP 오염형 = '함께 읍으면 좋은 글</strong> - [slug](/posts/...)' 조합이므로
#  '함께 읽으면' + '](/posts/' 두 마커로 충분)
_POLLUTION_MARKERS = ("함께 읽으면", "](/posts/")
# desc 라인 추출 (folded scalar 시작 라인만 — 값은 마커 여부 판정에 충분)
_DESC_RE = re.compile(r'^description:\s*["\']?(.*)$', re.MULTILINE)


def _desc_is_polluted(desc_value: str) -> str | None:
    """desc 값에 마커 포함 시 증거 조각 반환, 아니면 None."""
    for marker in _POLLUTION_MARKERS:
        if marker in desc_value:
            return desc_value[:60]
    return None


@register_check("desc_pollution")
def check_desc_pollution(conn, blog_id: str) -> dict:
    """ERR-023 desc 오염 탐지 (DETECT-ONLY, 무윈도우 전수 스캔).

    Hugo 계열 블로그 전부 적용 (desc는 공통 frontmatter 키).
    Blogger 플랫폼(blog_id 끝 -blogger)은 site_path 없음 → unknown.
    """
    if blog_id.endswith("-blogger"):
        return {"status": "unknown", "detail": "Blogger 플랫폼 — Hugo 체크 미적용 (ERR-030)",
                "evidence_url": ""}
    site = _find_site_path(conn, blog_id)
    if not site:
        return {"status": "unknown", "detail": "site_path 미확인", "evidence_url": ""}
    posts_dir = site / "content" / "posts"
    if not posts_dir.exists():
        return {"status": "unknown", "detail": "posts 디렉터리 없음", "evidence_url": ""}

    hits: list[str] = []
    scanned = 0
    for md_file in posts_dir.rglob("*.md"):
        if md_file.name == "_index.md":
            continue
        scanned += 1
        content = md_file.read_text(encoding="utf-8", errors="replace")
        m = _DESC_RE.search(content)
        if not m:
            continue
        evidence = _desc_is_polluted(m.group(1))
        if evidence:
            hits.append(f"{md_file.parent.name}: {evidence}")
        if len(hits) >= 5:
            break

    if hits:
        return {"status": "fail",
                "detail": f"desc 오염 {len(hits)}건+ (전수 {scanned}건 스캔) — {hits[0]}",
                "evidence_url": ""}
    return {"status": "pass", "detail": f"desc 오염 0건 (전수 {scanned}건 스캔)",
            "evidence_url": ""}

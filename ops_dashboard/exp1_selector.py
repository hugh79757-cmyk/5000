"""ops_dashboard.exp1_selector — Exp1 대상 선정 보강 (stale/거짓양성 필터).

Exp1 Round 1 교훈:
- stale: check_results=fail 이나 소스는 이미 준수 → 재검사로 제외
- 거짓양성: content_integrity._parse_frontmatter가 block-style tags 미파싱 →
  python-frontmatter 라이브러리로 교차검증하여 제외

선정은 READ_ONLY (파일 수정/DB UPDATE 없음). recheck.py import만 사용.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import frontmatter

from ops_dashboard.checks.content_integrity import _find_site_path
from ops_dashboard.db import get_conn
from ops_dashboard.recheck import targeted_recheck

# 체커 파서 거짓양성 영향 블로그는 Exp2에서만 처리 → 선정에서 제외
PARSER_BUG_BLOGS = frozenset({"adventure-hugo"})

# gate_filtered 카테고리 (호텔/공항/식당 등) — 하위문자열 매칭
GATE_FILTERED_SUBSTR = ("hotel", "airport", "restaurant")

# Exp1 대상 SAFE check_name 집합
SAFE_CHECKERS = frozenset({
    "FM-DRAFT", "FM-MISSINGKEYS", "FM-FEATUREIMAGE", "FM-THUMBNAIL",
})

SEVERITY_ALLOWED = ("MINOR",)


@dataclass
class Candidate:
    blog_id: str
    post_path: str
    check_name: str
    pre_recheck_status: str  # "FAIL" (실제 위반) / "PASS" (stale)
    eligible: bool


def _all_post_files(site: Path) -> list[Path]:
    posts_dir = site / "content" / "posts"
    if not posts_dir.exists():
        return []
    return [p for p in posts_dir.rglob("*.md")]


def _is_gate_filtered(blog_id: str) -> bool:
    b = blog_id.lower()
    return any(s in b for s in GATE_FILTERED_SUBSTR)


def _fm_missingkeys_false_positive(content: str) -> bool:
    """python-frontmatter로 tags 실제 존재 확인 → 거짓양성 여부 반환."""
    try:
        fm = frontmatter.loads(content)
        tags = fm.metadata.get("tags")
        return bool(tags)  # tags 있으면 체커가 블록리스트 못 읽은 거짓양성
    except Exception:
        return False


def select_exp1_candidates(
    count: int,
    checkers: Optional[list[str]] = None,
    conn=None,
) -> list[Candidate]:
    """check_results fail 행 중 실제 위반만 선별 (stale/거짓양성 제외).

    - READ_ONLY: 파일 수정/DB UPDATE 없음
    - post_path가 check_results에 없으므로, blog site를 열거하여 재검사
    """
    if conn is None:
        conn = get_conn()
    checkers = checkers or list(SAFE_CHECKERS)

    rows = conn.execute(
        "SELECT DISTINCT blog_id, check_name FROM check_results "
        "WHERE status='fail' AND check_name IN ({}) AND severity IN ({})".format(
            ",".join("?" * len(checkers)), ",".join("?" * len(SEVERITY_ALLOWED))
        ),
        list(checkers) + list(SEVERITY_ALLOWED),
    ).fetchall()

    candidates: list[Candidate] = []
    for blog_id, check_name in rows:
        if blog_id in PARSER_BUG_BLOGS:
            continue
        if _is_gate_filtered(blog_id):
            continue
        site = _find_site_path(conn, blog_id)
        if not site:
            continue
        for md in _all_post_files(site):
            content = md.read_text(encoding="utf-8", errors="replace")
            res = targeted_recheck(blog_id, str(md), check_name)
            if res.passed:
                continue  # stale → 제외
            if check_name == "FM-MISSINGKEYS" and _fm_missingkeys_false_positive(content):
                continue  # 체커 거짓양성 → 제외
            candidates.append(Candidate(
                blog_id=blog_id, post_path=str(md),
                check_name=check_name, pre_recheck_status="FAIL", eligible=True,
            ))
            break  # blog당 1건
        if len(candidates) >= count:
            break
    return candidates

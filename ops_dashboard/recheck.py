"""ops_dashboard.recheck — BLK-4 TARGETED_RECHECK.

단일 포스트 + 단일 rule_id(FM-*) 정밀 재검사.
기존 checker(frontmatter.py)의 검출 로직을 import 재사용 (수정 금지).
전체 블로그 스캔 금지 — post_path 하나만 대상.
DB 기록 금지 — RecheckResult 반환만 (기록은 Phase 3 BLK-3 sidecar 범위).
"""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from ops_dashboard.checks.content_integrity import _parse_frontmatter
from ops_dashboard.checks.frontmatter import (
    REQUIRED_KEYS,
    _featureimage_bad,
    _fm_url_bad,
)

logger = logging.getLogger(__name__)

# rule_id(FM-*) → 단일 포스트 frontmatter 검사 fn
# fn(fm: dict) -> (triggered: bool, detail: str | None)
def _eval_fm_draft(fm: dict) -> tuple[bool, str | None]:
    draft = (fm.get("draft") or "").strip().lower()
    return (draft == "true"), ("draft:true" if draft == "true" else None)


def _eval_fm_missingkeys(fm: dict) -> tuple[bool, str | None]:
    missing = [k for k in REQUIRED_KEYS if not (fm.get(k) or "").strip()]
    return (bool(missing)), (f"누락 {missing}" if missing else None)


def _eval_fm_featureimage(fm: dict) -> tuple[bool, str | None]:
    feat = (fm.get("featureimage") or "").strip()
    if not feat:
        return False, None
    return _featureimage_bad(feat)


def _eval_fm_thumbnail(fm: dict) -> tuple[bool, str | None]:
    thumb = (fm.get("thumbnail") or "").strip()
    if not thumb:
        return False, None
    return _fm_url_bad(thumb, "thumbnail")


RULE_EVALS: dict[str, callable] = {
    "FM-DRAFT": _eval_fm_draft,
    "FM-MISSINGKEYS": _eval_fm_missingkeys,
    "FM-FEATUREIMAGE": _eval_fm_featureimage,
    "FM-THUMBNAIL": _eval_fm_thumbnail,
}


@dataclass
class RecheckResult:
    blog_id: str
    post_path: str
    check_name: str
    previous_status: str
    current_status: str
    passed: bool
    timestamp: str
    detail: str

    def to_dict(self) -> dict:
        return asdict(self)


def _read_previous_status(blog_id: str, check_name: str) -> str:
    """check_results 에서 해당 행 현재 status 조회 (SELECT only, 기록 안 함)."""
    try:
        from ops_dashboard.db import get_conn

        conn = get_conn()
        try:
            row = conn.execute(
                "SELECT status FROM check_results WHERE blog_id=? AND check_name=? "
                "ORDER BY checked_at DESC LIMIT 1",
                (blog_id, check_name),
            ).fetchone()
        finally:
            conn.close()
        return row["status"] if row else "unknown"
    except Exception as e:  # 조회 불가 시 unknown — 블로커 아님
        logger.warning("[recheck] previous_status 조회 실패 %s/%s: %s",
                       blog_id, check_name, e)
        return "unknown"


def targeted_recheck(blog_id: str, post_path: str, check_name: str) -> RecheckResult:
    """단일 포스트 대상 rule_id(FM-*) 재검사.

    전체 스캔 호출 금지 — post_path 하나만 파싱.
    DB INSERT/UPDATE 금지 — SELECT(previous_status) + 반환만.
    """
    if check_name not in RULE_EVALS:
        raise ValueError(
            f"지원 안 되는 check_name(rule_id): {check_name}. "
            f"지원: {list(RULE_EVALS)}"
        )
    path = Path(post_path)
    content = path.read_text(encoding="utf-8")
    _, fm = _parse_frontmatter(content)

    triggered, why = RULE_EVALS[check_name](fm)
    prev = _read_previous_status(blog_id, check_name)
    ts = datetime.now(timezone.utc).isoformat()

    if triggered:
        return RecheckResult(
            blog_id=blog_id, post_path=str(path), check_name=check_name,
            previous_status=prev, current_status="fail", passed=False,
            timestamp=ts, detail=f"FM 위반: {why}",
        )
    return RecheckResult(
        blog_id=blog_id, post_path=str(path), check_name=check_name,
        previous_status=prev, current_status="pass", passed=True,
        timestamp=ts, detail="FM 통과",
    )

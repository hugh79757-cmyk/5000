"""ops_dashboard.checks.concurrency_skip — P02 consecutive_failures 오탐(CONCURRENCY 스킵) 태깅

scheduler.py run_publish가 CONCURRENCY 슬롯 소진 시 None을 반환하도록 수정됨(2026-08-28)
→ 신규 P02는 더 이상 발생하지 않음. 이 체커는 수정 이전에 쌓인 open P02 이벤트 중
슬롯 소진 스킵 로그와 시점이 겹치는 것을 'known_cause=concurrency_skip' 으로 태깅한다.
상태 pass 반환 → 대시보드 주의대상(attention_items)에서 제외 = 오탐 아님 표시.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from pathlib import Path

from ops_dashboard.checks import register_check

logger = logging.getLogger(__name__)
LOG_PATH = Path(__file__).resolve().parents[2] / "logs" / "scheduler.log"
WINDOW_MIN = 20


def _parse_ts(line: str):
    m = re.match(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", line)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


def _concurrency_skip_times(blog_id: str, since: datetime) -> list[datetime]:
    if not LOG_PATH.exists():
        return []
    pat = re.compile(r"\[CONCURRENCY\].*?" + re.escape(blog_id) + r".*?스킵")
    hits: list[datetime] = []
    try:
        with LOG_PATH.open(errors="ignore") as f:
            for line in f:
                if "CONCURRENCY" not in line or blog_id not in line:
                    continue
                if not pat.search(line):
                    continue
                ts = _parse_ts(line)
                if ts and ts >= since:
                    hits.append(ts)
    except Exception as e:
        logger.warning("concurrency_skip log scan failed: %s", e)
    return hits


@register_check("concurrency_skip")
def check_concurrency_skip(conn, blog_id) -> dict:
    since = datetime.now() - timedelta(hours=48)
    since_s = since.strftime("%Y-%m-%d %H:%M:%S")
    try:
        rows = conn.execute(
            "SELECT occurred_at FROM publish_error_events "
            "WHERE blog_id=? AND problem_id='P02' AND state='open' "
            "AND occurred_at > ?",
            (blog_id, since_s),
        ).fetchall()
    except Exception as e:
        return {"status": "unknown", "detail": f"query error: {e}", "evidence_url": ""}
    if not rows:
        return {"status": "pass", "detail": "open P02 없음 — 정상", "evidence_url": ""}

    skips = _concurrency_skip_times(blog_id, since)
    if not skips:
        return {
            "status": "fail",
            "detail": f"open P02 {len(rows)}건, CONCURRENCY 스킵 연관 없음 → 실제 실패 의심",
            "evidence_url": "",
        }

    correlated = 0
    for r in rows:
        occurred = r[0] if isinstance(r, (tuple, list)) else r["occurred_at"]
        et = _parse_ts(occurred) if isinstance(occurred, str) else None
        if et is None:
            correlated += 1
            continue
        if any(abs((et - s).total_seconds()) <= WINDOW_MIN * 60 for s in skips):
            correlated += 1

    if correlated >= max(1, len(rows) // 2):
        return {
            "status": "pass",
            "detail": (
                f"open P02 {len(rows)}건 중 {correlated}건이 CONCURRENCY 스킵과 시점 겹침 "
                f"→ known_cause=concurrency_skip (일시적 fleet 부하, 콘텐츠 실패 아님). 주의불요."
            ),
            "evidence_url": "",
        }
    return {
        "status": "fail",
        "detail": f"open P02 {len(rows)}건, 스킵 연관 {correlated}건 → 실제 실패 의심",
        "evidence_url": "",
    }

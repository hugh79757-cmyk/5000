"""ops_dashboard.checks.content_freshness — 본문 날짜 만료 / DB 신선도 검사 (CF-01, ERR-021/022)"""
from __future__ import annotations

import logging
import re
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from ops_dashboard.checks import register_check

logger = logging.getLogger(__name__)

DATE_RE = re.compile(r"(20\d{2})년\s*(\d{1,2})월\s*(\d{1,2})일")
ISO_RE = re.compile(r"(20\d{2})[-./](\d{1,2})[-./](\d{1,2})")
STALE_DAYS = 60
DB_STALE_DAYS = 30
EXEMPT_DB_TYPES = {"camping", "heritage", "food", "course"}


def _extract_dates(text: str) -> list[date]:
    out: list[date] = []
    for m in DATE_RE.finditer(text):
        try:
            out.append(date(int(m.group(1)), int(m.group(2)), int(m.group(3))))
        except ValueError:
            continue
    # ISO fallback only if no Korean dates found (avoid double count)
    if not out:
        for m in ISO_RE.finditer(text):
            try:
                y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                if 1 <= mo <= 12 and 1 <= d <= 31:
                    out.append(date(y, mo, d))
            except ValueError:
                continue
    return out


def _get_site(conn, blog_id: str) -> Path | None:
    try:
        from ops_dashboard.db import get_blog_detail
        row = get_blog_detail(conn, blog_id)
        if row and row.get("site_path"):
            p = Path(row["site_path"])
            if p.is_dir():
                return p
    except Exception:
        pass
    # fallback direct query (get_blog_detail may be filtered)
    try:
        cur = conn.cursor()
        cur.execute("SELECT site_path FROM blog_lifecycle WHERE blog_id=?", (blog_id,))
        r = cur.fetchone()
        if r and r[0]:
            p = Path(r[0])
            if p.is_dir():
                return p
            # also try without is_dir (container path may be symlink)
            if p.exists():
                return p
    except Exception:
        pass
    return None


def _get_fetch_type(conn, blog_id: str) -> str:
    try:
        import yaml, glob
        for f in glob.glob("config/blogs.d/*.yaml"):
            import yaml as _y
            data = _y.safe_load(open(f))
            if not data or "blogs" not in data:
                continue
            for b in data["blogs"]:
                if b.get("id") == blog_id:
                    fs = b.get("fetch_sources") or []
                    if fs and isinstance(fs[0], dict):
                        return fs[0].get("type", "")
                    return b.get("pipeline", "")
    except Exception:
        pass
    return ""


@register_check("content_freshness")
def check_content_freshness(conn, blog_id: str) -> dict:
    site = _get_site(conn, blog_id)
    if site is None:
        return {"status": "unknown", "detail": "site_path not found — N/A"}

    # reuse standard.py _recent_posts
    try:
        from ops_dashboard.checks.standard import _recent_posts, _read_file_safe
    except Exception as e:
        return {"status": "unknown", "detail": f"import failed: {e}"}

    posts = _recent_posts(site, 10)
    if not posts:
        return {"status": "pass", "detail": "posts 0 — N/A"}

    all_dates: list[date] = []
    stale_hits: list[str] = []
    for p in posts:
        idx = p / "index.md"
        if not idx.exists():
            continue
        try:
            body = _read_file_safe(idx)
            # strip frontmatter for date extraction (frontmatter date is publish date, not event date)
            if body.startswith("---"):
                end = body.find("\n---", 3)
                if end != -1:
                    body = body[end + 4 :]
            dates = _extract_dates(body)
            if dates:
                all_dates.extend(dates)
        except Exception:
            continue

    today = date.today()
    # DB freshness only for festival type
    fetch_type = _get_fetch_type(conn, blog_id)
    is_festival = fetch_type == "festival"
    db_status = None
    db_detail = ""
    if is_festival:
        try:
            import os
            # project root data/festival.db
            db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "festival.db")
            if os.path.exists(db_path):
                c = sqlite3.connect(db_path)
                row = c.execute(
                    "SELECT COUNT(*) FROM festivals WHERE eventstartdate >= strftime('%Y%m%d','now')"
                ).fetchone()
                future_cnt = row[0] if row else 0
                row2 = c.execute("SELECT max(eventstartdate) FROM festivals").fetchone()
                max_date = row2[0] if row2 and row2[0] else ""
                c.close()
                if future_cnt == 0:
                    db_status = "db_stale"
                    db_detail = f"festival DB future 0 (max {max_date}) — 갱신 중단"
                else:
                    # also check max future recency
                    db_detail = f"festival future {future_cnt}"
            else:
                db_status = "db_stale"
                db_detail = "festival.db not found"
        except Exception as e:
            db_status = "db_stale"
            db_detail = f"DB check failed: {e}"

    # Content staleness: max_content_date < today - STALE_DAYS
    if all_dates:
        max_content = max(all_dates)
        days_old = (today - max_content).days
        if days_old > STALE_DAYS:
            detail = f"STALE: max content date {max_content} ({days_old}d ago > {STALE_DAYS}d) — {len(all_dates)} dates in 10 posts"
            if db_detail:
                detail += f" | {db_detail}"
            # db_stale takes precedence if both
            if db_status == "db_stale":
                return {"status": "db_stale", "detail": f"DB_STALE: {db_detail} | {detail}"}
            return {"status": "stale", "detail": detail}

    if db_status == "db_stale":
        return {"status": "db_stale", "detail": db_detail}

    detail = f"pass: {len(all_dates)} content dates, max {max(all_dates) if all_dates else 'N/A'} | {db_detail or 'no DB check'}"
    return {"status": "pass", "detail": detail}

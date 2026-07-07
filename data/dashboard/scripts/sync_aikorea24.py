"""
aikorea24 → dashboard 캐시 동기화

aikorea24 Astro 블로그의 MD 파일 frontmatter를 파싱하여
발행 이력을 대시보드 캐시에 저장.

사용법:
    python sync_aikorea24.py
"""

import os
import re
import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path

# ── Paths ──
_AIKOREA24_CONTENT = Path.home() / "Projects" / "aikorea24" / "src" / "content" / "blog"
_AIKOREA24_SITEMAP = "https://aikorea24.kr/sitemap.xml"
_DASHBOARD_DATA = Path(__file__).resolve().parent.parent / "data"
_CACHE_DB = _DASHBOARD_DATA / "aikorea24_posts.db"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


def _parse_md_frontmatter(filepath: Path) -> dict | None:
    """MD 파일 frontmatter 파싱"""
    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning(f"  읽기 실패 {filepath.name}: {e}")
        return None

    # frontmatter (--- ... ---)
    m = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not m:
        return None

    fm = {}
    for line in m.group(1).strip().split("\n"):
        if ":" in line:
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            fm[key] = val

    return fm


def sync_aikorea24() -> dict:
    """aikorea24 MD 파일 스캔 → DB 캐시"""
    if not _AIKOREA24_CONTENT.exists():
        logger.error(f"aikorea24 content 경로 없음: {_AIKOREA24_CONTENT}")
        return {"status": "error", "message": f"Path not found: {_AIKOREA24_CONTENT}"}

    _DASHBOARD_DATA.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(_CACHE_DB))
    conn.execute(
        """CREATE TABLE IF NOT EXISTS aikorea24_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            date TEXT NOT NULL,
            file_path TEXT UNIQUE,
            tags TEXT DEFAULT '',
            category TEXT DEFAULT '',
            synced_at TEXT DEFAULT (datetime('now','localtime'))
        )"""
    )
    conn.execute(
        """CREATE INDEX IF NOT EXISTS idx_ak24_date
           ON aikorea24_posts(date)"""
    )

    md_files = sorted(_AIKOREA24_CONTENT.glob("*.md"), reverse=True)
    logger.info(f"aikorea24 MD 파일: {len(md_files)}개")

    inserted = 0
    skipped = 0
    errors = 0

    for fpath in md_files:
        fm = _parse_md_frontmatter(fpath)
        if not fm:
            errors += 1
            continue

        title = fm.get("title", fpath.stem)
        date_raw = fm.get("date") or fm.get("pubDate") or fpath.stem[:10]
        # date 형식 정규화
        date_str = date_raw.replace("T", " ")[:10] if "T" in str(date_raw) else str(date_raw)[:10]
        tags = fm.get("tags", "")
        if isinstance(tags, str):
            tags = tags.strip("[]").replace("'", "").replace('"', "")
        category = fm.get("category", "")

        try:
            cur = conn.execute(
                """INSERT OR IGNORE INTO aikorea24_posts
                   (title, date, file_path, tags, category)
                   VALUES (?,?,?,?,?)""",
                (title, date_str, str(fpath.relative_to(_AIKOREA24_CONTENT.parent.parent)), tags, category),
            )
            if cur.rowcount > 0:
                inserted += 1
            else:
                skipped += 1
        except Exception as e:
            logger.warning(f"  INSERT 실패 {fpath.name}: {e}")
            errors += 1

    conn.commit()
    conn.close()
    logger.info(f"aikorea24 동기화 완료: {inserted}건 추가, {skipped}건 중복, {errors}건 오류")
    return {"status": "ok", "total": len(md_files), "inserted": inserted, "skipped": skipped, "errors": errors}


if __name__ == "__main__":
    result = sync_aikorea24()
    print(f"Result: {result}")

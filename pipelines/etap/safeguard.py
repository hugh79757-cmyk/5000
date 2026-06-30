"""ETAP 공통 안전장치 - 데이터 기반 발행 원칙 적용"""
import contextlib
import logging
import os
import sqlite3

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, "data", "travel-en.db")


def get_db():
    return sqlite3.connect(DB_PATH)


def check_remaining_topics(blog_id, topic_table="topics"):
    db = get_db()
    try:
        return db.execute(
            "SELECT COUNT(*) FROM " + topic_table + " t "
            "WHERE t.exhausted = 0 "
            "AND NOT EXISTS ("
            "  SELECT 1 FROM publish_log pl "
            "  WHERE pl.topic_id = t.id AND pl.blog_id = ?"
            ")", (blog_id,)
        ).fetchone()[0]
    finally:
        db.close()


def check_data_availability(table, min_rows=1):
    db = get_db()
    try:
        count = db.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]
        return count >= min_rows
    finally:
        db.close()


def should_publish(blog_id, topic_table, data_table, min_data=1):
    if not check_data_availability(data_table, min_data):
        return False, "no data in " + data_table
    remaining = check_remaining_topics(blog_id, topic_table)
    if remaining <= 0:
        return False, "no topics left in " + topic_table
    if remaining <= 10:
        logger.warning("[%s] only %d topics remaining", blog_id, remaining)
    return True, "OK (%d topics left)" % remaining


def send_exhaustion_alert(blog_id, remaining, tg_func=None) -> None:
    if remaining <= 0:
        msg = f"[ETAP] {blog_id}: topics exhausted, publishing stopped."
        logger.error(msg)
        if tg_func:
            with contextlib.suppress(Exception):
                tg_func(msg)
    elif remaining <= 10:
        msg = "[ETAP] %s: only %d topics left." % (blog_id, remaining)
        logger.warning(msg)
        if tg_func:
            with contextlib.suppress(Exception):
                tg_func(msg)


def safe_run(blog_id, topic_table, data_table, run_fn, tg_func=None, min_data=1):
    can_publish, reason = should_publish(blog_id, topic_table, data_table, min_data)
    if not can_publish:
        logger.info("[%s] stopped: %s", blog_id, reason)
        send_exhaustion_alert(blog_id, 0, tg_func)
        return {"status": "stopped", "reason": reason}
    try:
        result = run_fn()
    except Exception as e:
        logger.exception("[%s] error: %s", blog_id, e)
        if tg_func:
            with contextlib.suppress(Exception):
                tg_func(f"[ETAP] {blog_id} error: {e}")
        return {"status": "error", "reason": str(e)}
    remaining = check_remaining_topics(blog_id, topic_table)
    send_exhaustion_alert(blog_id, remaining, tg_func)
    if isinstance(result, dict):
        result["remaining_topics"] = remaining
    return result


def validate_article_data(article, required_fields):
    if not article:
        return False, "article is None"
    for field in required_fields:
        val = article.get(field)
        if val is None or (isinstance(val, str) and len(val.strip()) == 0):
            return False, "missing field: " + field
        if isinstance(val, (list, dict)) and len(val) == 0:
            return False, "empty field: " + field
    return True, "OK"

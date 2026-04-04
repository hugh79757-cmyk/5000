"""ETAP topic_manager — 통합 토픽 선택, 발행 기록, 고갈 감지, 중복 방지.

모든 ETAP 파이프라인은 이 모듈의 함수를 사용해야 합니다.
중복 체크는 topics 테이블의 PK(id)를 기준으로 합니다.
"""
import sqlite3
import logging
import os
import requests
from pathlib import Path
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent.parent / "data" / "travel-en.db"

# 텔레그램 설정
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TG_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# 고갈 임계값
EXHAUSTION_WARN_THRESHOLD = 10   # 남은 토픽 10개 이하 → 경고
EXHAUSTION_STOP_THRESHOLD = 0    # 남은 토픽 0개 → 발행 중지


def _get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def send_telegram(message):
    """텔레그램 메시지 전송"""
    if not TG_TOKEN or not TG_CHAT_ID:
        logger.warning("[TG] Token or chat_id missing, skip telegram")
        return False
    try:
        url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
        resp = requests.post(url, json={
            "chat_id": TG_CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
        }, timeout=10)
        if resp.status_code == 200:
            logger.info(f"[TG] Sent: {message[:50]}...")
            return True
        else:
            logger.error(f"[TG] Failed: {resp.status_code} {resp.text[:100]}")
            return False
    except Exception as e:
        logger.error(f"[TG] Error: {e}")
        return False


def get_remaining_count(topic_table, blog_id):
    """특정 블로그의 남은 미발행 토픽 수 조회"""
    conn = _get_db()
    try:
        count = conn.execute(
            f"SELECT count(*) FROM {topic_table} WHERE exhausted = 0"
        ).fetchone()[0]
        return count
    except Exception as e:
        logger.error(f"get_remaining_count error: {e}")
        return -1
    finally:
        conn.close()


def check_exhaustion(topic_table, blog_id):
    """데이터 고갈 체크. 반환값: (can_publish: bool, remaining: int)"""
    remaining = get_remaining_count(topic_table, blog_id)

    if remaining <= EXHAUSTION_STOP_THRESHOLD:
        msg = (
            f"🛑 <b>[ETAP] {blog_id} 발행 중지</b>\n"
            f"토픽 테이블: {topic_table}\n"
            f"남은 토픽: {remaining}개\n"
            f"데이터가 고갈되어 자동 발행을 중지합니다."
        )
        logger.warning(f"[{blog_id}] EXHAUSTED: {topic_table} has {remaining} topics left")
        send_telegram(msg)
        return False, remaining

    if remaining <= EXHAUSTION_WARN_THRESHOLD:
        msg = (
            f"⚠️ <b>[ETAP] {blog_id} 토픽 부족 경고</b>\n"
            f"토픽 테이블: {topic_table}\n"
            f"남은 토픽: {remaining}개\n"
            f"{EXHAUSTION_STOP_THRESHOLD}개 도달 시 자동 중지됩니다."
        )
        logger.warning(f"[{blog_id}] LOW TOPICS: {remaining} remaining in {topic_table}")
        send_telegram(msg)

    return True, remaining


def pick_topic_by_id(topic_table, blog_id):
    """PK(id) 기준으로 미발행 토픽 1개 선택.
    
    중복 방지 로직:
    1. exhausted = 0 (아직 소진 안 됨)
    2. id NOT IN publish_log (PK 기준으로 이미 발행된 적 없음)
    3. priority DESC, id ASC (높은 우선순위 먼저)
    """
    # 먼저 고갈 체크
    can_publish, remaining = check_exhaustion(topic_table, blog_id)
    if not can_publish:
        return None

    conn = _get_db()
    try:
        row = conn.execute(f"""
            SELECT * FROM {topic_table}
            WHERE exhausted = 0
              AND id NOT IN (
                  SELECT topic_id FROM publish_log
                  WHERE blog_id = ? AND topic_id IS NOT NULL
              )
            ORDER BY priority DESC, id ASC
            LIMIT 1
        """, (blog_id,)).fetchone()

        if not row:
            logger.info(f"[{blog_id}] No unpublished topics in {topic_table}")
            # exhausted=0이지만 publish_log에 있는 경우: 정합성 복구
            orphan = conn.execute(f"""
                SELECT count(*) FROM {topic_table}
                WHERE exhausted = 0
            """).fetchone()[0]
            if orphan > 0:
                logger.warning(
                    f"[{blog_id}] {orphan} topics with exhausted=0 but already in publish_log. "
                    f"Syncing exhausted flags..."
                )
                conn.execute(f"""
                    UPDATE {topic_table} SET exhausted = 1
                    WHERE exhausted = 0 AND id IN (
                        SELECT topic_id FROM publish_log
                        WHERE blog_id = ? AND topic_id IS NOT NULL
                    )
                """, (blog_id,))
                conn.commit()
            return None

        topic = dict(row)
        logger.info(
            f"[{blog_id}] Picked topic id={topic['id']}, "
            f"city={topic.get('city','')}, slug={topic.get('slug','')}, "
            f"remaining={remaining - 1}"
        )
        return topic

    except Exception as e:
        logger.error(f"pick_topic_by_id error: {e}")
        return None
    finally:
        conn.close()


def mark_published_by_id(topic_id, topic_table, blog_id, title, slug, url=""):
    """PK 기준으로 발행 완료 기록.
    
    1. publish_log에 topic_id 포함하여 INSERT
    2. topics 테이블의 exhausted = 1로 UPDATE (id 기준)
    3. 중복 INSERT 방지 (같은 topic_id + blog_id 조합)
    """
    conn = _get_db()
    try:
        # 중복 체크
        existing = conn.execute(
            "SELECT log_id FROM publish_log WHERE topic_id = ? AND blog_id = ?",
            (topic_id, blog_id)
        ).fetchone()

        if existing:
            logger.warning(
                f"[{blog_id}] DUPLICATE PREVENTED: topic_id={topic_id} "
                f"already published (log_id={existing['log_id']})"
            )
            return False

        # publish_log에 기록
        conn.execute(
            "INSERT INTO publish_log (topic_id, blog_id, title, slug, published_at, url) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (topic_id, blog_id, title, slug, datetime.now().isoformat(), url)
        )

        # topics 테이블 exhausted 마킹 (PK 기준)
        conn.execute(
            f"UPDATE {topic_table} SET exhausted = 1 WHERE id = ?",
            (topic_id,)
        )

        conn.commit()
        logger.info(f"[{blog_id}] Published: topic_id={topic_id}, slug={slug}")
        return True

    except Exception as e:
        logger.error(f"mark_published_by_id error: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


# === 하위 호환: pipeline.py (tour-hugo)용 ===
def pick_topic(blog_id, window_days=30):
    """tour-hugo 전용 pick_topic (topics 테이블 사용)"""
    conn = _get_db()
    try:
        cutoff = (datetime.now() - timedelta(days=window_days)).isoformat()
        row = conn.execute("""
            SELECT t.topic_id, t.dest_id, t.template_key, t.title, t.slug,
                   d.city, d.country, d.region
            FROM topics t
            JOIN destinations d ON t.dest_id = d.dest_id
            WHERE t.exhausted = 0
              AND t.topic_id NOT IN (
                  SELECT COALESCE(topic_id, 0) FROM publish_log
                  WHERE blog_id = ? AND published_at > ?
              )
            ORDER BY t.priority DESC, t.topic_id ASC
            LIMIT 1
        """, (blog_id, cutoff)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def mark_published(topic_id, blog_id, title, slug, url=""):
    """tour-hugo 전용 mark_published (topics 테이블 사용)"""
    conn = _get_db()
    try:
        existing = conn.execute(
            "SELECT log_id FROM publish_log WHERE topic_id = ? AND blog_id = ?",
            (topic_id, blog_id)
        ).fetchone()
        if existing:
            logger.warning(f"[{blog_id}] DUPLICATE: topic_id={topic_id}")
            return False
        conn.execute(
            "INSERT INTO publish_log (topic_id, blog_id, title, slug, published_at, url) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (topic_id, blog_id, title, slug, datetime.now().isoformat(), url)
        )
        conn.execute(
            "UPDATE topics SET exhausted = 1 WHERE topic_id = ?", (topic_id,)
        )
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"mark_published error: {e}")
        return False
    finally:
        conn.close()

import re
import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "content.db")


def get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_conn()
    conn.execute(
        "CREATE TABLE IF NOT EXISTS articles ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "blog_id TEXT NOT NULL,"
        "title TEXT NOT NULL,"
        "slug TEXT,"
        "body_md TEXT,"
        "body_html TEXT,"
        "thumbnail_url TEXT,"
        "category TEXT,"
        "tags TEXT,"
        "data_source TEXT,"
        "source_id TEXT,"
        "prompt_id TEXT,"
        "model TEXT,"
        "published_url TEXT,"
        "published_at TEXT,"
        "platform TEXT,"
        "status TEXT DEFAULT 'draft',"
        "created_at TEXT DEFAULT (datetime('now'))"
        ")"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_articles_blog_id ON articles(blog_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_articles_status ON articles(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_articles_source ON articles(data_source, source_id)")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_articles_published_url ON articles(published_url)")
    conn.commit()
    conn.close()


def insert_article(article):
    conn = get_conn()
    cur = conn.execute(
        "INSERT OR IGNORE INTO articles"
        " (blog_id, title, slug, body_md, body_html, thumbnail_url, category, tags,"
        "  data_source, source_id, prompt_id, model, published_url, published_at,"
        "  platform, status, created_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            article.get("blog_id", ""),
            article.get("title", ""),
            article.get("slug", ""),
            article.get("body_md", ""),
            article.get("body_html", ""),
            article.get("thumbnail_url", ""),
            article.get("category", ""),
            article.get("tags", ""),
            article.get("data_source", ""),
            article.get("source_id", ""),
            article.get("prompt_id", ""),
            article.get("model", ""),
            article.get("published_url", "") or f"pending://{article.get('blog_id','unknown')}/{datetime.now().timestamp()}",
            article.get("published_at", ""),
            article.get("platform", ""),
            article.get("status", "published"),
            article.get("created_at", datetime.now().isoformat()),
        ),
    )
    row_id = cur.lastrowid
    conn.commit()
    conn.close()
    return row_id


def update_published(article_id, published_url):
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE articles SET published_url=?, status='published',"
            " published_at=datetime('now') WHERE id=?",
            (published_url, article_id),
        )
        conn.commit()
    except Exception as e:
        # UNIQUE 충돌 시 status만 업데이트
        import logging
        logging.getLogger(__name__).warning(f"update_published 충돌: {e}")
        conn.execute(
            "UPDATE articles SET status='published', published_at=datetime('now') WHERE id=?",
            (article_id,),
        )
        conn.commit()
    conn.close()


def get_today_count(blog_id):
    conn = get_conn()
    today = datetime.now().strftime("%Y-%m-%d")
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM articles WHERE blog_id=? AND date(created_at)=? AND status='published'",
        (blog_id, today),
    ).fetchone()
    conn.close()
    return row["cnt"] if row else 0


def article_exists(published_url):
    conn = get_conn()
    row = conn.execute(
        "SELECT 1 FROM articles WHERE published_url=?",
        (published_url,),
    ).fetchone()
    conn.close()
    return row is not None


def get_all_articles(blog_id=None, limit=100, offset=0):
    conn = get_conn()
    if blog_id:
        rows = conn.execute(
            "SELECT * FROM articles WHERE blog_id=? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (blog_id, limit, offset),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM articles ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def register_images(article_id, blog_id, html):
    conn = get_conn()
    urls = re.findall(r'<img[^>]+src=["\'](https?://[^"\'>]+)["\'"]', html or "")
    md_urls = re.findall(r'!\[[^\]]*\]\((https?://[^)]+)\)', html or "")
    all_urls = list(set(urls + md_urls))
    count = 0
    for url in all_urls:
        try:
            conn.execute(
                "INSERT OR IGNORE INTO used_images (image_url, article_id, blog_id) VALUES (?,?,?)",
                (url, article_id, blog_id),
            )
            count += 1
        except sqlite3.IntegrityError as e:
            import logging
            logging.getLogger(__name__).warning(f"[DB_ERROR] INSERT used_images failed: {e}")
    conn.commit()
    conn.close()
    return count


def is_image_used(image_url, blog_id=None):
    conn = get_conn()
    if blog_id:
        row = conn.execute(
            "SELECT 1 FROM used_images WHERE image_url=? AND blog_id=?",
            (image_url, blog_id),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT 1 FROM used_images WHERE image_url=?",
            (image_url,),
        ).fetchone()
    conn.close()
    return row is not None


def filter_unused_images(image_urls):
    conn = get_conn()
    unused = []
    for url in image_urls:
        row = conn.execute(
            "SELECT 1 FROM used_images WHERE image_url=?",
            (url,),
        ).fetchone()
        if not row:
            unused.append(url)
    conn.close()
    return unused


def get_used_image_count(blog_id=None):
    conn = get_conn()
    if blog_id:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM used_images WHERE blog_id=?",
            (blog_id,),
        ).fetchone()
    else:
        row = conn.execute("SELECT COUNT(*) as cnt FROM used_images").fetchone()
    conn.close()
    return row["cnt"] if row else 0


def source_exists(blog_id, data_source, source_id):
    if not source_id:
        return False
    conn = get_conn()
    row = conn.execute(
        "SELECT 1 FROM articles WHERE blog_id=? AND data_source=? AND source_id=?",
        (blog_id, data_source, source_id),
    ).fetchone()
    conn.close()
    return row is not None


def title_similar_exists(blog_id, title):
    import re
    # 실시간 데이터 기반 블로그는 날짜 포함 시 중복 허용
    REALTIME_BLOGS = {"sector-hugo", "stock-hugo", "dividend-hugo", "etf-hugo", "ipo-hugo", "finance-hugo"}
    if blog_id in REALTIME_BLOGS:
        date_pattern = re.search(r"\d{1,2}월\s*\d{1,2}일|\d{4}년\s*\d{1,2}월", title)
        if date_pattern:
            return False
    conn = get_conn()
    # 숫자·조사 제거 후 핵심 키워드로 비교 (20자)
    _normalized = re.sub(r"[0-9]곳|[0-9]선|총정리|정리|한눈에 보기|추천 리스트|비교|체크리스트|소개", "", title).strip()
    core = _normalized[:20] if len(_normalized) >= 20 else _normalized[:15]
    row = conn.execute(
        "SELECT 1 FROM articles WHERE blog_id=? AND title LIKE ?",
        (blog_id, "%" + core + "%"),
    ).fetchone()
    conn.close()
    return row is not None

def init_used_places():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS used_places (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            place_name TEXT NOT NULL,
            content_id TEXT DEFAULT '',
            blog_id TEXT NOT NULL,
            article_id INTEGER,
            published_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(place_name, blog_id)
        )
    """)
    conn.commit()
    conn.close()


def is_place_used(place_name, blog_id):
    conn = get_conn()
    row = conn.execute(
        "SELECT 1 FROM used_places WHERE place_name=? AND blog_id=?",
        (place_name, blog_id),
    ).fetchone()
    conn.close()
    return row is not None


def register_places(article_id, blog_id, place_names, content_ids=None):
    conn = get_conn()
    init_used_places()
    count = 0
    for i, name in enumerate(place_names):
        cid = content_ids[i] if content_ids and i < len(content_ids) else ""
        try:
            conn.execute(
                "INSERT OR IGNORE INTO used_places (place_name, content_id, blog_id, article_id) VALUES (?,?,?,?)",
                (name, cid, blog_id, article_id),
            )
            count += 1
        except sqlite3.Error as e:
            import logging
            logging.getLogger(__name__).error(f"[DB_ERROR] INSERT used_places failed: {e}")
    conn.commit()
    conn.close()
    return count


def filter_unused_places(place_names, blog_id):
    conn = get_conn()
    init_used_places()
    unused = []
    for name in place_names:
        row = conn.execute(
            "SELECT 1 FROM used_places WHERE place_name=? AND blog_id=?",
            (name, blog_id),
        ).fetchone()
        if not row:
            unused.append(name)
    conn.close()
    return unused


# 모듈 import 시 자동 초기화
init_db()

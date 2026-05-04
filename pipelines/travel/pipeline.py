import os
import sys
import logging
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.getenv("TAP_ROOT", "/Users/twinssn/Projects/TAP"))
os.chdir(os.getenv("TAP_ROOT", "/Users/twinssn/Projects/TAP"))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.getenv("TAP_ROOT", "/Users/twinssn/Projects/TAP"), ".env"))
load_dotenv("/Users/twinssn/Projects/5000/.env")

from shared.content_store import init_db, get_today_count, register_images, register_places
from shared.publisher import publish, get_blog_config
from pipelines.travel.fetcher import fetch_camping, fetch_korservice, fetch_korservice_heritage, fetch_wellness, fetch_heritage, fetch_festival, fetch_food, fetch_course, fetch_random
from pipelines.travel.writer import generate_content

logger = logging.getLogger(__name__)

try:
    from shared.telegram_notifier import send_error as tg_error
except ImportError:
    tg_error = lambda *a, **k: None

import random
from shared.validators import sanitize_title

# ── travel pipeline 전용 중복체크 (content.db/publish_ledger 기반) ──
def _travel_source_exists(blog_id, source_id):
    """publish_ledger에서 source_id 중복 확인 — stap_content.db 참조 방지"""
    if not source_id:
        return False
    import sqlite3 as _sq
    _db = "/Users/twinssn/Projects/5000/data/content.db"
    try:
        _cn = _sq.connect(_db)
        _row = _cn.execute(
            "SELECT 1 FROM publish_ledger WHERE blog_id=? AND source_id=?",
            (blog_id, source_id)
        ).fetchone()
        _cn.close()
        return _row is not None
    except Exception as _e:
        logger.warning(f"_travel_source_exists 오류: {_e}")
        return False

def _travel_title_similar_exists(blog_id, title):
    """publish_ledger에서 유사 제목 중복 확인"""
    if not title:
        return False
    import sqlite3 as _sq
    _db = "/Users/twinssn/Projects/5000/data/content.db"
    try:
        _cn = _sq.connect(_db)
        _rows = _cn.execute(
            "SELECT title FROM publish_ledger WHERE blog_id=? ORDER BY created_at DESC LIMIT 200",
            (blog_id,)
        ).fetchall()
        _cn.close()
        title_norm = title.replace(" ", "").lower()
        for (_t,) in _rows:
            if _t and _t.replace(" ", "").lower() == title_norm:
                return True
        return False
    except Exception as _e:
        logger.warning(f"_travel_title_similar_exists 오류: {_e}")
        return False


BLOG_FETCH_MAP = {
    "travel-hugo": [
        (fetch_camping, 0.45),
        (fetch_korservice, 0.25),
        (fetch_wellness, 0.15),
        (fetch_heritage, 0.15),
    ],
    "travel1-hugo": [
        (fetch_festival, 1.0),
    ],
    "travel2-hugo": [
        (fetch_heritage, 0.6),
        (fetch_korservice_heritage, 0.4),
    ],
    "travel3-hugo": [
        (fetch_food, 1.0),
    ],
    "travel4-hugo": [
        (fetch_course, 1.0),
    ],
}


def _fetch_for_blog(blog_id):
    fetch_list = BLOG_FETCH_MAP.get(blog_id, [(fetch_random, 1.0)])
    funcs = [f for f, w in fetch_list]
    weights = [w for f, w in fetch_list]

    selected = random.choices(funcs, weights=weights, k=1)[0]
    logger.info(blog_id + " fetcher: " + selected.__name__)

    data = selected()
    if data:
        return data

    for func, _ in fetch_list:
        if func != selected:
            data = func()
            if data:
                return data

    # 단일 소스 블로그는 random 폴백 금지 (축제/맛집 전용 블로그 보호)
    if len(fetch_list) == 1:
        logger.warning(blog_id + " 단일 소스 fetch 실패, random 폴백 차단")
        return None

    return fetch_random()




def _run_single(target_blog_id, blog_cfg=None):
    init_db()
    if blog_cfg is None:
        blog_cfg = get_blog_config(target_blog_id)
    quota = blog_cfg.get("daily_quota", 50)
    current = get_today_count(target_blog_id)

    if current >= quota:
        logger.info(target_blog_id + " quota reached: " + str(current) + "/" + str(quota))
        return None

    data = _fetch_for_blog(target_blog_id)
    if not data:
        logger.error("No data fetched for " + target_blog_id)
        tg_error(target_blog_id, "data_fetch", "데이터 수집 실패 (fetcher 반환값 없음)")
        return None

    # ── source_id 기반 중복 발행 방지 ──
    _content_ids = data.get("content_ids", [])
    if _content_ids:
        _sid = ",".join(_content_ids)
        if _travel_source_exists(target_blog_id, _sid):
            logger.warning(target_blog_id + " source_id 중복: " + _sid[:60])
            return None
        # 개별 contentid도 체크 (복합 source_id 대응)
        for _cid in _content_ids:
            if _cid and _travel_source_exists(target_blog_id, _cid):
                logger.warning(target_blog_id + " 개별 contentid 중복: " + _cid)
                return None

    result = generate_content(data, blog_id=target_blog_id)
    if not result:
        logger.error("Content generation failed for " + target_blog_id)
        tg_error(target_blog_id, "content_generation", "AI 본문 생성 실패")
        return None

    result["title"] = sanitize_title(result["title"])
    if _travel_title_similar_exists(target_blog_id, result["title"]):
        logger.warning(target_blog_id + " similar title exists: " + result["title"][:30])
        return None

    body_md = result.get("body_md", "")
    body_html = result.get("body_html", "")

    # SEO description 삽입
    _travel_desc = result.get("description", "")
    if _travel_desc:
        body_md = "<!-- DESC: " + _travel_desc + " -->\n" + body_md


    # ── 발행 전 검증 (문제 시 draft, 텔레그램 경고) ──
    _is_draft = False
    try:
        from shared.validators import validate_post_extended as _validate
        _val_ctx = {
            "blog_id": target_blog_id,
            "keyword": result.get("keyword", ""),
            "event_date": result.get("event_date", ""),
            "daily_quota": 5,
        }
        _issues = _validate(target_blog_id, result["title"], body_md, _val_ctx, pipeline="travel")
        if _issues:
            _is_draft = True
            logger.warning(f"[Validate] {len(_issues)} issues → draft: {_issues}")
    except Exception as _ve:
        logger.warning(f"[Validate] Error (non-fatal): {_ve}")

    pub_result = publish(
        blog_id=target_blog_id,
        title=result["title"],
        body_md=body_md,
        body_html=body_html,
        category=result.get("category", ""),
        tags=",".join(result.get("labels", [])),
        thumbnail_url="",
        data_source=result.get("source_type", ""),
        source_id=",".join(data.get("content_ids", [])),
        prompt_id=result.get("prompt_id", ""),
        model=result.get("model", ""),
        is_draft=_is_draft,
    )

    if pub_result and pub_result.get("success"):
        article_id = pub_result.get("article_id")
        if article_id and body_html:
            register_images(article_id, target_blog_id, body_html)
        if article_id and body_md:
            register_images(article_id, target_blog_id, body_md)
        # 장소 발행 이력 등록
        place_names = [it.get("title", it.get("facltNm", "")).strip()
                       for it in data.get("items", [])
                       if it.get("title") or it.get("facltNm")]
        if article_id and place_names:
            register_places(article_id, target_blog_id, place_names)
            logger.info("장소 %d건 등록: %s", len(place_names), ", ".join(n[:10] for n in place_names))
        # course_published 테이블에 코스 contentid 등록 (travel4-hugo 중복 방지)
        if data.get("source_type") == "course" and data.get("content_ids"):
            try:
                import sqlite3 as _sq
                _dbp = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "content.db")
                _cn = _sq.connect(_dbp)
                _cn.execute(
                    "CREATE TABLE IF NOT EXISTS course_published ("
                    "id INTEGER PRIMARY KEY AUTOINCREMENT, blog_id TEXT NOT NULL, "
                    "course_contentid TEXT NOT NULL, course_title TEXT NOT NULL, "
                    "published_at TEXT DEFAULT (datetime('now')), "
                    "UNIQUE(blog_id, course_contentid))"
                )
                for _cid in data["content_ids"]:
                    _cn.execute(
                        "INSERT OR IGNORE INTO course_published (blog_id, course_contentid, course_title) VALUES (?, ?, ?)",
                        (target_blog_id, str(_cid), result.get("title", ""))
                    )
                _cn.commit()
                _cn.close()
                logger.info("course_published 등록: %s", ",".join(data["content_ids"]))
            except Exception as _ec:
                logger.warning("course_published 등록 실패: %s", _ec)

    logger.info(target_blog_id + " result: " + str(pub_result.get("success", False)) + " " + str(pub_result.get("url", "")))
    return pub_result


def run(cfg):
    """dispatcher에서 호출하는 통일 인터페이스"""
    blog_id = cfg["id"]
    result = _run_single(blog_id, blog_cfg=cfg)

    # 발행 후 섹션 인덱스 가드 (2026-05-01 추가)
    # content/posts/index.md 폭탄 방지 — 발견 시 로그 경고
    try:
        import subprocess, logging
        _logger = logging.getLogger(__name__)
        _guard = "/Users/twinssn/Projects/TAP/scripts/check_section_index.sh"
        _r = subprocess.run(["bash", _guard], capture_output=True, text=True, timeout=10)
        if _r.returncode != 0:
            _msg = "[GUARD] 섹션 인덱스 이상 감지: " + (_r.stdout or "") + " | " + (_r.stderr or "")
            _logger.error(_msg)
        else:
            _logger.info("[GUARD] " + (_r.stdout or "").strip())
    except Exception as _e:
        try:
            import logging
            logging.getLogger(__name__).warning("[GUARD] 점검 스크립트 실행 실패: " + str(_e))
        except Exception:
            pass

    return result

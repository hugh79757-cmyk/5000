import logging
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.getenv("TAP_ROOT", "/Users/twinssn/Projects/TAP"))
os.chdir(os.getenv("TAP_ROOT", "/Users/twinssn/Projects/TAP"))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.getenv("TAP_ROOT", "/Users/twinssn/Projects/TAP"), ".env"))
load_dotenv("/Users/twinssn/Projects/5000/.env")

from pipelines.travel.fetcher import (
    fetch_camping,
    fetch_course,
    fetch_festival,
    fetch_food,
    fetch_heritage,
    fetch_korservice,
    fetch_korservice_heritage,
    fetch_random,
    fetch_wellness,
)
from pipelines.travel.writer import generate_content
from shared.content_store import (
    get_today_count,
    init_db,
    is_place_used,
    register_images,
    register_places,
)
from shared.publisher import get_blog_config, publish

logger = logging.getLogger(__name__)

from shared.log_config import log_stage
try:
    from shared.telegram_notifier import send_error as tg_error
except ImportError:
    def tg_error(*a, **k) -> None:
        return None

import random

from shared.validators import sanitize_title


# ── travel pipeline 전용 중복체크 (content.db/publish_ledger 기반) ──
def _travel_source_exists(blog_id, source_id):
    """publish_ledger에서 source_id 중복 확인 — stap_content.db 참조 방지"""
    if not source_id:
        return False
    import sqlite3 as _sq
    from shared.db_paths import PUBLISH_LEDGER_DB
    try:
        _cn = _sq.connect(PUBLISH_LEDGER_DB)
        _row = _cn.execute(
            "SELECT 1 FROM publish_ledger WHERE blog_id=? AND source_id=?",
            (blog_id, source_id)
        ).fetchone()
        _cn.close()
        return _row is not None
    except Exception as _e:
        logger.warning(f"_travel_source_exists 오류: {_e}")
        return False

def _travel_title_similar_exists(blog_id, title) -> bool | None:
    """publish_ledger에서 유사 제목 중복 확인 (정확 일치 + 80% 유사도)"""
    if not title:
        return False
    import sqlite3 as _sq
    from difflib import SequenceMatcher
    from shared.db_paths import PUBLISH_LEDGER_DB
    try:
        _cn = _sq.connect(PUBLISH_LEDGER_DB)
        _rows = _cn.execute(
            "SELECT title FROM publish_ledger WHERE blog_id=? ORDER BY created_at DESC LIMIT 200",
            (blog_id,)
        ).fetchall()
        _cn.close()
        title_norm = title.replace(" ", "").lower()
        for (_t,) in _rows:
            if not _t:
                continue
            _t_norm = _t.replace(" ", "").lower()
            if _t_norm == title_norm:
                return True
            if SequenceMatcher(None, title_norm, _t_norm).ratio() >= 0.8:
                logger.info(f"제목 유사도 80% 이상: '{title[:30]}' ≈ '{_t[:30]}' ({SequenceMatcher(None, title_norm, _t_norm).ratio():.0%})")
                return True
        return False
    except Exception as _e:
        logger.warning(f"_travel_title_similar_exists 오류: {_e}")
        return False


def _travel_sigungu_recently_published(blog_id, sigungu, days=14) -> bool | None:
    """최근 days일 내 동일 blog_id + sigungu 조합이
    published 상태로 존재하면 True 반환.

    우선순위:
      1순위: articles.sigungu 컬럼 직접 조회 (stap_content.db — 최신 발행 데이터)
      2순위: articles.title 파싱 fallback
             (sigungu 컬럼이 NULL인 기존 데이터 커버용)

    sigungu가 빈 문자열이면 False 반환 (체크 스킵).
    DB 오류 시 False 반환 (안전 방향 — 발행 허용).
    """
    if not sigungu or not sigungu.strip():
        return False

    import sqlite3 as _sq
    from datetime import timedelta

    from shared.db_paths import ARTICLES_DB

    cutoff = (datetime.now() - timedelta(days=days)).isoformat()

    try:
        _cn = _sq.connect(ARTICLES_DB)

        # 1순위: sigungu 컬럼 직접 조회
        _row = _cn.execute(
            """SELECT id FROM articles
               WHERE blog_id    = ?
                 AND sigungu    = ?
                 AND status     = 'published'
                 AND created_at > ?
               LIMIT 1""",
            (blog_id, sigungu, cutoff)
        ).fetchone()

        if _row:
            _cn.close()
            logger.info(f"_travel_sigungu_recently_published: {blog_id} '{sigungu}' 컬럼매칭")
            return True

        _cn.close()

        return False

    except Exception as _e:
        logger.warning(f"_travel_sigungu_recently_published 오류: {_e}")
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
    "tap-blogger": [
        (fetch_camping, 0.4),
        (fetch_heritage, 0.4),
        (fetch_festival, 0.2),
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

    _MAX_SIGUNGU_RETRIES = 5
    for _attempt in range(1, _MAX_SIGUNGU_RETRIES + 1):
        data = _fetch_for_blog(target_blog_id)
        if not data:
            logger.error("No data fetched for " + target_blog_id)
            if _attempt == 1:
                tg_error(target_blog_id, "data_fetch", "데이터 수집 실패 (fetcher 반환값 없음)")
            return None

        # ── source_id 기반 중복 발행 방지 ──
        _content_ids = data.get("content_ids", [])
        if _content_ids:
            _sid = ",".join(_content_ids)
            if _travel_source_exists(target_blog_id, _sid):
                logger.warning(target_blog_id + " source_id 중복: " + _sid[:60])
                return None
            for _cid in _content_ids:
                if not _cid:
                    continue
                try:
                    import sqlite3 as _sq
                    from shared.db_paths import PUBLISH_LEDGER_DB
                    _cn = _sq.connect(PUBLISH_LEDGER_DB)
                    _row = _cn.execute(
                        "SELECT 1 FROM publish_ledger WHERE blog_id=? AND INSTR(',' || source_id || ',', ',' || ? || ',') > 0",
                        (target_blog_id, _cid)
                    ).fetchone()
                    _cn.close()
                    if _row:
                        logger.warning(target_blog_id + " 개별 contentid 중복: " + _cid)
                        return None
                except Exception as _e:
                    logger.warning(f"개별 contentid 체크 오류: {_e}")

        # ── 시군구 기반 주제 중복 발행 방지 + 재시도 ──
        # 다른 시군구가 나올 때까지 최대 _MAX_SIGUNGU_RETRIES회 재시도
        _source_type = data.get("source_type", "")
        _sigungu = data.get("sigungu", "")
        if _sigungu and _source_type != "festival" and _travel_sigungu_recently_published(target_blog_id, _sigungu, days=3):
            if _attempt < _MAX_SIGUNGU_RETRIES:
                logger.info(f"{target_blog_id} 시군구 중복: {_sigungu}, 재시도 {_attempt}/{_MAX_SIGUNGU_RETRIES}")
                continue
            else:
                logger.warning(f"{target_blog_id} 시군구 중복: {_sigungu} (최대 재시도 {_MAX_SIGUNGU_RETRIES}회 초과)")
                return None

        # ── 가게명 기반 중복 발행 방지 (used_places ALL-TIME 체크) ──
        _place_names = [
            it.get("title", it.get("facltNm", "")).strip()
            for it in data.get("items", [])
            if it.get("title") or it.get("facltNm")
        ]
        if _place_names:
            _used_places = [n for n in _place_names if is_place_used(n, target_blog_id)]
            _dup_threshold = 2 if _source_type == "festival" else 1
            if len(_used_places) >= _dup_threshold:
                logger.warning(
                    f"{target_blog_id} 가게명 중복: {', '.join(_used_places)}"
                    f" (이미 발행된 가게 — used_places에서 감지, {_dup_threshold}건 이상)"
                )
                return None
            elif _used_places:
                logger.info(
                    f"{target_blog_id} 가게명部分 중복 (허용): {', '.join(_used_places)}"
                )

        # 모든 체크 통과 → 루프 탈출
        break

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

    # ── camping 차트 데이터 삽입 (site counts 비교) ──
    if blog_cfg.get("shortcodes_enabled", True) and data.get("source_type") == "camping":
        _chart_items = []
        for _item in data.get("items", []):
            _has_num = any(_item.get(k, "") for k in ("gnrlSiteCo", "glampSiteCo", "caravSiteCo", "toiletCo", "swrmCo"))
            if _has_num:
                _chart_items.append({
                    "name": _item.get("title", "")[:20],
                    "gnrlSiteCo": int(_item.get("gnrlSiteCo", 0)) if str(_item.get("gnrlSiteCo", "")).isdigit() else 0,
                    "glampSiteCo": int(_item.get("glampSiteCo", 0)) if str(_item.get("glampSiteCo", "")).isdigit() else 0,
                    "caravSiteCo": int(_item.get("caravSiteCo", 0)) if str(_item.get("caravSiteCo", "")).isdigit() else 0,
                    "toiletCo": int(_item.get("toiletCo", 0)) if str(_item.get("toiletCo", "")).isdigit() else 0,
                    "swrmCo": int(_item.get("swrmCo", 0)) if str(_item.get("swrmCo", "")).isdigit() else 0,
                })
        if len(_chart_items) >= 2:
            import json as _json
            body_md += f"\n<!-- CHART: {_json.dumps(_chart_items, ensure_ascii=False)} -->\n"


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
        sigungu=data.get("sigungu", ""),
    )

    if pub_result and pub_result.get("success"):
        article_id = pub_result.get("article_id")
        if article_id and body_html:
            register_images(article_id, target_blog_id, body_html)
        if article_id and body_md:
            register_images(article_id, target_blog_id, body_md)
        # 장소 발행 이력 등록 — 기사 본문에 실제로 등장하는 장소만 등록
        all_place_names = [it.get("title", it.get("facltNm", "")).strip()
                           for it in data.get("items", [])
                           if it.get("title") or it.get("facltNm")]
        # body_md에서 장소명 매칭 필터링 (대소문자 무시, 공백 정규화)
        _body_lower = (body_md or "").lower()
        _body_normalized = _body_lower.replace(" ", "")
        place_names = [
            n for n in all_place_names
            if n.lower().replace(" ", "") in _body_normalized
            or n.split()[0] in (body_md or "")  # 시군구명 등 부분 매칭 허용
        ]
        # 매칭된 장소가 없으면 전체 등록 (fallback — AI가 이름을 바꾼 경우 대비)
        if not place_names and all_place_names:
            place_names = all_place_names
        if article_id and place_names:
            register_places(article_id, target_blog_id, place_names)
            logger.info("장소 %d건 등록 (전체 %d건 중): %s",
                        len(place_names), len(all_place_names),
                        ", ".join(n[:10] for n in place_names))
        # course_published 테이블에 코스 contentid 등록 (travel4-hugo 중복 방지)
        if data.get("source_type") == "course" and data.get("content_ids"):
            try:
                import sqlite3 as _sq
                from shared.db_paths import PUBLISH_LEDGER_DB
                _cn = _sq.connect(PUBLISH_LEDGER_DB)
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


@log_stage("travel_pipeline")


def run(cfg):
    """dispatcher에서 호출하는 통일 인터페이스"""
    blog_id = cfg["id"]
    result = _run_single(blog_id, blog_cfg=cfg)

    # 발행 성공 시 품질 메트릭 기록 (Phase 16)
    if result and result.get("success"):
        try:
            from shared.quality_recorder import record_quality
            body_md = result.get("body_md", "")
            body_html = result.get("body_html", body_md)
            slug = result.get("slug", "")
            title = result.get("title", "")
            metrics = {
                "content_length": len(body_md) if body_md else 0,
                "paragraph_count": body_md.count("\n\n") + 1 if body_md else 0,
                "has_cta": "cta_html" in (result.get("body_html", "") or ""),
                "has_og_image": bool(result.get("thumbnail_url")),
                "min_length_pass": len(body_md or "") >= 500,
                "empty_template_count": 0,
            }
            record_quality(blog_id, slug, title, datetime.now().isoformat(), metrics)
        except Exception as e:
            logger.warning(f"[travel] 품질 메트릭 기록 실패 (비치명적): {e}")

    # 발행 후 섹션 인덱스 가드 (2026-05-01 추가)
    # content/posts/index.md 폭탄 방지 — 발견 시 로그 경고
    try:
        import subprocess
        _guard = "/Users/twinssn/Projects/TAP/scripts/check_section_index.sh"
        _r = subprocess.run(["bash", _guard], capture_output=True, text=True, timeout=10)
        if _r.returncode != 0:
            _msg = "[GUARD] 섹션 인덱스 이상 감지: " + (_r.stdout or "") + " | " + (_r.stderr or "")
            logger.error(_msg)
        else:
            logger.info("[GUARD] " + (_r.stdout or "").strip())
    except Exception as _e:
        logger.warning("[GUARD] 점검 스크립트 실행 실패: " + str(_e))

    return result

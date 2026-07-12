"""시니어 복지 파이프라인 — fetch → write → publish"""

import logging
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv

from shared.validators import assert_korean_or_reject, sanitize_title

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"))

logger = logging.getLogger(__name__)

_topic_index = {}


# ─── 헬퍼 함수 ───

def _get_published_titles(site_path):
    try:
        import glob as _glob
        posts_dir = os.path.join(site_path, "content", "posts")
        published = set()
        for md in _glob.glob(os.path.join(posts_dir, "*/index.md")):
            with open(md, encoding="utf-8") as f:
                content = f.read()
            m = re.search(r'^title:\s*["\'](.+?)["\']', content, re.MULTILINE)
            if m:
                published.add(m.group(1).strip())
        return published
    except Exception:
        return set()


def _pick_topic(blog_id, services):
    available = list({s["category"] for s in services})
    if not available:
        return "생활지원"
    idx = _topic_index.get(blog_id, 0)
    topic = available[idx % len(available)]
    _topic_index[blog_id] = idx + 1
    return topic


def _make_slug(title):
    return re.sub(r"[^가-힣a-zA-Z0-9\s-]", "", title).replace(" ", "-")[:80]


def _make_thumbnail(cfg, article, topic_type, platform):
    """썸네일 생성 — shared Playwright generator 사용"""
    try:
        from shared.thumbnail_generator import generate_thumbnail

        import hashlib
        from datetime import datetime

        title_hash = hashlib.md5(article["title"].encode()).hexdigest()[:10]
        slug = f"{datetime.now().strftime('%Y%m%d')}-{title_hash}"

        url = generate_thumbnail(
            site_id="senior",
            slug=slug,
            title=article["title"],
            category=article.get("category", topic_type),
        )
        if url:
            logger.info(f"[SeniorThumb] 생성 완료: {url}")
            return url
        logger.warning("[SeniorThumb] 생성 실패, 빈 값 반환")
    except Exception as e:
        logger.warning(f"Thumbnail failed: {e}")
    return ""


def _prepare_tags(article, topic_type):
    raw = article.get("tags", [])
    if isinstance(raw, list):
        tags = ", ".join(str(t).strip() for t in raw if str(t).strip())
    else:
        tags = str(raw)
    if "시니어복지" not in tags:
        tags = tags + ", 시니어복지" if tags else "시니어복지"
    return tags


def _convert_md_to_blogger_html(body_md):
    import markdown

    body_md = re.sub(
        r'\{\{<\s*btn\s+url="([^"]*)"\s+text="([^"]*)"\s*>\}\}',
        r'<div style="text-align:center;margin:20px 0"><a href="\1" target="_blank" '
        r'rel="noopener" style="display:inline-block;padding:14px 28px;background:#2563eb;'
        r'color:#fff;border-radius:8px;text-decoration:none;font-weight:bold;font-size:16px">\2</a></div>',
        body_md
    )
    body_md = re.sub(
        r"- \[([^\]]*)\]\((https://link\.coupang\.com[^)]+)\)",
        r'<div style="margin:8px 0"><a href="\2" target="_blank" rel="noopener" '
        r'style="color:#e74c3c;font-weight:bold">\1</a></div>',
        body_md
    )
    import re as _re
    html = markdown.markdown(body_md, extensions=["tables", "fenced_code"])
    def _auto_link(m) -> str:
        url = m.group(0)
        return f'<a href="{url}" target="_blank" rel="noopener">{url}</a>'
    return _re.sub(r'(?<!href=\")(?<!src=\")(https?://[^\s<>\"\)]+)', _auto_link, html)


# ─── 메인 run ───

def run(cfg):
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"), override=True)

    blog_id   = cfg.get("id", "senior-hugo")
    platform  = cfg.get("platform", "hugo")
    cfg.get("site_path", "")

    from pipelines.senior.fetcher import (
        SENIOR_DB_PATH,
        enrich_service_detail,
        get_pending_count,
        get_pending_service,
        sync_services,
    )
    from pipelines.senior.writer import generate_senior_article as generate_article
    from shared.content_store import get_today_count, init_db

    init_db()

    # 1. 일일 쿼터 체크
    today_count = get_today_count(blog_id)
    quota = cfg.get("daily_quota", 5)
    if today_count >= quota:
        logger.info(f"{blog_id}: 오늘 발행 완료 ({today_count}/{quota})")
        return {"success": False, "reason": "quota_met"}

    # 2. pending 소진 시 자동 재수집
    pending = get_pending_count()
    logger.info(f"{blog_id}: pending 서비스 {pending}건")
    if pending < 10:
        logger.info(f"pending {pending}건 부족 → API 재수집 시작")
        synced = sync_services()
        logger.info(f"재수집 완료: {synced}건 신규 저장")
        pending = get_pending_count()
        if pending == 0:
            logger.error(f"{blog_id}: 재수집 후에도 pending 0건")
            return {"success": False, "reason": "no_data"}

    # 3. 카테고리 선택
    topic_type = _pick_topic(blog_id, [])
    logger.info(f"Topic selected: {topic_type}")

    # 4. DB에서 pending 서비스 선택
    candidate = get_pending_service(category=topic_type)
    if not candidate:
        candidate = get_pending_service(category=None)
    if not candidate:
        logger.error(f"{blog_id}: pending 서비스 없음")
        return {"success": False, "reason": "no_data"}

    # 5. 상세 보강
    if not candidate.get("support_content"):
        candidate = enrich_service_detail(candidate)

    # 6. 만료 체크
    import re as _re
    from datetime import datetime as _dt
    dl = str(candidate.get("deadline", "")).strip()
    if dl:
        date_match = _re.search(r"(\d{4})[.\-/년]\s*(\d{1,2})[.\-/월]\s*(\d{1,2})", dl)
        if date_match:
            try:
                end_date = _dt(int(date_match.group(1)), int(date_match.group(2)), int(date_match.group(3)))
                if end_date < _dt.now():
                    logger.info(f"만료 서비스 skip: {candidate.get('service_name')} (deadline={dl})")
                    import sqlite3 as _sq
                    _c = _sq.connect(SENIOR_DB_PATH)
                    _c.execute("UPDATE services SET status='expired' WHERE service_id=?", (candidate.get("service_id",""),))
                    _c.commit()
                    _c.close()
                    return {"success": False, "reason": "expired_service"}
            except Exception:
                pass

    # 7. 글 생성 + 썸네일 R2 업로드
    try:
        from datetime import datetime as _dt2
        tags = _prepare_tags(candidate, topic_type)
        # related 서비스 — 같은 카테고리 pending 3건 추가 조회
        related_services = []
        try:
            import sqlite3 as _sq2
            _rc = _sq2.connect(SENIOR_DB_PATH)
            _rc.row_factory = _sq2.Row
            _rows = _rc.execute(
                """SELECT * FROM services
                   WHERE status='pending'
                   AND category=?
                   AND service_id != ?
                   ORDER BY id ASC LIMIT 3""",
                (candidate.get("category", "생활지원"), candidate.get("service_id", ""))
            ).fetchall()
            cols = ["id","service_id","service_name","description","target","category",
                    "apply_method","apply_url","department","support_content","purpose",
                    "selection_criteria","documents","contact","law_basis","deadline",
                    "status","collected_at","published_at"]
            for row in _rows:
                related_services.append(dict(zip(cols, row, strict=False)))
            _rc.close()
            logger.info(f"related 서비스 {len(related_services)}건 조회")
        except Exception as _re:
            logger.warning(f"related 조회 실패: {_re}")

        data = {
            "services": [candidate, *related_services],
            "jobs": [],
            "today": _dt2.now().strftime("%Y년 %m월 %d일"),
            "total_services": 1 + len(related_services),
            "total_jobs": 0,
            "categories": [candidate.get("category", "생활지원")],
        }
        article = generate_article(data, topic_type=topic_type, enriched_service=candidate)
        if not article:
            logger.error(f"{blog_id}: 글 생성 실패")
            return {"success": False, "reason": "no_content"}

        # 언어 검증 — 중국어 생성 차단
        _lang_err = assert_korean_or_reject(article.get("title", ""), article.get("body_md", ""), blog_id)
        if _lang_err:
            logger.error(f"[{blog_id}] {_lang_err}")
            return {"success": False, "reason": "language_error"}

        thumb_url = _make_thumbnail(cfg, article, topic_type, platform)
    except Exception as e:
        logger.exception(f"{blog_id}: 글 생성 예외: {e}")
        return {"success": False, "reason": "no_content"}

    # 8. 발행
    if platform == "hugo":
        return _do_publish_hugo(cfg, blog_id, article, tags, thumb_url, candidate)
    return _do_publish_blogger(cfg, blog_id, article, tags, thumb_url, candidate)


def _do_publish_hugo(cfg, blog_id, article, tags, thumb_url, candidate=None):
    from shared.publisher import publish

    _is_draft = False
    try:
        from shared.validators import validate_post_extended as _validate
        _val_ctx = {
            "keyword": article.get("keyword", ""),
            "event_date": article.get("event_date", article.get("policy_date", "")),
            "daily_quota": 5,
        }
        article["title"] = sanitize_title(article["title"])
        _issues = _validate(blog_id, article["title"], article.get("body_md", ""), _val_ctx, pipeline="senior")
        if _issues:
            _is_draft = True
            logger.warning(f"[Validate] {len(_issues)} issues -> draft: {_issues}")
    except Exception as _ve:
        logger.warning(f"[Validate] Error (non-fatal): {_ve}")

    try:
        result = publish(
            blog_id=blog_id,
            title=article["title"],
            body_md=article["body_md"],
            category=article.get("category", ""),
            tags=tags,
            thumbnail_url=thumb_url,
            is_draft=_is_draft,
            data_source="gov24_api",
            source_id=article.get("service_id", ""),
            model=os.getenv("OPENAI_MODEL", "mimo-v2.5"),
        )
        if result and result.get("success"):
            logger.info(f"Hugo published: {article['title']} -> {result.get('url')}")
            if candidate and candidate.get("service_id"):
                try:
                    from pipelines.senior.fetcher import mark_published
                    mark_published(candidate["service_id"])
                    logger.info(f"mark_published: {candidate['service_id']}")
                except Exception as _me:
                    logger.warning(f"mark_published 실패: {_me}")
            return result
        logger.error(f"Hugo publish failed: {result}")
        return {"success": False, "reason": "publish_error"}
    except Exception as e:
        logger.exception(f"Hugo publish error: {e}")
        return {"success": False, "reason": "publish_error"}


def _do_publish_blogger(cfg, blog_id, article, tags, thumb_url, candidate=None):
    body_html = _convert_md_to_blogger_html(article["body_md"])

    if thumb_url:
        thumb_html = (
            '<div style="text-align:center;margin-bottom:20px">'
            f'<img src="{thumb_url}" alt="{article["title"]}" '
            'style="max-width:100%;border-radius:12px" /></div>'
        )
        body_html = thumb_html + body_html

    from shared.publisher import publish

    _is_draft = False
    try:
        from shared.validators import validate_post_extended as _validate
        _val_ctx = {
            "keyword": article.get("keyword", ""),
            "event_date": article.get("event_date", article.get("policy_date", "")),
            "daily_quota": 5,
        }
        _issues = _validate(blog_id, article["title"], article.get("body_md", ""), _val_ctx, pipeline="senior")
        if _issues:
            _is_draft = True
            logger.warning(f"[Validate] {len(_issues)} issues -> draft: {_issues}")
    except Exception as _ve:
        logger.warning(f"[Validate] Error (non-fatal): {_ve}")

    try:
        result = publish(
            blog_id=blog_id,
            title=article["title"],
            body_md=article["body_md"],
            body_html=body_html,
            category=article.get("category", ""),
            tags=tags,
            thumbnail_url=thumb_url,
            is_draft=_is_draft,
            data_source="gov24_api",
            source_id=article.get("service_id", ""),
            model=os.getenv("OPENAI_MODEL", "mimo-v2.5"),
        )
        if result and result.get("success"):
            logger.info(f"Blogger published: {article['title']} -> {result.get('url')}")
            if candidate and candidate.get("service_id"):
                try:
                    from pipelines.senior.fetcher import mark_published
                    mark_published(candidate["service_id"])
                    logger.info(f"mark_published: {candidate['service_id']}")
                except Exception as _me:
                    logger.warning(f"mark_published 실패: {_me}")
            return result
        logger.error(f"Blogger publish failed: {result}")
        return {"success": False, "reason": "publish_error"}
    except Exception as e:
        logger.exception(f"Blogger publish error: {e}")
        return {"success": False, "reason": "publish_error"}

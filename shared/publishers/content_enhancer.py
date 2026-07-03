import logging
import os
import re
import sqlite3

from shared.paths import STAP_ROOT, TAP_ROOT

logger = logging.getLogger(__name__)

STAP_ENTITY_DB = os.path.join(STAP_ROOT, "data", "stap_entities.db")
STAP_ENTITY_LINKER_PATH = os.path.join(STAP_ROOT, "shared")
STAP_BLOGS = {"stock-hugo", "dividend-hugo", "etf-hugo", "sector-hugo", "ipo-hugo", "finance-hugo"}
TAP_TRAVEL_BLOGS = {"travel-hugo", "travel1-hugo", "travel2-hugo", "travel3-hugo", "travel4-hugo"}

try:
    import sys as _sys
    _sys.path.insert(0, os.path.join(TAP_ROOT, "core"))
    from tap_entity_manager import inject_cards as _tap_inject_cards
    from tap_entity_manager import register_post as _tap_register_post
    TAP_ENTITY_AVAILABLE = True
except Exception:
    TAP_ENTITY_AVAILABLE = False


def _insert_coupang(body_md, segment="", fuel_type="", blog_cfg=None):
    if not body_md:
        return body_md, "SKIP"
    if blog_cfg and blog_cfg.get("id", "").startswith("rap"):
        from shared.coupang_senior import inject_coupang as _cp
    elif segment or fuel_type:
        from shared.coupang_car import inject_coupang as _cp
    else:
        from shared.coupang_senior import inject_coupang as _cp
    try:
        result = _cp(body_md, segment=segment, fuel_type=fuel_type, blog_cfg=blog_cfg)
        result = re.sub(r"\{\{(?![<%])[^}]*\}\}", "", result)
        return result, "OK"
    except Exception as e:
        logger.warning(f"[COUPANG] inject failed: {e}")
        return body_md, "FAIL"


def _insert_internal_links(body_md, blog_id, slug):
    try:
        from shared.entity_linker import inject_internal_links
        result = inject_internal_links(body_md, blog_id, slug)
        return result or body_md
    except Exception as e:
        logger.warning(f"[LINKER] inject failed: {e}")
        return body_md


def _extract_first_image(body_md):
    m = re.search(r"!\[.*?\]\((.*?)\)", body_md or "")
    if m:
        return m.group(1)
    m = re.search(r'<img[^>]+src="(.*?)"', body_md or "")
    if m:
        return m.group(1)
    return ""


def _extract_description(body_md):
    clean = re.sub(r"<[^>]+>", "", body_md or "")
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean[:200]


def _get_related_posts(blog_id, current_slug, max_count=3):
    try:
        from shared.content_store import get_conn
        conn = get_conn()
        rows = conn.execute(
            "SELECT slug, title FROM articles WHERE blog_id=? AND slug!=? AND status='published' ORDER BY RANDOM() LIMIT ?",
            (blog_id, current_slug, max_count)
        ).fetchall()
        conn.close()
        return rows
    except Exception as e:
        logger.debug(f"[RELATED] query failed: {e}")
        return []


def _inject_related_cards_midpoint(body_md, blog_id, slug, title, category):
    cards_html = _inject_related_cards("", blog_id, slug, title, category)
    if not cards_html.strip():
        return body_md
    matches = list(re.finditer(r"^##\s+[^#\n]", body_md, re.MULTILINE))
    if len(matches) >= 2:
        insert_pos = matches[-1].start()
        return body_md[:insert_pos] + cards_html.lstrip("\n") + "\n\n" + body_md[insert_pos:]
    return body_md.rstrip() + cards_html


def _inject_related_cards(body_md, blog_id, slug, title, category):
    import re as _re
    import sqlite3 as _sq

    STAP_CONTENT_DB = os.path.join(STAP_ROOT, "data", "stap_content.db")
    BLOG_DOMAINS = {
        "stock-hugo": "https://stock.informationhot.kr",
        "dividend-hugo": "https://dividend.techpawz.com",
        "etf-hugo": "https://etf.techpawz.com",
        "sector-hugo": "https://sector.techpawz.com",
        "ipo-hugo": "https://ipo.techpawz.com",
        "finance-hugo": "https://finance.techpawz.com",
    }
    BLOG_LABELS = {
        "stock-hugo": "주식분석",
        "dividend-hugo": "배당블로그",
        "etf-hugo": "ETF블로그",
        "sector-hugo": "업종분석",
        "ipo-hugo": "IPO블로그",
        "finance-hugo": "금융블로그",
    }
    _JOSA_END = _re.compile(r"[이가을를은는에서으로과와도만도의]$")
    _VERB_END = _re.compile(r"[한된됩습니다했하며이인한]$")
    _NUMBER_ONLY = _re.compile(r"^\d+$")

    def _extract_keywords(t):
        stop = {
            "분석","비교","추천","전망","가이드","입문","투자","배당","실적",
            "영업","이익","매출","증가","감소","급등","급락","순이익","손실",
            "원가","절감","업종","업황","리스크","판단","결론","현황","정리",
            "방법","이유","원인","효과","전략","수익","금리","예금","적금",
            "영향","기록","개선","비밀","가져온","미친","지속",
        }
        candidates = _re.findall(r"[가-힣]{3,10}", t)
        result = []
        for c in candidates:
            if c in stop:
                continue
            if _JOSA_END.search(c):
                c = _JOSA_END.sub("", c)
            if len(c) < 2 or _NUMBER_ONLY.match(c) or _VERB_END.search(c):
                continue
            result.append(c)
        return result[:10]

    cards = []

    if blog_id in STAP_BLOGS:
        try:
            conn = _sq.connect(STAP_CONTENT_DB)
            conn.row_factory = _sq.Row
            same_blog = conn.execute(
                "SELECT title, published_url, slug FROM articles WHERE blog_id=? AND slug!=? AND status='published' ORDER BY ROWID DESC LIMIT 2",
                (blog_id, slug)
            ).fetchall()
            for r in same_blog:
                url = r["published_url"] or f'{BLOG_DOMAINS.get(blog_id, "")}/{r["slug"]}/'
                cards.append((r["title"], url, "same-blog"))
            keywords = _extract_keywords(title)
            if keywords:
                cross = conn.execute(
                    "SELECT title, published_url, slug, blog_id FROM articles WHERE blog_id IN "
                     "(" + ",".join("?" for _ in STAP_BLOGS) + ") AND blog_id!=? AND slug!=? AND status='published' ORDER BY ROWID DESC LIMIT 6",
                    tuple(STAP_BLOGS) + (blog_id, slug)
                ).fetchall()
                for r in cross:
                    kw_title = _extract_keywords(r["title"])
                    if any(k in " ".join(kw_title) for k in keywords):
                        url = r["published_url"] or f'{BLOG_DOMAINS.get(r["blog_id"], "")}/{r["slug"]}/'
                        cards.append((r["title"], url, BLOG_LABELS.get(r["blog_id"], "other")))
                        if len(cards) >= 4:
                            break
            conn.close()
        except Exception as e:
            logger.debug(f"[CARDS] query failed: {e}")

    if not cards:
        return ""

    html = '\n<div class="related-cards">\n<h2>함께 읽으면 좋은 글</h2>\n<div class="card-grid">\n'
    for title_text, url, label in cards:
        html += f'<a href="{url}" class="related-card">\n<span class="card-label">{label}</span>\n<span class="card-title">{title_text}</span>\n</a>\n'
    html += "</div>\n</div>\n"
    return html

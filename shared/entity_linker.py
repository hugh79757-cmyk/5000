"""
entity_linker.py – ETAP 내부링크 자동 삽입 시스템

기능:
1. register_entity() – 글 발행 시 엔티티 DB에 등록
2. mark_entity_published() – 발행 완료 시 published=1
3. inject_internal_links() – 본문에서 엔티티 키워드를 찾아 내부링크 삽입

규칙:
- 같은 키워드는 글 내 첫 등장 1회만 링크
- 자기 블로그 링크 제외
- H1/H2 제목 안에는 링크 안 함
- 이미 마크다운 링크 안에 있는 텍스트는 건너뜀
- 글 하나당 내부링크 최대 max_links개
- published=1인 엔티티만 링크 대상
"""

import sqlite3
import re
import os
import logging

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "travel-en.db")

BLOG_DOMAINS = {
    "tour-hugo":        "https://tour.techpawz.com",
    "flights-hugo":     "https://flights.techpawz.com",
    "tours-hugo":       "https://tours.techpawz.com",
    "michelin-hugo":    "https://michelin.techpawz.com",
    "visa-hugo":        "https://visa.techpawz.com",
    "esim-hugo":        "https://esim.techpawz.com",
    "trains-hugo":      "https://trains.techpawz.com",
    "airports-hugo":    "https://airports.techpawz.com",
    "airlines-hugo":    "https://airlines.techpawz.com",
    "daytrips-hugo":    "https://daytrips.techpawz.com",
    "walking-hugo":     "https://walking.techpawz.com",
    "foodtour-hugo":    "https://foodtour.techpawz.com",
    "adventure-hugo":   "https://adventure.techpawz.com",
    "watersports-hugo": "https://watersports.techpawz.com",
    "bus-hugo":         "https://bus.techpawz.com",
    "ferry-hugo":       "https://ferry.techpawz.com",
    "dining-hugo":      "https://dining.techpawz.com",
    "culture-hugo":     "https://culture.techpawz.com",
    "transfers-hugo":   "https://transfers.techpawz.com",
    "multiday-hugo":    "https://multiday.techpawz.com",
    "nature-hugo":      "https://nature.techpawz.com",
    "visafree-hugo":    "https://visafree.techpawz.com",
    "deals-hugo":       "https://deals.techpawz.com",
    "eurail-hugo":      "https://eurail.techpawz.com",
    "cruise-hugo":      "https://cruise.techpawz.com",
    "phototour-hugo":   "https://phototour.techpawz.com",
}


def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def register_entity(entity_type, entity_name, blog_id, post_slug,
                     link_label, priority=50, published=0):
    """글 발행 시 엔티티 등록. 이미 있으면 무시."""
    if not entity_name or len(entity_name) <= 2:
        return
    domain = BLOG_DOMAINS.get(blog_id, "")
    if not domain:
        logger.warning(f"Unknown blog_id: {blog_id}")
        return
    post_url = f"{domain}/posts/{post_slug}/"
    conn = _get_db()
    try:
        conn.execute("""
            INSERT OR IGNORE INTO entity_links
            (entity_type, entity_name, blog_id, post_slug, post_url,
             link_label, priority, published)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (entity_type, entity_name, blog_id, post_slug,
              post_url, link_label, priority, published))
        conn.commit()
    except Exception as e:
        logger.error(f"register_entity failed: {e}")
    finally:
        conn.close()


def mark_entity_published(blog_id, post_slug):
    """발행 완료된 글의 엔티티를 published=1로 마킹"""
    conn = _get_db()
    try:
        updated = conn.execute("""
            UPDATE entity_links SET published = 1
            WHERE blog_id = ? AND post_slug = ?
        """, (blog_id, post_slug)).rowcount
        conn.commit()
        if updated:
            logger.info(f"Entity published: {blog_id}/{post_slug} ({updated}건)")
        return updated
    except Exception as e:
        logger.error(f"mark_entity_published failed: {e}")
        return 0
    finally:
        conn.close()


def get_cross_links(country=None, city=None, exclude_blog=None, max_links=5):
    """
    같은 국가/도시에 대해 다른 블로그에서 발행된 글 목록 반환.
    published=1인 것만.
    """
    conn = _get_db()
    links = []
    try:
        conditions = ["published = 1"]
        params = []

        if exclude_blog:
            conditions.append("blog_id != ?")
            params.append(exclude_blog)

        names = []
        if country:
            names.append(country)
        if city:
            names.append(city)

        if not names:
            return links

        name_conditions = " OR ".join(["entity_name = ?"] * len(names))
        conditions.append(f"({name_conditions})")
        params.extend(names)

        sql = f"""
            SELECT DISTINCT entity_type, entity_name, blog_id, post_slug,
                   post_url, link_label, priority
            FROM entity_links
            WHERE {' AND '.join(conditions)}
            ORDER BY priority DESC
            LIMIT ?
        """
        params.append(max_links)

        links = [dict(r) for r in conn.execute(sql, params).fetchall()]
    except Exception as e:
        logger.error(f"get_cross_links failed: {e}")
    finally:
        conn.close()
    return links


def inject_internal_links(content, current_blog, max_links=5):
    """
    본문(markdown)에서 entity_name이 등장하면 내부링크로 교체.

    규칙:
    - published=1인 엔티티만 대상
    - current_blog 자신은 제외
    - 같은 키워드 첫 등장 1회만
    - H1/H2 헤딩 라인 내부는 건너뜀
    - 이미 []() 링크 안에 있는 텍스트는 건너뜀
    - 최대 max_links개
    """
    conn = _get_db()
    try:
        # 발행된 엔티티 중 현재 블로그가 아닌 것
        entities = conn.execute("""
            SELECT entity_name, post_url, link_label, priority
            FROM entity_links
            WHERE published = 1 AND blog_id != ?
            ORDER BY priority DESC, length(entity_name) DESC
        """, (current_blog,)).fetchall()
    except Exception as e:
        logger.error(f"inject_internal_links DB error: {e}")
        return content
    finally:
        conn.close()

    if not entities:
        return content

    lines = content.split("\n")
    linked_names = set()
    total_links_added = 0

    for entity in entities:
        if total_links_added >= max_links:
            break

        name = entity["entity_name"]
        url = entity["post_url"]

        if name in linked_names:
            continue

        # 이름이 너무 짧으면 skip (오탐 방지)
        if len(name) <= 3:
            continue

        # 정규식: 단어 경계로 매칭, 대소문자 무시하지 않음 (고유명사)
        pattern = re.compile(
            r'(?<!\[)(?<!\()'          # 앞에 [ 또는 ( 가 아닌
            r'\b(' + re.escape(name) + r')\b'
            r'(?!\]|\))'               # 뒤에 ] 또는 ) 가 아닌
        )

        replaced = False
        for i, line in enumerate(lines):
            # H1/H2 라인 skip
            if line.startswith("# ") or line.startswith("## "):
                continue

            # 이미 링크 안에 있는지 전체 체크
            # 마크다운 링크 패턴 안의 텍스트는 건너뜀
            if f"[{name}]" in line or f"({name})" in line:
                continue

            # 이미 이 라인에 마크다운 링크가 있으면, 링크 내부 텍스트 제외하고 매칭
            # 링크 영역을 임시로 플레이스홀더로 교체
            placeholders = []
            def _placeholder(m):
                placeholders.append(m.group(0))
                return f"__LINK_PH_{len(placeholders)-1}__"

            safe_line = re.sub(r'\[.*?\]\(.*?\)', _placeholder, line)

            m = pattern.search(safe_line)
            if m:
                # 원본 line에서 같은 위치에 교체
                replacement = f"[{name}]({url})"
                safe_line = safe_line[:m.start()] + replacement + safe_line[m.end():]

                # 플레이스홀더 복원
                for j, ph in enumerate(placeholders):
                    safe_line = safe_line.replace(f"__LINK_PH_{j}__", ph)

                lines[i] = safe_line
                linked_names.add(name)
                total_links_added += 1
                replaced = True
                break

            # 플레이스홀더 복원 (교체 안 된 경우)
            if not replaced:
                for j, ph in enumerate(placeholders):
                    safe_line = safe_line.replace(f"__LINK_PH_{j}__", ph)

    result = "\n".join(lines)
    if total_links_added:
        logger.info(f"내부링크 {total_links_added}개 삽입 (대상: {list(linked_names)})")
    return result


def build_cross_sell_html(country=None, city=None, exclude_blog=None, max_items=3):
    """
    크로스셀 HTML 블록 생성.
    상단에 자연스럽게 배치할 수 있는 관련 링크 카드.
    """
    links = get_cross_links(country=country, city=city,
                            exclude_blog=exclude_blog, max_links=max_items)
    if not links:
        return ""

    # 블로그 타입별 아이콘
    ICONS = {
        "visa-hugo": "📋",
        "esim-hugo": "📱",
        "tours-hugo": "🎯",
        "michelin-hugo": "🍽️",
        "trains-hugo": "🚆",
        "airports-hugo": "✈️",
        "airlines-hugo": "🛫",
        "flights-hugo": "💰",
        "tour-hugo": "🗺️",
        "daytrips-hugo": "🚌",
        "walking-hugo": "🚶",
        "foodtour-hugo": "🍜",
        "adventure-hugo": "🧗",
        "watersports-hugo": "🏄",
        "bus-hugo": "🚍",
        "ferry-hugo": "⛴️",
        "dining-hugo": "🍷",
        "culture-hugo": "🏛️",
        "transfers-hugo": "🚐",
        "multiday-hugo": "🗓️",
        "nature-hugo": "🌿",
        "visafree-hugo": "🛂",
        "deals-hugo": "✈️",
        "eurail-hugo": "🚄",
        "cruise-hugo": "🚢",
        "phototour-hugo": "📸",
    }

    items_html = []
    for link in links:
        icon = ICONS.get(link["blog_id"], "🔗")
        label = link["link_label"]
        url = link["post_url"]
        items_html.append(
            f'<a href="{url}" style="display:inline-flex;align-items:center;gap:6px;'
            f'padding:8px 14px;background:#f0f7ff;border:1px solid #d0e3ff;'
            f'border-radius:8px;text-decoration:none;color:#1a56db;font-size:14px;'
            f'margin:4px">{icon} {label}</a>'
        )

    name = city or country or ""
    html = (
        f'\n<div style="margin:20px 0;padding:16px;background:#fafbfc;'
        f'border-radius:12px;border:1px solid #e8ecf0">\n'
        f'<p style="margin:0 0 10px;font-weight:600;font-size:15px;color:#374151">'
        f'📌 More about {name}</p>\n'
        f'<div style="display:flex;flex-wrap:wrap;gap:4px">\n'
        + "\n".join(items_html) +
        f'\n</div>\n</div>\n'
    )
    return html

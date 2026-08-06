"""cuap_entity_linker.py – CUAP 거미줄 엔티티 링크 시스템

기능:
1. register_cuap_entity() – 글 발행 시 엔티티 DB에 등록
2. inject_cross_blog_links() – 본문에서 엔티티 키워드를 찾아 타 블로그 링크 삽입
3. build_cross_sell_card() – 크로스셀 카드 HTML 생성 (본문 하단)
4. build_funnel_header() – 퍼널 헤더 HTML 생성 (본문 상단)
5. init_cuap_tables() – travel-en.db에 CUAP 테이블 생성

규칙 (ETAP entity_linker.py 패턴 재사용):
- 같은 키워드는 글 내 첫 등장 1회만 링크
- 자기 블로그 링크 제외
- H1/H2 제목 안에는 링크 안 함
- 이미 마크다운 링크 안에 있는 텍스트는 건너뜀
- 글 하나당 내부링크 최대 max_links개
- published=1인 엔티티만 링크 대상

보안:
- 모든 SQL은 parameterized query (? 플레이스홀더)
- HTML은 inline style만, JavaScript 없음
- URL은 BLOG_DOMAINS에서만 구성 (외부 입력 차단)
"""

import logging
import os
import re
import sqlite3

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "travel-en.db")

# 10개 CUAP 블로그 도메인 (config/blogs.d/cuap.yaml 기준)
BLOG_DOMAINS = {
    "appliance-hugo": "https://appliance.informationhot.kr",
    "baby-hugo":      "https://baby.informationhot.kr",
    "fitness-hugo":   "https://fitness.informationhot.kr",
    "interior-hugo":  "https://interior.informationhot.kr",
    "laptop-hugo":    "https://laptop.informationhot.kr",
    "health-hugo":    "https://health.informationhot.kr",
    "pet-hugo":       "https://pet.informationhot.kr",
    "kitchen-hugo":   "https://kitchen.informationhot.kr",
    "beauty-hugo":    "https://beauty.informationhot.kr",
    "camping-hugo":   "https://camping.informationhot.kr",
    "massage-hugo":      "https://massage.informationhot.kr",
    "car-hugo":          "https://car.informationhot.kr",
    "homeappliance-hugo":"https://homeappliance.informationhot.kr",
    "golf-hugo":         "https://golf.informationhot.kr",
    "bike-hugo":         "https://bike.informationhot.kr",
}

# 블로그별 아이콘
ICONS = {
    "appliance-hugo": "🔌",
    "baby-hugo":      "👶",
    "fitness-hugo":   "💪",
    "interior-hugo":  "🛋️",
    "laptop-hugo":    "💻",
    "health-hugo":    "🍎",
    "pet-hugo":       "🐾",
    "kitchen-hugo":   "🍳",
    "beauty-hugo":    "💄",
    "camping-hugo":   "⛺",
}

# 블로그별 테마 컬러 (퍼널 헤더)
THEME_COLORS = {
    "appliance-hugo": "#2563eb",
    "baby-hugo":      "#ec4899",
    "fitness-hugo":   "#16a34a",
    "interior-hugo":  "#a16207",
    "laptop-hugo":    "#7c3aed",
    "health-hugo":    "#dc2626",
    "pet-hugo":       "#d97706",
    "kitchen-hugo":   "#ea580c",
    "beauty-hugo":    "#db2777",
    "camping-hugo":   "#0891b2",
}

# 10개 블로그 연결 그래프 (고정 퍼널 경로)
# weight: primary=100, secondary=50, use_cases=30
CROSS_GRAPH = {
    "beauty-hugo": {
        "primary": ["appliance-hugo", "camping-hugo"],
        "secondary": ["interior-hugo", "health-hugo"],
        "use_cases": ["kitchen-hugo", "baby-hugo"],
    },
    "appliance-hugo": {
        "primary": ["kitchen-hugo", "interior-hugo"],
        "secondary": ["laptop-hugo", "camping-hugo"],
        "use_cases": ["baby-hugo", "pet-hugo"],
    },
    "kitchen-hugo": {
        "primary": ["appliance-hugo", "interior-hugo"],
        "secondary": ["baby-hugo", "health-hugo"],
        "use_cases": ["pet-hugo", "camping-hugo"],
    },
    "interior-hugo": {
        "primary": ["appliance-hugo", "kitchen-hugo"],
        "secondary": ["camping-hugo", "baby-hugo"],
        "use_cases": ["fitness-hugo", "beauty-hugo"],
    },
    "laptop-hugo": {
        "primary": ["appliance-hugo", "fitness-hugo"],
        "secondary": ["camping-hugo", "health-hugo"],
        "use_cases": ["pet-hugo", "baby-hugo"],
    },
    "fitness-hugo": {
        "primary": ["health-hugo", "camping-hugo"],
        "secondary": ["baby-hugo", "interior-hugo"],
        "use_cases": ["beauty-hugo", "kitchen-hugo"],
    },
    "health-hugo": {
        "primary": ["fitness-hugo", "kitchen-hugo"],
        "secondary": ["baby-hugo", "beauty-hugo"],
        "use_cases": ["pet-hugo", "interior-hugo"],
    },
    "baby-hugo": {
        "primary": ["kitchen-hugo", "health-hugo"],
        "secondary": ["interior-hugo", "pet-hugo"],
        "use_cases": ["beauty-hugo", "appliance-hugo"],
    },
    "pet-hugo": {
        "primary": ["baby-hugo", "kitchen-hugo"],
        "secondary": ["interior-hugo", "health-hugo"],
        "use_cases": ["camping-hugo", "appliance-hugo"],
    },
    "camping-hugo": {
        "primary": ["appliance-hugo", "fitness-hugo"],
        "secondary": ["interior-hugo", "pet-hugo"],
        "use_cases": ["kitchen-hugo", "laptop-hugo"],
    },
}


def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_cuap_tables():
    """travel-en.db에 CUAP 전용 테이블 생성 (ETAP entity_links는 수정하지 않음)."""
    conn = _get_db()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cuap_entities (
                entity_type TEXT,
                entity_name TEXT,
                blog_id TEXT,
                post_slug TEXT,
                post_url TEXT,
                link_label TEXT,
                category TEXT,
                priority INTEGER,
                published INTEGER DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cuap_link_graph (
                source_blog TEXT,
                target_blog TEXT,
                link_type TEXT,
                weight INTEGER
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_cuap_entities_blog_pub "
            "ON cuap_entities(blog_id, published)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_cuap_entities_name "
            "ON cuap_entities(entity_name)"
        )
        conn.commit()
        logger.info("CUAP tables initialized (cuap_entities, cuap_link_graph)")
    except Exception as e:
        logger.exception(f"init_cuap_tables failed: {e}")
        raise
    finally:
        conn.close()


def register_cuap_entity(entity_type, entity_name, blog_id, post_slug,
                         link_label, priority=50, published=0) -> None:
    """글 발행 시 엔티티 등록. 이미 있으면 무시 (INSERT OR IGNORE).

    보안: entity_name len > 2, blog_id in BLOG_DOMAINS 검증.
    """
    if not entity_name or len(entity_name) <= 2:
        return
    domain = BLOG_DOMAINS.get(blog_id, "")
    if not domain:
        logger.warning(f"Unknown blog_id: {blog_id}")
        return
    # CUAP 블로그 permalink은 /posts/<slug>/ 형식 (Blowfish 테마 기본)
    post_url = f"{domain}/posts/{post_slug}/"
    conn = _get_db()
    try:
        conn.execute("""
            INSERT OR IGNORE INTO cuap_entities
            (entity_type, entity_name, blog_id, post_slug, post_url,
             link_label, priority, published)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (entity_type, entity_name, blog_id, post_slug,
              post_url, link_label, priority, published))
        conn.commit()
    except Exception as e:
        logger.exception(f"register_cuap_entity failed: {e}")
    finally:
        conn.close()


def inject_cross_blog_links(content, blog_id, max_links=3):
    """본문(markdown)에서 entity_name이 등장하면 타 블로그 링크로 교체.

    규칙:
    - published=1인 엔티티만 대상
    - blog_id 자신은 제외
    - 같은 키워드 첫 등장 1회만
    - H1/H2 헤딩 라인 내부는 건너뜀
    - 이미 []() 링크 안에 있는 텍스트는 건너뜀
    - 최대 max_links개
    """
    conn = _get_db()
    try:
        entities = conn.execute("""
            SELECT entity_name, post_url, link_label, priority
            FROM cuap_entities
            WHERE published = 1 AND blog_id != ?
            ORDER BY priority DESC, length(entity_name) DESC
        """, (blog_id,)).fetchall()
    except Exception as e:
        logger.exception(f"inject_cross_blog_links DB error: {e}")
        entities = []
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

        pattern = re.compile(
            r"(?<!\[)(?<!\()"          # 앞에 [ 또는 ( 가 아닌
            r"\b(" + re.escape(name) + r")\b"
            r"(?!\]|\))"               # 뒤에 ] 또는 ) 가 아닌
        )

        replaced = False
        for i, line in enumerate(lines):
            if line.startswith(("# ", "## ")):
                continue

            if f"[{name}]" in line or f"({name})" in line:
                continue

            placeholders = []
            def _placeholder(m) -> str:
                placeholders.append(m.group(0))
                return f"__LINK_PH_{len(placeholders)-1}__"

            safe_line = re.sub(r"\[.*?\]\(.*?\)", _placeholder, line)

            m = pattern.search(safe_line)
            if m:
                replacement = f"[{name}]({url})"
                safe_line = safe_line[:m.start()] + replacement + safe_line[m.end():]

                for j, ph in enumerate(placeholders):
                    safe_line = safe_line.replace(f"__LINK_PH_{j}__", ph)

                lines[i] = safe_line
                linked_names.add(name)
                total_links_added += 1
                replaced = True
                break

            if not replaced:
                for j, ph in enumerate(placeholders):
                    safe_line = safe_line.replace(f"__LINK_PH_{j}__", ph)

    result = "\n".join(lines)
    if total_links_added:
        logger.info(f"CUAP 크로스링크 {total_links_added}개 삽입 (대상: {list(linked_names)})")
    return result


# ── cross-sell 차단 블로그 (CoT 미해결 또는 오염 블로그) ──
BLOCKED_CROSS_SELL_BLOGS = {"fitness-hugo", "laptop-hugo"}

# ── 후기·실사용 프레임 slug 필터 ──
_REVIEW_FRAME_PATTERNS = ["실사용", "후기", "느낌", "써본", "리뷰"]

# ── fallback용 안전 블로그 (우선순위) ──
_SAFE_FALLBACK_BLOGS = [
    "kitchen-hugo", "baby-hugo", "beauty-hugo",
    "camping-hugo", "appliance-hugo", "interior-hugo",
]


def _is_review_frame_slug(slug: str) -> bool:
    """slug에 후기·실사용 프레임 문자열이 포함되어 있는지 판정."""
    return any(p in slug for p in _REVIEW_FRAME_PATTERNS)


def _target_blogs(blog_id, max_targets=4):
    """CROSS_GRAPH에서 대상 블로그 목록 반환 (primary → secondary 순).

    BLOCKED_CROSS_SELL_BLOGS 에 해당하는 블로그는 제외.
    """
    graph = CROSS_GRAPH.get(blog_id, {})
    targets = list(graph.get("primary", []))
    for t in graph.get("secondary", []):
        if t not in targets:
            targets.append(t)
    return [t for t in targets if t not in BLOCKED_CROSS_SELL_BLOGS][:max_targets]


def _pick_safe_entity(conn, blog_id, max_candidates=5):
    """안전한 엔티티(후기 프레임 미포함)를 선택. 없으면 None 반환."""
    rows = conn.execute("""
        SELECT entity_name, post_url, link_label, post_slug
        FROM cuap_entities
        WHERE published = 1 AND blog_id = ?
        ORDER BY priority DESC, rowid DESC
        LIMIT ?
    """, (blog_id, max_candidates)).fetchall()
    for r in rows:
        if not _is_review_frame_slug(r["post_slug"] or ""):
            return r
    return None


def _fallback_blog(blog_id, used_blogs, max_candidates=5):
    """blocked/필터된 블로그 대체: 안전 블로그에서 첫 번째 엔티티 반환.

    audit Q5 준수: CROSS_GRAPH[blog_id]에 정의된 블로그(primary/secondary/
    use_cases 합집합)만 fallback 대상으로 제한. 그래프 밖 무관 크로스링크
    (INC-CL-01~04: camping→baby, health→camping, laptop→kitchen,
    pet→beauty)를 차단한다. 판정 기준은 crosslink.py _is_crosslink_allowed와
    동일 — CROSS_GRAPH가 카테고리 인접성 메타데이터.
    """
    graph = CROSS_GRAPH.get(blog_id, {})
    allowed = set()
    for category in ("primary", "secondary", "use_cases"):
        allowed.update(graph.get(category, []))
    if not allowed:
        return None, None
    for fb in _SAFE_FALLBACK_BLOGS:
        if fb == blog_id or fb in used_blogs or fb not in allowed:
            continue
        conn = _get_db()
        try:
            row = _pick_safe_entity(conn, fb, max_candidates)
            if row:
                return fb, row
        finally:
            conn.close()
    return None, None


def build_cross_sell_card(blog_id, max_items=4):
    """크로스셀 카드 HTML 생성. 본문 하단에 삽입.

    CROSS_GRAPH 기반으로 타 블로그 최신 발행 글을 카드로 노출.
    - BLOCKED_CROSS_SELL_BLOGS 차단
    - 후기·실사용 프레임 slug 필터
    - 부족 시 안전 블로그로 fallback
    """
    conn = _get_db()
    try:
        targets = _target_blogs(blog_id, max_items + 2)  # 여유분 확보
        if not targets:
            return ""

        items_html = []
        used_blogs = set()
        for target in targets:
            if len(items_html) >= max_items:
                break
            row = _pick_safe_entity(conn, target)
            if not row:
                logger.warning(
                    f"[cross-sell] No safe entity for target={target} "
                    f"in card for blog={blog_id}"
                )
                continue
            icon = ICONS.get(target, "🔗")
            label = row["link_label"] or row["entity_name"]
            url = row["post_url"]
            items_html.append(
                f'<a href="{url}" class="cross-sell-card__link">{icon} {label}</a>'
            )
            used_blogs.add(target)

        # fallback: 부족하면 안전 블로그로 채우기
        while len(items_html) < max_items:
            fb_blog, fb_row = _fallback_blog(blog_id, used_blogs)
            if not fb_row:
                break
            icon = ICONS.get(fb_blog, "🔗")
            label = fb_row["link_label"] or fb_row["entity_name"]
            url = fb_row["post_url"]
            items_html.append(
                f'<a href="{url}" class="cross-sell-card__link">{icon} {label}</a>'
            )
            used_blogs.add(fb_blog)
            logger.info(f"[cross-sell] fallback: {blog_id} → {fb_blog}")
    except Exception as e:
        logger.exception(f"build_cross_sell_card failed: {e}")
        return ""
    finally:
        conn.close()

    if not items_html:
        return ""

    if len(items_html) < max_items:
        logger.warning(
            f"[cross-sell] Only {len(items_html)}/{max_items} links for blog={blog_id}"
        )

    return (
        f'\n<div class="cross-sell-card">\n'
        f'<p class="cross-sell-card__title">'
        f'🛍️ 이런 상품도 좋아하실 거예요</p>\n'
        f'<div class="cross-sell-card__links">\n'
        + "\n".join(items_html) +
        "\n</div>\n</div>\n"
    )


def build_funnel_header(blog_id):
    """퍼널 헤더 HTML 생성. 본문 상단에 삽입.

    CROSS_GRAPH primary 연결 기반으로 카테고리 유도 링크 노출.
    - BLOCKED_CROSS_SELL_BLOGS 차단
    - 후기·실사용 프레임 slug 필터
    - 부족 시 안전 블로그로 fallback (최대 3개)
    """
    graph = CROSS_GRAPH.get(blog_id, {})
    primaries = graph.get("primary", [])
    if not primaries:
        return ""

    color = THEME_COLORS.get(blog_id, "#1a56db")
    items_html = []
    used_blogs = set()

    for target in primaries:
        if len(items_html) >= 3:
            break
        if target in BLOCKED_CROSS_SELL_BLOGS:
            logger.info(f"[funnel] excluded: {target} (blocked blog)")
            continue
        conn = _get_db()
        try:
            row = _pick_safe_entity(conn, target)
        finally:
            conn.close()
        if not row:
            logger.info(f"[funnel] no safe entity for {target}")
            continue
        icon = ICONS.get(target, "🔗")
        label = row["link_label"] or row["entity_name"]
        url = row["post_url"]
        items_html.append(
            f'<a href="{url}" class="funnel-header__link" style="color:{color}">'
            f'{icon} {label}</a>'
        )
        used_blogs.add(target)

    # fallback: 3개 미달 시 안전 블로그로 채우기
    while len(items_html) < 3:
        fb_blog, fb_row = _fallback_blog(blog_id, used_blogs)
        if not fb_row:
            break
        icon = ICONS.get(fb_blog, "🔗")
        label = fb_row["link_label"] or fb_row["entity_name"]
        url = fb_row["post_url"]
        items_html.append(
            f'<a href="{url}" class="funnel-header__link" style="color:{color}">'
            f'{icon} {label}</a>'
        )
        used_blogs.add(fb_blog)
        logger.info(f"[funnel] fallback: {blog_id} → {fb_blog}")

    if not items_html:
        return ""

    return (
        f'<div class="funnel-header">\n'
        f'<p class="funnel-header__label">'
        f'💡 다른 추천도 확인해보세요</p>\n'
        f'<div class="funnel-header__links">' + "\n".join(items_html) +
        "\n</div>\n</div>\n\n"
    )

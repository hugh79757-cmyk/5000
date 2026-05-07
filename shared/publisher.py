import logging
logger = logging.getLogger(__name__)
import os
import sqlite3
import re
import yaml
import subprocess
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(override=True)
from shared.content_store import insert_article, update_published, get_today_count


STAP_ENTITY_DB = "/Users/twinssn/Projects/STAP/data/stap_entities.db"
STAP_ENTITY_LINKER_PATH = "/Users/twinssn/Projects/STAP/shared"

# TAP 엔티티 (6개 여행 블로그 교차 카드)
TAP_TRAVEL_BLOGS = {
    "travel-hugo", "travel1-hugo", "travel2-hugo",
    "travel3-hugo", "travel4-hugo",
}
try:
    import sys as _sys
    _sys.path.insert(0, "/Users/twinssn/Projects/TAP/core")
    from tap_entity_manager import inject_cards as _tap_inject_cards
    from tap_entity_manager import register_post as _tap_register_post
    TAP_ENTITY_AVAILABLE = True
except Exception:
    TAP_ENTITY_AVAILABLE = False


CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")


def load_blogs():
    blogs = []
    main_path = os.path.join(CONFIG_DIR, "blogs.yaml")
    with open(main_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    blogs.extend(data.get("blogs", []))
    blogs_d = os.path.join(CONFIG_DIR, "blogs.d")
    if os.path.isdir(blogs_d):
        for fname in sorted(os.listdir(blogs_d)):
            if fname.endswith(".yaml"):
                with open(os.path.join(blogs_d, fname), "r", encoding="utf-8") as f:
                    d = yaml.safe_load(f) or {}
                blogs.extend(d.get("blogs", []))
    return blogs


def get_blog_config(blog_id):
    blogs = load_blogs()
    for b in blogs:
        if b["id"] == blog_id:
            return b
    raise ValueError("Blog not found: " + blog_id)


def slugify(text):
    text = re.sub(r"[^\w\s가-힣-]", "", text)
    text = re.sub(r"[\s]+", "-", text.strip())
    return text.lower()[:80]


# ===== 2026-05-01: front matter sanitize / 검증 헬퍼 =====
def _sanitize_yaml_value(s, max_len=None):
    """YAML 문자열 값을 안전하게 정리 (한글 블로그 대응)."""
    if s is None:
        return ""
    s = str(s)
    # 한글 스마트 따옴표 정규화
    smart = {
        "“": '"', "”": '"',
        "‘": "'", "’": "'",
        "«": '"', "»": '"',
        "「": '"', "」": '"',
        "『": '"', "』": '"',
    }
    for k, v in smart.items():
        s = s.replace(k, v)
    # 제어문자 제거 (NULL, CR, LF, TAB은 공백으로)
    s = s.replace("\x00", "")
    s = s.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    # 비인쇄 제어문자 제거 (스페이스 미만)
    s = "".join(ch for ch in s if ord(ch) >= 32)
    # 연속 공백 정리
    s = " ".join(s.split())
    # 큰따옴표 문자열로 감쌀 것이므로 역슬래시와 큰따옴표만 이스케이프
    s = s.replace("\\", "\\\\").replace('"', '\\"')
    if max_len:
        s = s[:max_len].rstrip()
    return s


def _validate_frontmatter(fm_text):
    """front matter 텍스트가 YAML 파싱 가능한지 검증."""
    try:
        if not fm_text.startswith("---"):
            return False, "front matter does not start with ---"
        end = fm_text.find("---", 3)
        if end < 0:
            return False, "front matter has no closing ---"
        fm_body = fm_text[3:end].strip()
        parsed = yaml.safe_load(fm_body)
        if not isinstance(parsed, dict):
            return False, "front matter is not a dict"
        if not parsed.get("title"):
            return False, "title is missing or empty"
        if not parsed.get("date"):
            return False, "date is missing"
        try:
            from datetime import datetime as _dt
            d_str = str(parsed.get("date"))
            d = _dt.fromisoformat(d_str.replace("Z", "+00:00"))
            now = _dt.now(d.tzinfo) if d.tzinfo else _dt.now()
            if (d - now).total_seconds() > 3600:
                return False, "date is in the future: " + d_str
        except Exception:
            pass
        return True, None
    except Exception as e:
        return False, "yaml.safe_load failed: " + str(e)



def _clean_body(body_md):
    """AI가 생성한 가짜 내부링크 제거"""
    if not body_md:
        return ""
    import re
    body_md = re.sub(r"\n+##\s*(함께|관련|추천)\s*(읽어보기|읽을거리|글|포스트).*", "", body_md, flags=re.DOTALL)
    return body_md.rstrip()


def _insert_coupang(body_md, segment="", fuel_type="", blog_cfg=None):
    """
    쿠팡 파트너스 링크 삽입
    
    Returns:
        tuple[str, str]: (수정된 body_md, 상태) 상태는 "OK", "FAIL", "SKIP" 중 하나
    """
    # blog_cfg 없으면 SKIP (publish()에서 조건 필터링)
    if not blog_cfg:
        return body_md, "SKIP"
    
    try:
        from shared.coupang_car import CoupangCar
        coupang = CoupangCar()
        if not coupang.is_configured():
            return body_md, "SKIP"
        
        coupang_md = coupang.get_car_product_links(segment=segment, fuel_type=fuel_type, count=2)
        if not coupang_md:
            return body_md, "SKIP"
        
        body_md = body_md.rstrip() + coupang_md
        return body_md, "OK"
        
    except ImportError as e:
        logger.error(f"[COUPANG_ERROR] Import failed: {e}")
        return body_md, "FAIL"
    except Exception as e:
        logger.error(f"[COUPANG_ERROR] Insert failed: {e}")
        return body_md, "FAIL"


def _insert_internal_links(body_md, blog_id, slug):
    """
    StapEntityLinker inject — stock-hugo 포함 전체 블로그 적용
    Returns:
        tuple[str, int]: (수정된 body_md, 삽입된 링크 수)
    """
    import sys
    if STAP_ENTITY_LINKER_PATH not in sys.path:
        sys.path.insert(0, STAP_ENTITY_LINKER_PATH)
    try:
        from stap_entity_linker import StapEntityLinker
        linker = StapEntityLinker(db_path=STAP_ENTITY_DB)
        new_body = linker.inject(body_md, current_blog=blog_id)
        injected = new_body.count("](") - body_md.count("](")
        link_count = max(0, injected)
        return new_body, link_count
    except Exception as e:
        logger.warning(f"[EntityLinker] inject 실패 (blog={blog_id}): {e}")
        return body_md, 0


def _extract_first_image(body_md):
    m = re.search(r'!\[.*?\]\((https?://[^)]+)\)', body_md)
    if not m:
        return ""
    url = m.group(1)
    if "tong.visitkorea.or.kr" in url and url.startswith("http://"):
        url = url.replace("http://", "https://", 1)
    return url


def _extract_description(body_md):
    """본문에서 SEO용 description 추출 — DESC 주석 우선"""
    import re as _desc_re
    _m = _desc_re.search(r"<!-- DESC: (.+?) -->", body_md)
    if _m:
        return _m.group(1).strip()[:160]
    # 기존 로직 (아래에서 본문 기반 추출 — DESC 주석 우선, 없으면 본문 기반"""
    import re as _re
    _desc_match = _re.search(r'<!-- DESC: (.+?) -->', body_md)
    if _desc_match:
        return _desc_match.group(1).strip()[:160]
    lines = []
    for line in body_md.split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("#") or line.startswith(">") or line.startswith("!") or line.startswith("---") or line.startswith("<!--") or line.startswith("|") or line.startswith("<"):
            continue
        clean = re.sub(r'\*\*|\[([^\]]+)\]\([^)]*\)', r'\1', line)
        if len(clean) > 20:
            lines.append(clean)
        if len(lines) >= 3:
            break
    if not lines:
        return ""
    # 첫 문장이 아닌 2~3번째 문장에서 핵심 수치 포함 문장 우선
    for line in lines[1:]:
        if any(c.isdigit() for c in line):
            return line[:160]
    # 수치 문장 없으면 첫 문장 축약
    return lines[0][:160]

def _build_frontmatter_congo(title, slug, category, tags, thumbnail_url, description, is_draft=False, blog_id=""):
    date_str = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00")
    fm = "---\n"
    fm += 'title: "' + _sanitize_yaml_value(title) + '"\n'
    fm += "date: " + date_str + "\n"
    fm += f"draft: {'true' if is_draft else 'false'}\n"
    if description:
        fm += 'description: "' + _sanitize_yaml_value(description, max_len=200) + '"\n'
    fm += 'slug: "' + slug + '"\n'
    if category:
        fm += 'categories: ["' + category + '"]\n'
    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        fm += "tags: [" + ", ".join('"' + t + '"' for t in tag_list) + "]\n"
    if thumbnail_url:
        fm += 'image: "' + thumbnail_url + '"\n'
    else:
        if "stock" in blog_id:
            fm += 'image: "https://pub-2f5c7af1c303419a933069212bc25874.r2.dev/common/stock-default-thumbnail.webp"\n'
        else:
            fm += 'image: "https://pub-2f5c7af1c303419a933069212bc25874.r2.dev/common/default-thumbnail.webp"\n'
    fm += "---\n"
    return fm, date_str

def _build_frontmatter_papermod(title, slug, category, tags, thumbnail_url, description, is_draft=False):
    date_str = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00")
    fm = "---\n"
    fm += 'title: "' + _sanitize_yaml_value(title) + '"\n'
    fm += "date: '" + date_str + "'\n"
    fm += "slug: '" + slug + "'\n"
    fm += f"draft: {'true' if is_draft else 'false'}\n"
    if description:
        fm += 'description: "' + _sanitize_yaml_value(description, max_len=200) + '"\n'
    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        fm += "tags: " + str(tag_list) + "\n"
    if category:
        fm += "categories: ['" + category + "']\n"
    if thumbnail_url:
        fm += "cover:\n"
        fm += '  image: "' + thumbnail_url + '"\n'
        fm += '  alt: "' + _sanitize_yaml_value(title) + '"\n'
        fm += "  hidden: false\n"
    fm += "---\n\n"
    return fm, date_str


def _build_frontmatter_blowfish(title, slug, category, tags, thumbnail_url, description, is_draft=False, blog_id=""):
    date_str = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00")
    fm = "---\n"
    fm += 'title: "' + _sanitize_yaml_value(title) + '"\n'
    fm += "slug: '" + slug + "'\n"
    fm += "date: '" + date_str + "'\n"
    fm += f"draft: {'true' if is_draft else 'false'}\n"
    if description:
        fm += 'description: "' + _sanitize_yaml_value(description, max_len=200) + '"\n'
    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        fm += "tags: " + str(tag_list) + "\n"
    if category:
        fm += "categories: ['" + category + "']\n"
    if thumbnail_url:
        if "tong.visitkorea.or.kr" in thumbnail_url and thumbnail_url.startswith("http://"):
            thumbnail_url = thumbnail_url.replace("http://", "https://", 1)
        fm += 'featureimage: "' + thumbnail_url + '"\n'
    else:
        if "stock" in blog_id:
            fm += 'featureimage: "https://pub-2f5c7af1c303419a933069212bc25874.r2.dev/common/stock-default-thumbnail.webp"\n'
        else:
            fm += 'featureimage: "https://pub-2f5c7af1c303419a933069212bc25874.r2.dev/common/default-thumbnail.webp"\n'
    fm += "---\n\n"
    return fm, date_str


def _get_related_posts(blog_id, current_slug, max_count=3):
    """같은 블로그의 최근 발행 글에서 관련 글 추출"""
    try:
        db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "stap_content.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT title, slug FROM articles WHERE blog_id=? AND slug!=? AND status='published' ORDER BY created_at DESC LIMIT ?",
            (blog_id, current_slug, max_count)
        ).fetchall()
        conn.close()
        return [{"title": r["title"], "slug": r["slug"]} for r in rows]
    except Exception:
        return []


def _inject_related_cards_midpoint(body_md, blog_id, slug, title, category):
    """
    관련 글 카드를 마지막 ## 헤딩 바로 앞에 삽입
    마지막 ## 헤딩이 없으면 본문 말미에 삽입
    """
    import re as _re
    cards_html = _inject_related_cards("", blog_id, slug, title, category)
    if not cards_html.strip():
        return body_md
    matches = list(_re.finditer(r"^##\s+[^#\n]", body_md, _re.MULTILINE))
    if len(matches) >= 2:
        insert_pos = matches[-1].start()
        return body_md[:insert_pos] + cards_html.lstrip("\n") + "\n\n" + body_md[insert_pos:]
    else:
        return body_md.rstrip() + cards_html


def _inject_related_cards(body_md, blog_id, slug, title, category):
    """
    후처리: 관련 글 카드 섹션을 본문 말미에 HTML로 삽입
    - 같은 블로그 동일 카테고리 최근 2개 (same-blog, 자기 자신 제외)
    - cross-blog: 제목에서 한글 고유명사(3자 이상)만 추출해 타 블로그 검색 최대 2개
    """
    import sqlite3 as _sq
    import re as _re

    STAP_CONTENT_DB = "/Users/twinssn/Projects/STAP/data/stap_content.db"
    BLOG_DOMAINS = {
        "stock-hugo":    "https://stock.informationhot.kr",
        "dividend-hugo": "https://dividend.techpawz.com",
        "etf-hugo":      "https://etf.techpawz.com",
        "sector-hugo":   "https://sector.techpawz.com",
        "ipo-hugo":      "https://ipo.techpawz.com",
        "finance-hugo":  "https://finance.techpawz.com",
    }
    BLOG_LABELS = {
        "stock-hugo":    "주식분석",
        "dividend-hugo": "배당블로그",
        "etf-hugo":      "ETF블로그",
        "sector-hugo":   "업종분석",
        "ipo-hugo":      "IPO블로그",
        "finance-hugo":  "금융블로그",
    }

    # 동사/형용사/조사 어미 패턴 (cross-blog 키워드 오염 방지)
    _JOSA_END = _re.compile(r"[이가을를은는에서으로과와도만도의]$")
    _VERB_END = _re.compile(r"[한된됩습니다했하며이인한]$")
    _NUMBER_ONLY = _re.compile(r"^\d+$")

    def _extract_keywords(t):
        stop = {
            "분석","비교","추천","전망","가이드","입문","투자","배당","실적",
            "영업","이익","매출","증가","감소","급등","급락","순이익","손실",
            "원가","절감","업종","업황","리스크","판단","결론","현황","정리",
            "방법","이유","원인","효과","전략","수익","금리","예금","적금",
            "영향","기록","개선","감소","증가","비밀","가져온","미친","지속",
        }
        candidates = _re.findall(r"[가-힣]{3,10}", t)
        result = []
        for c in candidates:
            if c in stop:
                continue
            if _JOSA_END.search(c):
                continue
            if _VERB_END.search(c):
                continue
            result.append(c)
        return result[:4]

    cards = []

    try:
        conn = _sq.connect(STAP_CONTENT_DB)
        conn.row_factory = _sq.Row

        # ① 같은 블로그 동일 카테고리 최근 2개 (slug 정확 일치로 자기 자신 제외)
        import os as _os
        BLOG_SITE_PATHS = {
            "stock-hugo":    "/Users/twinssn/Projects/STAP/stock-hugo",
            "dividend-hugo": "/Users/twinssn/Projects/STAP/dividend-hugo",
            "etf-hugo":      "/Users/twinssn/Projects/STAP/etf-hugo",
            "sector-hugo":   "/Users/twinssn/Projects/STAP/sector-hugo",
            "ipo-hugo":      "/Users/twinssn/Projects/STAP/ipo-hugo",
            "finance-hugo":  "/Users/twinssn/Projects/STAP/finance-hugo",
        }
        def _file_exists(bid, sl):
            site = BLOG_SITE_PATHS.get(bid, "")
            if not site:
                return True
            return _os.path.exists(_os.path.join(site, "content", "posts", sl, "index.md"))

        same = conn.execute(
            "SELECT title, slug, category FROM articles "
            "WHERE blog_id=? AND slug!=? AND status='published' "
            "AND category=? "
            "ORDER BY created_at DESC LIMIT 10",
            (blog_id, slug, category)
        ).fetchall()
        for r in same:
            if len(cards) >= 2:
                break
            if not _file_exists(blog_id, r["slug"]):
                continue
            url = "/posts/" + r["slug"] + "/"
            cards.append({
                "title": r["title"], "url": url,
                "label": BLOG_LABELS.get(blog_id, "관련글"),
                "meta": r["category"], "cross": False,
            })

        # 동일 카테고리 2개 미만이면 최근 글로 보충
        if len(cards) < 2:
            existing_urls = {c["url"] for c in cards}
            recent = conn.execute(
                "SELECT title, slug, category FROM articles "
                "WHERE blog_id=? AND slug!=? AND status='published' "
                "ORDER BY created_at DESC LIMIT 20",
                (blog_id, slug)
            ).fetchall()
            for r in recent:
                if len(cards) >= 2:
                    break
                if not _file_exists(blog_id, r["slug"]):
                    continue
                url = "/posts/" + r["slug"] + "/"
                if url not in existing_urls:
                    cards.append({
                        "title": r["title"], "url": url,
                        "label": BLOG_LABELS.get(blog_id, "관련글"),
                        "meta": r["category"], "cross": False,
                    })

        # ② cross-blog: 한글 고유명사(3자 이상)만 추출
        keywords = _extract_keywords(title)

        cross_blogs = [b for b in BLOG_DOMAINS if b != blog_id]
        cross_found = []
        for kw in keywords:
            if len(cross_found) >= 2:
                break
            for cb in cross_blogs:
                if len(cross_found) >= 2:
                    break
                rows = conn.execute(
                    "SELECT title, slug, category, blog_id FROM articles "
                    "WHERE blog_id=? AND status='published' "
                    "AND (title LIKE ? OR tags LIKE ?) "
                    "ORDER BY created_at DESC LIMIT 1",
                    (cb, f"%{kw}%", f"%{kw}%")
                ).fetchall()
                for r in rows:
                    domain = BLOG_DOMAINS.get(r["blog_id"], "")
                    if not domain:
                        continue
                    url = domain + "/posts/" + r["slug"] + "/"
                    if any(c["url"] == url for c in cards + cross_found):
                        continue
                    cross_found.append({
                        "title": r["title"], "url": url,
                        "label": BLOG_LABELS.get(r["blog_id"], "관련블로그"),
                        "meta": r["category"], "cross": True,
                    })
        conn.close()
        cards.extend(cross_found)

    except Exception as e:
        logger.warning(f"[RelatedCards] DB 조회 실패: {e}")
        return body_md

    if not cards:
        return body_md

    # URL 인코딩 (한글 slug 대응)
    from urllib.parse import quote as _quote
    def _safe_url(url):
        if url.startswith("http"):
            parts = url.split("/posts/", 1)
            if len(parts) == 2:
                return parts[0] + "/posts/" + _quote(parts[1], safe="/-_.")
            return url
        return "/posts/" + _quote(url.replace("/posts/", "").strip("/"), safe="/-_.") + "/"

    # HTML 카드 블록 생성
    html = '\n\n<div class="stap-related">\n'
    html += '<h2>📌 관련 글</h2>\n'
    html += '<div class="stap-cards">\n'
    for c in cards:
        badge_cls = "stap-card-badge cross" if c["cross"] else "stap-card-badge"
        target = 'target="_blank" rel="noopener"' if c["cross"] else ""
        safe_url = _safe_url(c["url"])
        html += f'<a class="stap-card" href="{safe_url}" {target}>\n'
        html += f'  <span class="{badge_cls}">{c["label"]}</span>\n'
        html += f'  <div class="stap-card-title">{c["title"]}</div>\n'
        html += f'  <div class="stap-card-meta">{c["meta"]}</div>\n'
        html += '</a>\n'
    html += '</div>\n</div>\n'

    return body_md.rstrip() + html


def _write_hugo_post(blog_cfg, title, body_md, slug, category, tags, thumbnail_url, is_draft=False):
    # ✅ slug 빈값 가드 (2026-05-01 추가) — content/posts/index.md 폭탄 방지
    if not slug or not str(slug).strip():
        try:
            logger.error(f"[PUBLISH] slug가 비어있어 발행 중단: title={title}")
        except Exception:
            pass
        return {"success": False, "error": "empty slug"}

    theme = blog_cfg.get("theme", "PaperMod")
    site_path = blog_cfg.get("site_path", "")
    if not site_path:
        site_path = os.path.join("/Users/twinssn/Projects", blog_cfg.get("repo", ""))
    description = _extract_description(body_md)

    if not thumbnail_url:
         thumbnail_url = _extract_first_image(body_md)
    if not thumbnail_url:
        _blog_id = blog_cfg.get("id", "")
        if "stock" in _blog_id:
         thumbnail_url = "https://pub-2f5c7af1c303419a933069212bc25874.r2.dev/common/stock-default-thumbnail.webp"
        
    if thumbnail_url and thumbnail_url.startswith("http://tong.visitkorea.or.kr"):
        thumbnail_url = thumbnail_url.replace("http://", "https://", 1)

    if theme.lower() == "blowfish":
        fm, date_str = _build_frontmatter_blowfish(title, slug, category, tags, thumbnail_url, description, is_draft=is_draft, blog_id=blog_cfg.get("id", ""))
        post_dir = os.path.join(site_path, "content", "posts", slug)
        os.makedirs(post_dir, exist_ok=True)
        file_path = os.path.join(post_dir, "index.md")
    elif theme.lower() == "congo":
        fm, date_str = _build_frontmatter_congo(title, slug, category, tags, thumbnail_url, description, is_draft=is_draft, blog_id=blog_cfg.get("id", ""))
        post_dir = os.path.join(site_path, "content", "posts", slug)
        os.makedirs(post_dir, exist_ok=True)
        file_path = os.path.join(post_dir, "index.md")
    else:
        fm, date_str = _build_frontmatter_papermod(title, slug, category, tags, thumbnail_url, description, is_draft=is_draft)
        date_prefix = datetime.now().strftime("%Y-%m-%d")
        post_dir = os.path.join(site_path, "content", "posts")
        os.makedirs(post_dir, exist_ok=True)
        file_path = os.path.join(post_dir, date_prefix + "-" + slug + ".md")


    # DESC 주석 제거 (front-matter에 이미 반영됨)
    import re as _pub_re
    body_md = _pub_re.sub(r"<!-- DESC:.*?-->", "", body_md).strip()
    content = fm + body_md

    # ✅ 작성 전 front matter 검증 (2026-05-01 추가)
    _ok, _err = _validate_frontmatter(fm)
    if not _ok:
        try:
            logger.error("[PUBLISH] front matter 검증 실패, 발행 중단: blog=" + str(blog_cfg.get("id","")) + " err=" + str(_err))
        except Exception:
            pass
        return {"success": False, "error": "frontmatter invalid: " + str(_err)}

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    # ✅ 작성 후 디스크 재검증 (2026-05-01 추가) — 인코딩 문제까지 차단
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            _disk = f.read()
        _ok2, _err2 = _validate_frontmatter(_disk)
        if not _ok2:
            try:
                os.remove(file_path)
                if os.path.isdir(post_dir) and not os.listdir(post_dir):
                    os.rmdir(post_dir)
            except Exception:
                pass
            try:
                logger.error("[PUBLISH] 디스크 재검증 실패, 파일 삭제: " + str(_err2))
            except Exception:
                pass
            return {"success": False, "error": "frontmatter invalid on disk: " + str(_err2)}
    except Exception as _e:
        try:
            logger.warning("[PUBLISH] 디스크 재검증 예외(무시): " + str(_e))
        except Exception:
            pass

    expected_url = "https://" + blog_cfg.get("domain", "") + "/posts/" + slug + "/"
    return {"success": True, "url": expected_url, "file_path": file_path}


def deploy_site(site_path, cf_project):
    site = Path(site_path)
    # leaf bundle 방지: content/posts/index.md 존재 시 삭제
    rogue = site / "content" / "posts" / "index.md"
    if rogue.exists():
        rogue.unlink()
        print(f"[guard] Removed rogue index.md from {site}")

    log_path = Path("/Users/twinssn/Projects/5000/logs/deploy.log")
    with open(log_path, "a") as log_f:
        result = subprocess.run(
            ["/opt/homebrew/bin/hugo", "--gc", "--minify"],
            cwd=str(site), stdout=log_f, stderr=log_f
        )
    if result.returncode != 0:
        raise Exception("Hugo build failed: see deploy.log")
    index_file = site / "public" / "index.html"
    if not index_file.exists():
        raise Exception("Hugo build produced empty site: public/index.html not found")
    with open(log_path, "a") as log_f:
        result = subprocess.run(
            ["/opt/homebrew/bin/wrangler", "pages", "deploy", "./public",
             "--project-name=" + cf_project, "--branch=main", "--commit-dirty=true"],
            cwd=str(site), stdout=log_f, stderr=log_f
        )
    if result.returncode != 0:
        raise Exception("Wrangler deploy failed: see deploy.log")
    return True


def publish(blog_id, title, body_md, body_html=None, segment="", fuel_type="", blog_cfg=None,
            category="", tags="", thumbnail_url="",
            data_source="", source_id="", prompt_id="",
            model="", wp_category=None, is_draft=False):

    blog_cfg = get_blog_config(blog_id)

    today_count = get_today_count(blog_id)
    if today_count >= blog_cfg.get("daily_quota", 50):
        return {"success": False, "reason": "daily_quota_exceeded", "count": today_count}

    slug = slugify(title)

    article = {
        "blog_id": blog_id,
        "title": title,
        "slug": slug,
        "body_md": body_md,
        "body_html": body_html or "",
        "thumbnail_url": thumbnail_url,
        "category": category,
        "tags": tags,
        "data_source": data_source,
        "source_id": source_id,
        "prompt_id": prompt_id,
        "model": model,
        "platform": blog_cfg["platform"],
        "status": "pending",
        "published_url": f"pending://{blog_id}/{__import__('datetime').datetime.now().timestamp()}",
        "published_at": "",
    }
    article_id = insert_article(article)

    platform = blog_cfg.get("platform", "hugo")

    if platform == "blogger":
        import os
        from dotenv import load_dotenv as _ldenv
        _ldenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"), override=True)
        from shared.blogger_publisher import publish_to_blogger
        blogger_blog_id = blog_cfg.get("blogger_blog_id", "")
        if not blogger_blog_id:
            blog_id_env = blog_cfg.get("blog_id_env", "")
            blogger_blog_id = os.getenv(blog_id_env, "") if blog_id_env else ""
        if not blogger_blog_id:
            return {"success": False, "error": "blogger blog_id not configured"}
        labels = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
        html_content = body_html or body_md
        # markdown -> HTML 변환 (Blogger는 HTML 필요)
        if not body_html and body_md:
            import markdown
            html_content = markdown.markdown(body_md, extensions=['tables', 'fenced_code'])
        result = publish_to_blogger(blogger_blog_id, title, html_content, labels)
        logger.info(f'[PUBLISH] blog={blog_id} | title="{title}" | coupang=SKIP | internal_links=0 | chars={len(body_md)}')

    elif platform == "wordpress":
        import os
        from dotenv import load_dotenv as _ldenv2
        _ldenv2(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"), override=True)
        from shared.wordpress_publisher import publish_to_wordpress
        wp_url = os.getenv(blog_cfg.get("wp_url_env", ""), "")
        wp_user = os.getenv(blog_cfg.get("wp_user_env", ""), "")
        wp_pass = os.getenv(blog_cfg.get("wp_pass_env", ""), "")
        if not wp_url:
            return {"success": False, "error": "wordpress url not configured"}
        html_content = body_html or body_md
        # markdown -> HTML 변환 (WordPress도 HTML 필요)
        if not body_html and body_md:
            import markdown
            html_content = markdown.markdown(body_md, extensions=['tables', 'fenced_code'])
        result = publish_to_wordpress(wp_url, wp_user, wp_pass, title, html_content, categories=[wp_category] if wp_category else None, featured_image_url=thumbnail_url)
        logger.info(f'[PUBLISH] blog={blog_id} | title="{title}" | coupang=SKIP | internal_links=0 | chars={len(body_md)}')


    else:
        # 서브함수 순서대로 호출
        if body_md:
            body_md = _clean_body(body_md)
        
        coupang_status = "SKIP"
        if data_source == "car_db":
            body_md, coupang_status = _insert_coupang(body_md, segment, fuel_type, blog_cfg)
        
        body_md, link_count = _insert_internal_links(body_md, blog_id, slug)

        body_md = _inject_related_cards_midpoint(body_md, blog_id, slug, title, category)

        # TAP 엔티티 카드 삽입 (travel 6개 블로그)
        if TAP_ENTITY_AVAILABLE and blog_id in TAP_TRAVEL_BLOGS:
            try:
                import re as _re
                _region = ""
                for _tag in (tags or "").split(","):
                    _tag = _tag.strip()
                    for _do in ['서울','부산','대구','인천','광주','대전','울산','세종',
                                '경기','강원','충북','충남','전북','전남','경북','경남','제주']:
                        if _tag.startswith(_do):
                            _region = _do
                            break
                    if _region:
                        break
                if not _region:
                    for _do in ['서울','부산','대구','인천','광주','대전','울산','세종',
                                '경기','강원','충북','충남','전북','전남','경북','경남','제주']:
                        if _do in title:
                            _region = _do
                            break
                body_md, _card_cnt = _tap_inject_cards(body_md, blog_id, _region)
                logger.info(f"[TapEntity] Hugo 카드 {_card_cnt}개 삽입 (region={_region})")
            except Exception as _te:
                logger.warning(f"[TapEntity] Hugo 카드 삽입 실패 (무시): {_te}")

        result = _write_hugo_post(blog_cfg, title, body_md, slug, category, tags, thumbnail_url, is_draft=is_draft)

        # 엔티티 register
        if result.get("success"):
            try:
                import sys as _sys
                if STAP_ENTITY_LINKER_PATH not in _sys.path:
                    _sys.path.insert(0, STAP_ENTITY_LINKER_PATH)
                from stap_entity_linker import StapEntityLinker as _SEL
                _SEL(db_path=STAP_ENTITY_DB).register(blog_id, title, slug, tags=tags)
                logger.info(f"[EntityLinker] registered: {blog_id}/{slug}")
            except Exception as _e:
                logger.warning(f"[EntityLinker] register 실패: {_e}")

            # TAP 엔티티 DB 등록
            if TAP_ENTITY_AVAILABLE and blog_id in TAP_TRAVEL_BLOGS:
                try:
                    _pub_url = result.get("url", "")
                    _tap_register_post(
                        blog_id=blog_id,
                        title=title,
                        url=_pub_url,
                        slug=slug,
                        category=category,
                        region=_region if '_region' in dir() else "",
                    )
                except Exception as _te:
                    logger.warning(f"[TapEntity] register 실패 (무시): {_te}")

        # 로그 추가
        logger.info(f'[PUBLISH] blog={blog_id} | title="{title}" | coupang={coupang_status} | internal_links={link_count} | chars={len(body_md)}')

    if result.get("success"):
        update_published(article_id, result.get("url", ""))
        cf_project = blog_cfg.get("cf_project", "")
        site_path = blog_cfg.get("site_path", "")
        if cf_project and site_path:
            try:
                deploy_site(site_path, cf_project)
                result["deployed"] = True
            except Exception as e:
                result["deployed"] = False
                result["deploy_error"] = str(e)
                from shared.telegram_notifier import send_error as _tg_err
                _tg_err(blog_id, "deploy", "Hugo빌드/Wrangler배포 실패: " + str(e)[:200])

    result["article_id"] = article_id
    return result

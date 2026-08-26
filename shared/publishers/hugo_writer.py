import json
import logging
import os
import re
import subprocess
import uuid
from datetime import datetime
from pathlib import Path

from shared.paths import FIVEK_ROOT, HUGO_PATH
logger = logging.getLogger(__name__)


def _detect_locale(text):
    """콘텐츠에 한글(CJK)이 포함됐는지 감지해 locale 결정.

    한글 음절·가나·한자 등 CJK 문자가 1개라도 있으면 'ko', 없으면 'en'.
    _write_hugo_post의 3개 C04 훅에서 locale 자동 결정에 사용.
    (기존 locale="ko" 고정 → 영문 C04 패턴 미차단 문제 해소)
    """
    if not text:
        return "en"
    for c in text:
        o = ord(c)
        if 0xAC00 <= o <= 0xD7AF:  # 한글 음절
            return "ko"
        if 0x4E00 <= o <= 0x9FFF:  # 한자/중국어
            return "ko"
        if 0x3040 <= o <= 0x30FF:  # 일본어 가나
            return "ko"
    return "en"


def _fix_repeated_image_urls(body_md):
    """Detect and fix image URLs with token repetition patterns (LLM stutter).

    LLMs sometimes repeat trailing tokens in image URLs (e.g.,
    'gLozv0gLozv0gLozv0gLozv0...'). This function detects such repetition
    and strips all repeating content from the URL.

    Detection: substring of length 4+ repeating 5+ times consecutively.
    """
    if not body_md:
        return body_md

    def _has_repeated_pattern(url, min_repeat_len=4, min_repeats=5):
        url_str = url.rstrip("/")
        url_len = len(url_str)
        for sub_len in range(min_repeat_len, min(50, url_len // min_repeats + 1)):
            for start in range(url_len - sub_len * min_repeats + 1):
                sub = url_str[start:start + sub_len]
                count = 0
                pos = start
                while pos + sub_len <= url_len and url_str[pos:pos + sub_len] == sub:
                    count += 1
                    pos += sub_len
                if count >= min_repeats:
                    return sub, count, start
        return None

    def _fix_url(match):
        alt, url = match.group(1), match.group(2)
        result = _has_repeated_pattern(url)
        if result:
            sub, count, pos = result
            clean_url = url[:pos]
            logger.warning(
                f"[URL-REPEAT] Image URL has repeated pattern '{sub}' x{count} "
                f"({len(url)} chars → {len(clean_url)} chars): "
                f"{url[:80]}... → {clean_url[:80]}..."
            )
            return f"![{alt}]({clean_url})"
        return match.group(0)

    return re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", _fix_url, body_md)


def _sanitize_yaml_value(s, max_len=None):
    """Sanitize a string value for YAML frontmatter output.

    Returns a *pre-quoted* YAML string value (with surrounding quotes).
    Callers must NOT add their own quotes.

    Strategy:
    - If value has no single quotes → wrap in single quotes (no escape processing)
    - If value has single quotes → wrap in double quotes with \\ and \" escaping
    - Strip trailing/leading backslash artifacts that could break YAML quoting
    """
    if s is None:
        return "''"
    s = str(s)
    if max_len:
        s = s[:max_len]
    # Strip trailing backslash artifacts (up to 3 levels)
    for _ in range(3):
        if not s:
            break
        if s.endswith('\\') and not s.endswith('\\\\'):
            s = s[:-1]
        else:
            break
    # Strip leading backslash artifacts (up to 3 levels)
    for _ in range(3):
        if not s:
            break
        if s.startswith('\\') and not s.startswith('\\\\'):
            s = s[1:]
        else:
            break
    # Use single-quoted YAML when safe (no escape processing by YAML parser)
    if "'" in s:
        # Fall back to double-quoted with safe escaping
        escaped = s.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    else:
        return f"'{s}'"


def _build_frontmatter_congo(title, slug, category, tags, thumbnail_url, description, is_draft=False, blog_id=""):
    date_str = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00")
    # Convert inline markdown in frontmatter fields to HTML for proper rendering
    title = _convert_inline_md_to_html(title)
    description = _convert_inline_md_to_html(description) if description else ""
    category = _convert_inline_md_to_html(category) if category else ""
    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        tag_list = [_convert_inline_md_to_html(t) for t in tag_list]
    else:
        tag_list = []
    
    fm = "---\n"
    # _sanitize_yaml_value() returns pre-quoted values, callers must NOT add quotes
    fm += 'title: ' + _sanitize_yaml_value(title) + '\n'
    fm += "date: " + date_str + "\n"
    fm += f"draft: {'true' if is_draft else 'false'}\n"
    if description:
        fm += 'description: ' + _sanitize_yaml_value(description, max_len=200) + '\n'
    fm += 'slug: ' + _sanitize_yaml_value(slug) + '\n'
    if category:
        fm += 'categories:\n  - ' + category + '\n'
    if tag_list:
        fm += "tags: [" + ", ".join(t.strip("'\"") for t in (_sanitize_yaml_value(t) for t in tag_list)) + "]\n"
    if thumbnail_url:
        fm += 'image: ' + _sanitize_yaml_value(thumbnail_url) + '\n'
        fm += 'featureimage: ' + _sanitize_yaml_value(thumbnail_url) + '\n'
    elif "stock" in blog_id:
        _url = "https://pub-2f5c7af1c303419a933069212bc25874.r2.dev/common/stock-default-thumbnail.webp"
        fm += 'image: ' + _sanitize_yaml_value(_url) + '\n'
        fm += 'featureimage: ' + _sanitize_yaml_value(_url) + '\n'
    else:
        _url = "https://pub-2f5c7af1c303419a933069212bc25874.r2.dev/common/default-thumbnail.webp"
        fm += 'image: ' + _sanitize_yaml_value(_url) + '\n'
        fm += 'featureimage: ' + _sanitize_yaml_value(_url) + '\n'
    # W5 R17: featureimage(R2 URL) 존재 시 twitter_card 필수 (없으면 deploy 게이트 차단)
    fm += 'twitter_card: summary_large_image\n'
    fm += "---\n"
    return fm, date_str


def _build_frontmatter_papermod(title, slug, category, tags, thumbnail_url, description, is_draft=False):
    date_str = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00")
    # Convert inline markdown in frontmatter fields to HTML for proper rendering
    title = _convert_inline_md_to_html(title)
    description = _convert_inline_md_to_html(description) if description else ""
    category = _convert_inline_md_to_html(category) if category else ""
    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        tag_list = [_convert_inline_md_to_html(t) for t in tag_list]
    else:
        tag_list = []
    
    if thumbnail_url and not thumbnail_url.startswith(("http://", "https://")):
        thumbnail_url = "https://img.informationhot.kr/" + thumbnail_url.lstrip("/")
    
    fm = "---\n"
    # _sanitize_yaml_value() returns pre-quoted values, callers must NOT add quotes
    fm += 'title: ' + _sanitize_yaml_value(title) + '\n'
    fm += "date: '" + date_str + "'\n"
    fm += 'slug: ' + _sanitize_yaml_value(slug) + '\n'
    fm += f"draft: {'true' if is_draft else 'false'}\n"
    if description:
        fm += 'description: ' + _sanitize_yaml_value(description, max_len=200) + '\n'
    if tag_list:
        fm += "tags: [" + ", ".join(t.strip("'\"") for t in (_sanitize_yaml_value(t) for t in tag_list)) + "]\n"
    if category:
        fm += "categories:\n  - " + category + "\n"
    if thumbnail_url:
        fm += 'featureimage: ' + _sanitize_yaml_value(thumbnail_url) + '\n'
    fm += 'twitter_card: summary_large_image\n'
    fm += "---\n\n"
    return fm, date_str


def _build_frontmatter_blowfish(title, slug, category, tags, thumbnail_url, description, is_draft=False, blog_id=""):
    date_str = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00")
    # Convert inline markdown in frontmatter fields to HTML for proper rendering
    title = _convert_inline_md_to_html(title)
    description = _convert_inline_md_to_html(description) if description else ""
    category = _convert_inline_md_to_html(category) if category else ""
    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        tag_list = [_convert_inline_md_to_html(t) for t in tag_list]
    else:
        tag_list = []
    
    if thumbnail_url and not thumbnail_url.startswith(("http://", "https://")):
        thumbnail_url = "https://img.informationhot.kr/" + thumbnail_url.lstrip("/")
    
    fm = "---\n"
    # _sanitize_yaml_value() returns pre-quoted values, callers must NOT add quotes
    fm += 'title: ' + _sanitize_yaml_value(title) + '\n'
    fm += "date: " + date_str + "\n"
    fm += "draft: " + str(is_draft).lower() + "\n"
    if description:
        fm += 'description: ' + _sanitize_yaml_value(description, max_len=200) + '\n'
    fm += 'slug: ' + _sanitize_yaml_value(slug) + '\n'
    if category:
        fm += 'categories:\n  - ' + category + '\n'
    if tag_list:
        fm += "tags: [" + ", ".join(t.strip("'\"") for t in (_sanitize_yaml_value(t) for t in tag_list)) + "]\n"
    if thumbnail_url:
        fm += 'featureimage: ' + _sanitize_yaml_value(thumbnail_url) + '\n'
    elif "stock" in blog_id:
        _url = "https://pub-2f5c7af1c303419a933069212bc25874.r2.dev/common/stock-default-thumbnail.webp"
        fm += 'featureimage: ' + _sanitize_yaml_value(_url) + '\n'
    else:
        _url = "https://pub-2f5c7af1c303419a933069212bc25874.r2.dev/common/default-thumbnail.webp"
        fm += 'featureimage: ' + _sanitize_yaml_value(_url) + '\n'
    fm += 'twitter_card: summary_large_image\n'
    fm += "---\n"
    return fm, date_str


def _download_image_bytes(url: str) -> tuple[bytes, str] | None:
    """Download image from URL, return (data, content_type) or None."""
    try:
        import httpx
        resp = httpx.get(url, timeout=30, follow_redirects=True)
        resp.raise_for_status()
        ctype = resp.headers.get("content-type", "image/webp")
        return resp.content, ctype
    except Exception as e:
        logger.warning(f"[IMAGE-DOWNLOAD] 다운로드 실패 ({url[:60]}...): {e}")
        return None


def _convert_to_webp(data: bytes, quality: int = 75) -> bytes | None:
    """Convert image bytes to WebP format using Pillow. Returns WebP bytes or None."""
    try:
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(data))
        buf = io.BytesIO()
        img.save(buf, format="WEBP", quality=quality, method=6)
        return buf.getvalue()
    except Exception as e:
        logger.warning(f"[IMAGE-WEBP] WebP 변환 실패: {e}")
        return None


def _save_image_static(data: bytes, site_path: str, url_hash: str, ext: str = ".webp") -> str | None:
    """Save image bytes to Hugo static/img/ directory, return relative URL."""
    static_dir = os.path.join(site_path, "static", "img")
    try:
        os.makedirs(static_dir, exist_ok=True)
    except OSError:
        return None
    filepath = os.path.join(static_dir, f"{url_hash}{ext}")
    with open(filepath, "wb") as f:
        f.write(data)
    return f"/img/{url_hash}{ext}"


def _upload_image_to_r2(url: str, site_path: str = "") -> str | None:
    """Download image from long URL, upload to R2 with short hash name, return short URL.
    
    Primary: Upload to R2 → return R2 public URL.
    Fallback: Save to Hugo static/img/ → return relative URL.
    Returns None if both fail.
    """
    import hashlib
    from shared.r2_uploader import file_exists, _public_url, upload_bytes

    url_hash = hashlib.md5(url.encode()).hexdigest()[:16]
    r2_key = f"curation-images/thumbnails/{url_hash}.webp"

    # Skip if already in R2
    if file_exists(r2_key):
        return _public_url("hotissue-images", r2_key)

    # Download image data
    result = _download_image_bytes(url)
    if result is None:
        return None
    data, _ = result

    webp_data = _convert_to_webp(data, quality=75)
    if webp_data is None:
        webp_data = data

    try:
        r2_url = upload_bytes(webp_data, r2_key, content_type="image/webp")
        if r2_url:
            return r2_url
    except Exception as e:
        logger.warning(f"[IMAGE-UPLOAD] R2 업로드 실패 ({url[:60]}...): {e}")

    # Fallback: Save to Hugo static/img/
    if site_path:
        local_url = _save_image_static(webp_data, site_path, url_hash, ext=".webp")
        if local_url:
            logger.info(f"[IMAGE-UPLOAD] 로컬 static 저장: {local_url}")
            return local_url

    return None


def _clean_body(body_md, site_path=""):
    """Clean body markdown — AI 가짜 내부링크, 빈 템플릿, 과도한 개행, 부적절한 H2 헤딩 제거"""
    if not body_md:
        return body_md
    # ── URL 토큰 반복(repetition) 버그 수정: LLM이 생성한 비정상 URL 정리 ──
    body_md = _fix_repeated_image_urls(body_md)
    body_md = re.sub(
        r"\n+##\s*(함께|관련|추천|더)\s*(읽어보기|읽을거리|글|포스트|게시물|기사)[^\n]*(\n(?!##|$)[^\n]*)*",
        lambda m: m.group() if "{{<" in m.group() else "",
        body_md,
    )
    body_md = re.sub(r"\{\{[\s]*\}\}", "", body_md)
    body_md = re.sub(
        r"https?://[^/\s]*sspark\.genspark\.ai[^\s)]*",
        "https://pub-2f5c7af1c303419a933069212bc25874.r2.dev/placeholder.webp",
        body_md
    )

    # ── 부적절한 H2 헤딩 검증/수정 ──
    _ALLOWED_H2_PATTERNS = [
        r"고를 때 확인할 포인트",
        r"한눈에 보는 비교표",
        r"[0-9]+위:",
        r"자주 묻는 질문",
        r"상황별 추천 정리",
        r"추천",
        r"^비교$",
        r"^장단점$",
        r"^구매 가이드$",
        # RAP(청약/임대/토지/상가) 섹션 허용
        r"^[0-9]+\.\s",            # "1. ", "2. " 번호형 섹션
        r"입주 자격", r"신청\s*절차", r"신청\s*방법", r"필요\s*서류",
        r"자격\s*요건", r"당첨", r"주의사항", r"핵심\s*요약",
        r"공고", r"활용\s*팁", r"입찰", r"계약", r"함께 읽으면 좋은 글",
        # travel/정보전달형 섹션 허용 (정보글 H2: 개요/일정/프로그램/교통/주차/준비/마무리/주변)
        r"개요", r"일정", r"프로그램", r"체험", r"교통", r"주차",
        r"준비\s*사항", r"참고", r"마무리", r"마치며", r"주변",
        r"찾아가는\s*길", r"입장료", r"운영\s*시간", r"이용\s*안내",
        r"한눈에\s*보기", r"한눈에\s*비교", r"비교표", r"정보\s*한눈",
        # travel 정보형 H2 추가 (상세/예약/요금/규칙/소개/정리/방법)
        r"상세\s*정보", r"상세\s*안내", r"소개", r"정리", r"안내",
        r"예약", r"요금", r"가격", r"이용\s*시간", r"이용\s*규칙", r"규칙",
        r"방법", r"정보\s*정리", r"한눈에", r"알아보기", r"확인",
        # 문화유산/여행 H2 (역사적 배경/조형/특징/관람/부재/시대/지정/위치)
        r"역사적\s*배경", r"조형", r"특징", r"관람\s*포인트", r"관람\s*정보",
        r"부재", r"시대", r"지정", r"위치", r"입지", r"배경",
        r"구성", r"구조", r"양식", r"해설", r"가치", r"의미",
        # ── 영어 여행 콘텐츠 H2 패턴 (ETAP 등) ──
        r"^[Tt]op\s+.+[Ee]xcursions",     # "Top Shore Excursions in ..."
        r"^[Bb]est\s+.+[Tt]ours",         # "Best Half-Day Port Tours"
        r"^[Ff]ull-[Dd]ay\s+.+",          # "Full-Day Excursions Worth the Splurge"
        r"^[Tt]ips\s+for\s+",             # "Tips for Cruise Passengers in ..."
        r"^[Bb]udget\s+.+[Tt]rips",       # "Budget Day Trips" 또는 유사
        r"^[Bb]est\s+[Bb]udget\s+.+[Tt]rips",  # "Best Budget Day Trips"
        # ── airlines-hugo 동적 H2 ({name} + 항공사명) ──
        r"^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+at\s+a\s+Glance",                       # "{name} at a Glance"
        r"^Where\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+[Ff]lies:\s+[Rr]oute\s+[Nn]etwork",  # "Where {name} Flies: Route Network"
        r"^[Cc]urrent\s+[Pp]rices\s+[Oo]n\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+[Ff]lights",  # "Current Prices on {name} Flights"
        r"^[Bb]est\s+[Mm]onth\s+[Tt]o\s+[Ff]ly\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*",   # "Best Month to Fly {name}"
        r"^[Mm]arket\s+[Pp]rices:\s+[Ww]hat\s+[Yy]ou'?ll\s+[Pp]ay\s+[Oo]n\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+[Rr]outes",  # "Market Prices: ... on {name} Routes"
        r"^[Tt]rending\s+[Rr]outes\s+[Oo]n\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*",        # "Trending Routes on {name}"
        r"^[Ww]hat\s+[Tt]o\s+[Ee]xpect\s+[Ff]lying\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*", # "What to Expect Flying {name}"
        r"^[Mm]id-[Rr]ange\s+.+",         # "Mid-Range Excursions Worth the Upgrade"
        r"^[Pp]remium\s+.+[Ee]xp",        # "Premium Full-Day Experiences"
        r"^[Pp]lanning\s+Your\s+.+",      # "Planning Your Day Trip"
        r"^[Dd]ay\s+[Tt]rips?\s+[Ff]rom", # "Day Trips From ..."
        r"^[Ee]scaping\s+.+",             # "Escaping ..."
        r"^[Ii]nner\s+[Cc]ities?",        # "Inner Cities"
        r"^[Cc]ity\s+[Tt]ours?",          # "City Tours"
        r"^[Ff]light\s+[Gg]uide",         # "Flight Guide"
        r"^[Aa]irport\s+[Gg]uide",        # "Airport Guide"
        r"^[Ee][Ss][Ii][Mm]\s+[Gg]uide",    # "eSIM Guide"
        r"^[Vv]isa\s+[Gg]uide",           # "Visa Guide"
        r"^[Tt]rain\s+[Gg]uide",          # "Train Guide"
        r"^[Bb]us\s+[Gg]uide",            # "Bus Guide"
        r"^[Dd]ining\s+[Gg]uide",         # "Dining Guide"
        r"^[Cc]ruise\s+[Gg]uide",         # "Cruise Guide"
        r"^[Mm]ichelin\s+[Gg]uide",       # "Michelin Guide"
        r"^[Tt]our\s+[Gg]uide",           # "Tour Guide"
        r"^[Ss]ightseeing",               # "Sightseeing"
        r"^[Aa]ctivities",                # "Activities"
        r"^[Ee]xcursions?",               # "Excursions"
        r"^[Tt]ours?",                    # "Tours"
        r"^[Bb]est\s+.+[Ee]xcursions",    # "Best Shore Excursions in ..."
        # ── nature 파이프라인 H2 ──
        r"^[Tt]op\s+[Nn]ature\s+[Aa]nd\s+[Ww]ildlife\s+[Tt]ours", # "Top Nature and Wildlife Tours in {city}"
        r"^[Hh]iking\s+[Aa]nd\s+[Oo]utdoor\s+[Aa]dventures",       # "Hiking and Outdoor Adventures"
        r"^[Bb]udget-[Ff]riendly\s+[Nn]ature",                     # "Budget-Friendly Nature Experiences"
        r"^[Pp]lanning\s+[Yy]our\s+[Nn]ature\s+[Tt]rip",           # "Planning Your Nature Trip"
        # ── phototour 파이프라인 H2 ──
        r"^[Tt]op\s+[Pp]hotography\s+[Tt]ours",                  # "Top Photography Tours in {city}"
        r"^[Bb]est\s+[Pp]hoto\s+[Ww]alks\s+[Aa]nd\s+[Ww]orkshops", # "Best Photo Walks and Workshops"
        r"^[Ss]unrise\s+[Aa]nd\s+[Gg]olden\s+[Hh]our\s+[Tt]ours", # "Sunrise and Golden Hour Tours"
        r"^[Cc]amera\s+[Gg]ear\s+[Aa]nd\s+[Pp]hotography\s+[Tt]ips", # "Camera Gear and Photography Tips for {city}"
        # ── airlines 파이프라인 H2 ──
        r"^[Qq]uick\s+[Ff]acts",                                 # "Quick Facts"
        r"^[Rr]oute\s+[Nn]etwork",                               # "Route Network"
        r"^[Pp]rices\s+[Aa]nd\s+[Ff]ares",                      # "Prices and Fares"
        r"^[Cc]abin\s+[Ee]xperience",                            # "Cabin Experience"
        r"^[Bb]ooking\s+[Tt]ips",                                # "Booking Tips"
        r"^[Vv]erdict\s*:\s*[Ii]s\s+.+[Ww]orth\s+[Ii]t",        # "Verdict: Is {name} Worth It?"
        r"^[Pp]ractical\s+[Cc]hecklist",                         # "Practical Checklist"
        r"^[Cc]losing\s+[Vv]erdict",                             # "Closing verdict"
        # ── airports 파이프라인 H2 ──
        r"^[Qq]uick\s+[Ff]acts",                                 # "Quick Facts"
        r"^[A-Za-z\s]+\s*\([A-Z]{3}\)\s*[Oo]verview",           # "{name} (IATA) Overview"
        r"^[Aa]irlines\s+[Oo]perating\s+at",                     # "Airlines Operating at {iata}"
        r"^[Dd]irect\s+[Dd]estinations\s+[Ff]rom",              # "Direct Destinations from {iata}"
        r"^[Gg]etting\s+[Tt]o\s+[Aa]nd\s+[Ff]rom\s+[Tt]he\s+[Aa]irport", # "Getting To and From the Airport"
        r"^[Pp]ractical\s+[Tt]ips\s+[Ff]or\s+[Tt]ravelers",     # "Practical Tips for Travelers"
        r"^[Cc]losing\s*",                                        # "Closing"
        # ── esim 파이프라인 H2 ──
        r"^[Ww]hy\s+[Gg]et\s+[Aa]n\s+[Ee][Ss][Ii][Mm]\s+[Ff]or", # "Why Get an eSIM for {country}"
        r"^[Aa]vailable\s+[Pp]lans\s+[Cc]ompared",              # "Available Plans Compared"
        r"^[Bb]est\s+[Vv]alue\s*:\s*[Ww]hich\s+[Pp]lan\s+[Ss]aves\s+[Yy]ou\s+[Tt]he\s+[Mm]ost", # "Best Value: Which Plan Saves You the Most"
        r"^[Hh]ow\s+[Tt]o\s+[Ii]nstall\s+[Yy]our\s+[Ee][Ss][Ii][Mm]\s+[Bb]efore", # "How to Install Your eSIM Before Traveling"
        r"^[Ee][Ss][Ii][Mm]\s+[Vv]s\s+[Pp]hysical\s+[Ss][Ii][Mm]\s+[Vv]s\s+[Rr]oaming",  # "eSIM vs Physical SIM vs Roaming" (SIM 대소문자 모두 허용)
        r"^[Tt]ips\s+[Ff]or\s+[Ss]taying\s+[Cc]onnected\s+[Ii]n", # "Tips for Staying Connected in {country}"
        # ── flights 파이프라인 H2 ──
        r"^[Cc]urrent\s+[Ff]light\s+[Pp]rices",                 # "Current Flight Prices: {o_city} to {d_city}"
        r"^[Bb]est\s+[Tt]ime\s+[Tt]o\s+[Bb]ook\s+[Ff]lights\s+[Tt]o", # "Best Time to Book Flights to {d_city}"
        r"^[Dd]irect\s+[Vv]s\.?\s*[Cc]onnecting\s+[Ff]lights",  # "Direct vs. Connecting Flights"
        r"^[Ww]hich\s+[Aa]irlines\s+[Ff]ly\s+[Tt]his\s+[Rr]oute", # "Which Airlines Fly This Route?"
        r"^[Mm]oney-[Ss]aving\s+[Tt]ips\s+[Ff]or",              # "Money-Saving Tips for {o_city} to {d_city} Flights"
        r"^[Ww]hat\s+[Tt]o\s+[Ee]xpect\s+[Ww]hen\s+[Yy]ou\s+[Aa]rrive\s+[Ii]n", # "What to Expect When You Arrive in {d_city}"
        # ── michelin 파이프라인 H2 ──
        r"^[Mm]ichelin\s+[Dd]ining\s+[Ii]n\s+.+[:\s]",   # "Michelin Dining in {city}: An Overview"
        r"^[Tt]hree-[Ss]tar\s+[Aa]nd\s+[Tt]wo-[Ss]tar\s+[Ee]xcellence", # "Three-Star and Two-Star Excellence"
        r"^[Oo]ne-[Ss]tar\s+[Gg]ems",                           # "One-Star Gems"
        r"^[Bb]ib\s+[Gg]ourmand\s*:\s*[Bb]est\s+[Vv]alue\s+[Ff]ine\s+[Dd]ining", # "Bib Gourmand: Best Value Fine Dining"
        r"^[Cc]uisine\s+[Ss]tyles\s+[Yy]ou\s+[Ww]ill\s+[Ff]ind\s+[Ii]n", # "Cuisine Styles You Will Find in {city}"
        r"^[Pp]rice\s+[Rr]anges\s+[Aa]nd\s+[Ww]hat\s+[Tt]o\s+[Ee]xpect", # "Price Ranges and What to Expect"
        r"^[Hh]ow\s+[Tt]o\s+[Bb]ook\s+[Aa]nd\s+[Tt]ips\s+[Ff]or\s+[Dd]ining", # "How to Book and Tips for Dining"
        # ── visa 파이프라인 H2 ──
        r"^[^\n]+\s+[Vv]isa\s+[Pp]olicy\s+[Oo]verview",                   # "{passport} Visa Policy Overview" (영문 multi-word + 그리스어·한글·키릴·아랍어 등 비라틴 여권명 포함)
        r"^[Vv]isa-[Ff]ree\s+[Aa]nd\s+[Vv]isa-[Oo]n-[Aa]rrival\s+[Aa]ccess", # "Visa-Free and Visa-on-Arrival Access"
        r"^[Ee]-[Vv]isa\s+[Aa]nd\s+[Ee][Tt][Aa]\s+[Oo]ptions", # "e-Visa and ETA Options"
        r"^[Cc]ountries\s+[Tt]hat\s+[Rr]equire\s+[Aa]\s+[Vv]isa", # "Countries That Require a Visa"
        r"^[Ee]ntry\s+[Rr]equirements\s+[Aa]nd\s+[Pp]ractical\s+[Tt]ips", # "Entry Requirements and Practical Tips"
        r"^[^\n]+\s+[Pp]assport\s*:\s*[Tt]ravel\s+[Ff]reedom\s+[Oo]verview", # "{passport} Passport: Travel Freedom Overview" (비라틴 여권명 포함)
        r"^[Vv]isa-[Ff]ree\s+[Dd]estinations",                  # "Visa-Free Destinations"
        r"^[Vv]isa\s+[Oo]n\s+[Aa]rrival\s+[Cc]ountries",        # "Visa on Arrival Countries"
        r"^[Ee]-[Vv]isa\s+[Aa]nd\s+[Ee][Tt][Aa]\s+[Dd]estinations", # "e-Visa and ETA Destinations"
        r"^[Cc]ountries\s+[Rr]equiring\s+[Aa]\s+[Tt]raditional\s+[Vv]isa", # "Countries Requiring a Traditional Visa"
        r"^[Tt]ips\s+[Ff]or\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+[Pp]assport\s+[Hh]olders", # "Tips for {passport} Passport Holders"
        # ── dining 파이프라인 H2 ──
        r"^[Tt]he\s+[Dd]ining\s+[Ss]cene\s+[Ii]n\s+[^#]+",   # "The Dining Scene in {city}"
        r"^[Ff]ine\s+[Dd]ining\s+[Aa]t\s+[Ii]ts\s+[Bb]est\s*:\s*[Mm]ulti-[Ss]tar\s+[Rr]estaurants", # "Fine Dining at Its Best: Multi-Star Restaurants"
        r"^[Oo]ne-[Ss]tar\s+[Rr]estaurants\s+[Ww]orth\s+[Aa]\s+[Dd]etour", # "One-Star Restaurants Worth a Detour"
        r"^[Bb]ib\s+[Gg]ourmand\s*:\s*[Gg]reat\s+[Ff]ood\s+[Ww]ithout\s+[Tt]he\s+[Ss]plurge", # "Bib Gourmand: Great Food Without the Splurge"
        r"^[Gg]reen\s+[Ss]tar\s*:\s*[Ss]ustainable\s+[Dd]ining\s+[Ii]n\s+[^#]+", # "Green Star: Sustainable Dining in {city}"
        r"^[Cc]uisine\s+[Ss]tyles\s+[Aa]nd\s+[Ww]hat\s+[^#]+\s+[Dd]oes\s+[Bb]est", # "Cuisine Styles and What {city} Does Best"
        r"^[Pp]rice\s+[Gg]uide\s*:\s*[Ww]hat\s+[Tt]o\s+[Bb]udget\s+[Ff]or\s+[Mm]ichelin\s+[Dd]ining", # "Price Guide: What to Budget for Michelin Dining"
        r"^[Bb]ooking\s+[Tt]ips\s+[Aa]nd\s+[Ww]hat\s+[Tt]o\s+[Kk]now\s+[Bb]efore\s+[Yy]ou\s+[Gg]o", # "Booking Tips and What to Know Before You Go"
        # ── michelin 신규 strict 4-H2 구조 (michelin_writer.py 필수 H2, 2026-08-23 추가) ──
        r"^At\s+a\s+Glance$",   # "At a Glance" 요약 테이블
        r"^Where\s+to\s+Eat$",  # "Where to Eat" 식당별 H3 상세
        r"^Compare$",           # "Compare" 비교 테이블
        r"^FAQ$",               # "FAQ"
        # ── nomad 파이프라인 H2 (nomad_writer.py 필수 7종 중 미매칭 4종, 2026-08-23 추가) ──
        r"^Internet\s+[Ss][Ii][Mm]\s+[Cc]ards\s+[Aa]nd\s+[Cc]onnectivity$",  # "Internet SIM Cards and Connectivity"
        r"^Cost\s+[Oo]f\s+[Ll]iving\s+[Ff]or\s+[Nn]omads\s+[Ii]n",          # "Cost of Living for Nomads in {city}"
        r"^Visa\s+[Aa]nd\s+[Ss]tay\s+[Oo]ptions$",                          # "Visa and Stay Options"
        r"^Neighborhoods\s+[Aa]nd\s+[Ww]here\s+[Tt]o\s+[Ss]tay$",           # "Neighborhoods and Where to Stay"
        # ── foodtour 파이프라인 H2 ──
        r"^[Ww]hy\s+.+\s+is\s+a\s+[Ff]ood\s+[Ll]over'?s?\s+[Pp]aradise",  # "Why {city} is a Food Lover's Paradise"
        r"^[Bb]est\s+[Ss]treet\s+[Ff]ood\s+[Tt]ours",                       # "Best Street Food Tours"
        r"^[Hh]ands-[Oo]n\s+[Cc]ooking\s+[Cc]lasses",                        # "Hands-On Cooking Classes"
        r"^[Ff]ine\s+[Dd]ining\s+[Ee]xperiences",                            # "Fine Dining Experiences"
        r"^[Bb]est\s+[Dd]eals\s+on\s+[Ff]ood\s+[Tt]ours",                   # "Best Deals on Food Tours"
        r"^[Tt]ips\s+for\s+[Ff]ood\s+[Tt]ours\s+in",                        # "Tips for Food Tours in {city}"
        r"^[Tt]he\s+[Ff]ood\s+[Ss]cene\s+in",                                # "The Food Scene in {city}"
        r"^[Ww]here\s+to\s+[Ee]at\s+in",                                     # "Where to Eat in {city}"
        # ── curation 파이프라인 H2 (상품 비교) ──
        r"^상품별 상세 비교$",                   # "상품별 상세 비교" (curation _normalize_product_blocks 강제 H2)
        r"^구매 전 체크리스트$",                 # "구매 전 체크리스트" (curation writer.py 시스템 프롬프트 필수 H2, 2026-08-22 추가)
        # ── rap 파이프라인 H2 (부동산) ──
        # 근거: 발행 표본 2413개 H2 중 미등록 강등 193종 실측 (2026-08-23, /tmp/rap_phase0_inventory.md)
        # ponytail: 부동산 도메인 명사 허용 방식이라 서술형 소제목 일부 통과 가능 — 재발 시 형태 제한으로 조임
        r"^요약",
        r"체크리스트",                           # 매수 전/절세 체크리스트 등
        r"지역 특성",                             # 지역 특성 분석 / 및 인프라 환경
        r"거래",                                  # 거래 분석/내역/현황/사례/동향, 단지 거래
        r"단지",                                  # 단지별/단지 상세/기타 단지
        r"시세", r"실거래가?", r"매매가", r"전세가", r"전세가율",
        r"시장", r"추정", r"환산",                # 시장 동향, 전세 시세 추정, 월세 환산
        r"프리미엄", r"비브랜드",                 # 브랜드 프리미엄 분석 (rap5)
        r"분양", r"입주",                         # 분양 및 입주 현황 (rap5)
        r"세금|절세|취득세|양도세|양도소득세|재산세|보유세",  # rap3 세금 계열
        r"시뮬레이션",                            # 세금/취득세 시뮬레이션
        r"^결론",                                 # 실측 1건 (rap)
        r"팁",                                    # 실전 팁 / 절세 팁
        r"비교$",                                 # "~와 비교" 꼬리
        r"동향",                                  # "~동향" 꼬리 (청주 전세 및 월세 동향)
        # ── stap/seap 파이프라인 H2 (주식·예적금·복지) ──
        # 근거: 발행 표본 7블로그×80 포스트 2413 H2 중 미등록 강등 781종 실측 (2026-08-23,
        #       /tmp/stap_phase0_inventory.md·/tmp/seap_phase0_inventory.md)
        # ponytail: 도메인 명사 허용 방식이라 서술형 소제목 일부 통과 가능 — 재발 시 형태 제한으로 조임
        r"^함께\s*읽어",                          # 함께 읽어보기 (finance/etf/ipo/sector 최다 빈도)
        r"^관련\s*글$",                            # 관련글 / 관련 글
        r"^면책조항$",
        r"배당",                                   # dividend 전 카테고리 (배당률/배당컷/배당성향 등)
        r"ETF",
        r"공모가|주관사|보호예수|희석|증자",         # ipo
        r"업종",                                   # sector 업종 분석 계열
        r"실적|재무|매출|영업이익|순이익",           # 재무·실적 섹션
        r"리스크",
        r"전망|가능성|원인",                        # 향후 전망 / 반등 가능성 / 부진 원인
        r"예금|적금|금리|이자|실수령액|우대",        # finance 예적금 카테고리
        r"수익률",
        r"전략",
        r"종목|대장주|수혜주",
        r"(지원|서비스|혜택)\s*내용|보장\s*금액|적용\s*범위",  # senior 복지 혜택
        r"제도",                                   # 같이 신청하면 좋은 제도 등
        r"조건",                                   # 대상자/우대 조건
        r"주의할\s*점",                            # 이용 시 주의할 점
        r"(유리한가|유리할까|될까|어땠나|무엇인가|다를까|맞는가|맞을까|어디인가|어떤가)",  # 의문형 소제목
        r"추적오차",                               # etf
        r"하는\s*일$",                             # 이 회사가 하는 일
        r"매력도",                                 # 투자 매력도(평가)
        r"적합한\s*사람|부적합한\s*사람",
        r"\svs\s",                                # A vs B 비교형
        r"분석$",                                  # "~분석" 꼬리
        r"SPAC|스팩",
        r"^서론$",
        r"청약",
        r"데이터",
        # ── cap/car 파이프라인 H2 (자동차 비교·TCO·프로모션) ──
        # 근거: car writer 필수 H2 구조 (prompts/{guide,tco,deal,hotissue,compare,ev,rank,pick}),
        #       2026-08-23. re.search 부분일치 — 서술형 소제목은 강등 유지.
        r"기본\s*정보와\s*트림별\s*가격",     # 전 트림 가격 비교 계열
        r"트림별\s*가격",                      # 트림별 가격 / 가격 변동
        r"전\s*트림\s*가격",                   # 전 트림 가격과 가성비 분석
        r"월\s*유지비",                        # 월 유지비 시뮬레이션
        r"유지비",                             # 연간 유지비 상세 분석 / 유지비 총정리
        r"총\s*비용|총\s*소유비용|소유\s*비용",# 3년 보유 총비용 / 총 소유비용
        r"에너지\s*비용|보유\s*비용|실질\s*비용|전환\s*비용|실제\s*비용\s*계산",
        r"잔존가치",                           # 연차별 잔존가치 / 구조적 요인
        r"가성비",                             # 가성비 분석 / 가성비 트림
        r"경쟁\s*모델",                        # 경쟁 모델 비교
        r"TOP5|랭킹|순위",                     # TOP5 종합 랭킹표
        r"구매\s*타이밍|구매\s*판단|구매\s*결론|구매\s*가이드",
        r"어울리는\s*사람",                    # 이 차가 어울리는 사람, 어울리지 않는 사람
        r"경제성",                             # 하이브리드의 경제성
        r"혜택",                               # 세금·보험 혜택
        r"미리\s*알고",                        # 이런 점은 미리 알고 사야 한다
        r"(괜찮을까|진짜일까|싶을까|있을까|바뀌었나|얼마나|되나|될까|기다려야\s*하나)",  # 의문형 리드·판단 H2
    ]
    _ALLOWED_H2_RE = re.compile("|".join(_ALLOWED_H2_PATTERNS))

    def _fix_invalid_h2(match):
        heading_text = match.group(1).strip()
        if _ALLOWED_H2_RE.search(heading_text):
            return match.group(0)
        logger.warning(f"[H2-GUARD] 부적절한 H2 헤딩 감지 → bold 문단 변환: '{heading_text[:50]}'")
        return f"\n\n<strong>{heading_text}</strong>\n\n"

    body_md = re.sub(r"\n##\s+([^\n]+)", _fix_invalid_h2, body_md)
    
    # ── 긴 이미지 URL → R2 업로드 + 짧은 URL 대체 (파일명 255자 제한 회피) ──
    _DEFAULT_IMG = "https://pub-2f5c7af1c303419a933069212bc25874.r2.dev/common/default-thumbnail.webp"
    def _shorten_long_url(match):
        alt, url = match.group(1), match.group(2)
        if len(url) > 200:
            r2_url = _upload_image_to_r2(url, site_path=site_path)
            if r2_url:
                logger.info(f"[IMAGE-GUARD] 긴 URL({len(url)}자) → R2 업로드 완료")
                return f"![{alt}]({r2_url})"
            logger.warning(f"[IMAGE-GUARD] 긴 URL({len(url)}자) R2/로컬 업로드 실패, 원본 유지")
            return match.group(0)
        return match.group(0)
    body_md = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", _shorten_long_url, body_md)
    
    body_md = re.sub(r"\n{3,}", "\n\n", body_md)
    return body_md.strip()


def _convert_inline_md_to_html(text: str) -> str:
    """Convert markdown inline formatting to HTML inside raw HTML blocks.

    Hugo's Goldmark does not process markdown inside raw HTML elements
    (e.g. ``<p class="lead">``). This helper converts inline patterns
    so they render properly even inside HTML wrappers.

    Applied in order: strike > bold > italic > inline code > image > link.
    """
    import re as _re

    # must process in order to avoid interference
    # 1) ~~strike~~
    text = _re.sub(r"~~(.+?)~~", r"<del>\1</del>", text)
    # 2) **bold** (before single *)
    text = _re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    # 3) *italic* (only if not inside a word — avoid matching file_path or numbers)
    text = _re.sub(r"(?<!\w)\*(?!\*)(.+?)(?<!\*)\*(?!\w)", r"<em>\1</em>", text)
    # 4) `inline code`
    text = _re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    return text


def _fix_badge_shortcodes(body_md: str) -> str:
    """Remove orphaned {{< /badge >}} closing tags that lack a matching {{< badge >}}.

    AI sometimes generates {{< /badge >}} standalone (e.g. at end of a heading)
    or uses {{< /badge >}} instead of {{< badge >}} as the opening tag.
    Orphaned closing tags cause Hugo build failure with:
      'shortcode "badge" does not evaluate .Inner, yet a closing tag was provided'
    """
    parts = re.split(r"(\{\{< /?badge >\}\})", body_md)
    depth = 0
    result: list[str] = []
    for part in parts:
        if part == "{{< badge >}}":
            depth += 1
            result.append(part)
        elif part == "{{< /badge >}}":
            if depth > 0:
                depth -= 1
                result.append(part)
        else:
            result.append(part)
    return "".join(result)


def _apply_lead_shortcode(body_md: str) -> str:
    if not body_md.strip():
        return body_md

    if body_md.strip().startswith("{{< lead >}}"):
        return body_md

    blocks = body_md.split("\n\n")
    for i, block in enumerate(blocks):
        stripped = block.strip()
        if not stripped:
            continue
        if stripped.startswith(("# ", "## ", "### ", "{{<", "<p class", "```", ">")):
            return body_md
        stripped = _convert_inline_md_to_html(stripped)
        blocks[i] = f"{{{{< lead >}}}}\n{stripped}\n{{{{< /lead >}}}}"
        break
    return "\n\n".join(blocks)


def _apply_figure_shortcode(body_md: str) -> str:
    """Replace markdown images with {{< figure >}} shortcode."""
    if "![" not in body_md:
        return body_md
    lines = body_md.split("\n")
    in_code = False
    result = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.strip().startswith("```"):
            in_code = not in_code
            result.append(line)
            i += 1
            continue
        if not in_code:
            m = re.match(r'!\[([^\]]*)\]\(([^)]+)\)', line.strip())
            if m:
                alt = m.group(1)
                url = m.group(2)
                caption = alt
                for j in range(i + 1, min(i + 3, len(lines))):
                    next_line = lines[j].strip()
                    if not next_line:
                        continue
                    if not next_line.startswith(("#", "##", "###", "{{<", "![", "```", ">")):
                        if len(next_line) < 150:
                            caption = next_line
                            i = j
                        break
                escaped_caption = caption.replace("&", "&").replace("<", "<").replace(">", ">").replace('"', '"')
                if len(url) > 300:
                    result.append(f"![{alt}]({url})")
                else:
                    result.append(f"{{{{< figure src=\"{url}\" alt=\"{alt}\" caption=\"{escaped_caption}\" >}}}}")
                i += 1
                continue
        result.append(line)
        i += 1
    return "\n".join(result)


def _apply_gallery_shortcode(body_md: str) -> str:
    """Wrap 2+ consecutive {{< figure >}} shortcodes in {{< gallery >}}."""
    if "{{< figure" not in body_md:
        return body_md
    if "{{< gallery" in body_md:
        return body_md
    
    lines = body_md.split("\n")
    result = []
    i = 0
    while i < len(lines):
        if lines[i].strip().startswith("{{< figure"):
            fig_lines = [lines[i]]
            i += 1
            while i < len(lines):
                s = lines[i].strip()
                if s.startswith("{{< figure"):
                    fig_lines.append(lines[i])
                    i += 1
                elif not s:
                    i += 1
                else:
                    break
            if len(fig_lines) >= 2:
                result.append("{{< gallery >}}")
                result.extend(fig_lines)
                result.append("{{< /gallery >}}")
            else:
                result.extend(fig_lines)
            continue
        result.append(lines[i])
        i += 1
    return "\n".join(result)


def _apply_accordion_shortcode(body_md: str) -> str:
    """Wrap certain H2 sections (checkpoint, preparation) in {{< accordion >}}"""
    if "{{< accordion" in body_md:
        return body_md
    
    lines = body_md.split("\n")
    result = []
    i = 0
    collapse_patterns = ["체크포인트", "준비사항", "참고사항"]
    in_collapse = False
    buf = []
    label = ""
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        is_h2 = stripped.startswith("## ") and not stripped.startswith("### ")
        if is_h2:
            if in_collapse:
                result.extend(buf)
                result.append("{{< /accordion >}}")
                result.append('')
                buf = []
                in_collapse = False
            should_collapse = any(p in stripped for p in collapse_patterns)
            if should_collapse:
                in_collapse = True
                result.append(f'{{{{< accordion >}}}}')
                result.append('')
                i += 1
                continue
        if in_collapse:
            buf.append(line)
        else:
            result.append(line)
        i += 1
    if in_collapse:
        result.extend(buf)
        result.append("{{< /accordion >}}")
    return "\n".join(result)


_chart_idx = 0

def _apply_chart_shortcode(body_md: str) -> str:
    """Convert <!-- CHART: ... --> into inline chart HTML"""
    global _chart_idx
    if "<!-- CHART:" not in body_md:
        return body_md
    import json, re
    lines = body_md.split("\n")
    result = []
    for line in lines:
        m = re.search(r"<!--\s*CHART:\s*(.*?)-->", line)
        if m:
            try:
                items = json.loads(m.group(1))
                if len(items) < 2:
                    continue
                labels = [it["name"][:15] for it in items]
                datasets = []
                _m = {"gnrlSiteCo": "일반야영장", "glampSiteCo": "글램핑", "caravSiteCo": "카라반"}
                _f = {"toiletCo": "화장실", "swrmCo": "샤워실"}
                for key, label in {**_m, **_f}.items():
                    vals = [int(it.get(key, 0)) for it in items]
                    if any(v > 0 for v in vals):
                        datasets.append({"label": label, "data": vals})
                if not datasets:
                    continue
                cfg = json.dumps({
                    "type": "bar",
                    "data": {"labels": labels, "datasets": datasets},
                    "options": {
                        "responsive": True,
                        "plugins": {
                            "title": {"display": True, "text": "캠핑장 시설 비교", "font": {"size": 16}}
                        },
                        "scales": {
                            "y": {"beginAtZero": True, "title": {"display": True, "text": "개수"}}
                        }
                    }
                }, ensure_ascii=False)
                _chart_idx += 1
                cid = f"chart-{_chart_idx}"
                result.append(
                    f'<div class="chart"><canvas id="{cid}"></canvas>'
                    f'<script>window.addEventListener("DOMContentLoaded",()=>{{'
                    f'new Chart(document.getElementById("{cid}"),{cfg})}})</script></div>'
                )
            except Exception:
                pass
            continue
        result.append(line)
    return "\n".join(result)


def _validate_frontmatter(fm_text):
    """간단한 front matter 문법 검증 — 정규식으로 여는/closing --- 분리 (description 내 --- 무시)"""
    if not fm_text or "---" not in fm_text:
        return False, "no front matter"
    try:
        import yaml
        # ^---\\n 으로 시작하는 여는 marker 확인
        if not re.match(r"^---\s*\n", fm_text):
            return False, "front matter does not start with ---"
        # \\n---\\n 또는 \\n---$ 패턴으로 closing marker 찾기 (줄 끝의 --- 만 매칭)
        # split(\"---\")와 달리 값 안의 --- 를 무시함
        m = re.search(r"\n---\s*$", fm_text, re.MULTILINE)
        if not m:
            return False, "no closing front matter ---"
        fm_body = fm_text[4:m.start()].strip()
        if not fm_body:
            return False, "empty front matter"
        parsed = yaml.safe_load(fm_body)
        if not isinstance(parsed, dict):
            return False, "front matter is not a dict"
        return True, ""
    except Exception as e:
        return False, str(e)


def sanitize_featureimage_url(url, max_len=200):
    if not url:
        return ""
    if len(url) > max_len:
        logger.warning(f"[featureimage] URL이 {len(url)}자로 {max_len}자 초과 — 파일명 길이 제한 회피를 위해 기본 썸네일 사용")
        return ""
    return url


def _iter_body_images(body_md):
    """본문에서 이미지 URL을 순서대로 yield (쿠팡 광고 이미지 제외)."""
    import re as _re
    _skip_domains = ("ads-partners.coupang.com", "link.coupang.com")
    for m in _re.finditer(r"!\[.*?\]\((https?://[^)\s]+)\)", body_md or ""):
        url = m.group(1)
        if not any(d in url for d in _skip_domains):
            yield url
    for m in _re.finditer(r'<img[^>]+src="(https?://[^"]+)"', body_md or ""):
        url = m.group(1)
        if not any(d in url for d in _skip_domains):
            yield url


def _extract_first_image(body_md):
    """본문에서 첫 번째 이미지 URL 추출 (쿠팡 광고 이미지 제외)"""
    import re as _re2
    _skip_domains = ("ads-partners.coupang.com", "link.coupang.com")
    # 마크다운 이미지
    for m in _re2.finditer(r"!\[.*?\]\((.*?)\)", body_md or ""):
        url = m.group(1)
        if not any(d in url for d in _skip_domains):
            return url
    # HTML img
    for m in _re2.finditer(r'<img[^>]+src="(.*?)"', body_md or ""):
        url = m.group(1)
        if not any(d in url for d in _skip_domains):
            return url
    return ""


def _extract_description(body_md):
    _m = re.search(r"<!-- DESC:\s*(.+?)-->", body_md or "")
    if _m:
        desc = _m.group(1).strip()
    else:
        clean = body_md or ""
        # Strip Hugo shortcodes FIRST to prevent {{< lead >}} → {{}} when HTML is stripped
        # {{< lead >}}...{{< /lead >}} 블록 통째 제거 (퍼널 링크 텍스트 유입 방지)
        clean = re.sub(r"\{\{<\s*lead\s*>}}.*?\{\{<\s*/lead\s*>}}", "", clean, flags=re.DOTALL)
        clean = re.sub(r"\{\{<[^>]*?>}}", "", clean)
        clean = re.sub(r"<[^>]+>", "", clean)
        # 표가 시작되기 전까지만 사용 (파이프 행 제거)
        clean = re.split(r"\n\s*\|", clean)[0]
        # 마크다운 기호 제거: 헤딩(#), 볼드/이탤릭(*), 링크, 인용(>), 리스트(-)
        clean = re.sub(r"^#{1,6}\s*", "", clean, flags=re.MULTILINE)  # 헤딩
        clean = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", clean)      # 링크 → 텍스트
        clean = re.sub(r"[*_`>#|]+", "", clean)                        # 잔여 기호
        clean = re.sub(r"[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF\u2190-\u21FF\u2B00-\u2BFF]", "", clean)  # 이모지 제거
        clean = re.sub(r"^\s*[-]\s+", "", clean, flags=re.MULTILINE)  # 리스트 불릿
        clean = re.sub(r"\s+", " ", clean).strip()
        desc = clean
    
    # Truncate at word boundary (max 200 chars, but don't cut words)
    if len(desc) <= 200:
        # Even if <= 200, check if it ends mid-word (no trailing space/punctuation)
        if len(desc) == 200 and desc and desc[-1].isalnum():
            # Ends with alphanumeric - likely mid-word, find last space
            last_space = desc.rfind(' ')
            if last_space > 100:
                return desc[:last_space].rstrip() + '...'
        return desc
    
    truncated = desc[:200]
    last_space = truncated.rfind(' ')
    if last_space > 100:  # Only use word boundary if we don't lose too much
        return truncated[:last_space].rstrip() + '...'
    return truncated + '...'


def _build_schema_json(cfg, title, slug, body_md, category, tags, description=None):
    schema_type = "Article"
    if category in ("맛집", "식당"):
        schema_type = "LocalBusiness"
    elif category in ("관광", "여행"):
        schema_type = "Article"
    elif category == "캠핑":
        schema_type = "Campground"

    domain = cfg.get("domain", "")
    url = f"https://{domain}/posts/{slug}/" if domain else ""

    if description is None:
        description = _extract_description(body_md)
    date_published = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00")
    author_name = cfg.get("name", domain)

    schema = {
        "@context": "https://schema.org",
        "@type": schema_type,
        "name": title,
        "description": description,
        "datePublished": date_published,
        "author": {"@type": "Person", "name": author_name},
    }
    if url:
        schema["url"] = url

    if tags:
        if isinstance(tags, list):
            tag_list = [t.strip() for t in tags if t.strip()]
        else:
            tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        schema["keywords"] = ", ".join(tag_list)

    return '<script type="application/ld+json">\n' + json.dumps(schema, ensure_ascii=False, indent=2) + "\n</script>"


def _resolve_funnel_card_post(target_blog_id):
    try:
        from shared.content_store import get_conn
        conn = get_conn()
        row = conn.execute(
            "SELECT slug, title, published_url, blog_id, thumbnail_url FROM articles "
            "WHERE blog_id=? AND status='published' AND published_url IS NOT NULL "
            "ORDER BY created_at DESC LIMIT 1",
            (target_blog_id,)
        ).fetchone()
        conn.close()
        if row:
            return {
                "title": row["title"],
                "url": row["published_url"],
                "blog_id": row["blog_id"],
                "slug": row["slug"],
                "thumbnail_url": (row["thumbnail_url"] if "thumbnail_url" in row.keys() else "") or "",
            }
    except Exception as e:
        logger.debug(f"[FUNNEL] resolve post failed for {target_blog_id}: {e}")
    return None


def _build_funnel_card_html(post_info, funnel_type, source_blog_id):
    if not post_info:
        return None

    link_id = str(uuid.uuid4())[:8]
    target_blog_id = post_info.get("blog_id", "")
    target_url = post_info.get("url", "")
    target_title = post_info.get("title", "")
    thumbnail = post_info.get("thumbnail_url", "")

    label_text = "이 카테고리의 다음 글" if funnel_type == "depth" else "관련 카테고리 살펴보기"
    cta_text = "계속 읽기 →" if funnel_type == "depth" else "살펴보기 →"

    if thumbnail:
        thumbnail = sanitize_featureimage_url(thumbnail, max_len=500)
        thumb_html = f'<img class="funnel-card-thumb" src="{thumbnail}" alt="" loading="lazy">'
    else:
        thumb_html = '<div class="funnel-card-thumb funnel-card-thumb-placeholder"></div>'

    return (
        f'<div class="funnel-card funnel-{funnel_type} not-prose my-10" '
        f'data-funnel-link data-source-blog="{source_blog_id}" '
        f'data-target-blog="{target_blog_id}" '
        f'data-funnel-type="{funnel_type}" '
        f'data-funnel-id="{link_id}">'
        f'<div class="funnel-card-inner">'
        f'{thumb_html}'
        f'<div class="funnel-card-body">'
        f'<span class="funnel-card-label">{label_text}</span>'
        f'<h4 class="funnel-card-title">{_convert_inline_md_to_html(target_title)}</h4>'
        f'<a class="funnel-card-cta" href="{target_url}">{cta_text}</a>'
        f'</div></div></div>'
    )


def _extract_keywords(text, top_n=10):
    if not text:
        return []

    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[#*_`~\[\]()]", "", text)
    tokens = text.lower().split()

    ko_stop = {"이", "가", "은", "는", "을", "를", "의", "에", "에서", "와", "과", "도", "로",
               "으로", "하다", "있다", "되다", "같다", "그", "이런", "저런", "어떤", "모든",
               "통해", "대한", "위한", "때문", "아니", "등", "수", "것", "더", "매우", "정도",
               "및", "또는", "그리고", "하지만", "그러나", "때", "안", "후", "전", "중", "경우"}
    en_stop = {"the", "a", "an", "in", "of", "to", "is", "and", "or", "for", "on", "with",
               "at", "by", "from", "as", "are", "was", "were", "been", "be", "has", "have",
               "had", "do", "does", "did", "but", "not", "so", "if", "no", "up", "out", "it",
               "its", "all", "this", "that", "these", "those"}

    freq = {}
    for t in tokens:
        t = t.strip(".,;:!?\"'()-")
        if len(t) < 2:
            continue
        if t in ko_stop or t in en_stop:
            continue
        freq[t] = freq.get(t, 0) + 1

    sorted_words = sorted(freq.items(), key=lambda x: -x[1])
    return [w for w, _ in sorted_words[:top_n]]


def _keywords_overlap_check(src_keywords, tgt_keywords, threshold=0.0):
    # ponytail: threshold=0 disables broken Korean filter (no morpheme analyzer);
    # install konlpy if precision needed
    if not src_keywords or not tgt_keywords:
        return True

    src_set = set(src_keywords)
    tgt_set = set(tgt_keywords)
    intersection = src_set & tgt_set
    union = src_set | tgt_set

    if not union:
        return True

    overlap = len(intersection) / len(union)
    return overlap >= threshold


def _build_funnel_cards_md(blog_cfg, body_md):
    # ponytail: markdown-level injection. Hugo Goldmark passes raw HTML through,
    # so cards embedded in .md survive batch publishes (Hugo rebuild no longer wipes them).
    # Replaces v1 HTML-level injection which had double-build + batch-wipe bugs.
    blog_id = blog_cfg.get("id", "")
    depth_next = blog_cfg.get("depth_next") or []
    bridge_to = blog_cfg.get("bridge_to") or []

    if not depth_next and not bridge_to:
        return body_md, (0, 0)

    funnel_stage = blog_cfg.get("funnel_stage", "")
    if funnel_stage == "landing" and bridge_to:
        logger.info(f"[FUNNEL] {blog_id} is landing stage — suppressing bridge_to cards")
        bridge_to = []

    src_keywords = _extract_keywords(body_md) if body_md else []
    depth_html_parts = []
    bridge_html_parts = []

    for target in depth_next:
        if target.get("id") == blog_id:
            continue
        post = _resolve_funnel_card_post(target["id"])
        if not post:
            logger.debug(f"[FUNNEL] depth skip {target['id']} — no published post")
            continue
        card_html = _build_funnel_card_html(post, "depth", blog_id)
        if card_html:
            depth_html_parts.append(card_html)

    for target in bridge_to:
        if target.get("id") == blog_id:
            continue
        post = _resolve_funnel_card_post(target["id"])
        if not post:
            logger.debug(f"[FUNNEL] bridge skip {target['id']} — no published post")
            continue
        if src_keywords:
            tgt_keywords = _extract_keywords(post.get("title", ""))
            if not _keywords_overlap_check(src_keywords, tgt_keywords):
                logger.debug(f"[FUNNEL] bridge skip {target['id']} — context mismatch")
                continue
        card_html = _build_funnel_card_html(post, "bridge", blog_id)
        if card_html:
            bridge_html_parts.append(card_html)

    if not depth_html_parts and not bridge_html_parts:
        return body_md, (0, 0)

    paragraphs = body_md.split("\n\n") if body_md else []
    if bridge_html_parts and len(paragraphs) > 2:
        mid_idx = max(1, int(len(paragraphs) * 0.5))
        bridge_block = "\n\n".join(bridge_html_parts)
        paragraphs.insert(mid_idx, bridge_block)
        body_md = "\n\n".join(paragraphs)
    elif bridge_html_parts:
        body_md = body_md + "\n\n" + "\n\n".join(bridge_html_parts)

    if depth_html_parts:
        body_md = body_md + "\n\n" + "\n\n".join(depth_html_parts)

    counts = (len(depth_html_parts), len(bridge_html_parts))
    logger.info(f"[FUNNEL] cards injected: {counts[0]} depth + {counts[1]} bridge")
    return body_md, counts


def _write_hugo_post(blog_cfg, title, body_md, slug, category, tags, thumbnail_url, is_draft=False,
                     inject_internal_links=False, adsense_config=None, cross_sell_config=None,
                     body_images=None):
    """Write a Hugo post with optional ETAP post-processing hooks.

    Args:
        blog_cfg: Blog configuration dict (theme, site_path, id, domain, etc.)
        title: Post title
        body_md: Markdown body content
        slug: URL slug
        category: Post category
        tags: Comma-separated tags string or list
        thumbnail_url: Featured image URL
        is_draft: Whether post is a draft
        inject_internal_links: If True, inject cross-blog internal links via entity_linker
        adsense_config: If provided, insert AdSense blocks. Dict with keys:
            None = use default ETAP AdSense block
            {"html": "..."} = use custom AdSense HTML
        cross_sell_config: If provided, insert cross-sell block. Dict with keys:
            country, city, exclude_blog, max_items, position ("top"|"bottom")
        body_images: List of body image dicts (url, credit) to insert after H2 headings

    Returns:
        dict with success, file, url keys on success; or success=False with error
    """
    if not slug or not str(slug).strip():
        logger.error(f"[PUBLISH] slug가 비어있어 발행 중단: title={title}")
        return {"success": False, "error": "empty slug"}

    # ── C01 사전 정규화 (2026-08-22 Paris 재발행 실패 근본 수정) ──
    # 곡선따옴표(’ ‘ ”)를 fm 빌드 전에 직선화한다. _sanitize_yaml_value는
    # 직선 ' 유무로 단일/이중 인용 전략을 결정하므로, 곡선따옴표가 남은 채
    # 빌드되면 'A Food Lover's ...' 형태의 단일따옴표 YAML이 만들어지고,
    # 이후 C01 치환이 그 내부를 직선화해 invalid_frontmatter로 쓰기 차단됨.
    # title/body를 여기서 1회 정규화하면 description(_extract_description 결과)
    # 까지 자동 정규화되고, fm 후처리 치환은 불필요해짐.
    def _c01_straight(_s):
        if not isinstance(_s, str):
            return _s
        for _q in ("\u2018", "\u2019"):
            _s = _s.replace(_q, "'")
        for _q in ("\u201c", "\u201d"):
            _s = _s.replace(_q, '"')
        return _s

    title = _c01_straight(title)
    body_md = _c01_straight(body_md)

    # locale 감지 (schema_json 오염 전 — 본문 기준으로만 결정)
    _locale = _detect_locale(body_md)

    theme = blog_cfg.get("theme", "PaperMod")
    site_path = blog_cfg.get("site_path", "")
    if not site_path:
        site_path = os.path.join(os.path.dirname(FIVEK_ROOT), blog_cfg.get("repo", ""))
    # ── C01/C04 원인추적 훅 (a) 생성 직후 ──
    try:
        from shared.leak_tracker import check_c01_c04
        _leak_result = check_c01_c04(body_md, "after_generation", slug, locale=_locale, blog_id=blog_cfg.get("id", ""), log_every_stage=True)
        if _leak_result["c01_detected"] or _leak_result["c04_detected"]:
            logger.info(f"[LEAK-TRACKER] (a)생성직후 C01:{_leak_result['c01_detected']} C04:{_leak_result['c04_detected']} {slug}")
    except ImportError:
        pass

    body_md = _clean_body(body_md, site_path=site_path)

    # ── recurrence prevention: editorial_synthesis 프롬프트 릭 자동 제거 (A=데이터 문장, B=메타 블록) ──
    # CUAP/SEAP/CAP/TAP 공통: _sentence_for(table,...)가 "From {table}, verified records indicate..." 생성.
    # table은 products/cars/trims/hotels 등 가변 → 테이블명 무관하게 제거. 단 "
    # {{" shortcode는 아님(오탐 방지). 생성 직후 본문에서 제거해 live 누수 차단.
    _leak_re = re.compile(r"(?im)^\s*From [a-z]+, verified records indicate[^\n]*\n?")
    if _leak_re.search(body_md):
        body_md = _leak_re.sub("", body_md)
        logger.info(f"[LEAK-STRIP] editorial_synthesis 데이터 문장(Part A) 제거: {slug}")
    # Part B: editorial_synthesis 메타 코멘트 블록 ("This editorial synthesis is constructed exclusively...preserving the integrity of the reported facts")
    _leak_re_b = re.compile(r"(?is)This editorial synthesis is constructed exclusively.*?preserving the integrity of the reported facts\.?")
    if _leak_re_b.search(body_md):
        body_md = _leak_re_b.sub("", body_md)
        logger.info(f"[LEAK-STRIP] CUAP 프롬프트 릭 블록(Part B) 제거: {slug}")

    # ── recurrence prevention: P35 라벨덤프 자동 제거 (C10_LABEL_RE 미러) ──
    # 가격:/장점:/단점: 등 라벨 표기는 위키/블로그 본문에 부적합. STAP/TAP/CUAP 공통.
    # 라인 전체(HTML 태그 포함) 제거해 잔여 라벨덤프 차단.
    _label_re = re.compile(
        r"(?im)^\s*(?:가격|배송|쿠팡순위|장점|아쉬운점|단점|적당한대상|적합대상|"
        r"추천대상|추천\s*대상|페르소나)\s*[:：].*$"
    )
    if _label_re.search(body_md):
        body_md = _label_re.sub("", body_md)
        logger.info(f"[LABEL-STRIP] P35 라벨덤프 라인 제거: {slug}")
    # ── C01/C04 원인추적 훅 (b) humanizer 통과 직후 ──
    try:
        from shared.leak_tracker import check_c01_c04
        _leak_result = check_c01_c04(body_md, "after_humanizer", slug, locale=_locale, blog_id=blog_cfg.get("id", ""), log_every_stage=True)
        if _leak_result["c01_detected"] or _leak_result["c04_detected"]:
            logger.info(f"[LEAK-TRACKER] (b)humanizer후 C01:{_leak_result['c01_detected']} C04:{_leak_result['c04_detected']} {slug}")
    except ImportError:
        pass

    description = _extract_description(body_md)

    if not thumbnail_url:
        # featureimage 중복 방지: 이미 사용된(is_image_used) 이미지는 건너뛰고
        # 본문에서 다음 사용 가능한 이미지를 찾는다.
        try:
            from shared.content_store import is_image_used
        except ImportError:
            is_image_used = None
        _bid = (blog_cfg or {}).get("id", "")
        for _cand in _iter_body_images(body_md):
            if is_image_used is None or not is_image_used(_cand, blog_id=_bid):
                thumbnail_url = _cand
                break
        if not thumbnail_url:
            thumbnail_url = _extract_first_image(body_md)
    
    if thumbnail_url and not thumbnail_url.startswith(("http://", "https://")):
        thumbnail_url = "https://img.informationhot.kr/" + thumbnail_url.lstrip("/")
    
    # Long featureimage URL → R2 업로드 (파일명 255자 제한 회피)
    if thumbnail_url and len(thumbnail_url) > 500:
        r2_url = _upload_image_to_r2(thumbnail_url, site_path=site_path)
        if r2_url:
            thumbnail_url = r2_url
    
    thumbnail_url = sanitize_featureimage_url(thumbnail_url, max_len=500)
    if not thumbnail_url:
        _blog_id = blog_cfg.get("id", "")
        if "stock" in _blog_id:
            thumbnail_url = "https://pub-2f5c7af1c303419a933069212bc25874.r2.dev/common/stock-default-thumbnail.webp"

    if thumbnail_url and thumbnail_url.startswith("http://tong.visitkorea.or.kr"):
        thumbnail_url = thumbnail_url.replace("http://", "https://", 1)

    # Convert inline markdown in title to HTML (for bold, strike, etc.)
    # so it renders correctly in the frontmatter and page title
    title = _convert_inline_md_to_html(title)

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
        fm, _date_str = _build_frontmatter_papermod(title, slug, category, tags, thumbnail_url, description, is_draft=is_draft)
        date_prefix = datetime.now().strftime("%Y-%m-%d")
        post_dir = os.path.join(site_path, "content", "posts")
        os.makedirs(post_dir, exist_ok=True)
        file_path = os.path.join(post_dir, date_prefix + "-" + slug + ".md")

    body_md = re.sub(r"<!-- DESC:.*?-->", "", body_md).strip()
    body_md = _fix_badge_shortcodes(body_md)
    if blog_cfg.get("theme", "").lower() == "blowfish" and blog_cfg.get("shortcodes_enabled", True):
        body_md = _apply_lead_shortcode(body_md)
        body_md = _apply_figure_shortcode(body_md)
        body_md = _apply_gallery_shortcode(body_md)
        body_md = _apply_chart_shortcode(body_md)
        body_md = _apply_accordion_shortcode(body_md)
    # Convert inline markdown (**bold**, ~~strike~~, *italic*, `code`) to HTML
    # globally — Hugo's Goldmark does not process markdown inside raw HTML
    # elements (e.g. <figcaption>, <p> generated by shortcode functions, or
    # AI output with mixed HTML+markdown).  Doing it here ensures readers
    # never see raw ** or ~~ in the rendered page.
    body_md = _convert_inline_md_to_html(body_md)
    body_md, _funnel_counts = _build_funnel_cards_md(blog_cfg, body_md)

    # ── ETAP post-processing hooks (additive, opt-in) ──
    blog_id = blog_cfg.get("id", "")

    # 1. Internal links injection
    if inject_internal_links:
        try:
            from shared.entity_linker import inject_internal_links as _inject_links
            body_md = _inject_links(body_md, current_blog=blog_id, max_links=5)
        except ImportError:
            logger.warning("[PUBLISH] shared.entity_linker not available — skipping internal links")

    # 2. Body images insertion (after H2 headings)
    if body_images:
        h2_positions = [m.start() for m in re.finditer(r"^## ", body_md, re.MULTILINE)]
        for idx in range(min(len(body_images), len(h2_positions))):
            img = body_images[idx]
            img_url = img.get("url", "")
            img_credit = img.get("credit", "")
            # M3.2(2026-08-21): alt="Photo" 하드코딩 금지 — 문맥(글 제목) 기반 alt
            alt_text = (title or img_credit or "Photo") or "Photo"
            img_block = f"\n\n![{alt_text}]({img_url})\n*{img_credit}*\n"
            h2_line_end = body_md.index("\n", h2_positions[idx]) + 1
            next_pp = body_md.find("\n\n", h2_line_end)
            if next_pp == -1:
                next_pp = len(body_md)
            body_md = body_md[:next_pp] + img_block + body_md[next_pp:]
            # Recalculate H2 positions after insertion
            h2_positions = [m.start() for m in re.finditer(r"^## ", body_md, re.MULTILINE)]

    # 2.5. Disclaimer insertion before first affiliate link (Rule B)
    #    Insert "이 포스팅은 쿠팡 파트너스 활동의 일환으로..." right before
    #    the first affiliate link (<a href="...link.coupang.com...">).
    #    Skip if no affiliate link found (do NOT insert at top as fallback —
    #    misplaced disclosure must be avoided).
    #    Skip if disclaimer already exists near top (top 20% of body).
    _DISCLAIMER_TEXT = (
        "이 포스팅은 쿠팡 파트너스 활동의 일환으로, "
        "이에 따른 일정액의 수수료를 제공받습니다.\n\n"
    )
    _affiliate_link_re = re.compile(r'<a\s[^>]*href=["\'][^"\']*link\.coupang\.com[^"\']*["\'][^>]*>', re.IGNORECASE)
    _top_disclaimer_re = re.compile(
        r'이 포스팅은 쿠팡 파트너스 활동의 일환으로.*수수료를 제공받습니다\.?',
        re.DOTALL,
    )

    def _needs_disclaimer(body: str) -> bool:
        """본문 어디에든 면책이 이미 있으면 False.

        ⚠️ 상단 30%만 검사하면 쿠팡 그리드(<div>) 안에 plain text 면책을
        중복 삽입하게 되어 Goldmark raw-HTML 블록이 끊긴다.
        (Goldmark가 문단을 <p>로 재감싸며 style 따옴표를 벗기고 그리드를 해체
        → 카드가 가로 정렬되지 않음)
        coupon_travel.get_product_cards()가 이미 그리드 뒤에 <p> 면책을 1회
        추가하므로, 본문 전체에 면책 문구가 있으면 여기서는 스킵한다."""
        if not body:
            return False
        return not re.search(r'이 포스팅은 쿠팡 파트너스 활동의 일환으로', body)

    def _insert_disclaimer_before_first_affiliate(body: str) -> tuple[str, bool, str]:
        """첫 제휴 링크 앞에 면책 삽입. 성공 시 (body, True, ''), 실패 시 (body, False, 사유)."""
        if not _needs_disclaimer(body):
            return body, False, "상단 면책 이미 존재 — 스킵"
        m = _affiliate_link_re.search(body)
        if not m:
            return body, False, "제휴 링크 특정 불가 — 스킵 (폴백 삽입 금지)"
        insert_pos = m.start()
        # 앞 라인 끝을 정리 (빈 줄 하나 추가)
        prefix = body[:insert_pos].rstrip()
        if prefix and not prefix.endswith("\n"):
            prefix += "\n\n"
        return prefix + _DISCLAIMER_TEXT + body[insert_pos:], True, ""

    body_md, disc_inserted, disc_reason = _insert_disclaimer_before_first_affiliate(body_md)
    if disc_inserted:
        logger.info(f"[PUBLISH] 면책 문구 첫 제휴 링크 직전 삽입 완료: {blog_id}/{slug}")
    elif disc_reason != "상단 면책 이미 존재 — 스킵":
        logger.warning(f"[PUBLISH] 면책 문구 삽입 스킵: {blog_id}/{slug} — {disc_reason}")

    # 3. AdSense block insertion
    if adsense_config is not None:
        try:
            from pipelines.etap.post_processor import insert_adsense as _insert_ads
            body_md = _insert_ads(body_md)
        except ImportError:
            logger.warning("[PUBLISH] pipelines.etap.post_processor not available — skipping AdSense")

    # 4. Cross-sell block insertion
    if cross_sell_config is not None:
        try:
            from shared.entity_linker import build_cross_sell_html as _build_cross
            from pipelines.etap.post_processor import insert_cross_sell_block as _insert_cross
            _cs_country = cross_sell_config.get("country", "")
            _cs_city = cross_sell_config.get("city", "")
            _cs_exclude = cross_sell_config.get("exclude_blog", blog_id)
            _cs_max = cross_sell_config.get("max_items", 3)
            _cs_position = cross_sell_config.get("position", "bottom")
            _cross_html = _build_cross(country=_cs_country, city=_cs_city,
                                       exclude_blog=_cs_exclude, max_items=_cs_max)
            if _cross_html:
                body_md = _insert_cross(body_md, _cross_html, position=_cs_position)
        except ImportError:
            logger.warning("[PUBLISH] cross-sell modules not available — skipping cross-sell")

    schema_json = _build_schema_json(blog_cfg, title, slug, body_md, category, tags, description=description)
    body_md = body_md + "\n\n" + schema_json

    # ── Defense-in-depth: 본문 소실 방지 가드 (크로스셀/카드 삽입 후 재검증) ──
    # 진입부 가드(L1245-1258)는 article["content"] 초기 상태만 검사하므로,
    # 이후 삽입 과정에서 본문이 소실된 경우를 여기서 막는다.
    _body_word_count = len(body_md.split())
    if _body_word_count < 200:
        logger.error(
            f"[ETAP-GUARD] 본문 소실 감지: blog_id={blog_id}, slug={slug}, "
            f"title={title}, words={_body_word_count} < 200. "
            f"포스트처리 중 본문이 삭제/소실되었을 가능성이 높습니다. 발행을 거부합니다."
        )
        return {"success": False, "error": f"body_md_too_short: {_body_word_count} words"}

    # ── C01 fix (defense-in-depth): 본문만 치환 (2026-08-22 수정) ──
    # title/description은 위 _c01_straight()로 fm 빌드 전 정규화되므로 fm은
    # 이미 안전함. 여기서 fm을 치환하면 _sanitize_yaml_value가 단일따옴표로
    # 감싼 값 내부가 직선화되어 invalid_frontmatter 쓰기 차단이 재발함.
    # (humanizer 우회 경로 등 본문 잔존 곡선따옴표 대비 — body_md만 치환)
    for _c in ["\u2018", "\u2019"]:
        body_md = body_md.replace(_c, "'")
    for _c in ["\u201c", "\u201d"]:
        body_md = body_md.replace(_c, '"')

    # ── PHASE 70 WAVE 3: lastmod in frontmatter (overrides date on re-publish) ──
    # Freshness signals for Google (dateModified). ISO format matches date field.
    _lastmod_iso = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00")
    if fm.endswith("---\n"):
        fm = fm[: -len("---\n")] + f"lastmod: {_lastmod_iso}\n---\n"
    elif fm.endswith("---"):
        fm = fm[:-3] + f"lastmod: {_lastmod_iso}\n---\n"

    content = fm + body_md

    # ── C01/C04 원인추적 훅 (c) 저장 직전 ──
    try:
        from shared.leak_tracker import check_c01_c04
        _leak_result = check_c01_c04(content, "before_write", slug, locale=_locale, blog_id=blog_cfg.get("id", ""), log_every_stage=True)
        if _leak_result["c01_detected"] or _leak_result["c04_detected"]:
            logger.warning(f"[LEAK-TRACKER] (c)저장직전 C01:{_leak_result['c01_detected']} C04:{_leak_result['c04_detected']} — 배포중단 대상 {slug}")
            return {"success": False, "error": f"leak_detected: C01={_leak_result['c01_detected']}, C04={_leak_result['c04_detected']}"}
    except ImportError:
        pass

    # ── C09: categories/tags 문자열화 저장 직전 차단 (CRITICAL) ──
    try:
        import yaml as _yaml9
        _c09_fm = _yaml9.safe_load(fm) or {}
        if isinstance(_c09_fm, dict):
            _c09_issues = []
            for _c09_field in ('categories', 'tags'):
                _c09_val = _c09_fm.get(_c09_field)
                if _c09_val is not None and isinstance(_c09_val, str):
                    import re as _re9
                    if _re9.match(r'^\[\s*[\'"].*[\'"]\s*\]$', _c09_val.strip()):
                        _c09_issues.append(f"{_c09_field}='{_c09_val}'")
            if _c09_issues:
                logger.warning(f"[C09] 저장직전 categories/tags 문자열화 탐지 — 배포차단 {slug}: {_c09_issues}")
                return {"success": False, "error": f"C09_violation: {_c09_issues}"}
    except Exception:
        pass  # YAML 파싱 실패 시 C09 검사는 skip

    _ok, _err = _validate_frontmatter(fm)
    if not _ok:
        logger.error(f"[PUBLISH] Invalid front matter — write blocked: {_err}")
        return {"success": False, "error": f"invalid_frontmatter: {_err}"}

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    logger.info(f"[PUBLISH] Hugo post written: {file_path}")

    domain = blog_cfg.get("domain", "")
    expected_url = f"https://{domain}/posts/{slug}/"
    return {"success": True, "file": file_path, "url": expected_url}


def _write_hugo_post_etap(article, cover_image=None, body_images=None, blog_id=None,
                          site_path=None, category=None, is_draft=False):
    """ETAP convenience wrapper — maps ETAP article format to shared _write_hugo_post().

    This function translates the ETAP article dict convention into the shared
    _write_hugo_post() call, enabling all ETAP-specific post-processing hooks
    (internal links, AdSense, body images, cross-sell).

    Args:
        article: ETAP article dict with keys: slug, title, content, tags, description,
                 _draft, country, city, image_url, image_credit
        cover_image: Cover image dict with 'url' and optional 'credit' keys
        body_images: List of body image dicts with 'url' and 'credit' keys
        blog_id: Blog identifier string
        site_path: Hugo site filesystem path
        category: Post category string
        is_draft: Whether post is a draft

    Returns:
        Post directory path on success, None on failure
    """
    slug = article["slug"]
    title = article["title"]
    content = article["content"]

    # ── ETAP-GUARD: 빈 content / 최소 단어수 미달 차단 (2026-08-12 재발 방지) ──
    if not content or not content.strip():
        logger.error(
            f"[ETAP-GUARD] 빈 content 차단: blog_id={blog_id}, slug={slug}, "
            f"title={title}. article['content']가 비어있어 발행을 거부합니다."
        )
        return None

    if len(content.split()) < 200:
        logger.error(
            f"[ETAP-GUARD] 최소 단어수 미달 차단: blog_id={blog_id}, slug={slug}, "
            f"words={len(content.split())} < 200"
        )
        return None

    # ── C01 fix: 곡선따옴표 → 직선따옴표 (ETAP 영어 콘텐츠는 humanizer 미적용) ──
    _C01_CURVED_SINGLE = ["\u2018", "\u2019"]  # ' '
    _C01_CURVED_DOUBLE = ["\u201c", "\u201d"]  # " "
    for _c in _C01_CURVED_SINGLE:
        content = content.replace(_c, "'")
    for _c in _C01_CURVED_DOUBLE:
        content = content.replace(_c, '"')

    # ── C01/C04 원인추적 훅 (a) ETAP 생성 직후 ──
    try:
        from shared.leak_tracker import check_c01_c04  # _detect_locale(content) for etap locale fix
        _leak_result = check_c01_c04(content, "after_generation_etap", slug, locale=_detect_locale(content), blog_id=blog_id or "", log_every_stage=True)
        if _leak_result["c04_detected"]:
            logger.info(f"[LEAK-TRACKER] (a)ETAP생성직후 C04:{_leak_result['c04_detected']} {slug}")
    except ImportError:
        pass

    tags = article.get("tags", [])
    # ETAP article의 tags는 list — shared _build_frontmatter_*()는 콤마 구분
    # 문자열을 기대(tags.split(",")). list는 콤마 join으로 정규화 (str이면 그대로).
    if isinstance(tags, list):
        tags = ",".join(str(t).strip() for t in tags if str(t).strip())
    description = article.get("description", "")
    is_draft = is_draft or article.get("_draft", False)

    # Resolve thumbnail: prefer cover_image arg → article.image_url → None
    thumbnail_url = None
    if cover_image and cover_image.get("url"):
        thumbnail_url = cover_image["url"]
    elif article.get("image_url"):
        thumbnail_url = article["image_url"]

    # Build blog_cfg for the shared function
    blog_cfg = {
        "id": blog_id or "",
        "site_path": site_path or "",
        "theme": "Blowfish",
        "domain": "",
        "shortcodes_enabled": True,
    }

    result = _write_hugo_post(
        blog_cfg=blog_cfg,
        title=title,
        body_md=content,
        slug=slug,
        category=category or "",
        tags=tags,
        thumbnail_url=thumbnail_url,
        is_draft=is_draft,
        inject_internal_links=True,
        adsense_config={},
        cross_sell_config={
            "country": article.get("country", ""),
            "city": article.get("city", ""),
            "exclude_blog": blog_id or "",
            "max_items": 3,
            "position": "bottom",
        },
        body_images=body_images,
    )

    if result.get("success"):
        return os.path.join(site_path, "content", "posts", slug)
    else:
        logger.error(f"[ETAP] _write_hugo_post_etap failed: {result.get('error')}")
        return None

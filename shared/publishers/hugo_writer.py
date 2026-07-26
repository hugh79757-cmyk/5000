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
        fm += 'categories: [' + _sanitize_yaml_value(category) + ']\n'
    if tag_list:
        fm += "tags: [" + ", ".join(_sanitize_yaml_value(t) for t in tag_list) + "]\n"
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
        fm += "tags: [" + ", ".join(_sanitize_yaml_value(t) for t in tag_list) + "]\n"
    if category:
        fm += "categories: ['" + category + "']\n"
    if thumbnail_url:
        fm += "cover:\n"
        fm += '  image: ' + _sanitize_yaml_value(thumbnail_url) + '\n'
        fm += '  relative: true\n'
        fm += '  alt: ' + _sanitize_yaml_value(title) + '\n'
        fm += "  hidden: false\n"
        fm += 'featureimage: ' + _sanitize_yaml_value(thumbnail_url) + '\n'
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
        fm += 'categories: [' + _sanitize_yaml_value(category) + ']\n'
    if tag_list:
        fm += "tags: [" + ", ".join(_sanitize_yaml_value(t) for t in tag_list) + "]\n"
    if thumbnail_url:
        fm += "cover:\n"
        fm += '  image: ' + _sanitize_yaml_value(thumbnail_url) + '\n'
        fm += '  relative: true\n'
        fm += 'featureimage: ' + _sanitize_yaml_value(thumbnail_url) + '\n'
    elif "stock" in blog_id:
        _url = "https://pub-2f5c7af1c303419a933069212bc25874.r2.dev/common/stock-default-thumbnail.webp"
        fm += "cover:\n"
        fm += '  image: ' + _sanitize_yaml_value(_url) + '\n'
        fm += '  relative: true\n'
        fm += 'featureimage: ' + _sanitize_yaml_value(_url) + '\n'
    else:
        _url = "https://pub-2f5c7af1c303419a933069212bc25874.r2.dev/common/default-thumbnail.webp"
        fm += "cover:\n"
        fm += '  image: ' + _sanitize_yaml_value(_url) + '\n'
        fm += '  relative: true\n'
        fm += 'featureimage: ' + _sanitize_yaml_value(_url) + '\n'
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
        r"^[가-힣]+ 고를 때 확인할 포인트",
        r"^한눈에 보는 비교표",
        r"^[0-9]+위:",
        r"^자주 묻는 질문",
        r"^상황별 추천 정리",
        r"^[가-힣]+ 추천$",
        r"^비교$",
        r"^장단점$",
        r"^구매 가이드$",
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


def _extract_first_image(body_md):
    """본문에서 첫 번째 이미지 URL 추출"""
    import re as _re2
    m = _re2.search(r"!\[.*?\]\((.*?)\)", body_md or "")
    if m:
        return m.group(1)
    m = _re2.search(r'<img[^>]+src="(.*?)"', body_md or "")
    if m:
        return m.group(1)
    return ""


def _extract_description(body_md):
    _m = re.search(r"<!-- DESC:\s*(.+?)-->", body_md or "")
    if _m:
        desc = _m.group(1).strip()
    else:
        clean = body_md or ""
        # Strip Hugo shortcodes FIRST to prevent {{< lead >}} → {{}} when HTML is stripped
        clean = re.sub(r"\{\{<[^>]*?>}}", "", clean)
        clean = re.sub(r"<[^>]+>", "", clean)
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
                "thumbnail_url": row.get("thumbnail_url") or "",
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


def _write_hugo_post(blog_cfg, title, body_md, slug, category, tags, thumbnail_url, is_draft=False):
    if not slug or not str(slug).strip():
        logger.error(f"[PUBLISH] slug가 비어있어 발행 중단: title={title}")
        return {"success": False, "error": "empty slug"}

    theme = blog_cfg.get("theme", "PaperMod")
    site_path = blog_cfg.get("site_path", "")
    if not site_path:
        site_path = os.path.join(os.path.dirname(FIVEK_ROOT), blog_cfg.get("repo", ""))
    body_md = _clean_body(body_md, site_path=site_path)
    description = _extract_description(body_md)

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
    schema_json = _build_schema_json(blog_cfg, title, slug, body_md, category, tags, description=description)
    body_md = body_md + "\n\n" + schema_json
    content = fm + body_md

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

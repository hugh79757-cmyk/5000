import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path

from shared.paths import FIVEK_ROOT
logger = logging.getLogger(__name__)


def _sanitize_yaml_value(s, max_len=None):
    if s is None:
        return ""
    s = str(s)
    if max_len:
        s = s[:max_len]
    return s.replace("\\", "\\\\").replace('"', '\\"')


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
    fm += 'title: "' + _sanitize_yaml_value(title) + '"\n'
    fm += "date: " + date_str + "\n"
    fm += f"draft: {'true' if is_draft else 'false'}\n"
    if description:
        fm += 'description: "' + _sanitize_yaml_value(description, max_len=200) + '"\n'
    fm += 'slug: "' + slug + '"\n'
    if category:
        fm += 'categories: ["' + category + '"]\n'
    if tag_list:
        fm += "tags: [" + ", ".join('"' + t + '"' for t in tag_list) + "]\n"
    if thumbnail_url:
        fm += 'image: "' + thumbnail_url + '"\n'
        fm += 'featureimage: "' + thumbnail_url + '"\n'
    elif "stock" in blog_id:
        _url = "https://pub-2f5c7af1c303419a933069212bc25874.r2.dev/common/stock-default-thumbnail.webp"
        fm += 'image: "' + _url + '"\n'
        fm += 'featureimage: "' + _url + '"\n'
    else:
        _url = "https://pub-2f5c7af1c303419a933069212bc25874.r2.dev/common/default-thumbnail.webp"
        fm += 'image: "' + _url + '"\n'
        fm += 'featureimage: "' + _url + '"\n'
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
    
    fm = "---\n"
    fm += 'title: "' + _sanitize_yaml_value(title) + '"\n'
    fm += "date: '" + date_str + "'\n"
    fm += "slug: '" + slug + "'\n"
    fm += f"draft: {'true' if is_draft else 'false'}\n"
    if description:
        fm += 'description: "' + _sanitize_yaml_value(description, max_len=200) + '"\n'
    if tag_list:
        fm += "tags: " + str(tag_list) + "\n"
    if category:
        fm += "categories: ['" + category + "']\n"
    if thumbnail_url:
        fm += "cover:\n"
        fm += '  image: "' + thumbnail_url + '"\n'
        fm += '  alt: "' + _sanitize_yaml_value(title) + '"\n'
        fm += "  hidden: false\n"
        fm += 'featureimage: "' + thumbnail_url + '"\n'
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
    
    fm = "---\n"
    fm += 'title: "' + _sanitize_yaml_value(title) + '"\n'
    fm += "date: " + date_str + "\n"
    fm += "draft: " + str(is_draft).lower() + "\n"
    if description:
        fm += 'description: "' + _sanitize_yaml_value(description, max_len=200) + '"\n'
    fm += 'slug: "' + slug + '"\n'
    if category:
        fm += "categories: " + str([category]) + "\n"
    if tag_list:
        fm += "tags: " + str(tag_list) + "\n"
    if thumbnail_url:
        fm += "cover:\n"
        fm += '  image: "' + thumbnail_url + '"\n'
        fm += 'featureimage: "' + thumbnail_url + '"\n'
    elif "stock" in blog_id:
        _url = "https://pub-2f5c7af1c303419a933069212bc25874.r2.dev/common/stock-default-thumbnail.webp"
        fm += 'cover:\n  image: "' + _url + '"\n'
        fm += 'featureimage: "' + _url + '"\n'
    else:
        _url = "https://pub-2f5c7af1c303419a933069212bc25874.r2.dev/common/default-thumbnail.webp"
        fm += 'cover:\n  image: "' + _url + '"\n'
        fm += 'featureimage: "' + _url + '"\n'
    fm += "---\n"
    return fm, date_str


def _clean_body(body_md):
    """Clean body markdown — AI 가짜 내부링크, 빈 템플릿, 과도한 개행 제거"""
    if not body_md:
        return body_md
    body_md = re.sub(
        r"\n+##\s*(함께|관련|추천|더)\s*(읽어보기|읽을거리|글|포스트|게시물|기사)[^\n]*(\n(?!##|$)[^\n]*)*",
        lambda m: m.group() if "{{<" in m.group() else "",
        body_md,
    )
    body_md = re.sub(r"\{\{(?![<%])[^}]*\}\}", "", body_md)
    # 외부 CDN 이미지 차단 → Cloudflare R2 fallback으로 대체
    body_md = re.sub(
        r"https?://[^/\s]*sspark\.genspark\.ai[^\s)]*",
        "https://pub-2f5c7af1c303419a933069212bc25874.r2.dev/placeholder.webp",
        body_md
    )
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


def _apply_lead_shortcode(body_md: str) -> str:
    if not body_md.strip():
        return body_md

    if body_md.strip().startswith("<p class=\"lead\""):
        # Body already has a lead block (from a previous run).
        # Convert inline markdown inside existing HTML wrappers.
        return _convert_inline_md_to_html(body_md)

    blocks = body_md.split("\n\n")
    for i, block in enumerate(blocks):
        stripped = block.strip()
        if not stripped:
            continue
        if stripped.startswith(("# ", "## ", "### ", "{{<", "<p class", "```", ">")):
            continue
        # Convert inline markdown inside the lead block because Hugo
        # does not process markdown inside raw HTML elements.
        stripped = _convert_inline_md_to_html(stripped)
        blocks[i] = f'<p class="lead">\n{stripped}\n</p>'
        break
    return "\n\n".join(blocks)


def _apply_figure_shortcode(body_md: str) -> str:
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
                escaped_caption = caption.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
                result.append(f'<figure><img src="{url}" alt="{alt}" /><figcaption>{escaped_caption}</figcaption></figure>')
                i += 1
                continue
        result.append(line)
        i += 1
    return "\n".join(result)


def _apply_gallery_shortcode(body_md: str) -> str:
    """Wrap 2+ consecutive <figure> blocks in <div class=\"gallery\">"""
    if "<figure>" not in body_md:
        return body_md
    lines = body_md.split("\n")
    result = []
    i = 0
    while i < len(lines):
        if lines[i].strip().startswith("<figure>"):
            fig_lines = [lines[i]]
            i += 1
            while i < len(lines) and lines[i].strip().startswith("<figure>"):
                fig_lines.append(lines[i])
                i += 1
            if len(fig_lines) >= 2:
                result.append('<div class="gallery">')
                result.extend(fig_lines)
                result.append('</div>')
            else:
                result.extend(fig_lines)
            continue
        result.append(lines[i])
        i += 1
    return "\n".join(result)


def _apply_accordion_shortcode(body_md: str) -> str:
    """Wrap certain H2 sections (체크포인트, 준비사항) in {{< accordion >}}"""
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
                result.append('</details>')
                result.extend(buf)
                result.append('')
                buf = []
                in_collapse = False
            should_collapse = any(p in stripped for p in collapse_patterns)
            if should_collapse:
                label = stripped.lstrip("#").strip()
                in_collapse = True
                result.append(f'<details><summary>{label}</summary>')
                result.append('')
                i += 1
                continue
        if in_collapse:
            buf.append(line)
        else:
            result.append(line)
        i += 1
    if in_collapse:
        result.append('</details>')
        result.extend(buf)
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
    """간단한 front matter 문법 검증"""
    if not fm_text or "---" not in fm_text:
        return False, "no front matter"
    try:
        import yaml
        parts = fm_text.split("---")
        if len(parts) < 2:
            return False, "invalid yaml"
        yaml.safe_load(parts[1])
        return True, ""
    except Exception as e:
        return False, str(e)


def sanitize_featureimage_url(url, max_len=255):
    if not url:
        return ""
    if len(url) > max_len:
        logger.warning(f"[featureimage] URL이 {len(url)}자로 {max_len}자 초과")
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
        return _m.group(1).strip()[:200]
    clean = re.sub(r"<[^>]+>", "", body_md or "")
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean[:200]


def _build_schema_json(cfg, title, slug, body_md, category, tags):
    schema_type = "Article"
    if category in ("맛집", "식당"):
        schema_type = "LocalBusiness"
    elif category in ("관광", "여행"):
        schema_type = "Article"
    elif category == "캠핑":
        schema_type = "Campground"

    domain = cfg.get("domain", "")
    url = f"https://{domain}/posts/{slug}/" if domain else ""

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


def _write_hugo_post(blog_cfg, title, body_md, slug, category, tags, thumbnail_url, is_draft=False):
    if not slug or not str(slug).strip():
        logger.error(f"[PUBLISH] slug가 비어있어 발행 중단: title={title}")
        return {"success": False, "error": "empty slug"}

    theme = blog_cfg.get("theme", "PaperMod")
    site_path = blog_cfg.get("site_path", "")
    if not site_path:
        site_path = os.path.join(os.path.dirname(FIVEK_ROOT), blog_cfg.get("repo", ""))
    body_md = _clean_body(body_md)
    description = _extract_description(body_md)

    if not thumbnail_url:
        thumbnail_url = _extract_first_image(body_md)
    thumbnail_url = sanitize_featureimage_url(thumbnail_url, max_len=250)
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
    schema_json = _build_schema_json(blog_cfg, title, slug, body_md, category, tags)
    body_md = body_md + "\n\n" + schema_json
    content = fm + body_md

    _ok, _err = _validate_frontmatter(fm)
    if not _ok:
        logger.warning(f"[PUBLISH] Invalid front matter: {_err}")

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    logger.info(f"[PUBLISH] Hugo post written: {file_path}")
    return {"success": True, "file": file_path}

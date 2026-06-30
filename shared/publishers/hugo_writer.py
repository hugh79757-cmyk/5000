import logging
import os
import re
from datetime import datetime
from pathlib import Path

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
    elif "stock" in blog_id:
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
    fm += "date: " + date_str + "\n"
    fm += "draft: " + str(is_draft).lower() + "\n"
    if description:
        fm += 'description: "' + _sanitize_yaml_value(description, max_len=200) + '"\n'
    fm += 'slug: "' + slug + '"\n'
    if category:
        fm += "categories: " + str([category]) + "\n"
    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        fm += "tags: " + str(tag_list) + "\n"
    if thumbnail_url:
        fm += "cover:\n"
        fm += '  image: "' + thumbnail_url + '"\n'
    elif "stock" in blog_id:
        fm += 'cover:\n  image: "https://pub-2f5c7af1c303419a933069212bc25874.r2.dev/common/stock-default-thumbnail.webp"\n'
    else:
        fm += 'cover:\n  image: "https://pub-2f5c7af1c303419a933069212bc25874.r2.dev/common/default-thumbnail.webp"\n'
    fm += "---\n"
    return fm, date_str


def _clean_body(body_md):
    """Clean body markdown from various artifacts"""
    if not body_md:
        return body_md
    body_md = re.sub(r"</?[^>]+>", "", body_md)
    body_md = re.sub(r"\n{3,}", "\n\n", body_md)
    return body_md.strip()


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
    clean = re.sub(r"<[^>]+>", "", body_md or "")
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean[:200]


def _write_hugo_post(blog_cfg, title, body_md, slug, category, tags, thumbnail_url, is_draft=False):
    if not slug or not str(slug).strip():
        logger.error(f"[PUBLISH] slug가 비어있어 발행 중단: title={title}")
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
        fm, _date_str = _build_frontmatter_papermod(title, slug, category, tags, thumbnail_url, description, is_draft=is_draft)
        date_prefix = datetime.now().strftime("%Y-%m-%d")
        post_dir = os.path.join(site_path, "content", "posts")
        os.makedirs(post_dir, exist_ok=True)
        file_path = os.path.join(post_dir, date_prefix + "-" + slug + ".md")

    body_md = re.sub(r"<!-- DESC:.*?-->", "", body_md).strip()
    content = fm + body_md

    _ok, _err = _validate_frontmatter(fm)
    if not _ok:
        logger.warning(f"[PUBLISH] Invalid front matter: {_err}")

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    logger.info(f"[PUBLISH] Hugo post written: {file_path}")
    return {"success": True, "file": file_path}

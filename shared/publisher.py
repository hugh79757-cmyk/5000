import os
import sqlite3
import re
import yaml
import subprocess
from datetime import datetime
from pathlib import Path
from shared.content_store import insert_article, update_published, get_today_count

CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")


def load_blogs():
    with open(os.path.join(CONFIG_DIR, "blogs.yaml"), "r", encoding="utf-8") as f:
        return yaml.safe_load(f)["blogs"]


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


def _extract_first_image(body_md):
    m = re.search(r'!\[.*?\]\((https?://[^)]+)\)', body_md)
    if not m:
        return ""
    url = m.group(1)
    if "tong.visitkorea.or.kr" in url and url.startswith("http://"):
        url = url.replace("http://", "https://", 1)
    return url


def _extract_description(body_md):
    for line in body_md.split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("#") or line.startswith(">") or line.startswith("!") or line.startswith("---") or line.startswith("<!--") or line.startswith("|"):
            continue
        clean = re.sub(r'\*\*|\[([^\]]+)\]\([^)]+\)', r'\1', line)
        if len(clean) > 30:
            return clean[:150]
    return ""


def _build_frontmatter_papermod(title, slug, category, tags, thumbnail_url, description):
    date_str = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00")
    fm = "---\n"
    fm += 'title: "' + title.replace('"', '\\"') + '"\n'
    fm += "date: '" + date_str + "'\n"
    fm += "slug: '" + slug + "'\n"
    fm += "draft: false\n"
    if description:
        fm += 'description: "' + description.replace('"', '\\"') + '"\n'
    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        fm += "tags: " + str(tag_list) + "\n"
    if category:
        fm += "categories: ['" + category + "']\n"
    if thumbnail_url:
        fm += "cover:\n"
        fm += '  image: "' + thumbnail_url + '"\n'
        fm += '  alt: "' + title.replace('"', '\\"') + '"\n'
        fm += "  hidden: false\n"
    fm += "---\n\n"
    return fm, date_str


def _build_frontmatter_blowfish(title, slug, category, tags, thumbnail_url, description):
    date_str = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00")
    fm = "---\n"
    fm += 'title: "' + title.replace('"', '\\"') + '"\n'
    fm += "slug: '" + slug + "'\n"
    fm += "date: '" + date_str + "'\n"
    fm += "draft: false\n"
    if description:
        fm += 'description: "' + description.replace('"', '\\"') + '"\n'
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
        fm += 'featureimage: "https://pub-2f5c7af1c303419a933069212bc25874.r2.dev/common/default-thumbnail.webp"\n'
    fm += "---\n\n"
    return fm, date_str



def _get_related_posts(blog_id, current_slug, max_count=3):
    """같은 블로그의 최근 발행 글에서 관련 글 추출"""
    try:
        db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "content.db")
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


def _write_hugo_post(blog_cfg, title, body_md, slug, category, tags, thumbnail_url):
    theme = blog_cfg.get("theme", "PaperMod")
    site_path = blog_cfg.get("site_path", "")
    if not site_path:
        site_path = os.path.join("/Users/twinssn/Projects", blog_cfg.get("repo", ""))
    description = _extract_description(body_md)

    if not thumbnail_url:
        thumbnail_url = _extract_first_image(body_md)
    if thumbnail_url and thumbnail_url.startswith("http://tong.visitkorea.or.kr"):
        thumbnail_url = thumbnail_url.replace("http://", "https://", 1)

    if theme == "Blowfish":
        fm, date_str = _build_frontmatter_blowfish(title, slug, category, tags, thumbnail_url, description)
        post_dir = os.path.join(site_path, "content", "posts", slug)
        os.makedirs(post_dir, exist_ok=True)
        file_path = os.path.join(post_dir, "index.md")
    else:
        fm, date_str = _build_frontmatter_papermod(title, slug, category, tags, thumbnail_url, description)
        date_prefix = datetime.now().strftime("%Y-%m-%d")
        post_dir = os.path.join(site_path, "content", "posts")
        os.makedirs(post_dir, exist_ok=True)
        file_path = os.path.join(post_dir, date_prefix + "-" + slug + ".md")

    # 내부 링크 삽입
    blog_id_for_links = blog_cfg.get("id", "")
    related = _get_related_posts(blog_id_for_links, slug)
    if related:
        links_md = "\n\n## 함께 읽어보기\n\n"
        for rp in related:
            links_md += "- [" + rp["title"] + "](/posts/" + rp["slug"] + "/)\n"
        body_md = body_md.rstrip() + links_md

    content = fm + body_md
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    expected_url = "https://" + blog_cfg.get("domain", "") + "/posts/" + slug + "/"
    return {"success": True, "url": expected_url, "file_path": file_path}


def deploy_site(site_path, cf_project):
    site = Path(site_path)
    result = subprocess.run(["/opt/homebrew/bin/hugo", "--gc", "--minify"], cwd=str(site), capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception("Hugo build failed: " + result.stderr[:500])
    result = subprocess.run(
        ["/opt/homebrew/bin/wrangler", "pages", "deploy", "./public",
         "--project-name=" + cf_project, "--branch=main", "--commit-dirty=true"],
        cwd=str(site), capture_output=True, text=True
    )
    if result.returncode != 0:
        raise Exception("Wrangler deploy failed: " + result.stderr[:500])
    public_dir = site / "public"
    if public_dir.exists():
        subprocess.run(["rm", "-rf", str(public_dir)])
    return True


def publish(blog_id, title, body_md, body_html=None,
            category="", tags="", thumbnail_url="",
            data_source="", source_id="", prompt_id="",
            model=""):

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
        "published_url": "",
        "published_at": "",
    }
    article_id = insert_article(article)

    result = _write_hugo_post(blog_cfg, title, body_md, slug, category, tags, thumbnail_url)

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

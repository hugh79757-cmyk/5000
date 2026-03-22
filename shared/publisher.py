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

def _build_frontmatter_congo(title, slug, category, tags, thumbnail_url, description):
    date_str = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00")
    fm = "---\n"
    fm += 'title: "' + title.replace('"', '\\"') + '"\n'
    fm += "date: " + date_str + "\n"
    fm += "draft: false\n"
    if description:
        fm += 'description: "' + description[:200].replace('"', '\\"') + '"\n'
    fm += 'slug: "' + slug + '"\n'
    if category:
        fm += 'categories: ["' + category + '"]\n'
    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        fm += "tags: [" + ", ".join('"' + t + '"' for t in tag_list) + "]\n"
    if thumbnail_url:
        fm += 'image: "' + thumbnail_url + '"\n'
    else:
        fm += 'image: "https://pub-2f5c7af1c303419a933069212bc25874.r2.dev/common/default-thumbnail.webp"\n'
    fm += "---\n"
    return fm, date_str

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

    if theme.lower() == "blowfish":
        fm, date_str = _build_frontmatter_blowfish(title, slug, category, tags, thumbnail_url, description)
        post_dir = os.path.join(site_path, "content", "posts", slug)
        os.makedirs(post_dir, exist_ok=True)
        file_path = os.path.join(post_dir, "index.md")
    elif theme.lower() == "congo":
        fm, date_str = _build_frontmatter_congo(title, slug, category, tags, thumbnail_url, description)
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
    _skip_links = blog_id_for_links in ("stock-hugo",)
    related = [] if _skip_links else _get_related_posts(blog_id_for_links, slug)
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


def publish(blog_id, title, body_md, body_html=None, segment="", fuel_type="",
            category="", tags="", thumbnail_url="",
            data_source="", source_id="", prompt_id="",
            model="", wp_category=None):

    # 후처리: AI가 생성한 가짜 내부링크 제거
    import re
    if body_md:
        body_md = re.sub(r"\n+##\s*(함께|관련|추천)\s*(읽어보기|읽을거리|글|포스트).*", "", body_md, flags=re.DOTALL)
        body_md = body_md.rstrip()

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

    platform = blog_cfg.get("platform", "hugo")

    if platform == "blogger":
        import os
        from dotenv import load_dotenv as _ldenv
        _ldenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"), override=True)
        from shared.blogger_publisher import publish_to_blogger
        blog_id_env = blog_cfg.get("blog_id_env", "")
        blogger_blog_id = os.getenv(blog_id_env, "")
        if not blogger_blog_id:
            return {"success": False, "error": "blogger blog_id not configured"}
        labels = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
        html_content = body_html or body_md
        # markdown -> HTML 변환 (Blogger는 HTML 필요)
        if not body_html and body_md:
            import markdown
            html_content = markdown.markdown(body_md, extensions=['tables', 'fenced_code'])
        result = publish_to_blogger(blogger_blog_id, title, html_content, labels)

    elif platform == "wordpress":
        import os
        from dotenv import load_dotenv as _ldenv2
        _ldenv2(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"), override=True)
        from shared.wp_publisher import publish_to_wordpress
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


    else:
        # ── 쿠팡 파트너스 링크 삽입 (CAR만) ──
        if data_source == "car_db":
            try:
                from shared.coupang_car import CoupangCar
                coupang = CoupangCar()
                if coupang.is_configured():
                    coupang_md = coupang.get_car_product_links(segment=segment, fuel_type=fuel_type, count=2)
                    if coupang_md:
                        body_md = body_md.rstrip() + coupang_md
                        logger.info("쿠팡 링크 삽입 완료")
            except Exception as e:
                logger.warning(f"쿠팡 링크 삽입 실패: {e}")

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

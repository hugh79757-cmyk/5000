"""ETAP pipeline — 영문 travel 블로그 자동 발행."""
import logging
import os
import logging
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from pipelines.etap.topic_manager import pick_topic, mark_published, check_exhaustion, send_telegram
from pipelines.etap.writer import generate_city_guide
from pipelines.etap.quality_guard import postprocess_content, send_alert, make_draft
from pipelines.etap.image_fetcher import fetch_city_image, fetch_body_images
from pipelines.etap.post_processor import insert_adsense
from shared.entity_linker import inject_internal_links, register_entity, mark_entity_published



def _insert_body_images(content, images):
    """H2 헤딩 뒤에 본문 이미지 삽입 (최대 3장)"""
    if not images:
        return content
    lines = content.split("\n")
    h2_indices = [i for i, line in enumerate(lines) if line.startswith("## ")]
    # 2번째, 3번째, 4번째 H2 뒤에 삽입
    insert_after = h2_indices[1:4] if len(h2_indices) > 1 else h2_indices
    inserted = 0
    offset = 0
    for idx in insert_after:
        if inserted >= len(images):
            break
        img = images[inserted]
        img_md = f"\n![Photo]({img['url']})\n*{img['credit']}*\n"
        pos = idx + offset + 2  # H2 다음 줄 + 한 줄 여유
        if pos > len(lines):
            pos = len(lines)
        lines.insert(pos, img_md)
        offset += 1
        inserted += 1
    return "\n".join(lines)

def _write_hugo_post(cfg: dict, article: dict) -> str:
    """Hugo 마크다운 파일 생성. 발행된 파일 경로 반환."""
    site_path = Path(cfg["site_path"])
    slug = article["slug"]
    post_dir = site_path / "content" / "posts" / slug
    post_dir.mkdir(parents=True, exist_ok=True)

    tags_str = "\n".join(f'  - "{t}"' for t in article["tags"])

    image_block = ""
    credit_line = ""
    if article.get("image"):
        img_url = article["image"]["url"]
        image_block = f'\nfeatureimage: "{img_url}"\n'
        if article["image"].get("credit"):
            credit_line = article["image"]["credit"] + "\n\n"

    draft_line = "draft: true\n" if article.get("_draft") else ""
    frontmatter = f"""---
title: "{article['title']}"
date: {datetime.now().astimezone().isoformat(timespec='seconds')}
description: "{article['description']}"
{image_block}tags:
{tags_str}
categories:
  - "Travel Guide"
showTableOfContents: true
{draft_line}---

{credit_line}"""
    filepath = post_dir / "index.md"
    final_content = article["content"]
    if article.get("body_images"):
        final_content = _insert_body_images(final_content, article["body_images"])
    filepath.write_text(frontmatter + final_content, encoding="utf-8")
    return str(filepath)


def _build_and_deploy(cfg: dict) -> bool:
    """Hugo 빌드 + Wrangler 배포."""
    import subprocess
    site_path = cfg["site_path"]
    cf_project = cfg["cf_project"]

    build = subprocess.run(
        ["/opt/homebrew/bin/hugo", "--gc", "--minify"],
        cwd=site_path, capture_output=True, text=True, timeout=120
    )
    if build.returncode != 0:
        print(f"[ETAP] Hugo build failed: {build.stderr}")
        return False

    deploy = subprocess.run(
        ["/opt/homebrew/bin/wrangler", "pages", "deploy", "public", "--project-name", cf_project],
        cwd=site_path, capture_output=True, text=True, timeout=120
    )
    if deploy.returncode != 0:
        print(f"[ETAP] Wrangler deploy failed: {deploy.stderr}")
        return False

    print(f"[ETAP] Deployed to {cfg['domain']}")
    return True


def run(cfg: dict) -> dict:
    """dispatcher에서 호출하는 메인 함수."""
    blog_id = cfg["id"]


    # 고갈 체크
    can_pub, remaining = check_exhaustion("topics", blog_id)
    if not can_pub:
        return {"status": "exhausted", "remaining": 0}

    topic = pick_topic(blog_id)
    if not topic:
        print(f"[ETAP] {blog_id}: 발행 가능한 토픽 없음")
        return {"status": "skip", "reason": "no_topic"}

    print(f"[ETAP] {blog_id}: {topic['city']}, {topic['country']} 글 생성 시작")

    article = generate_city_guide(topic)

    # Quality guard
    article["content"], post_issues, is_draft = postprocess_content(
        article["content"], data_prices=None, blog_id=blog_id, slug=article["slug"])
    if is_draft:
        logger.warning(f"[ETAP] {blog_id} DRAFT: {article['slug']} - {post_issues}")
        send_alert(blog_id, article["slug"], post_issues)
        article["_draft"] = True
    elif post_issues:
        logger.info(f"[ETAP] {blog_id} quality: {post_issues}")

    image = fetch_city_image(topic["city"], topic["country"], article["slug"])
    if image:
        article["image"] = image
    body_imgs = fetch_body_images(topic.get("city", ""), topic.get("country", ""), article["slug"], count=3)
    if body_imgs:
        article["body_images"] = body_imgs
    filepath = _write_hugo_post(cfg, article)
    print(f"[ETAP] 파일 생성: {filepath}")

    deployed = _build_and_deploy(cfg)

    mark_published(
        topic_id=topic["topic_id"],
        blog_id=blog_id,
        title=article["title"],
        slug=article["slug"],
        url=f"https://{cfg['domain']}/posts/{article['slug']}/" if deployed else ""
    )

    return {
        "status": "ok" if deployed else "build_fail",
        "title": article["title"],
        "slug": article["slug"],
        "city": article["city"],
    }



def run_batch(cfg: dict, count: int = 3) -> list:
    from pipelines.etap.topic_manager import check_daily_quota
    blog_id = cfg["id"]
    can_pub, today_count = check_daily_quota(blog_id, max_per_day=cfg.get("daily_quota", 5))
    if not can_pub:
        print(f"[ETAP] {blog_id}: daily quota reached ({today_count})")
        return []
    count = min(count, cfg.get("daily_quota", 5) - today_count)
    """count건 연속 발행 후 마지막에 1회 빌드+배포."""
    import time
    blog_id = cfg["id"]
    results = []

    for i in range(count):
        topic = pick_topic(blog_id)
        if not topic:
            print(f"[ETAP] {blog_id}: 토픽 소진 (발행 {i}건 후 중단)")
            break

        print(f"[ETAP] {blog_id}: [{i+1}/{count}] {topic['city']}, {topic['country']}")

        article = generate_city_guide(topic)

        # Quality guard
        article["content"], post_issues, is_draft = postprocess_content(
            article["content"], data_prices=None, blog_id=blog_id, slug=article["slug"])
        if is_draft:
            logger.warning(f"[ETAP] {blog_id} DRAFT: {article['slug']} - {post_issues}")
            send_alert(blog_id, article["slug"], post_issues)
            article["_draft"] = True
        elif post_issues:
            logger.info(f"[ETAP] {blog_id} quality: {post_issues}")

        image = fetch_city_image(topic["city"], topic["country"], article["slug"])
        if image:
            article["image"] = image
        # 본문 이미지 삽입
        body_imgs = fetch_body_images(topic.get("city", ""), topic.get("country", ""), article["slug"], count=3)
        if body_imgs:
            article["body_images"] = body_imgs
        article["content"] = insert_adsense(article["content"])
        article["content"] = inject_internal_links(article["content"], current_blog=blog_id, max_links=5)
        register_entity("city", topic["city"], blog_id, article["slug"],
                        f'https://{cfg["domain"]}/posts/{article["slug"]}/',
                        topic["city"], priority=70)
        _write_hugo_post(cfg, article)

        mark_published(
            topic_id=topic["topic_id"],
            blog_id=blog_id,
            title=article["title"],
            slug=article["slug"],
            url=""
        )
        mark_entity_published(blog_id, article["slug"])
        results.append({"title": article["title"], "city": article["city"]})

        if i < count - 1:
            time.sleep(5)

    if results:
        deployed = _build_and_deploy(cfg)
        if deployed:
            print(f"[ETAP] {blog_id}: {len(results)}건 발행 + 배포 완료")
        else:
            print(f"[ETAP] {blog_id}: {len(results)}건 발행, 배포 실패")

    return results

if __name__ == "__main__":
    test_cfg = {
        "id": "tour-hugo",
        "domain": "tour.techpawz.com",
        "site_path": "/Users/twinssn/Projects/ETAP/tour-hugo",
        "cf_project": "tour-hugo",
    }
    result = run(test_cfg)
    print(result)


# ─── dispatcher 경유 진입점 ───────────────────────────────────────────────────
_BLOG_PIPELINE_MAP = {
    "tour-hugo":        ("pipelines.etap.pipeline",            "run_batch"),
    "airlines-hugo":    ("pipelines.etap.airlines_pipeline",   "run_batch"),
    "airports-hugo":    ("pipelines.etap.airports_pipeline",   "run_batch"),
    "esim-hugo":        ("pipelines.etap.esim_pipeline",       "run_batch"),
    "flights-hugo":     ("pipelines.etap.flight_pipeline",     "run_batch"),
    "michelin-hugo":    ("pipelines.etap.michelin_pipeline",   "run_batch"),
    "tours-hugo":       ("pipelines.etap.tours_pipeline",      "run_batch"),
    "trains-hugo":      ("pipelines.etap.trains_pipeline",     "run_batch"),
    "visa-hugo":        ("pipelines.etap.visa_pipeline",       "run_batch"),
    "bus-hugo":         ("pipelines.etap.bus_pipeline",        "run_batch"),
    "ferry-hugo":       ("pipelines.etap.ferry_pipeline",      "run_batch"),
    "dining-hugo":      ("pipelines.etap.dining_pipeline",     "run_batch"),
    "culture-hugo":     ("pipelines.etap.culture_pipeline",    "run_batch"),
    "transfers-hugo":   ("pipelines.etap.transfers_pipeline",  "run_batch"),
    "multiday-hugo":    ("pipelines.etap.multiday_pipeline",   "run_batch"),
    "nature-hugo":      ("pipelines.etap.nature_pipeline",     "run_batch"),
    "visafree-hugo":    ("pipelines.etap.visafree_pipeline",   "run_batch"),
    "deals-hugo":       ("pipelines.etap.deals_pipeline",      "run_batch"),
    "eurail-hugo":      ("pipelines.etap.eurail_pipeline",     "run_batch"),
    "cruise-hugo":      ("pipelines.etap.cruise_pipeline",     "run_batch"),
    "phototour-hugo":   ("pipelines.etap.phototour_pipeline",  "run_batch"),
    "daytrips-hugo":    ("pipelines.etap.daytrips_pipeline",   "run_batch"),
    "walking-hugo":     ("pipelines.etap.walking_pipeline",    "run_batch"),
    "foodtour-hugo":    ("pipelines.etap.foodtour_pipeline",   "run_batch"),
    "adventure-hugo":   ("pipelines.etap.adventure_pipeline",  "run_batch"),
    "watersports-hugo": ("pipelines.etap.watersports_pipeline","run_batch"),
}


# ─── 블로그별 콘텐츠 검증 가드 ───
# 발행 전 slug/title/category가 블로그 성격에 맞는지 검증
_BLOG_CONTENT_RULES = {
    "esim-hugo":      {"slug_must": [], "title_keywords": ["esim", "sim", "data plan", "mobile", "connected"], "category": "eSIM Guide", "min_keyword_hits": 1},
    "airlines-hugo":  {"slug_must": [], "title_keywords": ["airline", "airways", "air line", "review"], "category": "Airline Review", "min_keyword_hits": 1},
    "airports-hugo":  {"slug_must": [], "title_keywords": ["airport", "terminal", "lounge"], "category": "Airport Guide", "min_keyword_hits": 1},
    "flights-hugo":   {"slug_must": [], "title_keywords": ["flight", "fly", "route", "cheap flight", "fare"], "category": "Flight Guide", "min_keyword_hits": 1},
    "michelin-hugo":  {"slug_must": [], "title_keywords": ["michelin", "restaurant", "dining", "food", "star"], "category": "Michelin Guide", "min_keyword_hits": 1},
    "visa-hugo":      {"slug_must": [], "title_keywords": ["visa", "entry", "requirement", "passport", "immigration"], "category": "Visa Guide", "min_keyword_hits": 1},
    "trains-hugo":    {"slug_must": [], "title_keywords": ["train", "rail", "railway", "station"], "category": "Train Guide", "min_keyword_hits": 1},
    "tours-hugo":     {"slug_must": [], "title_keywords": ["tour", "guided", "excursion", "activity"], "category": "Tour Guide", "min_keyword_hits": 1},
    "deals-hugo":     {"slug_must": [], "title_keywords": ["deal", "cheap", "budget", "price", "fare"], "category": "Flight Deals", "min_keyword_hits": 1},
    "cruise-hugo":    {"slug_must": [], "title_keywords": ["cruise", "ship", "sailing", "port", "cabin"], "category": "Cruise Guide", "min_keyword_hits": 1},
    "bus-hugo":       {"slug_must": [], "title_keywords": ["bus", "coach", "intercity"], "category": "Bus Guide", "min_keyword_hits": 1},
    "ferry-hugo":     {"slug_must": [], "title_keywords": ["ferry", "boat", "crossing", "port"], "category": "Ferry Guide", "min_keyword_hits": 1},
    "eurail-hugo":    {"slug_must": [], "title_keywords": ["eurail", "rail pass", "train pass", "europe train"], "category": "Eurail Guide", "min_keyword_hits": 1},
    "dining-hugo":    {"slug_must": [], "title_keywords": ["restaurant", "food", "dining", "eat", "cuisine", "dish"], "category": "Dining Guide", "min_keyword_hits": 1},
    "adventure-hugo": {"slug_must": [], "title_keywords": ["adventure", "hiking", "trek", "outdoor", "climb"], "category": "Adventure Guide", "min_keyword_hits": 1},
    "walking-hugo":   {"slug_must": [], "title_keywords": ["walking", "walk", "stroll", "foot", "pedestrian"], "category": "Walking Guide", "min_keyword_hits": 1},
    "foodtour-hugo":  {"slug_must": [], "title_keywords": ["food tour", "food walk", "street food", "tasting", "culinary tour"], "category": "Food Tour Guide", "min_keyword_hits": 1},
    "watersports-hugo": {"slug_must": [], "title_keywords": ["surf", "dive", "snorkel", "kayak", "water sport", "beach"], "category": "Water Sports Guide", "min_keyword_hits": 1},
    "phototour-hugo": {"slug_must": [], "title_keywords": ["photo", "photography", "camera", "instagram", "scenic"], "category": "Photo Tour Guide", "min_keyword_hits": 1},
    "daytrips-hugo":  {"slug_must": [], "title_keywords": ["day trip", "daytrip", "excursion", "half day", "nearby"], "category": "Day Trip Guide", "min_keyword_hits": 1},
    "multiday-hugo":  {"slug_must": [], "title_keywords": ["multi-day", "multiday", "itinerary", "multi day", "package tour"], "category": "Multi-Day Guide", "min_keyword_hits": 1},
    "nature-hugo":    {"slug_must": [], "title_keywords": ["nature", "park", "wildlife", "landscape", "forest", "mountain"], "category": "Nature Guide", "min_keyword_hits": 1},
    "culture-hugo":   {"slug_must": [], "title_keywords": ["culture", "museum", "heritage", "art", "history", "tradition"], "category": "Culture Guide", "min_keyword_hits": 1},
    "transfers-hugo": {"slug_must": [], "title_keywords": ["transfer", "shuttle", "airport transfer", "taxi", "transport"], "category": "Transfer Guide", "min_keyword_hits": 1},
    "visafree-hugo":  {"slug_must": [], "title_keywords": ["visa-free", "visa free", "no visa", "exempt", "waiver"], "category": "Visa-Free Guide", "min_keyword_hits": 1},
    "tour-hugo":      {"slug_must": [], "title_keywords": [], "category": "Travel Guide", "min_keyword_hits": 0},
}
def run(cfg: dict) -> dict:
    import importlib
    from pipelines.etap.topic_manager import check_daily_quota
    blog_id = cfg.get("id", "")
    max_daily = cfg.get("daily_quota", 5)

    # 일일 quota 강제
    can_pub, today_count = check_daily_quota(blog_id, max_per_day=max_daily)
    if not can_pub:
        logger.info(f"[ETAP] {blog_id}: daily quota reached ({today_count}/{max_daily})")
        return {"success": False, "reason": "daily_quota_reached", "today": today_count}

    remaining = max_daily - today_count
    count = min(cfg.get("count", 1), remaining)
    if count <= 0:
        return {"success": False, "reason": "daily_quota_reached"}

    entry = _BLOG_PIPELINE_MAP.get(blog_id)
    if not entry:
        logger.error(f"[ETAP] 알 수 없는 blog_id: {blog_id}")
        return {"success": False, "reason": "unknown_blog_id"}

    module_path, func_name = entry
    try:
        mod = importlib.import_module(module_path)
        fn  = getattr(mod, func_name)
        if blog_id == "tour-hugo":
            result = fn(cfg, count=count)
        else:
            result = fn(count=count)
        ok = result if isinstance(result, int) else (1 if result else 0)
        return {"success": ok > 0, "published": ok}
    except Exception as e:
        logger.error(f"[ETAP] {blog_id} 실패: {e}")
        return {"success": False, "reason": str(e)}

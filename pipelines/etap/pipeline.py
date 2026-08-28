"""ETAP pipeline — 영문 travel 블로그 자동 발행."""
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST = timezone(timedelta(hours=9))
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

import re  # viator

from pipelines.etap.image_fetcher import fetch_body_images, fetch_city_image
from pipelines.etap.post_processor import (
    insert_adsense,
    insert_cross_sell_block,
    insert_product_cards,
)
from pipelines.etap.quality_guard import postprocess_content, send_alert
from pipelines.etap.topic_manager import check_exhaustion, mark_published, pick_topic
from pipelines.etap.writer import generate_city_guide
from shared.entity_linker import (
    build_cross_sell_html,
    inject_internal_links,
    mark_entity_published,
    register_entity,
)


def _get_viator_products(city: str, limit: int = 5, blog_id: str = "") -> list:
    """viator_tours 테이블에서 해당 도시 투어 상품 조회 + 어필리에이트 파라미터 추가."""
    import sqlite3
    from pathlib import Path
    db_path = Path(__file__).parent.parent.parent / "data" / "travel-en.db"
    pid  = os.getenv("VIATOR_PID", "")
    mcid = os.getenv("VIATOR_MCID", "42383")   # Viator 기본 MCID
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT product_name, price, currency, discount_percent,
                      image_url, deep_link, category
               FROM viator_tours
               WHERE lower(city) = lower(?)
                 AND deep_link IS NOT NULL
               ORDER BY discount_percent DESC, price ASC
               LIMIT ?""",
            (city, limit)
        ).fetchall()
        conn.close()
    except Exception:
        return []

    products = []
    for r in rows:
        link = r["deep_link"] or ""
        # 어필리에이트 파라미터 추가
        if pid and "pid=" not in link:
            sep = "&" if "?" in link else "?"
            link = f"{link}{sep}pid={pid}&mcid={mcid}&medium=link&campaign={blog_id}"
        # "Save XX%! " 접두사 제거
        name = re.sub(r"^Save [\d.]+%!\s*", "", r["product_name"] or "")
        products.append({
            "name":     name,
            "price":    r["price"],
            "currency": r["currency"] or "USD",
            "discount": r["discount_percent"],
            "image_url": r["image_url"] or "",
            "link":     link,
            "category": r["category"] or "",
        })
    return products


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
        pos = min(pos, len(lines))
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
        from shared.publisher import sanitize_featureimage_url
        img_url = sanitize_featureimage_url(article["image"]["url"])
        credit = article["image"].get("credit", "")
        if img_url:
            if credit:
                image_block = f'\nfeatureimage: "{img_url}"\nfeatureimagecaption: "{credit}"\n'
            else:
                image_block = f'\nfeatureimage: "{img_url}"\n'

    draft_line = "draft: true\n" if article.get("_draft") else ""
    frontmatter = f"""---
title: "{article['title']}"
date: {datetime.now().astimezone().isoformat(timespec='seconds')}
description: "{article['description']}"
{image_block}tags:
{tags_str}
categories:
  - "Travel Guide"
showTableOfContents: false
{draft_line}---

{credit_line}"""
    filepath = post_dir / "index.md"
    final_content = article["content"]
    if article.get("body_images"):
        final_content = _insert_body_images(final_content, article["body_images"])
    filepath.write_text(frontmatter + final_content, encoding="utf-8")
    return str(filepath)


def _build_and_deploy(cfg: dict) -> bool:
    """Hugo 빌드 + Wrangler 배포 — shared/publishers/deploy.py 위임 (정규 경로).

    ETAP fallback(tour-hugo 등 base 폴백)용. 직접 wrangler 호출 대신
    deploy_site()가 build_wrangler_env()(CLOUDFLARE_API_TOKEN 제거),
    HUGO_THEMESDIR, 직렬화 락, 재시도를 모두 처리한다.
    """
    try:
        from shared.publishers.deploy import deploy_site
    except Exception as e:
        print(f"[ETAP] deploy import failed: {e}")
        return False
    site_path = cfg["site_path"]
    cf_project = cfg.get("cf_project") or cfg.get("repo") or cfg["id"]
    try:
        # deploy_site가 HUGO_THEMESDIR / env 정리 / 락 / 빌드+배포 전부 담당
        ok = deploy_site(site_path, cf_project, deploy_type=cfg.get("deploy_type"))
        if ok:
            print(f"[ETAP] Deployed to {cfg['domain']}")
        return bool(ok)
    except Exception as e:
        print(f"[ETAP] Deploy failed: {e}")
        return False


def _get_esim_product(country: str) -> dict:
    """airalo_esim 테이블에서 해당 국가 eSIM 상품 조회."""
    import sqlite3
    from pathlib import Path
    if not country:
        return {}
    db_path = Path(__file__).parent.parent.parent / "data" / "travel-en.db"
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT title, link, price, sale_price, image_link FROM airalo_esim "
            "WHERE title LIKE ? ORDER BY CAST(REPLACE(COALESCE(sale_price,price),'$','') AS REAL) ASC LIMIT 1",
            ("%" + country + "%",)
        ).fetchone()
        conn.close()
        if not row:
            return {}
        p = row["sale_price"] or row["price"]
        return {
            "name": country + " eSIM - " + (row["title"] or ""),
            "price": str(p).replace("$", ""),
            "currency": "$",
            "discount": "",
            "image_url": row["image_link"] or "",
            "link": row["link"],
            "category": "eSIM",
        }
    except Exception:
        return {}


def run(cfg: dict, force_topic_id: int | None = None) -> dict:
    """dispatcher에서 호출하는 메인 함수.

    Args:
        cfg: 블로그 설정 dict (id, site_path, domain, cf_project 등)
        force_topic_id: 지정 topic_id로 강제 발행 (None이면 정상 pick_topic)
    """
    blog_id = cfg["id"]
    topic_table = "topics"  # pipeline.py는 topics 테이블 사용

    # force_topic_id 지정 시 해당 토픽 직접 fetch
    if force_topic_id is not None:
        from pipelines.etap.topic_manager import get_topic_by_id
        topic = get_topic_by_id(topic_table, force_topic_id)
        if not topic:
            print(f"[ETAP] {blog_id}: force_topic_id={force_topic_id} not found")
            return {"status": "skip", "reason": "topic_not_found"}
        print(f"[ETAP] {blog_id}: force_topic_id={force_topic_id} generating "
              f"(city={topic.get('city','')}, country={topic.get('country','')})")
    else:
        # 고갈 체크
        can_pub, _remaining = check_exhaustion(topic_table, blog_id)
        if not can_pub:
            return {"status": "exhausted", "remaining": 0}

        topic = pick_topic(blog_id)
        if not topic:
            print(f"[ETAP] {blog_id}: 발행 가능한 토픽 없음")
            return {"status": "skip", "reason": "no_topic"}

        print(f"[ETAP] {blog_id}: {topic['city']}, {topic['country']} 글 생성 시작")

    article = generate_city_guide(topic)
    article["viator_products"] = _get_viator_products(topic.get("city", ""), blog_id=blog_id)
    # eSIM 카드 추가
    esim = _get_esim_product(topic.get("country", ""))
    if esim:
        article["viator_products"].append(esim)

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



def run_batch(cfg: dict, count: int = 3, force_topic_id: int | None = None) -> list:
    from pipelines.etap.topic_manager import check_daily_quota, get_topic_by_id
    blog_id = cfg["id"]
    topic_table = "topics"
    can_pub, today_count = check_daily_quota(blog_id, max_per_day=cfg.get("daily_quota", 5))
    if not can_pub:
        print(f"[ETAP] {blog_id}: daily quota reached ({today_count})")
        return []
    count = min(count, cfg.get("daily_quota", 5) - today_count)
    """count건 연속 발행 후 마지막에 1회 빌드+배포."""
    import time
    results = []

    for i in range(count):
        if force_topic_id is not None:
            topic = get_topic_by_id(topic_table, force_topic_id)
            if not topic:
                print(f"[ETAP] {blog_id}: force_topic_id={force_topic_id} not found")
                break
            print(f"[ETAP] {blog_id}: [{i+1}/{count}] force_topic_id={force_topic_id} "
                  f"{topic['city']}, {topic['country']}")
        else:
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
        # Viator 상품 카드 삽입
        viator_products = article.get("viator_products", [])
        if viator_products:
            article["content"] = insert_product_cards(article["content"], viator_products)
        cross_html = build_cross_sell_html(
            country=topic.get("country", ""),
            city=topic.get("city", ""),
            exclude_blog=blog_id, max_items=3)
        if cross_html:
            article["content"] = insert_cross_sell_block(article["content"], cross_html, position="bottom")
        article["content"] = inject_internal_links(article["content"], current_blog=blog_id, max_links=5)
        register_entity("city", topic["city"], blog_id, article["slug"],
                        f'https://{cfg["domain"]}/posts/{article["slug"]}/',
                        topic["city"], 70)
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
        # 배포는 dispatcher 중앙 경유(_build_and_deploy_central)가 담당 — 중복 배포 방지.
        # tour-hugo를 포함한 모든 ETAP 블로그는 ETAP_PIPELINE_BLOGS 경유로 단일 배포(fallback 0 블로그).
        print(f"[ETAP] {blog_id}: {len(results)}건 발행 완료 (중앙 배포 경유)")

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
        result = fn(cfg, count=count) if blog_id == "tour-hugo" else fn(count=count)
        ok = result if isinstance(result, int) else (1 if result else 0)
        return {"success": ok > 0, "published": ok}
    except Exception as e:
        logger.exception(f"[ETAP] {blog_id} 실패: {e}")
        return {"success": False, "reason": str(e)}

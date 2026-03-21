import sys
import os
import logging
from shared.telegram_notifier import send_error as _tg_error
import yaml
import random
import sqlite3
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, "/Users/twinssn/Projects/TAP")

from dotenv import load_dotenv
load_dotenv("/Users/twinssn/Projects/TAP/.env")
load_dotenv("/Users/twinssn/Projects/5000/.env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

PROJECT_DIR = Path(__file__).parent
CONFIG_DIR = PROJECT_DIR / "config"
CAR_DB_PATH = PROJECT_DIR / "data" / "car.db"
PROMPTS_DIR = PROJECT_DIR / "prompts"


def load_blogs():
    with open(CONFIG_DIR / "blogs.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)["blogs"]


def get_blog_config(blog_id):
    for b in load_blogs():
        if b["id"] == blog_id:
            return b
    return None


def _select_car_image(conn, car_id, slug):
    try:
        c = conn.cursor()
        used = c.execute(
            "SELECT image_url FROM publish_log WHERE published_at > datetime('now', '-7 days') AND image_url IS NOT NULL AND image_url != ''"
        ).fetchall()
        used_urls = {r['image_url'] for r in used} if used else set()
        images = c.execute(
            "SELECT image_url, source FROM car_images WHERE car_id = ? AND verified != -1 ORDER BY RANDOM()",
            (car_id,)
        ).fetchall()
        selected_url = None
        for img in images:
            if img['image_url'] not in used_urls:
                selected_url = img['image_url']
                break
        if not selected_url and images:
            selected_url = images[0]['image_url']
        if not selected_url:
            # fallback: 같은 모델 기본형 이미지 사용 (hev/25 등 변형 → 기본 모델)
            import re
            base_id = re.sub(r'_(hev|phev|ev|25|35|lpg)(?=_)', '', car_id)
            if base_id != car_id:
                fallback_imgs = c.execute(
                    "SELECT image_url FROM car_images WHERE car_id = ? AND verified != -1 ORDER BY RANDOM()",
                    (base_id,)
                ).fetchall()
                for img in fallback_imgs:
                    if img['image_url'] not in used_urls:
                        selected_url = img['image_url']
                        break
                if not selected_url and fallback_imgs:
                    selected_url = fallback_imgs[0]['image_url']
        if not selected_url:
            return "", ""
        import urllib.request
        from shared.image_handler import process_and_upload
        req = urllib.request.Request(selected_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            image_data = resp.read()
        r2_url = process_and_upload(image_data)
        return r2_url, selected_url
    except Exception as e:
        logger.warning("Image failed: " + str(e))
        return "", ""


def run_car(blog_cfg):
    blog_id = blog_cfg["id"]
    logger.info("CAP pipeline: " + blog_id)

    from pipelines.car.topic_manager import select_topic, generate_title, make_slug, validate_body
    from pipelines.car.data_builder import build_input
    from shared.content_store import init_db, get_today_count

    init_db()
    today_count = get_today_count(blog_id)
    if today_count >= blog_cfg.get("daily_quota", 50):
        logger.info(blog_id + " quota reached: " + str(today_count))
        return None

    conn = sqlite3.connect(str(CAR_DB_PATH))
    conn.row_factory = sqlite3.Row

    MAX_RETRY = 3
    topic = None
    data = None
    skip_ids = []

    for attempt in range(1, MAX_RETRY + 1):
        logger.info("토픽 선택 (시도 " + str(attempt) + "/" + str(MAX_RETRY) + ")")
        car_site_id = blog_id.replace('-hugo', '')
        topic = select_topic(conn, site_id=car_site_id, skip_ids=skip_ids, post_type=blog_cfg.get('post_type'))
        if not topic:
            logger.info(blog_id + " no topics available")
            conn.close()
            return None
        data = build_input(conn, topic, CAR_DB_PATH)
        if data:
            data['site_id'] = blog_id
            break
        skip_ids.append(topic['id'])
        conn.execute("UPDATE topics SET status='skip_no_data' WHERE id=?", (topic['id'],))
        conn.commit()

    if not data:
        conn.close()
        return None

    logger.info(data['model'] + " " + data['trim'] + " (" + str(data['base_price']) + "만원)")

    prompt_file = PROMPTS_DIR / blog_cfg.get("prompt", "")
    if not prompt_file.exists():
        logger.error("Prompt not found: " + str(prompt_file))
        conn.close()
        return None

    prompt_text = prompt_file.read_text(encoding="utf-8")
    from shared.ai_writer import generate_car
    body = generate_car(prompt_text, data)
    if not body:
        logger.error(blog_id + " content generation failed")
        _tg_error(blog_id, "content_generation", "AI 본문 생성 실패")
        conn.close()
        return None

    body = validate_body(body, data)
    title = generate_title(data, site_id=car_site_id)
    slug = make_slug(title)
    logger.info("제목: " + title)

    r2_url, origin_url = _select_car_image(conn, topic['car_id'], slug)
    if r2_url:
        logger.info("R2: " + r2_url)

    tags_list = [data.get("model", ""), data.get("competitor", ""), "잔존가치", "중고시세"]
    tags_str = ",".join([t for t in tags_list if t])

    from shared.publisher import publish
    result = publish(
        blog_id=blog_id,
        title=title,
        body_md=body,
        category="자동차",
        tags=tags_str,
        thumbnail_url=r2_url,
        data_source="car_db",
        source_id=str(topic['car_id']),
        prompt_id=blog_cfg.get("post_type", ""),
        model="gpt-4o-mini",
    )

    c = conn.cursor()
    c.execute(
        "INSERT INTO publish_log (topic_id, site, title, slug, published_at, image_url, r2_url) VALUES (?,?,?,?,?,?,?)",
        (topic['id'], car_site_id, title, slug, datetime.now().isoformat(), origin_url or "", r2_url or "")
    )
    conn.commit()
    conn.close()

    logger.info(blog_id + " result: " + str(result.get("success", False)))
    return result


def run_travel(blog_cfg):
    blog_id = blog_cfg["id"]
    logger.info("Travel pipeline: " + blog_id)

    os.chdir("/Users/twinssn/Projects/TAP")

    from shared.content_store import init_db, get_today_count
    from shared.publisher import publish
    from pipelines.travel.fetcher import (
        fetch_camping, fetch_korservice, fetch_korservice_heritage,
        fetch_wellness, fetch_heritage, fetch_festival, fetch_food,
        fetch_course, fetch_random
    )
    from pipelines.travel.writer import generate_content

    init_db()
    today_count = get_today_count(blog_id)
    if today_count >= blog_cfg.get("daily_quota", 50):
        logger.info(blog_id + " quota reached: " + str(today_count))
        return None

    FETCH_FUNCS = {
        "camping": fetch_camping,
        "korservice": fetch_korservice,
        "korservice_heritage": fetch_korservice_heritage,
        "wellness": fetch_wellness,
        "heritage": fetch_heritage,
        "festival": fetch_festival,
        "food": fetch_food,
        "course": fetch_course,
    }

    fetch_sources = blog_cfg.get("fetch_sources", [])
    data = None
    if fetch_sources:
        funcs = []
        weights = []
        for src in fetch_sources:
            func = FETCH_FUNCS.get(src["type"])
            if func:
                funcs.append(func)
                weights.append(src["weight"])
        if funcs:
            selected = random.choices(funcs, weights=weights, k=1)[0]
            logger.info(blog_id + " fetcher: " + selected.__name__)
            data = selected()
            if not data:
                for f in funcs:
                    if f != selected:
                        data = f()
                        if data:
                            break
    if not data:
        data = fetch_random()

    if not data:
        logger.error(blog_id + " no data fetched")
        _tg_error(blog_id, "data_fetch", "데이터 수집 실패")
        return None

    result = generate_content(data, blog_id=blog_id)
    if not result:
        logger.error(blog_id + " content generation failed")
        _tg_error(blog_id, "content_generation", "AI 본문 생성 실패")
        return None

    from shared.content_store import title_similar_exists, register_images, register_places
    if title_similar_exists(blog_id, result["title"]):
        logger.warning(blog_id + " similar title: " + result["title"][:30])
        return None

    pub_result = publish(
        blog_id=blog_id,
        title=result["title"],
        body_md=result.get("body_md", ""),
        body_html=result.get("body_html", ""),
        category=result.get("category", ""),
        tags=",".join(result.get("labels", [])),
        thumbnail_url="",
        data_source=result.get("source_type", ""),
        source_id="",
        prompt_id=result.get("prompt_id", ""),
        model=result.get("model", ""),
    )

    if pub_result and pub_result.get("success"):
        article_id = pub_result.get("article_id")
        body_md = result.get("body_md", "")
        body_html = result.get("body_html", "")
        if article_id and body_html:
            register_images(article_id, blog_id, body_html)
        if article_id and body_md:
            register_images(article_id, blog_id, body_md)
        # 장소 발행 이력 등록
        place_names = [it.get("title", it.get("facltNm", "")).strip()
                       for it in data.get("items", [])
                       if it.get("title") or it.get("facltNm")]
        if article_id and place_names:
            register_places(article_id, blog_id, place_names)
            logger.info("장소 %d건 등록: %s", len(place_names), ", ".join(n[:10] for n in place_names))

    logger.info(blog_id + " result: " + str(pub_result.get("success", False)))
    return pub_result


def dispatch(blog_id):
    cfg = get_blog_config(blog_id)
    if not cfg:
        logger.error("Unknown blog_id: " + blog_id)
        _tg_error(blog_id, "config", "blogs.yaml에 없는 blog_id")
        return None
    if cfg.get("status") != "active":
        logger.info(blog_id + " is not active")
        return None

    pipeline = cfg.get("pipeline", "")
    if pipeline == "senior":
        from pipelines.senior.pipeline import run
        return run(cfg)
    elif pipeline == "car":
        return run_car(cfg)
    elif pipeline == "travel":
        return run_travel(cfg)
    elif pipeline == "stock":
        blog_id = cfg.get("id", "")
        # STAP 블로그별 전문 파이프라인 매핑 (확장 시 여기만 추가)
        STAP_PIPELINE_MAP = {
            "dividend-hugo": "dividend",
            "etf-hugo": "etf",
            "sector-hugo": "sector",
            "ipo-hugo": "ipo",
            "finance-hugo": "finance",
        }
        stap_name = STAP_PIPELINE_MAP.get(blog_id)
        if stap_name:
            import importlib
            # STAP 경로를 최상위에 삽입 + 모듈 캐시 정리
            stap_root = "/Users/twinssn/Projects/STAP"
            if stap_root in sys.path:
                sys.path.remove(stap_root)
            sys.path.insert(0, stap_root)
            # 기존 shared/pipelines 모듈 캐시 제거
            for mod_name in list(sys.modules.keys()):
                if mod_name.startswith("shared.") or mod_name.startswith("pipelines."):
                    del sys.modules[mod_name]
            if "shared" in sys.modules:
                del sys.modules["shared"]
            if "pipelines" in sys.modules:
                del sys.modules["pipelines"]
            mod = importlib.import_module(f"pipelines.{stap_name}.pipeline")
            importlib.reload(mod)
            result = mod.run(cfg)
            # 복원: STAP 경로 제거, 5000 모듈 캐시도 정리
            if stap_root in sys.path:
                sys.path.remove(stap_root)
            for mod_name in list(sys.modules.keys()):
                if mod_name.startswith("shared.") or mod_name.startswith("pipelines."):
                    del sys.modules[mod_name]
            if "shared" in sys.modules:
                del sys.modules["shared"]
            if "pipelines" in sys.modules:
                del sys.modules["pipelines"]
            return result
        else:
            from pipelines.stock.pipeline import run as run_stock
            return run_stock(cfg)
    elif pipeline == "gap":
        from pipelines.gap.pipeline import run as run_gap
        return run_gap(cfg)
    else:
        logger.error("Unknown pipeline: " + pipeline)
        _tg_error(blog_id, "pipeline", "Unknown pipeline: " + pipeline)
        return None


def main():
    if len(sys.argv) < 2:
        print("usage: dispatcher.py <blog_id|report|init-db>")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "init-db":
        from shared.content_store import init_db
        init_db()
        print("DB initialized")
        return

    if cmd == "report":
        try:
            from shared.monitor import send_daily_report
            send_daily_report()
        except Exception as e:
            print("Report failed: " + str(e))
        return

    dispatch(cmd)


if __name__ == "__main__":
    main()

import os
import sys
import re
import sqlite3
import logging
import urllib.request
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv("/Users/twinssn/Projects/5000/.env")

from shared.content_store import init_db, get_today_count, title_similar_exists
from shared.publisher import publish
from shared.image_handler import process_and_upload
from shared.ai_writer import generate_car
from shared.telegram_notifier import send_error as _tg_error
from pipelines.car.topic_manager import select_topic, generate_title, make_slug, validate_body
from pipelines.car.data_builder import build_input

logger = logging.getLogger(__name__)

PROJECT_DIR = Path(__file__).parent.parent.parent
CAR_DB_PATH = PROJECT_DIR / "data" / "car.db"
PROMPTS_DIR = PROJECT_DIR / "prompts"


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
        req = urllib.request.Request(selected_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            image_data = resp.read()
        r2_url = process_and_upload(image_data)
        return r2_url, selected_url
    except Exception as e:
        logger.warning("Image failed: " + str(e))
        return "", ""


def run(blog_cfg):
    blog_id = blog_cfg["id"]
    logger.info("CAP pipeline: " + blog_id)

    init_db()
    today_count = get_today_count(blog_id)
    if today_count >= blog_cfg.get("daily_quota", 50):
        logger.info(blog_id + " quota reached: " + str(today_count))
        return {"success": False, "reason": "quota_met"}

    conn = sqlite3.connect(str(CAR_DB_PATH))
    conn.row_factory = sqlite3.Row

    MAX_RETRY = 6
    topic = None
    data = None
    skip_ids = []

    today_car_ids = set()
    _today_rows = conn.execute(
        "SELECT DISTINCT t.car_id FROM publish_log p JOIN topics t ON t.id=p.topic_id "
        "WHERE p.site=? AND date(p.published_at)=date('now','localtime')",
        (blog_id.replace('-hugo', ''),)
    ).fetchall()
    today_car_ids = {r[0] for r in _today_rows}
    logger.info("today car_ids for " + blog_id + ": " + str(today_car_ids))

    car_site_id = blog_id.replace('-hugo', '')

    for attempt in range(1, MAX_RETRY + 1):
        logger.info("토픽 선택 (시도 " + str(attempt) + "/" + str(MAX_RETRY) + ")")
        pt_cfg = blog_cfg.get('post_type')
        if isinstance(pt_cfg, list):
            import random as _rnd
            _rnd.shuffle(pt_cfg)
            topic = None
            for _pt in pt_cfg:
                topic = select_topic(conn, site_id=car_site_id, skip_ids=skip_ids, post_type=_pt)
                if topic:
                    break
        else:
            topic = select_topic(conn, site_id=car_site_id, skip_ids=skip_ids, post_type=pt_cfg)
        if not topic:
            logger.info(blog_id + " no topics available")
            conn.close()
            return {"success": False, "reason": "no_topics"}
        if topic and topic['car_id'] in today_car_ids:
            logger.info("car_id dup skip: " + str(topic['car_id']))
            skip_ids.append(topic['id'])
            topic = None
            continue
        data = build_input(conn, topic, CAR_DB_PATH)
        if data:
            data['site_id'] = blog_id
            break
        skip_ids.append(topic['id'])
        conn.execute("UPDATE topics SET status='skip_no_data' WHERE id=?", (topic['id'],))
        conn.commit()

    if not data:
        conn.close()
        return {"success": False, "reason": "no_data"}

    logger.info(data['model'] + " " + data['trim'] + " (" + str(data['base_price']) + "만원)")

    prompt_cfg = blog_cfg.get("prompt", "")
    if isinstance(prompt_cfg, dict):
        prompt_file = PROMPTS_DIR / prompt_cfg.get(topic['post_type'], "")
    else:
        prompt_file = PROMPTS_DIR / prompt_cfg
    if not prompt_file.exists():
        logger.error("Prompt not found: " + str(prompt_file))
        conn.close()
        return {"success": False, "reason": "prompt_not_found"}

    prompt_text = prompt_file.read_text(encoding="utf-8")
    body = generate_car(prompt_text, data)
    if not body:
        logger.error(blog_id + " content generation failed")
        _tg_error(blog_id, "content_generation", "AI 본문 생성 실패")
        conn.close()
        return {"success": False, "reason": "generation_failed"}

    body = validate_body(body, data)

    MIN_CHARS = 2200
    if len(body) < MIN_CHARS:
        logger.warning(f"글자수 {len(body)}자 미달({MIN_CHARS}자) — 힌트 추가 재생성")
        length_hint = (
            "\n\n[추가 지시]\n"
            "이전 응답이 너무 짧았습니다. 반드시 2,500자 이상 작성하세요.\n"
            "각 H2 섹션을 5문장 이상으로 쓰고, 모든 숫자에 해석 문장을 붙이세요.\n"
            "표 아래에 핵심 요약 문장을 추가하세요. 절대 글을 일찍 끝내지 마세요."
        )
        body2 = generate_car(prompt_text + length_hint, data)
        if body2:
            body2 = validate_body(body2, data)
            if len(body2) >= len(body):
                body = body2
                logger.info(f"재생성 완료: {len(body)}자")
            else:
                logger.warning(f"재생성도 미달: {len(body2)}자 — 긴 쪽 유지")

    title = None
    for _title_attempt in range(5):
        candidate = generate_title(data, site_id=car_site_id)
        if not title_similar_exists(blog_id, candidate):
            title = candidate
            break
        logger.warning(f"제목 중복 재시도 {_title_attempt+1}/5: {candidate[:40]}")
    if title is None:
        title = generate_title(data, site_id=car_site_id)
        logger.warning(f"5회 모두 중복 — 마지막 제목 사용: {title[:40]}")
    slug = make_slug(title)
    logger.info("제목: " + title)

    r2_url, origin_url = _select_car_image(conn, topic['car_id'], slug)
    if r2_url:
        logger.info("R2: " + r2_url)

    tags_list = [data.get("model", ""), data.get("competitor", ""), "잔존가치", "중고시세"]
    tags_str = ",".join([t for t in tags_list if t])

    _comp = data.get("competitor", "")
    if _comp:
        _seo_desc = (
            f"{data['model']} vs {_comp}, "
            f"3년 총비용 {data.get('three_year_total_cost',0):,}만원 vs "
            f"{data.get('competitor_three_year_total_cost',0):,}만원. "
            f"감가 {data.get('three_year_depreciation',0):,}만원, "
            f"잔존가치율 {data.get('resale_rate_percent',0)}%. "
            f"{datetime.now().strftime('%Y년 %m월')} 기준 실비용 비교."
        )
    else:
        _maint_m = round((data.get('tax_annual',0)+data.get('insurance_estimate',0)+data.get('annual_fuel_cost',0))/12)
        _seo_desc = (
            f"{data['model']} {data.get('trim','')} "
            f"3년 총비용 {data.get('three_year_total_cost',0):,}만원, "
            f"월 유지비 약 {_maint_m}만원. "
            f"{datetime.now().strftime('%Y년 %m월')} 기준 분석."
        )
    body = "<!-- DESC: " + _seo_desc[:160] + " -->\n" + body

    result = publish(
        blog_id=blog_id,
        title=title,
        body_md=body,
        category="자동차",
        tags=tags_str,
        thumbnail_url=r2_url,
        data_source="car_db",
        source_id=str(topic['car_id']),
        prompt_id=topic["post_type"] if topic else blog_cfg.get("post_type", ""),
        model="gpt-4o-mini",
        segment=data.get("segment", ""),
        fuel_type=data.get("fuel_type", ""),
    )

    c = conn.cursor()
    c.execute(
        "INSERT INTO publish_log (topic_id, site, title, slug, published_at, image_url, r2_url) VALUES (?,?,?,?,?,?,?)",
        (topic['id'], car_site_id, title, slug, datetime.now().isoformat(), origin_url or "", r2_url or "")
    )
    c.execute("UPDATE topics SET status='published', published_at=? WHERE id=?",
              (datetime.now().isoformat(), topic['id']))
    conn.commit()
    conn.close()

    logger.info(blog_id + " result: " + str(result.get("success", False)))
    return result

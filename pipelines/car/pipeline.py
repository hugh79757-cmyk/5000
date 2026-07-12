import logging
import os
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv

load_dotenv("/Users/twinssn/Projects/5000/.env")

from pipelines.car.data_builder import build_input
from pipelines.car.topic_manager import generate_title, make_slug, select_topic, validate_body
from shared.ai_writer import generate_car
from shared.content_store import get_today_count, init_db, title_similar_exists
from shared.publisher import publish
from shared.telegram_notifier import send_error as _tg_error
from shared.validators import sanitize_title

logger = logging.getLogger(__name__)

PROJECT_DIR = Path(__file__).parent.parent.parent
CAR_DB_PATH = PROJECT_DIR / "data" / "car.db"
PROMPTS_DIR = PROJECT_DIR / "prompts"


def _select_car_image(conn, car_id, slug):
    try:
        c = conn.cursor()
        used = c.execute(
            "SELECT r2_url FROM publish_log WHERE published_at > datetime('now', '-7 days') AND r2_url IS NOT NULL AND r2_url != ''"
        ).fetchall()
        used_urls = {r["r2_url"] for r in used} if used else set()
        images = c.execute(
            "SELECT r2_url, image_url FROM car_images WHERE car_id = ? AND verified = 1 AND r2_url IS NOT NULL AND r2_url != '' ORDER BY RANDOM()",
            (car_id,)
        ).fetchall()
        selected = None
        for img in images:
            if img["r2_url"] not in used_urls:
                selected = img
                break
        if not selected and images:
            selected = images[0]
        if not selected:
            base_id = re.sub(r"_(hev|phev|ev|25|35|lpg)(?=_)", "", car_id)
            if base_id != car_id:
                fallback_imgs = c.execute(
                    "SELECT r2_url, image_url FROM car_images WHERE car_id = ? AND verified = 1 AND r2_url IS NOT NULL AND r2_url != '' ORDER BY RANDOM()",
                    (base_id,)
                ).fetchall()
                for img in fallback_imgs:
                    if img["r2_url"] not in used_urls:
                        selected = img
                        break
                if not selected and fallback_imgs:
                    selected = fallback_imgs[0]
        if not selected:
            logger.warning("No verified R2 image for: " + car_id)
            return "", ""
        return selected["r2_url"], selected["image_url"]
    except Exception as e:
        logger.warning("Image failed: " + str(e))
        return "", ""


# /Users/twinssn/Projects/5000/pipelines/car/pipeline.py
# run() 함수 내부 전체 교체

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

    MAX_RETRY = 26
    topic = None
    data = None
    skip_ids = []

    today_car_ids = set()
    _today_rows = conn.execute(
        "SELECT DISTINCT t.car_id FROM publish_log p JOIN topics t ON t.id=p.topic_id "
        "WHERE p.site=? AND date(p.published_at)=date('now','localtime')",
        (blog_id.replace("-hugo", ""),)
    ).fetchall()
    today_car_ids = {r[0] for r in _today_rows}
    logger.info("today car_ids for " + blog_id + ": " + str(today_car_ids))

    car_site_id = blog_id.replace("-hugo", "")

    # ── post_type 확정 ──
    pt_cfg = blog_cfg.get("post_type")
    if isinstance(pt_cfg, list):
        import random as _rnd
        _rnd.shuffle(pt_cfg)
        resolved_post_type = pt_cfg[0]
    else:
        resolved_post_type = pt_cfg

    NEW_TYPES = ("top5_rank", "persona_pick", "price_trend")

    for attempt in range(1, MAX_RETRY + 1):
        logger.info("토픽 선택 (시도 " + str(attempt) + "/" + str(MAX_RETRY) + ")")

        # post_type 선택 (list인 경우 순환)
        if isinstance(pt_cfg, list):
            import random as _rnd
            _rnd.shuffle(pt_cfg)
            topic = None
            for _pt in pt_cfg:
                topic = select_topic(conn, site_id=car_site_id, skip_ids=skip_ids, post_type=_pt)
                if topic:
                    resolved_post_type = _pt
                    break
        else:
            topic = select_topic(conn, site_id=car_site_id, skip_ids=skip_ids, post_type=pt_cfg)
            resolved_post_type = pt_cfg

        if not topic:
            logger.info(blog_id + " no topics available")
            conn.close()
            return {"success": False, "reason": "no_topics"}

        topic = dict(topic)

        if topic["car_id"] in today_car_ids:
            logger.info("car_id dup skip: " + str(topic["car_id"]))
            skip_ids.append(topic["id"])
            continue

        post_type = topic.get("post_type", resolved_post_type)

        # ── 신규 타입: build_input() 우회, 전용 빌더 직접 호출 ──
        if post_type in NEW_TYPES:
            try:
                if post_type == "top5_rank":
                    import random as _rnd

                    from pipelines.car.data_builder import build_top5_rank_input
                    topic["rank_type"] = _rnd.choice(["resale", "maintenance", "monthly_cost", "value"])
                    data = build_top5_rank_input(conn, topic, CAR_DB_PATH)

                elif post_type == "persona_pick":
                    import random as _rnd

                    from pipelines.car.data_builder import build_persona_pick_input
                    # 차량 가격대 조회
                    _car_price_row = conn.execute(
                        "SELECT MIN(price) as min_price FROM trims WHERE car_id=? AND status='시판' AND price >= 500",
                        (topic["car_id"],)
                    ).fetchone()
                    _price = _car_price_row["min_price"] if _car_price_row and _car_price_row["min_price"] else 5000
                    # 가격대별 적합 페르소나 매핑
                    if _price <= 2500:
                        _eligible = ["first_car", "commuter"]
                    elif _price <= 4000:
                        _eligible = ["first_car", "commuter", "newlywed"]
                    elif _price <= 6000:
                        _eligible = ["commuter", "newlywed", "family"]
                    elif _price <= 9000:
                        _eligible = ["family", "premium"]
                    else:
                        _eligible = ["premium"]
                    topic["persona_type"] = _rnd.choice(_eligible)
                    logger.info(f"persona_pick: {topic['car_id']} 가격 {_price}만원 → {topic['persona_type']}")
                    data = build_persona_pick_input(conn, topic, CAR_DB_PATH)


                elif post_type == "price_trend":
                    from pipelines.car.data_builder import build_price_trend_input
                    data = build_price_trend_input(conn, topic["car_id"], CAR_DB_PATH)

            except Exception as _e:
                logger.warning(f"[{post_type}] 빌더 예외: {_e}")
                data = None

            if data:
                data["site_id"] = blog_id
                break
            # 신규 타입 실패 → skip_no_data 아닌 pending 유지 (재시도 가능하게)
            logger.warning(f"{blog_id} {post_type} 데이터 없음: {topic['car_id']} — skip 처리 안함")
            skip_ids.append(topic["id"])
            continue

        # ── 기존 타입: build_input() 사용 ──
        data = build_input(conn, topic, CAR_DB_PATH)
        if data:
            data["site_id"] = blog_id
            break
        skip_ids.append(topic["id"])
        conn.execute("UPDATE topics SET status='skip_no_data' WHERE id=?", (topic["id"],))
        conn.commit()

    if not data:
        conn.close()
        return {"success": False, "reason": "no_data"}

    logger.info(data["model"] + " " + data.get("trim", "") + " (" + str(data.get("base_price", "")) + "만원)")

    prompt_cfg = blog_cfg.get("prompt", "")
    if isinstance(prompt_cfg, dict):
        prompt_file = PROMPTS_DIR / prompt_cfg.get(topic["post_type"], "")
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

    title = None
    for _title_attempt in range(5):
        candidate = generate_title(data, site_id=car_site_id)
        if not title_similar_exists(blog_id, candidate):
            title = candidate
            break
        logger.warning(f"제목 중복 재시도 {_title_attempt+1}/5: {candidate[:40]}")
    if title is None:
        title = generate_title(data, site_id=car_site_id)
    title = sanitize_title(title) if title else title
    slug = make_slug(title)
    logger.info("제목: " + title)

    r2_url, origin_url = _select_car_image(conn, topic["car_id"], slug)
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
        _maint_m = round((data.get("tax_annual",0)+data.get("insurance_estimate",0)+data.get("annual_fuel_cost",0))/12)
        _seo_desc = (
            f"{data['model']} {data.get('trim','')} "
            f"3년 총비용 {data.get('three_year_total_cost',0):,}만원, "
            f"월 유지비 약 {_maint_m}만원. "
            f"{datetime.now().strftime('%Y년 %m월')} 기준 분석."
        )
    body = "<!-- DESC: " + _seo_desc[:160] + " -->\n" + body

    _is_draft = False
    try:
        from shared.validators import validate_post_extended as _validate
        _val_ctx = {
            "keyword": data.get("model_name", ""),
            "event_date": "",
            "daily_quota": blog_cfg.get("daily_quota", 5),
            "post_type": post_type,
        }
        _issues = _validate(blog_id, title, body, _val_ctx, pipeline="car")
        if _issues:
            _is_draft = True
            logger.warning(f"[Validate] {len(_issues)} issues → draft: {_issues}")
    except Exception as _ve:
        logger.warning(f"[Validate] Error (non-fatal): {_ve}")

    result = publish(
        blog_id=blog_id,
        title=title,
        body_md=body,
        category="자동차",
        tags=tags_str,
        thumbnail_url=r2_url,
        data_source="car_db",
        source_id=str(topic["car_id"]),
        prompt_id=topic.get("post_type", blog_cfg.get("post_type", "")),
        model=os.getenv("OPENAI_MODEL", "mimo-v2.5"),
        segment=data.get("segment", ""),
        fuel_type=data.get("fuel_type", ""),
        is_draft=_is_draft,
    )

    c = conn.cursor()
    c.execute(
        "INSERT INTO publish_log (topic_id, site, title, slug, published_at, image_url, r2_url) VALUES (?,?,?,?,?,?,?)",
        (topic["id"], car_site_id, title, slug, datetime.now().isoformat(), origin_url or "", r2_url or "")
    )
    c.execute("UPDATE topics SET status='published', published_at=? WHERE id=?",
              (datetime.now().isoformat(), topic["id"]))
    conn.commit()
    conn.close()

    logger.info(blog_id + " result: " + str(result.get("success", False)))
    return result


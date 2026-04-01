"""
Viator 투어 피드 수집기
- gzip JSON 피드 다운로드 -> viator_tours 테이블
- 피드 URL: Travelpayouts 지원팀에 요청 (support@travelpayouts.com)
"""
import os
import gzip
import json
import sqlite3
import logging
import requests
from datetime import datetime

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "data", "travel-en.db")


def _get_db():
    return sqlite3.connect(DB_PATH)


def collect_viator_tours():
    """Viator 할인 투어 피드 다운로드 및 DB 저장"""
    feed_url = os.getenv("VIATOR_FEED_URL", "")
    if not feed_url:
        logger.warning("[Viator] VIATOR_FEED_URL 미설정 — .env에 추가 필요")
        return 0

    try:
        resp = requests.get(feed_url, timeout=120, stream=True)
        resp.raise_for_status()

        raw = gzip.decompress(resp.content)
        tours = json.loads(raw)
        if not isinstance(tours, list):
            tours = [tours]

        db = _get_db()
        count = 0
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for t in tours:
            savings = t.get("savings_percent", "0%").replace("%", "")
            try:
                discount = float(savings)
            except ValueError:
                discount = 0.0

            price = float(t.get("search_price", 0) or 0)
            original_price = price / (1 - discount / 100) if discount > 0 else price

            db.execute("""
                INSERT OR REPLACE INTO viator_tours
                (tour_id, title, description, destination_city, destination_country,
                 price, original_price, discount_pct, currency, photo_url, tour_url,
                 rating, review_count, duration, category, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                t.get("merchant_product_id", ""),
                t.get("product_name", ""),
                t.get("description", "")[:500],
                t.get("merchant_product_category_path", ""),
                t.get("merchant_product_second_category", ""),
                price, round(original_price, 2), discount,
                t.get("currency", "USD"),
                t.get("merchant_image_url", ""),
                t.get("merchant_deep_link", ""),
                0, 0, "",
                t.get("merchant_category", ""),
                now,
            ))
            count += 1

        db.commit()
        db.close()
        logger.info(f"[Viator] {count}건 투어 저장 완료")
        return count

    except Exception as e:
        logger.error(f"[Viator] 수집 실패: {e}")
        return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), ".env"))
    count = collect_viator_tours()
    print(f"Viator tours: {count}건")

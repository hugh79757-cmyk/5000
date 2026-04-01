"""
Omio 인기 노선 피드 수집기
- XML 또는 CSV 피드 -> omio_routes 테이블
- 피드 URL: Travelpayouts 문서에서 제공
"""
import os
import csv
import io
import sqlite3
import logging
import requests
import xml.etree.ElementTree as ET
from datetime import datetime

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "data", "travel-en.db")


def _get_db():
    return sqlite3.connect(DB_PATH)


def collect_omio_routes():
    """Omio 인기 노선 수집"""
    feed_url = os.getenv("OMIO_FEED_URL", "")
    if not feed_url:
        logger.warning("[Omio] OMIO_FEED_URL 미설정 — .env에 추가 필요")
        return 0

    try:
        resp = requests.get(feed_url, timeout=60)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")

        db = _get_db()
        count = 0
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if "xml" in content_type or resp.content[:5] == b"<?xml":
            root = ET.fromstring(resp.content)
            for item in root.findall(".//item") or root.findall(".//route"):
                origin = item.findtext("origin_name", "") or item.findtext("origin", "")
                destination = item.findtext("destination_name", "") or item.findtext("destination", "")
                transport = item.findtext("travel_mode", "") or item.findtext("transport_type", "")
                rank_text = item.findtext("Top_Seller_Rank", "0")
                rank = int(rank_text) if rank_text.isdigit() else 0

                db.execute("""
                    INSERT INTO omio_routes
                    (origin, destination, transport_type, country, popularity_rank, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (origin, destination, transport, "", rank, now))
                count += 1
        else:
            text = resp.text
            reader = csv.DictReader(io.StringIO(text))
            for row in reader:
                origin = row.get("origin_name", "") or row.get("origin", "")
                destination = row.get("destination_name", "") or row.get("destination", "")
                transport = row.get("travel_mode", "") or row.get("transport_type", "")
                rank = int(row.get("Top_Seller_Rank", 0) or 0)

                db.execute("""
                    INSERT INTO omio_routes
                    (origin, destination, transport_type, country, popularity_rank, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (origin, destination, transport, "", rank, now))
                count += 1

        db.commit()
        db.close()
        logger.info(f"[Omio] {count}건 노선 저장 완료")
        return count

    except Exception as e:
        logger.error(f"[Omio] 수집 실패: {e}")
        return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), ".env"))
    count = collect_omio_routes()
    print(f"Omio routes: {count}건")

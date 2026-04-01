"""
Airalo eSIM 피드 수집기
- XML(Google Shopping 형식) 피드 -> airalo_esim 테이블
- 피드 URL: Travelpayouts 문서에서 제공
"""
import os
import re
import sqlite3
import logging
import requests
import xml.etree.ElementTree as ET
from datetime import datetime

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "data", "travel-en.db")


def _get_db():
    return sqlite3.connect(DB_PATH)


def _parse_title(title):
    """title에서 데이터량, 유효기간 추출"""
    data_match = re.search(r"(\d+(?:\.\d+)?)\s*(GB|MB)", title, re.IGNORECASE)
    days_match = re.search(r"(\d+)\s*Days?", title, re.IGNORECASE)
    data_amount = f"{data_match.group(1)} {data_match.group(2).upper()}" if data_match else ""
    validity = int(days_match.group(1)) if days_match else 0
    return data_amount, validity


def collect_airalo_esim():
    """Airalo eSIM 피드 수집"""
    feed_url = os.getenv("AIRALO_FEED_URL", "")
    if not feed_url:
        logger.warning("[Airalo] AIRALO_FEED_URL 미설정 — .env에 추가 필요")
        return 0

    try:
        resp = requests.get(feed_url, timeout=60)
        resp.raise_for_status()

        ns = {"g": "http://base.google.com/ns/1.0"}
        root = ET.fromstring(resp.content)
        items = root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry")

        db = _get_db()
        count = 0
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for item in items:
            title = item.findtext("title", "") or item.findtext("g:title", "", ns)
            price_text = item.findtext("g:price", "0", ns)
            price = float(re.sub(r"[^\d.]", "", price_text)) if price_text else 0

            data_amount, validity = _parse_title(title)
            product_type = item.findtext("g:product_type", "", ns)
            country = product_type if product_type else title.split(" - ")[0] if " - " in title else ""

            db.execute("""
                INSERT INTO airalo_esim
                (country, country_code, plan_name, data_amount, validity_days,
                 price, currency, operator, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                country, "", title, data_amount, validity,
                price, "USD", item.findtext("g:brand", "", ns), now,
            ))
            count += 1

        db.commit()
        db.close()
        logger.info(f"[Airalo] {count}건 eSIM 저장 완료")
        return count

    except Exception as e:
        logger.error(f"[Airalo] 수집 실패: {e}")
        return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), ".env"))
    count = collect_airalo_esim()
    print(f"Airalo eSIM: {count}건")

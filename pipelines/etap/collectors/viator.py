"""Viator deals feed collector – downloads gzipped JSON from Travelpayouts."""
import os, sys, json, gzip, sqlite3, logging, io
from datetime import datetime

try:
    import requests
except ImportError:
    requests = None

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DB_PATH = os.path.join(BASE_DIR, "data", "travel-en.db")

def _get_db():
    return sqlite3.connect(DB_PATH)

def _token():
    return os.getenv("TRAVELPAYOUTS_API_TOKEN", "")

def _safe_float(val):
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None

def collect_viator_feed():
    """Viator deals feed (JSON.gz) 다운로드 및 DB 저장"""
    token = _token()
    if not token:
        logger.error("[Viator] TRAVELPAYOUTS_API_TOKEN 없음")
        return 0

    feed_url = f"https://api.travelpayouts.com/data/viator_deals_feed.json.gz?token={token}"
    logger.info(f"[Viator] 피드 다운로드: {feed_url[:60]}...")

    if requests is None:
        logger.error("[Viator] requests 모듈 없음")
        return 0

    resp = requests.get(feed_url, timeout=120)
    resp.raise_for_status()

    # gzip 해제
    try:
        buf = io.BytesIO(resp.content)
        with gzip.GzipFile(fileobj=buf) as gz:
            raw = gz.read().decode("utf-8")
        data = json.loads(raw)
    except Exception:
        # gzip이 아닌 경우 직접 JSON 파싱
        data = resp.json()

    # data 구조 확인 (리스트 또는 dict with key)
    if isinstance(data, dict):
        items = data.get("data", data.get("deals", data.get("products", [])))
        if not isinstance(items, list):
            items = [data]
    elif isinstance(data, list):
        items = data
    else:
        logger.error(f"[Viator] 예상치 못한 데이터 형식: {type(data)}")
        return 0

    logger.info(f"[Viator] {len(items)}개 항목 수신")

    db = _get_db()
    count = 0

    for item in items:
        try:
            merchant_id = str(item.get("merchant_product_id", item.get("id", item.get("productCode", ""))))
            product_name = item.get("product_name", item.get("name", item.get("title", "")))
            if not merchant_id and not product_name:
                continue

            description = item.get("description", "")
            category = item.get("category", item.get("product_category", ""))
            image_url = item.get("image_url", item.get("image", ""))
            thumbnail_url = item.get("thumbnail_url", item.get("thumbnail", ""))
            price = _safe_float(item.get("price", item.get("retail_price")))
            currency = item.get("currency", "USD")
            discount = _safe_float(item.get("discount_percent", item.get("discount", 0)))
            sale_flag = str(item.get("sale_flag", item.get("on_sale", "")))
            promo_text = item.get("promotional_text", item.get("promo_text", ""))
            valid_from = item.get("valid_from", item.get("start_date", ""))
            valid_to = item.get("valid_to", item.get("end_date", ""))
            deep_link = item.get("deep_link", item.get("link", item.get("url", "")))

            db.execute("""
                INSERT OR REPLACE INTO viator_tours
                (merchant_id, product_name, description, category, image_url, thumbnail_url,
                 price, currency, discount_percent, sale_flag, promotional_text,
                 valid_from, valid_to, deep_link)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (merchant_id, product_name, description, category, image_url, thumbnail_url,
                  price, currency, discount, sale_flag, promo_text,
                  valid_from, valid_to, deep_link))
            count += 1
        except Exception as e:
            logger.warning(f"[Viator] item 파싱 오류: {e}")
            continue

    db.commit()
    db.close()
    logger.info(f"[Viator] {count}건 저장 완료")
    return count

def run_full_collection():
    return collect_viator_feed()

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BASE_DIR, ".env"))
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    total = run_full_collection()
    print(f"Viator tours: {total}건")

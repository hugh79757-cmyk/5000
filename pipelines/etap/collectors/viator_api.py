"""Viator Partner API v2 직접 수집기 — products/search 기반"""
import os, sys, json, sqlite3, logging, time
from datetime import datetime

try:
    import requests
except ImportError:
    requests = None

logger = logging.getLogger(__name__)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DB_PATH = os.path.join(BASE_DIR, "data", "travel-en.db")

API_BASE = "https://api.viator.com/partner"
HEADERS = lambda key: {
    "exp-api-key": key,
    "Accept": "application/json;version=2.0",
    "Accept-Language": "en-US",
    "Content-Type": "application/json",
}

def _get_db():
    return sqlite3.connect(DB_PATH)

def _api_key():
    return os.getenv("VIATOR_API_KEY", "")

def _search_products(dest_id, offset=0, limit=50):
    key = _api_key()
    payload = {
        "filtering": {"destination": str(dest_id)},
        "pagination": {"offset": offset, "limit": limit},
        "currency": "USD",
        "sorting": {"sort": "DEFAULT"}
    }
    r = requests.post(f"{API_BASE}/products/search", headers=HEADERS(key), json=payload, timeout=30)
    r.raise_for_status()
    return r.json()

def _extract_product(p, dest_name, dest_id):
    """API 응답에서 viator_tours 스키마에 맞게 추출"""
    images = p.get("images", [])
    cover = next((i for i in images if i.get("isCover")), images[0] if images else {})
    variants = cover.get("variants", [])
    image_url = ""
    thumbnail_url = ""
    if variants:
        largest = max(variants, key=lambda v: v.get("width", 0))
        image_url = largest.get("url", "")
        smallest = min(variants, key=lambda v: v.get("width", 0))
        thumbnail_url = smallest.get("url", "")

    pricing = p.get("pricing", {})
    summary = pricing.get("summary", {})
    price = summary.get("fromPrice", None)
    currency = pricing.get("currency", "USD")

    # deep_link: PID로 affiliate URL 생성
    pid = os.getenv("VIATOR_PID", "")
    product_code = p.get("productCode", "")
    product_url = p.get("productUrl", "")
    deep_link = f"{product_url}?pid={pid}" if pid and product_url else product_url

    # category: tags에서 추출
    tags = p.get("tags", [])
    category = ""
    if tags:
        # 첫 번째 태그 ID → 카테고리명 매핑은 단순화
        category = str(tags[0]) if tags else ""

    destinations = p.get("destinations", [])
    primary_dest = next((d for d in destinations if d.get("primary")), destinations[0] if destinations else {})
    city = primary_dest.get("name", dest_name)
    country = ""

    return {
        "merchant_id": product_code,
        "product_name": p.get("title", ""),
        "description": p.get("description", ""),
        "category": category,
        "image_url": image_url,
        "thumbnail_url": thumbnail_url,
        "price": price,
        "currency": currency,
        "discount_percent": None,
        "deep_link": deep_link,
        "city": city,
        "country": country,
    }

def collect_for_destinations(dest_ids, max_per_dest=100):
    """지정된 destination ID 목록에서 상품 수집"""
    key = _api_key()
    if not key:
        logger.error("[ViatorAPI] VIATOR_API_KEY 없음")
        return 0

    db = _get_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total = 0

    for dest_id, dest_name in dest_ids:
        logger.info(f"[ViatorAPI] 수집: {dest_name} (ID={dest_id})")
        offset = 0
        dest_count = 0

        while offset < max_per_dest:
            try:
                data = _search_products(dest_id, offset=offset, limit=50)
                products = data.get("products", [])
                if not products:
                    break
                for p in products:
                    item = _extract_product(p, dest_name, dest_id)
                    if not item["merchant_id"] or not item["product_name"]:
                        continue
                    db.execute("""
                        INSERT OR REPLACE INTO viator_tours
                        (merchant_id, product_name, description, category, image_url, thumbnail_url,
                         price, currency, discount_percent, deep_link, city, country, collected_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (item["merchant_id"], item["product_name"], item["description"],
                          item["category"], item["image_url"], item["thumbnail_url"],
                          item["price"], item["currency"], item["discount_percent"],
                          item["deep_link"], item["city"], item["country"], now))
                    dest_count += 1
                db.commit()
                offset += len(products)
                if len(products) < 50:
                    break
                time.sleep(0.3)
            except Exception as e:
                logger.warning(f"[ViatorAPI] {dest_name} offset={offset} 오류: {e}")
                break

        logger.info(f"[ViatorAPI] {dest_name}: {dest_count}건")
        total += dest_count
        time.sleep(0.5)

    db.close()
    logger.info(f"[ViatorAPI] 총 {total}건 수집 완료")
    return total

def run_full_collection():
    """viator_destinations의 CITY 타입 상위 500개 수집"""
    db = _get_db()
    rows = db.execute("""
        SELECT destination_id, name FROM viator_destinations
        WHERE type = 'CITY'
        ORDER BY destination_id
        LIMIT 500
    """).fetchall()
    db.close()
    logger.info(f"[ViatorAPI] 대상 destinations: {len(rows)}개")
    return collect_for_destinations(rows, max_per_dest=100)

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BASE_DIR, ".env"))
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    total = run_full_collection()
    print(f"총 수집: {total}건")

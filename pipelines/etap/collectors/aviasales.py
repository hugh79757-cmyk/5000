"""
Aviasales 항공권 가격 수집기
- /v2/prices/latest: 최근 48시간 최저가
- /v1/prices/cheap: 노선별 최저가
- /v1/prices/calendar: 월별 일일 가격
- /v1/city-directions: 도시별 인기 방면
"""
import os
import time
import sqlite3
import logging
import requests
from datetime import datetime

logger = logging.getLogger(__name__)

BASE_URL = "https://api.travelpayouts.com"
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "data", "travel-en.db")

ORIGIN_CITIES = ["NYC", "LAX", "SFO", "ORD", "MIA", "SEA", "DFW", "ATL", "BOS", "DEN"]


def _token():
    return os.getenv("TRAVELPAYOUTS_API_TOKEN", "")


def _headers():
    return {"X-Access-Token": _token()}


def _get_db():
    return sqlite3.connect(DB_PATH)


def _get_destination_iata_codes():
    db = _get_db()
    rows = db.execute("SELECT iata_code, city, country FROM destinations WHERE iata_code != \'\'").fetchall()
    db.close()
    return [(r[0], r[1], r[2]) for r in rows]


def collect_latest_prices(origin="NYC", limit=30):
    """최근 48시간 최저가 수집 -> flight_prices"""
    url = f"{BASE_URL}/v2/prices/latest"
    params = {
        "origin": origin, "currency": "usd",
        "period_type": "year", "page": 1,
        "limit": limit, "sorting": "price", "trip_class": 0,
    }
    try:
        resp = requests.get(url, headers=_headers(), params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            logger.warning(f"[Aviasales] latest prices failed for {origin}")
            return 0

        db = _get_db()
        count = 0
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for item in data.get("data", []):
            db.execute("""
                INSERT INTO flight_prices
                (origin, destination, price, currency, airline, flight_number, stops,
                 departure_date, return_date, expires_at, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                origin, item.get("destination", ""),
                item.get("value", 0), "USD",
                item.get("gate", ""), item.get("flight_number", 0),
                item.get("number_of_changes", 0),
                item.get("depart_date", ""), item.get("return_date", ""),
                item.get("expires_at", ""), now,
            ))
            count += 1
        db.commit()
        db.close()
        logger.info(f"[Aviasales] {origin} latest prices: {count}건 저장")
        return count
    except Exception as e:
        logger.error(f"[Aviasales] latest prices error ({origin}): {e}")
        return 0


def collect_cheap_prices(origin="NYC", destinations=None):
    """특정 노선 최저가 수집 -> flight_prices"""
    if destinations is None:
        destinations = [code for code, _, _ in _get_destination_iata_codes()]

    url = f"{BASE_URL}/v1/prices/cheap"
    db = _get_db()
    total = 0
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for dest in destinations[:50]:
        if dest == origin:
            continue
        params = {"origin": origin, "destination": dest, "currency": "usd"}
        try:
            resp = requests.get(url, headers=_headers(), params=params, timeout=15)
            if resp.status_code != 200:
                continue
            data = resp.json().get("data", {})
            for dest_code, stops_dict in data.items():
                for stop_key, info in stops_dict.items():
                    db.execute("""
                        INSERT INTO flight_prices
                        (origin, destination, price, currency, airline, flight_number, stops,
                         departure_date, return_date, expires_at, fetched_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        origin, dest_code, info.get("price", 0), "USD",
                        info.get("airline", ""), info.get("flight_number", 0),
                        int(stop_key) if stop_key.isdigit() else 0,
                        info.get("departure_at", ""), info.get("return_at", ""),
                        info.get("expires_at", ""), now,
                    ))
                    total += 1
            time.sleep(0.5)
        except Exception as e:
            logger.error(f"[Aviasales] cheap {origin}-{dest}: {e}")
            continue

    db.commit()
    db.close()
    logger.info(f"[Aviasales] {origin} cheap prices: {total}건 저장")
    return total


def collect_popular_directions(origin="NYC"):
    """도시별 인기 방면 수집 -> popular_directions"""
    url = f"{BASE_URL}/v1/city-directions"
    params = {"origin": origin, "currency": "usd"}
    try:
        resp = requests.get(url, headers=_headers(), params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json().get("data", {})

        db = _get_db()
        count = 0
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for dest_code, info in data.items():
            db.execute("""
                INSERT INTO popular_directions
                (origin, destination, price, currency, airline, stops,
                 departure_date, return_date, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                origin, dest_code, info.get("price", 0), "USD",
                info.get("airline", ""), info.get("number_of_changes", 0),
                info.get("departure_at", ""), info.get("return_at", ""), now,
            ))
            count += 1
        db.commit()
        db.close()
        logger.info(f"[Aviasales] {origin} popular directions: {count}건 저장")
        return count
    except Exception as e:
        logger.error(f"[Aviasales] popular directions error ({origin}): {e}")
        return 0


def collect_calendar(origin="NYC", destination="TYO", month=None):
    """월별 일일 가격 수집 -> flight_calendar"""
    if month is None:
        month = datetime.now().strftime("%Y-%m")
    url = f"{BASE_URL}/v1/prices/calendar"
    params = {"origin": origin, "destination": destination, "month": month, "currency": "usd"}
    try:
        resp = requests.get(url, headers=_headers(), params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json().get("data", {})

        db = _get_db()
        count = 0
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for date_str, info in data.items():
            try:
                db.execute("""
                    INSERT OR REPLACE INTO flight_calendar
                    (origin, destination, date, price, currency, airline, stops, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    origin, destination, date_str, info.get("price", 0), "USD",
                    info.get("airline", ""), info.get("transfers", 0), now,
                ))
                count += 1
            except sqlite3.IntegrityError:
                pass
        db.commit()
        db.close()
        logger.info(f"[Aviasales] {origin}-{destination} calendar ({month}): {count}건 저장")
        return count
    except Exception as e:
        logger.error(f"[Aviasales] calendar error ({origin}-{destination}): {e}")
        return 0


def run_full_collection():
    """전체 수집 실행"""
    total = 0
    for origin in ORIGIN_CITIES:
        total += collect_latest_prices(origin)
        total += collect_popular_directions(origin)
        time.sleep(1)

    destinations = _get_destination_iata_codes()[:10]
    for origin in ORIGIN_CITIES[:5]:
        for iata, city, country in destinations:
            if iata and iata != origin:
                total += collect_calendar(origin, iata)
                time.sleep(0.5)

    logger.info(f"[Aviasales] 전체 수집 완료: {total}건")
    return total


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), ".env"))

    logging.basicConfig(level=logging.INFO)
    tok = _token()
    print(f"Token length: {len(tok)}, first 8: {tok[:8]}")
    if not tok:
        print("ERROR: TRAVELPAYOUTS_API_TOKEN not loaded!")
        sys.exit(1)

    count = collect_latest_prices("NYC", limit=10)
    print(f"NYC latest: {count}건")

    count2 = collect_popular_directions("NYC")
    print(f"NYC popular: {count2}건")

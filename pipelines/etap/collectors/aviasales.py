"""Aviasales 항공권 가격 수집기
- /v2/prices/latest: 최근 48시간 최저가
- /v1/prices/cheap: 노선별 최저가
- /v1/prices/calendar: 월별 일일 가격
- /v1/city-directions: 도시별 인기 방면
"""
import logging
import os
import sqlite3
import time
from datetime import datetime

import requests

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
    rows = db.execute("SELECT iata_code, city, country FROM destinations WHERE iata_code != ''").fetchall()
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
        logger.exception(f"[Aviasales] latest prices error ({origin}): {e}")
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
            logger.exception(f"[Aviasales] cheap {origin}-{dest}: {e}")
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
        logger.exception(f"[Aviasales] popular directions error ({origin}): {e}")
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
        logger.exception(f"[Aviasales] calendar error ({origin}-{destination}): {e}")
        return 0




def collect_direct_prices(origin="NYC", destinations=None):
    """직항 최저가 수집 -> flight_direct"""
    if destinations is None:
        destinations = [code for code, _, _ in _get_destination_iata_codes()]

    url = f"{BASE_URL}/v1/prices/direct"
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
                for info in stops_dict.values():
                    db.execute("""
                        INSERT INTO flight_direct
                        (origin, destination, price, currency, airline, flight_number,
                         departure_date, return_date, expires_at, fetched_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        origin, dest_code, info.get("price", 0), "USD",
                        info.get("airline", ""), info.get("flight_number", 0),
                        info.get("departure_at", ""), info.get("return_at", ""),
                        info.get("expires_at", ""), now,
                    ))
                    total += 1
            time.sleep(0.5)
        except Exception as e:
            logger.exception(f"[Aviasales] direct {origin}-{dest}: {e}")
    db.commit()
    db.close()
    logger.info(f"[Aviasales] {origin} direct prices: {total}건 저장")
    return total


def collect_monthly_prices(origin="NYC", destination="TYO"):
    """월별 최저가 수집 -> flight_monthly"""
    url = f"{BASE_URL}/v1/prices/monthly"
    params = {"origin": origin, "destination": destination, "currency": "usd"}
    try:
        resp = requests.get(url, headers=_headers(), params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json().get("data", {})
        db = _get_db()
        count = 0
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for month_str, info in data.items():
            try:
                db.execute("""
                    INSERT OR REPLACE INTO flight_monthly
                    (origin, destination, month, price, currency, airline, stops,
                     departure_date, return_date, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    origin, destination, month_str, info.get("price", 0), "USD",
                    info.get("airline", ""), info.get("transfers", 0),
                    info.get("departure_at", ""), info.get("return_at", ""), now,
                ))
                count += 1
            except Exception:
                pass
        db.commit()
        db.close()
        logger.info(f"[Aviasales] {origin}-{destination} monthly: {count}건 저장")
        return count
    except Exception as e:
        logger.exception(f"[Aviasales] monthly error ({origin}-{destination}): {e}")
        return 0


def collect_nearby_prices(origin="NYC", destination="TYO"):
    """인근 공항 대안 가격 수집 -> flight_nearby"""
    url = f"{BASE_URL}/v2/prices/nearest-places-matrix"
    params = {"origin": origin, "destination": destination, "currency": "usd", "show_to_affiliates": "true", "limit": 10}
    try:
        resp = requests.get(url, headers=_headers(), params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json().get("data", [])
        db = _get_db()
        count = 0
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for item in data:
            db.execute("""
                INSERT INTO flight_nearby
                (origin, destination, price, currency, stops, airline,
                 departure_date, return_date, distance, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                item.get("origin", ""), item.get("destination", ""),
                item.get("value", 0), "USD",
                item.get("number_of_changes", 0), "",
                item.get("depart_date", ""), item.get("return_date", ""),
                item.get("distance", 0), now,
            ))
            count += 1
        db.commit()
        db.close()
        logger.info(f"[Aviasales] {origin}-{destination} nearby: {count}건 저장")
        return count
    except Exception as e:
        logger.exception(f"[Aviasales] nearby error ({origin}-{destination}): {e}")
        return 0


def collect_airline_routes(airline_code="AA", limit=50):
    """항공사별 인기 노선 수집 -> airline_routes"""
    url = f"{BASE_URL}/v1/airline-directions"
    params = {"airline_code": airline_code, "limit": limit}
    try:
        resp = requests.get(url, headers=_headers(), params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json().get("data", {})
        db = _get_db()
        count = 0
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for route, popularity in data.items():
            parts = route.split("-")
            if len(parts) == 2:
                db.execute("""
                    INSERT INTO airline_routes
                    (airline, origin, destination, popularity, fetched_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (airline_code, parts[0], parts[1], popularity, now))
                count += 1
        db.commit()
        db.close()
        logger.info(f"[Aviasales] {airline_code} routes: {count}건 저장")
        return count
    except Exception as e:
        logger.exception(f"[Aviasales] airline routes error ({airline_code}): {e}")
        return 0

def run_full_collection():
    """전체 수집 실행"""
    total = 0
    destinations = _get_destination_iata_codes()

    # Phase 1: latest + popular + direct (10개 출발도시)
    for origin in ORIGIN_CITIES:
        total += collect_latest_prices(origin)
        total += collect_popular_directions(origin)
        time.sleep(1)

    # Phase 2: 직항 (상위 5개 출발도시 × 전체 도착지)
    for origin in ORIGIN_CITIES[:5]:
        total += collect_direct_prices(origin, [c for c, _, _ in destinations])
        time.sleep(1)

    # Phase 3: 캘린더 + 월별 + 인근공항 (상위 5개 × 상위 10개)
    top_dests = destinations[:10]
    for origin in ORIGIN_CITIES[:5]:
        for iata, _city, _country in top_dests:
            if iata and iata != origin:
                total += collect_calendar(origin, iata)
                total += collect_monthly_prices(origin, iata)
                total += collect_nearby_prices(origin, iata)
                time.sleep(0.5)

    # Phase 4: 주요 항공사 인기 노선
    major_airlines = ["AA", "UA", "DL", "WN", "B6", "NK", "F9", "AS",
                      "BA", "LH", "AF", "EK", "SQ", "CX", "NH", "JL",
                      "TG", "QR", "TK", "KE", "OZ"]
    for airline in major_airlines:
        total += collect_airline_routes(airline, limit=30)
        time.sleep(0.3)

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

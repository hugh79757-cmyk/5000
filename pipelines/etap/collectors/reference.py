"""
Aviasales 레퍼런스 데이터 수집기 (인증 불필요)
- 공항, 항공사, 도시, 국가 JSON
"""
import os
import sqlite3
import logging
import requests

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "data", "travel-en.db"
)

BASE = "https://api.travelpayouts.com/data"


def _get_db():
    return sqlite3.connect(DB_PATH)


def collect_airports():
    """전 세계 공항 목록 수집"""
    try:
        resp = requests.get(f"{BASE}/en/airports.json", timeout=30)
        resp.raise_for_status()
        data = resp.json()
        db = _get_db()
        count = 0
        for a in data:
            code = a.get("code", "")
            if not code:
                continue
            db.execute("""
                INSERT OR REPLACE INTO ref_airports
                (iata, name, city_code, country_code, lat, lng, timezone)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                code, a.get("name", ""), a.get("city_code", ""),
                a.get("country_code", ""),
                a.get("coordinates", {}).get("lat", 0),
                a.get("coordinates", {}).get("lon", 0),
                a.get("time_zone", ""),
            ))
            count += 1
        db.commit()
        db.close()
        logger.info(f"[Reference] airports: {count}건")
        return count
    except Exception as e:
        logger.error(f"[Reference] airports error: {e}")
        return 0


def collect_airlines():
    """전 세계 항공사 목록 수집"""
    try:
        resp = requests.get(f"{BASE}/en/airlines.json", timeout=30)
        resp.raise_for_status()
        data = resp.json()
        db = _get_db()
        count = 0
        for a in data:
            code = a.get("code", "")
            if not code:
                continue
            db.execute("""
                INSERT OR REPLACE INTO ref_airlines
                (iata, name, country_code, is_lowcost)
                VALUES (?, ?, ?, ?)
            """, (
                code, a.get("name", ""), a.get("country_code", ""),
                1 if a.get("is_lowcost", False) else 0,
            ))
            count += 1
        db.commit()
        db.close()
        logger.info(f"[Reference] airlines: {count}건")
        return count
    except Exception as e:
        logger.error(f"[Reference] airlines error: {e}")
        return 0


def collect_cities():
    """전 세계 도시 목록 수집"""
    try:
        resp = requests.get(f"{BASE}/en/cities.json", timeout=30)
        resp.raise_for_status()
        data = resp.json()
        db = _get_db()
        count = 0
        for c_item in data:
            code = c_item.get("code", "")
            if not code:
                continue
            db.execute("""
                INSERT OR REPLACE INTO ref_cities
                (code, name, country_code, lat, lng, timezone)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                code, c_item.get("name", ""), c_item.get("country_code", ""),
                c_item.get("coordinates", {}).get("lat", 0),
                c_item.get("coordinates", {}).get("lon", 0),
                c_item.get("time_zone", ""),
            ))
            count += 1
        db.commit()
        db.close()
        logger.info(f"[Reference] cities: {count}건")
        return count
    except Exception as e:
        logger.error(f"[Reference] cities error: {e}")
        return 0


def collect_countries():
    """전 세계 국가 목록 수집"""
    try:
        resp = requests.get(f"{BASE}/en/countries.json", timeout=30)
        resp.raise_for_status()
        data = resp.json()
        db = _get_db()
        count = 0
        for c_item in data:
            code = c_item.get("code", "")
            if not code:
                continue
            db.execute("""
                INSERT OR REPLACE INTO ref_countries
                (code, name, currency)
                VALUES (?, ?, ?)
            """, (
                code, c_item.get("name", ""), c_item.get("currency", ""),
            ))
            count += 1
        db.commit()
        db.close()
        logger.info(f"[Reference] countries: {count}건")
        return count
    except Exception as e:
        logger.error(f"[Reference] countries error: {e}")
        return 0


def run_full_reference():
    """전체 레퍼런스 수집"""
    total = 0
    total += collect_airports()
    total += collect_airlines()
    total += collect_cities()
    total += collect_countries()
    logger.info(f"[Reference] 전체 수집 완료: {total}건")
    return total


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    total = run_full_reference()
    print(f"Reference data: {total}건")

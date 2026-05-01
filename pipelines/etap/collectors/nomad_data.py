#!/usr/bin/env python3
"""nomad 데이터 주간 수집기 - 코워킹/기후/카페 (Overpass + Open-Meteo)
Numbeo는 rate-limit 심해서 별도 실행"""
import sqlite3, requests, time, re, logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DB = "/Users/twinssn/Projects/5000/data/travel-en.db"
NOMINATIM = "https://nominatim.openstreetmap.org/search"
OVERPASS = "https://overpass-api.de/api/interpreter"
HEADERS = {"User-Agent": "ETAP-NomadCollector/1.0"}


def _geocode(city, country):
    try:
        resp = requests.get(NOMINATIM, params={"q": f"{city}, {country}", "format": "json", "limit": 1},
                            headers=HEADERS, timeout=10)
        if resp.status_code == 200 and resp.json():
            r = resp.json()[0]
            return float(r["lat"]), float(r["lon"])
    except:
        pass
    return None, None


def _overpass_query(lat, lon, radius, tags):
    filters = "\n".join([f'node[{t}](around:{radius},{lat},{lon});way[{t}](around:{radius},{lat},{lon});'
                         for t in tags])
    query = f"[out:json][timeout:60];({filters});out body;"
    try:
        resp = requests.get(OVERPASS, params={"data": query}, timeout=90)
        if resp.status_code == 429:
            logger.warning("Overpass 429, 30s 대기")
            time.sleep(30)
            resp = requests.get(OVERPASS, params={"data": query}, timeout=90)
        if resp.status_code == 200:
            return resp.json().get("elements", [])
    except:
        pass
    return []


def collect_coworking(conn, cities):
    logger.info("=== 코워킹 수집 시작 ===")
    existing = set(r[0] for r in conn.execute("SELECT DISTINCT city FROM coworking_spaces").fetchall())
    added = 0
    for city, country in cities:
        if city in existing:
            continue
        lat, lon = _geocode(city, country)
        if not lat:
            continue
        time.sleep(1.5)
        elements = _overpass_query(lat, lon, 25000,
                                   ['"amenity"="coworking_space"', '"office"="coworking"'])
        time.sleep(3)
        for el in elements:
            tags = el.get("tags", {})
            try:
                conn.execute("""INSERT OR IGNORE INTO coworking_spaces
                    (osm_id,osm_type,name,city,country,lat,lon,address,phone,website,
                     opening_hours,internet_access,operator,wheelchair,fee)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (el["id"], el.get("type","node"), tags.get("name",""),
                     city, country, el.get("lat"), el.get("lon"),
                     " ".join(filter(None, [tags.get("addr:street",""), tags.get("addr:housenumber","")])),
                     tags.get("phone",""), tags.get("website",""),
                     tags.get("opening_hours",""), tags.get("internet_access",""),
                     tags.get("operator",""), tags.get("wheelchair",""), tags.get("fee","")))
                added += 1
            except:
                pass
        conn.commit()
    logger.info(f"코워킹 신규: {added}건")


def collect_cafes(conn, cities):
    logger.info("=== 카페 수집 시작 ===")
    existing = set(r[0] for r in conn.execute("SELECT DISTINCT city FROM nomad_cafes").fetchall())
    added = 0
    for city, country in cities:
        if city in existing:
            continue
        lat, lon = _geocode(city, country)
        if not lat:
            continue
        time.sleep(1.5)
        elements = _overpass_query(lat, lon, 15000,
                                   ['"amenity"="cafe""internet_access"~"yes|wlan|wifi"'])
        time.sleep(3)
        for el in elements:
            tags = el.get("tags", {})
            try:
                conn.execute("""INSERT OR IGNORE INTO nomad_cafes
                    (osm_id,osm_type,name,city,country,lat,lon,address,phone,website,
                     opening_hours,internet_access,cuisine,wheelchair)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (el["id"], el.get("type","node"), tags.get("name",""),
                     city, country, el.get("lat"), el.get("lon"),
                     " ".join(filter(None, [tags.get("addr:street",""), tags.get("addr:housenumber","")])),
                     tags.get("phone",""), tags.get("website",""),
                     tags.get("opening_hours",""), tags.get("internet_access",""),
                     tags.get("cuisine",""), tags.get("wheelchair","")))
                added += 1
            except:
                pass
        conn.commit()
    logger.info(f"카페 신규: {added}건")


def collect_climate(conn, cities):
    logger.info("=== 기후 수집 시작 ===")
    existing = set(r[0] for r in conn.execute("SELECT DISTINCT city FROM nomad_climate").fetchall())
    added = 0
    for city, country in cities:
        if city in existing:
            continue
        lat, lon = _geocode(city, country)
        if not lat:
            continue
        time.sleep(1)
        try:
            resp = requests.get("https://climate-api.open-meteo.com/v1/climate", params={
                "latitude": lat, "longitude": lon,
                "models": "EC_Earth3P_HR",
                "monthly": "temperature_2m_mean,precipitation_sum,relative_humidity_2m_mean",
                "start_date": "2020-01-01", "end_date": "2020-12-31"
            }, timeout=15)
            if resp.status_code != 200:
                continue
            data = resp.json().get("monthly", {})
            temps = data.get("temperature_2m_mean", [])
            precip = data.get("precipitation_sum", [])
            humid = data.get("relative_humidity_2m_mean", [])
            for month in range(min(12, len(temps))):
                conn.execute("""INSERT OR IGNORE INTO nomad_climate
                    (city,country,month,avg_temp,precipitation,humidity,lat,lon)
                    VALUES (?,?,?,?,?,?,?,?)""",
                    (city, country, month+1,
                     round(temps[month], 1) if temps[month] else None,
                     round(precip[month], 1) if precip[month] else None,
                     round(humid[month], 1) if humid[month] else None,
                     lat, lon))
                added += 1
            conn.commit()
        except:
            pass
    logger.info(f"기후 신규: {added}건")


def main():
    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA journal_mode=WAL")
    cities = conn.execute("SELECT DISTINCT city, country FROM nomad_topics ORDER BY priority").fetchall()
    logger.info(f"대상 도시: {len(cities)}개")

    collect_coworking(conn, cities)
    collect_cafes(conn, cities)
    collect_climate(conn, cities)

    # 최종 현황
    for table in ["coworking_spaces", "nomad_cafes", "nomad_climate", "nomad_cost_of_living"]:
        cnt = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        cities_cnt = conn.execute(f"SELECT COUNT(DISTINCT city) FROM {table}").fetchone()[0]
        logger.info(f"{table}: {cnt}건, {cities_cnt}개 도시")
    conn.close()


if __name__ == "__main__":
    main()

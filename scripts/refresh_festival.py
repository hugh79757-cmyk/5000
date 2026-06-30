#!/usr/bin/env python3
"""scripts/refresh_festival.py — TourAPI searchFestival2로 festival.db 신규 데이터 갱신

실행: python3 scripts/refresh_festival.py
스케줄: scheduler.py에서 매일 06:00 자동 실행
"""
import logging
import os
import sqlite3
import sys
from datetime import datetime

sys.path.insert(0, os.getenv("TAP_ROOT", "/Users/twinssn/Projects/TAP"))
os.chdir(os.getenv("TAP_ROOT", "/Users/twinssn/Projects/TAP"))
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("refresh_festival")

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "festival.db")

def fetch_api_festivals():
    import requests as req
    key = os.getenv("TOUR_API_KEY", "") or os.getenv("DATA_GO_KR_API_KEY", "")
    if not key:
        logger.error("TOUR_API_KEY not found")
        return []
    today = datetime.now().strftime("%Y%m%d")
    all_items = []
    page_no = 1
    while True:
        resp = req.get(
            "http://apis.data.go.kr/B551011/KorService2/searchFestival2",
            params={
                "serviceKey": key,
                "MobileOS": "ETC",
                "MobileApp": "TAP",
                "_type": "json",
                "numOfRows": 200,
                "pageNo": page_no,
                "eventStartDate": today,
                "arrange": "Q",
            },
            timeout=30,
        )
        data = resp.json()
        items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
        if isinstance(items, dict):
            items = [items]
        if not items:
            break
        all_items.extend(items)
        total_count = data.get("response", {}).get("body", {}).get("totalCount", 0)
        if len(all_items) >= total_count:
            break
        page_no += 1
    logger.info(f"API total: {len(all_items)}건")
    return all_items


def main() -> None:
    items = fetch_api_festivals()
    if not items:
        logger.warning("API 응답 없음")
        return

    conn = sqlite3.connect(DB_PATH)
    existing_ids = {str(r[0]) for r in conn.execute("SELECT contentid FROM festivals").fetchall()}

    new_count = 0
    for item in items:
        cid = str(item.get("contentid", "")).strip()
        if not cid or cid in existing_ids:
            continue
        conn.execute("""
            INSERT OR IGNORE INTO festivals
                (contentid, title, addr1, addr2, areacode, sigungucode,
                 mapx, mapy, firstimage, firstimage2, tel,
                 eventstartdate, eventenddate, playtime, eventplace,
                 usetimefestival, sponsor1, program, subevent, agelimit)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            cid,
            item.get("title", ""),
            item.get("addr1", ""),
            item.get("addr2", ""),
            item.get("areacode", ""),
            item.get("sigungucode", ""),
            item.get("mapx", ""),
            item.get("mapy", ""),
            item.get("firstimage", ""),
            item.get("firstimage2", ""),
            item.get("tel", ""),
            item.get("eventstartdate", ""),
            item.get("eventenddate", ""),
            item.get("playtime", ""),
            item.get("eventplace", ""),
            item.get("usetimefestival", ""),
            item.get("sponsor1", ""),
            item.get("program", ""),
            item.get("subevent", ""),
            item.get("agelimit", ""),
        ))
        new_count += 1
        existing_ids.add(cid)

    conn.commit()

    now_count = conn.execute("SELECT COUNT(*) FROM festivals").fetchone()[0]
    future_count = conn.execute(
        "SELECT COUNT(*) FROM festivals WHERE eventstartdate >= ?",
        (datetime.now().strftime("%Y%m%d"),)
    ).fetchone()[0]

    conn.close()
    logger.info(f"신규 추가: {new_count}건 (총 {now_count}건, 미래 {future_count}건)")


if __name__ == "__main__":
    main()

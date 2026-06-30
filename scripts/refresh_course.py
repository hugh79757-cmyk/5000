#!/usr/bin/env python3
"""scripts/refresh_course.py — TourAPI contentTypeId=25(여행코스) 목록 캐싱

실행: python3 scripts/refresh_course.py
스케줄: scheduler.py에서 매주 월요일 06:30 자동 실행

 overview/sub는 발행 시점에 On-demand로 가져옵니다 (API 호출 횟수 절약).
"""
import logging
import os
import sqlite3
import sys
import time

sys.path.insert(0, os.getenv("TAP_ROOT", "/Users/twinssn/Projects/TAP"))
os.chdir(os.getenv("TAP_ROOT", "/Users/twinssn/Projects/TAP"))
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("refresh_course")

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "course.db")

AREA_CODES = {
    "서울": 1, "인천": 2, "대전": 3, "대구": 4, "광주": 5,
    "부산": 6, "울산": 7, "세종": 8, "경기": 31, "강원": 32,
    "충북": 33, "충남": 34, "경북": 35, "경남": 36,
    "전북": 37, "전남": 38, "제주": 39,
}


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS courses (
            contentid TEXT PRIMARY KEY,
            title TEXT,
            addr1 TEXT, addr2 TEXT,
            areacode TEXT, sigungucode TEXT,
            mapx TEXT, mapy TEXT,
            firstimage TEXT, firstimage2 TEXT,
            cat1 TEXT, cat2 TEXT, cat3 TEXT,
            tel TEXT,
            createdtime TEXT, modifiedtime TEXT,
            overview TEXT,
            fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    return conn


def fetch_courses_for_area(key, area_code, area_name):
    import requests as req
    all_items = []
    page_no = 1
    while True:
        try:
            resp = req.get(
                "http://apis.data.go.kr/B551011/KorService2/areaBasedList2",
                params={
                    "serviceKey": key, "MobileOS": "ETC", "MobileApp": "TAP",
                    "_type": "json", "numOfRows": 100, "pageNo": page_no,
                    "contentTypeId": 25, "areaCode": area_code, "arrange": "C",
                },
                timeout=15,
            )
            data = resp.json()
            header = data.get("response", {}).get("header", {})
            if header.get("resultCode") != "0000":
                logger.warning(f"API error for {area_name}: {header}")
                break
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
            time.sleep(0.3)
        except Exception as e:
            logger.warning(f"fetch error for {area_name} page {page_no}: {e}")
            break
    return all_items


def main() -> None:
    key = os.getenv("TOUR_API_KEY", "") or os.getenv("DATA_GO_KR_API_KEY", "")
    if not key:
        logger.error("TOUR_API_KEY not found")
        return

    conn = init_db()
    existing_ids = {row[0] for row in conn.execute("SELECT contentid FROM courses").fetchall()}
    logger.info(f"기존 코스: {len(existing_ids)}건")

    new_count = 0

    for area_name, area_code in AREA_CODES.items():
        logger.info(f"[{area_name}] 코스 목록 조회 중...")
        items = fetch_courses_for_area(key, area_code, area_name)
        logger.info(f"[{area_name}] {len(items)}건 조회")

        for item in items:
            cid = str(item.get("contentid", ""))
            if not cid or cid in existing_ids:
                continue

            conn.execute("""
                INSERT OR IGNORE INTO courses
                (contentid, title, addr1, addr2, areacode, sigungucode,
                 mapx, mapy, firstimage, firstimage2, cat1, cat2, cat3,
                 tel, createdtime, modifiedtime)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                cid, item.get("title", ""),
                item.get("addr1", ""), item.get("addr2", ""),
                item.get("areacode", ""), item.get("sigungucode", ""),
                item.get("mapx", ""), item.get("mapy", ""),
                item.get("firstimage", ""), item.get("firstimage2", ""),
                item.get("cat1", ""), item.get("cat2", ""), item.get("cat3", ""),
                item.get("tel", ""), item.get("createdtime", ""), item.get("modifiedtime", ""),
            ))
            new_count += 1
            existing_ids.add(cid)

        conn.commit()

    total = conn.execute("SELECT COUNT(*) FROM courses").fetchone()[0]
    with_img = conn.execute("SELECT COUNT(*) FROM courses WHERE firstimage != '' AND firstimage IS NOT NULL").fetchone()[0]
    conn.close()
    logger.info(f"=== 완료: 신규 {new_count}건, 전체 {total}건 (이미지 있음: {with_img}건) ===")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""festival.db 일일 갱신 — searchFestival2 + detailIntro2"""
import os, sys, sqlite3, time, logging, requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.getenv("TAP_ROOT", "/Users/twinssn/Projects/TAP"), ".env"))
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

logger = logging.getLogger("festival_refresh")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "festival.db")
KEY = os.getenv("TOUR_API_KEY", "")

SIDO_ALIAS = {
    "서울특별시": ("1", "서울"), "부산광역시": ("6", "부산"), "대구광역시": ("4", "대구"),
    "인천광역시": ("2", "인천"), "광주광역시": ("5", "광주"), "대전광역시": ("3", "대전"),
    "울산광역시": ("7", "울산"), "세종특별자치시": ("8", "세종"),
    "경기도": ("31", "경기"), "강원특별자치도": ("32", "강원"), "강원도": ("32", "강원"),
    "충청북도": ("33", "충북"), "충청남도": ("34", "충남"),
    "전라북도": ("37", "전북"), "전북특별자치도": ("37", "전북"),
    "전라남도": ("38", "전남"), "경상북도": ("35", "경북"), "경상남도": ("36", "경남"),
    "제주특별자치도": ("39", "제주"),
}


def _parse_area(addr1):
    if not addr1:
        return "", ""
    parts = addr1.split()
    if not parts:
        return "", ""
    code, _ = SIDO_ALIAS.get(parts[0], ("", ""))
    sigungu = parts[1] if len(parts) >= 2 else ""
    return code, sigungu


def refresh():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS festivals (
            contentid TEXT PRIMARY KEY,
            title TEXT, addr1 TEXT, addr2 TEXT,
            areacode TEXT, sigungucode TEXT,
            mapx TEXT, mapy TEXT,
            firstimage TEXT, firstimage2 TEXT, tel TEXT,
            eventstartdate TEXT, eventenddate TEXT,
            playtime TEXT, eventplace TEXT, usetimefestival TEXT,
            sponsor1 TEXT, program TEXT, subevent TEXT, agelimit TEXT,
            fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    from datetime import datetime
    year = datetime.now().strftime("%Y")
    page = 1
    total_saved = 0

    while True:
        r = requests.get(
            "http://apis.data.go.kr/B551011/KorService2/searchFestival2",
            params={
                "serviceKey": KEY, "MobileOS": "ETC", "MobileApp": "TAP",
                "_type": "json", "numOfRows": 100, "pageNo": page,
                "eventStartDate": year + "0101",
            },
            timeout=15,
        )
        data = r.json()
        total_count = data.get("response", {}).get("body", {}).get("totalCount", 0)
        items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
        if isinstance(items, dict):
            items = [items]
        if not items:
            break

        logger.info(f"page {page}: {len(items)}건 (전체 {total_count}건)")

        for item in items:
            cid = item.get("contentid", "")
            try:
                dr = requests.get(
                    "http://apis.data.go.kr/B551011/KorService2/detailIntro2",
                    params={
                        "serviceKey": KEY, "MobileOS": "ETC", "MobileApp": "TAP",
                        "_type": "json", "contentId": cid, "contentTypeId": 15,
                    },
                    timeout=10,
                )
                intro = dr.json().get("response", {}).get("body", {}).get("items", {}).get("item", [])
                if isinstance(intro, dict):
                    intro = [intro]
                if intro:
                    det = intro[0]
                    for k in ("eventstartdate", "eventenddate", "playtime", "eventplace",
                              "usetimefestival", "sponsor1", "program", "subevent", "agelimit"):
                        item[k] = det.get(k, "") or item.get(k, "")
            except Exception:
                pass

            areacode, sigungu = _parse_area(item.get("addr1", ""))

            conn.execute("""
                INSERT OR REPLACE INTO festivals
                (contentid, title, addr1, addr2, areacode, sigungucode, mapx, mapy,
                 firstimage, firstimage2, tel, eventstartdate, eventenddate,
                 playtime, eventplace, usetimefestival, sponsor1, program, subevent, agelimit)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                cid, item.get("title", ""), item.get("addr1", ""), item.get("addr2", ""),
                areacode, sigungu,
                item.get("mapx", ""), item.get("mapy", ""),
                item.get("firstimage", ""), item.get("firstimage2", ""),
                item.get("tel", ""),
                item.get("eventstartdate", ""), item.get("eventenddate", ""),
                item.get("playtime", ""), item.get("eventplace", ""),
                item.get("usetimefestival", ""), item.get("sponsor1", ""),
                item.get("program", ""), item.get("subevent", ""),
                item.get("agelimit", ""),
            ))
            total_saved += 1

        conn.commit()
        if page * 100 >= total_count:
            break
        page += 1
        time.sleep(0.3)

    conn.close()
    logger.info(f"festival refresh 완료: {total_saved}건")
    return total_saved


if __name__ == "__main__":
    refresh()

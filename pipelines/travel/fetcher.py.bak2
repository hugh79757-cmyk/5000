import sys
import os
import random
import logging

sys.path.insert(0, "/Users/twinssn/Projects/tour-auto-publisher")
os.chdir("/Users/twinssn/Projects/tour-auto-publisher")

from dotenv import load_dotenv
load_dotenv("/Users/twinssn/Projects/tour-auto-publisher/.env")

logger = logging.getLogger(__name__)


def _safe_region(addr_str):
    if not addr_str or not addr_str.strip():
        return ""
    parts = addr_str.strip().split()
    return parts[0] if parts else ""


def _adapt_korservice_items(items_raw):
    from core.naver_map import get_naver_map_link
    adapted = []
    for item in items_raw:
        title_val = item.get("title", "")
        addr_val = item.get("addr1", item.get("baseAddr", ""))
        adapted.append({
            "facltNm": title_val,
            "title": title_val,
            "addr": addr_val,
            "addr1": addr_val,
            "firstImageUrl": item.get("firstimage", item.get("orgImage", "")),
            "firstimage": item.get("firstimage", item.get("orgImage", "")),
            "image": item.get("firstimage", item.get("orgImage", "")),
            "mapX": str(item.get("mapx", item.get("mapX", ""))),
            "mapY": str(item.get("mapy", item.get("mapY", ""))),
            "map_url": get_naver_map_link(title_val),
            "tel": item.get("tel", ""),
            "homepage": item.get("homepage", ""),
            "contentid": item.get("contentid", item.get("contentId", "")),
            "contenttypeid": str(item.get("contenttypeid", "")),
            "overview": item.get("overview", ""),
            "_raw": item,
        })
    return adapted


def fetch_camping():
    from core.camping_data import get_camping_data, get_random_theme
    theme_name, theme_conf = get_random_theme()
    logger.info("camping theme: " + theme_name)
    data = get_camping_data(theme_name, theme_conf=theme_conf)
    if not data:
        data = get_camping_data("글램핑")
    if not data:
        return None
    data["category"] = "캠핑"
    if not data.get("angle"):
        data["angle"] = theme_name
    data["source_type"] = "camping"
    return data


def fetch_korservice():
    from core.korservice_data import get_korservice_data
    ks = get_korservice_data()
    if not ks:
        return None
    adapted_items = _adapt_korservice_items(ks.get("items", []))
    search_details = ks.get("search_details", [])
    search_detail = random.choice(search_details) if search_details else ""
    return {
        "items": adapted_items,
        "display_region": ks.get("region", ""),
        "sigungu": ks.get("region", ""),
        "do_name": ks.get("region", ""),
        "theme": ks.get("theme_name", ""),
        "category": ks.get("category", "관광지"),
        "angle": search_detail if search_detail else ks.get("theme_name", ""),
        "source_type": "korservice",
        "season": ks.get("season", ""),
        "keywords": ks.get("keywords", []),
    }




# Filtered korservice fetchers for blog-specific topics
HERITAGE_TYPES = {"12", "14"}  # 12=tourist, 14=cultural
HERITAGE_KEYWORDS = {"국보", "보물", "사적", "유산", "문화재", "사찰", "고궁", "서원", "탑", "성곽", "역사"}

def fetch_korservice_heritage():
    """fetch_korservice filtered for cultural heritage content"""
    for _ in range(5):
        data = fetch_korservice()
        if not data:
            continue
        theme = data.get("theme", "")
        category = data.get("category", "")
        items = data.get("items", [])
        # Check content type or theme/keyword match
        type_match = any(i.get("contenttypeid", "") in HERITAGE_TYPES for i in items)
        keyword_match = any(k in theme for k in HERITAGE_KEYWORDS)
        cat_match = any(k in category for k in HERITAGE_KEYWORDS)
        if type_match or keyword_match or cat_match:
            return data
        logger.info("korservice_heritage: skipped theme '%s', retrying", theme)
    logger.warning("korservice_heritage: 5 retries exhausted, using fetch_heritage fallback")
    return fetch_heritage()


def fetch_festival():
    import requests as req
    AREA_CODES = {
        "서울": 1, "인천": 2, "대전": 3, "대구": 4, "광주": 5,
        "부산": 6, "울산": 7, "세종": 8, "경기": 31, "강원": 32,
        "충북": 33, "충남": 34, "경북": 35, "경남": 36,
        "전북": 37, "전남": 38, "제주": 39,
    }
    region_name = random.choice(list(AREA_CODES.keys()))
    area_code = AREA_CODES[region_name]
    key = os.getenv("TOUR_API_KEY", "")
    try:
        resp = req.get(
            "http://apis.data.go.kr/B551011/KorService2/areaBasedList2",
            params={
                "serviceKey": key,
                "MobileOS": "ETC",
                "MobileApp": "TAP",
                "_type": "json",
                "numOfRows": 20,
                "pageNo": 1,
                "contentTypeId": 15,
                "areaCode": area_code,
                "arrange": "C",
            },
            timeout=15,
        )
        data = resp.json()
        header = data.get("response", {}).get("header", {})
        if header.get("resultCode") != "0000":
            logger.warning("festival API error: " + str(header))
            return None
        items_raw = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
        if isinstance(items_raw, dict):
            items_raw = [items_raw]
        if not items_raw:
            logger.warning("festival: no data for " + region_name)
            return None
        selected = random.sample(items_raw, min(5, len(items_raw)))
        adapted = _adapt_korservice_items(selected)
        return {
            "items": adapted,
            "display_region": region_name,
            "sigungu": region_name,
            "do_name": region_name,
            "theme": "축제·행사",
            "category": "축제",
            "angle": "축제·행사",
            "source_type": "korservice",
        }
    except Exception as e:
        logger.warning("festival fetch failed: " + str(e))
        return None


def fetch_food():
    import requests as req
    AREA_CODES = {
        "서울": 1, "인천": 2, "대전": 3, "대구": 4, "광주": 5,
        "부산": 6, "울산": 7, "세종": 8, "경기": 31, "강원": 32,
        "충북": 33, "충남": 34, "경북": 35, "경남": 36,
        "전북": 37, "전남": 38, "제주": 39,
    }
    region_name = random.choice(list(AREA_CODES.keys()))
    area_code = AREA_CODES[region_name]
    keywords = ["맛집", "한정식", "해물", "고기", "국밥", "칼국수", "냉면", "떡볶이", "카페"]
    keyword = random.choice(keywords)
    key = os.getenv("TOUR_API_KEY", "")
    try:
        resp = req.get(
            "http://apis.data.go.kr/B551011/KorService2/areaBasedList2",
            params={
                "serviceKey": key,
                "MobileOS": "ETC",
                "MobileApp": "TAP",
                "_type": "json",
                "numOfRows": 20,
                "pageNo": 1,
                "contentTypeId": 39,
                "areaCode": area_code,
                "arrange": "C",
            },
            timeout=15,
        )
        data = resp.json()
        header = data.get("response", {}).get("header", {})
        if header.get("resultCode") != "0000":
            logger.warning("food API error: " + str(header))
            return None
        items_raw = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
        if isinstance(items_raw, dict):
            items_raw = [items_raw]
        if not items_raw:
            logger.warning("food: no data for " + region_name)
            return None
        selected = random.sample(items_raw, min(5, len(items_raw)))
        adapted = _adapt_korservice_items(selected)
        return {
            "items": adapted,
            "display_region": region_name,
            "sigungu": region_name,
            "do_name": region_name,
            "theme": keyword,
            "category": "맛집",
            "angle": region_name + " " + keyword,
            "source_type": "korservice",
        }
    except Exception as e:
        logger.warning("food fetch failed: " + str(e))
        return None


def fetch_course():
    import requests as req
    AREA_CODES = {
        "서울": 1, "인천": 2, "대전": 3, "대구": 4, "광주": 5,
        "부산": 6, "울산": 7, "세종": 8, "경기": 31, "강원": 32,
        "충북": 33, "충남": 34, "경북": 35, "경남": 36,
        "전북": 37, "전남": 38, "제주": 39,
    }
    region_name = random.choice(list(AREA_CODES.keys()))
    area_code = AREA_CODES[region_name]
    key = os.getenv("TOUR_API_KEY", "")
    try:
        resp = req.get(
            "http://apis.data.go.kr/B551011/KorService2/areaBasedList2",
            params={
                "serviceKey": key,
                "MobileOS": "ETC",
                "MobileApp": "TAP",
                "_type": "json",
                "numOfRows": 20,
                "pageNo": 1,
                "contentTypeId": 25,
                "areaCode": area_code,
                "arrange": "C",
            },
            timeout=15,
        )
        data = resp.json()
        header = data.get("response", {}).get("header", {})
        if header.get("resultCode") != "0000":
            logger.warning("course API error: " + str(header))
            return None
        items_raw = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
        if isinstance(items_raw, dict):
            items_raw = [items_raw]
        if not items_raw:
            logger.warning("course: no data for " + region_name)
            return None
        selected = random.sample(items_raw, min(5, len(items_raw)))
        adapted = _adapt_korservice_items(selected)
        return {
            "items": adapted,
            "display_region": region_name,
            "sigungu": region_name,
            "do_name": region_name,
            "theme": "여행코스",
            "category": "여행코스",
            "angle": region_name + " 여행코스",
            "source_type": "korservice",
        }
    except Exception as e:
        logger.warning("course fetch failed: " + str(e))
        return None


def fetch_wellness():
    from core.wellness_api import WellnessAPI
    api = WellnessAPI()
    try:
        params = {"numOfRows": 50, "pageNo": 1}
        data = api._request("areaBasedList", params)
        items_raw = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
        if isinstance(items_raw, dict):
            items_raw = [items_raw]
        if not items_raw:
            return None
        selected = random.sample(items_raw, min(5, len(items_raw)))
        items = []
        for item in selected:
            items.append({
                "title": item.get("title", ""),
                "addr": item.get("addr1", ""),
                "addr1": item.get("addr1", ""),
                "firstimage": item.get("firstimage", ""),
                "image": item.get("firstimage", ""),
                "overview": item.get("overview", ""),
                "tel": item.get("tel", ""),
                "_raw": item,
            })
        region = _safe_region(items[0].get("addr", "")) if items else ""
        return {
            "items": items,
            "display_region": region,
            "sigungu": region,
            "do_name": region,
            "theme": "웰니스 여행",
            "category": "웰니스",
            "angle": "웰니스 여행",
            "source_type": "wellness",
        }
    except Exception as e:
        logger.warning("wellness fetch failed: " + str(e))
        return None


def fetch_heritage():
    import requests, random
    key = os.getenv("TOUR_API_KEY", "")
    if not key:
        logger.error("TOUR_API_KEY not set")
        return None

    area_codes = {
        "서울": 1, "인천": 2, "대전": 3, "대구": 4, "광주": 5,
        "부산": 6, "울산": 7, "세종": 8, "경기": 31, "강원": 32,
        "충북": 33, "충남": 34, "경북": 35, "경남": 36, "전북": 37,
        "전남": 38, "제주": 39,
    }
    region_name, area_code = random.choice(list(area_codes.items()))

    try:
        resp = requests.get(
            "http://apis.data.go.kr/B551011/KorService2/areaBasedList2",
            params={
                "serviceKey": key,
                "MobileOS": "ETC",
                "MobileApp": "TAP",
                "_type": "json",
                "numOfRows": 50,
                "pageNo": 1,
                "contentTypeId": 12,
                "areaCode": area_code,
                "arrange": "C",
            },
            timeout=15,
        )
        data = resp.json()
        header = data.get("response", {}).get("header", {})
        if header.get("resultCode") != "0000":
            logger.warning(f"heritage API: {header.get('resultCode')} {header.get('resultMsg')}")
            return None

        body = data.get("response", {}).get("body", {})
        items_wrapper = body.get("items", "")
        if not items_wrapper or isinstance(items_wrapper, str):
            logger.warning(f"heritage: empty items for {region_name}")
            return None

        raw_items = items_wrapper.get("item", [])
        if isinstance(raw_items, dict):
            raw_items = [raw_items]
        if not raw_items:
            logger.warning(f"heritage: no items for {region_name}")
            return None

        with_img = [i for i in raw_items if i.get("firstimage")]
        pool = with_img if len(with_img) >= 3 else raw_items
        selected = random.sample(pool, min(5, len(pool)))

        heritage_themes = ["국보 탐방", "보물 탐방", "사적 탐방", "문화유산 투어"]
        theme = random.choice(heritage_themes)

        items = []
        for raw in selected:
            items.append({
                "title": raw.get("title", ""),
                "addr": raw.get("addr1", ""),
                "addr1": raw.get("addr1", ""),
                "firstimage": raw.get("firstimage", ""),
                "firstImageUrl": raw.get("firstimage", ""),
                "image": raw.get("firstimage2", raw.get("firstimage", "")),
                "overview": "",
                "tel": raw.get("tel", ""),
                "contentid": raw.get("contentid", ""),
                "contenttypeid": raw.get("contenttypeid", ""),
                "mapx": raw.get("mapx", ""),
                "mapy": raw.get("mapy", ""),
                "_raw": raw,
            })

        return {
            "items": items,
            "source_type": "heritage",
            "theme": theme,
            "category": "문화유산",
            "display_region": region_name,
            "sigungu": "",
            "angle": theme,
        }
    except Exception as e:
        logger.error(f"heritage fetch error: {e}")
        return None


def fetch_random():
    sources = [
        (0.35, fetch_korservice),
        (0.30, fetch_camping),
        (0.15, fetch_heritage),
        (0.10, fetch_wellness),
        (0.10, fetch_festival),
    ]
    roll = random.random()
    cumulative = 0
    for weight, func in sources:
        cumulative += weight
        if roll < cumulative:
            result = func()
            if result:
                return result
            break
    for _, func in sources:
        result = func()
        if result:
            return result
    return None

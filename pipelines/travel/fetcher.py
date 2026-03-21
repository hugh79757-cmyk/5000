import sys
import os
import random
import logging

sys.path.insert(0, "/Users/twinssn/Projects/TAP")
os.chdir("/Users/twinssn/Projects/TAP")

from dotenv import load_dotenv
load_dotenv("/Users/twinssn/Projects/TAP/.env")

logger = logging.getLogger(__name__)

def _fix_image_https(url):
    """http://tong.visitkorea.or.kr → https 변환"""
    if url and url.startswith("http://tong.visitkorea.or.kr"):
        return url.replace("http://", "https://", 1)
    return url



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
        import re as _re; title_val = _re.sub(r"202[0-4]", "2026", title_val)
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
            "eventstartdate": item.get("eventstartdate", ""),
            "eventenddate": item.get("eventenddate", ""),
            "playtime": item.get("playtime", ""),
            "eventplace": item.get("eventplace", ""),
            "usetimefestival": item.get("usetimefestival", ""),
            "sponsor1": item.get("sponsor1", ""),
            "program": item.get("program", ""),
            "subevent": item.get("subevent", ""),
            "agelimit": item.get("agelimit", ""),
        })
    return adapted



def _filter_by_season(items, title_key="title"):
    """현재 월에 맞지 않는 콘텐츠 필터링"""
    import datetime
    m = datetime.datetime.now().month
    ban = {
        1: ["벚꽃", "유채꽃", "여름", "물놀이", "해수욕", "피서"],
        2: ["벚꽃", "유채꽃", "여름", "물놀이", "해수욕", "피서", "단풍", "억새"],
        3: ["여름", "물놀이", "해수욕", "피서", "단풍", "억새", "눈썰매", "스키", "겨울"],
        4: ["여름", "물놀이", "해수욕", "피서", "단풍", "억새", "눈썰매", "스키", "겨울"],
        5: ["단풍", "억새", "눈썰매", "스키", "겨울"],
        6: ["단풍", "억새", "눈썰매", "스키", "겨울", "벚꽃"],
        7: ["단풍", "억새", "눈썰매", "스키", "겨울", "벚꽃"],
        8: ["단풍", "억새", "눈썰매", "스키", "겨울", "벚꽃"],
        9: ["눈썰매", "스키", "겨울", "벚꽃", "물놀이", "해수욕", "피서"],
        10: ["눈썰매", "스키", "겨울", "벚꽃", "물놀이", "해수욕", "피서"],
        11: ["벚꽃", "물놀이", "해수욕", "피서", "봄"],
        12: ["봄", "벚꽃", "유채꽃", "여름", "물놀이", "해수욕", "피서"],
    }
    bw = ban.get(m, [])
    if not bw:
        return items
    return [i for i in items if not any(w in i.get(title_key, "") for w in bw)]

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

        # 계절 필터는 detailIntro 이후로 이동됨

        with_img = [i for i in items_raw if i.get('firstimage')]
        pool = with_img if len(with_img) >= 3 else items_raw
        selected = random.sample(pool, min(5, len(pool)))
        
        # detailIntro API로 축제 상세정보 보강
        for item in selected:
            cid = item.get("contentid")
            if not cid:
                continue
            try:
                detail_resp = req.get(
                    "http://apis.data.go.kr/B551011/KorService2/detailIntro2",
                    params={
                        "serviceKey": key,
                        "MobileOS": "ETC",
                        "MobileApp": "TAP",
                        "_type": "json",
                        "contentId": cid,
                        "contentTypeId": 15,
                    },
                    timeout=15,
                )
                d2 = detail_resp.json()
                intro_items = d2.get("response", {}).get("body", {}).get("items", {}).get("item", [])
                if isinstance(intro_items, dict):
                    intro_items = [intro_items]
                if intro_items:
                    detail = intro_items[0]
                    item["eventstartdate"] = detail.get("eventstartdate", "")
                    item["eventenddate"] = detail.get("eventenddate", "")
                    item["playtime"] = detail.get("playtime", "")
                    item["eventplace"] = detail.get("eventplace", "")
                    item["usetimefestival"] = detail.get("usetimefestival", "")
                    item["sponsor1"] = detail.get("sponsor1", "")
                    item["program"] = detail.get("program", "")
                    item["subevent"] = detail.get("subevent", "")
                    item["agelimit"] = detail.get("agelimit", "")
                    logger.info(f"festival detailIntro: {item.get('title','')} 보강 완료")
            except Exception as e:
                logger.warning(f"festival detailIntro 실패 (무시): {e}")
        
        # 계절 필터: detailIntro 이후 eventstartdate 기반 필터링
        from datetime import datetime, timedelta
        now = datetime.now()
        month_ago = (now - timedelta(days=30)).strftime("%Y%m%d")
        month_later = (now + timedelta(days=60)).strftime("%Y%m%d")
        seasonal = []
        for item in selected:
            estart = str(item.get("eventstartdate", ""))
            eend = str(item.get("eventenddate", "")) or estart
            if not estart:
                continue  # 날짜 없는 축제는 제외
            if eend >= month_ago and estart <= month_later:
                seasonal.append(item)
                logger.info(f"festival 계절 통과: {item.get('title','')} ({estart}~{eend})")
            else:
                logger.info(f"festival 계절 제외: {item.get('title','')} ({estart}~{eend})")
        if seasonal:
            selected = seasonal[:1]
            logger.info(f"festival: 계절 필터 후 {len(seasonal)}건 중 1건 선택")
        else:
            # 현재 월 기준 축제 재검색
            logger.warning(f"festival: 계절 필터 후 0건, 현재 월 축제 재검색")
            try:
                now_month = now.strftime("%Y%m")
                re_params = {
                    "numOfRows": "50", "pageNo": "1",
                    "contentTypeId": "15", "arrange": "C",
                    "eventStartDate": now_month + "01",
                }
                re_resp = requests.get(
                    "http://apis.data.go.kr/B551011/KorService2/searchFestival2",
                    params={**{"serviceKey": TOUR_API_KEY, "MobileOS": "ETC", "MobileApp": "TAP", "_type": "json"}, **re_params},
                    timeout=10
                )
                if re_resp.status_code == 200:
                    re_items = re_resp.json().get("response", {}).get("body", {}).get("items", {}).get("item", [])
                    if re_items:
                        selected = [random.choice(re_items)]
                        logger.info(f"festival: searchFestival로 현재 월 축제 {len(re_items)}건 중 1건 재선택: {selected[0].get('title','')}")
                    else:
                        selected = selected[:1]
                        logger.warning("festival: searchFestival 결과 0건, 원본 사용")
                else:
                    selected = selected[:1]
                    logger.warning(f"festival: searchFestival 실패 ({re_resp.status_code}), 원본 사용")
            except Exception as e:
                selected = selected[:1]
                logger.warning(f"festival: searchFestival 예외 ({e}), 원본 사용")

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
    keywords = ["맛집"]  # 테마를 맛집으로 고정 (TourAPI가 세부 카테고리 필터링 불가)
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
                "numOfRows": 50,
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
        with_img = [i for i in items_raw if i.get('firstimage')]
        pool = with_img if len(with_img) >= 3 else items_raw
        selected = random.sample(pool, min(3, len(pool)))
        adapted = _adapt_korservice_items(selected)
        # 시군구 추출: addr1에서 두 번째 토큰 (예: "경기도 수원시 팔달구..." → "수원시")
        sigungu_name = region_name
        try:
            addrs = [item.get("addr1", "") for item in selected if item.get("addr1")]
            if addrs:
                from collections import Counter
                sigungu_tokens = []
                for addr in addrs:
                    parts = addr.split()
                    if len(parts) >= 2:
                        sigungu_tokens.append(parts[1])
                if sigungu_tokens:
                    most_common = Counter(sigungu_tokens).most_common(1)[0][0]
                    cleaned = most_common.replace("시", "").replace("군", "").replace("구", "")
                    # 1글자면(동구→동, 서구→서) 원본 유지
                    sigungu_name = cleaned if len(cleaned) >= 2 else most_common
        except Exception:
            pass
        display = sigungu_name if sigungu_name != region_name else region_name
        return {
            "items": adapted,
            "display_region": display,
            "sigungu": sigungu_name,
            "do_name": region_name,
            "theme": keyword,
            "category": "맛집",
            "angle": display + " " + keyword,
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
        with_img = [i for i in items_raw if i.get('firstimage')]
        pool = with_img if len(with_img) >= 3 else items_raw
        # 계절 부적합 코스 필터링
        import datetime
        _month = datetime.datetime.now().month
        _season_ban = {
            12: ["봄", "벚꽃", "유채꽃", "여름", "물놀이", "해수욕", "피서"],
            1: ["봄", "벚꽃", "유채꽃", "여름", "물놀이", "해수욕", "피서"],
            2: ["여름", "물놀이", "해수욕", "피서", "단풍", "억새"],
            3: ["여름", "물놀이", "해수욕", "피서", "단풍", "억새", "눈썰매", "스키", "겨울"],
            4: ["여름", "물놀이", "해수욕", "피서", "단풍", "억새", "눈썰매", "스키", "겨울"],
            5: ["단풍", "억새", "눈썰매", "스키", "겨울"],
            6: ["단풍", "억새", "눈썰매", "스키", "겨울", "벚꽃"],
            7: ["단풍", "억새", "눈썰매", "스키", "겨울", "벚꽃"],
            8: ["단풍", "억새", "눈썰매", "스키", "겨울", "벚꽃"],
            9: ["눈썰매", "스키", "겨울", "벚꽃", "물놀이", "해수욕", "피서"],
            10: ["눈썰매", "스키", "겨울", "벚꽃", "물놀이", "해수욕", "피서"],
            11: ["벚꽃", "물놀이", "해수욕", "피서", "봄"],
        }
        ban_words = _season_ban.get(_month, [])
        if ban_words:
            pool = [i for i in pool if not any(bw in i.get("title", "") for bw in ban_words)]
            if len(pool) < 3:
                pool = with_img if len(with_img) >= 3 else items_raw  # 필터 후 부족하면 원복

        selected = random.sample(pool, min(5, len(pool)))
        
        # detailIntro API로 축제 상세정보 보강
        for item in selected:
            cid = item.get("contentid")
            if not cid:
                continue
            try:
                detail_resp = req.get(
                    "http://apis.data.go.kr/B551011/KorService2/detailIntro2",
                    params={
                        "serviceKey": key,
                        "MobileOS": "ETC",
                        "MobileApp": "TAP",
                        "_type": "json",
                        "contentId": cid,
                        "contentTypeId": 15,
                    },
                    timeout=15,
                )
                d2 = detail_resp.json()
                intro_items = d2.get("response", {}).get("body", {}).get("items", {}).get("item", [])
                if isinstance(intro_items, dict):
                    intro_items = [intro_items]
                if intro_items:
                    detail = intro_items[0]
                    item["eventstartdate"] = detail.get("eventstartdate", "")
                    item["eventenddate"] = detail.get("eventenddate", "")
                    item["playtime"] = detail.get("playtime", "")
                    item["eventplace"] = detail.get("eventplace", "")
                    item["usetimefestival"] = detail.get("usetimefestival", "")
                    item["sponsor1"] = detail.get("sponsor1", "")
                    item["program"] = detail.get("program", "")
                    item["subevent"] = detail.get("subevent", "")
                    item["agelimit"] = detail.get("agelimit", "")
                    logger.info(f"festival detailIntro: {item.get('title','')} 보강 완료")
            except Exception as e:
                logger.warning(f"festival detailIntro 실패 (무시): {e}")
        
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
    """웰니스관광정보 API (WellnessTursmService) - http, langDivCd=KOR 필수"""
    import requests
    api_key = os.environ.get("TOUR_API_KEY", "") or os.environ.get("DATA_GO_KR_API_KEY", "")
    if not api_key:
        logger.warning("wellness: API key not found")
        return None
    try:
        resp = requests.get(
            "http://apis.data.go.kr/B551011/WellnessTursmService/areaBasedList",
            params={
                "serviceKey": api_key,
                "numOfRows": 50,
                "pageNo": 1,
                "MobileOS": "ETC",
                "MobileApp": "5000",
                "_type": "json",
                "langDivCd": "KOR",
            },
            timeout=15,
        )
        data = resp.json()
        items_raw = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
        if isinstance(items_raw, dict):
            items_raw = [items_raw]
        if not items_raw:
            return None
        with_img = [i for i in items_raw if i.get('orgImage') or i.get('thumbImage')]
        pool = with_img if len(with_img) >= 3 else items_raw
        selected = random.sample(pool, min(5, len(pool)))
        items = []
        for item in selected:
            org_img = item.get("orgImage", "") or ""
            thumb_img = item.get("thumbImage", "") or ""
            img = org_img or thumb_img
            items.append({
                "title": item.get("title", ""),
                "addr": item.get("baseAddr", ""),
                "addr1": item.get("baseAddr", ""),
                "firstimage": _fix_image_https(img),
                "image": _fix_image_https(img),
                "overview": item.get("overview", ""),
                "tel": item.get("tel", ""),
                "contentId": item.get("contentId", ""),
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

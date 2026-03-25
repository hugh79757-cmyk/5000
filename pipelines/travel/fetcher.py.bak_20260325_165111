import sys
import os
import random
import logging

sys.path.insert(0, os.getenv("TAP_ROOT", "/Users/twinssn/Projects/TAP"))
os.chdir(os.getenv("TAP_ROOT", "/Users/twinssn/Projects/TAP"))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.getenv("TAP_ROOT", "/Users/twinssn/Projects/TAP"), ".env"))

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




def _select_same_sigungu(items_raw, count=3):
    """같은 시군구의 아이템만 선택. 실패시 원본에서 랜덤."""
    from collections import defaultdict
    by_sigungu = defaultdict(list)
    for item in items_raw:
        addr = item.get("addr1", item.get("baseAddr", ""))
        parts = (addr or "").split()
        if len(parts) >= 2:
            by_sigungu[parts[1]].append(item)
    # 가장 많은 시군구 우선, 최소 count개 이상인 것
    candidates = sorted(by_sigungu.items(), key=lambda x: -len(x[1]))
    for sigungu, group in candidates:
        with_img = [i for i in group if i.get("firstimage")]
        pool = with_img if len(with_img) >= count else group
        if len(pool) >= count:
            import random as _r
            return _r.sample(pool, count), sigungu
    # 못 찾으면 가장 큰 그룹에서 있는 만큼
    if candidates:
        best_name, best_group = candidates[0]
        import random as _r
        return _r.sample(best_group, min(count, len(best_group))), best_name
    import random as _r
    return _r.sample(items_raw, min(count, len(items_raw))), ""

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
        selected, _ = _select_same_sigungu(pool, 3)
        
        # detailIntro API로 상세정보 보강
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
        selected, _sg = _select_same_sigungu(pool, 3)
        adapted = _adapt_korservice_items(selected)
        sigungu_name = _sg if _sg else region_name
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
                "contentTypeId": 12,
                "cat1": "A02",
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

        selected, _ = _select_same_sigungu(pool, 3)
        
        # detailIntro API로 상세정보 보강
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
        # [PATCH] 지역별 그룹핑 후 가장 많은 지역에서 최대 3곳 선택
        from collections import Counter
        _region_items = {}
        for item in pool:
            _addr = item.get("baseAddr", "")
            _r = _safe_region(_addr)
            if _r:
                _region_items.setdefault(_r, []).append(item)
        if _region_items:
            # 가장 많은 아이템이 있는 지역 선택
            _best_region = max(_region_items, key=lambda r: len(_region_items[r]))
            _region_pool = _region_items[_best_region]
        else:
            _best_region = ""
            _region_pool = pool
        selected = random.sample(_region_pool, min(3, len(_region_pool)))
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
        region = _best_region if _best_region else (_safe_region(items[0].get("addr", "")) if items else "")
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
    """국가유산청 데이터(heritage_list.json)에서 문화유산 아이템을 가져옵니다."""
    import json, random, time, re

    HERITAGE_JSON = "/Users/twinssn/Projects/heritage/scripts/data/heritage_list.json"

    # 시도명 → 지역명 매핑
    region_map = {
        "서울": "서울", "부산": "부산", "대구": "대구", "인천": "인천",
        "광주": "광주", "대전": "대전", "울산": "울산", "세종": "세종",
        "경기": "경기", "강원": "강원", "충북": "충북", "충남": "충남",
        "전북": "전북", "전남": "전남", "경북": "경북", "경남": "경남",
        "제주": "제주",
    }

    try:
        with open(HERITAGE_JSON, "r", encoding="utf-8") as f:
            all_items = json.load(f)
        logger.info(f"heritage: heritage_list.json 로드 완료 ({len(all_items)}건)")
    except Exception as e:
        logger.error(f"heritage: heritage_list.json 로드 실패: {e}")
        return None

    # 취소되지 않은 항목만
    # 블로그 품질 필터: 취소X, 상세정보 있음, 좌표 유효, 종목 제한
    ALLOWED_KD = {"국보", "보물", "사적", "명승", "국가등록문화유산"}
    valid = []
    for i in all_items:
        if i.get("cancel") == "Y":
            continue
        if i.get("kdName", "") not in ALLOWED_KD:
            continue
        if not i.get("city") or i.get("city") == "기타":
            continue
        lat = i.get("lat", 0)
        lng = i.get("lng", 0)
        if not lat or not lng or lat == 0 or lng == 0:
            continue
        det = i.get("detail") or {}
        content = det.get("content", "")
        if len(content) < 100:
            continue
        if not det.get("address"):
            continue
        valid.append(i)
    logger.info(f"heritage: 품질 필터 후 {len(valid)}건 (원본 {len(all_items)}건)")

    # 랜덤 지역 선택
    cities = list(set(i.get("city", "") for i in valid if i.get("city")))
    if not cities:
        logger.warning("heritage: 유효한 지역 없음")
        return None
    region_name = random.choice(cities)

    # 해당 지역 항목 필터
    regional = [i for i in valid if i.get("city") == region_name]
    if not regional:
        logger.warning(f"heritage: {region_name} 지역 항목 0건")
        return None

    # 이미지 있는 항목 우선
    with_img = [i for i in regional if (i.get("detail") or {}).get("imageUrl")]
    pool = with_img if len(with_img) >= 3 else regional
    selected = random.sample(pool, min(5, len(pool)))

    # 종목 기반 테마 결정
    kd_names = [i.get("kdName", "") for i in selected]
    if any("국보" in k for k in kd_names):
        theme = "국보 탐방"
    elif any("보물" in k for k in kd_names):
        theme = "보물 탐방"
    elif any("사적" in k for k in kd_names):
        theme = "사적 탐방"
    elif any("명승" in k for k in kd_names):
        theme = "명승 탐방"
    elif any("천연기념물" in k for k in kd_names):
        theme = "천연기념물 탐방"
    else:
        theme = "문화유산 투어"

    logger.info(f"heritage: {region_name} / {theme} / {len(selected)}건 선택")

    # TourAPI 형식으로 변환
    items = []
    for item in selected:
        detail = item.get("detail") or {}
        overview = detail.get("content", "")
        # HTML 태그 제거
        overview = re.sub(r"<[^>]+>", "", overview) if overview else ""

        adapted = {
            "title": item.get("nameKr", ""),
            "addr": detail.get("address", ""),
            "image": detail.get("imageUrl", ""),
            "tel": "",
            "content_id": item.get("cpno", ""),
            "contenttypeid": "12",
            "overview": overview,
            "homepage": "",
            "mapx": str(item.get("lng", "")),
            "mapy": str(item.get("lat", "")),
            "kdName": item.get("kdName", ""),
            "era": detail.get("era", ""),
            "owner": detail.get("owner", ""),
            "quantity": detail.get("quantity", ""),
            "designatedDate": detail.get("designatedDate", ""),
            "category1": detail.get("category1", ""),
            "category2": detail.get("category2", ""),
        }
        items.append(adapted)

    if not items:
        logger.warning(f"heritage: {region_name} 변환 후 0건")
        return None

    return {
        "items": items,
        "region": region_name,
        "theme": theme,
        "source_type": "heritage",
    }


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

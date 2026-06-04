import sys
import os
import random
import logging

sys.path.insert(0, os.getenv("TAP_ROOT", "/Users/twinssn/Projects/TAP"))
os.chdir(os.getenv("TAP_ROOT", "/Users/twinssn/Projects/TAP"))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.getenv("TAP_ROOT", "/Users/twinssn/Projects/TAP"), ".env"))

logger = logging.getLogger(__name__)

try:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from shared.telegram_notifier import send as _tg_send
except ImportError:
    _tg_send = lambda *a, **k: None

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

    # [GUARD] 빈 데이터 방지
    if not adapted_items:
        logger.warning("korservice GUARD: adapted_items 0건 → None 반환")
        return None
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
HERITAGE_TYPES = {"14"}  # 14=cultural only (12=tourist 제거 — 테마파크 유입 차단)
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


def fetch_festival(_is_retry=False):
    """festival.db 기반 스마트 발행: 축제 시작일 역산으로 발행 대상 자동 선택"""
    import sqlite3
    from datetime import datetime, timedelta
    from collections import defaultdict

    DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "festival.db")
    CONTENT_DB = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "content.db")

    if not os.path.exists(DB_PATH):
        logger.warning("festival.db not found: " + DB_PATH)
        return None

    AREA_NAMES = {
        "1": "서울", "2": "인천", "3": "대전", "4": "대구", "5": "광주",
        "6": "부산", "7": "울산", "8": "세종", "31": "경기", "32": "강원",
        "33": "충북", "34": "충남", "35": "경북", "36": "경남",
        "37": "전북", "38": "전남", "39": "제주",
    }

    try:
        # 이미 발행된 축제 contentid 조회 (중복 방지)
        published_ids = set()
        if os.path.exists(CONTENT_DB):
            cconn = sqlite3.connect(CONTENT_DB)
            published_ids = set(
                r[0] for r in cconn.execute(
                    "SELECT source_id FROM publish_ledger WHERE blog_id='travel1-hugo' AND source_id != ''"
                ).fetchall()
            )
            # articles 테이블도 확인
            published_ids.update(
                r[0] for r in cconn.execute(
                    "SELECT source_id FROM articles WHERE blog_id='travel1-hugo' AND source_id != ''"
                ).fetchall()
            )
            cconn.close()

        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        now = datetime.now()
        today = now.strftime("%Y%m%d")

        # 미래 축제만 조회
        rows = conn.execute("""
            SELECT * FROM festivals
            WHERE eventstartdate >= ?
            ORDER BY eventstartdate ASC
        """, (today,)).fetchall()

        if not rows:
            logger.warning("festival.db: 미래 축제 0건")
            conn.close()
            if not _is_retry:
                logger.warning("festival 소진 감지 — refresh_festival 자동 트리거")
                try:
                    import subprocess as _sp
                    _r = _sp.run([_sp.sys.executable, "scripts/refresh_festival.py"],
                                 capture_output=True, text=True,
                                 cwd="/Users/twinssn/Projects/5000", timeout=120)
                    logger.info(f"festival 자동 갱신 결과: {_r.stdout.strip()}")
                except Exception as _e:
                    logger.error(f"festival 자동 갱신 실패: {_e}")
                return fetch_festival(_is_retry=True)
            return None

        # 스마트 발행: 축제 시작일 역산으로 분류
        # 0~13일: 색인 불가 → 발행 안 함
        # 14~21일: 긴급 → 최대 5건/일
        # 22~28일: 높음 → 최대 3건/일
        # 29~42일: 보통 → 최대 2건/일
        # 43~60일: 낮음 → 최대 1건/일
        # 61일+: 대기 → 발행 안 함
        urgent = []   # 14~21일
        high = []     # 22~28일
        normal = []   # 29~42일
        low = []      # 43~60일
        late = []     # 7~14일 (늦게 등록된 축제, 최초 1회만 발행 허용)

        for r in rows:
            title = r["title"]
            if str(r['contentid']) in published_ids:
                continue
            estart = r["eventstartdate"]
            start_date = datetime.strptime(estart, "%Y%m%d")
            days_left = (start_date - now).days

            if days_left < 7:
                continue  # 7일 미만: SEO 색인 불가
            elif days_left <= 14:
                late.append(r)   # 늦게 등록 — 최초 1회 발행 허용
            elif days_left <= 21:
                urgent.append(r)
            elif days_left <= 28:
                high.append(r)
            elif days_left <= 42:
                normal.append(r)
            elif days_left <= 60:
                low.append(r)
            # 61일+ 대기

        # 우선순위 순서대로 후보 선택
        _is_fallback = False
        if urgent:
            candidates = urgent
            logger.info(f"festival 스마트발행: 긴급(14~21일) {len(urgent)}건")
        elif high:
            candidates = high
            logger.info(f"festival 스마트발행: 높음(22~28일) {len(high)}건")
        elif normal:
            candidates = normal
            logger.info(f"festival 스마트발행: 보통(29~42일) {len(normal)}건")
        elif low:
            candidates = low
            logger.info(f"festival 스마트발행: 낮음(43~60일) {len(low)}건")
        elif late:
            candidates = late
            logger.info(f"festival 스마트발행: 늦등록(7~14일) {len(late)}건 — 최초 1회 발행")
        else:
            # [AUTO REFRESH] published_ids 필터로 후보 0건 → DB 갱신 후 1회 재시도
            if not _is_retry:
                logger.warning("festival 소진 감지 — refresh_festival 자동 트리거")
                try:
                    import subprocess as _sp
                    _r = _sp.run([_sp.sys.executable, "scripts/refresh_festival.py"],
                                 capture_output=True, text=True,
                                 cwd="/Users/twinssn/Projects/5000", timeout=120)
                    logger.info(f"festival 자동 갱신 결과: {_r.stdout.strip()}")
                except Exception as _e:
                    logger.error(f"festival 자동 갱신 실패: {_e}")
                return fetch_festival(_is_retry=True)
            _is_fallback = True
            logger.warning("festival 스마트발행: 발행 대상 0건 — published_ids fallback 시도")
            _tg_send("⚠️ travel1-hugo festival 콘텐츠 소진 — fallback 발행 중")
            # [DEPLETION FALLBACK] 모든 축제가 이미 발행됨 → published_ids 무시하고 재시도
            urgent = []
            high = []
            normal = []
            low = []
            late = []
            for r in rows:
                estart = r["eventstartdate"]
                start_date = datetime.strptime(estart, "%Y%m%d")
                days_left = (start_date - now).days
                if days_left < 7:
                    continue
                elif days_left <= 14:
                    late.append(r)
                elif days_left <= 21:
                    urgent.append(r)
                elif days_left <= 28:
                    high.append(r)
                elif days_left <= 42:
                    normal.append(r)
                elif days_left <= 60:
                    low.append(r)
            if urgent:
                candidates = urgent
                logger.info(f"festival fallback: 긴급(14~21일) {len(urgent)}건")
            elif high:
                candidates = high
                logger.info(f"festival fallback: 높음(22~28일) {len(high)}건")
            elif normal:
                candidates = normal
                logger.info(f"festival fallback: 보통(29~42일) {len(normal)}건")
            elif low:
                candidates = low
                logger.info(f"festival fallback: 낮음(43~60일) {len(low)}건")
            elif late:
                candidates = late
                logger.info(f"festival fallback: 늦등록(7~14일) {len(late)}건")
            else:
                logger.warning("festival: fallback 후에도 0건 (DB 갱신 필요)")
                _tg_send("🚨 travel1-hugo festival 발행 불가 — DB 갱신 필요")
                conn.close()
                return None

        # 이미지 있는 것 우선
        with_image = [r for r in candidates if r["firstimage"]]
        if with_image:
            candidates = with_image

        # 같은 시군구 묶기
        by_sigungu = defaultdict(list)
        for r in candidates:
            key = (r["areacode"], r["sigungucode"])
            by_sigungu[key].append(r)

        # 3건 이상 있는 시군구 우선
        groups_3 = [v for v in by_sigungu.values() if len(v) >= 3]
        if groups_3:
            group = random.choice(groups_3)
            selected = random.sample(group, min(3, len(group)))
        else:
            groups_any = [v for v in by_sigungu.values() if len(v) >= 1]
            if groups_any:
                group = random.choice(groups_any)
                selected = group[:3]
            else:
                conn.close()
                return None

        # 결과 구성
        region_name = AREA_NAMES.get(str(selected[0]["areacode"]), "")
        sigungu_name = selected[0]["sigungucode"] or ""
        if not sigungu_name and selected[0]["addr1"]:
            parts = selected[0]["addr1"].split()
            if len(parts) >= 2:
                sigungu_name = parts[1]

        adapted = []
        for r in selected:
            adapted.append({
                "title": r["title"],
                "addr1": r["addr1"] or "",
                "mapx": r["mapx"] or "",
                "mapy": r["mapy"] or "",
                "firstimage": _fix_image_https(r["firstimage"] or ""),
                "tel": r["tel"] or "",
                "eventstartdate": r["eventstartdate"] or "",
                "eventenddate": r["eventenddate"] or "",
                "eventplace": r["eventplace"] or "",
                "playtime": r["playtime"] or "",
                "usetimefestival": r["usetimefestival"] or "",
                "sponsor1": r["sponsor1"] or "",
                "program": r["program"] or "",
                "subevent": r["subevent"] or "",
                "agelimit": r["agelimit"] or "",
            })

        if not adapted or not adapted[0].get("title"):
            logger.warning("festival GUARD: adapted 결과 0건 → None 반환")
            conn.close()
            return None

        conn.close()
        # contentid 리스트 (중복 발행 방지용)
        # fallback 모드: 이미 발행된 contentid → 빈 리스트로 pipeline 중복체크 우회
        content_ids = [] if _is_fallback else [str(r["contentid"]) for r in selected if r["contentid"]]

        result = {
            "items": adapted,
            "display_region": f"{region_name} {sigungu_name}".strip(),
            "sigungu": sigungu_name,
            "do_name": region_name,
            "theme": "축제",
            "category": "festival",
            "angle": "축제 일정과 방문 정보",
            "source_type": "festival",
            "region": region_name,
            "content_ids": content_ids,
        }
        logger.info(f"festival 선택: {adapted[0]['title']} ({adapted[0]['eventstartdate']})")
        return result

    except Exception as e:
        logger.warning("festival fetch failed: " + str(e))
        return None


def _get_recent_published_sigungus(days=7):
    """최근 N일간 travel3-hugo에 발행된 시군구 이름 집합
    우선 articles.sigungu 컬럼 직접 조회 (stap_content.db), NULL이면 title 파싱 fallback"""
    import sqlite3
    try:
        from shared.db_paths import ARTICLES_DB
    except ImportError:
        ARTICLES_DB = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "stap_content.db")
    sigungus = set()
    try:
        conn = sqlite3.connect(ARTICLES_DB)
        # sigungu 컬럼 직접 조회
        col_rows = conn.execute(
            "SELECT DISTINCT sigungu FROM articles WHERE blog_id='travel3-hugo' AND sigungu IS NOT NULL AND sigungu != '' AND created_at >= datetime('now', ? || ' days')",
            (str(days),)
        ).fetchall()
        if col_rows:
            sigungus = {row[0] for row in col_rows}
        else:
            # title 파싱 fallback
            rows = conn.execute(
                "SELECT title FROM articles WHERE blog_id='travel3-hugo' AND created_at >= datetime('now', ? || ' days')",
                (str(days),)
            ).fetchall()
            _do_set = {'서울','인천','대전','대구','광주','부산','울산','세종',
                        '경기','강원','충북','충남','전북','전남','경북','경남','제주'}
            for (title,) in rows:
                if not title:
                    continue
                parts = title.split()
                for p in parts:
                    if p in _do_set:
                        continue
                    if p.endswith('시') or p.endswith('군') or p.endswith('구'):
                        sigungus.add(p)
                        break
        conn.close()
        if sigungus:
            logger.info(f"_get_recent_sigungus ({days}일, ARTICLES_DB): {len(sigungus)}개: {sigungus}")
    except Exception as e:
        logger.warning(f"_get_recent_sigungus 오류: {e}")
    return sigungus


def fetch_food():
    """TourAPI contentTypeId=39 + sigunguCode 직접 지정으로 균등 분산
    - pipelines.travel.area_codes의 FOOD_AREA_SIGUNGU에서 랜덤 시군구 선택
    - sigunguCode 파라미터 전달로 특정 시군구 데이터만 조회
    - 최근 5일간 발행된 시군구는 제외 (주제 중복 방지)
    """
    import requests as req
    from pipelines.travel.area_codes import get_weighted_random_sigungu, get_do_name

    key = os.getenv("TOUR_API_KEY", "") or os.getenv("DATA_GO_KR_API_KEY", "")

    # 기존 발행 contentid 사전 로드
    _published_cids = set()
    try:
        import sqlite3 as _sql
        _db = _sql.connect(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "content.db"))
        for row in _db.execute("SELECT source_id FROM articles WHERE blog_id='travel3-hugo' AND source_id != ''"):
            for _cid in row[0].split(","):
                if _cid.strip():
                    _published_cids.add(_cid.strip())
        for row in _db.execute("SELECT source_id FROM publish_ledger WHERE blog_id='travel3-hugo' AND source_id != ''"):
            for _cid in row[0].split(","):
                if _cid.strip():
                    _published_cids.add(_cid.strip())
        _db.close()
    except Exception as _e:
        logger.warning(f"food dup-check DB error: {_e}")

    # 최근 7일 발행 시군구 제외
    _recent_sigungus = _get_recent_published_sigungus(7)

    # 가중치 기반 시군구 선택 (최근 발행 시군구 제외)
    # 최대 50회 시도 — exclude_sigungus로 전부 소진 시 제한 해제됨
    for _attempt in range(50):
        area_code, sigungu_code, sigungu_name = get_weighted_random_sigungu(
            exclude_sigungus=_recent_sigungus
        )
        do_name = get_do_name(area_code)

        try:
            resp = req.get(
                "http://apis.data.go.kr/B551011/KorService2/areaBasedList2",
                params={
                    "serviceKey": key,
                    "MobileOS": "ETC",
                    "MobileApp": "TAP",
                    "_type": "json",
                    "numOfRows": 100,
                    "pageNo": random.randint(1, 3),
                    "contentTypeId": 39,
                    "areaCode": area_code,
                    "sigunguCode": sigungu_code,
                    "arrange": random.choice(["C", "Q", "A"]),
                },
                timeout=15,
            )
            data = resp.json()
            header = data.get("response", {}).get("header", {})
            if header.get("resultCode") != "0000":
                logger.warning(f"food API error ({do_name} {sigungu_name}): {header}")
                continue

            items_raw = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
            if isinstance(items_raw, dict):
                items_raw = [items_raw]
            if not items_raw:
                logger.info(f"food: {do_name} {sigungu_name} 데이터 0건 → 다음 시군구")
                continue

            # 음식점 + 카페 혼합
            _cafe_kw = {"카페", "cafe", "커피", "디저트", "베이커리", "빵집", "브런치", "펫카페", "애견카페"}
            def _is_cafe(item):
                return any(kw in (item.get("title", "") or "").lower() for kw in _cafe_kw)
            _restaurants = [i for i in items_raw if not _is_cafe(i)]
            _cafes = [i for i in items_raw if _is_cafe(i)]
            if len(_restaurants) >= 2 and _cafes:
                _mixed = _restaurants + _cafes[:1]
            elif len(_restaurants) >= 3:
                _mixed = _restaurants
            else:
                _mixed = items_raw

            with_img = [i for i in _mixed if i.get("firstimage")]
            pool = with_img if len(with_img) >= 3 else _mixed
            pool = [item for item in pool if str(item.get("contentid", "")) not in _published_cids]

            if len(pool) < 3:
                logger.info(f"food: {do_name} {sigungu_name} 중복 제외 후 {len(pool)}건 → 다음 시군구")
                continue

            # 같은 시군구 내에서 3개 랜덤 선택 (_select_same_sigungu 불필요)
            selected = random.sample(pool, min(3, len(pool)))
            adapted = _adapt_korservice_items(selected)
            display = f"{do_name} {sigungu_name}"
            content_ids = [str(item.get("contentid", "")) for item in selected if item.get("contentid")]

            logger.info(f"food 선택: {do_name} {sigungu_name} {len(selected)}건")
            return {
                "items": adapted,
                "display_region": display,
                "sigungu": sigungu_name,
                "do_name": do_name,
                "theme": "맛집",
                "category": "맛집",
                "angle": display + " 맛집",
                "source_type": "korservice",
                "content_ids": content_ids,
            }
        except Exception as e:
            logger.warning(f"food fetch failed ({do_name} {sigungu_name}): " + str(e))
            continue

    # [DEPLETION FALLBACK] sigungu 제한 완화 → published_ids 무시, 2건 허용
    logger.warning("food: 콘텐츠 소진 — 중복 체크 완화 fallback 시도")
    _tg_send("⚠️ travel3-hugo food 콘텐츠 소진 — fallback 발행 중")
    for _attempt in range(50):
        area_code, sigungu_code, sigungu_name = get_weighted_random_sigungu()
        do_name = get_do_name(area_code)
        try:
            resp = req.get(
                "http://apis.data.go.kr/B551011/KorService2/areaBasedList2",
                params={
                    "serviceKey": key,
                    "MobileOS": "ETC",
                    "MobileApp": "TAP",
                    "_type": "json",
                    "numOfRows": 100,
                    "pageNo": random.randint(1, 3),
                    "contentTypeId": 39,
                    "areaCode": area_code,
                    "sigunguCode": sigungu_code,
                    "arrange": random.choice(["C", "Q", "A"]),
                },
                timeout=15,
            )
            data = resp.json()
            header = data.get("response", {}).get("header", {})
            if header.get("resultCode") != "0000":
                continue
            items_raw = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
            if isinstance(items_raw, dict):
                items_raw = [items_raw]
            if not items_raw:
                continue
            _cafe_kw = {"카페", "cafe", "커피", "디저트", "베이커리", "빵집", "브런치", "펫카페", "애견카페"}
            def _is_cafe_fb(item):
                return any(kw in (item.get("title", "") or "").lower() for kw in _cafe_kw)
            _restaurants = [i for i in items_raw if not _is_cafe_fb(i)]
            _cafes = [i for i in items_raw if _is_cafe_fb(i)]
            if len(_restaurants) >= 1 and _cafes:
                _mixed = _restaurants + _cafes[:1]
            elif len(_restaurants) >= 2:
                _mixed = _restaurants
            else:
                _mixed = items_raw
            with_img = [i for i in _mixed if i.get("firstimage")]
            pool = with_img if len(with_img) >= 2 else _mixed
            if len(pool) < 2:
                if len(pool) == 1:
                    selected = pool
                else:
                    continue
            else:
                selected = random.sample(pool, min(2, len(pool)))
            adapted = _adapt_korservice_items(selected)
            display = f"{do_name} {sigungu_name}"
            content_ids = [str(item.get("contentid", "")) for item in selected if item.get("contentid")]
            logger.info(f"food fallback 성공: {do_name} {sigungu_name} {len(selected)}건")
            return {
                "items": adapted,
                "display_region": display,
                "sigungu": sigungu_name,
                "do_name": do_name,
                "theme": "맛집",
                "category": "맛집",
                "angle": display + " 맛집",
                "source_type": "korservice",
                "content_ids": content_ids,
            }
        except Exception as e:
            logger.warning(f"food fallback failed ({do_name} {sigungu_name}): " + str(e))
            continue

    logger.warning("food: fallback 전체 시군구 순회 후 발행 불가")
    _tg_send("🚨 travel3-hugo food 발행 불가 — 모든 시군구 콘텐츠 소진")
    return None


def fetch_course():
    """TourAPI contentTypeId=25(여행코스) + detailInfo2로 코스 하위 장소 데이터 확보"""
    import requests as req
    AREA_CODES = {
        "서울": 1, "인천": 2, "대전": 3, "대구": 4, "광주": 5,
        "부산": 6, "울산": 7, "세종": 8, "경기": 31, "강원": 32,
        "충북": 33, "충남": 34, "경북": 35, "경남": 36,
        "전북": 37, "전남": 38, "제주": 39,
    }
    region_name = random.choice(list(AREA_CODES.keys()))
    area_code = AREA_CODES[region_name]
    key = os.getenv("TOUR_API_KEY", "") or os.getenv("DATA_GO_KR_API_KEY", "")
    try:
        # 1단계: 여행코스 목록 조회 (contentTypeId=25)
        resp = req.get(
            "http://apis.data.go.kr/B551011/KorService2/areaBasedList2",
            params={
                "serviceKey": key,
                "MobileOS": "ETC",
                "MobileApp": "TAP",
                "_type": "json",
                "numOfRows": 30,
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
            logger.warning("course API error: %s", header)
            return None
        items_raw = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
        if isinstance(items_raw, dict):
            items_raw = [items_raw]
        if not items_raw:
            logger.warning("course: no data for %s", region_name)
            return None

        # 이미지 있는 코스 우선
        with_img = [i for i in items_raw if i.get("firstimage")]
        pool = with_img if len(with_img) >= 3 else items_raw

        # 계절 필터링
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
            filtered = [i for i in pool if not any(bw in i.get("title", "") for bw in ban_words)]
            if len(filtered) >= 1:
                pool = filtered

        # 기존 발행 contentid 제외 (articles + publish_ledger + course_published)
        _published_cids = set()
        _published_titles = set()
        try:
            import sqlite3 as _sql
            _db = _sql.connect(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "content.db"))
            for row in _db.execute("SELECT source_id FROM articles WHERE blog_id='travel4-hugo' AND source_id != ''"):
                for _cid in row[0].split(","):
                    if _cid.strip():
                        _published_cids.add(_cid.strip())
            for row in _db.execute("SELECT source_id FROM publish_ledger WHERE blog_id='travel4-hugo' AND source_id != ''"):
                for _cid in row[0].split(","):
                    if _cid.strip():
                        _published_cids.add(_cid.strip())
            # course_published 테이블에서 contentid + 제목 수집
            try:
                for row in _db.execute("SELECT course_contentid, course_title FROM course_published WHERE blog_id='travel4-hugo'"):
                    cid_val = row[0] or ""
                    if cid_val and not cid_val.startswith("title_"):
                        _published_cids.add(cid_val)
                    if row[1]:
                        _published_titles.add(row[1].strip())
            except Exception:
                pass  # 테이블 없으면 무시
            _db.close()
        except Exception as _e:
            logger.warning("course dup-check DB error: %s", _e)
        # 1차: contentid + title 둘 다 체크
        pool_strict = [item for item in pool
                if str(item.get("contentid", "")) not in _published_cids
                and item.get("title", "").strip() not in _published_titles]
        # 2차: contentid만 체크 (title 차단 누적 시 폴백)
        pool_relaxed = [item for item in pool
                if str(item.get("contentid", "")) not in _published_cids]
        if pool_strict:
            pool = pool_strict
            logger.info(f"course: strict 필터 후 {len(pool)}건")
        elif pool_relaxed:
            pool = pool_relaxed
            logger.warning(f"course: title 차단 완화 (relaxed) 후 {len(pool)}건")
        else:
            logger.warning("course: 중복 제외 후 아이템 0건 → 다른 지역으로 재시도")
            # 지역 재시도를 위해 다른 areaCode 랜덤 선택 후 재귀 1회
            import random as _rr
            _fallback_codes = [c for c in [1,2,3,4,5,6,7,8,31,32,33,34,35,36,37,38,39] if c != area_code]
            area_code = _rr.choice(_fallback_codes)
            _resp_fb = req.get(
                "http://apis.data.go.kr/B551011/KorService2/areaBasedList2",
                params={"serviceKey": key, "MobileOS": "ETC", "MobileApp": "TAP",
                        "_type": "json", "numOfRows": 30, "pageNo": 1,
                        "contentTypeId": 25, "areaCode": area_code, "arrange": "C"},
                timeout=15,
            )
            _fb_items = _resp_fb.json().get("response", {}).get("body", {}).get("items", {}).get("item", [])
            if isinstance(_fb_items, dict):
                _fb_items = [_fb_items]
            pool = [i for i in _fb_items if str(i.get("contentid", "")) not in _published_cids]
            if not pool:
                logger.warning("course: 폴백 지역도 0건")
                return None
            logger.info(f"course: 폴백 지역 areaCode={area_code} → {len(pool)}건")

        # 랜덤 1개 코스 선택
        course_item = random.choice(pool)
        course_cid = course_item.get("contentid")
        course_title = course_item.get("title", "")
        course_image = _fix_image_https(course_item.get("firstimage", ""))

        # 2단계: detailInfo2로 코스 하위 장소 조회
        resp2 = req.get(
            "http://apis.data.go.kr/B551011/KorService2/detailInfo2",
            params={
                "serviceKey": key,
                "MobileOS": "ETC",
                "MobileApp": "TAP",
                "_type": "json",
                "contentId": course_cid,
                "contentTypeId": 25,
            },
            timeout=15,
        )
        data2 = resp2.json()
        sub_items = data2.get("response", {}).get("body", {}).get("items", {}).get("item", [])
        if isinstance(sub_items, dict):
            sub_items = [sub_items]
        if not sub_items:
            logger.warning("course detailInfo: %s 하위장소 0건", course_title)
            return None

        # 3단계: detailCommon2로 코스 overview 조회
        course_overview = ""
        try:
            resp3 = req.get(
                "http://apis.data.go.kr/B551011/KorService2/detailCommon2",
                params={
                    "serviceKey": key,
                    "MobileOS": "ETC",
                    "MobileApp": "TAP",
                    "_type": "json",
                    "contentId": course_cid,
                },
                timeout=15,
            )
            data3 = resp3.json()
            _items_raw3 = data3.get("response", {}).get("body", {}).get("items", "")
            if isinstance(_items_raw3, str):
                common_items = []
            else:
                common_items = _items_raw3.get("item", [])
            if isinstance(common_items, dict):
                common_items = [common_items]
            if common_items:
                import re as _re_ov
                ov = common_items[0].get("overview", "")
                course_overview = _re_ov.sub(r"<[^>]+>", "", ov).strip() if ov else ""
        except Exception as _e3:
            logger.warning("course detailCommon failed: %s", _e3)

        # 4단계: 하위 장소를 adapted items로 변환 (subcontentid로 보강)
        import re as _re_html
        course_mapx = course_item.get("mapx", "")
        course_mapy = course_item.get("mapy", "")
        adapted = []
        for idx, sub in enumerate(sub_items):
            sub_overview = sub.get("subdetailoverview", "")
            sub_overview = _re_html.sub(r"<[^>]+>", "", sub_overview).strip() if sub_overview else ""
            sub_img = _fix_image_https(sub.get("subdetailimg", ""))
            sub_addr = ""
            sub_mapx = course_mapx
            sub_mapy = course_mapy
            sub_tel = ""
            # subcontentid로 detailCommon2 호출하여 주소/좌표/overview 보강
            scid = sub.get("subcontentid", "")
            if scid:
                try:
                    _resp_sub = req.get(
                        "http://apis.data.go.kr/B551011/KorService2/detailCommon2",
                        params={
                            "serviceKey": key,
                            "MobileOS": "ETC",
                            "MobileApp": "TAP",
                            "_type": "json",
                            "contentId": scid,
                        },
                        timeout=10,
                    )
                    _d_sub = _resp_sub.json()
                    _items_sub = _d_sub.get("response", {}).get("body", {}).get("items", "")
                    if isinstance(_items_sub, str):
                        _items_sub_list = []
                    else:
                        _items_sub_list = _items_sub.get("item", [])
                    if isinstance(_items_sub_list, dict):
                        _items_sub_list = [_items_sub_list]
                    if _items_sub_list:
                        _si = _items_sub_list[0]
                        sub_addr = _si.get("addr1", "")
                        if _si.get("mapx"):
                            sub_mapx = _si["mapx"]
                        if _si.get("mapy"):
                            sub_mapy = _si["mapy"]
                        if _si.get("tel"):
                            sub_tel = _si["tel"]
                        # overview가 비었으면 보강
                        if not sub_overview and _si.get("overview"):
                            sub_overview = _re_html.sub(r"<[^>]+>", "", _si["overview"]).strip()
                        # 이미지가 비었으면 보강
                        if not sub_img and _si.get("firstimage"):
                            sub_img = _fix_image_https(_si["firstimage"])
                except Exception as _e_sub:
                    logger.debug("course sub detail failed for %s: %s", scid, _e_sub)
            adapted.append({
                "title": sub.get("subname", ""),
                "facltNm": sub.get("subname", ""),
                "addr1": sub_addr,
                "addr": sub_addr,
                "firstimage": sub_img,
                "firstImageUrl": sub_img,
                "image": sub_img,
                "overview": sub_overview,
                "subnum": sub.get("subnum", str(idx)),
                "subcontentid": scid,
                "tel": sub_tel,
                "contenttypeid": "25",
                "mapx": str(sub_mapx),
                "mapy": str(sub_mapy),
            })

        if not adapted:
            logger.warning("course: adapted 결과 0건")
            return None

        # 코스 제목에서 지역 보정 (시군구명 추출)
        _course_do_name = region_name
        _course_sigungu = ""
        addr1 = course_item.get("addr1", "")
        if addr1:
            parts = addr1.split()
            if len(parts) >= 2:
                _course_do_name = parts[0]
                _course_sigungu = parts[1]
            elif parts:
                _course_do_name = parts[0]
        display_region = f"{_course_do_name} {_course_sigungu}".strip()

        # 코스 테마 추출 (cat2 기반)
        cat2_map = {
            "C0112": "가족코스",
            "C0113": "나홀로코스",
            "C0114": "힐링코스",
            "C0115": "도보코스",
            "C0116": "캠핑코스",
            "C0117": "맛코스",
        }
        cat2 = course_item.get("cat2", "")
        theme_label = cat2_map.get(cat2, "여행코스")

        logger.info("course: %s / %s / %d개 하위장소", course_title, region_name, len(adapted))

        return {
            "items": adapted,
            "display_region": display_region,
            "sigungu": _course_sigungu,
            "do_name": _course_do_name,
            "theme": theme_label,
            "category": "여행코스",
            "angle": course_title,
            "source_type": "course",
            "course_title": course_title,
            "course_overview": course_overview,
            "course_image": course_image,
            "content_ids": [str(course_cid)],
        }
    except Exception as e:
        logger.warning("course fetch failed: %s", e)
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

    # ── 기존 발행 content_id 제외 (중복 방지) ──
    _published_cids = set()
    try:
        import sqlite3 as _sql
        _db = _sql.connect(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "content.db"))
        for row in _db.execute("SELECT source_id FROM articles WHERE blog_id='travel2-hugo' AND source_id != ''"):
            for _cid in str(row[0]).split(","):
                if _cid.strip():
                    _published_cids.add(_cid.strip())
        _db.close()
    except Exception as _e:
        logger.warning("heritage dup-check DB error: %s", _e)
    if _published_cids:
        before_count = len(valid)
        valid = [i for i in valid if str(i.get("cpno", "")) not in _published_cids]
        logger.info("heritage 중복 제외: %d → %d건", before_count, len(valid))

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
    pool = with_img if len(with_img) >= 1 else regional

    # ── 전략 선택: 심층(1곳) 70% / 맥락묶기(2~3곳) 30% ──
    _roll = random.random()
    _deep_candidates = [i for i in pool if len((i.get("detail") or {}).get("content", "")) >= 500]

    if _roll < 0.7 and _deep_candidates:
        # 심층 전략: overview 500자 이상, 데이터 풍부한 1곳
        selected = [random.choice(_deep_candidates)]
        _strategy = "deep"
        logger.info(f"heritage 심층전략: {selected[0].get('nameKr', '')[:20]} (overview {len((selected[0].get('detail') or {}).get('content', ''))}자)")
    else:
        # 맥락묶기 전략: 같은 종목 + 같은 시대계열 우선, 2~3곳
        # 종목별 그룹핑
        from collections import defaultdict
        _kd_groups = defaultdict(list)
        for i in pool:
            _kd_groups[i.get("kdName", "")].append(i)

        # 같은 종목에서 2~3곳 선택, 시대 유사성 우선
        _best_group = None
        for _kd, _items in sorted(_kd_groups.items(), key=lambda x: -len(x[1])):
            if len(_items) >= 2:
                _best_group = (_kd, _items)
                break

        if _best_group:
            _kd, _items = _best_group
            # 시대별 하위 그룹핑 시도 (시대 앞 2글자 기준: 고려, 조선, 신라 등)
            _era_groups = defaultdict(list)
            for i in _items:
                _era = (i.get("detail") or {}).get("era", "")[:2]
                _era_groups[_era if _era else "미상"].append(i)
            # 같은 시대 2곳 이상 있으면 그 그룹에서 선택
            _era_match = None
            for _era, _eitems in sorted(_era_groups.items(), key=lambda x: -len(x[1])):
                if len(_eitems) >= 2 and _era != "미상":
                    _era_match = _eitems
                    break
            if _era_match:
                selected = random.sample(_era_match, min(3, len(_era_match)))
            else:
                selected = random.sample(_items, min(3, len(_items)))
        else:
            # 종목 그룹 2곳 미만이면 그냥 1~2곳
            selected = random.sample(pool, min(2, len(pool)))
        _strategy = "grouped"
        logger.info(f"heritage 묶기전략: {len(selected)}곳, 종목 {[i.get('kdName','') for i in selected]}")

    # 종목 기반 테마 결정
    kd_names = [i.get("kdName", "") for i in selected]
    if any("국보" in k for k in kd_names):
        theme = "국보"
    elif any("보물" in k for k in kd_names):
        theme = "보물"
    elif any("사적" in k for k in kd_names):
        theme = "사적"
    elif any("명승" in k for k in kd_names):
        theme = "명승"
    else:
        theme = "문화유산"

    # 심층 전략일 때 테마를 더 구체적으로
    if _strategy == "deep":
        _det = selected[0].get("detail") or {}
        _cat1 = _det.get("category1", "")
        _cat2 = _det.get("category2", "")
        if _cat2:
            theme = f"{kd_names[0]} {_cat2}"
        elif _cat1:
            theme = f"{kd_names[0]} {_cat1}"

    logger.info(f"heritage: {region_name} / {theme} / {len(selected)}건 / {_strategy}")

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

    # content_ids: cpno 기반 중복 방지용
    _content_ids = [str(item.get("content_id", "")) for item in items if item.get("content_id")]

    # 시군구명 추출 (선택된 items의 district 사용)
    _sigungu_name = ""
    for _it in selected:
        _d = _it.get("district", "")
        if _d:
            _sigungu_name = _d
            break

    return {
        "items": items,
        "region": region_name,
        "display_region": f"{region_name} {_sigungu_name}".strip(),
        "sigungu": _sigungu_name,
        "do_name": region_name,
        "theme": theme,
        "category": theme,
        "angle": f"{region_name} {theme}",
        "source_type": "heritage",
        "content_ids": _content_ids,
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

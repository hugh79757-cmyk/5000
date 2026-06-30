"""다이닝코드 enricher - v3.6: 메뉴명/영업시간/주차/리뷰 보강

방송사 크롤링으로 얻은 가게명+주소로 다이닝코드를 검색하여
메뉴명, 영업시간, 주차, 평점, 리뷰 등 상세 정보를 보강한다.

사용법:
    from utils.diningcode_enricher import enrich_from_diningcode
    result = enrich_from_diningcode("ATO", "대전 유성구 궁동")
"""

import logging
import re

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# 요청 헤더
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9",
}

# 요청 타임아웃
TIMEOUT = 10


def _extract_dong(address: str) -> str:
    """주소에서 동/읍/면 단위 추출
    '대전 유성구 궁동 406-3' → '궁동'
    '서울 마포구 망원동 484-7' → '망원동'
    '경기 성남시 분당구 삼평동 680' → '삼평동'
    """
    if not address:
        return ""
    match = re.search(r"([가-힣]+[동읍면리])\s", address)
    if match:
        return match.group(1)
    # 끝에 있는 경우
    match = re.search(r"([가-힣]+[동읍면리])$", address.strip())
    if match:
        return match.group(1)
    return ""


def _search_rid_naver(shop_name: str, dong: str) -> str | None:
    """네이버 검색으로 다이닝코드 rid 찾기 (API 키 불필요)"""
    query = f"site:diningcode.com {shop_name} {dong}"
    search_url = "https://search.naver.com/search.naver"
    params = {"query": query}

    try:
        resp = requests.get(search_url, params=params, headers=HEADERS, timeout=TIMEOUT)
        if resp.status_code != 200:
            return None

        pattern = r"diningcode\.com/profile\.php\?rid=([A-Za-z0-9]+)"
        match = re.search(pattern, resp.text)
        if match:
            rid = match.group(1)
            logger.info(f"[다이닝코드] rid 발견 (네이버): {shop_name} → {rid}")
            return rid
    except Exception as e:
        logger.debug(f"[다이닝코드] 네이버 검색 실패: {e}")

    return None


def _search_rid_google(shop_name: str, dong: str) -> str | None:
    """구글 검색으로 다이닝코드 rid 찾기 (API 키 불필요)"""
    query = f"site:diningcode.com/profile.php {shop_name} {dong}"
    search_url = "https://www.google.com/search"
    params = {"q": query}
    google_headers = {**HEADERS, "Accept": "text/html"}

    try:
        resp = requests.get(search_url, params=params, headers=google_headers, timeout=TIMEOUT)
        if resp.status_code != 200:
            return None

        pattern = r"diningcode\.com/profile\.php\?rid=([A-Za-z0-9]+)"
        match = re.search(pattern, resp.text)
        if match:
            rid = match.group(1)
            logger.info(f"[다이닝코드] rid 발견 (구글): {shop_name} → {rid}")
            return rid
    except Exception as e:
        logger.debug(f"[다이닝코드] 구글 검색 실패: {e}")

    return None


def _search_rid(shop_name: str, address: str) -> str | None:
    """Rid 검색 - 네이버 → 구글 순서로 시도"""
    dong = _extract_dong(address)
    if not dong:
        # 동 이름 없으면 주소 전체에서 시/구 추출
        match = re.search(r"([가-힣]+[시군구])", address)
        dong = match.group(1) if match else ""

    if not dong:
        logger.warning(f"[다이닝코드] 주소에서 지역명 추출 실패: {address}")
        return None

    # 네이버 먼저
    rid = _search_rid_naver(shop_name, dong)
    if rid:
        return rid

    # 구글 폴백
    rid = _search_rid_google(shop_name, dong)
    if rid:
        return rid

    logger.info(f"[다이닝코드] rid 미발견: {shop_name} ({dong})")
    return None


def _crawl_profile(rid: str) -> dict:
    """다이닝코드 프로필 페이지 크롤링"""
    url = f"https://www.diningcode.com/profile.php?rid={rid}"
    result = {
        "rid": rid,
        "address": "",
        "phone": "",
        "hours": "",
        "closed_days": "",
        "parking": "",
        "rating": "",
        "keywords": [],
        "reviews": [],
        "photo_urls": [],
    }

    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if resp.status_code != 200:
            logger.warning(f"[다이닝코드] 프로필 요청 실패: {rid} (status={resp.status_code})")
            return result

        soup = BeautifulSoup(resp.text, "html.parser")

        # === 평점 ===
        # <div class="star-point"> 안의 <span class="point">
        star_point = soup.select_one("div.star-point span.point")
        if star_point:
            result["rating"] = star_point.get_text(strip=True)

        # === 영업시간 ===
        # 첫 번째 비휴무 hour_time_item에서 추출
        hour_items = soup.select("div.hour_time_item")
        hours_parts = []
        closed_days_list = []
        for item in hour_items:
            times = item.select("span.hour_time")
            if times:
                first_text = times[0].get_text(strip=True)
                if "휴무" in first_text:
                    closed_days_list.append(first_text)
                elif not hours_parts:
                    # 첫 번째 영업일의 시간만 사용
                    for t in times:
                        hours_parts.append(t.get_text(strip=True))

        if hours_parts:
            result["hours"] = " / ".join(hours_parts)
        if closed_days_list:
            result["closed_days"] = ", ".join(closed_days_list)

        # 오늘 휴무 상태도 확인
        today_status = soup.select_one("span.today-main-hours.closed")
        if today_status and not result["closed_days"]:
            # open-desc에서 요일 추출
            open_desc = soup.select_one("span.open-desc")
            if open_desc:
                day_text = open_desc.get_text(strip=True)
                result["closed_days"] = f"{day_text} 휴무"

        # === 키워드 (new-keyword_list) ===
        # 상단의 char li에서 추출
        char_li = soup.select_one("li.char")
        if char_li:
            char_text = char_li.get_text(strip=True)
            raw_keywords = [k.strip() for k in char_text.split(",") if k.strip()]
            result["keywords"] = raw_keywords

        # === 주차 정보 ===
        for kw in result["keywords"]:
            if "주차" in kw:
                result["parking"] = kw
                break
        # 편의시설 키워드에서도 주차 확인
        if not result["parking"]:
            facility_els = soup.select("p.cate.js-keyword-expand-trigger")
            for el in facility_els:
                txt = el.get_text(strip=True)
                if "무료주차" in txt:
                    result["parking"] = "무료주차"
                    break
                if "주차불가" in txt:
                    result["parking"] = "주차불가"
                    break

        # === 리뷰 텍스트 ===
        review_els = soup.select(".review_contents.btxt")
        for el in review_els[:10]:
            text = el.get_text(strip=True)
            # "...더보기" 제거
            text = re.sub(r"\.{2,}더보기$", "", text).strip()
            if text and len(text) > 20:
                result["reviews"].append(text)

        # === 사진 URL ===
        photo_els = soup.select("img.center-croped")
        if not photo_els:
            photo_els = soup.select("div.dc-photo img")
        for img in photo_els[:5]:
            src = img.get("src", "") or img.get("data-src", "")
            if src and "icon" not in src and "logo" not in src and len(src) > 20:
                if not src.startswith("http"):
                    src = "https:" + src if src.startswith("//") else src
                result["photo_urls"].append(src)

        logger.info(f"[다이닝코드] 프로필 크롤링 완료: {rid} "
                     f"(평점 {result['rating']}, 리뷰 {len(result['reviews'])}개, "
                     f"키워드 {len(result['keywords'])}개)")

    except Exception as e:
        logger.exception(f"[다이닝코드] 프로필 크롤링 오류: {rid} - {e}")

    return result


def _extract_menus_from_reviews(reviews: list[str], shop_name: str) -> list[str]:
    """리뷰 텍스트에서 메뉴명 추출 (OpenAI API)"""
    if not reviews:
        return []

    import os
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    except Exception:
        logger.warning("[다이닝코드] OpenAI 클라이언트 없음, 메뉴 추출 스킵")
        return []

    combined = "\n".join(reviews[:5])

    try:
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "mimo-v2.5"),
            messages=[{
                "role": "user",
                "content": f"""다음은 식당 '{shop_name}'의 리뷰입니다.
리뷰에서 음식 메뉴명만 추출하세요.

규칙:
- 음식/음료 이름만 (분위기, 서비스 설명 제외)
- 가장 많이 언급된 순서로 정렬
- 최대 5개
- JSON 배열로만 응답: ["메뉴1", "메뉴2"]

리뷰:
{combined}"""
            }],

            max_completion_tokens=4000,
        )

        text = response.choices[0].message.content.strip()
        # JSON 배열 파싱
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            import json
            menus = json.loads(match.group())
            menus = [m.strip() for m in menus if isinstance(m, str) and m.strip()]
            logger.info(f"[다이닝코드] 메뉴 추출: {shop_name} → {menus}")

            return menus

    except Exception as e:
        logger.warning(f"[다이닝코드] 메뉴 추출 실패: {shop_name} - {e}")

    return []


def enrich_from_diningcode(shop_name: str, address: str = "") -> dict:
    """다이닝코드에서 가게 상세 정보 보강

    Args:
        shop_name: 가게명
        address: 주소 (동 이름 추출용)

    Returns:
        {
            'main_menus': ['고등어봉초밥', '후토마끼', ...],
            'hours': '11:30-20:30',
            'closed_days': '월, 화요일',
            'parking': '무료주차',
            'rating': '4.9',
            'keywords': ['데이트', '숨은맛집', ...],
            'reviews': ['리뷰1', '리뷰2', ...],
            'photo_urls': ['url1', 'url2', ...],
            'source': 'diningcode',
            'rid': 'xxxx'
        }
        검색 실패 시 빈 dict 반환: {}

    """
    empty = {}

    if not shop_name:
        return empty

    # 1. rid 검색
    rid = _search_rid(shop_name, address)
    if not rid:
        return empty

    # 2. 프로필 크롤링
    profile = _crawl_profile(rid)

    # 3. 리뷰에서 메뉴명 추출
    menus = _extract_menus_from_reviews(profile.get("reviews", []), shop_name)

    return {
        "main_menus": menus,
        "hours": profile.get("hours", ""),
        "closed_days": profile.get("closed_days", ""),
        "parking": profile.get("parking", ""),
        "rating": profile.get("rating", ""),
        "keywords": profile.get("keywords", []),
        "reviews": profile.get("reviews", []),
        "photo_urls": profile.get("photo_urls", []),
        "source": "diningcode",
        "rid": rid,
    }

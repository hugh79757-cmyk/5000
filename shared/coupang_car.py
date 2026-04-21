"""자동차 용품 쿠팡 파트너스 링크 생성

TV-show 프로젝트의 coupang_api.py를 기반으로 자동차 블로그 전용으로 구현.
고가 상품 우선 정렬 — 수수료 극대화.
상품 관련성 필터 적용.
링크: productId → coupang.com/vp/products/{id} → deeplink API → /a/ 단축링크
"""

import hmac
import hashlib
import time
import random
import requests
import os
import logging
from urllib.parse import urlencode
from typing import List, Optional

logger = logging.getLogger(__name__)

CAR_KEYWORD_MAP = {
    "블랙박스": ["파인뷰X7000 4채널블랙박스", "아이나비QXD8000 블랙박스", "팅크웨어 아이나비 블랙박스", "파인뷰LX7000 블랙박스", "만도 블랙박스"],
    "점프스타터": ["카버드 점프스타터", "픽스앤고 점프스타터", "비상시동장치", "리튬점프스타터 대용량"],
    "타이어": ["한국타이어 벤투스S2", "금호타이어 엑스타", "미쉐린 프라이머시4", "넥센타이어 엔페라"],
    "세차용품": ["케르허 고압세차기", "카처 고압세척기", "루나버블폼건세트", "세차왕 코팅제세트", "폼건세차세트"],
    "차량용청소기": ["다이슨V15 차량용", "샤오미차량용청소기", "차량용무선청소기"],
    "시트커버": ["프리미엄가죽시트커버", "통풍시트커버 차량용", "차량용쿨링시트", "전좌석가죽시트커버세트"],
    "공기청정기": ["샤오미차량용공기청정기", "LG퓨리케어미니 차량용", "차량용공기청정기", "에어테라피차량용"],
    "차량용충전기": ["차량용고속충전기 시거잭", "차량용무선충전거치대", "시거잭 고속충전기"],
    "네비게이션": ["아이나비L7 네비게이션", "파인드라이브IQ7 내비게이션", "만도네비게이션"],
    "보조배터리": ["차량용대용량보조배터리", "점프스타터겸용보조배터리"],
    "트렁크정리함": ["프리미엄차량트렁크정리함", "접이식트렁크박스", "가죽트렁크정리함"],
    "핸들커버": ["프리미엄가죽핸들커버", "알칸타라핸들커버", "D컷핸들커버"],
    "차량용방향제": ["불스원프리미엄방향제", "차량용디퓨저", "프리미엄차량방향제세트"],
    "와이퍼": ["보쉬에어로트윈와이퍼", "프리미엄실리콘와이퍼", "3M실리콘와이퍼"],
    "코팅제": ["소낙스프리미엄코팅제", "세라믹코팅제 차량용", "유리막코팅제세트", "카나우바왁스"],
    "루프박스": ["투레루프박스", "쿨링루프박스", "차량루프캐리어세트"],
    "캠핑용품": ["차박매트리스", "차박텐트", "차량용인버터2000W", "차박커튼세트"],
}

DEFAULT_CAR_KEYWORDS = ["블랙박스", "세차용품", "차량용충전기", "공기청정기", "점프스타터", "코팅제", "시트커버"]

SEGMENT_KEYWORDS = {
    "SUV": ["루프박스", "캠핑용품", "트렁크정리함"],
    "세단": ["시트커버", "핸들커버", "차량용방향제"],
    "경차": ["차량용충전기", "와이퍼", "차량용방향제"],
    "전기": ["차량용충전기", "세차용품", "공기청정기"],
}

CAR_INCLUDE_WORDS = [
    "차량", "자동차", "카", "시거잭", "블랙박스", "네비", "내비",
    "세차", "코팅", "와이퍼", "타이어", "핸들", "시트", "트렁크",
    "점프", "스타터", "루프", "차박", "방향제", "공기청정",
    "대시보드", "선바이저", "썬팅", "발판", "매트", "안마",
    "거치대", "충전기", "인버터", "보조배터리", "블랙박스",
    "캐치온", "파인뷰", "아이나비", "팅크웨어", "만도",
    "케르허", "카처", "보쉬", "소낙스", "폼건",
]

CAR_EXCLUDE_WORDS = [
    "이어폰", "이어팁", "이어버드", "헤드폰", "헤드셋",
    "화장지", "휴지", "티슈",
    "화장품", "스킨", "로션", "향수", "립",
    "의류", "신발", "바지", "스커트", "원피스", "티셔츠", "자켓",
    "가방", "지갑", "벨트", "모자", "선글라스", "귀걸이", "목걸이",
    "노인", "SOS", "비상 통화", "간호", "경보", "요양",
    "아이폰", "갤럭시", "노트북", "태블릿", "키보드", "마우스",
    "유아", "아기", "아동", "키즈", "분유", "기저귀",
    "코카콜라", "콜라", "사이다", "음료수", "과자", "라면",
    "커피", "맥주", "소주", "담배", "게임", "장난감",
    "벽걸이", "여행용 전원", "테슬라 모델",
    "냄비", "프라이팬", "식기", "수저", "접시",
]


def _is_car_relevant(product_name: str) -> bool:
    name_lower = product_name.lower()
    for word in CAR_EXCLUDE_WORDS:
        if word in name_lower:
            logger.debug(f"제외됨 [{word}]: {product_name[:40]}")
            return False
    for word in CAR_INCLUDE_WORDS:
        if word in name_lower:
            return True
    logger.debug(f"관련성 없음: {product_name[:40]}")
    return False


class CoupangCar:
    """자동차 블로그용 쿠팡 파트너스"""

    BASE_URL = "https://api-gateway.coupang.com"

    def __init__(self):
        self.access_key = os.getenv('COUPANG_ACCESS_KEY', '')
        self.secret_key = os.getenv('COUPANG_SECRET_KEY', '')
        self.partner_id = os.getenv('COUPANG_PARTNER_ID', '')

    def is_configured(self) -> bool:
        return bool(self.access_key and self.secret_key and self.partner_id)

    def _generate_signature(self, method: str, url_path: str, query_string: str = "") -> dict:
        datetime_now = time.strftime('%y%m%dT%H%M%SZ', time.gmtime())
        message = datetime_now + method + url_path + query_string
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        authorization = f"CEA algorithm=HmacSHA256, access-key={self.access_key}, signed-date={datetime_now}, signature={signature}"
        return {"Authorization": authorization, "Content-Type": "application/json"}

    def search_products(self, keyword: str, limit: int = 5) -> list:
        if not self.is_configured():
            return []
        try:
            url_path = "/v2/providers/affiliate_open_api/apis/openapi/products/search"
            params = {"keyword": keyword, "limit": limit}
            query_string = urlencode(params)
            headers = self._generate_signature("GET", url_path, query_string)
            response = requests.get(
                f"{self.BASE_URL}{url_path}?{query_string}",
                headers=headers, timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                return data.get('data', {}).get('productData', [])
            return []
        except requests.RequestException as e:
            logger.error(f"[COUPANG_ERROR] Search failed [{keyword}]: {e}")
            return []

    def generate_affiliate_link(self, product_id) -> str:
        """productId로 일반 URL을 구성한 뒤 deeplink API로 /a/ 단축링크 생성"""
        if not self.is_configured():
            return ""
        try:
            # productId → 일반 coupang URL 구성
            normal_url = f"https://www.coupang.com/vp/products/{product_id}"

            url_path = "/v2/providers/affiliate_open_api/apis/openapi/deeplink"
            headers = self._generate_signature("POST", url_path)
            body = {"coupangUrls": [normal_url]}
            response = requests.post(
                f"{self.BASE_URL}{url_path}",
                headers=headers, json=body, timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                links = data.get('data', [])
                if links:
                    short = links[0].get('shortenUrl', '')
                    if short and '/a/' in short:
                        return short
            logger.warning(f"deeplink 변환 실패: productId={product_id}")
            return ""
        except requests.RequestException as e:
            logger.error(f"[COUPANG_ERROR] Affiliate link generation failed: {e}")
            return ""

    def get_car_product_links(self, segment: str = "", fuel_type: str = "", count: int = 2) -> str:
        if not self.is_configured():
            logger.warning("쿠팡 파트너스 미설정 — 스킵")
            return ""

        keywords = list(DEFAULT_CAR_KEYWORDS)
        for seg_key, seg_kws in SEGMENT_KEYWORDS.items():
            if seg_key in segment or seg_key in fuel_type:
                keywords.extend(seg_kws)

        random.shuffle(keywords)

        products_md = []
        tried = 0
        for kw in keywords:
            if len(products_md) >= count:
                break
            if tried >= count + 4:
                break
            tried += 1

            kw_detail = CAR_KEYWORD_MAP.get(kw, [kw])
            search_term = random.choice(kw_detail[:3])

            results = self.search_products(search_term, limit=5)
            results = [p for p in results if _is_car_relevant(p.get('productName', ''))]
            results.sort(key=lambda p: p.get('productPrice', 0), reverse=True)

            for product in results:
                product_id = product.get('productId', '')
                if not product_id:
                    continue

                name = product.get('productName', search_term)
                price = product.get('productPrice', 0)

                affiliate_url = self.generate_affiliate_link(product_id)
                if not affiliate_url:
                    continue

                if price:
                    price_str = f"{int(price):,}원"
                    products_md.append(f"- [{name}]({affiliate_url}) — {price_str}")
                else:
                    products_md.append(f"- [{name}]({affiliate_url})")
                break  # 이 키워드에서 1개 확보했으므로 다음 키워드로

        if not products_md:
            return ""

        md = "\n\n## 차량 관리에 도움되는 추천 용품\n\n"
        md += "이 글에서 분석한 유지비를 줄이는 데 도움이 되는 제품입니다.\n\n"
        md += "\n".join(products_md)
        md += "\n\n> **이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.**\n"

        return md


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv("/Users/twinssn/Projects/5000/.env")

    coupang = CoupangCar()
    print(f"설정: {coupang.is_configured()}")

    if coupang.is_configured():
        for seg in ["SUV", "세단", "전기"]:
            print(f"\n=== {seg} ===")
            md = coupang.get_car_product_links(segment=seg, count=2)
            if md:
                print(md)
            else:
                print("  상품 없음")

"""시니어 복지 블로그용 쿠팡 파트너스 링크 생성

coupang_car.py를 기반으로 시니어 복지 카테고리 전용으로 구현.
고가 상품 우선 정렬 — 수수료 극대화.
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

# 시니어 복지 카테고리별 키워드 맵 — 고가순 정렬
SENIOR_KEYWORD_MAP = {
    "혈압계": ["오므론 자동혈압계", "녹십자 블루투스혈압계", "시티즌 가정용혈압계"],
    "혈당측정기": ["아큐첵 가이드 혈당측정기", "원터치셀렉트 혈당측정기세트", "케어센스N프리미엄"],
    "영양제": ["종근당 칼슘마그네슘아연비타민D", "뉴트리원 관절 보스웰리아", "안국건강 루테인오메가3"],
    "보행보조기": ["유모차형보행기", "실버카 경량보행차", "접이식 보행보조차"],
    "안마기": ["제스파 목어깨안마기", "브람스 안마의자", "코지마 안마의자", "클럭 무선안마기"],
    "난방용품": ["신일 전기요", "한일 온수매트", "귀뚜라미 전기장판", "일월 탄소매트"],
    "성인용기저귀": ["디펜드 성인용기저귀", "좋은느낌 성인팬티기저귀", "유한킴벌리 디펜드언더패드"],
    "간병용품": ["환자용침대 전동", "욕창방지매트리스", "이동식변기 접이식", "환자용휠체어"],
    "지팡이": ["탄소경량지팡이", "접이식지팡이", "4발지팡이 노인용", "LED야간지팡이"],
    "돋보기": ["프리미엄 확대경", "LED돋보기안경", "목걸이형확대경", "독서용돋보기"],
    "보청기": ["시그니아 보청기", "스타키 보청기", "포낙 보청기", "벨톤 보청기"],
    "건강식품": ["홍삼정 에브리타임", "녹용진액 선물세트", "산수유진액", "흑마늘진액"],
    "운동용품": ["시니어 탄력밴드세트", "노인 실내자전거", "스텝퍼 노인용", "시니어 요가매트"],
    "미끄럼방지": ["욕실미끄럼방지매트", "계단미끄럼방지테이프", "현관미끄럼방지", "욕조손잡이"],
}

# 카테고리별 기본 키워드 매핑
CATEGORY_KEYWORDS = {
    "의료지원": ["혈압계", "혈당측정기", "영양제", "보청기"],
    "돌봄서비스": ["성인용기저귀", "간병용품", "미끄럼방지"],
    "교통복지": ["지팡이", "보행보조기", "미끄럼방지"],
    "생활지원": ["난방용품", "돋보기", "미끄럼방지"],
    "연금생활지원": ["건강식품", "영양제", "혈압계"],
    "일자리금융": ["건강식품", "운동용품", "영양제"],
    "문화여가": ["운동용품", "돋보기", "건강식품"],
}

DEFAULT_KEYWORDS = ["혈압계", "영양제", "건강식품", "난방용품"]

EXCLUDE_WORDS = ["코카콜라", "콜라", "사이다", "음료수", "과자", "라면", "커피", "맥주",
                 "소주", "담배", "게임", "장난감", "화장품", "향수", "의류", "신발",
                 "팬츠", "바지", "스커트", "원피스", "티셔츠", "블라우스", "자켓",
                 "가방", "지갑", "벨트", "모자", "선글라스", "귀걸이", "목걸이",
                 "아이폰", "갤럭시", "노트북", "태블릿", "이어폰", "키보드",
                 "유아", "아기", "아동", "키즈", "장난감", "분유", "기저귀패드",
                 "포카리",
                 "이온음료",
                 "생수",
                 "음료",
                 "주스",
                 "탄산",
                 "전기요",
                 "전기장판",
                 "매트리스패드",
                 "이불",
                 "베개",
                 "세제",
                 "섬유유연제",
                 "주방세제",
                 "치약",
                 "마스크",
                 "물티슈",
                 "화장지",
                 "키친타올",
                 "반찬",
                 "김치",
                 "라면",
                 "과자",
                 "커피",
                 "차"]

def _is_relevant(product_name, category):
    name_lower = product_name.lower()
    for word in EXCLUDE_WORDS:
        if word in name_lower:
            return False
    return True


class CoupangSenior:
    """시니어 복지 블로그용 쿠팡 파트너스"""

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

    def search_products(self, keyword: str, limit: int = 3) -> list:
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
        except Exception as e:
            logger.error(f"쿠팡 검색 실패 [{keyword}]: {e}")
            return []

    def generate_affiliate_link(self, product_id) -> str:
        """productId로 일반 URL 구성 후 deeplink API로 /a/ 단축링크 생성"""
        if not self.is_configured():
            return ""
        try:
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
        except Exception as e:
            logger.error(f"제휴 링크 생성 실패: {e}")
            return ""

    def get_senior_product_links(self, category: str = "", count: int = 2) -> str:
        if not self.is_configured():
            logger.warning("쿠팡 파트너스 미설정 — 스킵")
            return ""

        keywords = list(CATEGORY_KEYWORDS.get(category, DEFAULT_KEYWORDS))
        random.shuffle(keywords)

        products_md = []
        for kw in keywords[:count + 2]:
            if len(products_md) >= count:
                break

            kw_detail = SENIOR_KEYWORD_MAP.get(kw, [kw])
            search_term = random.choice(kw_detail[:3])

            results = self.search_products(search_term, limit=5)
            # 연관성 필터 적용
            results = [p for p in results if _is_relevant(p.get('productName', ''), category)]
            if results:
                product = results[0]
                name = product.get('productName', search_term)[:30]
                price = product.get('productPrice', 0)
                product_url = product.get('productUrl', '')

                # 이미 affiliate URL이면 그대로 사용
                if product_url and 'link.coupang.com' in product_url:
                    affiliate_url = product_url
                else:
                    product_id = product.get('productId', '')
                    if not product_id:
                        continue
                    affiliate_url = self.generate_affiliate_link(product_id)

                if not affiliate_url:
                    continue

                if price:
                    price_str = f"{int(price):,}원"
                    products_md.append(f"- [{name}]({affiliate_url}) — {price_str}")
                else:
                    products_md.append(f"- [{name}]({affiliate_url})")

        if not products_md:
            return ""

        md = "\n\n---\n\n**어르신 건강관리에 도움되는 추천 제품**\n\n"
        md += "\n".join(products_md)
        md += "\n\n> 이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.\n"

        return md


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv("/Users/twinssn/Projects/5000/.env")

    coupang = CoupangSenior()
    print(f"설정 완료: {coupang.is_configured()}")

    if coupang.is_configured():
        for cat in ["의료지원", "돌봄서비스", "교통복지"]:
            print(f"\n=== {cat} ===")
            md = coupang.get_senior_product_links(category=cat, count=2)
            if md:
                print(md)
            else:
                print("  상품 없음")

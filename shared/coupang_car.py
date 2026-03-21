"""자동차 용품 쿠팡 파트너스 링크 생성

TV-show 프로젝트의 coupang_api.py를 기반으로 자동차 블로그 전용으로 구현.
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

# 자동차 용품 키워드 맵 — 고가순 정렬 (앞 3개 우선 사용)
CAR_KEYWORD_MAP = {
    "블랙박스": ["파인뷰X7000 4채널블랙박스", "아이나비QXD8000 블랙박스", "팅크웨어 아이나비 블랙박스", "파인뷰LX7000 블랙박스", "만도 블랙박스"],
    "점프스타터": ["카버드 점프스타터", "픽스앤고 점프스타터", "비상시동장치", "리튬점프스타터 대용량"],
    "타이어": ["한국타이어 벤투스S2", "금호타이어 엑스타", "미쉐린 프라이머시4", "넥센타이어 엔페라"],
    "세차용품": ["케르허 고압세차기", "카처 고압세척기", "루나버블폼건세트", "세차왕 코팅제세트", "폼건세차세트"],
    "차량용청소기": ["다이슨V15 차량용", "샤오미차량용청소기", "차량용무선청소기"],
    "시트커버": ["프리미엄가죽시트커버", "통풍시트커버", "차량용쿨링시트", "전좌석가죽시트커버세트"],
    "공기청정기": ["샤오미차량용공기청정기", "LG퓨리케어미니", "차량용공기청정기", "에어테라피차량용"],
    "차량용충전기": ["차량용고속충전기", "차량용무선충전거치대", "120W초고속시거잭충전기"],
    "네비게이션": ["아이나비L7 네비게이션", "파인드라이브IQ7 내비게이션", "만도네비게이션"],
    "보조배터리": ["차량용대용량보조배터리", "점프스타터겸용보조배터리"],
    "트렁크정리함": ["프리미엄차량트렁크정리함", "접이식트렁크박스", "가죽트렁크정리함"],
    "핸들커버": ["프리미엄가죽핸들커버", "알칸타라핸들커버", "D컷핸들커버"],
    "차량용방향제": ["불스원프리미엄방향제", "차량용디퓨저", "프리미엄차량방향제세트"],
    "와이퍼": ["보쉬에어로트윈와이퍼", "프리미엄실리콘와이퍼", "3M실리콘와이퍼"],
    "코팅제": ["소낙스프리미엄코팅제", "세라믹코팅제", "유리막코팅제세트", "카나우바왁스"],
    "루프박스": ["투레루프박스", "쿨링루프박스", "차량루프캐리어세트"],
    "캠핑용품": ["차박매트리스", "차박텐트", "차량용인버터2000W", "차박커튼세트"],
}

# 범용 키워드 — 어떤 차종이든 매칭
DEFAULT_CAR_KEYWORDS = ["블랙박스", "세차용품", "차량용충전기", "공기청정기", "점프스타터", "코팅제", "시트커버"]

# 차종별 추가 매칭
SEGMENT_KEYWORDS = {
    "SUV": ["루프박스", "캠핑용품", "트렁크정리함"],
    "세단": ["시트커버", "핸들커버", "차량용방향제"],
    "경차": ["차량용충전기", "와이퍼", "차량용방향제"],
    "전기": ["차량용충전기", "보조배터리", "세차용품"],
}


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
    
    def generate_affiliate_link(self, product_url: str) -> str:
        if not self.is_configured():
            return product_url
        try:
            url_path = "/v2/providers/affiliate_open_api/apis/openapi/deeplink"
            headers = self._generate_signature("POST", url_path)
            body = {"coupangUrls": [product_url]}
            response = requests.post(
                f"{self.BASE_URL}{url_path}",
                headers=headers, json=body, timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                links = data.get('data', [])
                if links:
                    return links[0].get('shortenUrl', product_url)
            return product_url
        except Exception as e:
            logger.error(f"제휴 링크 생성 실패: {e}")
            return product_url
    
    def get_car_product_links(self, segment: str = "", fuel_type: str = "", count: int = 2) -> str:
        """자동차 글에 삽입할 쿠팡 상품 링크 마크다운 생성
        
        Args:
            segment: 차량 세그먼트 (SUV, 세단, 경차 등)
            fuel_type: 연료 타입 (전기, 가솔린/하이브리드 등)
            count: 상품 수 (기본 2개)
        
        Returns:
            마크다운 형태의 상품 추천 블록
        """
        if not self.is_configured():
            logger.warning("쿠팡 파트너스 미설정 — 스킵")
            return ""
        
        # 키워드 선택: 세그먼트별 + 범용에서 랜덤
        keywords = list(DEFAULT_CAR_KEYWORDS)
        for seg_key, seg_kws in SEGMENT_KEYWORDS.items():
            if seg_key in segment or seg_key in fuel_type:
                keywords.extend(seg_kws)
        
        random.shuffle(keywords)
        
        products_md = []
        for kw in keywords[:count + 2]:  # 여유분 포함
            if len(products_md) >= count:
                break
            
            kw_detail = CAR_KEYWORD_MAP.get(kw, [kw])
            search_term = random.choice(kw_detail[:3])  # 고가 상위 3개 중 랜덤
            
            results = self.search_products(search_term, limit=1)
            if results:
                product = results[0]
                name = product.get('productName', search_term)
                price = product.get('productPrice', 0)
                url = product.get('productUrl', '')
                
                if url:
                    affiliate_url = self.generate_affiliate_link(url)
                    if price:
                        price_str = f"{int(price):,}원"
                        products_md.append(f"- [{name}]({affiliate_url}) — {price_str}")
                    else:
                        products_md.append(f"- [{name}]({affiliate_url})")
        
        if not products_md:
            return ""
        
        md = "\n\n## 차량 관리에 도움되는 추천 용품\n\n"
        md += "이 글에서 분석한 유지비를 줄이는 데 도움이 되는 제품입니다.\n\n"
        md += "\n".join(products_md)
        md += "\n\n> 이 링크를 통해 구매하시면 소정의 수수료를 받을 수 있습니다.\n"
        
        return md

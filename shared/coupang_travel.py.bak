import os
import sys
import time
import hmac
import hashlib
import logging
import requests
from urllib.parse import urlencode

sys.path.insert(0, "/Users/twinssn/Projects/5000")
from dotenv import load_dotenv
load_dotenv("/Users/twinssn/Projects/5000/.env")

logger = logging.getLogger(__name__)

# ── 블로그별 키워드 맵 ──────────────────────────────────────
TRAVEL_KEYWORD_MAP = {
    "travel-hugo": [
        "캠핑 의자", "캠핑 테이블", "캠핑 랜턴", "캠핑 화로대",
        "캠핑 침낭", "캠핑 매트", "캠핑 타프", "캠핑 코펠",
        "차박 매트", "차박 커튼", "캠핑 수납박스", "캠핑 감성 조명",
    ],
    "travel1-hugo": [
        "여행용 돗자리", "접이식 의자", "휴대용 선풍기", "여행용 우산",
        "여행용 보조배터리", "셀카봉 삼각대", "여행용 물병",
    ],
    "travel2-hugo": [
        "여행용 카메라 가방", "등산 스틱", "트레킹화", "등산 배낭",
        "여행용 보조배터리", "셀카봉 삼각대", "여행 크로스백",
    ],
    "travel3-hugo": [
        "여행용 텀블러", "휴대용 수저세트", "여행용 물병",
        "차량용 냉온장고", "보냉백", "여행용 도시락통",
    ],
    "travel4-hugo": [
        "여행용 캐리어", "여행용 파우치 세트", "목베개", "여행용 보조배터리",
        "셀카봉 삼각대", "여행 크로스백", "차량용 핸드폰 거치대",
    ],
}

DEFAULT_TRAVEL_KEYWORDS = [
    "여행용 보조배터리", "셀카봉 삼각대", "여행용 파우치",
    "휴대용 선풍기", "여행용 목베개", "여행 크로스백",
]

# ── 필터 단어 ────────────────────────────────────────────
TRAVEL_INCLUDE_WORDS = [
    "캠핑", "여행", "트레킹", "등산", "아웃도어", "캐리어", "배낭",
    "텀블러", "물병", "보온", "보냉", "돗자리", "랜턴", "침낭",
    "매트", "타프", "화로", "코펠", "차박", "수납", "접이식",
    "선풍기", "우산", "보조배터리", "셀카봉", "삼각대", "목베개",
    "파우치", "크로스백", "거치대", "냉온장고", "도시락", "수저",
    "의자", "테이블", "카메라", "스틱", "트레킹화", "등산화",
    "방수", "경량", "폴딩", "휴대용", "미니", "차량용",
]

TRAVEL_EXCLUDE_WORDS = [
    "이어폰", "이어팁", "화장지", "휴지", "변기", "SOS",
    "보청기", "지팡이", "혈압", "성인용", "기저귀", "유아",
]


class CoupangTravel:
    def __init__(self):
        self.access_key = os.environ.get("COUPANG_ACCESS_KEY", "")
        self.secret_key = os.environ.get("COUPANG_SECRET_KEY", "")
        self.partner_id = os.environ.get("COUPANG_PARTNER_ID", "")

    def is_configured(self):
        return bool(self.access_key and self.secret_key and self.partner_id)

    def _generate_signature(self, method, url_path, query_string=""):
        datetime_now = time.strftime("%y%m%dT%H%M%SZ", time.gmtime())
        message = datetime_now + method + url_path + query_string
        signature = hmac.new(
            self.secret_key.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return f"CEA algorithm=HmacSHA256, access-key={self.access_key}, signed-date={datetime_now}, signature={signature}"

    def search_products(self, keyword, limit=5):
        if not self.is_configured():
            return []
        method = "GET"
        path = "/v2/providers/affiliate_open_api/apis/openapi/products/search"
        params = {"keyword": keyword, "limit": limit}
        query_string = urlencode(params)
        authorization = self._generate_signature(method, path, query_string)
        url = f"https://api-gateway.coupang.com{path}?{query_string}"
        try:
            resp = requests.get(url, headers={"Authorization": authorization}, timeout=10)
            data = resp.json()
            return data.get("data", {}).get("productData", [])
        except Exception as e:
            logger.error("쿠팡 검색 실패 (%s): %s", keyword, e)
            return []

    def generate_affiliate_link(self, product_id):
        if not product_id:
            return ""
        original_url = f"https://www.coupang.com/vp/products/{product_id}"
        method = "POST"
        path = "/v2/providers/affiliate_open_api/apis/openapi/v1/deeplink"
        authorization = self._generate_signature(method, path)
        url = f"https://api-gateway.coupang.com{path}"
        try:
            resp = requests.post(
                url,
                headers={"Authorization": authorization, "Content-Type": "application/json"},
                json={"coupangUrls": [original_url]},
                timeout=10,
            )
            data = resp.json()
            links = data.get("data", [])
            if links:
                short_url = links[0].get("shortenUrl", "")
                if "/a/" in short_url:
                    return short_url
        except Exception as e:
            logger.error("딥링크 변환 실패 (pid=%s): %s", product_id, e)
        return ""

    @staticmethod
    def _is_travel_relevant(product_name):
        name_lower = product_name.lower()
        for ex in TRAVEL_EXCLUDE_WORDS:
            if ex in name_lower:
                return False
        for inc in TRAVEL_INCLUDE_WORDS:
            if inc in name_lower:
                return True
        return False

    def get_travel_product_links(self, blog_id="travel-hugo", count=2):
        if not self.is_configured():
            return ""
        import random
        keywords = TRAVEL_KEYWORD_MAP.get(blog_id, DEFAULT_TRAVEL_KEYWORDS)
        random.shuffle(keywords)

        products_found = []
        attempts = 0
        max_attempts = count + 4

        for kw in keywords:
            if len(products_found) >= count or attempts >= max_attempts:
                break
            attempts += 1
            results = self.search_products(kw, limit=5)
            relevant = [p for p in results if self._is_travel_relevant(p.get("productName", ""))]
            relevant.sort(key=lambda x: x.get("productPrice", 0), reverse=True)
            for p in relevant:
                pid = p.get("productId")
                if not pid:
                    continue
                dup = any(existing["productId"] == pid for existing in products_found)
                if dup:
                    continue
                link = self.generate_affiliate_link(pid)
                if link:
                    products_found.append({
                        "productId": pid,
                        "productName": p.get("productName", ""),
                        "productPrice": p.get("productPrice", 0),
                        "productImage": p.get("productImage", ""),
                        "affiliateLink": link,
                    })
                    break

        if not products_found:
            return ""

        lines = ["\n\n---\n", "## 여행 준비에 도움되는 추천 용품\n"]
        for p in products_found:
            price_str = f'{p["productPrice"]:,}원'
            lines.append(f'- [{p["productName"]}]({p["affiliateLink"]}) — {price_str}')
        lines.append("")
        lines.append('> **이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.**')
        lines.append("")
        return "\n".join(lines)

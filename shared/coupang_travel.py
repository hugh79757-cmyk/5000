"""여행/부동산 블로그용 쿠팡 파트너스 링크 생성 — 리팩토링 v2

⚠️ 쿠팡 파트너스 API RATE LIMIT (2026-07-16 제재)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- 검색 API:   분당 50회 (search_products)
- 링크생성:   분당 50회 (generate_affiliate_link = deeplink POST)
- 전체 API:   분당 100회
- 경고 3회 누적 → 이용제한 (재발생 시 추가 제재)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import hashlib
import hmac
import logging
import os
import sys
import time
from difflib import SequenceMatcher
from urllib.parse import urlencode

import requests

sys.path.insert(0, "/Users/twinssn/Projects/5000")
from dotenv import load_dotenv

load_dotenv("/Users/twinssn/Projects/5000/.env")

logger = logging.getLogger(__name__)

# ── 블로그별 카테고리별 키워드 맵 (브랜드명 제거, 용도별 분배) ──────────────────────────────────────
TRAVEL_KEYWORD_MAP = {
    "travel-hugo": {                    # 캠핑/아웃도어
        "shelter": ["캠핑 텐트", "타프", "그늘막", "차박 텐트"],
        "comfort": ["캠핑 의자", "캠핑 테이블", "캠핑 매트", "에어매트"],
        "utility": ["캠핑 랜턴", "캠핑 화로대", "캠핑 코펠", "캠핑 버너", "캠핑 수납박스"],
    },
    "travel1-hugo": {                   # 축제/행사
        "outdoor": ["여행용 돗자리", "접이식 의자", "휴대용 선풍기", "피크닉 매트"],
        "tech": ["여행용 보조배터리", "셀카봉 삼각대", "방수팩", "휴대용 와이파이"],
        "comfort": ["목베개", "여행용 물병", "여행용 파우치", "쿨토시"],
    },
    "travel2-hugo": {                   # 문화유산/등산
        "gear": ["등산 배낭", "트레킹 폴", "등산화", "등산 스틱"],
        "tech": ["액션캠", "보조배터리", "방수 케이스", "핸드폰 거치대"],
        "comfort": ["압축 수건", "등산 양말", "자외선 차단 모자", "쿨마스크"],
    },
    "travel3-hugo": {                   # 맛집/식도락
        "container": ["보온 도시락", "스텐 텀블러", "식기 세트", "수저 세트"],
        "cooking": ["휴대용 버너", "코펠 세트", "그릴 팬", "캠핑 그릇"],
        "storage": ["쿨러백", "음식 보관 용기", "진공 포장기", "아이스박스"],
    },
    "travel4-hugo": {                   # 여행코스/일정
        "luggage": ["기내용 캐리어", "여행용 백팩", "압축 파우치", "여행용 캐리어 커버"],
        "tech": ["차량용 충전기", "보조배터리", "멀티 어댑터", "차량용 핸드폰 거치대"],
        "comfort": ["목베개", "안대", "압축 양말", "여행용 슬리퍼"],
    },
    # ── RAP (부동산) 블로그 — 고가 입주/이사 가전 ──
    "rap-hugo": {
        "major": ["삼성 비스포크 냉장고", "LG 건조기", "삼성 식기세척기", "LG 공기청정기"],
        "climate": ["삼성 에어컨", "LG 스타일러", "다이슨 무선청소기", "코웨이 정수기"],
        "living": ["LG 워시타워", "코웨이 비데", "삼성 인덕션", "시몬스 매트리스", "일룸 매트리스"],
    },
    "rap2-hugo": {
        "major": ["냉장고", "세탁기", "에어컨", "매트리스", "건조기"],
        "kitchen": ["식기세척기", "공기청정기", "무선청소기", "인덕션", "전자레인지"],
        "living": ["가스레인지", "정수기", "비데", "LED조명", "스마트도어락", "수납장"],
    },
    "rap3-hugo": {
        "premium": ["안마의자", "스타일러", "건조기", "공기청정기", "식기세척기"],
        "clean": ["로봇청소기", "무선청소기", "음식물처리기", "정수기", "비데"],
        "home": ["매트리스", "전동커튼", "와인셀러", "커피머신", "제습기"],
    },
    "rap4-hugo": {
        "small": ["미니세탁기", "공기청정기", "건조기", "전자레인지", "로봇청소기"],
        "climate": ["제습기", "무선청소기", "비데", "정수기", "인덕션"],
        "living": ["전기포트", "접이식빨래건조대", "수납선반", "전신거울", "LED스탠드"],
    },
    "rap5-hugo": {
        "major": ["삼성 비스포크 냉장고", "LG 시그니처 세탁기", "삼성 식기세척기"],
        "premium": ["드롱기 커피머신", "LG 퓨리케어 공기청정기", "다이슨 에어랩"],
        "home": ["삼성 비스포크 에어컨", "LG 스타일러", "일룸 매트리스", "보쉬 식기세척기"],
    },
}

DEFAULT_TRAVEL_KEYWORDS = {
    "general": ["여행용 보조배터리", "셀카봉 삼각대", "여행용 파우치", "휴대용 선풍기", "여행용 목베개", "여행 크로스백"],
}

# ── 필터 단어 ────────────────────────────────────────────
TRAVEL_INCLUDE_WORDS = [
    "캠핑", "여행", "트레킹", "등산", "아웃도어", "캐리어", "배낭",
    "텀블러", "물병", "보온", "보냉", "돗자리", "랜턴", "침낭",
    "매트", "타프", "화로", "코펠", "차박", "수납", "접이식",
    "선풍기", "우산", "보조배터리", "셀카봉", "삼각대", "목베개",
    "파우치", "크로스백", "거치대", "냉온장고", "도시락", "수저",
    "식기", "머그컵", "에어프라이어", "미니밥솥", "와인오프너", "음식보관",
    "의자", "테이블", "카메라", "스틱", "트레킹화", "등산화",
    "방수", "경량", "폴딩", "휴대용", "미니", "차량용",
    "공기청정기", "로봇청소기", "건조기", "식기세척기", "안마의자",
    "매트리스", "스타일러", "냉장고", "세탁기", "에어컨", "제습기",
    "전자레인지", "미니세탁기", "무선청소기", "음식물처리기", "정수기",
    "비데", "가습기", "전동커튼", "스마트도어락", "인덕션", "전기오븐",
    "커피머신", "와인셀러", "공기순환기", "수납", "행거", "신발장",
    "LED", "전기포트", "전기히터", "선풍기", "거울", "빨래건조대",
]

TRAVEL_EXCLUDE_WORDS = [
    "이어폰", "이어팁", "화장지", "휴지", "변기", "SOS",
    "보청기", "지팡이", "혈압", "성인용", "기저귀", "유아",
    "사무용", "사무실", "회의실", "독서실", "학생의자", "책상의자",
    "컴퓨터의자", "공부의자", "게이밍", "오피스",
]

# 블로그별 섹션 제목
SECTION_TITLES = {
    "travel-hugo": "여행 준비에 도움되는 추천 용품",
    "travel1-hugo": "축제·나들이 준비에 도움되는 용품",
    "travel2-hugo": "문화유산 탐방에 도움되는 용품",
    "travel3-hugo": "맛집 탐방에 도움되는 용품",
    "travel4-hugo": "여행코스 준비에 도움되는 용품",
    "rap-hugo": "새 아파트 입주 준비 추천 가전",
    "rap2-hugo": "청약 당첨 후 입주 준비 추천 가전",
    "rap3-hugo": "이사·입주 시 필요한 추천 가전",
    "rap4-hugo": "전세 입주 시 필요한 추천 가전",
    "rap5-hugo": "새 아파트 입주 준비 추천 가전",
}


class CoupangTravel:
    def __init__(self) -> None:
        self.access_key = os.environ.get("COUPANG_ACCESS_KEY", "")
        self.secret_key = os.environ.get("COUPANG_SECRET_KEY", "")
        self.partner_id = os.environ.get("COUPANG_PARTNER_ID", "")
        
        # 세션 레벨 캐시: productId → {name, price, link, image, category}
        self._session_cache = {}
        # 블로그별 사용 이력: blog_id → set(productId)
        self._blog_used = {}
        # 상품명 유사도 캐시
        self._name_similarity_cache = {}

    def is_configured(self):
        return bool(self.access_key and self.secret_key and self.partner_id)

    def _generate_signature(self, method, url_path, query_string="") -> str:
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
            logger.exception("쿠팡 검색 실패 (%s): %s", keyword, e)
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
            logger.exception("딥링크 변환 실패 (pid=%s): %s", product_id, e)
        return ""

    @staticmethod
    def _is_travel_relevant(product_name) -> bool:
        name_lower = product_name.lower()
        for ex in TRAVEL_EXCLUDE_WORDS:
            if ex in name_lower:
                return False
        return any(inc in name_lower for inc in TRAVEL_INCLUDE_WORDS)

    def _similarity(self, a: str, b: str) -> float:
        """상품명 유사도 (SequenceMatcher ratio)"""
        cache_key = (a, b)
        if cache_key in self._name_similarity_cache:
            return self._name_similarity_cache[cache_key]
        ratio = SequenceMatcher(None, a, b).ratio()
        self._name_similarity_cache[cache_key] = ratio
        return ratio

    def _deduplicate(self, products: list, blog_id: str) -> list:
        """productId + 상품명 유사도(Levenshtein > 0.8) 중복 제거"""
        unique = []
        seen_ids = set()
        seen_names = []
        
        blog_used = self._blog_used.get(blog_id, set())
        
        for p in products:
            pid = p.get("productId")
            name = p.get("productName", "")
            
            # 1) productId 중복 (세션 + 블로그 이력)
            if pid in seen_ids or pid in blog_used:
                continue
            
            # 2) 상품명 유사도 (SequenceMatcher ratio > 0.8)
            is_dup = False
            for existing_name in seen_names:
                if self._similarity(name, existing_name) > 0.8:
                    is_dup = True
                    break
            if is_dup:
                continue
            
            seen_ids.add(pid)
            seen_names.append(name)
            unique.append(p)
        
        # 블로그별 사용 이력 업데이트
        self._blog_used.setdefault(blog_id, set()).update(seen_ids)
        return unique

    def _distribute_by_category(self, products: list, count: int) -> list:
        """카테고리별 1개씩 우선 배정, 부족하면 나머지 채움"""
        # TRAVEL_KEYWORD_MAP의 카테고리 구조를 이용해 매핑
        # 단순화: 순서대로 골라서 분배 시도
        if len(products) <= count:
            return products
        
        result = []
        # 카테고리 키워드와 매칭되는 것부터 우선 선택
        # 나머지는 가격 높은 순으로 채움
        products.sort(key=lambda x: x.get("productPrice", 0), reverse=True)
        return products[:count]

    def get_product_cards(self, blog_id: str = "travel-hugo", count: int = 3) -> str:
        """
        블로그당 3개 상품 카드 반환 (HTML 그리드)
        - 카테고리 분배: shelter/comfort/utility 등 골고루
        - 중복 방지: 세션 캐시 + 블로그별 사용 이력
        - 반환: <div class="coupang-product-grid">...</div>
        """
        if not self.is_configured():
            return ""
        
        # 키워드 맵에서 카테고리별 키워드 수집
        keyword_map = TRAVEL_KEYWORD_MAP.get(blog_id, DEFAULT_TRAVEL_KEYWORDS)
        
        # 카테고리별 대표 키워드 1개씩 추출 (최대 count개 카테고리)
        categories = list(keyword_map.keys())[:count]
        selected_keywords = []
        for cat in categories:
            kws = keyword_map[cat]
            if kws:
                selected_keywords.append(kws[0])  # 각 카테고리 첫 번째 키워드
        
        # 키워드가 부족하면 기본 키워드에서 채움
        if len(selected_keywords) < count:
            for kw in DEFAULT_TRAVEL_KEYWORDS.get("general", []):
                if len(selected_keywords) >= count:
                    break
                selected_keywords.append(kw)
        
        # 배치 검색 (각 키워드당 3개씩)
        all_products = []
        for kw in selected_keywords:
            results = self.search_products(kw, limit=3)
            relevant = [p for p in results if self._is_travel_relevant(p.get("productName", ""))]
            # 카테고리 태그 추가
            for p in relevant:
                p["_category"] = kw
            all_products.extend(relevant)
        
        # 중복 제거
        all_products = self._deduplicate(all_products, blog_id)
        
        # 카테고리별 분배
        final_products = self._distribute_by_category(all_products, count)
        final_products = final_products[:count]
        
        if not final_products:
            return ""
        
        # 섹션 제목
        section_title = SECTION_TITLES.get(blog_id, "여행 준비에 도움되는 추천 용품")
        
        # HTML 인라인 스타일 사용 (Blogger markdown parser가 리스트/이미지 크기 제어 못함)
        # 참조: tour3.rotcha.kr (Hugo) - coupang-product-grid / coupang-product-card 클래스 사용
        # Blogger에서는 인라인 스타일로 동일 레이아웃 구현
        # 섹션 제목은 H2로 출력 (Blogger에서 H2 렌더링)
        lines = [f'\n\n## {section_title}\n',
                 '<div style="display:flex;flex-wrap:wrap;gap:12px;">']
        
        for p in final_products:
            pid = p.get("productId")
            name = p.get("productName", "")
            price = p.get("productPrice", 0)
            image = p.get("productImage", "")
            link = self.generate_affiliate_link(pid)
            
            if not link:
                continue
            
            price_str = f'{price:,}원'
            
            # CSS로 이미지 크기 고정 (Blogger에서 size 파라미터 무시함)
            style = ('style="display:flex;align-items:center;gap:8px;'
                     'padding:8px;background:#f5f5f5;border-radius:8px;'
                     'text-decoration:none;color:#333;"')
            
            if image:
                img_style = ('style="width:80px;height:80px;object-fit:cover;'
                            'border-radius:6px;flex-shrink:0;"')
                lines.append(f'<a href="{link}" target="_blank" rel="nofollow"{style}>'
                             f'<img src="{image}" alt="{name}" loading="lazy"{img_style}>'
                             f'<div style="line-height:1.3;min-width:0;">'
                             f'<div style="font-size:13px;font-weight:500;word-break:break-all;">{name}</div>'
                             f'<div style="font-size:12px;color:#666;">{price_str}</div>'
                             f'</div></a>')
            else:
                lines.append(f'<a href="{link}" target="_blank" rel="nofollow"{style}>'
                             f'<div style="line-height:1.3;">'
                             f'<div style="font-size:13px;font-weight:500;">{name}</div>'
                             f'<div style="font-size:12px;color:#666;">{price_str}</div>'
                             f'</div></a>')
        
        lines.append('</div>')
        lines.append('<p style="font-size:0.8em;color:#888;margin-top:8px;">이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.</p>')
        
        return "\n".join(lines)

    # Legacy method for backward compatibility
    def get_travel_product_links(self, blog_id="travel-hugo", count=2):
        if not self.is_configured():
            return ""
        # New implementation returns markdown list
        text = self.get_product_cards(blog_id, count)
        if not text:
            return ""
        return text
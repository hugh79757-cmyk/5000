"""상품 데이터 인리치 — 상품명 파싱 + 네이버 쇼핑 API brand/maker 보강"""
import os
import re
import logging
import requests

logger = logging.getLogger(__name__)

NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID", "")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "")
NAVER_SHOP_URL = "https://openapi.naver.com/v1/search/shop.json"

# ── 카테고리별 정규식 패턴 ──
SPEC_PATTERNS = {
    "laptop-hugo": [
        (r'(\d+)\s*GB\s*RAM', 'ram', 'GB'),
        (r'RAM\s*(\d+)\s*GB', 'ram', 'GB'),
        (r'(\d+)\s*GB\s*(?:DDR|LPDDR)', 'ram', 'GB'),
        (r'(\d+)\s*TB\s*SSD', 'ssd', 'TB'),
        (r'(\d+)\s*GB\s*SSD', 'ssd', 'GB'),
        (r'(\d+(?:\.\d+)?)\s*(?:인치|inch|")', 'screen', '인치'),
        (r'(\d+(?:\.\d+)?)\s*cm', 'screen_cm', 'cm'),
        (r'(\d+(?:\.\d+)?)\s*kg', 'weight', 'kg'),
        (r'(코어\s*(?:i[3579]|Ultra\s*\d)|Core\s*(?:i[3579]|Ultra\s*\d))', 'cpu', ''),
        (r'(라이젠\s*\d|Ryzen\s*\d)', 'cpu', ''),
        (r'(M[1-4]\s*(?:Pro|Max|Ultra)?)', 'cpu', ''),
        (r'(지포스\s*RTX\s*\d+|GeForce\s*RTX\s*\d+|RTX\s*\d+)', 'gpu', ''),
        (r'(라데온|Radeon\s*\w+)', 'gpu', ''),
        (r'(WIN\s*\d+|윈도우\s*\d+|Windows\s*\d+)', 'os', ''),
    ],
    "appliance-hugo": [
        (r'(\d+(?:\.\d+)?)\s*[Ll리터]', 'capacity', 'L'),
        (r'(\d+)\s*[Ww](?:att)?', 'power', 'W'),
        (r'(\d+)\s*d[Bb]', 'noise', 'dB'),
        (r'(\d+(?:\.\d+)?)\s*kg', 'weight', 'kg'),
        (r'(\d+)\s*AW', 'suction', 'AW'),
        (r'(\d+)\s*pa|Pa|PA', 'suction_pa', 'Pa'),
        (r'(\d+)\s*분', 'battery_min', '분'),
    ],
    "interior-hugo": [
        (r'(\d+(?:\.\d+)?)\s*cm', 'size_cm', 'cm'),
        (r'(\d+(?:\.\d+)?)\s*mm', 'size_mm', 'mm'),
        (r'(\d+(?:\.\d+)?)\s*kg', 'weight', 'kg'),
        (r'(원목|스틸|철제|메탈|패브릭|가죽|메쉬|강화유리|MDF|PB)', 'material', ''),
        (r'(\d+)\s*단', 'tier', '단'),
    ],
    "baby-hugo": [
        (r'(\d+(?:\.\d+)?)\s*kg', 'weight', 'kg'),
        (r'(\d+)\s*개월', 'age_month', '개월'),
        (r'(신생아|영아|유아|아동)', 'age_group', ''),
        (r'(ISOFIX|ISO\s*FIX)', 'isofix', ''),
        (r'(\d+)\s*단계', 'stage', '단계'),
        (r'(\d+)\s*(?:PCS|pcs|피스|P|p)\b', 'pieces', '개'),
        (r'(\d+)\s*[Ll리터]|(\d+)\s*ml|(\d+)\s*ML', 'capacity', ''),
    ],
    "fitness-hugo": [
        (r'(\d+(?:\.\d+)?)\s*kg', 'weight', 'kg'),
        (r'최대\s*(\d+)\s*kg|(\d+)\s*kg\s*하중', 'max_load', 'kg'),
        (r'(\d+(?:\.\d+)?)\s*cm', 'size_cm', 'cm'),
        (r'(\d+(?:\.\d+)?)\s*mm', 'size_mm', 'mm'),
        (r'(접이식|폴딩)', 'foldable', ''),
        (r'(\d+)\s*단계', 'resistance', '단계'),
        (r'(\d+)\s*(?:PCS|pcs|피스)', 'pieces', '개'),
    ],
}

# 전 카테고리 공통 패턴
COMMON_PATTERNS = [
    (r'(\d+(?:\.\d+)?)\s*kg', 'weight', 'kg'),
]


def _parse_specs_from_name(product_name, blog_id):
    """상품명에서 정규식으로 스펙 추출"""
    specs = {}
    patterns = SPEC_PATTERNS.get(blog_id, COMMON_PATTERNS)
    for pattern, key, unit in patterns:
        m = re.search(pattern, product_name, re.IGNORECASE)
        if m:
            val = m.group(1) if m.group(1) else m.group(0)
            if key not in specs:
                specs[key] = f"{val}{unit}" if unit else val
    # 쿠팡 상품명 "..., 512GB, 16GB, WIN11" 구조 파싱
    # 큰 GB=SSD, 작은 GB=RAM
    if 'ram' not in specs or 'ssd' not in specs:
        import re as _re
        gb_values = _re.findall(r'(?:,\s*)(\d+)GB', product_name)
        if len(gb_values) >= 2:
            nums = sorted([int(v) for v in gb_values], reverse=True)
            if 'ssd' not in specs and nums[0] >= 128:
                specs['ssd'] = f"{nums[0]}GB"
            if 'ram' not in specs and nums[1] <= 64:
                specs['ram'] = f"{nums[1]}GB"
        elif len(gb_values) == 1:
            val = int(gb_values[0])
            if val >= 128 and 'ssd' not in specs:
                specs['ssd'] = f"{val}GB"
            elif val <= 64 and 'ram' not in specs:
                specs['ram'] = f"{val}GB"

    return specs


def _naver_shop_search(query):
    """네이버 쇼핑 검색 API로 brand/maker 조회"""
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        return {}
    try:
        resp = requests.get(
            NAVER_SHOP_URL,
            params={"query": query, "display": 3, "sort": "sim"},
            headers={
                "X-Naver-Client-Id": NAVER_CLIENT_ID,
                "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
            },
            timeout=5,
        )
        if resp.status_code == 200:
            items = resp.json().get("items", [])
            if items:
                item = items[0]
                # 여러 결과 중 brand가 있는 첫 결과 우선
                best = item
                for it in items[:3]:
                    if it.get("brand"):
                        best = it
                        break
                return {
                    "brand": best.get("brand", ""),
                    "maker": best.get("maker", ""),
                    "category": best.get("category2", "") or best.get("category1", ""),
                    "naver_category3": best.get("category3", ""),
                    "naver_category4": best.get("category4", ""),
                    "naver_lprice": best.get("lprice", ""),
                    "naver_hprice": best.get("hprice", ""),
                    "naver_mall": best.get("mallName", ""),
                    "naver_product_id": best.get("productId", ""),
                }
    except Exception as e:
        logger.warning(f"네이버 쇼핑 API 실패: {e}")
    return {}


def enrich_products(products, blog_id):
    """상품 리스트에 스펙 + 브랜드 정보 추가"""
    for p in products:
        name = p.get("product_name", "")

        # 1) 상품명 정규식 파싱
        p["parsed_specs"] = _parse_specs_from_name(name, blog_id)

        # 2) 네이버 쇼핑 API (상위 2개 상품만 — API 호출 절약)
        if products.index(p) < 5:
            naver_info = _naver_shop_search(name[:50])
            p["brand"] = naver_info.get("brand", "")
            p["maker"] = naver_info.get("maker", "")
            p["naver_category"] = naver_info.get("category", "")
        else:
            if not p.get("brand"):
                p["brand"] = ""
            if not p.get("maker"):
                p["maker"] = ""
            p["naver_category3"] = ""
            p["naver_category4"] = ""
            p["naver_mall"] = ""

    return products

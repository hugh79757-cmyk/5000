#!/usr/bin/env python3
"""레버 1 before/after 측정 — 제목 프레임 + 본문1인칭"""

import sys, os, re, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipelines.curation.writer import generate_curation_article, _build_system_prompt, _build_user_prompt, _build_product_block, BLOG_EXTRA_RULES
from shared.ai_writer import generate as ai_generate

# 고정 키워드
KEYWORDS = ["비타민D", "수분크림"]

# mock 상품 데이터 (실제 쿠팡 포맷)
MOCK_PRODUCTS = {
    "비타민D": [
        {"product_name": "뉴트리디타 비타민D3 2000IU 90캡슐", "brand": "뉴트리디타", "maker": "뉴트리디타", "product_price": 15900, "category_name": "건강식품", "is_rocket": True, "is_free_shipping": False, "rank": 1, "parsed_specs": {"용량": "90캡슐", "함량": "2000IU"}, "product_url": "https://example.com/1", "product_image": "https://example.com/img1.jpg", "naver_lprice": "14900"},
        {"product_name": "닥터스 베스트 비타민D3 5000IU 360软capsule", "brand": "닥터스베스트", "maker": "닥터스베스트", "product_price": 28000, "category_name": "건강식품", "is_rocket": True, "is_free_shipping": False, "rank": 2, "parsed_specs": {"용량": "360소프트캡슐", "함량": "5000IU"}, "product_url": "https://example.com/2", "product_image": "https://example.com/img2.jpg", "naver_lprice": "26500"},
        {"product_name": "GNC 비타민D3 1000IU 180정", "brand": "GNC", "maker": "GNC", "product_price": 19900, "category_name": "건강식품", "is_rocket": False, "is_free_shipping": True, "rank": 3, "parsed_specs": {"용량": "180정", "함량": "1000IU"}, "product_url": "https://example.com/3", "product_image": "https://example.com/img3.jpg", "naver_lprice": "18500"},
        {"product_name": "solgar 비타민D3 1000IU 100 Liquid Softgels", "brand": "Solgar", "maker": "Solgar", "product_price": 22000, "category_name": "건강식품", "is_rocket": False, "is_free_shipping": True, "rank": 4, "parsed_specs": {"용량": "100소프트젤", "함량": "1000IU"}, "product_url": "https://example.com/4", "product_image": "https://example.com/img4.jpg", "naver_lprice": "21000"},
        {"product_name": "나우푸드 비타민D3 2000IU 120소프트젤", "brand": "나우푸드", "maker": "나우푸드", "product_price": 13500, "category_name": "건강식품", "is_rocket": True, "is_free_shipping": False, "rank": 5, "parsed_specs": {"용량": "120소프트젤", "함량": "2000IU"}, "product_url": "https://example.com/5", "product_image": "https://example.com/img5.jpg", "naver_lprice": "12800"},
    ],
    "수분크림": [
        {"product_name": "이니스프리 그린티 수분크림 50ml", "brand": "이니스프리", "maker": "이니스프리", "product_price": 22000, "category_name": "스킨케어", "is_rocket": True, "is_free_shipping": False, "rank": 1, "parsed_specs": {"용량": "50ml"}, "product_url": "https://example.com/6", "product_image": "https://example.com/img6.jpg", "naver_lprice": "19900"},
        {"product_name": "라네즈 워터 슬리핑 마스크 EX 70ml", "brand": "라네즈", "maker": "아모레퍼시픽", "product_price": 32000, "category_name": "스킨케어", "is_rocket": True, "is_free_shipping": False, "rank": 2, "parsed_specs": {"용량": "70ml"}, "product_url": "https://example.com/7", "product_image": "https://example.com/img7.jpg", "naver_lprice": "28900"},
        {"product_name": "벨라몬스터 수분크림 50ml", "brand": "벨라몬스터", "maker": "벨라몬스터", "product_price": 18000, "category_name": "스킨케어", "is_rocket": False, "is_free_shipping": True, "rank": 3, "parsed_specs": {"용량": "50ml"}, "product_url": "https://example.com/8", "product_image": "https://example.com/img8.jpg", "naver_lprice": "16500"},
        {"product_name": "닥터지 레드블레미쉬 클리어 수딩크림 50ml", "brand": "닥터지", "maker": "닥터지", "product_price": 29000, "category_name": "스킨케어", "is_rocket": True, "is_free_shipping": False, "rank": 4, "parsed_specs": {"용량": "50ml"}, "product_url": "https://example.com/9", "product_image": "https://example.com/img9.jpg", "naver_lprice": "26000"},
        {"product_name": "유세린 수분크림 50ml", "brand": "유세린", "maker": "유세린", "product_price": 35000, "category_name": "스킨케어", "is_rocket": False, "is_free_shipping": True, "rank": 5, "parsed_specs": {"용량": "50ml"}, "product_url": "https://example.com/10", "product_image": "https://example.com/img10.jpg", "naver_lprice": "32000"},
    ],
}

# 프레임 패턴
TITLE_FRAMES = {
    "후기": re.compile(r"후기"),
    "실사용": re.compile(r"실\s*사\s*용"),
    "써본": re.compile(r"써\s*본"),
    "경험": re.compile(r"경\s*험"),
    "느낌": re.compile(r"느\s*낌"),
    "직접": re.compile(r"직\s*접"),
}

BODY_1PERSON = re.compile(r"(저도|저는|내가|직접\s*사용|실제\s*사용|실사용|써보니|사용해보니|써본|경험했|느꼈|만족스러웠|체험)")

def count_title_frames(title):
    hits = []
    for name, pat in TITLE_FRAMES.items():
        if pat.search(title):
            hits.append(name)
    return hits

def count_body_1person(body):
    return BODY_1PERSON.findall(body)

def generate_titles(keyword, products, blog_id, n=5):
    """제목 n개 생성 (H1 추출)"""
    titles = []
    product_block = _build_product_block(products)
    for i in range(n):
        system_prompt = _build_system_prompt(keyword, blog_id=blog_id)
        user_prompt = _build_user_prompt(keyword, product_block)
        try:
            result = ai_generate(system_prompt, user_prompt, temperature=0.9, max_tokens=2000)
        except Exception as e:
            print(f"  [ERROR] LLM 실패: {e}")
            continue
        body = result if isinstance(result, str) else (result.get("content", "") if isinstance(result, dict) else "")
        if not body:
            continue
        for line in body.split("\n"):
            line = line.strip()
            if line.startswith("# "):
                titles.append(line.lstrip("# ").strip())
                break
        else:
            titles.append(body.split("\n")[0][:60])
    return titles

def generate_body(keyword, products, blog_id):
    """본문 1건 생성"""
    result = generate_curation_article(keyword, products, blog_id=blog_id)
    if not result:
        return None
    return result.get("body_md", "")

def main():
    print("=" * 70)
    print("LEVER 1 BEFORE/_AFTER MEASUREMENT")
    print("=" * 70)

    # ── 제목 측정 ──
    print("\n[1] 제목 프레임 측정 (2개 키워드 × 5회 = 10건)")
    all_titles = []
    for kw in KEYWORDS:
        blog = "health-hugo" if "비타민" in kw else "beauty-hugo"
        titles = generate_titles(kw, MOCK_PRODUCTS[kw], blog, n=5)
        for t in titles:
            frames = count_title_frames(t)
            all_titles.append({"keyword": kw, "title": t, "frames": frames})
            status = f"⚠ {frames}" if frames else "✓"
            print(f"  {kw}: [{status}] {t}")

    frame_counts = {}
    for item in all_titles:
        for f in item["frames"]:
            frame_counts[f] = frame_counts.get(f, 0) + 1

    print(f"\n  프레임 합계: {json.dumps(frame_counts, ensure_ascii=False)}")
    print(f"  총 제목: {len(all_titles)}건")

    # ── 본문 측정 ──
    print("\n[2] 본문 1인칭/경험 주장 측정 (health 1건 + beauty 1건)")
    body_results = []
    for kw, blog in [("비타민D", "health-hugo"), ("수분크림", "beauty-hugo")]:
        body = generate_body(kw, MOCK_PRODUCTS[kw], blog)
        if not body:
            print(f"  {kw}: [생성 실패]")
            continue
        matches = count_body_1person(body)
        body_results.append({"keyword": kw, "blog": blog, "matches": matches, "body_len": len(body)})
        status = f"⚠ {len(matches)}건: {matches}" if matches else "✓ 0건"
        print(f"  {kw} ({blog}): [{status}] ({len(body)}자)")
        # 첫 500자 미리보기
        print(f"    미리보기: {body[:200]}...")

    # ── JSON 출력 ──
    output = {"titles": all_titles, "title_frame_summary": frame_counts, "bodies": body_results}
    with open("/Users/twinssn/Projects/5000/scripts/lever1_before.json", "w") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n결과 저장: scripts/lever1_before.json")

if __name__ == "__main__":
    main()

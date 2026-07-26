#!/usr/bin/env python3
"""
CUAP 전체 사이트 ASCII 슬러그 마이그레이션 스크립트

1. 모든 포스트의 한글 슬러그를 ASCII 안전 슬러그로 변환
2. 폴더명 변경
3. front matter slug 필드 업데이트
4. cuap_entities DB 업데이트
5. 재빌드 및 재배포
"""

import re
import sqlite3
import shutil
from pathlib import Path
from shared.cuap_entity_linker import BLOG_DOMAINS, DB_PATH
from hangul_romanize import Transliter
from hangul_romanize.rule import academic

CUAP_BASE = "/Users/twinssn/Projects/cuap"
BLOGS = [
    "appliance-hugo", "baby-hugo", "beauty-hugo", "camping-hugo",
    "fitness-hugo", "health-hugo", "interior-hugo", "kitchen-hugo",
    "laptop-hugo", "pet-hugo"
]

# 한글 → 영문 매핑 (브랜드명/핵심 키워드 중심)
KOREAN_TO_ENGLISH = {
    # 브랜드명
    "삼성": "samsung", "엘지": "lg", "LG": "lg", "다이슨": "dyson",
    "필립스": "philips", "브라운": "braun", "오랄비": "oralb",
    "코웨이": "coway", "쿠쿠": "cuckoo", "쿠첸": "cuchen",
    "테팔": "tefal", "WMF": "wmf", "키친아트": "kitchenart",
    "한일": "hanil", "신일": "shinil", "위닉스": "winix",
    "LG전자": "lg", "삼성전자": "samsung",
    # 가전제품
    "냉장고": "refrigerator", "세탁기": "washer", "건조기": "dryer",
    "청소기": "vacuum", "로봇청소기": "robot-vacuum", "무선청소기": "cordless-vacuum",
    "공기청정기": "air-purifier", "가습기": "humidifier", "제습기": "dehumidifier",
    "에어컨": "aircon", "선풍기": "fan", "히터": "heater",
    "전자레인지": "microwave", "오븐": "oven", "식기세척기": "dishwasher",
    "커피머신": "coffee-machine", "믹서기": "blender", "토스터": "toaster",
    "밥솥": "rice-cooker", "전기밥솥": "rice-cooker", "압력밥솥": "pressure-cooker",
    "인덕션": "induction", "가스레인지": "gas-range", "후드": "hood",
    "김치냉장고": "kimchi-fridge", "와인냉장고": "wine-fridge",
    "헤어드라이기": "hair-dryer", "고데기": "hair-iron", "면도기": "shaver",
    "전기면도기": "electric-shaver", "칫솔": "toothbrush", "전동칫솔": "electric-toothbrush",
    "구강세정기": "water-flosser", "워터픽": "waterpik",
    "마사지기": "massager", "안마기": "massager", "눈마사지기": "eye-massager",
    "발마사지기": "foot-massager", "목마사지기": "neck-massager",
    "혈압계": "blood-pressure", "체온계": "thermometer", "체중계": "scale",
    "스마트워치": "smartwatch", "밴드": "band", "이어폰": "earphone",
    "헤드폰": "headphone", "블루투스": "bluetooth", "스피커": "speaker",
    "노트북": "laptop", "태블릿": "tablet", "모니터": "monitor",
    "키보드": "keyboard", "마우스": "mouse", "공유기": "router",
    "와이파이": "wifi", "메시": "mesh", "나스": "nas",
    # 캠핑
    "텐트": "tent", "타프": "tarp", "그늘막": "shade", "원터치": "onetouch",
    "에어텐트": "air-tent", "면텐트": "cotton-tent", "돔텐트": "dome-tent",
    "차박": "chabak", "캠핑카": "campervan", "카라반": "caravan",
    "캠핑의자": "camping-chair", "캠핑테이블": "camping-table",
    "버너": "burner", "그릴": "grill", "화로대": "fire-pit",
    "쿨러": "cooler", "아이스박스": "ice-box", "냉장고": "fridge",
    "매트": "mat", "에어매트": "air-mat", "자충매트": "self-inflating-mat",
    "침낭": "sleeping-bag", "이불": "blanket", "베개": "pillow",
    "랜턴": "lantern", "헤드랜턴": "headlamp", "손전등": "flashlight",
    "파워뱅크": "power-bank", "보조배터리": "power-bank", "태양광": "solar",
    "캠핑장비": "camping-gear", "캠핑용품": "camping-gear",
    # 뷰티
    "크림": "cream", "세럼": "serum", "에센스": "essence", "앰플": "ampoule",
    "토너": "toner", "로션": "lotion", "에멀전": "emulsion",
    "클렌징": "cleansing", "폼클렌징": "foam-cleansing", "클렌징오일": "cleansing-oil",
    "선크림": "sunscreen", "선블록": "sunblock", "자외선차단제": "sunscreen",
    "마스크팩": "mask-pack", "시트마스크": "sheet-mask", "워시오프": "wash-off",
    "필링": "peeling", "스크럽": "scrub", "각질제거": "exfoliator",
    "아이크림": "eye-cream", "립밤": "lip-balm", "립스틱": "lipstick",
    "쿠션": "cushion", "파운데이션": "foundation", "컨실러": "concealer",
    "파우더": "powder", "팩트": "pact", "블러셔": "blusher", "하이라이터": "highlighter",
    "섀도우": "shadow", "아이라이너": "eyeliner", "마스카라": "mascara",
    "브로우": "brow", "브로우펜슬": "brow-pencil", "브로우카라": "brow-cara",
    "네일": "nail", "젤네일": "gel-nail", "네일아트": "nail-art",
    "향수": "perfume", "오드퍼퓸": "eau-de-parfum", "오드뚜왈렛": "eau-de-toilette",
    "바디워시": "body-wash", "바디로션": "body-lotion", "바디스크럽": "body-scrub",
    "샴푸": "shampoo", "컨디셔너": "conditioner", "트리트먼트": "treatment",
    "헤어오일": "hair-oil", "헤어에센스": "hair-essence", "헤어팩": "hair-pack",
    "염색약": "hair-dye", "새치염색": "gray-hair-dye",
    # 건강
    "영양제": "supplement", "비타민": "vitamin", "미네랄": "mineral",
    "유산균": "probiotics", "프로바이오틱스": "probiotics", "오메가3": "omega3",
    "루테인": "lutein", "밀크씨슬": "milk-thistle", "홍삼": "red-ginseng",
    "프로폴리스": "propolis", "콜라겐": "collagen", "히알루론산": "hyaluronic-acid",
    "코엔자임큐텐": "coq10", "마그네슘": "magnesium", "칼슘": "calcium",
    "철분": "iron", "아연": "zinc", "비타민D": "vitamin-d", "비타민B": "vitamin-b",
    "종합비타민": "multivitamin", "멀티비타민": "multivitamin",
    "관절영양제": "joint-supplement", "눈영양제": "eye-supplement",
    "간영양제": "liver-supplement", "혈행개선": "circulation",
    "면역력": "immunity", "피로회복": "fatigue-recovery", "항산화": "antioxidant",
    "다이어트": "diet", "체지방감소": "fat-burn", "단백질": "protein",
    "프로틴": "protein", "BCAA": "bcaa", "크레아틴": "creatine",
    # 가구/인테리어
    "소파": "sofa", "침대": "bed", "매트리스": "mattress", "메모리폼": "memory-foam",
    "라텍스": "latex", "스프링": "spring", "프레임": "frame",
    "식탁": "dining-table", "의자": "chair", "책상": "desk", "책장": "bookshelf",
    "장롱": "wardrobe", "서랍장": "drawer", "수납장": "storage",
    "거실장": "tv-stand", "협탁": "side-table", "화장대": "vanity",
    "식탁세트": "dining-set", "소파세트": "sofa-set",
    "원목": "solid-wood", "원목가구": "solid-wood-furniture",
    "세라믹": "ceramic", "포세린": "porcelain", "강화유리": "tempered-glass",
    # 펫
    "강아지": "dog", "고양이": "cat", "반려동물": "pet",
    "사료": "food", "간식": "treat", "캣타워": "cat-tower",
    "스크래쳐": "scratcher", "하네스": "harness", "리드줄": "leash",
    "배변패드": "pee-pad", "화장실": "litter-box", "모래": "litter",
    "이동장": "carrier", "켄넬": "kennel", "방석": "bed",
    "급식기": "feeder", "정수기": "water-fountain", "드라이룸": "dry-room",
    "샴푸": "shampoo", "치약": "toothpaste", "유모차": "stroller",
    "노즈워크": "nose-work", "그루밍": "grooming", "영양제": "supplement",
    "장난감": "toy", "간식토이": "treat-toy", "미용": "grooming",
    "클리퍼": "clipper", "브러쉬": "brush", "발톱": "nail",
    "관절": "joint", "눈물자국": "tear-stain", "치석": "tartar",
    # 캠핑/아웃도어 용어
    "방수": "waterproof", "방풍": "windproof", "보온": "thermal",
    "경량": "lightweight", "초경량": "ultralight", "컴팩트": "compact",
    "내구성": "durable", "가성비": "value", "실속": "practical",
    "추천": "recommend", "비교": "compare", "순위": "ranking",
    "베스트": "best", "톱": "top", "인기": "popular",
    "신상": "new", "최신": "latest", "2026년": "2026", "2025년": "2025",
    "7월": "july", "6월": "june", "8월": "august",
    "선택가이드": "buying-guide", "선택기준": "selection-guide",
    "실속선택": "value-pick", "합격점": "passing-grade",
    "실제후기": "real-review", "사용후기": "user-review",
    "장단점": "pros-cons", "특징": "features", "스펙": "spec",
    "용량": "capacity", "크기": "size", "무게": "weight",
    "가격": "price", "비용": "cost", "할인": "discount",
    "로켓배송": "rocket-delivery", "무료배송": "free-shipping",
    "쿠팡": "coupang", "네이버": "naver", "다나와": "danawa",
}

# 한글 자모 분해용
from hangul_romanize.rule import academic
transliterator = Transliter(academic)

def korean_to_roman(text):
    """한글을 영문으로 변환 (매핑 테이블 + hangul_romanize fallback)"""
    result = text
    
    # 1. 매핑 테이블 적용 (긴 것부터)
    sorted_keys = sorted(KOREAN_TO_ENGLISH.keys(), key=len, reverse=True)
    for kor in sorted_keys:
        eng = KOREAN_TO_ENGLISH[kor]
        result = result.replace(kor, eng)
    
    # 2. 남은 한글 문자를 hangul_romanize로 변환
    # hangul_romanize는 공백 기준으로 동작하므로 문자별로 처리
    def replace_korean(match):
        korean_text = match.group(0)
        try:
            return transliterator.translit(korean_text)
        except:
            return ""
    
    # 한글 문자열 찾아서 변환 (연속된 한글 블록)
    result = re.sub(r'[가-힣]+', replace_korean, result)
    
    # 3. 특수문자 정리
    result = re.sub(r'[^\w\s-]', '', result)  # 특수문자 제거
    result = re.sub(r'[\s_]+', '-', result)   # 공백/언더바를 하이픈으로
    result = re.sub(r'-+', '-', result)        # 연속 하이픈 정리
    result = result.strip('-')                 # 앞뒤 하이픈 제거
    result = result.lower()                    # 소문자
    
    # 4. 너무 길면 자르기 (200자 제한)
    if len(result) > 200:
        result = result[:200].rstrip('-')
    
    # 5. 빈 문자열 방지
    if not result:
        result = "post"
    
    return result

def generate_ascii_slug(title, existing_slugs=None):
    """제목에서 ASCII 슬러그 생성"""
    # 제목에서 슬러그 생성
    slug = korean_to_roman(title)
    
    # 중복 방지
    if existing_slugs and slug in existing_slugs:
        base = slug
        counter = 1
        while f"{base}-{counter}" in existing_slugs:
            counter += 1
        slug = f"{base}-{counter}"
    
    return slug

def scan_all_posts():
    """모든 블로그의 포스트 스캔"""
    posts = []
    for blog in BLOGS:
        blog_path = Path(CUAP_BASE) / blog / "content" / "posts"
        if not blog_path.exists():
            continue
        for post_dir in blog_path.iterdir():
            if post_dir.is_dir():
                index_md = post_dir / "index.md"
                if index_md.exists():
                    posts.append({
                        "blog": blog,
                        "folder": post_dir.name,
                        "path": post_dir,
                        "index_md": index_md
                    })
    return posts

def read_front_matter(md_path):
    """front matter 파싱"""
    content = md_path.read_text(encoding='utf-8')
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            fm_text = parts[1]
            body = parts[2]
            # 간단한 파싱
            fm = {}
            for line in fm_text.strip().split('\n'):
                if ':' in line:
                    key, val = line.split(':', 1)
                    fm[key.strip()] = val.strip().strip('"\'')
            return fm, body
    return {}, content

def write_front_matter(md_path, fm, body):
    """front matter 쓰기"""
    lines = ["---"]
    for k, v in fm.items():
        # 값에 특수문자가 있으면 따옴표로 감싸기
        if any(c in str(v) for c in [':', '#', '"', "'", '\n']):
            lines.append(f'{k}: "{v}"')
        else:
            lines.append(f'{k}: {v}')
    lines.append("---")
    lines.append(body.lstrip('\n'))
    md_path.write_text('\n'.join(lines), encoding='utf-8')

def main():
    print("=== CUAP ASCII 슬러그 마이그레이션 시작 ===\n")
    
    # 1. 모든 포스트 스캔
    posts = scan_all_posts()
    print(f"총 {len(posts)}개 포스트 발견\n")
    
    # 2. 기존 슬러그 수집 (중복 방지용)
    existing_slugs = set()
    for p in posts:
        existing_slugs.add(p["folder"])
    
    # 3. 각 포스트 처리
    changes = []
    for i, post in enumerate(posts):
        blog = post["blog"]
        old_folder = post["folder"]
        md_path = post["index_md"]
        
        # front matter 읽기
        fm, body = read_front_matter(md_path)
        title = fm.get("title", "")
        
        # 새 슬러그 생성
        new_slug = generate_ascii_slug(title, existing_slugs)
        
        if new_slug != old_folder:
            print(f"[{i+1}/{len(posts)}] {blog}")
            print(f"  제목: {title[:60]}...")
            print(f"  기존: {old_folder}")
            print(f"  변경: {new_slug}")
            
            changes.append({
                "blog": blog,
                "old_folder": old_folder,
                "new_slug": new_slug,
                "old_path": post["path"],
                "new_path": post["path"].parent / new_slug,
                "title": title,
                "fm": fm
            })
            existing_slugs.add(new_slug)
        else:
            print(f"[{i+1}/{len(posts)}] {blog} - {old_folder} (변경 없음)")
    
    print(f"\n=== 변경 대상: {len(changes)}개 ===")
    
    if not changes:
        print("변경할 항목이 없습니다.")
        return
    
    # 4. 실행 확인
    confirm = input("\n실행하시겠습니까? (y/N): ")
    if confirm.lower() != 'y':
        print("취소됨")
        return
    
    # 5. 폴더명 변경 & front matter 업데이트
    print("\n=== 폴더명 변경 및 front matter 업데이트 ===")
    for change in changes:
        old_path = change["old_path"]
        new_path = change["new_path"]
        
        # 폴더 이동
        if old_path.exists():
            shutil.move(str(old_path), str(new_path))
            print(f"  이동: {change['blog']}/{change['old_folder']} -> {change['new_slug']}")
        
        # front matter 업데이트
        new_md = new_path / "index.md"
        fm = change["fm"]
        fm["slug"] = change["new_slug"]
        # body 읽기
        _, body = read_front_matter(new_md)
        write_front_matter(new_md, fm, body)
    
    # 6. DB 업데이트
    print("\n=== cuap_entities DB 업데이트 ===")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    for change in changes:
        blog = change["blog"]
        entity_name = change["fm"].get("title", "").replace("추천", "").replace("비교", "").strip()
        # 더 정확한 매칭을 위해 title로 찾기
        domain = BLOG_DOMAINS.get(blog, "")
        new_url = f"{domain}/posts/{change['new_slug']}/"
        
        cursor.execute("""
            UPDATE cuap_entities 
            SET post_slug = ?, post_url = ?
            WHERE blog_id = ? AND post_slug = ?
        """, (change["new_slug"], new_url, blog, change["old_folder"]))
        
        if cursor.rowcount > 0:
            print(f"  DB 업데이트: {blog} | {change['old_folder']} -> {change['new_slug']}")
        else:
            # entity_name으로도 시도
            cursor.execute("""
                UPDATE cuap_entities 
                SET post_slug = ?, post_url = ?
                WHERE blog_id = ? AND entity_name LIKE ? AND published = 1
            """, (change["new_slug"], new_url, blog, f"%{entity_name}%"))
            if cursor.rowcount > 0:
                print(f"  DB 업데이트(entity_name): {blog} | {entity_name} -> {change['new_slug']}")
    
    conn.commit()
    conn.close()
    
    print("\n=== 완료! 이제 각 블로그 재빌드 및 재배포 필요 ===")
    for blog in BLOGS:
        print(f"  cd {CUAP_BASE}/{blog} && hugo --gc --minify && wrangler deploy")

if __name__ == "__main__":
    main()
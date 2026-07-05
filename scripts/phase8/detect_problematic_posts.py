import os
import re
import sys
import yaml
import argparse

CUAP_ROOT = "/Users/twinssn/Projects/CUAP"
BLOGS = [
    "laptop-hugo", "appliance-hugo", "interior-hugo", "baby-hugo",
    "fitness-hugo", "health-hugo", "pet-hugo", "kitchen-hugo",
    "beauty-hugo", "camping-hugo",
]

CATEGORY_FILTERS = {
    "laptop-hugo": {
        "blocked": ["도서", "교재", "필기", "실기", "기능사", "자격증",
                     "스티커", "마우스패드", "장패드", "키보드", "마우스",
                     "가방", "파우치", "거치대", "받침대", "쿨링패드",
                     "모니터", "데스크탑", "태블릿", "아이패드", "갤럭시탭",
                     "헤드셋", "이어폰", "이어버드", "스피커",
                     "웹캠", "캡쳐보드", "캡처보드",
                     "책상", "의자", "케이블", "HDMI", "USB허브",
                     "dock", "어댑터", "충전기", "보호필름", "스킨",
                     "서류가방", "노트북가방", "CrowPi", "크롤파이",
                     "중고", "트레이딩",
                     "생활용품", "가구", "홈인테리어", "주방용품", "문구/오피스",
                     "식품", "출산/유아", "반려동물"],
    },
    "appliance-hugo": {
        "blocked": ["도서", "교재", "스티커", "인형", "장난감",
                     "의류", "패션", "화장품",
                     "생활용품", "출산/유아", "반려동물", "식품", "완구"],
    },
    "interior-hugo": {
        "blocked": ["도서", "교재", "식품", "화장품", "의류", "패션",
                     "장난감", "완구",
                     "생활용품", "전자기기", "가전", "출산/유아", "반려동물",
                     "주방용품", "스포츠"],
    },
    "baby-hugo": {
        "blocked": ["강아지", "반려견", "반려동물", "개모차", "pet", "여성의류", "남성의류", "패션의류", "여성패션", "남성패션",
                     "고양이", "강아지용", "도그", "dog",
                     "도서", "교재", "성인용",
                     "장난감", "완구", "블록", "보드게임", "퍼즐",
                     "유모차 가방", "유모차 후크", "유모차 고리", "유모차 걸이",
                     "유모차 정리함", "유모차 양산", "유모차 액세서리",
                     "핸들장난감", "드라이빙", "모빌",
                     "생활용품", "식품", "가전", "가구", "홈인테리어"],
    },
    "fitness-hugo": {
        "blocked": ["도서", "교재", "인형", "장난감", "화장품",
                     "생활용품", "출산/유아", "반려동물", "식품", "가전",
                     "패션의류", "여성의류", "남성의류"],
    },
    "health-hugo": {
        "blocked": ["생활용품", "주방", "반려동물", "패션", "전자기기", "장난감", "완구",
                     "식품", "가전", "출산/유아"],
    },
    "pet-hugo": {
        "blocked": ["식품", "의류", "전자기기", "가전", "주방", "완구", "장난감",
                     "생활용품", "출산/유아", "가구", "홈인테리어", "스포츠/레저", "패션"],
    },
    "kitchen-hugo": {
        "blocked": ["패션", "의류", "반려동물", "완구", "장난감", "건강식품", "영양제",
                     "생활용품", "가전디지털", "출산/유아", "스포츠/레저", "식품"],
    },
    "beauty-hugo": {
        "blocked": ["식품", "전자기기", "가전", "완구", "반려동물", "주방", "캠핑", "생활용품", "위생용품", "음료",
                     "출산/유아", "스포츠/레저", "문구/오피스", "가구"],
    },
    "camping-hugo": {
        "blocked": ["식품", "건강식품", "완구", "장난감", "주방가전", "뷰티", "화장품",
                     "생활용품", "출산/유아", "가전", "패션", "의류", "문구/오피스"],
    },
}

CJK_RE = re.compile(r'[\u4E00-\u9FFF\u3400-\u4DBF]')
HANGUL_RE = re.compile(r'[\uAC00-\uD7AF]')


def parse_frontmatter(filepath):
    """Extract YAML frontmatter from index.md"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    if not content.startswith('---'):
        return {}
    parts = content.split('---', 2)
    if len(parts) < 3:
        return {}
    try:
        return yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        return {}


def is_chinese_title(title):
    """True if title has CJK chars but fewer than 5 Korean chars"""
    if not title:
        return False
    has_cjk = bool(CJK_RE.search(title))
    hangul_count = len(HANGUL_RE.findall(title))
    return has_cjk and hangul_count < 5


BODY_BLOCKED_CACHE = {}


def is_offtopic(title, tags, blocked_keywords):
    """True if title or tags contain any blocked keyword"""
    combined = title.lower()
    if tags:
        combined += " " + " ".join(t.lower() for t in tags)
    for kw in blocked_keywords:
        if kw.lower() in combined:
            return kw
    return None


def get_body_content(filepath):
    """Extract body content (after frontmatter) from index.md"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    if not content.startswith('---'):
        return content
    parts = content.split('---', 2)
    if len(parts) < 3:
        return content
    return parts[2].strip()


def build_body_regex(blocked_keywords):
    """Build compiled word-boundary regex for blocked keywords"""
    key = tuple(blocked_keywords)
    if key in BODY_BLOCKED_CACHE:
        return BODY_BLOCKED_CACHE[key]
    patterns = []
    for kw in blocked_keywords:
        patterns.append(f"(?<![가-힣]){re.escape(kw.lower())}(?![가-힣])")
    regex = re.compile("|".join(patterns))
    BODY_BLOCKED_CACHE[key] = regex
    return regex


def is_body_offtopic(body, blocked_keywords):
    """Check body content using Korean word-boundary regex"""
    if not body:
        return None
    regex = build_body_regex(blocked_keywords)
    m = regex.search(body.lower())
    if m:
        return m.group()
    return None


def scan_blog(blog_id, scan_body=False):
    posts_dir = os.path.join(CUAP_ROOT, blog_id, "content", "posts")
    if not os.path.isdir(posts_dir):
        print(f"  [건너뜀] 디렉토리 없음: {posts_dir}")
        return [], [], []
    chinese = []
    offtopic = []
    body_offtopic = []
    blocked = CATEGORY_FILTERS.get(blog_id, {}).get("blocked", [])

    for slug in sorted(os.listdir(posts_dir)):
        index_path = os.path.join(posts_dir, slug, "index.md")
        if not os.path.isfile(index_path):
            continue
        fm = parse_frontmatter(index_path)
        if not fm:
            continue
        title = fm.get("title", "")
        tags = fm.get("tags", [])
        if isinstance(tags, str):
            tags = [tags]

        if is_chinese_title(title):
            chinese.append({
                "blog": blog_id,
                "slug": slug,
                "title": title,
                "path": index_path,
            })

        reason = is_offtopic(title, tags, blocked)
        if reason:
            offtopic.append({
                "blog": blog_id,
                "slug": slug,
                "title": title,
                "reason": reason,
                "path": index_path,
            })

        if scan_body:
            body = get_body_content(index_path)
            body_reason = is_body_offtopic(body, blocked)
            if body_reason:
                body_offtopic.append({
                    "blog": blog_id,
                    "slug": slug,
                    "title": title,
                    "reason": body_reason,
                    "path": index_path,
                    "source": "body",
                })

    return chinese, offtopic, body_offtopic


def main():
    parser = argparse.ArgumentParser(description="CUAP 문제 포스트 탐지 스크립트")
    parser.add_argument("--dry-run", action="store_true", default=True,
                        help="실행만 하고 삭제하지 않음 (기본값)")
    parser.add_argument("--scan-body", action="store_true",
                        help="본문 내용까지 word-boundary regex로 스캔")
    args = parser.parse_args()

    all_chinese = []
    all_offtopic = []
    all_body = []
    blog_stats = {}

    scan_mode = "제목+태그"
    if args.scan_body:
        scan_mode = "제목+태그+본문(word-boundary)"

    print("=" * 60)
    print(f"CUAP 문제 포스트 탐지 스캔 (모드: {scan_mode})")
    print("=" * 60)

    for blog_id in BLOGS:
        print(f"\n🔍 [{blog_id}] 스캔 중...")
        chinese, offtopic, body = scan_blog(blog_id, scan_body=args.scan_body)
        all_chinese.extend(chinese)
        all_offtopic.extend(offtopic)
        all_body.extend(body)
        total = len(chinese) + len(offtopic) + len(body)
        blog_stats[blog_id] = total
        print(f"  중국어: {len(chinese)}건, 오프토픽: {len(offtopic)}건, 본문: {len(body)}건, 총: {total}건")

    # Deduplicate by (blog, slug) across all categories
    seen_slugs = set()
    unique_chinese = []
    for item in all_chinese:
        key = (item["blog"], item["slug"])
        if key not in seen_slugs:
            seen_slugs.add(key)
            unique_chinese.append(item)

    unique_offtopic = []
    for item in all_offtopic:
        key = (item["blog"], item["slug"])
        if key not in seen_slugs:
            seen_slugs.add(key)
            unique_offtopic.append(item)

    unique_body = []
    for item in all_body:
        key = (item["blog"], item["slug"])
        if key not in seen_slugs:
            seen_slugs.add(key)
            unique_body.append(item)

    total_flagged = len(unique_chinese) + len(unique_offtopic) + len(unique_body)

    result = {
        "chinese": unique_chinese,
        "offtopic": unique_offtopic,
        "body_offtopic": unique_body,
        "summary": {
            "total_flagged": total_flagged,
            "chinese": len(unique_chinese),
            "offtopic": len(unique_offtopic),
            "body_offtopic": len(unique_body),
            "by_blog": blog_stats,
        },
    }

    output_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(output_dir, "flagged_posts.yaml")
    with open(output_path, 'w', encoding='utf-8') as f:
        yaml.dump(result, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    print(f"\n{'=' * 60}")
    print(f"스캔 완료!")
    print(f"  중국어 제목: {len(unique_chinese)}건")
    print(f"  오프토픽(제목/태그): {len(unique_offtopic)}건")
    print(f"  오프토픽(본문): {len(unique_body)}건")
    print(f"  총 탐지: {total_flagged}건")
    print(f"  결과 저장: {output_path}")
    print(f"{'=' * 60}")

    if total_flagged == 0:
        print("\n⚠️  탐지된 문제가 없습니다.")


if __name__ == "__main__":
    main()

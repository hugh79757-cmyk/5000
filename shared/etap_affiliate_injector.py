"""
ETAP 블로그 포스트용 제휴 링크 삽입기

기존 생성된 포스트에 제휴 링크를 추가하는 후처리 도구.
정적 사이트에 배포하기 전에 실행하여 제휴 링크를 삽입한다.
"""

import os
import re
import sys
from typing import List, Dict, Optional

sys.path.insert(0, "/Users/twinssn/Projects/5000")
from shared.etap_affiliate import get_affiliate


class AffiliateLinkInjector:
    """ETAP 포스트에 제휴 링크 삽입"""
    
    # 블로그별 제휴 링크 키워드 매핑
    BLOG_KEYWORDS = {
        "flights-hugo": {
            "triggers": ["flight", "airline", "airport", "fly", "항공", "비행기", "공항"],
            "affiliate_type": "skyscanner",
            "link_template": "https://www.skyscanner.com/transport/flights/{origin}/{destination}/{date}/",
        },
        "airlines-hugo": {
            "triggers": ["airline", "flight", "항공사", "비행"],
            "affiliate_type": "skyscanner",
            "link_template": "https://www.skyscanner.com/transport/flights/",
        },
        "airports-hugo": {
            "triggers": ["airport", "공항", "터미널"],
            "affiliate_type": "skyscanner",
            "link_template": "https://www.skyscanner.com/transport/flights/",
        },
        "tour-hugo": {
            "triggers": ["hotel", "accommodation", "stay", "호텔", "숙박", "리조트"],
            "affiliate_type": "trip",
            "link_template": "https://www.trip.com/hotels/",
        },
        "dining-hugo": {
            "triggers": ["restaurant", "dining", "food", "맛집", "식당", "음식"],
            "affiliate_type": "trip",
            "link_template": "https://www.trip.com/restaurants/",
        },
        "tours-hugo": {
            "triggers": ["tour", "activity", "excursion", "투어", "액티비티", "체험"],
            "affiliate_type": "viator",
            "link_template": "",
        },
        "deals-hugo": {
            "triggers": ["deal", "discount", "cheap", "특가", "할인", "저렴한"],
            "affiliate_type": "trip",
            "link_template": "https://www.trip.com/deals/",
        },
        "default": {
            "triggers": ["hotel", "flight", "tour", "booking", "예약", "호텔", "항공권", "투어"],
            "affiliate_type": "trip",
            "link_template": "https://www.trip.com/",
        },
    }
    
    # 제휴 링크 삽입 위치 마커 (H2 제목에서 감지)
    INSERTION_TRIGGERS = {
        "where to stay": "trip",       # 숙소 섹션 → Trip.com 호텔
        "accommodation": "trip",
        "hotel": "trip",
        "best time to visit": None,    # 시간 정보 → 제휴 불필요
        "getting there": "skyscanner", # 교통편 → Skyscanner
        "transportation": "skyscanner",
        "flight": "skyscanner",
        "top things to do": "viator",  # 액티비티 → Viator
        "things to do": "viator",
        "tours": "viator",
        "activities": "viator",
        "budget breakdown": "trip",    # 예산 → Trip.com
        "food and dining": "trip",     # 맛집 → Trip.com
        "dining": "trip",
        "travel tips": None,           # 팁 → 제휴 불필요
    }
    
    def __init__(self, blog_id: str):
        self.blog_id = blog_id
        self.config = self.BLOG_KEYWORDS.get(blog_id, self.BLOG_KEYWORDS["default"])
        self.affiliate = get_affiliate()
        self.inserted_links: List[Dict] = []
    
    def should_insert_in_section(self, h2_title: str) -> Optional[str]:
        """H2 제목 기준으로 해당 섹션에 제휴 링크 삽입이 적절한지 판단"""
        title_lower = h2_title.lower().strip()
        
        for trigger, affiliate_type in self.INSERTION_TRIGGERS.items():
            if trigger in title_lower:
                return affiliate_type
        
        return None
    
    def find_insertion_points(self, content: str) -> List[Dict]:
        """
        콘텐츠에서 제휴 링크 삽입 지점 찾기
        
        Returns:
            [{"position": int, "context": str, "type": str, "line": str}, ...]
        """
        insertion_points = []
        lines = content.split('\n')
        
        current_h2 = None
        h2_pattern = re.compile(r'^##\s+(.+)$', re.IGNORECASE)
        
        for i, line in enumerate(lines):
            # H2 감지
            h2_match = h2_pattern.match(line)
            if h2_match:
                current_h2 = h2_match.group(1).strip()
                # 이 H2 섹션에 제휴 링크 삽입이 적절한지 확인
                affiliate_type = self.should_insert_in_section(current_h2)
                if affiliate_type:
                    insertion_points.append({
                        "position": i,
                        "context": f"H2: {current_h2}",
                        "type": affiliate_type,
                        "line": line,
                        "after_h2": True,
                    })
                continue
            
            # H2 다음 첫 문단 찾기
            if current_h2 and line.strip() and not line.startswith('#'):
                affiliate_type = self.should_insert_in_section(current_h2)
                if affiliate_type and not any(
                    p["position"] == i - 1 and p.get("after_h2") 
                    for p in insertion_points
                ):
                    # 이미 해당 H2에 대해 삽입 지점을 추가했는지 확인
                    already_added = any(
                        p["position"] == i and p["context"].startswith(f"H2: {current_h2}")
                        for p in insertion_points
                    )
                    if not already_added:
                        insertion_points.append({
                            "position": i,
                            "context": f"본문: {line[:50]}...",
                            "type": affiliate_type,
                            "line": line,
                            "after_h2": False,
                        })
                
                # 한 섹션당 1개만 삽입 (중복 방지)
                current_h2 = None
        
        return insertion_points
    
    def generate_trip_hotel_link(self, destination: str, checkin: str = "", 
                                  checkout: str = "") -> str:
        """Trip.com 호텔 검색 링크 생성"""
        if not self.affiliate.is_trip_configured():
            # 폴백: 일반 Trip.com 검색 링크
            encoded_dest = destination.replace(" ", "-").lower()
            return f"https://www.trip.com/hotels/{encoded_dest}/"
        
        # API 기반 링크 (구현 필요)
        return self.affiliate.generate_trip_hotel_link(
            hotel_id="", checkin=checkin, checkout=checkout
        )
    
    def generate_skyscanner_link(self, origin: str = "", destination: str = "") -> str:
        """Skyscanner 항공권 검색 링크 생성"""
        if not self.affiliate.is_skyscanner_configured():
            # 폴백: 일반 Skyscanner 링크
            if destination:
                encoded_dest = destination.replace(" ", "-").lower()
                return f"https://www.skyscanner.com/transport/flights/{encoded_dest}/"
            return "https://www.skyscanner.com/"
        
        return self.affiliate.generate_skyscanner_link(origin, destination, "")
    
    def insert_affiliate_link(self, content: str, insert_after_line: int,
                               link_text: str, url: str) -> str:
        """
        지정된 라인 다음에 제휴 링크 삽입
        
        Args:
            content: 원본 콘텐츠
            insert_after_line: 삽입할 라인 번호 (0-indexed)
            link_text: 링크 텍스트
            url: 제휴 URL
        
        Returns:
            수정된 콘텐츠
        """
        lines = content.split('\n')
        
        # 링크 HTML 생성
        affiliate_html = f'''
**[바로 예약하기]({url})** — {link_text}
'''
        
        # 삽입 지점 찾기 (빈 줄 다음)
        insert_pos = insert_after_line + 1
        while insert_pos < len(lines) and lines[insert_pos].strip() == '':
            insert_pos += 1
        
        # 삽입
        lines.insert(insert_pos, "")
        lines.insert(insert_pos + 1, affiliate_html.strip())
        lines.insert(insert_pos + 2, "")
        
        return '\n'.join(lines)
    
    def add_disclosure(self, content: str) -> str:
        """포스트 하단에 제휴 면책 문구 추가"""
        disclosure = '''
---

*이 포스트에는 제휴 링크가 포함될 수 있습니다. 링크를 통해 예약/구매 시 추가 비용 없이 소정의 수수료를 받을 수 있습니다.*
'''
        
        # 기존 면책 문구가 있는지 확인
        if "제휴 링크" in content or "affiliate" in content.lower():
            return content
        
        # 마지막 H2 뒤에 추가 (맺음말 섹션이 있다면 그 앞에)
        lines = content.rstrip().split('\n')
        
        # 마지막 문단 찾기
        last_content_idx = len(lines) - 1
        while last_content_idx >= 0 and lines[last_content_idx].strip() == '':
            last_content_idx -= 1
        
        if last_content_idx >= 0:
            lines.insert(last_content_idx + 1, disclosure.strip())
        
        return '\n'.join(lines)
    
    def process(self, content: str, max_links: int = 3) -> str:
        """
        콘텐츠에 제휴 링크 삽입
        
        Args:
            content: 원본 마크다운 콘텐츠
            max_links: 최대 삽입할 링크 수
        
        Returns:
            수정된 콘텐츠
        """
        insertion_points = self.find_insertion_points(content)
        
        # 삽입 지점 필터링 (중복 제거, 적절한 위치만)
        filtered_points = []
        seen_sections = set()
        
        for point in insertion_points:
            # H2 기준 중복 방지
            if point.get("after_h2"):
                # H2 제목에서 핵심 단어 추출
                section_key = point["context"][4:20]  # "H2: " 이후
                if section_key in seen_sections:
                    continue
                seen_sections.add(section_key)
            
            filtered_points.append(point)
        
        # 링크 생성 및 삽입
        result = content
        inserted_count = 0
        
        for point in filtered_points:
            if inserted_count >= max_links:
                break
            
            affiliate_type = point["type"]
            url = ""
            link_text = ""
            
            if affiliate_type == "trip":
                # Trip.com 호텔 링크
                url = "https://www.trip.com/hotels/"
                link_text = " Trip.com에서 현재 특가 호텔 확인"
            elif affiliate_type == "skyscanner":
                # Skyscanner 항공권 링크
                url = "https://www.skyscanner.com/"
                link_text = " Skyscanner에서 항공권 최저가 비교"
            elif affiliate_type == "viator":
                # Viator 투어 링크
                url = "https://www.viator.com/"
                link_text = " Viator에서 투어/액티비티 예약"
            
            if url:
                result = self.insert_affiliate_link(
                    result,
                    point["position"],
                    link_text.strip(),
                    url
                )
                inserted_count += 1
        
        # 면책 문구 추가
        result = self.add_disclosure(result)
        
        return result


def process_post(post_path: str, blog_id: str, dry_run: bool = False) -> str:
    """
    단일 포스트 처리
    
    Args:
        post_path: 포스트 index.md 경로
        blog_id: 블로그 ID
        dry_run: True면 수정 없이 결과만 출력
    
    Returns:
        수정된 콘텐츠
    """
    with open(post_path, 'r') as f:
        original_content = f.read()
    
    injector = AffiliateLinkInjector(blog_id)
    modified_content = injector.process(original_content)
    
    if dry_run:
        print(f"=== Dry run: {post_path} ===")
        if original_content != modified_content:
            print("변경 사항 발생:")
            print(modified_content[-500:])  # 마지막 500자만 출력
        else:
            print("변경 없음")
        return modified_content
    
    # 파일 저장
    with open(post_path, 'w') as f:
        f.write(modified_content)
    
    print(f"처리 완료: {post_path}")
    return modified_content


def process_blog_posts(blog_path: str, blog_id: str, dry_run: bool = False):
    """블로그의 모든 포스트 처리"""
    posts_dir = os.path.join(blog_path, "content", "posts")
    
    if not os.path.isdir(posts_dir):
        print(f"포스트 디렉토리 없음: {posts_dir}")
        return
    
    count = 0
    for root, dirs, files in os.walk(posts_dir):
        for fname in files:
            if fname == "index.md":
                fpath = os.path.join(root, fname)
                process_post(fpath, blog_id, dry_run)
                count += 1
    
    print(f"\n총 {count}개 포스트 처리")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="ETAP 제휴 링크 삽입기")
    parser.add_argument("blog_path", help="블로그 디렉토리 경로")
    parser.add_argument("--blog-id", help="블로그 ID (예: tour-hugo)", default="")
    parser.add_argument("--dry-run", action="store_true", help="실제 수정 없이 결과만 확인")
    
    args = parser.parse_args()
    
    blog_id = args.blog_id or os.path.basename(args.blog_path).replace("-hugo", "")
    
    if args.dry_run:
        print("=== Dry Run Mode ===")
    
    process_blog_posts(args.blog_path, blog_id, args.dry_run)

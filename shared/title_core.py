"""Unified title generation core — shared by TAP (Blogger) and 5000 (Hugo) pipelines."""
import re
import random
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────
BANNED_ENDINGS = ["소개", "알아보기", "만나보기", "살펴보기", "확인하기", "코스 안내", "안내"]
BANNED_PHRASES = ["에서 즐기는", "에서 만나는", "에서 즐길 수 있는"]
BANNED_WORDS = [
    '포함', '직접 가본', '직접 다녀온', '다녀왔어요', '다녀왔습니다',
    '방문 후기', '솔직 후기', '실제 후기', '이용 후기', '후기',
    '실제 방문', '실제 이용', '인생', '꼭 가봐야', '필수', '최고의', '감성 가득',
    '핫플', 'SNS 핫플', '인생샷',
]
MIN_TITLE_LEN = 25
MAX_TITLE_LEN = 35

# Travel blog TITLE_TEMPLATES (moved from writer.py, all <=35 chars when filled)
TRAVEL_TITLE_TEMPLATES = {
    "travel-hugo": [
        "{region} {first_camp} 포함 {count}곳 비교",
        "{region} {theme} {count}곳 총정리",
        "{region} 캠핑장 {first_camp} 등 {count}곳",
        "{region} {first_camp}부터 {last_camp}까지",
        "{region} {theme} {first_camp} 주변",
        "{region} {first_camp} 시설과 예약 정보",
        "{region} {theme} {count}곳 비교",
        "{region} {first_camp} 포함 캠핑장 {count}곳",
        "{region} {count}곳 {first_camp} 등 시설",
        "{region} {first_camp} 예약 전 알아둘 것",
    ],
    "travel1-hugo": [
        "2026 {region} {first_name} 일정과 입장료",
        "{region} {first_name} 프로그램과 체험",
        "{first_name} 일정부터 주차까지",
        "2026 {region} {first_name} 개최 정보",
        "{region} {first_name} 교통과 주차 정보",
        "{first_name} 방문 전 준비 사항",
        "{region} {first_name} 주변 가볼만한 곳",
        "2026 {region} {first_name} 관람 정보",
        "{first_name} 함께 즐기는 {region}",
        "{region} {first_name} 포함 축제 일정",
        "{region} {theme} 일정과 입장료",
        "{region} {theme} 가볼만한 곳 {count}선",
        "{region} {theme} 일정부터 주차까지",
        "2026 {region} 축제 {count}곳 일정",
        "주말 나들이 {region} {theme} {count}곳",
        "{region} 무료 축제 {count}곳 총정리",
        "{region} {theme} 포토존과 인생샷 팁",
        "{region} {theme} 야간 프로그램 안내",
        "{region} {theme}와 당일치기 코스",
        "{region} {theme} 사전예약과 입장 안내",
    ],
    "travel2-hugo": [
        "{region} {first_name} 역사와 건축",
        "{region} {first_name} 방문 전 역사 정리",
        "{first_name} 시대적 배경과 특징",
        "{region} {theme} {first_name} 지정 가치",
        "{first_name} 탐방 가이드 총정리",
        "{region} {first_name} 역사 해설",
        "{region} {theme} {first_name} 양식 비교",
        "{first_name}이 {theme}로 지정된 이유",
        "{region} {first_name} 완전 해설",
        "{region} {theme} {first_name} 탐방 정보",
    ],
    "travel3-hugo": [
        "{region} {theme} 현지인 추천 {count}곳",
        "{region} 꼭 먹어야 할 {theme} {count}선",
        "{region} {theme} 가성비 식당 {count}곳",
        "현지인만 아는 {region} {theme}",
        "{region} {theme} 웨이팅 없는 식당",
        "{region} 로컬 맛집 {count}곳 정리",
        "{region} {theme} 혼밥하기 좋은 식당",
        "여행 중 들르기 좋은 {region}",
        "주말 {region} {theme} {count}곳",
        "{region} {angle} 맛집 {count}곳",
        "{region} {theme} 가성비 식당 비교",
        "{region} {theme} 주차 가능한 식당",
        "아이와 가기 좋은 {region}",
        "{region} {theme} 오래된 노포 {count}곳",
        "{region} {theme} 점심 특선 비교",
        "관광지 근처 {region} {theme}",
        "{region} {theme} 예약 필수 식당",
        "{region} 새벽 영업 {theme} {count}곳",
        "{region} {theme} 뷰 좋은 식당",
        "포장 배달 가능한 {region}",
    ],
    "travel4-hugo": [
        "{region} 여행코스 {first_name} 포함",
        "{region} {theme} {first_name}부터 코스",
        "{region} {theme} 추천 코스 {count}곳",
        "{region} 당일치기 여행코스 {count}곳",
        "{region} {theme} {count}곳 코스 정리",
        "{region} {first_name} 주변 여행코스",
        "주말 {region} {theme} 코스 {count}곳",
        "{region} {theme} 코스 {first_name} 등",
        "{region} 여행코스 {first_name} 포함",
        "{region} {theme} {count}곳 코스 순서",
    ],
}


# ── Core functions ─────────────────────────────────────────────────────

def extract_place_names(items: list) -> list:
    """Extract place names from API items. Returns sorted by length (shortest first), max 4.

    Upper length limit is loose (<= 30) so longer proper nouns like
    "봉포레이크 글램핑 오토캠핑장" reach the title prompt and fallback.
    """
    names = []
    for item in items:
        name = item.get("title", "") or item.get("facltNm", "")
        if name and 2 <= len(name) <= 30:
            names.append(name)
    names.sort(key=len)
    return names[:4]


def clean_title(title: str) -> str:
    """Post-process: remove banned words, clean punctuation, normalize spaces."""
    if not title:
        return title
    for word in BANNED_WORDS:
        title = title.replace(word, "")
    for phrase in BANNED_PHRASES:
        title = title.replace(phrase, " ")
    for ban in BANNED_ENDINGS:
        if title.endswith(ban):
            title = title[: -len(ban)].rstrip()
            break
    title = title.replace(",", "").replace(";", "").replace(":", "")
    title = re.sub(r"\s+", " ", title).strip()
    return title


def build_title_prompt(region: str, theme: str, place_names: list,
                       source_type: str = "", blog_id: str = "") -> str:
    """Build AI prompt for title generation.

    Args:
        region: Display region name (e.g., "강원도")
        theme: Content theme (e.g., "캠핑", "맛집")
        place_names: List of place names to include
        source_type: "heritage", "camping", "food", "course", etc.
        blog_id: Blog identifier for prompt variation

    Returns:
        Prompt string for AI title generation
    """
    places_str = ", ".join(place_names[:3]) if place_names else theme

    if source_type == "heritage" or blog_id == "travel2-hugo":
        return f"""자연스럽고 클릭하고 싶은 한국어 블로그 제목 1개만 출력하세요. 따옴표 없이 제목만.

지역: {region}
테마: {theme}
문화유산: {places_str}

핵심 원칙: 지역명과 문화유산 실제 이름을 앞쪽에 넣고, 역사·건축·가치 등 성격이 드러나게. 군더더기 없이 25~35자.
특수기호(콜론/느낌표/하이픈)와 가격 표현만 금지. 어순·표현은 가장 자연스럽게 자유롭게.

좋은 제목 예시 (그대로 베끼지 말고 톤과 감각만 참고):
- 경주 불국사 다보탑 석조 기법과 지정 배경
- 강화 전등사의 시대적 배경과 건축적 가치
- 서울 숭례문 복원 과정과 국보의 의미

제목만 출력:"""
    else:
        return f"""클릭하고 싶은 한국어 블로그 제목 1개만 출력하세요. 따옴표 없이 제목만.

지역: {region}
테마: {theme}
장소: {places_str}

규칙:
- 장소 이름을 제목 앞쪽에 배치 (특정 장소명 검색에 걸리도록)
- "정리", "비교", "모음", "총정리", "안내", "목록" 등 정보 나열형 종결어 사용 금지
- 특수기호(콜론/느낌표/하이픈)와 가격 표현 금지
- 25~35자

제목만 출력:"""


def validate_and_retry(title: str, prompt: str, ai_func, max_len: int = 35) -> str:
    """Validate title against bans and length. Retry once if invalid.

    Args:
        title: Generated title to validate
        prompt: Original prompt for retry
        ai_func: Callable(system, user, tier, temperature) -> dict with "content" key
        max_len: Maximum allowed title length

    Returns:
        Validated title, or fallback if all attempts fail
    """
    if not title:
        return title

    title = clean_title(title)

    # Check length
    if len(title) > max_len:
        # Try word-boundary truncation
        truncated = title[:max_len].rsplit(" ", 1)
        title = truncated[0] if len(truncated) > 1 else title[:max_len]

    # Check banned content remains
    has_ban = False
    for w in BANNED_WORDS:
        if w in title:
            has_ban = True
            break
    if not has_ban:
        for e in BANNED_ENDINGS:
            if title.endswith(e):
                has_ban = True
                break

    if has_ban or len(title) < MIN_TITLE_LEN:
        # Retry once
        retry_prompt = prompt + "\n\n[재시도] 이전 제목이 규칙을 위반했습니다. 반드시 25~35자, 금지어 없이 다시 작성하세요."
        try:
            result = ai_func("블로그 제목 생성 전문가. 제목 1개만 출력.", retry_prompt, "default", 0.7)
            if result and result.get("content"):
                title = result["content"].strip().strip('"').strip("'")
                title = re.sub(r"^(제목[:\s]*|Title[:\s]*)", "", title).strip()
                title = clean_title(title)
                if len(title) > max_len:
                    truncated = title[:max_len].rsplit(" ", 1)
                    title = truncated[0] if len(truncated) > 1 else title[:max_len]
        except Exception as e:
            logger.warning(f"Title retry failed: {e}")

    return title


def make_fallback(region: str, theme: str, count: int,
                  camp_names: list = None, blog_id: str = "travel-hugo") -> str:
    """Generate a deterministic fallback title <= 35 chars. No AI needed."""
    first = ""
    if camp_names:
        first = camp_names[0] if isinstance(camp_names[0], str) else ""

    if blog_id == "travel3-hugo":
        base = f"{region} {theme} {count}곳"
    elif blog_id == "travel4-hugo":
        base = f"{region} 여행코스 {count}곳"
    elif first:
        base = f"{region} {first} 포함 {count}곳"
    else:
        base = f"{region} {theme} {count}곳"

    # Ensure <= max_len
    if len(base) > MAX_TITLE_LEN:
        base = base[:MAX_TITLE_LEN]

    logger.info(f"Fallback title ({len(base)} chars): {base}")
    return base

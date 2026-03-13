import sys
import os
import logging
import re

sys.path.insert(0, "/Users/twinssn/Projects/tour-auto-publisher")
os.chdir("/Users/twinssn/Projects/tour-auto-publisher")

from dotenv import load_dotenv
load_dotenv("/Users/twinssn/Projects/tour-auto-publisher/.env")
load_dotenv("/Users/twinssn/Projects/5000/.env")

sys.path.insert(0, "/Users/twinssn/Projects/5000")

from shared.ai_writer import generate as ai_generate
from shared.prompt_builder import build as build_prompt

logger = logging.getLogger(__name__)

BLOG_PROMPT_MAP = {
    "travel-hugo": {"camping": "tour1_camping", "korservice": "tour1_leports", "wellness": "tour1_leports", "heritage": "tour1_leports"},
    "travel1-hugo": {"korservice": "travel1_festival", "festival": "travel1_festival"},
    "travel2-hugo": {"heritage": "travel2_heritage", "korservice": "travel2_heritage"},
    "travel3-hugo": {"korservice": "tour2_food", "food": "tour2_food"},
    "travel4-hugo": {"korservice": "tour3_course", "course": "tour3_course"},
}


def _select_prompt_id(blog_id, source_type):
    blog_map = BLOG_PROMPT_MAP.get(blog_id, BLOG_PROMPT_MAP.get("travel-hugo", {}))
    return blog_map.get(source_type, "tour1_camping")


def _build_data_block(data):
    items = data.get("items", [])
    lines = []
    lines.append(f"지역: {data.get('display_region', '')}")
    lines.append(f"시군구: {data.get('sigungu', '')}")
    lines.append(f"테마: {data.get('theme', '')}")
    lines.append(f"세부조건: {data.get('angle', '')}")
    lines.append(f"장소 수: {len(items)}")
    lines.append("")

    for i, item in enumerate(items, 1):
        lines.append(f"[장소 {i}]")
        lines.append(f"이름: {item.get('facltNm', item.get('title', ''))}")
        lines.append(f"주소: {item.get('addr1', item.get('addr', ''))}")

        if item.get("lineIntro"):
            lines.append(f"한줄소개: {item['lineIntro']}")
        if item.get("featureNm"):
            lines.append(f"특징: {item['featureNm']}")
        if item.get("sbrsCl"):
            lines.append(f"부대시설: {item['sbrsCl']}")
        if item.get("posblFcltyCl"):
            lines.append(f"주변시설: {item['posblFcltyCl']}")
        if item.get("themaEnvrnCl"):
            lines.append(f"테마환경: {item['themaEnvrnCl']}")
        if item.get("induty"):
            lines.append(f"업종: {item['induty']}")
        if item.get("lctCl"):
            lines.append(f"입지: {item['lctCl']}")
        if item.get("facltDivNm"):
            lines.append(f"시설구분: {item['facltDivNm']}")
        if item.get("manageSttus"):
            lines.append(f"운영상태: {item['manageSttus']}")
        if item.get("homepage"):
            lines.append(f"홈페이지: {item['homepage']}")
        if item.get("tel"):
            lines.append(f"전화: {item['tel']}")
        if item.get("firstImageUrl"):
            lines.append(f"이미지: {item['firstImageUrl']}")

        lines.append("")

    return "\n".join(lines)



def _inject_naver_map(body_md, items):
    import urllib.parse
    if not items:
        return body_md
    map_links = []
    for item in items:
        title = item.get("title", item.get("facltNm", "")).strip()
        if not title:
            continue
        encoded = urllib.parse.quote(title)
        url = "https://map.naver.com/v5/search/" + encoded
        map_links.append((title, url))
    if not map_links:
        return body_md
    lines = body_md.split("\n")
    result = []
    for line in lines:
        result.append(line)
        if not re.match(r"^##\s+", line):
            continue
        for ml_title, ml_url in map_links:
            name_parts = [p for p in ml_title.split() if len(p) >= 2]
            if any(part in line for part in name_parts):
                btn = "> [" + ml_title + " 네이버 지도에서 보기](" + ml_url + ")"
                result.append("")
                result.append(btn)
                break
    return "\n".join(result)


def _inject_images(items, content):
    """API image URLs into body after each H2 in order"""
    existing = len(re.findall(r'!\[', content))
    if existing >= len(items):
        return content

    img_list = []
    for item in items:
        name = item.get("facltNm", item.get("title", ""))
        img = item.get("firstImageUrl") or item.get("firstimage") or item.get("image") or ""
        if name and img and img.startswith("http"):
            img_list.append((name, img))

    if not img_list:
        return content

    lines = content.split("\n")
    result = []
    img_idx = 0
    for line in lines:
        result.append(line)
        if line.startswith("## ") and img_idx < len(img_list):
            name, img_url = img_list[img_idx]
            result.append("")
            result.append(f"![{name}]({img_url})")
            result.append("")
            img_idx += 1

    if img_idx < len(img_list):
        result.append("")
        for name, img_url in img_list[img_idx:]:
            result.append(f"![{name}]({img_url})")
            result.append("")

    return "\n".join(result)

def _enrich_with_nearby(data, html):
    import urllib.parse
    from core.content_processor import enrich_items_with_blog_info, get_nearby_info

    items = data.get("items", [])
    sigungu = data.get("sigungu", "")

    items = enrich_items_with_blog_info(items)
    nearby_data = get_nearby_info(items, sigungu)

    if not nearby_data:
        return html

    nearby_html = ""

    attractions = nearby_data.get("attractions", [])
    if attractions:
        nearby_html += "\n\n## 반경 10km 내 가볼만한 곳\n\n"
        for a in attractions[:3]:
            name = a.get("title", "")
            if not name:
                continue
            encoded = urllib.parse.quote(name)
            url = "https://map.naver.com/v5/search/" + encoded
            nearby_html += "[" + name + " 지도에서 보기](" + url + ")\n\n"

    restaurants = nearby_data.get("restaurants", [])
    if restaurants:
        nearby_html += "\n\n## 반경 10km 내 맛집\n\n"
        for r in restaurants[:3]:
            name = r.get("title", "")
            if not name:
                continue
            encoded = urllib.parse.quote(name)
            url = "https://map.naver.com/v5/search/" + encoded
            tel = r.get("tel", "")
            nearby_html += "[" + name + " 지도에서 보기](" + url + ")\n\n"
            if tel:
                nearby_html += "전화: " + tel + "\n\n"

    return html + nearby_html


def generate_content(data, blog_id="travel-hugo"):
    source_type = data.get("source_type", "camping")
    prompt_id = _select_prompt_id(blog_id, source_type)

    data_block = _build_data_block(data)

    extra_vars = {
        "region": data.get("display_region", ""),
        "theme": data.get("theme", ""),
        "angle": data.get("angle", ""),
        "count": str(len(data.get("items", []))),
    }

    prompt_result = build_prompt(prompt_id, data_block, extra_vars=extra_vars)
    system_prompt = prompt_result["system"]
    user_prompt = prompt_result["user"]

    result = ai_generate(system_prompt, user_prompt, tier="default")

    if not result or not result.get("content"):
        logger.error("AI 생성 실패: prompt_id=%s", prompt_id)
        return None

    content = result["content"]
    model_used = result.get("model", "")

    content = _enrich_with_nearby(data, content)
    items = data.get("items", [])
    content = _inject_images(items, content)
    content = _inject_naver_map(content, items)

    display_region = data.get("display_region", "")
    theme = data.get("theme", "")
    angle = data.get("angle", theme)
    items = data.get("items", [])

    TITLE_TEMPLATES = {
        "travel-hugo": [
            "{region} {theme} {count}곳 가격 시설 완전 비교",
            "{region} {angle} 캠핑장 {count}곳 비교 후 고른 곳",
            "{region} {theme} 어디가 좋을까 {count}곳 비교",
            "{count}곳 비교 {region} {angle} 캠핑장 추천",
            "{region} 캠핑장 {count}곳 1박 가격 총정리",
            "{region} {theme} 예약 전 반드시 확인할 {count}곳",
            "{region} {angle} 캠핑장 가격 순위 TOP {count}",
            "2026 {region} {theme} {count}곳 시설 비교 정리",
            "{region} 반려동물 동반 캠핑장 {count}곳 비교",
            "{region} {theme} 전기 사이트 있는 곳 {count}선",
            "{region} 주말 캠핑 {count}곳 가격대별 정리",
            "{region} {angle} 초보 캠퍼 추천 {count}곳",
            "{region} 캠핑장 {count}곳 장단점 솔직 비교",
            "{region} {theme} 가성비 좋은 {count}곳 정리",
            "가족 캠핑 {region} {theme} {count}곳 비교",
            "{region} {angle} 조용한 캠핑장 {count}곳",
            "{region} 캠핑장 {count}곳 예약 꿀팁 포함",
            "{region} {theme} 시즌별 가격 차이 {count}곳",
            "올여름 {region} {theme} {count}곳 비교 정리",
            "{region} 계곡 근처 캠핑장 {count}곳 총정리",
        ],
        "travel1-hugo": [
            "{region} {theme} 일정 입장료 주차 총정리 2026",
            "2026 {region} {theme} 축제 {count}선",
            "{region} {theme} 알고 가면 2배 즐기는 법",
            "이번 주말 {region} {theme} 완벽 가이드",
            "{region} {theme} 입장료 무료인 곳 {count}선",
            "2026 {region} 봄 축제 {count}곳 일정 정리",
            "{region} {theme} 주차 셔틀 총정리",
            "{region} {theme} 아이와 가기 좋은 {count}곳",
            "{region} {theme} 비 올 때 대안 코스 포함",
            "{region} {theme} 현장 꿀팁 {count}가지",
            "2026 {region} 가을 축제 {count}곳 총정리",
            "{region} {theme} 사진 명소 {count}곳 포함",
            "{region} {theme} 먹거리 볼거리 {count}가지",
            "주말 나들이 {region} {theme} {count}곳 정리",
            "{region} {theme} 혼잡 시간 피하는 법",
            "2026 {region} 여름 축제 일정 {count}선",
            "{region} {theme} 대중교통으로 가는 법",
            "{region} {theme} 근처 맛집까지 {count}곳",
            "{region} 무료 축제 {count}곳 일정 총정리",
            "{region} {theme} 준비물 체크리스트 포함",
        ],
        "travel2-hugo": [
            "{region} {theme} 꼭 가봐야 할 {count}곳",
            "{region}에서 만나는 역사 여행 {count}선",
            "{region} {angle} 사진 찍기 좋은 명소 {count}곳",
            "{region} {theme} 해설 프로그램 있는 {count}곳",
            "{region} 국보 보물 {count}곳 입장료 총정리",
            "{region} {theme} 반나절 코스 {count}곳",
            "{region} 사찰 여행 {count}곳 주차 정보 포함",
            "역사 여행 {region} {theme} {count}곳 정리",
            "{region} {theme} 무료 입장 {count}곳 모음",
            "{region} 문화유산 {count}곳 숨은 디테일 정리",
            "{region} {angle} 걸어서 도는 코스 {count}곳",
            "{region} {theme} 봄에 가면 좋은 {count}곳",
            "아이와 함께 {region} {theme} {count}곳",
            "{region} {theme} 근처 카페까지 {count}곳 정리",
            "{region} 유네스코 유산 포함 {count}곳 코스",
            "{region} {theme} 사진 포인트 {count}곳",
            "{region} 고궁 탐방 {count}곳 운영시간 정리",
            "{region} {theme} 가을 단풍과 함께 {count}곳",
            "{region} 문화재 {count}곳 해설사 동행 가능",
            "{region} {theme} 주말 반나절 추천 {count}곳",
        ],
        "travel3-hugo": [
            "{region} {theme} 현지인 맛집 {count}곳 총정리",
            "{region} {angle} 맛집 {count}곳 메뉴 가격 정리",
            "현지인 추천 {region} {theme} {count}곳",
            "{region} 가면 꼭 먹어야 할 {theme} {count}선",
            "{region} {theme} 가성비 맛집 {count}곳 비교",
            "{region} {theme} 웨이팅 없는 곳 {count}선",
            "{region} 점심 맛집 {count}곳 1만원대 정리",
            "{region} {theme} 주차 편한 맛집 {count}곳",
            "{region} 로컬 맛집 {count}곳 메뉴판 가격 공개",
            "{region} {angle} 혼밥 가능한 맛집 {count}곳",
            "{region} {theme} 예약 필수인 곳 {count}선",
            "{region} 맛집 {count}곳 영업시간 휴무일 정리",
            "여행 중 {region} {theme} {count}곳 동선 포함",
            "{region} {theme} 2인 기준 가격 비교 {count}곳",
            "{region} {angle} 디저트 맛집까지 {count}곳",
            "{region} 향토 음식 {count}곳 메뉴 해설 포함",
            "{region} {theme} 아이와 가기 좋은 {count}곳",
            "{region} 맛집 {count}곳 리뷰 평점 비교",
            "{region} {theme} 저녁 코스로 좋은 {count}곳",
            "주말 {region} {theme} 맛집 {count}곳 총정리",
        ],
        "travel4-hugo": [
            "{region} 당일치기 코스 {count}곳 동선 정리",
            "{region} {theme} 1박2일 완벽 동선 {count}코스",
            "주말 {region} {theme} {count}곳 코스 플랜",
            "{region} {angle} 베스트 코스 {count}선",
            "{region} 7시간 완주 코스 {count}곳 타임라인",
            "{region} {theme} 차 없이 가능한 코스 {count}곳",
            "{region} 가족 여행 {count}곳 코스 총예산 포함",
            "{region} {theme} 오전 반나절 코스 {count}곳",
            "{region} 드라이브 코스 {count}곳 주차 정보",
            "2026 {region} {theme} 추천 코스 {count}선",
            "{region} 커플 여행 코스 {count}곳 동선 정리",
            "{region} {theme} 맛집 포함 {count}곳 풀코스",
            "{region} 당일치기 {count}곳 이동시간 총정리",
            "{region} {theme} 사진 명소 포함 {count}곳 코스",
            "{region} 아이와 하루 코스 {count}곳 플랜",
            "{region} {angle} 예산 5만원 코스 {count}곳",
            "{region} {theme} 계절별 추천 코스 {count}선",
            "평일 {region} {theme} 한적한 코스 {count}곳",
            "{region} 대중교통 코스 {count}곳 시간표 포함",
            "{region} {theme} 일출부터 일몰까지 {count}곳",
        ],
    }

    import random as _rand
    templates = TITLE_TEMPLATES.get(blog_id, TITLE_TEMPLATES["travel-hugo"])
    template = _rand.choice(templates)
    fallback_title = template.format(
        region=display_region,
        theme=theme,
        angle=angle,
        count=str(len(items)),
    )

    place_names = ', '.join([i.get('title', i.get('facltNm', ''))[:12] for i in items[:3]])
    title_prompt = f"""블로그 제목 1개만 출력하세요. 따옴표 없이 제목 텍스트만 출력.

지역: {display_region}
테마: {theme}
장소수: {len(items)}
대표 장소: {place_names}

필수 규칙:
- 25~40자 (이 범위 밖이면 불합격)
- 지역명 + 숫자 + 고유명사(축제명/장소명/메뉴명) 반드시 포함
- 구체적 정보 1개 포함 (가격, 시간, 거리, 입장료 등)
- 경어체 금지 (입니다, 합니다, 드립니다, 하세요)
- 특수기호 금지 (콜론, 하이픈, 파이프, 플러스, 느낌표)

금지 표현:
- "완벽 가이드", "총정리", "꼭 가봐야 할", "추천", "베스트"
- "현지인 추천", "상세정보", "즐기기"

좋은 제목 예시:
- "강릉 커피축제 입장 무료 3곳 주차 500대 가능"
- "부산 불꽃축제 2026 관람 명당 4곳 셔틀 노선 포함"
- "전주 비빔밥축제 체험비 5천원 아이 동반 프로그램 3가지"
- "대구 치맥페스티벌 무료존 위치와 야간 공연 시간표"

나쁜 제목 예시 (이렇게 쓰지 마):
- "경북 축제 추천 3곳 청도반시축제와 백두대간 봉자페스티벌 상세정보" (너무 김, 추천/상세정보 사용)
- "충북 제천과 단양의 5대 축제 명소 가을철 즐기기 완벽 가이드" (완벽 가이드, 즐기기 사용)
"""

    title_result = ai_generate(
        "블로그 제목 생성 전문가. 제목 1개만 출력.",
        title_prompt,
        tier="economy"
    )

    if title_result and title_result.get("content"):
        generated_title = title_result["content"].strip().strip('"').strip("'").strip()
        generated_title = re.sub(r'^(제목[:\s]*|Title[:\s]*)', '', generated_title).strip()
        if len(generated_title) > 5:
            title = generated_title

    labels = list(set(filter(None, [
        data.get("category", "국내여행"),
        theme,
        display_region,
    ])))

    return {
        "title": title,
        "body_md": content,
        "body_html": "",
        "labels": labels,
        "theme": theme,
        "category": data.get("category", "국내여행"),
        "region": display_region,
        "angle": angle,
        "items_count": len(items),
        "source_type": source_type,
        "prompt_id": prompt_id,
        "model": model_used,
    }

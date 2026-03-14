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



def _validate_and_retry(content, system_prompt, user_prompt, max_retries=1):
    """생성된 콘텐츠의 H2 수, 글자수, 금지표현을 검증하고 미달 시 재생성"""
    BANNED = ["바랍니다", "되시길", "있으시", "마무리하며", "마치며"]
    
    for attempt in range(max_retries + 1):
        # 검증
        h2_count = len(re.findall(r'^## ', content, re.MULTILINE))
        char_count = len(content)
        banned_found = [b for b in BANNED if b in content]
        
        issues = []
        if h2_count > 6:
            issues.append(f"H2 {h2_count}개→4개 필요")
        if char_count < 1800:
            issues.append(f"글자수 {char_count}→2200 필요")
        if banned_found:
            issues.append(f"금지표현: {banned_found}")
        
        if not issues:
            logger.info("콘텐츠 검증 통과 (H2:%d, 글자수:%d)", h2_count, char_count)
            return content
        
        if attempt < max_retries:
            logger.warning("콘텐츠 검증 실패 (시도 %d/%d): %s → 재생성", 
                          attempt + 1, max_retries + 1, ", ".join(issues))
            
            fix_instruction = f"""이전 글에 문제가 있어 다시 작성합니다.
수정사항:
- H2(##)는 정확히 4개만 사용하세요. 현재 {h2_count}개입니다.
- 글자수는 2,200자 이상이어야 합니다. 현재 {char_count}자입니다.
- 금지 표현({', '.join(BANNED)})을 절대 사용하지 마세요.
- 나머지 규칙은 동일합니다.

""" + user_prompt
            
            retry_result = ai_generate(system_prompt, fix_instruction, tier="default")
            if retry_result and retry_result.get("content"):
                content = retry_result["content"]
            else:
                logger.error("재생성 실패, 원본 유지")
                return content
        else:
            logger.warning("최종 검증: H2:%d, 글자수:%d, 금지:%s (수정 가능 항목 자동 보정)", 
                          h2_count, char_count, banned_found)
            
            # H2 초과 시 자동 보정: 5번째 이후 H2를 H3로 변환
            if h2_count > 4:
                lines = content.split("\n")
                h2_seen = 0
                for i, line in enumerate(lines):
                    if line.startswith("## "):
                        h2_seen += 1
                        if h2_seen > 4:
                            lines[i] = "###" + line[2:]
                content = "\n".join(lines)
                logger.info("H2 자동 보정: %d개 → 4개 (초과분 H3 변환)", h2_count)
            
            # H1→H2 자동 변환
            h1_lines = re.findall(r'^# [^#]', content, re.MULTILINE)
            if h1_lines:
                lines = content.split("\n")
                for i, line in enumerate(lines):
                    if re.match(r'^# [^#]', line):
                        lines[i] = "#" + line  # # → ##
                content = "\n".join(lines)
                logger.info("H1 자동 보정: %d개 → H2 변환", len(h1_lines))

            # 금지표현 자동 제거
            for b in banned_found:
                content = content.replace(b, "")
            
            return content
    
    return content


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

    # 후처리: H2 수, 글자수, 금지표현 검증 및 재생성
    content = _validate_and_retry(content, system_prompt, user_prompt)

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
            "2026 {region} {theme} {count}곳 시설과 가격 총정리",
            "{region}에서 찾은 {theme} {count}곳 비교 정리",
            "{region} {theme} 어디가 좋을까? {count}곳 비교해봤다",
            "{region} {angle} 캠핑장 {count}곳, 예약 전 꼭 확인하세요",
            "{region} 캠핑장 {count}곳 1박 가격과 시설 총정리",
            "{region} {theme} 중 가성비 좋은 {count}곳 추천",
            "가족 캠핑으로 좋은 {region} {theme} {count}곳 정리",
            "{region} {angle} 캠핑장 {count}곳, 조용한 곳만 골랐다",
            "올여름 {region} {theme} {count}곳 비교 총정리",
            "{region} 계곡 근처 캠핑장 {count}곳 추천 리스트",
        ],
        "travel1-hugo": [
            "2026 {region} {theme} 일정과 입장료 총정리",
            "{region} {theme} 가볼만한 곳 {count}선 추천",
            "이번 주말 {region} {theme}, 알고 가면 2배 즐긴다",
            "{region} {theme} 일정부터 주차까지 한눈에 보기",
            "2026 {region} 봄 축제 {count}곳 일정 총정리",
            "{region} {theme}, 아이와 함께 가기 좋은 {count}곳",
            "{region} {theme} 근처 맛집까지 한번에 정리",
            "주말 나들이로 딱! {region} {theme} {count}곳 추천",
            "{region} 무료 축제 {count}곳, 일정과 위치 총정리",
            "2026 {region} 가을 축제 {count}곳 완벽 가이드",
        ],
        "travel2-hugo": [
            "2026 {region} {theme} {count}곳 입장료와 운영시간 총정리",
            "{region} 문화유산 {count}곳으로 떠나는 역사 탐방 코스",
            "{region} 사적지 {count}곳, 해설 프로그램과 함께 즐기기",
            "{region} 역사 여행 {count}곳 주차와 교통 정보 정리",
            "{region}에서 만나는 국보와 보물 {count}곳 탐방 가이드",
            "{region} 문화재 {count}곳, 사진 찍기 좋은 포인트까지",
        ],
        "travel3-hugo": [
            "{region} {theme} 현지인이 추천하는 맛집 {count}곳",
            "{region}에 가면 꼭 먹어야 할 {theme} {count}선",
            "{region} {theme} 가성비 맛집 {count}곳 메뉴와 가격 정리",
            "현지인만 아는 {region} {theme} 맛집 {count}곳 총정리",
            "{region} {theme} 웨이팅 없는 맛집 {count}곳 추천",
            "{region} 로컬 맛집 {count}곳, 메뉴와 가격까지 정리",
            "{region} {theme} 혼밥하기 좋은 맛집 {count}곳",
            "여행 중 들르기 좋은 {region} {theme} 맛집 {count}곳",
            "주말 {region} {theme} 맛집 {count}곳 총정리",
            "{region} {angle} 맛집 {count}곳, 영업시간과 휴무일 정리",
        ],
        "travel4-hugo": [
            "{region} 당일치기 여행 코스 {count}곳 동선 총정리",
            "{region} {theme} 1박2일 코스, 완벽한 동선 정리",
            "주말에 떠나는 {region} {theme} {count}곳 코스 추천",
            "{region} {angle} 베스트 코스 {count}선 추천",
            "{region} 가족 여행 {count}곳 코스와 예산 정리",
            "2026 {region} {theme} 추천 코스 {count}선 총정리",
            "{region} 드라이브 코스 {count}곳, 주차 정보 포함",
            "{region}에서 하루 만에 즐기는 {theme} {count}곳 플랜",
            "{region} 대중교통으로 가능한 여행 코스 {count}곳",
            "{region} {theme} 맛집까지 포함한 풀코스 {count}곳",
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
- 20~35자
- 지역명 반드시 포함
- 조사(에서, 의, 과, 와, 으로, 부터)를 넣어 자연스러운 문장으로 작성
- 서술어(총정리, 비교, 추천, 정리, 가이드, 소개)로 마무리
- 경어체 금지 (입니다, 합니다, 드립니다, 하세요)
- 특수기호 금지 (콜론, 느낌표, 하이픈)
- 가격 정보는 제목에 넣지 않기 (본문에서 다룸)
- 고유명사(축제명/장소명)는 1개만 포함

금지 표현:
- "완벽 가이드", "꼭 가봐야 할", "베스트", "상세정보", "즐기기"

좋은 제목 예시:
- "2026 광주 비어페스트 일정과 인근 맛집 총정리"
- "강릉 커피축제 일정부터 주차까지 한눈에 보기"
- "부산에서 만나는 불꽃축제 관람 명당 4곳 정리"
- "전주 비빔밥축제, 아이와 함께 즐기는 체험 3가지"
- "경남 하동별맛축제 일정과 근처 맛집 추천"

나쁜 제목 예시 (비문, 키워드 나열):
- "경북 축제 추천 3곳 청도반시축제와 백두대간 봉자페스티벌 상세정보"
- "전남 해물 맛집 5곳 숙자네 1인분 2만원"
- "서울 한옥 스테이 5곳 평균 1박 요금 10만원"
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

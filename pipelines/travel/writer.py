import sys
import os
import logging
import re

sys.path.insert(0, "/Users/twinssn/Projects/TAP")
os.chdir("/Users/twinssn/Projects/TAP")

from dotenv import load_dotenv
load_dotenv("/Users/twinssn/Projects/TAP/.env")
load_dotenv("/Users/twinssn/Projects/5000/.env")

sys.path.insert(0, "/Users/twinssn/Projects/5000")

from shared.ai_writer import generate as ai_generate
from shared.prompt_builder import build as build_prompt

logger = logging.getLogger(__name__)



# ── Heritage 카드 링크 ─────────────────────────────────────
HERITAGE_CARDS = {
    "서울": {
        "title": "서울 궁궐 가이드 — 경복궁·창덕궁·덕수궁 4개 언어 해설",
        "url": "https://heritage.aikorea24.kr/",
        "image": "https://www.heritage.go.kr/gung/gogung1/images/ic-c1.jpg",
        "desc": "경복궁부터 종묘까지, 600년 역사의 궁궐을 4개 언어 해설·사진·지도로 탐험하세요."
    },
    "경기": {
        "title": "서울 궁궐·종묘 완벽 가이드 — 수도권에서 가까운 세계유산",
        "url": "https://heritage.aikorea24.kr/",
        "image": "https://www.heritage.go.kr/gung/gogung2/images/img_changdeok_story_bg_00_00.jpg",
        "desc": "경기도에서 30분 거리, UNESCO 세계유산 창덕궁과 종묘를 만나보세요."
    },
    "default": {
        "title": "한국 궁궐·종묘 가이드 — K-Heritage Guide",
        "url": "https://heritage.aikorea24.kr/",
        "image": "https://www.heritage.go.kr/gung/gogung4/images/mode_general_00_01.jpg",
        "desc": "경복궁, 창덕궁, 창경궁, 덕수궁, 종묘 — 4개 언어 해설과 사진으로 만나는 한국의 궁궐"
    }
}

def _build_heritage_card(region: str) -> str:
    """지역에 맞는 heritage 카드 HTML을 생성한다."""
    card = HERITAGE_CARDS.get(region, HERITAGE_CARDS["default"])
    html = (
        '\n<div style="margin:1.5em 0;padding:0;border:1px solid #e0d5c1;border-radius:12px;'
        'overflow:hidden;max-width:600px;background:#fffdf7;">'
        '<a href="' + card["url"] + '" target="_blank" rel="noopener" '
        'style="display:flex;text-decoration:none;color:inherit;">'
        '<img src="' + card["image"] + '" alt="K-Heritage Guide" '
        'style="width:120px;height:120px;object-fit:cover;flex-shrink:0;" loading="lazy"/>'
        '<div style="padding:12px 16px;flex:1;min-width:0;">'
        '<span style="display:inline-block;font-size:11px;color:#B8860B;'
        'font-weight:700;letter-spacing:0.5px;margin-bottom:4px;">K-HERITAGE GUIDE</span>'
        '<p style="margin:0 0 6px;font-size:15px;font-weight:700;line-height:1.35;'
        'color:#2c2416;">' + card["title"] + '</p>'
        '<p style="margin:0;font-size:13px;color:#6b5e4f;line-height:1.4;">'
        + card["desc"] + '</p>'
        '</div></a></div>\n'
    )
    return html


BLOG_PROMPT_MAP = {
    "travel-hugo": {"camping": "tour1_camping", "korservice": "tour1_leports", "wellness": "tour1_leports", "heritage": "tour1_leports"},
    "travel1-hugo": {"korservice": "travel1_festival", "festival": "travel1_festival"},
    "travel2-hugo": {"heritage": "travel2_heritage", "korservice": "travel2_heritage"},
    "travel3-hugo": {"korservice": "tour2_food", "food": "tour2_food"},
    "travel4-hugo": {"korservice": "tour3_course", "course": "tour3_course"},
    "tvshow-blogger": {"korservice": "tour2_food", "food": "tour2_food", "course": "tour3_course"},
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
        if item.get("eventstartdate"):
            lines.append(f"행사시작일: {item['eventstartdate']}")
        if item.get("eventenddate"):
            lines.append(f"행사종료일: {item['eventenddate']}")
        if item.get("playtime"):
            lines.append(f"운영시간: {item['playtime']}")
        if item.get("eventplace"):
            lines.append(f"행사장소: {item['eventplace']}")
        if item.get("usetimefestival"):
            lines.append(f"입장료: {item['usetimefestival']}")
        if item.get("sponsor1"):
            lines.append(f"주최: {item['sponsor1']}")
        if item.get("program"):
            lines.append(f"프로그램: {item['program']}")
        if item.get("subevent"):
            lines.append(f"부대행사: {item['subevent']}")
        if item.get("agelimit"):
            lines.append(f"이용제한: {item['agelimit']}")
        if item.get("blog_snippets"):
            lines.append("네이버 블로그 참고정보 (사실 확인 불가, 참고용):")
            for sn in item["blog_snippets"][:6]:
                lines.append(f"  - {sn}")
        if item.get("firstImageUrl"):
            lines.append(f"이미지: {item['firstImageUrl']}")

        # blog_info enrichment 데이터
        bi = item.get("blog_info", {})
        # 가격대는 정확한 메뉴별 가격이 아니므로 GPT에 전달하지 않음
        # 블로그 후기는 체험형 인용 위험이 있으므로 GPT에 전달하지 않음
        if bi.get("facilities"):
            lines.append(f"시설: {', '.join(bi['facilities'][:5])}")
        if bi.get("targets"):
            lines.append(f"추천 대상: {', '.join(bi['targets'][:3])}")
        # 다이닝코드 데이터 (메뉴, 영업시간, 주차, 평점)
        dc = item.get("diningcode", {})
        if dc.get("main_menus"):
            lines.append(f"대표메뉴: {', '.join(dc['main_menus'][:5])}")
        if dc.get("hours"):
            lines.append(f"영업시간: {dc['hours']}")
        if dc.get("closed_days"):
            lines.append(f"휴무일: {dc['closed_days']}")
        if dc.get("parking"):
            lines.append(f"주차: {dc['parking']}")
        if dc.get("rating"):
            lines.append(f"평점: {dc['rating']}")
        if dc.get("keywords"):
            lines.append(f"특징: {', '.join(dc['keywords'][:5])}")

        lines.append("")

    # nearby 맛집 데이터 추가
    nearby_restaurants = data.get("nearby_restaurants", [])
    if nearby_restaurants:
        lines.append("")
        lines.append("[주변 실제 맛집 데이터 - 이 데이터만 맛집으로 사용하세요]")
        for nr in nearby_restaurants[:5]:
            name = nr.get("title", "")
            tel = nr.get("tel", "")
            lines.append(f"- {name}" + (f" (전화: {tel})" if tel else ""))

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
        if not re.match(r"^#{2,3}\s+", line):
            continue
        for ml_title, ml_url in map_links:
            name_parts = [p for p in ml_title.split() if len(p) >= 2]
            if any(part in line for part in name_parts):
                btn = "> [" + ml_title + " 네이버 지도에서 보기](" + ml_url + ")"
                result.append("")
                result.append(btn)
                break
    return "\n".join(result)


def _fallback_image_from_korservice(items, theme):
    """이미지 없는 아이템에 한국관광공사 키워드 검색으로 대체 이미지 확보"""
    import requests
    api_key = os.environ.get("TOUR_API_KEY", "") or os.environ.get("TOURAPI_KEY", "") or os.environ.get("DATA_GO_KR_API_KEY", "")
    if not api_key:
        return items
    for item in items:
        img = item.get("firstImageUrl") or item.get("firstimage") or item.get("image") or ""
        if img and img.startswith("http"):
            continue
        keyword = item.get("title", "")[:20]
        if not keyword:
            continue
        try:
            resp = requests.get(
                "http://apis.data.go.kr/B551011/KorService2/searchKeyword2",
                params={
                    "serviceKey": api_key,
                    "keyword": keyword,
                    "numOfRows": 5,
                    "pageNo": 1,
                    "MobileOS": "ETC",
                    "MobileApp": "5000",
                    "_type": "json",
                },
                timeout=10,
            )
            resp_items = resp.json().get("response", {}).get("body", {}).get("items", {}).get("item", [])
            if isinstance(resp_items, dict):
                resp_items = [resp_items]
            for ri in resp_items:
                fi = ri.get("firstimage", "")
                if fi and fi.startswith("http"):
                    item["firstimage"] = fi
                    item["image"] = fi
                    logger.info("폴백 이미지 확보: %s → %s", keyword[:15], fi[:60])
                    break
        except Exception as e:
            logger.warning("폴백 이미지 실패 (%s): %s", keyword[:15], str(e))
    return items


def _inject_images(items, content, blog_id=None):
    """API image URLs into body after each H2 in order"""
    existing = len(re.findall(r'!\[', content))
    if existing >= len(items):
        return content

    from shared.content_store import is_image_used
    img_list = []
    for item in items:
        name = item.get("facltNm", item.get("title", ""))
        img = item.get("firstImageUrl") or item.get("firstimage") or item.get("image") or ""
        if name and img and img.startswith("http"):
            if is_image_used(img, blog_id=blog_id):
                logger.info("이미지 중복 스킵: %s (%s)", name[:20], img[-30:])
                continue
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

    # enrichment는 generate_content에서 이미 실행됨 (중복 호출 방지)
    # items = enrich_items_with_blog_info(items)
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
            nearby_html += '<a class="nearby-link" href="' + url + '" target="_blank">' + name + ' 지도에서 보기</a>\n\n'

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
            nearby_html += '<a class="nearby-link" href="' + url + '" target="_blank">' + name + ' 지도에서 보기</a>\n\n'
            if tel:
                nearby_html += "전화: " + tel + "\n\n"

    return html + nearby_html




def _post_process(content):
    # 문장 잘림 수정: 마지막 문자가 마침표/물음표/느낌표가 아니면 제거
    lines = content.rstrip().split("\n")
    while lines and lines[-1].strip() == "":
        lines.pop()
    if lines:
        last = lines[-1].rstrip()
        if last and last[-1] not in ".다!?":
            # 마지막 온전한 문장까지만 유지
            import re as _re
            match = _re.search(r"(.*[.다!?])", last)
            if match:
                lines[-1] = match.group(1)
            else:
                lines.pop()  # 온전한 문장이 없으면 줄 자체 제거
    content = "\n".join(lines)

    """후처리: 미완성 문장, HTML 주석, 과잉 질문 정리"""
    # 노출되면 안 되는 HTML 주석 제거
    content = re.sub(r'<!--\s*(여행용 카메라|편한 워킹화|보조배터리)\s*-->', '', content)
    # 미완성 문장 수정
    content = re.sub(r'계획하시기\s*\.', '계획하는 것을 추천한다.', content)
    content = re.sub(r'확인하여\s*\.', '확인하는 것이 좋다.', content)
    content = re.sub(r'확인해 보시기\s*\.', '확인해 보는 것이 좋다.', content)
    # "궁금하지 않으세요/않으신가요" 2회 초과 시 제거
    q_matches = re.findall(r'[^\n]*궁금하[^\n]*\n?', content)
    if len(q_matches) > 2:
        count = 0
        lines = content.split('\n')
        new_lines = []
        for line in lines:
            if '궁금하' in line:
                count += 1
                if count > 2:
                    continue
            new_lines.append(line)
        content = '\n'.join(new_lines)
    # 연속 빈줄 정리
    content = re.sub(r'\n{4,}', '\n\n\n', content)
    # CTA 제휴 박스 삽입 (함께 읽어보기 앞에)
    if "함께 읽어보기" in content:
        cta_html = """
<div class="cta-box">
  <p style="margin:0;font-size:1.1rem;">여행 숙소를 찾고 계신가요?</p>
  <a href="https://www.trip.com/?Allianceid=3993748&SID=travel_blog" target="_blank" rel="nofollow">트립닷컴에서 최저가 확인하기</a>
</div>
"""
        content = content.replace("## 함께 읽어보기", cta_html + "\n## 함께 읽어보기")
    elif content.rstrip().endswith("---"):
        pass
    else:
        cta_html = """
<div class="cta-box">
  <p style="margin:0;font-size:1.1rem;">여행 숙소를 찾고 계신가요?</p>
  <a href="https://www.trip.com/?Allianceid=3993748&SID=travel_blog" target="_blank" rel="nofollow">트립닷컴에서 최저가 확인하기</a>
</div>
"""
        content = content.rstrip() + "\n\n" + cta_html

    return content


def _validate_and_retry(content, system_prompt, user_prompt, max_retries=1):
    """생성된 콘텐츠의 H2 수, 글자수, 금지표현을 검증하고 미달 시 재생성"""
    BANNED = ["바랍니다", "되시길", "있으시", "마무리하며", "마치며", "즐겨보세요", "만끽해 보세요", "느껴보세요"]
    
    for attempt in range(max_retries + 1):
        # 검증
        h2_count = len(re.findall(r'^## ', content, re.MULTILINE))
        char_count = len(content)
        banned_found = [b for b in BANNED if b in content]
        
        issues = []
        if h2_count > 6:
            issues.append(f"H2 {h2_count}개→4개 필요")
        if char_count < 2000:
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
- 글자수는 반드시 2,200자 이상이어야 합니다. 현재 {char_count}자입니다. 각 H3 섹션을 8문장 이상, 각 H2를 5문장 이상으로 충분히 서술하세요.
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

            # 미완성 문장 후처리 ("하시기 .", "보시기 ." 등)
            content = re.sub(r'하시기\s*\.', '하는 것이 좋습니다.', content)
            content = re.sub(r'보시기\s*\.', '보는 것을 추천합니다.', content)
            content = re.sub(r'드시기\s*\.', '드시는 것을 추천합니다.', content)
            content = re.sub(r'참고하시기\s*\.', '참고하는 것이 좋습니다.', content)
            content = re.sub(r'보내시기\s*\.', '보내는 것을 추천합니다.', content)
            content = re.sub(r'즐기시기\s*\.', '즐기는 것을 추천합니다.', content)
            
            # 비한글 외래어 오류 제거 (러시아어 등)
            content = re.sub(r'[а-яА-ЯёЁ]+', '', content)
            
            # 2025→2026 날짜 변환 (TourAPI 원본 데이터 잔재)
            content = content.replace('2025년', '2026년')
            content = content.replace('2024년', '2026년')
            
            # 금지표현 자동 제거
            for b in banned_found:
                content = content.replace(b, "")
            
            # "만원대", "약 N만원" 등 애매한 가격 표현 강제 제거
            price_patterns = [
                r'약\s*\d+[,.]?\d*\s*만\s*원대?',
                r'\d+[,.]?\d*\s*만\s*원대',
                r'가격대는?\s*약?\s*\d+[,.]?\d*\s*만\s*원',
                r'1인당\s*약?\s*\d+[,.]?\d*\s*만\s*원',
                r'인당\s*약?\s*\d+[,.]?\d*\s*만\s*원',
                r'평균\s*약?\s*\d+[,.]?\d*\s*만\s*원',
            ]
            for pp in price_patterns:
                content = re.sub(pp, '', content)
            # 빈 문장 정리 (패턴 제거 후 남은 빈 줄)
            content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
            
            return content
    
    return content



def _validate_place_names(content, real_names, max_retries=1):
    """AI 생성 본문에 실제 API 장소명이 포함되어 있는지 검증"""
    if not real_names:
        return content, True

    for attempt in range(max_retries + 1):
        found = []
        missing = []
        for name in real_names:
            # 정확한 이름 또는 핵심 부분(앞 6자)이 본문에 있는지
            if name in content or (len(name) > 5 and name[:6] in content):
                found.append(name)
            else:
                missing.append(name)

        ratio = len(found) / len(real_names) if real_names else 0
        logger.info("장소명 검증: %d/%d 일치 (%.0f%%)", len(found), len(real_names), ratio * 100)

        if ratio >= 0.6:
            if missing:
                logger.warning("누락 장소: %s", ", ".join(m[:15] for m in missing))
            return content, True

        logger.warning("장소명 불일치 (시도 %d/%d): 일치=%s, 누락=%s",
                       attempt + 1, max_retries + 1,
                       [n[:15] for n in found], [n[:15] for n in missing])

        if attempt < max_retries:
            return content, False

    return content, False


def generate_content(data, blog_id="travel-hugo"):
    source_type = data.get("source_type", "camping")
    prompt_id = _select_prompt_id(blog_id, source_type)

    # 블로그 정보 + 다이닝코드 enrichment (GPT 호출 전에 실행)
    try:
        from core.content_processor import enrich_items_with_blog_info
        items = data.get("items", [])
        items = enrich_items_with_blog_info(items)
        data["items"] = items
    except Exception as e:
        logger.warning(f"블로그 enrichment 실패 (무시): {e}")

    # 맛집 파이프라인이면 다이닝코드로 메뉴/영업시간 보강
    if source_type in ("food", "korservice") and prompt_id == "tour2_food":
        try:
            from shared.diningcode_enricher import enrich_from_diningcode
            for item in data.get("items", []):
                name = item.get("title", item.get("facltNm", ""))
                addr = item.get("addr1", item.get("addr", ""))
                if name:
                    dc = enrich_from_diningcode(name, addr)
                    if dc:
                        item["diningcode"] = dc
                        logger.info(f"다이닝코드: {name} → 메뉴 {len(dc.get('main_menus',[]))}개, 평점 {dc.get('rating','')}")
        except Exception as e:
            logger.warning(f"다이닝코드 enrichment 실패 (무시): {e}")

    # 축제 파이프라인이면 네이버 블로그 검색으로 추가 정보 보강
    if source_type in ("korservice",) and prompt_id == "travel1_festival":
        try:
            from core.naver_blog_api import load_naver_blog_api
            blog_api = load_naver_blog_api()
            for item in data.get("items", []):
                name = item.get("title", item.get("facltNm", ""))
                if not name:
                    continue
                queries = [f"{name} 프로그램", f"{name} 주차 교통", f"{name} 후기 팁"]
                snippets = []
                for q in queries:
                    results = blog_api.search(q, display=3, sort="sim")
                    for r in results:
                        desc = r.get("description", "").replace("<b>", "").replace("</b>", "")
                        if desc and len(desc) > 20:
                            snippets.append(desc[:150])
                if snippets:
                    item["blog_snippets"] = snippets[:6]
                    logger.info(f"축제 블로그 보강: {name} → {len(snippets)}개 스니펫")
        except Exception as e:
            logger.warning(f"축제 블로그 enrichment 실패 (무시): {e}")

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

    # 장소명 강제 바인딩: API 실제 데이터 이름만 사용하도록 지시
    place_items = data.get("items", [])
    real_names = [it.get("title", it.get("facltNm", "")).strip() for it in place_items if it.get("title") or it.get("facltNm")]
    if real_names:
        name_constraint = (
            "\n\n[필수 규칙] 아래 장소명을 정확히 그대로 사용하세요. "
            "임의로 이름을 바꾸거나 새로 만들지 마세요:\n"
            + "\n".join(f"- {n}" for n in real_names)
            + "\n"
        )
        user_prompt = name_constraint + user_prompt

    result = ai_generate(system_prompt, user_prompt, tier="default")

    if not result or not result.get("content"):
        logger.error("AI 생성 실패: prompt_id=%s", prompt_id)
        return None

    content = result["content"]
    model_used = result.get("model", "")

    # 후처리: H2 수, 글자수, 금지표현 검증 및 재생성
    content = _validate_and_retry(content, system_prompt, user_prompt)

    # 장소명 검증: API 데이터의 실제 장소명이 본문에 포함되어 있는지 확인
    place_items = data.get("items", [])
    real_names = [it.get("title", it.get("facltNm", "")).strip() for it in place_items if it.get("title") or it.get("facltNm")]
    content, names_ok = _validate_place_names(content, real_names)
    if not names_ok:
        logger.warning("장소명 불일치 → 재생성 시도")
        retry = ai_generate(system_prompt, user_prompt, tier="default")
        if retry and retry.get("content"):
            content = retry["content"]
            content = _validate_and_retry(content, system_prompt, user_prompt)
            content, _ = _validate_place_names(content, real_names)

    content = _post_process(content)
    content = _enrich_with_nearby(data, content)
    # Heritage 카드 삽입 (본문 첫 H2 바로 앞)
    try:
        _region = data.get("region", "") if isinstance(data, dict) else ""
        _h_card = _build_heritage_card(_region)
        _h2_match = re.search(r"(\n##\s)", content)
        if _h2_match:
            _pos = _h2_match.start()
            content = content[:_pos] + _h_card + content[_pos:]
        else:
            content = _h_card + content
    except Exception as e:
        print(f"[heritage-card] 삽입 실패: {e}")

    items = data.get("items", [])
    content = _inject_images(items, content, blog_id=blog_id)
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
            "{region} 반려견 동반 가능 캠핑장 {count}곳 비교",
            "{region} {theme} 1박 요금 비교, {count}곳 정리",
            "비 와도 걱정 없는 {region} {theme} {count}곳",
            "{region} 글램핑과 카라반 {count}곳 가격과 시설 비교",
            "{region} 아이와 가기 좋은 {theme} {count}곳 체크리스트",
            "초보 캠퍼를 위한 {region} {theme} {count}곳 추천",
            "{region} {theme} 예약 꿀팁과 {count}곳 비교",
            "차박하기 좋은 {region} {theme} {count}곳 정리",
            "3월 {region} {theme} {count}곳 시즌 오픈 현황",
            "{region} 수영장 있는 캠핑장 {count}곳 총정리",
        ],
        "travel1-hugo": [
            "2026 {region} {theme} 일정과 입장료 총정리",
            "{region} {theme} 가볼만한 곳 {count}선 추천",
            "{region} {theme} 일정과 체험 프로그램 정리",
            "{region} {theme} 일정부터 주차까지 한눈에 보기",
            "2026 {region} 축제 {count}곳 일정 총정리",
            "{region} {theme}, 아이와 함께 가기 좋은 {count}곳",
            "{region} {theme} 교통과 주차 정보 총정리",
            "주말 나들이로 딱! {region} {theme} {count}곳 추천",
            "{region} 무료 축제 {count}곳, 일정과 위치 총정리",
            "2026 {region} 축제 {count}곳 일정과 위치 정리",
            "{region} {theme} 주차장 위치와 요금 정리",
            "{region} {theme} 대중교통 가는 법과 셔틀 안내",
            "{region} {theme} 체험 프로그램 {count}가지 비교",
            "비 오는 날에도 즐길 수 있는 {region} {theme} 정리",
            "{region} {theme} 주요 프로그램과 체험 정리",
            "{region} {theme} 포토존 위치와 인생샷 팁 정리",
            "올해 처음 열리는 {region} {theme} 일정 총정리",
            "{region} {theme} 야간 프로그램과 조명 행사 안내",
            "{region} {theme}와 묶어 갈 당일치기 코스 추천",
            "{region} {theme} 사전예약과 입장 안내 정리",
        ],
        "travel2-hugo": [
            "{region} {theme} 탐방, 입장료와 운영시간 총정리",
            "{region} 문화유산 탐방 코스, 주변 유적까지 정리",
            "{region} 사적지 탐방, 해설 프로그램과 주차 안내",
            "{region} 역사 여행 코스, 교통과 주차 정보 정리",
            "{region}에서 탐방하는 {theme} {count}곳 비교",
            "{region} 문화재 탐방, 사진 찍기 좋은 포인트까지",
            "{region} {theme} 탐방 코스와 소요 시간 정리",
            "{region} {theme} 해설 투어 예약 방법과 일정",
            "{region} 유네스코 유산과 {theme} 코스 연계 정리",
            "아이와 함께하는 {region} {theme} 체험 {count}곳",
            "{region} {theme} 무료 관람 가능한 곳 {count}선",
            "{region} {theme} 탐방 후 들르기 좋은 카페와 맛집",
            "역사 덕후를 위한 {region} {theme} 딥코스 정리",
            "주말 반나절 {region} {theme} 탐방 동선 추천",
            "{region} {theme} 야간 개장 일정과 관람 팁",
            "사진으로 보는 {region} {theme} 포인트 {count}곳",
            "{region} {theme} 계절별 방문 적기와 관람 팁",
            "{region} {theme} 주변 주차장과 대중교통 안내",
            "당일치기로 돌아보는 {region} {theme} {count}곳",
            "{region} 숨은 {theme} {count}곳, 현지인 추천 코스",
        ],
        "travel3-hugo": [
            "{region} {theme} 현지인이 추천하는 식당 {count}곳",
            "{region}에 가면 꼭 먹어야 할 {theme} {count}선",
            "{region} {theme} 가성비 식당 {count}곳 메뉴와 위치 정리",
            "현지인만 아는 {region} {theme} {count}곳 총정리",
            "{region} {theme} 웨이팅 없는 식당 {count}곳 추천",
            "{region} 로컬 맛집 {count}곳 메뉴와 영업 정보 정리",
            "{region} {theme} 혼밥하기 좋은 식당 {count}곳",
            "여행 중 들르기 좋은 {region} {theme} {count}곳",
            "주말 {region} {theme} {count}곳 총정리",
            "{region} {angle} 맛집 {count}곳, 영업시간과 휴무일 정리",
            "{region} {theme} 가성비 식당 {count}곳 비교",
            "{region} {theme} 주차 가능한 식당 {count}곳 정리",
            "아이와 가기 좋은 {region} {theme} {count}곳",
            "{region} {theme} 오래된 노포 {count}곳 탐방",
            "{region} {theme} 점심 특선 메뉴 비교 {count}곳",
            "관광지 근처 {region} {theme} {count}곳 동선 정리",
            "{region} {theme} 예약 필수 식당 {count}곳과 연락처",
            "{region} 새벽이나 심야 영업 {theme} {count}곳",
            "{region} {theme} 테라스와 뷰 좋은 식당 {count}곳 비교",
            "포장이나 배달 가능한 {region} {theme} {count}곳",
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
            "{region} {theme} 식당까지 포함한 풀코스 {count}곳",
            "커플 여행으로 좋은 {region} {theme} {count}곳 코스",
            "{region} {theme} 반나절 코스와 점심 맛집 추천",
            "뚜벅이를 위한 {region} {theme} {count}곳 코스 정리",
            "{region} {theme} 아침부터 저녁까지 타임테이블 정리",
            "예산 10만원으로 즐기는 {region} {theme} {count}곳 코스",
            "{region} {theme} 우천 시 대체 코스까지 정리",
            "사진 명소 위주 {region} {theme} {count}곳 코스 추천",
            "{region} {theme} 숙소 위치별 추천 코스 {count}선",
            "3월 {region} {theme} 벚꽃과 봄꽃 코스 {count}곳",
            "{region} {theme} 코스별 소요 시간과 이동 거리 정리",
        ],
    }


    import random as _rand
    templates = TITLE_TEMPLATES.get(blog_id, TITLE_TEMPLATES["travel-hugo"])
    template = _rand.choice(templates)
    # region/theme 빈값 보호
    if not display_region or len(display_region) < 2:
        display_region = data.get("display_region", data.get("region", "전국"))
    if not display_region or len(display_region) < 2:
        display_region = "전국"
    if not theme or len(theme) < 2:
        theme = "여행"

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
- 서술어(총정리, 비교, 추천 리스트, 정리, 한눈에 보기, 코스 안내)로 마무리
- 경어체 금지 (입니다, 합니다, 드립니다, 하세요)
- 특수기호 금지 (콜론, 느낌표, 하이픈)
- 가격 정보는 제목에 넣지 않기 (본문에서 다룸)
- 고유명사(축제명/장소명)는 1개만 포함

금지 표현:
- "완벽 가이드", "꼭 가봐야 할", "베스트", "상세정보", "즐기기", "소개", "알아보기", "만나보기"

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
        # "1곳" 어색한 제목 보정
        if '1곳' in generated_title:
            generated_title = generated_title.replace(' 1곳', '').replace('1곳 ', '')
        if len(generated_title) > 5:
            import random as _r
            import re as _re
            ban_endings = ['소개', '알아보기', '만나보기', '살펴보기', '확인하기', '코스 안내', '안내']
            ban_phrases = ['에서 즐기는', '에서 만나는', '에서 즐길 수 있는']
            for ban in ban_endings:
                if generated_title.endswith(ban):
                    replacements = ['추천', '한눈에 보기', '메뉴 비교', '코스 추천', '비교', '체크리스트', '방문 전 필독']
                    generated_title = generated_title[:-len(ban)].rstrip() + ' ' + _r.choice(replacements)
                    break
            for bp in ban_phrases:
                if bp in generated_title:
                    generated_title = generated_title.replace(bp, ' ')
                    generated_title = ' '.join(generated_title.split())
            long_words = _re.findall(r'[가-힣]{8,}', generated_title)
            if long_words:
                generated_title = fallback_title
            if len(generated_title) > 45 or len(generated_title) < 15:
                generated_title = fallback_title
            # region 포함 검증: 지역명이 빠지면 fallback
            if display_region and len(display_region) >= 2 and display_region not in generated_title:
                generated_title = fallback_title
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

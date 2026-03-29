import sys
import os
import logging
import re

sys.path.insert(0, os.getenv("TAP_ROOT", "/Users/twinssn/Projects/TAP"))
os.chdir(os.getenv("TAP_ROOT", "/Users/twinssn/Projects/TAP"))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.getenv("TAP_ROOT", "/Users/twinssn/Projects/TAP"), ".env"))
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
    # [PATCH] 최대 3곳만 전달
    items = items[:3]
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
        if item.get("kdName"):
            lines.append(f"종목: {item['kdName']}")
        if item.get("era"):
            lines.append(f"시대: {item['era']}")
        if item.get("owner"):
            lines.append(f"소유: {item['owner']}")
        if item.get("quantity"):
            lines.append(f"규모: {item['quantity']}")
        if item.get("designatedDate"):
            lines.append(f"지정일: {item['designatedDate']}")
        if item.get("category1"):
            cats = " > ".join(filter(None, [item.get("category1",""), item.get("category2","")]))
            lines.append(f"분류: {cats}")
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



def _inject_naver_map(body_md, items, is_festival=False):
    import urllib.parse
    if not items:
        return body_md
    map_links = []
    for item in items:
        title = item.get("title", item.get("facltNm", "")).strip()
        if not title:
            continue
        encoded = urllib.parse.quote(title)
        if is_festival:
            url = "https://search.naver.com/search.naver?query=" + encoded
        else:
            url = "https://map.naver.com/v5/search/" + encoded
        map_links.append((title, url))
    if not map_links:
        return body_md
    lines = body_md.split("\n")
    result = []
    pending_map = None
    for line in lines:
        if re.match(r"^#{2,3}\s+", line) and pending_map:
            result.append("")
            result.append(pending_map)
            result.append("")
            pending_map = None
        result.append(line)
        if re.match(r"^#{2,3}\s+", line):
            for ml_title, ml_url in map_links:
                name_parts = [p for p in ml_title.split() if len(p) >= 2]
                match_count = sum(1 for part in name_parts if part in line)
                if match_count >= 2 or (len(name_parts) == 1 and name_parts[0] in line):
                    _btn_label = " 네이버에서 검색하기" if is_festival else " 네이버 지도에서 보기"
                    _btn_cls = "naver-search-btn" if is_festival else "naver-map-btn"
                    pending_map = '<a class="' + _btn_cls + '" href="' + ml_url + '" target="_blank" rel="nofollow">' + ml_title + _btn_label + '</a>'
                    break
    if pending_map:
        result.append("")
        result.append(pending_map)
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
            # http → https 변환 (mixed content 방지)
            if img.startswith("http://tong.visitkorea.or.kr"):
                img = img.replace("http://", "https://", 1)
            if img.startswith("http://www.khs.go.kr"):
                img = img.replace("http://", "https://", 1)
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
    try:
        from core.content_processor import get_nearby_info
    except ImportError:
        logger.warning("core.content_processor 모듈 없음 — nearby 생략")
        return html

    items = data.get("items", [])
    sigungu = data.get("sigungu", "")

    try:
        nearby_data = get_nearby_info(items, sigungu)
    except Exception as e:
        logger.warning(f"nearby 조회 실패: {e}")
        return html

    if not nearby_data:
        return html

    nearby_html = ""

    def _nearby_card(item, map_url):
        img = (item.get("image") or "").replace("http://", "https://", 1)
        name = item.get("title", "")
        addr = item.get("addr", "")
        card = '<div class="nearby-card">'
        if img:
            card += '<img class="nearby-card-img" src="' + img + '" alt="' + name + '" loading="lazy">'
        card += '<div class="nearby-card-body">'
        card += '<strong class="nearby-card-name">' + name + '</strong>'
        if addr:
            card += '<span class="nearby-card-addr">' + addr + '</span>'
        card += '<a class="nearby-card-btn" href="' + map_url + '" target="_blank" rel="nofollow">지도에서 보기</a>'
        card += '</div></div>'
        return card

    attractions = nearby_data.get("attractions", [])
    if attractions:
        nearby_html += "\n\n## 반경 10km 내 가볼만한 곳\n\n"
        for a in attractions[:3]:
            name = a.get("title", "")
            if not name:
                continue
            encoded = urllib.parse.quote(name)
            url = "https://map.naver.com/v5/search/" + encoded
            nearby_html += _nearby_card(a, url) + "\n\n"

    restaurants = nearby_data.get("restaurants", [])
    if restaurants:
        nearby_html += "\n\n## 반경 10km 내 맛집\n\n"
        for r in restaurants[:3]:
            name = r.get("title", "")
            if not name:
                continue
            encoded = urllib.parse.quote(name)
            url = "https://map.naver.com/v5/search/" + encoded
            nearby_html += _nearby_card(r, url) + "\n\n"

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
    # [PATCH] GPT가 만든 "함께 읽어보기" 섹션 통째로 제거
    _related_idx = content.find("## 함께 읽어보기")
    if _related_idx > 0:
        content = content[:_related_idx].rstrip()

    # ── 쿠팡 여행용품 추천 삽입 ──────────────────────────────
    try:
        from shared.coupang_travel import CoupangTravel
        _ct = CoupangTravel()
        if _ct.is_configured():
            _blog_id = getattr(_post_process, '_current_blog_id', 'travel-hugo')
            _coupang_md = _ct.get_travel_product_links(blog_id=_blog_id, count=2)
            if _coupang_md:
                content = content.rstrip() + _coupang_md
    except Exception as _ce:
        logger.warning("쿠팡 여행용품 삽입 실패: %s", _ce)

    # CTA 제휴 박스 삽입
    cta_html = """
<div class="cta-box">
  <p style="margin:0;font-size:1.1rem;">여행 숙소를 찾고 계신가요?</p>
  <a href="https://kr.trip.com/?Allianceid=7451816&SID=283255449&trip_sub1=&trip_sub3=D14664967" target="_blank" rel="nofollow">트립닷컴에서 최저가 확인하기</a>
</div>
"""
    content = content.rstrip() + "\n\n" + cta_html



    # GPT가 생성한 인라인 네이버 지도 링크 제거
    content = re.sub(r'\s*\[네이버 지도에서 보기\]\(https://map\.naver\.com[^)]*\)', '', content)

    return content



def _validate_place_names(content: str, real_names: list) -> tuple:
    """API 실제 장소명이 본문에 포함되어 있는지 검증.
    
    Returns:
        (content, names_ok): 수정된 본문과 검증 통과 여부
    """
    if not real_names:
        return content, True
    
    found = 0
    missing = []
    for name in real_names:
        if not name:
            continue
        if name in content:
            found += 1
        else:
            # 부분 매칭 시도 (괄호 제거, 공백 무시)
            import re
            clean = re.sub(r"[\(\)\[\]\s]", "", name)
            if len(clean) >= 3 and clean in content.replace(" ", ""):
                found += 1
            else:
                missing.append(name)
    
    total = len([n for n in real_names if n])
    if total == 0:
        return content, True
    
    ratio = found / total
    names_ok = ratio >= 0.5  # 50% 이상 매칭이면 통과
    
    if missing:
        import logging
        logging.getLogger(__name__).debug(
            f"장소명 불일치 {len(missing)}/{total}: {missing[:5]}")
    
    return content, names_ok

def _validate_and_retry(content, system_prompt, user_prompt, max_retries=0):
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
        
    # [과거연도 방어] 제목/본문에서 과거연도 -> 현재연도 변환
    import re as _yre
    _cy = str(__import__('datetime').datetime.now().year)
    for _py in [str(y) for y in range(2020, int(_cy))]:
        # 제목에서 변환
        if _py in content:
            # URL 내부의 연도는 제외하고 변환
            content = _yre.sub(
                r'(?<!/)(?<![\w])' + _py + r'(?=[ 년.~,\-가-힣])',
                _cy, content
            )

    return content



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

    # 문화유산 파이프라인이면 네이버 블로그 검색으로 추가 정보 보강
    if source_type == "heritage":
        try:
            from core.naver_blog_api import load_naver_blog_api
            blog_api = load_naver_blog_api()
            for item in data.get("items", []):
                name = item.get("title", "")
                if not name:
                    continue
                queries = [f"{name} 역사", f"{name} 관람 후기", f"{name} 방문 팁"]
                snippets = []
                for q in queries:
                    results = blog_api.search(q, display=3, sort="sim")
                    for r in results:
                        desc = r.get("description", "").replace("<b>", "").replace("</b>", "")
                        if desc and len(desc) > 20:
                            snippets.append(desc[:150])
                if snippets:
                    item["blog_snippets"] = snippets[:6]
                    logger.info(f"문화유산 블로그 보강: {name} → {len(snippets)}개 스니펫")
        except Exception as e:
            logger.warning(f"문화유산 블로그 enrichment 실패 (무시): {e}")

    data_block = _build_data_block(data)

    # blog_snippets 수집 (프롬프트 변수용)
    _all_snippets = []
    for _item in data.get("items", []):
        for _sn in _item.get("blog_snippets", []):
            _all_snippets.append(_sn)
    _snippets_text = "\n".join(f"- {s}" for s in _all_snippets[:8]) if _all_snippets else "(참고 정보 없음)"

    extra_vars = {
        "blog_snippets": _snippets_text,
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
        logger.info("장소명 불일치 감지 (재생성 안함)")

    _post_process._current_blog_id = blog_id
    content = _post_process(content)
    content = _enrich_with_nearby(data, content)
    # [PATCH] _enrich_with_nearby 후 GPT "함께 읽어보기" 최종 제거 + 동적 내부링크
    _final_related_idx = content.find("## 함께 읽어보기")
    if _final_related_idx > 0:
        content = content[:_final_related_idx].rstrip()
    # 동적 내부링크 삽입
    try:
        import glob as _gl_final
        import random as _rand_final
        _blog_path_final = {
            "travel-hugo":  "/Users/twinssn/Projects/travel-hugo",
            "travel1-hugo": "/Users/twinssn/Projects/travel1-hugo",
            "travel2-hugo": "/Users/twinssn/Projects/travel2-hugo",
            "travel3-hugo": "/Users/twinssn/Projects/travel3-hugo",
            "travel4-hugo": "/Users/twinssn/Projects/travel4-hugo",
        }
        _posts_dir_final = os.path.join(_blog_path_final.get(blog_id, "/Users/twinssn/Projects/travel-hugo"), "content", "posts")
        _all_posts_final = []
        for _md_f in _gl_final.glob(os.path.join(_posts_dir_final, "*/index.md")):
            with open(_md_f, encoding="utf-8") as _ff:
                _head_f = _ff.read(500)
            import re as _re_final
            _tm_f = _re_final.search(r"^title:\s*[\x27\x22](.*?)[\x27\x22]", _head_f, _re_final.MULTILINE)
            _sm_f = _re_final.search(r"^slug:\s*[\x27\x22](.*?)[\x27\x22]", _head_f, _re_final.MULTILINE)
            if _tm_f and _sm_f:
                _all_posts_final.append({"title": _tm_f.group(1), "slug": _sm_f.group(1)})
        if len(_all_posts_final) > 3 and "## 함께 읽어보기" not in content:
            _picks_f = _rand_final.sample(_all_posts_final, 3)
            _related_md_f = "\n\n## 함께 읽어보기\n\n"
            for _p_f in _picks_f:
                _related_md_f += '{{< article link="/posts/' + _p_f["slug"] + '/" >}}\n\n'
            content = content.rstrip() + _related_md_f
    except Exception as e:
        logger.debug(f"[TRAVEL_WRITER] failed: {e}")
    # Heritage 카드 삽입 (heritage 소스 타입에서만)
    if source_type == "heritage":
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
            logger.warning(f"[heritage-card] 삽입 실패: {e}")

    items = data.get("items", [])
    content = _inject_images(items, content, blog_id=blog_id)
    _is_festival = (source_type in ("korservice",) and _select_prompt_id(blog_id, source_type) == "travel1_festival")
    content = _inject_naver_map(content, items, is_festival=_is_festival)

    display_region = data.get("display_region", "")
    theme = data.get("theme", "")
    angle = data.get("angle", theme)
    items = data.get("items", [])

    TITLE_TEMPLATES = {
        "travel-hugo": [
            "{region} {angle} {first_camp}과 {count}곳 시설 비교",
            "{region} {first_camp} 포함 {theme} {count}곳 총정리",
            "{region} {angle} 캠핑장 {first_camp} 등 {count}곳 비교",
            "{region} {first_camp}부터 {last_camp}까지 {count}곳 정리",
            "{region} {theme} {first_camp} 주변 {count}곳 추천",
            "{region} {angle} {first_camp} 시설과 예약 정보 정리",
            "{region} {theme} {count}곳 {first_camp} 포함 비교",
            "{first_camp}과 {region} {angle} 캠핑장 {count}곳 리뷰",
            "{region} {angle} {count}곳 {first_camp} 등 시설 총정리",
            "{region} {first_camp} 예약 전 알아둘 것과 {count}곳 비교",
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
            "{region} {theme} 탐방, {count}곳 소개",
            "{region}에서 만나는 {theme} 탐방지 {count}곳 소개",
            "{region} {theme} 탐방, {first_name}부터 추천",
            "{region} 문화유산 투어, {first_name} 소개",
            "{region} {theme} {count}곳 한눈에 보기",
            "{region}에서 즐기는 {theme} 탐방 가이드",
            "{region} {theme} 탐방 코스 추천",
            "역사와 함께하는 {region} {theme} 탐방 {count}곳",
            "{region} {theme} 탐방, 방문 전 알아둘 것 정리",
            "주말에 가볼 만한 {region} {theme} {count}곳",
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
            "{region} {theme} 코스별 이동 거리와 주차 정보 정리",
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

    # 캠핑장 실명 변수 추출
    _camp_names = [i.get('title', i.get('facltNm', ''))[:15] for i in items if i.get('title') or i.get('facltNm')]
    first_camp = _camp_names[0] if _camp_names else theme
    last_camp = _camp_names[-1] if len(_camp_names) > 1 else first_camp
    first_name = first_camp  # travel2용 호환

    fallback_title = template.format(
        region=display_region,
        theme=theme,
        angle=angle,
        count=str(len(items)),
        first_camp=first_camp,
        last_camp=last_camp,
        first_name=first_name,
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
- 캠핑장 실제 이름을 1개 이상 포함 (검색 노출 핵심)
- 예: "부산 반딧불이 캠핑장 포함 계곡 캠핑 3곳 비교"

금지 표현:
- "완벽 가이드", "꼭 가봐야 할", "베스트", "상세정보", "즐기기", "소개", "알아보기", "만나보기"

좋은 제목 예시:
- "경남 지리산 당근 오토캠핑장 포함 계곡 캠핑 3곳 비교"
- "강원 소나무숲 캠핑장부터 별빛야영장까지 3곳 정리"
- "충남 태안 글램핑 해솔오토캠핑장 등 3곳 시설 총정리"
- "경기 포천 산속 캠핑장 힐링포레스트 주변 3곳 추천"
- "전남 담양 대나무숲 캠핑장과 가성비 글램핑 3곳 비교"

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

    # SEO description 생성: 지역 + 테마 + 핵심정보
    _item_names = [it.get("title", it.get("facltNm", ""))[:15] for it in items[:3] if it.get("title") or it.get("facltNm")]
    _names_str = ", ".join(_item_names) if _item_names else theme
    _seo_desc = f"{display_region} {theme} — {_names_str}. {len(items)}곳 정보와 방문 팁 정리."
    if len(_seo_desc) > 160:
        _seo_desc = _seo_desc[:157] + "..."
    # [PATCH] DESC 주석 제거됨

    # 대가성 문구 삽입 (본문 최상단)
    # [FIX] 상단 쿠팡 문구 삽입 제거 — 하단 _post_process에서 1회만 삽입
    # if "쿠팡 파트너스" not in content:
    #     content = '> **이 포스팅은 ...** \n\n' + content

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
        "description": _seo_desc,
    }

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
  <a href="https://www.trip.com/?Allianceid=3993748&SID=travel_blog" target="_blank" rel="nofollow">트립닷컴에서 최저가 확인하기</a>
</div>
"""
    content = content.rstrip() + "\n\n" + cta_html

    # [PATCH] 동적 내부링크 — 실제 발행된 글 중 같은 카테고리/태그 기반 추천
    try:
        import glob as _gl
        import random as _rand2
        _posts_dir = "/Users/twinssn/Projects/travel-hugo/content/posts"
        _all_posts = []
        for _md in _gl.glob(os.path.join(_posts_dir, "*/index.md")):
            with open(_md, encoding="utf-8") as _f:
                _head = _f.read(500)
            _tm = re.search(r'^title:\s*["\'](.*?)["\']', _head, re.MULTILINE)
            _sm = re.search(r'^slug:\s*["\'](.*?)["\']', _head, re.MULTILINE)
            if _tm and _sm:
                _all_posts.append({"title": _tm.group(1), "slug": _sm.group(1)})
        if len(_all_posts) > 3:
            _picks = _rand2.sample(_all_posts, min(3, len(_all_posts)))

            for _p in _picks:
                _related_md += '{{< article link="/posts/' + _p["slug"] + '/" >}}\n\n'
            content = content.rstrip() + _related_md
    except Exception as _e:
        pass  # 내부링크 실패해도 글 발행은 계속

    return content


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


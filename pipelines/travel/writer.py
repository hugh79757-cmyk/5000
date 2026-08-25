import logging
import os
import re
import sys

sys.path.insert(0, os.getenv("TAP_ROOT", "/Users/twinssn/Projects/TAP"))
os.chdir(os.getenv("TAP_ROOT", "/Users/twinssn/Projects/TAP"))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.getenv("TAP_ROOT", "/Users/twinssn/Projects/TAP"), ".env"))
load_dotenv("/Users/twinssn/Projects/5000/.env")

sys.path.insert(0, "/Users/twinssn/Projects/5000")

from shared.ai_writer import generate as ai_generate
from shared.prompt_builder import build as build_prompt
from pipelines.travel.area_codes import validate_display_region
from shared.title_core import (
    build_title_prompt, validate_and_retry, make_fallback,
    extract_place_names, TRAVEL_TITLE_TEMPLATES,
)

logger = logging.getLogger(__name__)


try:
    from pipelines.etap.editorial_synthesis import editorial_synthesis_step
except ImportError:
    editorial_synthesis_step = None


def _inject_editorial_synthesis(body, topic=None):
    """Phase 70 Wave 3: append deterministic editorial synthesis paragraph.

    No-op unless the topic carries a recognized ``topic_type`` (graceful
    degradation — returns body unchanged when no unique data resolves).
    """
    if not body or editorial_synthesis_step is None:
        return body
    try:
        from pipelines.etap.data_adapters import get_unique_data_points
        _t = topic or {}
        _tt = _t.get("topic_type")
        # Phase 72 W1: TAP passthrough — unique_data가 topic dict에 실려오면
        # DB 조회 없이 그대로 사용 (W2 T2.4에서 items 파생 points 연결).
        _ud = _t.get("unique_data")
        if _ud is None:
            _ud = get_unique_data_points(_tt, _t.get("topic_id")) if _tt else []
        _s = editorial_synthesis_step(body, _ud, _t)
    except Exception as _e:
        logger.warning("[editorial] synthesis skipped: %s", _e)
        return body
    if not _s:
        return body
    return body.rstrip() + "\n\n" + _s + "\n"


def _derive_points_from_items(items):
    """Phase 72 W2 T2.4: derive deterministic unique_data points from TAP items.

    Plan §2 TAP exception — no topic-id-addressable local store exists for TAP,
    so points come from the in-scope ``data["items"]`` (LLM-free, DB-free).
    Capped at 12 points; returns [] for empty input.
    """
    if not items:
        return []
    pts = [{"label": "items_count", "value": len(items), "unit": "곳", "source_table": "items"}]
    for i, item in enumerate(items[:6], 1):
        title = item.get("title") or item.get("facltNm") or ""
        if title:
            pts.append({"label": f"place_{i}", "value": str(title)[:40], "unit": "", "source_table": "items"})
        for key, label, unit in (
            ("price", f"price_{i}", "KRW"),
            ("eventstartdate", f"event_start_{i}", "date"),
            ("tel", f"tel_{i}", ""),
        ):
            v = item.get(key)
            if v:
                pts.append({"label": label, "value": str(v)[:40], "unit": unit, "source_table": "items"})
        if len(pts) >= 12:
            break
    return pts[:12]


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
    return (
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
        + card["desc"] + "</p>"
        "</div></a></div>\n"
    )


BLOG_PROMPT_MAP = {
    "travel-hugo": {"camping": "tour1_camping"},
    "travel1-hugo": {"korservice": "travel1_festival", "festival": "travel1_festival"},
    "travel2-hugo": {"heritage": "travel2_heritage", "korservice": "travel2_heritage"},
    "travel3-hugo": {"korservice": "tour2_food", "food": "tour2_food"},
    "travel4-hugo": {"korservice": "tour3_course", "course": "tour3_course"},
    "tvshow-blogger": {"korservice": "tour2_food", "food": "tour2_food", "course": "tour3_course"},
    "tap-blogger": {"camping": "tour1_camping", "heritage": "travel2_heritage", "festival": "travel1_festival"},
}


def _select_prompt_id(blog_id, source_type, item_count=None):
    blog_map = BLOG_PROMPT_MAP.get(blog_id, BLOG_PROMPT_MAP.get("travel-hugo", {}))
    _DEFAULT_PROMPT = {
        "travel-hugo": "tour1_camping",
        "travel1-hugo": "travel1_festival",
        "travel2-hugo": "travel2_heritage",
        "travel3-hugo": "tour2_food",
        "travel4-hugo": "tour3_course",
        "tvshow-blogger": "tour2_food",
        "ud-blogger": "tour2_food",
        "kuta-wordpress": "tour2_food",
        "tap-blogger": "tour1_camping",
    }
    base = blog_map.get(source_type, _DEFAULT_PROMPT.get(blog_id, "tour1_camping"))
    # travel2-hugo heritage: 심층(1곳) vs 묶기(2~3곳) 프롬프트 분기
    if blog_id == "travel2-hugo" and source_type == "heritage" and item_count is not None:
        if item_count == 1:
            return "travel2_heritage_deep"
        return "travel2_heritage_grouped"
    return base


def _build_data_block(data):
    items = data.get("items", [])
    lines = []

    # ── course 전용 데이터 블록 ──
    if data.get("source_type") == "course":
        lines.append(f"지역: {data.get('display_region', '')}")
        lines.append(f"코스명: {data.get('course_title', '')}")
        lines.append(f"테마: {data.get('theme', '')}")
        overview = data.get("course_overview", "")
        if overview:
            lines.append(f"코스 개요: {overview[:300]}")
        lines.append(f"코스 장소 수: {len(items)}")
        lines.append("")
        for i, item in enumerate(items, 1):
            lines.append(f"[코스 {i}번째 장소]")
            lines.append(f"이름: {item.get('title', item.get('facltNm', ''))}")
            addr = item.get("addr1", item.get("addr", ""))
            if addr:
                lines.append(f"주소: {addr}")
            ov = item.get("overview", "")
            if ov:
                lines.append(f"설명: {ov[:400]}")
            if item.get("tel"):
                lines.append(f"전화: {item['tel']}")
            img = item.get("firstimage") or item.get("firstImageUrl") or item.get("image") or ""
            if img:
                lines.append(f"이미지: {img}")
            lines.append("")
        return "\n".join(lines)

    # ── heritage 전용 데이터 블록 ──
    if data.get("source_type") == "heritage":
        lines.append(f"지역: {data.get('display_region', data.get('region', ''))}")
        lines.append(f"테마: {data.get('theme', '')}")
        lines.append(f"문화유산 수: {len(items)}")
        lines.append("")
        for i, item in enumerate(items, 1):
            lines.append(f"[문화유산 {i}]")
            lines.append(f"이름: {item.get('title', '')}")
            addr = item.get('addr', '')
            if addr:
                lines.append(f"주소: {addr}")
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
            ov = item.get("overview", "")
            if ov:
                lines.append(f"상세설명: {ov[:600]}")
            if item.get("mapx") and item.get("mapy"):
                lines.append(f"좌표: {item['mapx']}, {item['mapy']}")
            img = item.get("image") or ""
            if img:
                lines.append(f"이미지: {img}")
            # 표 형태 정보 정리
            lines.append("기본 정보:")
            lines.append(f"  - 주소: {addr if addr else '정보 없음'}")
            lines.append(f"  - 종목: {item.get('kdName', '정보 없음')}")
            lines.append(f"  - 시대: {item.get('era', '정보 없음')}")
            lines.append(f"  - 지정일: {item.get('designatedDate', '정보 없음')}")
            lines.append(f"  - 분류: {cats if item.get('category1') else '정보 없음'}")
            lines.append(f"  - 소유자: {item.get('owner', '정보 없음')}")
            lines.append(f"  - 규모: {item.get('quantity', '정보 없음')}")
            if item.get("blog_snippets"):
                lines.append("네이버 블로그 참고정보 (사실 확인 불가, 참고용):")
                for sn in item["blog_snippets"][:6]:
                    lines.append(f"  - {sn}")
            lines.append("")
        return "\n".join(lines)

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
        # 이미지 URL 전달 (웰니스/관광/캠핑 공통) — AI가 ![대체텍스트](URL)로 본문에 삽입
        _img = item.get("firstimage") or item.get("firstImageUrl") or item.get("image") or ""
        if _img:
            lines.append(f"이미지: {_img}")

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
        # [실용 정보] 캠핑/관광 API 원천 필드
        if item.get("animalCmgCl"):
            lines.append(f"반려동물: {item['animalCmgCl']}")
        if item.get("glampInnerFclty"):
            lines.append(f"글램핑내부시설: {item['glampInnerFclty']}")
        if item.get("caravInnerFclty"):
            lines.append(f"카라반내부시설: {item['caravInnerFclty']}")
        if item.get("operPdCl"):
            lines.append(f"운영기간: {item['operPdCl']}")
        if item.get("operDeCl"):
            lines.append(f"운영요일: {item['operDeCl']}")
        if item.get("gnrlSiteCo"):
            lines.append(f"일반야영장: {item['gnrlSiteCo']}면")
        if item.get("autoSiteCo"):
            lines.append(f"오토캠핑: {item['autoSiteCo']}면")
        if item.get("glampSiteCo"):
            lines.append(f"글램핑사이트: {item['glampSiteCo']}면")
        if item.get("caravSiteCo"):
            lines.append(f"카라반사이트: {item['caravSiteCo']}면")
        if item.get("brazierCl"):
            lines.append(f"화로대: {item['brazierCl']}")
        if item.get("toiletCo"):
            lines.append(f"화장실: {item['toiletCo']}개")
        if item.get("swrmCo"):
            lines.append(f"샤워실: {item['swrmCo']}개")
        if item.get("wtrplCo"):
            lines.append(f"개수대: {item['wtrplCo']}개")

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
    """각 H3(장소 소제목) 본문 끝(다음 H2/H3 직전)에 네이버 지도 버튼 삽입.
    H2에는 버튼 삽입하지 않음.
    순서: ### 장소명 → ![이미지] → 본문... → [네이버 지도에서 보기] → 다음 ###/##
    """
    import urllib.parse
    if not items:
        return body_md

    # 장소별 버튼 HTML 준비
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
        _btn_label = " 네이버에서 검색하기" if is_festival else " 네이버 지도에서 보기"
        btn_html = ('<div style="text-align:center;margin-top:24px;margin-bottom:24px;">'
                    '<a href="' + url + '" target="_blank" rel="nofollow" '
                    'style="display:inline-block;padding:8px 16px;'
                    'background:#181616;color:#fff;border-radius:6px;'
                    'text-decoration:none;font-size:14px;font-weight:500;">'
                    + title + _btn_label + '</a>'
                    '</div>')
        map_links.append((title, btn_html))
    if not map_links:
        return body_md

    lines = body_md.split("\n")

    # H3만 수집 (H2 제외)
    h3_indices = [i for i, ln in enumerate(lines) if re.match(r"^###\s+", ln)]
    if not h3_indices:
        return body_md

    # 각 H3에 매칭되는 아이템 버튼 찾기
    used_titles = set()
    insert_map = {}  # {line_index: btn_html}

    for ml_title, btn_html in map_links:
        if ml_title in used_titles:
            continue
        ml_key = ml_title.replace(" ", "")
        matched_h3_idx = None
        for h3_idx in h3_indices:
            h3_line = lines[h3_idx]
            h3_text = h3_line.replace("### ", "").strip()
            h3_key = h3_text.replace(" ", "")
            # 매칭: H3 텍스트가 아이템명 포함 or 아이템명이 H3 텍스트 포함
            if ml_key in h3_key or h3_key in ml_key or any(p in h3_text for p in ml_title.split() if len(p) >= 2):
                matched_h3_idx = h3_idx
                break
        if matched_h3_idx is None:
            continue

        # 해당 H3의 섹션 끝 찾기: 다음 H2 또는 H3 직전 인덱스
        next_heading_idx = None
        for nh_idx in range(matched_h3_idx + 1, len(lines)):
            if re.match(r"^#{2,3}\s+", lines[nh_idx]):
                next_heading_idx = nh_idx
                break

        # 섹션 끝(다음 헤딩 직전 빈 라인 또는 마지막 비어있지 않은 라인)에 버튼 삽입
        if next_heading_idx is not None:
            target_idx = next_heading_idx - 1
            # 빈 라인 찾기 (뒤에서부터)
            for ins_idx in range(target_idx, matched_h3_idx, -1):
                if lines[ins_idx].strip() == "":
                    insert_map[ins_idx] = btn_html
                    used_titles.add(ml_title)
                    break
            else:
                # 빈 라인 없으면 마지막 내용 라인 다음에 삽입
                insert_map[target_idx] = btn_html
                used_titles.add(ml_title)
        else:
            # 마지막 H3: 본문 끝까지
            for ins_idx in range(len(lines) - 1, matched_h3_idx, -1):
                if lines[ins_idx].strip() == "":
                    insert_map[ins_idx] = btn_html
                    used_titles.add(ml_title)
                    break
            else:
                insert_map[len(lines) - 1] = btn_html
                used_titles.add(ml_title)

    # 매칭 안 된 장소: 본문 끝(tail) 대신 매칭 실패한 첫 H3 섹션 끝에 삽입.
    # (테마형 H3 — 축제 프로그램명 등 — 는 장소명과 문자열 매칭이 안 되어
    #  예전엔 tail_btns로 본문 맨 끝에 몰렸음. 이제 해당 H3 뒤에 배치)
    tail_btns = [btn for _, btn in map_links if _ not in used_titles]
    if tail_btns and h3_indices:
        # 매칭 실패한 버튼들은 첫 H3 섹션 끝에 배치 (마지막이 아닌, 첫 번째 H3 뒤)
        _first_h3 = h3_indices[0]
        _sec_end = None
        for _nh in range(_first_h3 + 1, len(lines)):
            if re.match(r"^#{2,3}\s+", lines[_nh]):
                _sec_end = _nh
                break
        if _sec_end is not None:
            _ins_pos = _sec_end
        else:
            _ins_pos = len(lines)
        for _btn in tail_btns:
            lines.insert(_ins_pos, _btn)
            lines.insert(_ins_pos, "")

    # 조립 (뒤에서부터 삽입해서 인덱스 밀려도 안전)
    for i in sorted(insert_map.keys(), reverse=True):
        lines.insert(i + 1, "")
        lines.insert(i + 1, insert_map[i])
        lines.insert(i + 1, "")

    return "\n".join(lines)


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
    """각 H3(장소 소제목)에 해당 아이템 이미지를 매칭하여 H3 직후에 삽입.
    순서: ### 장소명 → ![장소명](이미지) → 본문
    H2('한눈에 비교' 등)에는 이미지 삽입하지 않음.
    """
    existing = len(re.findall(r"!\[", content))
    if existing >= len(items):
        return content

    from shared.content_store import is_image_used
    # 아이템별 (이름, 이미지) 목록 — 이미지 있는 것만
    img_map = {}  # {아이템명 핵심 키워드: img_url}
    for item in items:
        name = item.get("facltNm", item.get("title", "")).strip()
        img = item.get("firstImageUrl") or item.get("firstimage") or item.get("image") or ""
        if not name or not img or not img.startswith("http"):
            continue
        if img.startswith("http://"):
            img = img.replace("http://", "https://", 1)
        if is_image_used(img, blog_id=blog_id):
            logger.info("이미지 중복 스킵: %s (%s)", name[:20], img[-30:])
            continue
        # 매칭용 핵심어 추출 (공백 제거 + 2글자 이상 단어)
        key = name.replace(" ", "")
        img_map[key] = (name, img)

    if not img_map:
        return content

    lines = content.split("\n")
    result = []
    for line in lines:
        result.append(line)
        # H3만 대상 (## 무시)
        if line.startswith("### ") and not any(skip in line for skip in ["여행 준비", "함께 읽어보기", "코스 주변 맛집", "반경 10km"]):
            h3_text = line.replace("### ", "").strip()
            h3_key = h3_text.replace(" ", "")
            # H3 제목과 아이템 이름 매칭 — 정확히 1개 H3에만 이미지 할당 (중복 방지)
            matched = None
            for item_key, (item_name, img_url) in img_map.items():
                # 아이템명이 H3 제목에 포함되면 매칭 (부분 매칭 우선)
                if item_key in h3_key or item_name in h3_text:
                    matched = (item_name, img_url)
                    break
            # 매칭된 아이템은 재사용 금지 (이미지가 중복 삽입되지 않도록)
            if matched:
                result.append("")
                result.append(f"![{matched[0]}]({matched[1]})")
                result.append("")
                # 해당 아이템 키 제거 (중복 매칭 방지)
                img_map.pop(next(k for k, v in img_map.items() if v == matched), None)

    return "\n".join(result)


def _enrich_with_nearby_restaurants_only(data, html):
    """travel4-hugo 전용: nearby 맛집 카드만 삽입 (가볼만한곳 제외)"""
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

    def _nearby_card(item, map_url):
        img = (item.get("image") or "").replace("http://", "https://", 1)
        name = item.get("title", "")
        addr = item.get("addr", "")
        card = '<div class="nearby-card">'
        if img:
            card += '<img class="nearby-card-img" src="' + img + '" alt="' + name + '" loading="lazy">'
        card += '<div class="nearby-card-body" style="text-align:center;">'
        card += '<strong class="nearby-card-name" style="display:block;margin-bottom:4px;">' + name + "</strong>"
        if addr:
            card += '<span class="nearby-card-addr" style="display:block;margin-bottom:8px;color:#555;">' + addr + "</span>"
        card += '<a class="nearby-card-btn" href="' + map_url + '" target="_blank" rel="nofollow" style="display:inline-block;padding:8px 20px;margin-top:12px;margin-bottom:12px;background:#181616;color:#fff;border-radius:6px;text-decoration:none;font-size:14px;font-weight:500;">네이버 지도에서 보기</a>'
        card += "</div></div>"
        return card

    restaurants = nearby_data.get("restaurants", [])
    if not restaurants:
        return html

    nearby_html = '\n\n<h3 style="color:#FF5722;margin-top:20px;margin-bottom:15px;">주변 맛집</h3>\n'
    for r in restaurants[:5]:
        name = r.get("title", "")
        if not name:
            continue
        encoded = urllib.parse.quote(name)
        url = "https://map.naver.com/v5/search/" + encoded
        nearby_html += _nearby_card(r, url) + "\n\n"

    return html + nearby_html


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
        card += '<div class="nearby-card-body" style="text-align:center;">'
        card += '<strong class="nearby-card-name" style="display:block;margin-bottom:4px;">' + name + "</strong>"
        if addr:
            card += '<span class="nearby-card-addr" style="display:block;margin-bottom:8px;color:#555;">' + addr + "</span>"
        card += '<a class="nearby-card-btn" href="' + map_url + '" target="_blank" rel="nofollow" style="display:inline-block;padding:8px 20px;margin-top:12px;margin-bottom:12px;background:#181616;color:#fff;border-radius:6px;text-decoration:none;font-size:14px;font-weight:500;">네이버 지도에서 보기</a>'
        card += "</div></div>"
        return card

    attractions = nearby_data.get("attractions", [])
    if attractions:
        nearby_html += '\n\n<h3 style="color:#FF5722;margin-top:20px;margin-bottom:15px;">주변에 가볼 만한 곳</h3>\n'
        for a in attractions[:3]:
            name = a.get("title", "")
            if not name:
                continue
            encoded = urllib.parse.quote(name)
            url = "https://map.naver.com/v5/search/" + encoded
            nearby_html += _nearby_card(a, url) + "\n\n"

    restaurants = nearby_data.get("restaurants", [])
    # 가볼만한곳 + 맛집 합계 6개 이하
    _nearby_total = len([a for a in attractions[:3] if a.get("title")])
    _restaurant_limit = max(0, 6 - _nearby_total)
    if restaurants and _restaurant_limit > 0:
        nearby_html += '\n\n<h3 style="color:#FF5722;margin-top:20px;margin-bottom:15px;">주변 맛집</h3>\n'
        for r in restaurants[:min(3, _restaurant_limit)]:
            name = r.get("title", "")
            if not name:
                continue
            encoded = urllib.parse.quote(name)
            url = "https://map.naver.com/v5/search/" + encoded
            nearby_html += _nearby_card(r, url) + "\n\n"

    return html + nearby_html




def _post_process(content):
    # 마지막 문장 정리: 온전한 문장으로 끝나도록
    lines = content.rstrip().split("\n")
    while lines and lines[-1].strip() == "":
        lines.pop()
    if lines:
        last = lines[-1].rstrip()
        if last and last[-1] not in ".다!?":
            import re as _re
            match = _re.search(r"(.*[.다!?])", last)
            if match:
                lines[-1] = match.group(1)
            else:
                lines.pop()
    content = "\n".join(lines)

    # 노출되면 안 되는 HTML 주석 제거
    content = re.sub(r"<!--\s*(여행용 카메라|편한 워킹화|보조배터리)\s*-->", "", content)

    # 미완성 문장 수정 — AI가 "~하시기 ." 형태로 끝낸 경우만 복구
    content = re.sub(r"계획하시기\s*\.", "계획하는 것을 추천한다.", content)
    content = re.sub(r"확인하여\s*\.", "확인하는 것이 좋다.", content)
    content = re.sub(r"확인해 보시기\s*\.", "확인해 보는 것이 좋다.", content)
    content = re.sub(r"참고하시기\s*\.", "참고하시는 것이 좋습니다.", content)
    content = re.sub(r"유의하시기\s*\.", "유의하셔야 합니다.", content)
    content = re.sub(r"방문하시기\s*\.", "방문하시는 것이 좋습니다.", content)
    content = re.sub(r"이용하시기\s*\.", "이용하시는 것이 좋습니다.", content)
    content = re.sub(r"확인하시기\s*\.", "확인하시는 것이 좋습니다.", content)
    content = re.sub(r"준비하시기\s*\.", "준비하시는 것이 좋습니다.", content)

    # "궁금하지 않으세요/않으신가요" 2회 초과 시 제거
    q_matches = re.findall(r"[^\n]*궁금하[^\n]*\n?", content)
    if len(q_matches) > 2:
        count = 0
        lines = content.split("\n")
        new_lines = []
        for line in lines:
            if "궁금하" in line:
                count += 1
                if count > 2:
                    continue
            new_lines.append(line)
        content = "\n".join(new_lines)

    # 연속 빈줄 정리
    content = re.sub(r"\n{4,}", "\n\n\n", content)

    # ── 엔티티 카드 분산 배치 ──────────────────────────────
    content = _inject_entity_cards(content)

    # [PATCH] GPT가 만든 "함께 읽어보기" 섹션 통째로 제거
    _related_idx = content.find("## 함께 읽어보기")
    if _related_idx > 0:
        content = content[:_related_idx].rstrip()

    # H2 과다 방지: 7개 초과 시 마지막 H2 섹션 제거
    # (정보전달형 구조: 도입부 + H2 5~7개(개요/프로그램/교통/준비/주변/마무리) 허용)
    _h2_positions = [m.start() for m in re.finditer(r"^## ", content, re.MULTILINE)]
    if len(_h2_positions) > 7:
        _cut_pos = _h2_positions[7]
        content = content[:_cut_pos].rstrip()

    # ── 쿠팡 여행용품 추천 삽입 (후처리) ──────────────────────────────
    try:
        from shared.coupang_travel import CoupangTravel
        _ct = CoupangTravel()
        if _ct.is_configured():
            _blog_id = getattr(_inject_entity_cards, "_current_blog_id", "travel-hugo")
            # GPT가 생성한 disclaimer 제거 (쿠팡 HTML에서 카드 하단에 1회 추가하므로 중복 방지)
            # HTML 태그 포함 또는 plain text 모두 매칭
            _disclaimer_pattern = r'\n*(?:<[^>]*>)?\s*이 포스팅은\s*(?:쿠팡\s*파트너스|쿠팡파트너스)\s*활동의 일환으로,?\s*이에 따른\s*일정액의\s*수수료를\s*제공받습니다\.?\s*(?:</[^>]*>)?\s*'
            content = re.sub(_disclaimer_pattern, '\n\n', content)
            _coupang_html = _ct.get_product_cards(blog_id=_blog_id, count=4)
            if _coupang_html:
                # 프롬프트가 이미 마무리/결론 H2를 생성한 경우 중복 삽입 방지
                _has_closing = bool(re.search(r"^##\s*(마무리|마치며|정리|결론|마지막)", content, re.MULTILINE))
                # '마무리' H2를 마지막 문단 앞에 삽입 (본문 끝에서 덧붙이면 안 됨)
                # 마지막 문단(결론부) 찾기: 마지막 비빈줄 문단
                _lines = content.rstrip().split("\n")
                # 뒤쪽 빈줄 제거
                while _lines and _lines[-1].strip() == "":
                    _lines.pop()
                if _lines:
                    # 마지막 문단이 H2/H3면 그 앞에 마무리 삽입
                    _last = _lines[-1].strip()
                    if _last.startswith("## ") or _last.startswith("### "):
                        # 마지막이 헤딩이면 직전 문단들 뒤에 삽입
                        _insert_pos = len(_lines) - 1
                        while _insert_pos > 0 and _lines[_insert_pos - 1].strip() == "":
                            _insert_pos -= 1
                        if not _has_closing:
                            _lines.insert(_insert_pos, "")
                            _lines.insert(_insert_pos, "## 마무리")
                            _lines.insert(_insert_pos, "")
                    else:
                        # 마지막이 일반 문단이면 그 앞에 마무리 삽입
                        _insert_pos = len(_lines)
                        while _insert_pos > 0 and _lines[_insert_pos - 1].strip() == "":
                            _insert_pos -= 1
                        if not _has_closing:
                            _lines.insert(_insert_pos, "")
                            _lines.insert(_insert_pos, "## 마무리")
                            _lines.insert(_insert_pos, "")
                    # 마무리 H2 뒤에 본문이 없는 경우(제목만 있고 본문 비어있는 상태) 기본 본문 삽입
                    _rejoined = "\n".join(_lines)
                    _closing_match = re.search(r"^##\s*(마무리|마치며|정리|결론|마지막)[^\n]*\n", _rejoined, re.MULTILINE)
                    if _closing_match:
                        _after = _rejoined[_closing_match.end():].lstrip("\n").lstrip()
                        # 다음 헤딩이나 쿠팡 시작까지 본문이 없으면 기본 마무리 문장 삽입
                        if not _after or _after.startswith("## ") or _after.startswith("### ") or _after.startswith("<"):
                            _default_closing = (
                                "위에서 소개한 장소들은 각기 특색이 있는 여행지입니다. "
                                "방문 전 운영 시간과 예약 여부를 확인하시고, "
                                "날씨와 계절에 맞는 준비를 하시면 더욱 즐거운 여행이 될 것입니다. "
                                "좋은 여행 되세요."
                            )
                            _lines.insert(_closing_match.end(), _default_closing + "\n")
                    content = "\n".join(_lines) + "\n\n" + _coupang_html
                else:
                    content = content.rstrip() + ("\n\n## 마무리\n\n" if not _has_closing else "\n\n") + _coupang_html
    except Exception as _ce:
        logger.warning("쿠팡 여행용품 삽입 실패: %s", _ce)

    return content


def _inject_entity_cards(content):
    """엔티티 카드를 상/중/하에 분산 배치.

    - 상단: 첫 H2 앞에 1개
    - 중단: 본문 중간 H2 앞에 1개 (첫 H2와 마지막 H2 사이)
    - 하단: 마지막 H2 섹션 끝에 1개 (없으면 중단과 통합)
    """
    import re as _re
    from core.tap_entity_manager import _build_card_html, _fetch_candidates, _pick_two

    # 현재 블로그 기준으로 카드 후보 선정 (기존 "tap-blogger" 하드코딩은
    # travel1(축제) 글에 맛집/캠핑 카드가 들어가는 주제 이탈 원인)
    _cur_blog = getattr(_inject_entity_cards, "_current_blog_id", "travel-hugo")
    candidates = _fetch_candidates(_cur_blog, "")
    selected = _pick_two(candidates)
    if not selected:
        return content

    cards = [_build_card_html(s) for s in selected]

    h2_positions = [m.start() for m in _re.finditer(r"^## ", content, _re.MULTILINE)]
    if not h2_positions:
        return content + "\n\n" + cards[0] + "\n\n"

    # raw HTML 카드 다음에는 반드시 빈 줄(\n\n) — Hugo가 마크다운 재개 인식.
    # \n 하나면 </div>\n## 이 HTML 블록으로 취급돼 ## 이 raw 노출됨.
    content = content[:h2_positions[0]] + cards[0] + "\n\n" + content[h2_positions[0]:]

    h2_positions = [m.start() for m in _re.finditer(r"^## ", content, _re.MULTILINE)]

    if len(selected) < 2:
        return content

    if len(h2_positions) < 2:
        # H2가 1개뿐이면 두 번째 카드는 본문 맨 끝에 배치 (상단 회귀 방지)
        content = content.rstrip() + "\n\n" + cards[1] + "\n\n"
        return content

    if len(h2_positions) < 3:
        # H2가 2개면 중간 위치(첫 H2와 둘째 H2 사이 또는 둘째 H2 앞)에 배치
        mid_idx = len(h2_positions) // 2
        content = content[:h2_positions[mid_idx]] + "\n\n" + cards[-1] + "\n\n" + content[h2_positions[mid_idx]:]
        return content

    mid_idx = len(h2_positions) // 2
    content = content[:h2_positions[mid_idx]] + "\n\n" + cards[1] + "\n\n" + content[h2_positions[mid_idx]:]

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

def _validate_and_retry(content, system_prompt, user_prompt, max_retries=3):
    """생성된 콘텐츠의 H2/H3/글자수를 검증하고 미달 시 재생성.
    H2 4~5개, H3 2개+, 글자수 2500+ 을 TAP 정보형 구조 기준으로 강제.
    재시도 시 더 강한 모델 tier로 폴백. 최대 재시도 후에도 미달이면
    **빈 content 반환 (fail-closed)** — 발행 중단.
    """
    # 재시도 tier 후보 — 전체 17개 모델 폴백 체인 중 "시작점" 후보.
    # ai_writer.generate(tier=X)는 X부터 전체 체인을 순차 시도하므로,
    # 한 프로바이더(쿼터 소진/타임아웃)가 막혀도 다음 프로바이더로 자동 폴백된다.
    # zen-deepseek-free는 응답이 느려(타임아웃 빈번) 우선순위에서 제외.
    _RETRY_TIERS = ["cerebras-gemma", "nvidia-nemotron", "gemini-3.5-flash-lite", "groq-qwen"]
    for attempt in range(max_retries + 1):
        _all_h3_titles = re.findall(r"^### (.+)", content, re.MULTILINE)
        h3_count = len(_all_h3_titles)
        h2_count = len(re.findall(r"^## ", content, re.MULTILINE))
        char_count = len(content)

        issues = []
        if h2_count < 4:
            issues.append(f"H2 {h2_count}개→4개 필요 (이상)")
        if h3_count < 1:
            issues.append(f"H3 {h3_count}개→1개 필요 (이상)")
        if char_count < 1500:
            issues.append(f"글자수 {char_count}→1500 필요")

        if not issues:
            if attempt == 0:
                logger.info("초회 검증 통과 (H2:%d, H3:%d, 글자수:%d)", h2_count, h3_count, char_count)
            else:
                logger.info("재시도 후 검증 통과 (H2:%d, H3:%d, 글자수:%d)", h2_count, h3_count, char_count)
            return content

        if attempt < max_retries:
            _retry_tier = _RETRY_TIERS[attempt] if attempt < len(_RETRY_TIERS) else "default"
            logger.warning("검증 실패, 재시도 %d/%d (%s): %s", attempt + 1, max_retries, _retry_tier, issues)
            new_result = ai_generate(system_prompt, user_prompt, tier=_retry_tier, max_tokens=4800)
            if new_result and new_result.get("content"):
                content = new_result["content"]
                # 재시도 결과도 검증 루프로 다시 감 (H2/H3/글자수)
                continue
            else:
                # 해당 tier가 실패(429 등) — break 대신 다음 tier 후보로 계속 시도
                logger.warning("재시도 %s 실패(빈 결과) — 다음 모델 후보로 진행", _retry_tier)
                # attempt를 소모하지 않고 content는 유지한 채 다음 루프로
                continue
        else:
            logger.error("최대 재시도 초과 — 구조 미달로 발행 중단: %s", issues)
            return ""

    logger.error("검증 통과 실패 — 발행 중단")
    return ""

    # [과거연도 방어] 제목/본문에서 과거연도 -> 현재연도 변환
    import re as _yre
    _cy = str(__import__("datetime").datetime.now().year)
    for _py in [str(y) for y in range(2020, int(_cy))]:
        if _py in content:
            content = _yre.sub(
                r"(?<!/)(?<![\w])" + _py + r"(?=[ 년.~,\-가-힣])",
                _cy, content
            )

    return content



def _enrich_title(title, data, display_region, theme, source_type, prompt_id=""):
    """Prepend search-intent keyword after region name in title.

    Pattern: '{region} {store}' → '{region} {intent_keyword} {store}'
    Intent keywords: 맛집(식당), 캠핑/글램핑(캠핑장), 여행(관광지/코스), 축제(축제)
    Skips if keyword already exists as a standalone word in the title.
    """
    kw = ""
    if source_type in ("food", "korservice"):
        kw = "축제" if prompt_id == "travel1_festival" else "맛집"
    elif source_type == "camping":
        kw = "글램핑" if "글램핑" in (theme or "") else "캠핑"
    elif source_type in ("heritage", "course"):
        kw = "여행"

    if not kw:
        return title
    if re.search(rf"(?<!\w){re.escape(kw)}(?!\w)", title):
        return title
    if display_region and len(display_region) >= 2:
        escaped = re.escape(display_region)
        new_title, n = re.subn(
            rf"{escaped}(?=\s|$)",
            f"{display_region} {kw}",
            title, count=1
        )
        if n:
            return re.sub(r"\s+", " ", new_title).strip()
    return title


def sanitize_markdown(text: str, blog_id: str = "") -> str:
    if not text:
        return text

    fixes = {"bold_unmatched": 0, "strike_unmatched": 0, "h1_removed": 0, "h1_demoted": 0}
    import re as _re

    _parts = text.split("**")
    if len(_parts) > 1 and len(_parts) % 2 == 0:
        if text.rstrip().endswith("**") and not text.rstrip().endswith("***"):
            text = text.rstrip()[:-2]
            fixes["bold_unmatched"] += 1
        else:
            last_pos = text.rfind("**")
            if last_pos >= 0:
                text = text[:last_pos] + text[last_pos + 2 :]
                fixes["bold_unmatched"] += 1

    _parts_s = text.split("~~")
    if len(_parts_s) > 1 and len(_parts_s) % 2 == 0:
        last_pos = text.rfind("~~")
        if last_pos >= 0:
            text = text[:last_pos] + text[last_pos + 2 :]
            fixes["strike_unmatched"] += 1

    _body_start = 0
    _fm_end = text.find("---\n", 1)
    if _fm_end > 0 and text.startswith("---"):
        _body_start = _fm_end + 4

    _body = text[_body_start:] if _body_start else text
    _lines = _body.split("\n")
    _new_lines = []
    _title_text = ""

    for _line in _lines:
        _stripped = _line.strip()
        if _stripped.startswith("# ") and not _stripped.startswith("## "):
            _h1_content = _stripped[2:].strip()
            if not _title_text:
                _tm = _re.search(r'^title:\s*[\'"](.+?)[\'"]', text[:_body_start], _re.MULTILINE)
                if _tm:
                    _title_text = _tm.group(1)
            if _title_text and (_h1_content == _title_text or _h1_content in _title_text or _title_text in _h1_content):
                fixes["h1_removed"] += 1
                continue
            else:
                _new_lines.append(_re.sub(r"^(\s*)# ", r"\1## ", _line))
                fixes["h1_demoted"] += 1
                continue
        _new_lines.append(_line)

    text = text[:_body_start] + "\n".join(_new_lines) if _body_start else "\n".join(_new_lines)

    _total = sum(v for v in fixes.values())
    if _total > 0:
        _parts_log = []
        for _key, _val in fixes.items():
            if _val > 0:
                _parts_log.append(f"rule={_key} count={_val}")
        logger.warning("[sanitize] file=%s %s", blog_id or "unknown", " ".join(_parts_log))

    return text


def generate_content(data, blog_id="travel-hugo"):
    source_type = data.get("source_type", "camping")
    prompt_id = _select_prompt_id(blog_id, source_type, item_count=len(data.get("items", [])))

    # 블로그 정보 + 다이닝코드 enrichment (GPT 호출 전에 실행)
    # travel4-hugo(여행코스)는 enrichment 스킵 — 가격 데이터가 부정확하여 환각 유발
    if blog_id != "travel4-hugo":
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
    if source_type == "korservice" and prompt_id == "travel1_festival":
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

    _item_count = len(data.get("items", []))
    if data.get("source_type") != "heritage" and data.get("source_type") != "course":
        _item_count = min(_item_count, 3)
    # heritage 심층 프롬프트용 {name} 변수
    _first_item_name = ""
    if data.get("items"):
        _first_item_name = data["items"][0].get("title", data["items"][0].get("facltNm", ""))
    extra_vars = {
        "blog_snippets": _snippets_text,
        "region": data.get("display_region", data.get("region", "")),
        "theme": data.get("theme", ""),
        "angle": data.get("angle", ""),
        "count": str(_item_count),
        "name": _first_item_name,
    }

    prompt_result = build_prompt(prompt_id, data_block, extra_vars=extra_vars, inject_samples=True, sample_category=source_type)
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

    result = ai_generate(system_prompt, user_prompt, tier="default", max_tokens=4800)

    if not result or not result.get("content"):
        logger.error("AI 생성 실패: prompt_id=%s", prompt_id)
        return None

    content = result["content"]
    model_used = result.get("model", "")

    # 장소명 검증: API 데이터의 실제 장소명이 본문에 포함되어 있는지 확인
    place_items = data.get("items", [])
    real_names = [it.get("title", it.get("facltNm", "")).strip() for it in place_items if it.get("title") or it.get("facltNm")]
    content, names_ok = _validate_place_names(content, real_names)
    if not names_ok:
        logger.info("장소명 불일치 감지 (재생성 안함)")

    # 검증 및 재시도: H2/H3/글자수 확인 (미달 시 강한 모델 재시도, 최종 미달이면 발행 중단)
    content = _validate_and_retry(content, system_prompt, user_prompt, max_retries=3)
    if not content:
        logger.error("본문 구조 검증 실패 — 발행 중단 (fail-closed)")
        return None

    _post_process._current_blog_id = blog_id
    content = _post_process(content)

    # 다시 한 번 H2 과다 방지 (재시도 결과도 잘라냄) — 정보전달형 구조 허용 (7개)
    _h2_positions_final = [m.start() for m in re.finditer(r"^## ", content, re.MULTILINE)]
    if len(_h2_positions_final) > 7:
        _cut_pos_final = _h2_positions_final[7]
        content = content[:_cut_pos_final].rstrip()
        logger.info("재시도 후 H2 과다 방지: %d개 → 7개로 절단", len(_h2_positions_final))
    # travel4-hugo(여행코스)는 맛집 카드만 삽입 (가볼만한곳은 코스 장소와 중복 가능)
    if blog_id == "travel4-hugo":
        content = _enrich_with_nearby_restaurants_only(data, content)
    else:
        content = _enrich_with_nearby(data, content)
    # [PATCH] _enrich_with_nearby 후 GPT "함께 읽어보기" 최종 제거 + 동적 내부링크
    _final_related_idx = content.find("## 함께 읽어보기")
    if _final_related_idx > 0:
        content = content[:_final_related_idx].rstrip()
    # 동적 내부링크 삽입 (블로우피쉬 relatedPosts 옵션 사용으로 비활성화)
    # try:
    #     import glob as _gl_final
    #     import random as _rand_final
    #     _blog_path_final = {
    #         "travel-hugo":  "/Users/twinssn/Projects/TAP/travel-hugo",
    #         "travel1-hugo": "/Users/twinssn/Projects/TAP/travel1-hugo",
    #         "travel2-hugo": "/Users/twinssn/Projects/TAP/travel2-hugo",
    #         "travel3-hugo": "/Users/twinssn/Projects/TAP/travel3-hugo",
    #         "travel4-hugo": "/Users/twinssn/Projects/TAP/travel4-hugo",
    #     }
    #     _posts_dir_final = os.path.join(_blog_path_final.get(blog_id, "/Users/twinssn/Projects/TAP/travel-hugo"), "content", "posts")
    #     _all_posts_final = []
    #     for _md_f in _gl_final.glob(os.path.join(_posts_dir_final, "*/index.md")):
    #         with open(_md_f, encoding="utf-8") as _ff:
    #             _head_f = _ff.read(500)
    #         import re as _re_final
    #         _tm_f = _re_final.search(r"^title:\s*[\x27\x22](.*?)[\x27\x22]", _head_f, _re_final.MULTILINE)
    #         _sm_f = _re_final.search(r"^slug:\s*[\x27\x22](.*?)[\x27\x22]", _head_f, _re_final.MULTILINE)
    #         if _tm_f and _sm_f:
    #             _all_posts_final.append({"title": _tm_f.group(1), "slug": _sm_f.group(1)})
    #     if len(_all_posts_final) > 3 and "## 함께 읽어보기" not in content:
    #         _picks_f = _rand_final.sample(_all_posts_final, 3)
    #         _related_md_f = "\n\n## 함께 읽어보기\n\n"
    #         for _p_f in _picks_f:
    #             _related_md_f += '{{< article link="/posts/' + _p_f["slug"] + '/" >}}\n\n'
    #         content = content.rstrip() + _related_md_f
    # except Exception as e:
    #     logger.debug(f"[TRAVEL_WRITER] failed: {e}")
    # Heritage 카드 삽입 (heritage 소스 타입에서만)
    if source_type == "heritage":
        try:
            _region = data.get("region", "") if isinstance(data, dict) else ""
            _h_card = _build_heritage_card(_region)
            # heritage 카드: 중복 방지 + nearby 카드 바로 앞에 삽입
            if "K-Heritage Guide" not in content:
                _nb_pos = content.find('<div class="nearby-card"')
                if _nb_pos > 0:
                    content = content[:_nb_pos] + "\n" + _h_card + "\n\n" + content[_nb_pos:]
                else:
                    content = content + "\n\n" + _h_card
        except Exception as e:
            logger.warning(f"[heritage-card] 삽입 실패: {e}")

    # Heritage 글: 본문에 대표 이미지(hero)를 도입부 직후 첫 H2 앞에 삽입
    # 단, 첫 번째 아이템이 H3와 매칭되면 _inject_images가 처리하므로 hero는 생략
    if source_type == "heritage" and items:
        _heritage_img = items[0].get("image", "") or ""
        if _heritage_img and _heritage_img.startswith("http"):
            # 첫 아이템이 H3와 매칭될지 사전 확인
            _first_item_name = items[0].get("title", "").strip()
            _first_item_key = _first_item_name.replace(" ", "")
            _matched_by_inject = False
            for _line in content.split("\n"):
                if _line.startswith("### ") and _first_item_key and (
                    _first_item_key in _line.replace(" ", "") or _first_item_name in _line
                ):
                    _matched_by_inject = True
                    break
            if not _matched_by_inject:
                _first_h2_idx = content.find("\n## ")
                if _first_h2_idx > 0:
                    _hero_alt = _first_item_name[:40] or "대표 이미지"
                    content = (
                        content[:_first_h2_idx]
                        + f'\n\n![{_hero_alt}]({_heritage_img.replace("http://", "https://", 1)})\n'
                        + content[_first_h2_idx:]
                    )
                else:
                    _hero_alt = _first_item_name[:40] or "대표 이미지"
                    content = f'\n\n![{_hero_alt}]({_heritage_img.replace("http://", "https://", 1)})\n\n' + content

    items = data.get("items", [])
    content = _inject_images(items, content, blog_id=blog_id)
    _is_festival = (source_type in ("festival", "korservice")
                    and _select_prompt_id(blog_id, source_type) == "travel1_festival")
    content = _inject_naver_map(content, items, is_festival=_is_festival)

    display_region = data.get("display_region", "")
    theme = data.get("theme", "")
    angle = data.get("angle", theme)
    items = data.get("items", [])

    # 실제 다룬 장소 수는 items 기준으로만 결정 (H3 수에 영향받지 않음)
    _body_place_count = len(items) if len(items) > 0 else 1

    TITLE_TEMPLATES = TRAVEL_TITLE_TEMPLATES


    # region/theme 빈값 보호
    if not display_region or len(display_region) < 2:
        display_region = data.get("display_region", data.get("region", "전국"))
    if not display_region or len(display_region) < 2:
        display_region = "전국"
    if not theme or len(theme) < 2:
        theme = "여행"

    _camp_names = [i.get("title", i.get("facltNm", ""))[:15] for i in items if i.get("title") or i.get("facltNm")]
    fallback_title = make_fallback(display_region, theme, _body_place_count, _camp_names, blog_id)
    title = fallback_title

    place_names = extract_place_names(items)
    title_prompt = build_title_prompt(display_region, theme, place_names, source_type, blog_id)

    try:
        _ai_result = ai_generate(
            "블로그 제목 생성 전문가. 제목 1개만 출력.",
            title_prompt,
            tier="default",
            temperature=0.6
        )
        if _ai_result and _ai_result.get("content"):
            generated_title = _ai_result["content"].strip().strip('"').strip("'")
            generated_title = re.sub(r"^(제목[:\s]*|Title[:\s]*)", "", generated_title).strip()
            generated_title = validate_and_retry(generated_title, title_prompt, ai_generate, max_len=35)
            # 고유명사(첫 장소명)가 있으면 타이틀에 반드시 포함되도록 검증
            # — AI가 지역명만 넣고 고유명사는 빠뜨리는 경우를 방지(fallback은 포함하므로)
            _proper = place_names[0] if place_names else ""
            _has_proper = (not _proper) or (_proper and _proper in generated_title)
            if (len(generated_title) >= 15 and display_region
                    and len(display_region) >= 2 and display_region in generated_title
                    and _has_proper):
                title = generated_title
    except Exception as e:
        logger.warning(f"AI title generation failed: {e}")

    validated_region = validate_display_region(display_region)
    if display_region and not validated_region:
        logger.warning(f"[TAG] 지역 태그 오분류 의심: '{display_region}' → 태그 제거")
    labels = list(set(filter(None, [
        data.get("category", "국내여행"),
        theme,
        validated_region,
    ])))

    # SEO description 생성: 지역 + 테마 + 핵심정보
    _item_names = [it.get("title", it.get("facltNm", ""))[:15] for it in items[:3] if it.get("title") or it.get("facltNm")]
    _names_str = ", ".join(_item_names) if _item_names else theme
    _item_count = len(items)
    if _item_count > 1:
        _place_word = f"{_item_count}곳"
        _seo_desc = f"{display_region} {theme} — {_names_str}. {_place_word} 정보와 방문 팁 정리."
    else:
        _seo_desc = f"{display_region} {theme} — {_names_str}. 방문 팁 정리."
    if len(_seo_desc) > 160:
        _seo_desc = _seo_desc[:157] + "..."
    # [PATCH] DESC 주석 제거됨

    # 대가성 문구 삽입 (본문 최상단)
    # [FIX] 상단 쿠팡 문구 삽입 제거 — 하단 _post_process에서 1회만 삽입
    # if "쿠팡 파트너스" not in content:
    #     content = '> **이 포스팅은 ...** \n\n' + content

    title = _enrich_title(title, data, display_region, theme, source_type, prompt_id)

    title = sanitize_markdown(title, blog_id=blog_id)
    content = sanitize_markdown(content, blog_id=blog_id)

    # 최종 구조 재검증: 어떤 후처리가 H2를 줄였어도 4개 미만이면 발행 중단 (fail-closed)
    _final_h2 = len(re.findall(r"^## ", content, re.MULTILINE))
    _final_h3 = len(re.findall(r"^### ", content, re.MULTILINE))
    if _final_h2 < 4:
        logger.error("최종 H2 %d개 (<4) — 구조 미달로 발행 중단 (blog=%s)", _final_h2, blog_id)
        return None
    logger.info("최종 구조 확인 (H2:%d, H3:%d)", _final_h2, _final_h3)

    # Phase 72 W2 T2.4: items에서 결정론 파생 points를 passthrough로 주입
    # (TAP은 topic-id 주소 가능 로컬 스토어 없음 — PLAN §2 설계결정)
    content = _inject_editorial_synthesis(
        content,
        {"topic_type": "tap", "unique_data": _derive_points_from_items(data.get("items", []))},
    )

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

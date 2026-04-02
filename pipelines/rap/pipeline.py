"""RAP (Real estate Auto Publisher) pipeline — RAP 전용 DB 사용"""
import os
import random
import sqlite3
import logging
from datetime import datetime
from shared.validators import sanitize_title

logger = logging.getLogger(__name__)

try:
    from shared.telegram_notifier import send_error as tg_error
except ImportError:
    tg_error = lambda *a, **k: None

RAP_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "rap.db")
GAP_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "gap.db")

# 부동산 무관 키워드 제외 패턴
RAP_EXCLUDE = [
    "기능사", "요리", "조리", "흑백", "레시피", "양식조리", "제과", "봉제",
    "롤러운전", "콘크리트", "전자기능", "주조", "인베디드", "견적서",
    "운세", "로또", "날씨", "웹툰", "게임", "파전", "킷트", "래시피",
    "키친보스", "오스틴강", "이탈리안", "이탈리아", "명태살", "1분링",
    "상가", "용지", "어린이집", "임차운영", "근린생활", "산업단지",
    "재입찰", "수의계약", "매각 공고", "주차장용지", "점포겸용",
]

# 부동산 카테고리 목록
RAP_CATEGORIES = ("금융/부동산",)

# 키워드 → 전략 매핑
TRADE_PATTERNS = ["실거래", "매매", "시세", "집값", "아파트", "공시지가", "빌라", "오피스텔"]
SUB_PATTERNS = ["청약", "분양", "LH", "행복주택", "임대", "전세"]

# blog_id별 키워드 필터 패턴
BLOG_KEYWORD_FILTER = {
    "rap-hugo":  ["아파트", "매매", "시세", "실거래", "집값", "공시지가", "빌라", "오피스텔",
                  "은마", "재건축", "재개발", "부동산", "드림타운", "레지던스",
                  "미소지움", "아르티스", "트인시아", "펠루시드", "팰루시드",
                  "S클래스", "브라이튼", "에테르노", "디아이엘", "하이니티", "비스타",
                  "냉난방", "전원주택", "모아타운", "아페르", "라엘",
                  "서울아파트", "동탄"],
    "rap2-hugo": ["청약", "분양", "LH", "행복주택", "임대주택", "청년주택", "청년안심",
                  "국민임대", "영구임대", "매입임대", "신혼희망"],
    "rap3-hugo": ["양도", "취득세", "상속세", "증여세", "세금", "과세", "공시지가", "재산세",
                  "종부세", "종합부동산세", "절세", "세율", "면제"],
    "rap4-hugo": ["전세", "월세", "임대", "보증금", "임대차", "전월세", "반전세",
                  "보증보험", "전세사기", "확정일자", "임차인", "계약갱신"],
    "rap5-hugo": ["헬리오시티", "힐스테이트", "래미안", "자이", "푸르지오", "아크로", "파크리오",
                  "더샵", "르엘", "롯데캐슬", "SK뷰", "아이파크", "e편한세상",
                  "디에이치", "트리우스", "브랜드", "풍림", "드파인", "브르넨",
                  "라브르", "원펜타스", "디디하우스"],
}

# blog_id별 강제 전략
BLOG_STRATEGY = {
    "rap-hugo":  "trade",
    "rap2-hugo": "subscription",
    "rap3-hugo": "trade",
    "rap4-hugo": "trade",
    "rap5-hugo": "trade",
}

WP_CATEGORY_MAP = {
    "부동산": 150,
    "실거래가": 150,
    "청약정보": 149,
    "임대주택": 149,
}


def _pick_keyword(blog_id):
    """RAP DB에서 키워드 선택 — 오염 필터 + 중복 발행 방지"""
    # RAP DB 우선, 없으면 GAP DB 폴백
    db_path = RAP_DB_PATH if os.path.exists(RAP_DB_PATH) else GAP_DB_PATH
    conn = sqlite3.connect(db_path)
    try:
        patterns = BLOG_KEYWORD_FILTER.get(blog_id, [])

        if db_path == RAP_DB_PATH:
            # RAP DB: blog_target 필터 우선
            rows = conn.execute(
                "SELECT keyword, category FROM keywords "
                "WHERE status='active' "
                "ORDER BY use_count ASC, last_used_at ASC NULLS FIRST "
                "LIMIT 200"
            ).fetchall()
        else:
            # GAP DB 폴백
            rows = conn.execute(
                "SELECT keyword, category FROM keywords "
                "WHERE category='금융/부동산' AND status='active' "
                "ORDER BY use_count ASC, last_used_at ASC NULLS FIRST "
                "LIMIT 200"
            ).fetchall()

        # 1단계: 오염 키워드 제거
        rows = [(kw, cat) for kw, cat in rows
                if not any(ex in kw for ex in RAP_EXCLUDE)]

        # 2단계: blog_id별 패턴 필터
        if patterns:
            filtered = [(kw, cat) for kw, cat in rows if any(p in kw for p in patterns)]
            if filtered:
                rows = filtered

        # 3단계: 이미 발행된 키워드 제외 (최근 7일)
        try:
            rap_conn = sqlite3.connect(RAP_DB_PATH) if db_path != RAP_DB_PATH else conn
            published = {r[0] for r in rap_conn.execute(
                "SELECT data_key FROM publish_log WHERE blog_id=? AND published_at > datetime('now', '-7 days')",
                (blog_id,)
            ).fetchall()}
            if db_path != RAP_DB_PATH:
                rap_conn.close()
            rows = [(kw, cat) for kw, cat in rows if kw not in published]
        except Exception:
            pass  # publish_log 테이블 없으면 스킵

        if not rows:
            logger.warning(f"{blog_id}: 사용 가능한 부동산 키워드 없음")
            return None, None

        keyword, category = random.choice(rows[:20])

        # 사용 기록 갱신
        conn.execute(
            "UPDATE keywords SET use_count = use_count + 1, "
            "last_used_at = datetime('now') WHERE keyword = ?",
            (keyword,)
        )
        conn.commit()
        logger.info(f"{blog_id}: 키워드 선택 -> {keyword} ({category})")
        return keyword, category
    finally:
        conn.close()


# trade 전략에 부적합한 키워드 패턴 (2차 방어)
TRADE_INCOMPATIBLE = ["상가", "용지", "어린이집", "임차운영", "근린생활",
                      "산업단지", "재입찰", "수의계약", "매각 공고", "주차장용지",
                      "점포겸용", "입점자 모집", "운영자 선정", "운영자 모집"]


def _pick_strategy(keyword, blog_id=None):
    """blog_id에 따라 전략 결정, 없으면 키워드 기반
    2차 방어: trade 강제 blog라도 키워드가 trade 부적합이면 subscription으로 전환
    """
    # 키워드 기반 trade 부적합 감지 (blog 강제보다 우선)
    if any(p in keyword for p in TRADE_INCOMPATIBLE):
        logger.info(f"2차 방어: trade 부적합 키워드 → subscription 전환: {keyword}")
        return "subscription"

    if blog_id and blog_id in BLOG_STRATEGY:
        return BLOG_STRATEGY[blog_id]
    for p in SUB_PATTERNS:
        if p in keyword:
            return "subscription"
    for p in TRADE_PATTERNS:
        if p in keyword:
            return "trade"
    return "trade"


def _post_process(body_md, blog_id, keyword):
    # 금지어 자동 치환
    body_md = body_md.replace("특히 ", "").replace("특히, ", "")
    body_md = body_md.replace("특히,", "").replace("  ", " ")

    """발행 전 후처리: 금지표현 제거 + 면책조항 + 쿠팡 + 내부링크"""
    import re as _re

    # 1. 금지 표현 제거
    BANNED = ["바랍니다", "되시길", "있으시", "마무리하며", "마치며", "즐겨보세요", "만끽해 보세요"]
    for b in BANNED:
        body_md = body_md.replace(b, "")

    # 2. GPT가 넣은 면책 문구 제거 (중복 방지)
    body_md = _re.sub(r"\n*이 글은 국토교통부[^\n]*", "", body_md)
    body_md = _re.sub(r"\n*> 이 글은[^\n]*", "", body_md)
    body_md = _re.sub(r"\n*이 포스팅은 쿠팡[^\n]*", "", body_md)
    body_md = _re.sub(r"\n*> 이 포스팅은 쿠팡[^\n]*", "", body_md)
    body_md = _re.sub(r"\n*\*이 포스팅은 쿠팡[^\n]*", "", body_md)
    body_md = _re.sub(r"\n*>\s*\*\*이 포스팅은 쿠팡[^\n]*", "", body_md)

    _gpt_section_keywords = ["자취", "신혼", "프리미엄 입주", "추천 가전", "필수 아이템",
                              "입주 준비", "이사 준비", "원룸 필수", "추천 용품"]
    _SYSTEM_TITLES = ["부동산 거래 시 유용한 추천 상품", "차량 관리에 도움되는 추천 용품", "여행 준비에 도움되는 추천 용품"]
    for _gsk in _gpt_section_keywords:
        while True:
            _gi = body_md.find("## " + _gsk)
            if _gi < 0:
                _gi2 = body_md.find("## ")
                _found = False
                while _gi2 >= 0:
                    _line_end = body_md.find("\n", _gi2)
                    if _line_end < 0:
                        _line_end = len(body_md)
                    _header = body_md[_gi2:_line_end]
                    if _gsk in _header:
                        _is_sys = any(st in _header for st in _SYSTEM_TITLES)
                        if _is_sys:
                            _gi2 = body_md.find("## ", _gi2 + 3)
                            continue
                        _gi = _gi2
                        _found = True
                        break
                    _gi2 = body_md.find("## ", _gi2 + 3)
                if not _found:
                    break
            _ge = len(body_md)
            _next = body_md.find("\n## ", _gi + 3)
            _next_hr = body_md.find("\n---", _gi + 3)
            if _next > 0:
                _ge = min(_ge, _next)
            if _next_hr > 0:
                _ge = min(_ge, _next_hr)
            body_md = body_md[:_gi] + body_md[_ge:]
            break
    body_md = _re.sub(r"\n*---\s*$", "", body_md.rstrip())
    body_md = _re.sub(r"\n*---\s*\n*---", "", body_md)
    body_md = body_md.rstrip()

    # 1-1. 글 중간 이탈방지 카드 삽입 (H2 3번째 뒤)
    try:
        import glob as _gl2
        import random as _rand2
        _blog_path_map = {
            "rap-hugo": "/Users/twinssn/Projects/RAP/rap-hugo",
            "rap2-hugo": "/Users/twinssn/Projects/RAP/rap2-hugo",
            "rap3-hugo": "/Users/twinssn/Projects/RAP/rap3-hugo",
            "rap4-hugo": "/Users/twinssn/Projects/RAP/rap4-hugo",
            "rap5-hugo": "/Users/twinssn/Projects/RAP/rap5-hugo",
        }
        _pdir = os.path.join(_blog_path_map.get(blog_id, ""), "content", "posts")
        _candidates = []
        for _md in _gl2.glob(os.path.join(_pdir, "*/index.md")):
            with open(_md, encoding="utf-8") as _f:
                _hd = _f.read(500)
            _tm = _re.search(r'^title:\s*["\'](.*?)["\']', _hd, _re.MULTILINE)
            _sm = _re.search(r'^slug:\s*["\'](.*?)["\']', _hd, _re.MULTILINE)
            if _tm and _sm:
                _candidates.append({"title": _tm.group(1), "slug": _sm.group(1)})
        if len(_candidates) >= 1:
            _pick = _rand2.choice(_candidates)
            _card_html = f'''

<div style="margin:28px 0;padding:18px 22px;background:linear-gradient(135deg,#f8f9ff 0%,#e8f4fd 100%);border-radius:14px;border-left:4px solid #3182ce;">
  <p style="margin:0 0 6px 0;font-size:0.85rem;color:#718096;">📌 놓치면 아쉬운 글</p>
  <a href="/posts/{_pick['slug']}/" style="font-size:1.05rem;font-weight:600;color:#2d3748;text-decoration:none;">{_pick['title']}</a>
</div>

'''
            _h2_positions = [m.start() for m in _re.finditer(r'^## ', body_md, _re.MULTILINE)]
            if len(_h2_positions) >= 4:
                _insert_pos = _h2_positions[3]
                body_md = body_md[:_insert_pos] + _card_html + body_md[_insert_pos:]
                logger.info("중간 이탈방지 카드 삽입 완료")
    except Exception as e:
        logger.warning(f"중간 카드 삽입 실패: {e}")

    # GPT가 생성한 내부링크/추천글 섹션 제거
    _strip_patterns = [
        r"\n*## 함께 읽[^\n]*(?:\n(?!## ).*)*",
        r"\n*## 관련 글[^\n]*(?:\n(?!## ).*)*",
        r"\n*## 추천 글[^\n]*(?:\n(?!## ).*)*",
        r"\n*## 더 읽[^\n]*(?:\n(?!## ).*)*",
        r"\n*## 함께 읽어보기[^\n]*(?:\n(?!## ).*)*",
    ]
    for _pat in _strip_patterns:
        body_md = _re.sub(_pat, "", body_md)

    parts = []

    # 3. 쿠팡 파트너스
    try:
        from shared.coupang_travel import CoupangTravel
        ct = CoupangTravel()
        if ct.is_configured():
            coupang_md = ct.get_travel_product_links(blog_id=blog_id, count=2)
            if coupang_md:
                parts.append(coupang_md)
                logger.info("쿠팡 링크 삽입 완료")
    except Exception as e:
        logger.warning(f"쿠팡 링크 삽입 실패: {e}")

    # 4. 네이버지도 버튼
    _NO_MAP_KEYWORDS = [
        "세금", "양도", "취득세", "종부세", "공시지가", "보증보험", "계약서",
        "임대차", "3법", "청약", "당첨", "확률", "신청", "공고",
        "청년", "LH", "임대주택", "공공임대", "행복주택", "안심주택",
        "총정리", "높이는", "전세사기",
        "단기임대",
        "2주택", "1가구", "종합부동산세", "확정일자",
        "납부시기", "계산방법", "비과세", "공제 기준", "합산배제",
    ]
    _skip_map = any(nk in keyword for nk in _NO_MAP_KEYWORDS) if keyword else True
    try:
        import urllib.parse as _up
        import requests as _req
        if _skip_map:
            logger.info(f"네이버지도 스킵 (비지역 키워드): {keyword}")
            raise ValueError("skip")
        map_query = keyword.strip()
        if not map_query:
            raise ValueError("empty keyword")
        map_label = {
            "rap-hugo": "아파트 매물",
            "rap2-hugo": "분양 단지",
            "rap3-hugo": "부동산 중개",
            "rap4-hugo": "전세 매물",
            "rap5-hugo": "아파트 단지",
        }
        label = map_label.get(blog_id, "부동산")
        _clean_parts = [w for w in label.split() if w not in _NO_MAP_KEYWORDS]
        _clean_label = " ".join(_clean_parts) if _clean_parts else ""
        _search_q = f"{map_query} {_clean_label}".strip() if _clean_label else map_query
        encoded = _up.quote(_search_q)

        # 네이버 지역검색 API로 부동산/주거 장소 존재 검증
        _naver_cid = os.getenv("NAVER_CLIENT_ID", "")
        _naver_csec = os.getenv("NAVER_CLIENT_SECRET", "")
        _PLACE_CATS = ["부동산", "아파트", "주거", "주택", "오피스텔", "공인중개", "중개업"]
        _has_place = False
        if _naver_cid and _naver_csec:
            _local_resp = _req.get(
                "https://openapi.naver.com/v1/search/local.json",
                params={"query": _search_q, "display": 5},
                headers={"X-Naver-Client-Id": _naver_cid, "X-Naver-Client-Secret": _naver_csec},
                timeout=5,
            )
            if _local_resp.status_code == 200:
                _items = _local_resp.json().get("items", [])
                _has_place = any(
                    any(pc in it.get("category", "") for pc in _PLACE_CATS)
                    for it in _items[:5]
                )
        
        if not _has_place:
            logger.info(f"네이버지도 부동산 결과 없음 → 버튼 생략: {_search_q}")
            raise ValueError("no place result")

        naver_map_html = f"""

<div style="margin:24px 0;padding:16px 20px;background:#f0f7ff;border-radius:12px;border:1px solid #d0e3ff;text-align:center;">
  <p style="margin:0 0 10px 0;font-size:1.05rem;font-weight:600;">📍 {_search_q} 주변 지도로 확인하기</p>
  <a href="https://map.naver.com/v5/search/{encoded}" target="_blank" rel="nofollow" style="display:inline-block;padding:10px 24px;background:#03C75A;color:white;border-radius:8px;text-decoration:none;font-weight:600;">네이버지도에서 보기</a>
</div>
"""
        parts.append(naver_map_html)
        logger.info(f"네이버지도 버튼 삽입 (검증완료): {_search_q}")
    except Exception as e:
        logger.warning(f"네이버지도 삽입 스킵: {e}")

    # 5. 내부링크
    try:
        import glob as _gl
        import random as _rand
        blog_cfg_map = {
            "rap-hugo": "/Users/twinssn/Projects/RAP/rap-hugo",
            "rap2-hugo": "/Users/twinssn/Projects/RAP/rap2-hugo",
            "rap3-hugo": "/Users/twinssn/Projects/RAP/rap3-hugo",
            "rap4-hugo": "/Users/twinssn/Projects/RAP/rap4-hugo",
            "rap5-hugo": "/Users/twinssn/Projects/RAP/rap5-hugo",
        }
        posts_dir = os.path.join(blog_cfg_map.get(blog_id, ""), "content", "posts")
        all_posts = []
        for md in _gl.glob(os.path.join(posts_dir, "*/index.md")):
            with open(md, encoding="utf-8") as f:
                head = f.read(500)
            tm = _re.search(r'^title:\s*["\'](.*?)["\']', head, _re.MULTILINE)
            sm = _re.search(r'^slug:\s*["\'](.*?)["\']', head, _re.MULTILINE)
            if tm and sm:
                all_posts.append({"title": tm.group(1), "slug": sm.group(1)})
        if len(all_posts) >= 2:
            picks = _rand.sample(all_posts, min(3, len(all_posts)))
            related = "\n\n## 함께 읽으면 좋은 글\n\n"
            for p in picks:
                related += f'- [{p["title"]}](/posts/{p["slug"]}/)\n'
            parts.append(related)
    except Exception as e:
        logger.warning(f"내부링크 삽입 실패: {e}")

    # 6. 면책조항
    disclaimer_map = {
        "rap-hugo": "이 글은 국토교통부 실거래가 공공데이터를 기반으로 작성되었습니다. 투자 판단의 책임은 본인에게 있으며, 최신 정보는 [국토교통부 실거래가 공개시스템](https://rt.molit.go.kr)에서 확인하세요.",
        "rap2-hugo": "이 글은 한국부동산원 청약홈 공공데이터를 기반으로 작성되었습니다. 정확한 청약 일정과 자격은 [청약홈](https://www.applyhome.co.kr)에서 확인하세요.",
        "rap3-hugo": "이 글은 국토교통부 실거래가 데이터를 기반으로 작성되었으며, 세금 계산은 참고용입니다. 정확한 세금 상담은 세무사에게 문의하세요.",
        "rap4-hugo": "이 글은 국토교통부 매매 실거래가 데이터를 기반으로 전세가를 추정한 것입니다. 실제 전월세 시세는 다를 수 있으니 반드시 현장 확인 후 계약하세요.",
        "rap5-hugo": "이 글은 국토교통부 실거래가 공공데이터를 기반으로 작성되었습니다. 투자 판단의 책임은 본인에게 있으며, 최신 정보는 [국토교통부 실거래가 공개시스템](https://rt.molit.go.kr)에서 확인하세요.",
    }
    disc = disclaimer_map.get(blog_id, disclaimer_map["rap-hugo"])
    parts.append(f"\n\n---\n\n> {disc}")

    # 7. 쿠팡 파트너스 면책
    _all_parts = "".join(parts)
    if "쿠팡 파트너스" not in _all_parts:
        parts.append("\n\n> 이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.")

    return body_md + "".join(parts)


def run(blog_cfg):
    """dispatcher에서 호출하는 통일 인터페이스"""
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"))

    # ★ RAP DB 일일 갱신 (첫 발행 시 자동 실행)
    try:
        from pipelines.rap.rap_data_sync import daily_refresh
        daily_refresh()
    except Exception as e:
        logger.warning(f"RAP DB 갱신 실패 (non-fatal): {e}")

    from shared.content_store import init_db, get_today_count
    from shared.publisher import publish
    from pipelines.rap.fetcher import fetch_apt_trade, fetch_subscription_info, fetch_subscription_from_db, find_lawd_cd, REGION_CD_MAP
    from pipelines.rap.writer import generate_trade_article, generate_subscription_article
    from pipelines.rap.thumbnail import upload_thumbnail

    blog_id = blog_cfg["id"]
    logger.info(f"RAP pipeline: {blog_id}")

    init_db()
    today_count = get_today_count(blog_id)
    daily_quota = blog_cfg.get("daily_quota", 5)
    if today_count >= daily_quota:
        logger.info(f"{blog_id} quota met: {today_count}/{daily_quota}")
        return {"success": False, "reason": "quota_met"}

    # 키워드 선택 (최대 5회 재시도, 데이터 매칭 실패 시 다음 키워드)
    MAX_KEYWORD_RETRY = 5
    _tried_keywords = set()
    article = None
    data_source = ""
    keyword = None
    kw_category = None

    for _attempt in range(MAX_KEYWORD_RETRY):
        keyword, kw_category = _pick_keyword(blog_id)
        if not keyword or keyword in _tried_keywords:
            if _attempt < MAX_KEYWORD_RETRY - 1:
                continue
            return {"success": False, "reason": "no_keyword"}
        _tried_keywords.add(keyword)

        strategy = _pick_strategy(keyword, blog_id)
        logger.info(f"{blog_id}: keyword={keyword}, strategy={strategy} (attempt {_attempt+1}/{MAX_KEYWORD_RETRY})")

        # ─── 실거래가 전략 ───
        if strategy == "trade":
            # 3차 방어: trade 진입 직전 최종 검증
            if any(p in keyword for p in TRADE_INCOMPATIBLE):
                logger.warning(f"3차 방어: trade 부적합 키워드 최종 차단: {keyword}")
                continue

            lawd_cd, city, district = find_lawd_cd(keyword)
            if not lawd_cd:
                logger.warning(f"{blog_id}: 법정동코드 미매칭, 키워드 스킵: {keyword}")
                continue

            trades = fetch_apt_trade(lawd_cd, rows=30)
            if not trades:
                from dateutil.relativedelta import relativedelta
                prev_ym = (datetime.now() - relativedelta(months=1)).strftime("%Y%m")
                trades = fetch_apt_trade(lawd_cd, deal_ymd=prev_ym, rows=30)

            if not trades:
                tg_error(blog_id, "fetcher", f"실거래가 0건: {keyword}")
                try:
                    db = RAP_DB_PATH if os.path.exists(RAP_DB_PATH) else GAP_DB_PATH
                    _gc = sqlite3.connect(db)
                    _gc.execute("UPDATE keywords SET status='inactive' WHERE keyword=?", (keyword,))
                    _gc.commit()
                    _gc.close()
                    logger.warning(f"키워드 자동 비활성화: {keyword} (실거래가 0건)")
                except Exception as _dbe:
                    logger.warning(f"키워드 비활성화 실패: {_dbe}")
                continue

            article = generate_trade_article(keyword, trades, region_info={"city": city, "district": district}, blog_id=blog_id)
            data_source = "molit_trade_api"

        # ─── 청약 전략 ───
        elif strategy == "subscription":
            # DB 기반 청약 공고 조회 (중복 자동 제외)
            region_nm = None
            for region in REGION_CD_MAP:
                if region in keyword:
                    region_nm = region
                    break

            subs = fetch_subscription_from_db(blog_id, keyword=keyword, region_nm=region_nm, limit=10)
            if not subs:
                logger.warning(f"{blog_id}: DB 청약 공고 0건, 키워드 스킵: {keyword}")
                continue

            article = generate_subscription_article(keyword, subs)
            data_source = "applyhome_db"

        if article:
            break
        else:
            if _attempt < MAX_KEYWORD_RETRY - 1:
                logger.warning(f"{blog_id}: 글 생성 실패, 다음 키워드 시도 ({_attempt+1}/{MAX_KEYWORD_RETRY})")
            continue

    if not article:
        return {"success": False, "reason": "write_failed"}

    # 썸네일
    article["title"] = sanitize_title(article["title"])
    thumb_url = upload_thumbnail(article["title"], article.get("category", "부동산"))

    # WordPress용 카테고리 ID
    wp_category = WP_CATEGORY_MAP.get(article.get("category", ""), 150)

    # 내부링크/CTA 삽입 (WordPress인 경우)
    body_html = None
    if blog_cfg.get("platform") == "wordpress":
        try:
            import markdown
            body_html = markdown.markdown(article["body_md"], extensions=["tables", "fenced_code"])
            from pipelines.gap.internal_links import process_gap_content
            body_html = process_gap_content(body_html, kw_category)
        except Exception as e:
            logger.warning(f"내부링크 삽입 실패: {e}")

    # 후처리 (면책조항 + 쿠팡 + 내부링크)
    article["body_md"] = _post_process(article["body_md"], blog_id, keyword)

    # ── 발행 전 검증 ──
    _is_draft = False
    try:
        from shared.validators import validate_post as _validate
        _val_ctx = {
            "keyword": keyword,
            "event_date": article.get("event_date", ""),
            "daily_quota": article.get("daily_quota", 5),
        }
        _issues = _validate(blog_id, article.get("title", ""), article["body_md"], _val_ctx)
        if _issues:
            _is_draft = True
            logger.warning(f"[Validate] {len(_issues)} issues → draft: {_issues}")
    except Exception as _ve:
        logger.warning(f"[Validate] Error (non-fatal): {_ve}")
    article["is_draft"] = _is_draft

    # 발행
    result = publish(
        blog_id=blog_id,
        title=article["title"],
        body_md=article["body_md"],
        body_html=body_html,
        category=article.get("category", "부동산"),
        is_draft=article.get("is_draft", False),
        tags=article.get("tags", ""),
        data_source=data_source,
        source_id=keyword,
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        thumbnail_url=thumb_url,
        wp_category=wp_category,
    )

    if result and result.get("success"):
        logger.info(f"RAP 발행 성공: {article['title']}")

        # ★ RAP DB에 발행 기록 (중복 방지)
        try:
            rap_conn = sqlite3.connect(RAP_DB_PATH)
            rap_conn.execute(
                "INSERT OR IGNORE INTO publish_log (blog_id, data_type, data_key, title) VALUES (?,?,?,?)",
                (blog_id, strategy, keyword, article["title"])
            )
            rap_conn.commit()
            rap_conn.close()
        except Exception as e:
            logger.warning(f"RAP publish_log 기록 실패: {e}")

        # 백링크 자동 생성
        try:
            from shared.backlink_publisher import post_publish_backlinks
            published_url = result.get("url", "")
            if published_url and article.get("body_md"):
                bl_results = post_publish_backlinks(
                    title=article["title"],
                    body_md=article["body_md"],
                    original_url=published_url,
                    blog_id=blog_id,
                )
                if bl_results:
                    logger.info(f"{blog_id}: 백링크 {len(bl_results)}개 생성")
        except Exception as e:
            logger.warning(f"백링크 생성 실패: {e}")
    else:
        reason = (result or {}).get("reason", "publish_failed")
        tg_error(blog_id, "publish", f"{keyword}: {reason}")

    if result and result.get("deploy_error"):
        tg_error(blog_id, "deploy", result["deploy_error"][:300])

    return result or {"success": False, "reason": "publish_failed"}

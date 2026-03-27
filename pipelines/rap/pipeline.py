"""RAP (Real estate Auto Publisher) pipeline — GAP 구조 기반"""
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

GAP_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "gap.db")

# 부동산 카테고리 목록
RAP_CATEGORIES = ("금융/부동산",)

# 키워드 → 전략 매핑
TRADE_PATTERNS = ["실거래", "매매", "시세", "집값", "아파트", "공시지가", "빌라", "오피스텔"]
SUB_PATTERNS = ["청약", "분양", "LH", "행복주택", "임대", "전세"]

# blog_id별 키워드 필터 패턴
BLOG_KEYWORD_FILTER = {
    "rap-hugo":  ["아파트", "매매", "시세", "실거래", "집값", "공시지가", "빌라", "오피스텔",
                  "은마", "재건축", "재개발", "부동산", "드림타운", "레지던스",
                  "단지", "미소지움", "아르티스", "트인시아", "펠루시드", "팰루시드",
                  "S클래스", "브라이튼", "에테르노", "디아이엘", "하이니티", "비스타",
                  "건설", "냉난방", "전원주택", "모아타운", "아페르", "라엘",
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
    """blog_id에 맞는 부동산 키워드 선택"""
    conn = sqlite3.connect(GAP_DB_PATH)
    try:
        patterns = BLOG_KEYWORD_FILTER.get(blog_id, [])
        rows = conn.execute(
            "SELECT keyword, category FROM keywords "
            "WHERE category = '금융/부동산' AND status = 'active' "
            "ORDER BY use_count ASC, last_used_at ASC NULLS FIRST "
            "LIMIT 100",
        ).fetchall()
        
        if patterns:
            filtered = [(kw, cat) for kw, cat in rows if any(p in kw for p in patterns)]
            if filtered:
                rows = filtered
        
        if not rows:
            logger.warning(f"{blog_id}: 사용 가능한 부동산 키워드 없음")
            return None, None
        
        keyword, category = random.choice(rows[:20])
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


def _pick_strategy(keyword, blog_id=None):
    """blog_id에 따라 전략 결정, 없으면 키워드 기반"""
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
    # GPT가 넣은 쿠팡 상품 추천 섹션도 제거
    # GPT 자체 쿠팡 섹션 제거 (H2부터 다음 H2 또는 ---까지)
    _gpt_section_keywords = ["자취", "신혼", "프리미엄 입주", "추천 가전", "필수 아이템",
                              "입주 준비", "이사 준비", "원룸 필수", "추천 용품"]
    # 시스템이 삽입하는 제목은 제거하지 않음
    _SYSTEM_TITLES = ["부동산 거래 시 유용한 추천 상품", "차량 관리에 도움되는 추천 용품", "여행 준비에 도움되는 추천 용품"]
    for _gsk in _gpt_section_keywords:
        while True:
            _gi = body_md.find("## " + _gsk)
            if _gi < 0:
                # 부분 매칭: "## 자취·원룸" 같은 경우
                _gi2 = body_md.find("## ")
                _found = False
                while _gi2 >= 0:
                    _line_end = body_md.find("\n", _gi2)
                    if _line_end < 0:
                        _line_end = len(body_md)
                    _header = body_md[_gi2:_line_end]
                    if _gsk in _header:
                        # 시스템 삽입 제목이면 스킵
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
            # 다음 H2 또는 --- 찾기
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
            # H2 3번째 뒤에 삽입
            _h2_positions = [m.start() for m in _re.finditer(r'^## ', body_md, _re.MULTILINE)]
            if len(_h2_positions) >= 4:
                _insert_pos = _h2_positions[3]
                body_md = body_md[:_insert_pos] + _card_html + body_md[_insert_pos:]
                logger.info("중간 이탈방지 카드 삽입 완료")
    except Exception as e:
        logger.warning(f"중간 카드 삽입 실패: {e}")

    # GPT가 생성한 모든 내부링크/추천글 섹션 제거 (시스템이 별도 삽입)
    # 다음 ##까지 또는 문서 끝까지만 제거 (DOTALL 제거하여 과잉삭제 방지)
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

    # 3. 쿠팡 파트너스 (blog_id별 키워드는 coupang_travel.py TRAVEL_KEYWORD_MAP에서 관리)
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

    # 4. 네이버지도 버튼 (지역/단지명 기반 — 비지역 키워드 스킵)
    _NO_MAP_KEYWORDS = [
        "세금", "양도", "취득세", "종부세", "공시지가", "보증보험", "계약서",
        "임대차", "3법", "청약", "당첨", "확률", "일정", "신청", "공고",
        "청년", "LH", "임대주택", "공공임대", "행복주택", "안심주택",
        "가이드", "총정리", "핵심", "방법", "높이는", "실거래가", "전세사기",
        "단기임대", "체크리스트", "아파트실거래가", "아파트매매",
        "2주택", "1가구", "종합부동산세", "보증금", "확정일자",
    ]
    _skip_map = any(nk in keyword for nk in _NO_MAP_KEYWORDS) if keyword else True
    try:
        import urllib.parse as _up
        if _skip_map:
            logger.info(f"네이버지도 스킵 (비지역 키워드): {keyword}")
            raise ValueError("skip")
        # 키워드에서 지역명이나 단지명 추출
        map_query = keyword.strip()
        if not map_query:
            raise ValueError("empty keyword")
        # 블로그별 지도 검색 최적화
        map_label = {
            "rap-hugo": "아파트 매물",
            "rap2-hugo": "청약 단지",
            "rap3-hugo": "부동산 중개",
            "rap4-hugo": "전세 매물",
            "rap5-hugo": "아파트 단지",
        }
        label = map_label.get(blog_id, "부동산")
        encoded = _up.quote(f"{map_query} {label}")
        naver_map_html = f"""

<div style="margin:24px 0;padding:16px 20px;background:#f0f7ff;border-radius:12px;border:1px solid #d0e3ff;text-align:center;">
  <p style="margin:0 0 10px 0;font-size:1.05rem;font-weight:600;">📍 {map_query} 주변 지도로 확인하기</p>
  <a href="https://map.naver.com/v5/search/{encoded}" target="_blank" rel="nofollow" style="display:inline-block;padding:10px 24px;background:#03C75A;color:white;border-radius:8px;text-decoration:none;font-weight:600;">네이버지도에서 보기</a>
</div>
"""
        parts.append(naver_map_html)
        logger.info(f"네이버지도 버튼 삽입: {map_query}")
    except Exception as e:
        logger.warning(f"네이버지도 삽입 실패: {e}")

    # 5. 내부링크 (같은 사이트 기존 글 추천)
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

    # 6. 면책조항 (1회만)
    disclaimer_map = {
        "rap-hugo": "이 글은 국토교통부 실거래가 공공데이터를 기반으로 작성되었습니다. 투자 판단의 책임은 본인에게 있으며, 최신 정보는 [국토교통부 실거래가 공개시스템](https://rt.molit.go.kr)에서 확인하세요.",
        "rap2-hugo": "이 글은 한국부동산원 청약홈 공공데이터를 기반으로 작성되었습니다. 정확한 청약 일정과 자격은 [청약홈](https://www.applyhome.co.kr)에서 확인하세요.",
        "rap3-hugo": "이 글은 국토교통부 실거래가 데이터를 기반으로 작성되었으며, 세금 계산은 참고용입니다. 정확한 세금 상담은 세무사에게 문의하세요.",
        "rap4-hugo": "이 글은 국토교통부 전월세 공공데이터를 기반으로 작성되었습니다. 계약 전 반드시 등기부등본을 확인하고, 전세보증보험 가입을 권장합니다.",
        "rap5-hugo": "이 글은 국토교통부 실거래가 공공데이터를 기반으로 작성되었습니다. 투자 판단의 책임은 본인에게 있으며, 최신 정보는 [국토교통부 실거래가 공개시스템](https://rt.molit.go.kr)에서 확인하세요.",
    }
    disc = disclaimer_map.get(blog_id, disclaimer_map["rap-hugo"])
    parts.append(f"\n\n---\n\n> {disc}")

    # 7. 쿠팡 파트너스 면책 (CoupangTravel 반환값에 미포함 시에만 추가)
    _all_parts = "".join(parts)
    if "쿠팡 파트너스" not in _all_parts:
        parts.append("\n\n> 이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.")

    return body_md + "".join(parts)


def run(blog_cfg):
    """dispatcher에서 호출하는 통일 인터페이스"""
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"))
    from shared.content_store import init_db, get_today_count
    from shared.publisher import publish
    from pipelines.rap.fetcher import fetch_apt_trade, fetch_subscription_info, find_lawd_cd, REGION_CD_MAP
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

    # 키워드 선택
    keyword, kw_category = _pick_keyword(blog_id)
    if not keyword:
        return {"success": False, "reason": "no_keyword"}

    strategy = _pick_strategy(keyword, blog_id)
    logger.info(f"{blog_id}: keyword={keyword}, strategy={strategy}")

    article = None
    data_source = ""

    # ─── 실거래가 전략 ───
    if strategy == "trade":
        lawd_cd, city, district = find_lawd_cd(keyword)
        if not lawd_cd:
            # 블로그별 다른 지역 풀에서 랜덤 선택
            import random as _rand
            BLOG_REGION_POOL = {
                "rap-hugo":  [("11680","서울","강남구"), ("11650","서울","서초구"), ("11710","서울","송파구"),
                              ("11440","서울","마포구"), ("11560","서울","영등포구"), ("11200","서울","성동구")],
                "rap3-hugo": [("11680","서울","강남구"), ("11650","서울","서초구"), ("11710","서울","송파구"),
                              ("11170","서울","용산구"), ("11500","서울","강서구")],
                "rap4-hugo": [("11440","서울","마포구"), ("11200","서울","성동구"), ("11215","서울","광진구"),
                              ("11620","서울","관악구"), ("11590","서울","동작구"), ("11470","서울","양천구")],
                "rap5-hugo": [("11680","서울","강남구"), ("11650","서울","서초구"), ("11710","서울","송파구"),
                              ("11560","서울","영등포구"), ("11170","서울","용산구")],
            }
            pool = BLOG_REGION_POOL.get(blog_id, [("11680","서울","강남구")])
            lawd_cd, city, district = _rand.choice(pool)
            logger.info(f"법정동코드 미매칭, 랜덤 선택: {city} {district}")

        trades = fetch_apt_trade(lawd_cd, rows=30)
        if not trades:
            from dateutil.relativedelta import relativedelta
            prev_ym = (datetime.now() - relativedelta(months=1)).strftime("%Y%m")
            trades = fetch_apt_trade(lawd_cd, deal_ymd=prev_ym, rows=30)

        if not trades:
            tg_error(blog_id, "fetcher", f"실거래가 0건: {keyword}")
            # 실거래가 0건 키워드 자동 비활성화 (동탄호수공원 같은 비아파트 키워드 방지)
            try:
                import sqlite3 as _sq3
                _gc = _sq3.connect(GAP_DB_PATH)
                _gc.execute("UPDATE keywords SET status='inactive' WHERE keyword=?", (keyword,))
                _gc.commit()
                _gc.close()
                logger.warning(f"키워드 자동 비활성화: {keyword} (실거래가 0건)")
            except Exception as _dbe:
                logger.warning(f"키워드 비활성화 실패: {_dbe}")
            return {"success": False, "reason": "no_trade_data"}

        article = generate_trade_article(keyword, trades, region_info={"city": city, "district": district}, blog_id=blog_id)
        data_source = "molit_trade_api"

    # ─── 청약 전략 ───
    elif strategy == "subscription":
        region_cd = None
        for region, code in REGION_CD_MAP.items():
            if region in keyword:
                region_cd = code
                break

        subs = fetch_subscription_info(region_cd=region_cd, page_size=10)
        if not subs:
            tg_error(blog_id, "fetcher", f"청약 공고 0건: {keyword}")
            return {"success": False, "reason": "no_subscription_data"}

        article = generate_subscription_article(keyword, subs)
        data_source = "applyhome_api"

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

    # ── 발행 전 검증 (문제 시 draft, 텔레그램 경고) ──
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

        # 백링크 자동 생성 (Phase 1: Telegraph)
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

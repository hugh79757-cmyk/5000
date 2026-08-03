"""RAP (Real estate Auto Publisher) pipeline — RAP 전용 DB 사용"""
import hashlib
import logging
import os
import random
import sqlite3
from datetime import datetime

from shared.validators import assert_korean_or_reject, sanitize_title

logger = logging.getLogger(__name__)

try:
    from shared.telegram_notifier import send_error as tg_error
except ImportError:
    def tg_error(*a, **k) -> None:
        return None

RAP_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "rap.db")
GAP_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "gap.db")

# 부동산 무관 키워드 제외 패턴
RAP_EXCLUDE = [
    "기능사", "요리", "조리", "흑백", "레시피", "양식조리", "제과", "봉제",
    "롤러운전", "콘크리트", "전자기능", "주조", "인베디드", "견적서",
    "운세", "로또", "날씨", "웹툰", "게임", "파전", "킷트", "래시피",
    "키친보스", "오스틴강", "이탈리안", "이탈리아", "명태살", "1분링",
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
                  "단지", "미소지움", "아르티스", "트인시아", "펠루시드", "팰루시드",
                  "S클래스", "브라이튼", "에테르노", "디아이엘", "하이니티", "비스타",
                  "건설", "냉난방", "전원주택", "모아타운", "아페르", "라엘",
                  "서울아파트", "동탄"],
    "rap2-hugo": ["청약", "분양", "LH", "행복주택", "임대주택", "청년주택", "청년안심",
                  "국민임대", "영구임대", "매입임대", "신혼희망"],
    "rap3-hugo": ["양도", "취득세", "상속세", "증여세", "세금", "과세", "공시지가", "재산세",
                  "종부세", "종합부동산세", "절세", "세율", "면제"],
    "rap4-hugo": ["전세", "월세", "보증금", "임대차", "전월세", "반전세",
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
    conn = sqlite3.connect(db_path, timeout=30)
    try:
        patterns = BLOG_KEYWORD_FILTER.get(blog_id, [])

        if db_path == RAP_DB_PATH:
            # RAP DB: blog_target 필터 우선
            rows = conn.execute(
                "SELECT keyword, category FROM keywords "
                "WHERE status='active' AND (blog_target=? OR blog_target IS NULL OR blog_target='') "
                "ORDER BY use_count ASC, last_used_at ASC NULLS FIRST "
                "LIMIT 200",
                (blog_id,)
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
            rap_conn = sqlite3.connect(RAP_DB_PATH, timeout=30) if db_path != RAP_DB_PATH else conn
            published = {r[0] for r in rap_conn.execute(
                "SELECT data_key FROM publish_log "
                "WHERE blog_id=? AND published_at >= datetime('now', '-7 days')",
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



def _fetch_rents_from_db(lawd_cd, keyword, months=3):
    """rap4-hugo 전용 — rents 테이블에서 전월세 데이터 조회"""
    if not os.path.exists(RAP_DB_PATH):
        logger.error(f"rap.db 없음: {RAP_DB_PATH}")
        return []
    try:
        from dateutil.relativedelta import relativedelta
        now = datetime.now()
        ymd_list = [(now - relativedelta(months=i)).strftime("%Y%m") for i in range(months)]
        placeholders = ",".join("?" * len(ymd_list))

        conn = sqlite3.connect(RAP_DB_PATH, timeout=30)

        # rents 테이블 존재 여부 확인
        tbl = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='rents'"
        ).fetchone()
        if not tbl:
            logger.warning("rents 테이블 없음 — sync_rents() 미실행 상태")
            conn.close()
            return []

        rows = conn.execute(
            f"SELECT apt_name, dong_name, exclu_use_ar, floor, build_year, "
            f"deposit, monthly_rent, rent_type, deal_year, deal_month, deal_day "
            f"FROM rents WHERE lawd_cd=? AND deal_ymd IN ({placeholders}) "
            f"ORDER BY deal_ymd DESC, deposit DESC",
            [lawd_cd, *ymd_list]
        ).fetchall()
        conn.close()

        if not rows:
            return []

        all_rents = []
        for r in rows:
            all_rents.append({
                "aptNm":          r[0] or "",
                "umdNm":          r[1] or "",
                "excluUseAr":     str(r[2] or ""),
                "floor":          str(r[3] or ""),
                "buildYear":      str(r[4] or ""),
                "deposit":        str(r[5] or 0),
                "depositInt":     r[5] or 0,
                "monthlyRent":    str(r[6] or 0),
                "monthlyRentInt": r[6] or 0,
                "rentType":       r[7] or "전세",
                "dealYear":       str(r[8] or ""),
                "dealMonth":      str(r[9] or ""),
                "dealDay":        str(r[10] or ""),
            })

        # 키워드 단지명 필터 (trades와 동일 로직)
        import re as _re2
        _SUFFIX_PAT = _re2.compile(
            r"^(실거래가|전세|월세|세금|브랜드|시세|매매|아파트|분석|가이드|"
            r"서울|경기|인천|부산|대구|대전|광주|울산|세종|"
            r".+특별시|.+광역시|.+특별자치시|.+특별자치도|"
            r".+구|.+시|.+군|.+동|.+읍|.+면|.+로|.+대로)$"
        )
        tokens = keyword.strip().split()
        apt_kw = " ".join(t for t in tokens if not _SUFFIX_PAT.match(t)).strip()

        # 아파트명이 추출되지 않은 비아파트 키워드 → 구 전체 데이터 반환
        NON_APT_KEYWORDS = ["체크리스트", "예방", "가이드", "방법", "절차", "주의사항"]
        is_non_apt = not apt_kw or any(k in apt_kw for k in NON_APT_KEYWORDS)
        if is_non_apt:
            logger.info(f"비아파트 키워드 [{keyword}] → 구 전체 {len(all_rents)}건 반환")
            return {
                "apt_kw":         keyword,
                "keyword_trades": [],
                "other_trades":   all_rents[:20],
                "data_type":      "rent",
            }

        def _match(apt_name) -> bool:
            n = (apt_name or "").strip()
            if not apt_kw:
                return False
            # 완전일치 우선
            if n == apt_kw:
                return True
            # apt_kw가 n에 포함 — 최소 3자 이상만 부분매칭 허용
            # (예: "청담자이" in "청담자이104동", "삼호3" in "삼호3차아파트")
            if len(apt_kw) >= 3 and apt_kw in n:
                idx = n.index(apt_kw)
                before_ok = (idx == 0 or not n[idx-1].isalnum())
                after_idx = idx + len(apt_kw)
                after_char = n[after_idx] if after_idx < len(n) else ""
                last_kw_char = apt_kw[-1] if apt_kw else ""
                after_ok = (
                    not after_char
                    or not after_char.isalnum()
                    or (last_kw_char.isdigit()
                        and "가" <= after_char <= "힣")
                )
                if before_ok and after_ok:
                    return True
            # 역방향 매칭 제거 — "대치팰리스" in "래미안대치팰리스" 오매칭 방지
            return False
        filtered = [r for r in all_rents if _match(r["aptNm"])]
        others   = [r for r in all_rents if not _match(r["aptNm"])]

        if filtered:
            logger.info(f"전월세 단지 필터: [{apt_kw}] {len(filtered)}건 + 구내 {len(others)}건")
        else:
            logger.info(f"전월세 단지 미매칭 [{apt_kw}] → 구 전체 {len(all_rents)}건")

        return {
            "apt_kw":         apt_kw,
            "keyword_trades": filtered[:10],
            "other_trades":   others[:20],
            "data_type":      "rent",
        }

    except Exception as e:
        logger.exception(f"DB rents 조회 실패: {e}")
        return []




BRAND_KEYWORDS = [
    "래미안", "자이", "힐스테이트", "푸르지오", "아이파크", "롯데캐슬",
    "더샵", "e편한세상", "아크로", "디에이치", "헬리오시티", "파크리오",
    "SK뷰", "위브", "센트럴", "풍림아이원", "트리우스", "드파인",
]

def _fetch_brand_trades_from_db(keyword, months=3):
    """rap5-hugo 전용 — 키워드에서 브랜드명 추출 후 전국 LIKE 검색"""
    import re as _re

    from dateutil.relativedelta import relativedelta

    if not os.path.exists(RAP_DB_PATH):
        logger.error(f"rap.db 없음: {RAP_DB_PATH}")
        return None

    # 키워드에서 브랜드명 추출
    brand_kw = None
    for brand in BRAND_KEYWORDS:
        if brand in keyword:
            brand_kw = brand
            break

    # 브랜드 미매칭 시 apt_kw 전체를 단지명으로 사용
    if not brand_kw:
        _SUFFIX_PAT = _re.compile(
            r"^(실거래가|전세|월세|세금|브랜드|시세|매매|아파트|분석|가이드|"
            r"서울|경기|인천|부산|대구|대전|광주|울산|세종|"
            r".+특별시|.+광역시|.+특별자치시|.+특별자치도|"
            r".+구|.+시|.+군|.+동|.+읍|.+면|.+로|.+대로)$"
        )
        tokens = keyword.strip().split()
        apt_kw = " ".join(t for t in tokens if not _SUFFIX_PAT.match(t)).strip()
        brand_kw = apt_kw or None

    if not brand_kw:
        logger.warning(f"rap5 브랜드 추출 실패: {keyword}")
        return None

    try:
        now = datetime.now()
        ymd_list = [(now - relativedelta(months=i)).strftime("%Y%m") for i in range(months)]
        placeholders = ",".join("?" * len(ymd_list))

        conn = sqlite3.connect(RAP_DB_PATH, timeout=30)
        rows = conn.execute(
            f"SELECT apt_name, dong_name, exclu_use_ar, floor, build_year, "
            f"deal_amount, deal_year, deal_month, deal_day, city, district "
            f"FROM trades WHERE apt_name LIKE ? AND deal_ymd IN ({placeholders}) "
            f"ORDER BY deal_ymd DESC, deal_amount DESC",
            [f"%{brand_kw}%", *ymd_list]
        ).fetchall()
        conn.close()

        if not rows:
            logger.warning(f"rap5 브랜드 [{brand_kw}] 전국 거래 0건")
            return None

        all_trades = []
        for r in rows:
            amt = r[5] or 0
            all_trades.append({
                "aptNm":         r[0] or "",
                "umdNm":         r[1] or "",
                "excluUseAr":    str(r[2] or ""),
                "floor":         str(r[3] or ""),
                "buildYear":     str(r[4] or ""),
                "dealAmount":    f"{amt:,}",
                "dealAmountInt": amt,
                "dealYear":      str(r[6] or ""),
                "dealMonth":     str(r[7] or ""),
                "dealDay":       str(r[8] or ""),
                "city":          r[9] or "",
                "district":      r[10] or "",
            })

        # 키워드 단지명과 정확히 매칭되는 거래 우선 분리
        _SUFFIX_PAT2 = _re.compile(
            r"^(실거래가|전세|월세|세금|브랜드|시세|매매|아파트|분석|가이드|"
            r"서울|경기|인천|부산|대구|대전|광주|울산|세종|"
            r".+특별시|.+광역시|.+특별자치시|.+특별자치도|"
            r".+구|.+시|.+군|.+동|.+읍|.+면|.+로|.+대로)$"
        )
        tokens2 = keyword.strip().split()
        apt_kw2 = " ".join(t for t in tokens2 if not _SUFFIX_PAT2.match(t)).strip()

        if apt_kw2 and len(apt_kw2) >= 3:
            keyword_trades = [t for t in all_trades if apt_kw2 in t["aptNm"]]
            other_trades   = [t for t in all_trades if apt_kw2 not in t["aptNm"]]
        else:
            keyword_trades = []
            other_trades   = all_trades

        logger.info(
            f"rap5 브랜드 [{brand_kw}] 전국 {len(all_trades)}건 "
            f"(단지매칭 {len(keyword_trades)}건 + 동일브랜드 {len(other_trades)}건)"
        )

        return {
            "apt_kw":         apt_kw2 or brand_kw,
            "brand_kw":       brand_kw,
            "keyword_trades": keyword_trades[:10],
            "other_trades":   other_trades[:20],
            "data_type":      "brand",
        }

    except Exception as e:
        logger.exception(f"rap5 브랜드 DB 조회 실패: {e}")
        return None

def _fetch_trades_from_db(lawd_cd, keyword, months=3, blog_id=None):
    # ── rap4-hugo: rents 테이블 조회 분기 ──
    if blog_id == "rap4-hugo":
        result = _fetch_rents_from_db(lawd_cd, keyword, months)
        if result:
            return result
        logger.warning("rents 0건 → trades 폴백 (rap4-hugo)")


    # ── rap5-hugo: 전국 브랜드명 LIKE 검색 분기 ──
    if blog_id == "rap5-hugo":
        result = _fetch_brand_trades_from_db(keyword, months)
        if result:
            return result
        logger.warning("브랜드 trades 0건 → 지역 폴백 (rap5-hugo)")

    """rap.db/trades에서 실거래가 조회 + 키워드 단지명 필터링
    1순위: 키워드에서 추출한 단지명과 매칭되는 거래
    2순위: 매칭 3건 미만이면 구 전체 반환 (분석용)
    """
    if not os.path.exists(RAP_DB_PATH):
        logger.error(f"rap.db 없음: {RAP_DB_PATH}")
        return []
    try:
        from dateutil.relativedelta import relativedelta
        now = datetime.now()
        ymd_list = [(now - relativedelta(months=i)).strftime("%Y%m") for i in range(months)]
        placeholders = ",".join("?" * len(ymd_list))

        conn = sqlite3.connect(RAP_DB_PATH, timeout=30)
        rows = conn.execute(
            f"SELECT apt_name, dong_name, exclu_use_ar, floor, build_year, "
            f"deal_amount, deal_year, deal_month, deal_day "
            f"FROM trades WHERE lawd_cd=? AND deal_ymd IN ({placeholders}) "
            f"ORDER BY deal_ymd DESC, deal_amount DESC",
            [lawd_cd, *ymd_list]
        ).fetchall()
        conn.close()

        if not rows:
            return []

        # dict 변환 (fetch_apt_trade 반환 형식과 동일)
        all_trades = []
        for r in rows:
            amt = r[5] or 0
            all_trades.append({
                "aptNm":        r[0] or "",
                "umdNm":        r[1] or "",
                "excluUseAr":   str(r[2] or ""),
                "floor":        str(r[3] or ""),
                "buildYear":    str(r[4] or ""),
                "dealAmount":   f"{amt:,}",
                "dealAmountInt": amt,
                "dealYear":     str(r[6] or ""),
                "dealMonth":    str(r[7] or ""),
                "dealDay":      str(r[8] or ""),
            })

        # 키워드에서 단지명 추출 (토큰 단위로 지역/용도 제거)
        import re as _re2
        _SUFFIX_PAT = _re2.compile(
            r"^(실거래가|전세|월세|세금|브랜드|시세|매매|아파트|분석|가이드|"
            r"서울|경기|인천|부산|대구|대전|광주|울산|세종|"
            r".+특별시|.+광역시|.+특별자치시|.+특별자치도|"
            r".+구|.+시|.+군|.+동|.+읍|.+면|.+로|.+대로)$"
        )
        tokens = keyword.strip().split()
        apt_kw = " ".join(t for t in tokens if not _SUFFIX_PAT.match(t)).strip()

        def _match(apt_name) -> bool:
            n = (apt_name or "").strip()
            if not apt_kw:
                return False
            # 완전일치 우선
            if n == apt_kw:
                return True
            # apt_kw가 n에 포함 — 최소 3자 이상만 부분매칭 허용
            # (예: "청담자이" in "청담자이104동", "삼호3" in "삼호3차아파트")
            if len(apt_kw) >= 3 and apt_kw in n:
                idx = n.index(apt_kw)
                before_ok = (idx == 0 or not n[idx-1].isalnum())
                after_idx = idx + len(apt_kw)
                after_char = n[after_idx] if after_idx < len(n) else ""
                last_kw_char = apt_kw[-1] if apt_kw else ""
                after_ok = (
                    not after_char
                    or not after_char.isalnum()
                    or (last_kw_char.isdigit()
                        and "가" <= after_char <= "힣")
                )
                if before_ok and after_ok:
                    return True
            # 역방향 매칭 제거 — "대치팰리스" in "래미안대치팰리스" 오매칭 방지
            return False
        filtered = [t for t in all_trades if _match(t["aptNm"])]
        others   = [t for t in all_trades if not _match(t["aptNm"])]

        if len(filtered) >= 1:
            logger.info(f"단지 필터: [{apt_kw}] {len(filtered)}건 + 구내 {len(others)}건")
        else:
            logger.info(f"단지 미매칭 [{apt_kw}] → 구 전체 {len(all_trades)}건")

        # keyword_trades / other_trades 분리 반환 (AI 혼동 방지)
        return {
            "apt_kw":         apt_kw,
            "keyword_trades": filtered[:10],
            "other_trades":   others[:20],
        }

    except Exception as e:
        logger.exception(f"DB trades 조회 실패: {e}")
        return []

def _post_process(body_md, blog_id, keyword):
    # 금지어 자동 치환
    body_md = body_md.replace("특히 ", "").replace("특히, ", "")
    body_md = body_md.replace("특히,", "").replace("  ", " ")

    """발행 전 후처리: 금지표현 제거 + 면책조항 + 쿠팡 + 내부링크"""
    import glob as _gl2
    import random as _rand2
    import re as _re

    # 0. 내부링크 상단 삽입
    try:
        blog_cfg_map = {
            "rap-hugo":  "/Users/twinssn/Projects/RAP/rap-hugo",
            "rap2-hugo": "/Users/twinssn/Projects/RAP/rap2-hugo",
            "rap3-hugo": "/Users/twinssn/Projects/RAP/rap3-hugo",
            "rap4-hugo": "/Users/twinssn/Projects/RAP/rap4-hugo",
            "rap5-hugo": "/Users/twinssn/Projects/RAP/rap5-hugo",
        }
        posts_dir = os.path.join(blog_cfg_map.get(blog_id, ""), "content", "posts")
        _top_posts = []
        for md in _gl2.glob(os.path.join(posts_dir, "*/index.md")):
            with open(md, encoding="utf-8") as f:
                head = f.read(500)
            tm = _re.search(r'^title:\s*["\'](.*?)["\']', head, _re.MULTILINE)
            sm = _re.search(r'^slug:\s*["\'](.*?)["\']', head, _re.MULTILINE)
            if tm and sm:
                _top_posts.append({"title": tm.group(1), "slug": sm.group(1)})
        if len(_top_posts) >= 2:
            _top_picks = _rand2.sample(_top_posts, min(2, len(_top_posts)))
            _top_links = "**함께 읽으면 좋은 글**\n"
            for p in _top_picks:
                _top_links += f'- [{p["title"]}](/posts/{p["slug"]}/)\n'
            body_md = _top_links + "\n---\n\n" + body_md
            logger.info("내부링크 상단 삽입 완료")
    except Exception as e:
        logger.warning(f"내부링크 상단 삽입 실패: {e}")

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

    # 1-0. 표 깨짐 복원 — 마크다운 table separator 행 수정
    _lines = body_md.split("\n")
    for _i, _line in enumerate(_lines):
        if _re.match(r"^\|[\|\-:\s]+\|$", _line):
            _j = _i - 1
            while _j >= 0 and not _lines[_j].strip():
                _j -= 1
            if _j >= 0 and _lines[_j].strip().startswith("|"):
                _col_count = _lines[_j].count("|") - 1
                if _col_count >= 1:
                    _lines[_i] = "|" + "---|" * _col_count
    body_md = "\n".join(_lines)

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
            _card_html = f"""

<div style="margin:28px 0;padding:18px 22px;background:linear-gradient(135deg,#f8f9ff 0%,#e8f4fd 100%);border-radius:14px;border-left:4px solid #3182ce;">
  <p style="margin:0 0 6px 0;font-size:0.85rem;color:#718096;">📌 놓치면 아쉬운 글</p>
  <a href="/posts/{_pick['slug']}/" style="font-size:1.05rem;font-weight:600;color:#2d3748;text-decoration:none;">{_pick['title']}</a>
</div>

"""
            _h2_positions = [m.start() for m in _re.finditer(r"^## ", body_md, _re.MULTILINE)]
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
        "rap4-hugo": "이 글은 국토교통부 전월세 실거래가 공공데이터를 기반으로 작성되었습니다. 실제 계약 전 반드시 현장 확인 및 등기부등본을 확인하세요.",
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

    # ★ RAP DB 일일 갱신 (첫 발행 시 자동 실행, 최대 120초)
    try:
        import threading as _th

        from pipelines.rap.rap_data_sync import daily_refresh
        _result = []
        _err = []
        def _run_refresh() -> None:
            try:
                _result.append(daily_refresh())
            except Exception as _e:
                _err.append(_e)
        _t = _th.Thread(target=_run_refresh, daemon=True)
        _t.start()
        _t.join(120)
        if _t.is_alive():
            logger.warning("RAP DB 갱신 120초 초과 — 타임아웃 (non-fatal)")
        elif _err:
            raise _err[0]
    except Exception as e:
        logger.warning(f"RAP DB 갱신 실패 (non-fatal): {e}")

    from pipelines.rap.fetcher import (
        REGION_CD_MAP,
        fetch_subscription_info,
        find_lawd_cd,
    )
    from shared.thumbnail_generator import generate_image_thumbnail
    from pipelines.rap.writer import generate_subscription_article, generate_trade_article
    from shared.content_store import get_today_count, init_db
    from shared.publisher import publish

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

        # ── rap.db에서 실거래가 조회 (API 호출 없음) ──
        trades = _fetch_trades_from_db(lawd_cd, keyword, blog_id=blog_id)


        # ── 제목-데이터 불일치 방지: 실거래 없는 단지명은 제목에서 제거 ──
        if blog_id != "rap5-hugo" and isinstance(trades, dict) and not trades.get("keyword_trades") \
                and trades.get("apt_kw") and district:
            _title_keyword = f"{district} 실거래가 종합"
            logger.info(f"단지 실거래 없음 → 제목 키워드 교체: [{keyword}] → [{_title_keyword}]")
            keyword = _title_keyword
        if not trades:
            tg_error(blog_id, "fetcher", f"실거래가 0건: {keyword}")
            try:
                if os.path.exists(RAP_DB_PATH):
                    _gc = sqlite3.connect(RAP_DB_PATH, timeout=30)
                    _gc.execute("UPDATE keywords SET status='inactive' WHERE keyword=?", (keyword,))
                    _gc.commit()
                    _gc.close()
                logger.warning(f"키워드 자동 비활성화: {keyword} (실거래가 0건)")
            except Exception as _dbe:
                logger.warning(f"키워드 비활성화 실패: {_dbe}")
            return {"success": False, "reason": "no_trade_data"}

        article = generate_trade_article(keyword, trades, region_info={"city": city, "district": district}, blog_id=blog_id)
        data_source = "rap_db"

    # ─── 청약 전략 ───
    elif strategy == "subscription":
        # 1순위: DB에서 키워드 지역 매칭 공고 조회
        subs = []
        if os.path.exists(RAP_DB_PATH):
            try:
                _sc = sqlite3.connect(RAP_DB_PATH, timeout=30)
                # 키워드에서 지역명 추출해 DB 매칭
                _region_tokens = [r for r in REGION_CD_MAP if r in keyword]
                if _region_tokens:
                    _placeholders = ",".join("?" * len(_region_tokens))
                    _subs_rows = _sc.execute(
                        f"SELECT pan_nm, pan_type, region_nm, pan_start, pan_end, pan_status, detail_url "
                        f"FROM subscriptions WHERE region_nm IN ({_placeholders}) "
                        f"ORDER BY pan_start DESC LIMIT 15",
                        _region_tokens
                    ).fetchall()
                else:
                    # 지역 토큰 없으면 pan_nm 키워드 직접 매칭
                    _subs_rows = _sc.execute(
                        "SELECT pan_nm, pan_type, region_nm, pan_start, pan_end, pan_status, detail_url "
                        "FROM subscriptions WHERE pan_nm LIKE ? "
                        "ORDER BY pan_start DESC LIMIT 15",
                        (f"%{keyword[:4]}%",)
                    ).fetchall()
                _sc.close()
                subs = [
                    {"pan_nm": r[0], "pan_type": r[1], "region_nm": r[2],
                     "pan_start": r[3], "pan_end": r[4], "pan_status": r[5], "detail_url": r[6]}
                    for r in _subs_rows
                ]
                logger.info(f"subscription DB 조회: keyword={keyword}, 지역={_region_tokens}, {len(subs)}건")
            except Exception as _se:
                logger.warning(f"subscription DB 조회 실패: {_se}")

        # 2순위: DB 결과 없으면 API 호출
        if not subs:
            region_cd = None
            for region, code in REGION_CD_MAP.items():
                if region in keyword:
                    region_cd = code
                    break
            subs = fetch_subscription_info(region_cd=region_cd, page_size=10)
            # API 결과도 키워드 지역과 관련 없으면 차단
            if subs and _region_tokens:
                subs = [s for s in subs
                        if any(r in s.get("CNP_CD_NM", "") or r in s.get("region_nm", "")
                               for r in _region_tokens)]
            logger.info(f"subscription API 조회: region_cd={region_cd}, 필터 후 {len(subs)}건")

        if not subs:
            tg_error(blog_id, "fetcher", f"청약 공고 매칭 0건: {keyword}")
            # 매칭 불가 키워드 비활성화
            try:
                _kc = sqlite3.connect(RAP_DB_PATH, timeout=30)
                _kc.execute("UPDATE keywords SET status='inactive' WHERE keyword=?", (keyword,))
                _kc.commit()
                _kc.close()
                logger.warning(f"키워드 비활성화: {keyword} (청약 매칭 0건)")
            except Exception as _ke:
                logger.warning(f"키워드 비활성화 실패: {_ke}")
            return {"success": False, "reason": "no_subscription_data"}

        article = generate_subscription_article(keyword, subs)
        data_source = "rap_db_subscription"

    if not article:
        return {"success": False, "reason": "write_failed"}

    # 언어 검증 — 중국어 생성 차단
    _lang_err = assert_korean_or_reject(article.get("title", ""), article.get("body_md", ""), blog_id)
    if _lang_err:
        logger.error(f"[{blog_id}] {_lang_err}")
        return {"success": False, "reason": "language_error"}

    # 썸네일
    article["title"] = sanitize_title(article["title"])
    title_hash = hashlib.md5(article["title"].encode()).hexdigest()[:10]
    slug = f"{datetime.now().strftime('%Y%m%d')}-{title_hash}"
    thumb_url = generate_image_thumbnail(
        site_id="rap",
        slug=slug,
        title=article["title"],
        category=article.get("category", "부동산"),
    )

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
    _is_draft = cfg.get("force_draft", False) or False
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
        source_id=f"{keyword}_{datetime.now().strftime('%Y%m%d')}",
        model=os.getenv("OPENAI_MODEL", "mimo-v2.5"),
        thumbnail_url=thumb_url,
        wp_category=wp_category,
    )

    if result and result.get("success"):
        logger.info(f"RAP 발행 성공: {article['title']}")

        # ★ RAP DB에 발행 기록 (중복 방지)
        try:
            rap_conn = sqlite3.connect(RAP_DB_PATH, timeout=30)
            rap_conn.execute(
                "INSERT INTO publish_log (blog_id, data_type, data_key, title, published_at) "
                "VALUES (?,?,?,?, datetime('now')) "
                "ON CONFLICT(blog_id, data_key) DO UPDATE SET "
                "title=excluded.title, published_at=datetime('now')",
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

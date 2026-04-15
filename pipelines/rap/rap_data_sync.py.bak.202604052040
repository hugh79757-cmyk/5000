"""RAP DB 일일 갱신 — 실거래가 + 청약 API 수집"""
import os
import sys
import time
import sqlite3
import logging
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"))

from pipelines.rap.fetcher import fetch_apt_trade, fetch_subscription_info, LAWD_MAP, REGION_CD_MAP

logger = logging.getLogger(__name__)

RAP_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "rap.db")

# 수집 대상 지역 (주요 거래 활발 지역)
SYNC_REGIONS = [
    # 서울
    ("11680", "서울", "강남구"), ("11650", "서울", "서초구"),
    ("11710", "서울", "송파구"), ("11740", "서울", "강동구"),
    ("11440", "서울", "마포구"), ("11170", "서울", "용산구"),
    ("11200", "서울", "성동구"), ("11215", "서울", "광진구"),
    ("11560", "서울", "영등포구"), ("11590", "서울", "동작구"),
    ("11620", "서울", "관악구"), ("11470", "서울", "양천구"),
    ("11500", "서울", "강서구"), ("11350", "서울", "노원구"),
    ("11290", "서울", "성북구"), ("11410", "서울", "서대문구"),
    ("11380", "서울", "은평구"), ("11110", "서울", "종로구"),
    # 수도권
    ("41135", "경기", "성남시분당구"), ("41465", "경기", "용인시수지구"),
    ("41590", "경기", "화성시"), ("41117", "경기", "수원시영통구"),
    ("41281", "경기", "고양시덕양구"), ("41570", "경기", "김포시"),
    ("41450", "경기", "하남시"), ("41210", "경기", "광명시"),
    # 광역시
    ("26350", "부산", "해운대구"), ("26290", "부산", "남구"),
    ("27260", "대구", "수성구"), ("28185", "인천", "연수구"),
]


def is_today_refreshed():
    """오늘 이미 갱신했는지 확인"""
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(RAP_DB_PATH)
    row = conn.execute("SELECT id FROM refresh_log WHERE refresh_date=?", (today,)).fetchone()
    conn.close()
    return row is not None


def sync_trades(conn):
    """실거래가 수집 → rap.db 저장"""
    deal_ymd = datetime.now().strftime("%Y%m")
    added = 0

    for lawd_cd, city, district in SYNC_REGIONS:
        trades = fetch_apt_trade(lawd_cd, deal_ymd=deal_ymd, rows=50)
        for t in trades:
            try:
                conn.execute("""
                    INSERT OR IGNORE INTO trades
                    (lawd_cd, city, district, deal_ymd, apt_name, dong_name,
                     exclu_use_ar, floor, build_year, deal_amount,
                     deal_year, deal_month, deal_day)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    lawd_cd, city, district, deal_ymd,
                    t.get("aptNm", "").strip(),
                    t.get("umdNm", "").strip(),
                    float(t.get("excluUseAr", 0) or 0),
                    int(t.get("floor", 0) or 0),
                    int(t.get("buildYear", 0) or 0),
                    t.get("dealAmountInt", 0),
                    int(t.get("dealYear", 0) or 0),
                    int(t.get("dealMonth", 0) or 0),
                    int(t.get("dealDay", 0) or 0),
                ))
                added += 1
            except Exception as e:
                logger.warning(f"거래 저장 실패: {e}")

    logger.info(f"실거래가 수집 완료: {added}건 추가")
    return added


def sync_subscriptions(conn):
    """청약 공고 수집 → rap.db 저장"""
    added = 0

    for region, code in REGION_CD_MAP.items():
        subs = fetch_subscription_info(region_cd=code, page_size=20)
        for s in subs:
            pan_id = s.get("PAN_ID", "") or s.get("DTL_URL", "")
            if not pan_id:
                continue
            try:
                conn.execute("""
                    INSERT OR IGNORE INTO subscriptions
                    (pan_id, pan_nm, region_cd, region_nm, pan_type,
                     pan_start, pan_end, pan_status, detail_url)
                    VALUES (?,?,?,?,?,?,?,?,?)
                """, (
                    pan_id,
                    s.get("PAN_NM", "").strip(),
                    code,
                    region,
                    s.get("AIS_TP_CD_NM", ""),
                    s.get("PAN_NT_ST_DT", ""),
                    s.get("CLSG_DT", ""),
                    s.get("PAN_SS", ""),
                    s.get("DTL_URL", ""),
                ))
                added += 1
            except Exception as e:
                logger.warning(f"청약 저장 실패: {e}")

    logger.info(f"청약 공고 수집 완료: {added}건 추가")
    return added


def sync_keywords_from_gap():
    """gap.db에서 부동산 키워드를 rap.db로 마이그레이션 (1회)"""
    gap_db = os.path.join(os.path.dirname(RAP_DB_PATH), "gap.db")
    if not os.path.exists(gap_db):
        return 0

    gap_conn = sqlite3.connect(gap_db)
    rap_conn = sqlite3.connect(RAP_DB_PATH)
    added = 0

    # 부동산 무관 키워드 제외
    EXCLUDE = [
        "기능사", "요리", "조리", "흑백", "레시피", "양식조리", "제과", "봉제",
        "롤러운전", "콘크리트", "전자기능", "주조", "인베디드", "견적서",
        "운세", "로또", "날씨", "웹툰", "게임", "파전", "킷트", "래시피",
        "키친보스", "오스틴강", "이탈리안", "이탈리아", "명태살", "1분링",
    ]

    # blog_target 자동 분류
    BLOG_PATTERNS = {
        "rap-hugo": ["아파트", "매매", "시세", "실거래", "집값", "공시지가", "빌라",
                     "오피스텔", "은마", "재건축", "재개발", "부동산", "단지"],
        "rap2-hugo": ["청약", "분양", "LH", "행복주택", "임대주택", "청년주택",
                      "청년안심", "국민임대", "영구임대", "매입임대", "신혼희망"],
        "rap3-hugo": ["양도", "취득세", "상속세", "증여세", "세금", "과세", "공시지가",
                      "재산세", "종부세", "종합부동산세", "절세", "세율", "면제"],
        "rap4-hugo": ["전세", "월세", "임대", "보증금", "임대차", "전월세", "반전세",
                      "보증보험", "전세사기", "확정일자", "임차인", "계약갱신"],
        "rap5-hugo": ["헬리오시티", "힐스테이트", "래미안", "자이", "푸르지오", "아크로",
                      "파크리오", "더샵", "르엘", "롯데캐슬", "아이파크", "브랜드", "풍림"],
    }

    rows = gap_conn.execute(
        "SELECT keyword, category, priority, use_count, last_used_at, status "
        "FROM keywords WHERE category='금융/부동산'"
    ).fetchall()

    for kw, cat, pri, uc, lua, st in rows:
        if any(ex in kw for ex in EXCLUDE):
            continue

        # blog_target 결정
        target = None
        for blog_id, patterns in BLOG_PATTERNS.items():
            if any(p in kw for p in patterns):
                target = blog_id
                break

        try:
            rap_conn.execute("""
                INSERT OR IGNORE INTO keywords
                (keyword, category, blog_target, priority, use_count, last_used_at, status)
                VALUES (?,?,?,?,?,?,?)
            """, (kw, cat, target, pri, uc, lua, st))
            added += 1
        except Exception:
            pass

    rap_conn.commit()
    rap_conn.close()
    gap_conn.close()
    logger.info(f"gap.db → rap.db 키워드 마이그레이션: {added}건")
    return added


def daily_refresh():
    """일일 갱신 메인 — 첫 발행 시 호출"""
    if is_today_refreshed():
        logger.info("오늘 이미 갱신됨 — 스킵")
        return False

    logger.info("=== RAP DB 일일 갱신 시작 ===")
    start = time.time()

    conn = sqlite3.connect(RAP_DB_PATH)
    trades_added = sync_trades(conn)
    subs_added = sync_subscriptions(conn)
    conn.commit()

    duration = time.time() - start
    today = datetime.now().strftime("%Y-%m-%d")
    conn.execute(
        "INSERT OR IGNORE INTO refresh_log (refresh_date, trades_added, subs_added, duration_sec) VALUES (?,?,?,?)",
        (today, trades_added, subs_added, round(duration, 1))
    )
    conn.commit()
    conn.close()

    logger.info(f"=== RAP DB 갱신 완료: 거래 {trades_added}건, 청약 {subs_added}건, {duration:.1f}초 ===")
    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    daily_refresh()
    sync_keywords_from_gap()

    # 결과 확인
    conn = sqlite3.connect(RAP_DB_PATH)
    t = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
    s = conn.execute("SELECT COUNT(*) FROM subscriptions").fetchone()[0]
    k = conn.execute("SELECT COUNT(*) FROM keywords WHERE status='active'").fetchone()[0]
    conn.close()
    print(f"\nRAP DB 현황: 거래 {t}건, 청약 {s}건, 키워드 {k}개")

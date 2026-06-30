"""RAP DB 일일 갱신 — 매매 실거래가 + 전월세 + 청약 API 수집"""
import logging
import os
import sqlite3
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"))

from pipelines.rap.fetcher import (
    REGION_CD_MAP,
    fetch_apt_rent,
    fetch_apt_trade,
    fetch_subscription_info,
)

logger = logging.getLogger(__name__)

RAP_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "rap.db")

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
    ("41590", "경기", "화성시"),      ("41117", "경기", "수원시영통구"),
    ("41281", "경기", "고양시덕양구"), ("41570", "경기", "김포시"),
    ("41450", "경기", "하남시"),      ("41210", "경기", "광명시"),
    # 광역시
    ("26350", "부산", "해운대구"), ("26290", "부산", "남구"),
    ("27260", "대구", "수성구"),   ("28185", "인천", "연수구"),
    # 경기 추가
    ("41220", "경기", "평택시"),
    ("41171", "경기", "안양시만안구"), ("41173", "경기", "안양시동안구"),
    ("41271", "경기", "안산시상록구"), ("41273", "경기", "안산시단원구"),
    ("41390", "경기", "시흥시"),
    # 강원
    ("42110", "강원", "춘천시"), ("42130", "강원", "원주시"), ("42150", "강원", "강릉시"),
    # 충북
    ("43111", "충북", "청주시상당구"), ("43112", "충북", "청주시서원구"),
    ("43113", "충북", "청주시흥덕구"), ("43114", "충북", "청주시청원구"),
    ("43130", "충북", "충주시"),
    # 충남
    ("44131", "충남", "천안시동남구"), ("44133", "충남", "천안시서북구"),
    # 전북
    ("45111", "전북", "전주시완산구"), ("45113", "전북", "전주시덕진구"),
    # 전남
    ("46150", "전남", "순천시"),
    # 경북
    ("47111", "경북", "포항시남구"), ("47113", "경북", "포항시북구"),
    ("47190", "경북", "구미시"),
    # 경남
    ("48121", "경남", "창원시의창구"), ("48123", "경남", "창원시성산구"),
    ("48125", "경남", "창원시마산합포구"), ("48127", "경남", "창원시마산회원구"),
    ("48129", "경남", "창원시진해구"),
    ("48310", "경남", "거제시"),
]


def _ensure_rents_table(conn) -> None:
    """Rents 테이블 없으면 생성"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lawd_cd TEXT NOT NULL,
            city TEXT NOT NULL,
            district TEXT NOT NULL,
            deal_ymd TEXT NOT NULL,
            apt_name TEXT NOT NULL,
            dong_name TEXT,
            exclu_use_ar REAL,
            floor INTEGER,
            build_year INTEGER,
            deposit INTEGER,
            monthly_rent INTEGER,
            rent_type TEXT,
            deal_year INTEGER,
            deal_month INTEGER,
            deal_day INTEGER,
            fetched_at TEXT DEFAULT (datetime('now')),
            UNIQUE(lawd_cd, deal_ymd, apt_name, exclu_use_ar, floor, deal_day, deposit, monthly_rent)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_rents_lawd ON rents(lawd_cd, deal_ymd)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_rents_apt  ON rents(apt_name)")
    conn.commit()


def is_today_refreshed():
    """오늘 이미 갱신했는지 확인 (DB 락 발생 시 False 반환)"""
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        conn = sqlite3.connect(RAP_DB_PATH, timeout=5)
        row = conn.execute("SELECT id FROM refresh_log WHERE refresh_date=?", (today,)).fetchone()
        conn.close()
        return row is not None
    except sqlite3.OperationalError:
        logger.warning("is_today_refreshed: DB 락 — False 반환")
        return False


_TRADE_INSERT = """INSERT OR IGNORE INTO trades
    (lawd_cd, city, district, deal_ymd, apt_name, dong_name,
     exclu_use_ar, floor, build_year, deal_amount,
     deal_year, deal_month, deal_day)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)"""

_RENT_INSERT = """INSERT OR IGNORE INTO rents
    (lawd_cd, city, district, deal_ymd, apt_name, dong_name,
     exclu_use_ar, floor, build_year, deposit, monthly_rent,
     rent_type, deal_year, deal_month, deal_day)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"""

_SUB_INSERT = """INSERT OR IGNORE INTO subscriptions
    (pan_id, pan_nm, region_cd, region_nm, pan_type,
     pan_start, pan_end, pan_status, detail_url)
    VALUES (?,?,?,?,?,?,?,?,?)"""


def _fetch_region_trades(args):
    """단일 지역 매매 API 호출 (executor 워커용)"""
    lawd_cd, city, district, deal_ymd = args
    try:
        items = fetch_apt_trade(lawd_cd, deal_ymd=deal_ymd, rows=100)
        if not items:
            return []
        rows = []
        for t in items:
            try:
                rows.append((
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
            except (ValueError, TypeError):
                continue
        return rows
    except Exception as e:
        logger.warning(f"매매 API 실패: {city} {district} — {e}")
        return []


def _fetch_region_rents(args):
    """단일 지역 전월세 API 호출 (executor 워커용)"""
    lawd_cd, city, district, deal_ymd = args
    try:
        items = fetch_apt_rent(lawd_cd, deal_ymd=deal_ymd, rows=100)
        if not items:
            return []
        rows = []
        for r in items:
            try:
                rows.append((
                    lawd_cd, city, district, deal_ymd,
                    r.get("aptNm", "").strip(),
                    r.get("umdNm", "").strip(),
                    float(r.get("excluUseAr", 0) or 0),
                    int(r.get("floor", 0) or 0),
                    int(r.get("buildYear", 0) or 0),
                    r.get("depositInt", 0),
                    r.get("monthlyRentInt", 0),
                    r.get("rentType", "전세"),
                    int(r.get("dealYear", 0) or 0),
                    int(r.get("dealMonth", 0) or 0),
                    int(r.get("dealDay", 0) or 0),
                ))
            except (ValueError, TypeError):
                continue
        return rows
    except Exception as e:
        logger.warning(f"전월세 API 실패: {city} {district} — {e}")
        return []


def _fetch_region_subs(args):
    """단일 지역 청약 API 호출 (executor 워커용)"""
    region, code = args
    try:
        items = fetch_subscription_info(region_cd=code, page_size=20)
        if not items:
            return []
        rows = []
        for s in items:
            pan_id = s.get("PAN_ID", "") or s.get("DTL_URL", "")
            if not pan_id:
                continue
            rows.append((
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
        return rows
    except Exception as e:
        logger.warning(f"청약 API 실패: {region} — {e}")
        return []


def _parallel_sync(conn, fetch_fn, regions_args, insert_sql, label):
    """공용 병렬 동기화: ThreadPoolExecutor로 API 호출 분산 후 단일 connection INSERT"""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    start = time.time()
    all_rows = []

    with ThreadPoolExecutor(max_workers=5) as ex:
        futures = {ex.submit(fetch_fn, args): args for args in regions_args}
        for future in as_completed(futures):
            rows = future.result()
            if rows:
                all_rows.extend(rows)

    if all_rows:
        conn.executemany(insert_sql, all_rows)
        conn.commit()

    elapsed = time.time() - start
    logger.info(f"{label} 수집 완료: {len(all_rows)}건 ({elapsed:.1f}초)")
    return len(all_rows)


def sync_trades(conn):
    """매매 실거래가 수집 (병렬, 최대 5워커)"""
    deal_ymd = datetime.now().strftime("%Y%m")
    args = [(lcd, ct, dt, deal_ymd) for lcd, ct, dt in SYNC_REGIONS]
    return _parallel_sync(conn, _fetch_region_trades, args, _TRADE_INSERT, "매매 실거래가")


def sync_rents(conn):
    """전월세 실거래가 수집 (병렬, 최대 5워커, rap4-hugo 전용)"""
    _ensure_rents_table(conn)
    deal_ymd = datetime.now().strftime("%Y%m")
    args = [(lcd, ct, dt, deal_ymd) for lcd, ct, dt in SYNC_REGIONS]
    return _parallel_sync(conn, _fetch_region_rents, args, _RENT_INSERT, "전월세 실거래가")


def sync_subscriptions(conn):
    """청약 공고 수집 (병렬, 최대 5워커)"""
    args = [(region, code) for region, code in REGION_CD_MAP.items()]
    return _parallel_sync(conn, _fetch_region_subs, args, _SUB_INSERT, "청약 공고")


def sync_keywords_from_gap():
    """gap.db에서 부동산 키워드를 rap.db로 마이그레이션 (1회)"""
    gap_db = os.path.join(os.path.dirname(RAP_DB_PATH), "gap.db")
    if not os.path.exists(gap_db):
        return 0

    gap_conn = sqlite3.connect(gap_db)
    rap_conn = sqlite3.connect(RAP_DB_PATH)
    added = 0

    EXCLUDE = [
        "기능사", "요리", "조리", "흑백", "레시피", "양식조리", "제과", "봉제",
        "롤러운전", "콘크리트", "전자기능", "주조", "인베디드", "견적서",
        "운세", "로또", "날씨", "웹툰", "게임", "파전", "킷트", "래시피",
        "키친보스", "오스틴강", "이탈리안", "이탈리아", "명태살", "1분링",
    ]
    BLOG_PATTERNS = {
        "rap-hugo":  ["아파트", "매매", "시세", "실거래", "집값", "공시지가", "빌라",
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




def _ensure_gongsijiga_table(conn) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS gongsijiga (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lawd_cd TEXT,
            apt_name TEXT,
            deal_year INTEGER,
            avg_deal_amount INTEGER,
            estimated_price INTEGER,
            actual_price INTEGER,
            source TEXT DEFAULT 'estimated',
            fetched_at TEXT DEFAULT (datetime('now')),
            UNIQUE(lawd_cd, apt_name, deal_year)
        )
    """)
    conn.commit()


def sync_gongsijiga(conn):
    """Trades 테이블 기반 공시가격 추정치 계산 (실거래가 × 0.69)
    단지별 연도별 평균 실거래가를 기준으로 추정 공시가격 생성
    """
    _ensure_gongsijiga_table(conn)

    rows = conn.execute("""
        SELECT lawd_cd, apt_name, deal_year,
               CAST(AVG(deal_amount) AS INTEGER) as avg_amt,
               COUNT(*) as cnt
        FROM trades
        GROUP BY lawd_cd, apt_name, deal_year
        HAVING cnt >= 1
        ORDER BY lawd_cd, apt_name, deal_year
    """).fetchall()

    inserted = 0
    updated  = 0
    for lawd_cd, apt_name, deal_year, avg_amt, _cnt in rows:
        if not avg_amt or avg_amt <= 0:
            continue
        estimated = int(avg_amt * 0.69)
        cur = conn.execute(
            "SELECT id, estimated_price FROM gongsijiga "
            "WHERE lawd_cd=? AND apt_name=? AND deal_year=?",
            (lawd_cd, apt_name, deal_year)
        ).fetchone()
        if cur is None:
            conn.execute(
                "INSERT INTO gongsijiga "
                "(lawd_cd, apt_name, deal_year, avg_deal_amount, estimated_price, source) "
                "VALUES (?, ?, ?, ?, ?, 'estimated')",
                (lawd_cd, apt_name, deal_year, avg_amt, estimated)
            )
            inserted += 1
        elif cur[1] != estimated:
            conn.execute(
                "UPDATE gongsijiga SET avg_deal_amount=?, estimated_price=?, "
                "fetched_at=datetime('now') "
                "WHERE lawd_cd=? AND apt_name=? AND deal_year=?",
                (avg_amt, estimated, lawd_cd, apt_name, deal_year)
            )
            updated += 1
    conn.commit()

    import logging
    logging.getLogger(__name__).info(
        f"gongsijiga 동기화 완료: 신규 {inserted}건, 갱신 {updated}건"
    )
    return inserted, updated

def daily_refresh() -> bool:
    """일일 갱신 메인 — 첫 발행 시 호출 (병렬 fetch + 90초 타임아웃)"""
    if is_today_refreshed():
        logger.info("오늘 이미 갱신됨 — 스킵")
        return False

    logger.info("=== RAP DB 일일 갱신 시작 ===")
    start = time.time()
    deadline = time.monotonic() + 90.0

    conn = sqlite3.connect(RAP_DB_PATH)
    _ensure_rents_table(conn)

    trades_added = 0
    rents_added  = 0
    subs_added   = 0

    # 각 sync 함수는 내부적으로 5개 워커 ThreadPoolExecutor 사용
    # 전체 90초 초과 시 중단 (일부만 갱신된 상태로 기록)
    try:
        trades_added = sync_trades(conn)
    except Exception as e:
        logger.warning(f"매매 수집 중단 (non-fatal): {e}")

    if time.monotonic() < deadline:
        try:
            rents_added = sync_rents(conn)
        except Exception as e:
            logger.warning(f"전월세 수집 중단 (non-fatal): {e}")

    if time.monotonic() < deadline:
        try:
            subs_added = sync_subscriptions(conn)
        except Exception as e:
            logger.warning(f"청약 수집 중단 (non-fatal): {e}")

    conn.commit()

    duration = time.time() - start
    today = datetime.now().strftime("%Y-%m-%d")
    conn.execute(
        "INSERT OR IGNORE INTO refresh_log "
        "(refresh_date, trades_added, subs_added, duration_sec) VALUES (?,?,?,?)",
        (today, trades_added + rents_added, subs_added, round(duration, 1))
    )
    conn.commit()
    conn.close()

    logger.info(
        f"=== RAP DB 갱신 완료: 매매 {trades_added}건, "
        f"전월세 {rents_added}건, 청약 {subs_added}건, {duration:.1f}초 ==="
    )
    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    daily_refresh()

    conn = sqlite3.connect(RAP_DB_PATH)
    t = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
    r = conn.execute("SELECT COUNT(*) FROM rents").fetchone()[0]
    s = conn.execute("SELECT COUNT(*) FROM subscriptions").fetchone()[0]
    k = conn.execute("SELECT COUNT(*) FROM keywords WHERE status='active'").fetchone()[0]
    conn.close()
    print(f"\nRAP DB 현황: 매매 {t}건, 전월세 {r}건, 청약 {s}건, 키워드 {k}개")

import logging
import os
import sqlite3
from datetime import datetime, timedelta

import requests

from shared.db import BranchDbMissingError, connect_branch_db

try:
    from shared.telegram_notifier import send_error as tg_error
except ImportError:
    def tg_error(*a, **k) -> None:
        return None

logger = logging.getLogger(__name__)

# 한국표준산업분류 주요 업종코드 매핑
INDUTY_MAP = {
    "10": "식료품", "11": "음료", "13": "섬유", "14": "의복",
    "20": "화학물질", "21": "의약품", "22": "고무·플라스틱", "23": "비금속광물",
    "24": "1차금속", "25": "금속가공", "26": "전자부품·컴퓨터", "27": "의료·정밀기기",
    "28": "전기장비", "29": "기계장비", "30": "자동차", "31": "운송장비",
    "32": "가구", "33": "기타제조", "35": "전기·가스", "41": "건설",
    "45": "자동차판매", "46": "도매", "47": "소매", "49": "육상운송",
    "50": "수상운송", "51": "항공운송", "52": "창고·운송서비스",
    "55": "숙박", "56": "음식점", "58": "출판", "59": "영상·오디오",
    "60": "방송", "61": "통신", "62": "컴퓨터프로그래밍", "63": "정보서비스",
    "64": "금융", "65": "보험", "66": "금융·보험서비스",
    "68": "부동산", "70": "연구개발", "71": "전문서비스", "72": "건축·엔지니어링",
    "73": "광고", "74": "기타전문서비스", "75": "사업시설관리",
    "84": "공공행정", "85": "교육", "86": "보건", "87": "사회복지",
}

def get_induty_name(code):
    """업종코드(5자리) → 업종명 변환"""
    if not code:
        return ""
    code = str(code).strip()
    # 5자리 정확 매칭 → 4자리 → 3자리 → 2자리 순서
    for length in [5, 4, 3, 2]:
        prefix = code[:length]
        if prefix in INDUTY_MAP:
            return INDUTY_MAP[prefix]
    return ""



DART_BASE = "https://opendart.fss.or.kr/api"
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "stock.db")


def _get_key():
    return os.getenv("DART_API_KEY", "")


def fetch_recent_disclosure(days=3, page_count=20):
    key = _get_key()
    end = datetime.now().strftime("%Y%m%d")
    bgn = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
    r = requests.get(f"{DART_BASE}/list.json", params={
        "crtfc_key": key,
        "bgn_de": bgn,
        "end_de": end,
        "page_no": 1,
        "page_count": page_count,
        "sort": "date",
        "sort_mth": "desc",
    }, timeout=15)
    data = r.json()
    if data.get("status") != "000":
        logger.warning(f"DART list error: {data.get('message')}")
        return []
    return data.get("list", [])


def fetch_major_disclosure(days=7):
    items = fetch_recent_disclosure(days=days, page_count=100)
    major_keywords = [
        "주요사항보고서", "증권신고서", "공개매수", "합병",
        "분할", "유상증자", "무상증자", "전환사채", "자기주식",
    ]
    major = []
    for item in items:
        report = item.get("report_nm", "")
        if any(kw in report for kw in major_keywords):
            major.append(item)
    logger.info(f"주요 공시 {len(major)}건 (전체 {len(items)}건 중)")
    return major


def fetch_company_info(corp_code):
    key = _get_key()
    r = requests.get(f"{DART_BASE}/company.json", params={
        "crtfc_key": key,
        "corp_code": corp_code,
    }, timeout=10)
    data = r.json()
    if data.get("status") == "000":
        if "induty_nm" not in data and data.get("induty_code"):
            data["induty_nm"] = get_induty_name(data["induty_code"])
        return data
    return None


def fetch_financial_summary(corp_code, year=None, report_code="11011"):
    if year is None:
        year = str(datetime.now().year - 1)
    key = _get_key()
    # [PATCH] CFS(연결) 먼저, 없으면 OFS(개별) fallback
    for fs_div in ("CFS", "OFS"):
        try:
            r = requests.get(f"{DART_BASE}/fnlttSinglAcntAll.json", params={
                "crtfc_key": key,
                "corp_code": corp_code,
                "bsns_year": year,
                "reprt_code": report_code,
                "fs_div": fs_div,
            }, timeout=15)
            data = r.json()
            if data.get("status") == "000" and data.get("list"):
                logger.info(f"재무 {fs_div} {len(data['list'])}건: {corp_code} ({year})")
                return data.get("list", [])
        except Exception as e:
            logger.warning(f"재무 {fs_div} 조회 실패 {corp_code}: {e}")
    return []


def fetch_ipo_securities(days=30):
    items = fetch_recent_disclosure(days=days, page_count=100)
    ipo = [i for i in items if "증권신고서" in i.get("report_nm", "")]
    logger.info(f"IPO/증권신고서 {len(ipo)}건")
    return ipo


def fetch_dividend_info(corp_code, year=None):
    if year is None:
        year = str(datetime.now().year - 1)
    key = _get_key()
    r = requests.get(f"{DART_BASE}/alotMatter.json", params={
        "crtfc_key": key,
        "corp_code": corp_code,
        "bsns_year": year,
        "reprt_code": "11011",
    }, timeout=10)
    data = r.json()
    if data.get("status") == "000":
        return data.get("list", [])
    return []


def get_listed_corps(limit=100):
    try:
        conn = connect_branch_db("stock_metrics", allow_create=False)
    except BranchDbMissingError:
        tg_error("stock_metrics DB 누락: get_listed_corps 스킵 (silent-create 방지)")
        return []
    conn.row_factory = sqlite3.Row
    # 재무 데이터가 있을 가능성 높은 기업 우선 (stock_code 있고, 최근 수정)
    rows = conn.execute(
        """SELECT corp_code, corp_name, stock_code, sector FROM corps
           WHERE is_listed=1 AND stock_code IS NOT NULL AND stock_code != ''
           ORDER BY modify_date DESC LIMIT ?""",
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def fetch_etf_daily(top_n=10):
    """네이버 금융 ETF API에서 전체 ETF 시세를 가져와 상위/하위/거래량 급증 분류"""
    import requests as _req
    url = "https://finance.naver.com/api/sise/etfItemList.nhn"
    # DB 캐시 먼저 확인
    cached = _get_etf_from_db()
    items = None
    items_from_db = False
    if cached and len(cached) >= 5:  # 5개 이상이면 사용 (10→5 완화)
        items_from_db = True
        items = cached
    else:
        # API 시도
        try:
            resp = _req.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            data = resp.json()
            items = data.get("result", {}).get("etfItemList", [])
            if items:
                saved = _save_etf_to_db(items)
                import logging
                logging.getLogger(__name__).info(f"ETF {saved}건 DB 캐시 저장")
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"ETF API 실패, DB 캐시 사용: {e}")
            # DB에 캐시가 있으면 사용 (개수 무관)
            if cached:
                items_from_db = True
                items = cached
    
    # 둘 다 없으면 최소 구조 반환 (기사 생성은 가능하게)
    if not items:
        return {
            "gainers": [],
            "losers": [],
            "volume_top": [],
            "total_count": 0,
            "source": "naver_finance_etf_api_unavailable",
            "note": "실시간 데이터 수신 불가 - 전략/방법론 중심 작성 필요",
        }

    # DB캐시와 API 응답 키 통일
    if items_from_db:
        for e in items:
            e["itemcode"] = e.get("item_code", "")
            e["itemname"] = e.get("item_name", "")
            e["nowVal"] = e.get("price", 0)
            e["changeRate"] = e.get("change_rate", 0)
            e["quant"] = e.get("volume", 0)
            e["marketSum"] = e.get("market_cap", 0)
            e["nav"] = e.get("nav", 0)
            e["threeMonthEarnRate"] = e.get("three_month_return")

    # 등락률 기준 정렬
    gainers = sorted([e for e in items if e.get("changeRate", 0) > 0], key=lambda x: x["changeRate"], reverse=True)[:top_n]
    losers = sorted([e for e in items if e.get("changeRate", 0) < 0], key=lambda x: x["changeRate"])[:top_n]

    # 거래량 상위 (시총 대비 거래량 비율로 급증 판단은 어려우므로 절대 거래량 상위)
    volume_top = sorted(items, key=lambda x: x.get("quant", 0), reverse=True)[:top_n]

    # 중복 제거: losers에서 gainers 종목코드 제외
    gainer_codes = {e["itemcode"] for e in gainers}
    losers = [e for e in losers if e["itemcode"] not in gainer_codes][:top_n]

    def _fmt(etf_list):
        result = []
        for e in etf_list:
            result.append({
                "name": e.get("itemname", ""),
                "code": e.get("itemcode", ""),
                "price": e.get("nowVal", 0),
                "change_rate": e.get("changeRate", 0),
                "volume": e.get("quant", 0),
                "market_cap": e.get("marketSum", 0),
                "nav": e.get("nav", 0),
                "three_month_return": e.get("threeMonthEarnRate"),
            })
        return result

    return {
        "gainers": _fmt(gainers),
        "losers": _fmt(losers),
        "volume_top": _fmt(volume_top),
        "total_count": len(items),
        "source": "naver_finance_etf_api",
    }



def fetch_dividend_ranking(top_n=10):
    """KSD 증권정보포털(seibro)에서 배당순위 TOP50 크롤링"""
    import requests as _req
    from bs4 import BeautifulSoup as _BS
    url = "https://m.seibro.or.kr/cnts/company/selectDiv50.do"
    # DB 캐시 먼저 확인
    cached = _get_dividend_from_db()
    if cached:
        rankings = [{"rank": r["rank"], "name": r["corp_name"], "dividend_yield": r["dividend_yield"], "dividend_per_share": r["dividend_per_share"]} for r in cached[:top_n]]
        return {"rankings": rankings, "total_count": len(cached), "source": "ksd_seibro_cached", "note": "DB 캐시 (당일)"}

    try:
        resp = _req.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        soup = _BS(resp.text, "html.parser")
        rows = soup.select("table tr")
        result = []
        for row in rows[1:]:  # 헤더 스킵
            cols = row.select("td")
            if len(cols) >= 4:
                rank = cols[0].get_text(strip=True)
                name = cols[1].get_text(strip=True)
                div_yield = cols[2].get_text(strip=True)
                div_per_share = cols[3].get_text(strip=True).replace(",", "")
                try:
                    result.append({
                        "rank": int(rank),
                        "name": name,
                        "dividend_yield": float(div_yield),
                        "dividend_per_share": int(div_per_share) if div_per_share.isdigit() else div_per_share,
                    })
                except (ValueError, TypeError):
                    continue
        if not result:
            return {"rankings": [], "total_count": 0, "source": "ksd_seibro_unavailable", "note": "배당 데이터 수신 불가 - 방법론 중심 작성 필요"}
        saved = _save_dividend_to_db(result)
        import logging
        logging.getLogger(__name__).info(f"배당 {saved}건 DB 캐시 저장")
        return {
            "rankings": result[:top_n],
            "total_count": len(result),
            "source": "ksd_seibro_div50",
            "note": "2025년 기준 시가배당률",
        }
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception(f"KSD 배당순위 fetch 실패: {e}")
        return {"rankings": [], "total_count": 0, "source": "ksd_seibro_error", "note": "배당 데이터 수신 불가 - 방법론 중심 작성 필요"}


def _save_etf_to_db(items):
    """ETF 시세를 DB에 저장 (당일 캐시)"""
    import sqlite3
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    conn = connect_branch_db("stock_metrics", allow_create=True)
    saved = 0
    for e in items:
        try:
            conn.execute(
                "INSERT OR IGNORE INTO etf_daily (date, item_code, item_name, price, change_rate, volume, market_cap, nav, three_month_return) VALUES (?,?,?,?,?,?,?,?,?)",
                (today, e.get("itemcode",""), e.get("itemname",""), e.get("nowVal",0), e.get("changeRate",0), e.get("quant",0), e.get("marketSum",0), e.get("nav",0), e.get("threeMonthEarnRate"))
            )
            saved += 1
        except Exception as e:
            logger.debug(f"[STOCK_FETCH] failed: {e}"); continue
    conn.commit()
    conn.close()
    return saved


def _get_etf_from_db():
    """DB에서 당일 ETF 데이터 조회"""
    import sqlite3
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        conn = connect_branch_db("stock_metrics", allow_create=False)
    except BranchDbMissingError:
        return None
    conn.row_factory = sqlite3.Row
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM etf_daily WHERE date=? ORDER BY change_rate DESC", (today,)).fetchall()
    conn.close()
    if not rows:
        return None
    return [dict(r) for r in rows]


def _save_dividend_to_db(rankings):
    """배당 순위를 DB에 저장"""
    import sqlite3
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    conn = connect_branch_db("stock_metrics", allow_create=True)
    saved = 0
    for r in rankings:
        try:
            conn.execute(
                "INSERT OR IGNORE INTO dividend_ranking (date, rank, corp_name, dividend_yield, dividend_per_share) VALUES (?,?,?,?,?)",
                (today, r.get("rank",0), r.get("name",""), r.get("dividend_yield",0), r.get("dividend_per_share",0))
            )
            saved += 1
        except Exception as e:
            logger.debug(f"[STOCK_FETCH] failed: {e}"); continue
    conn.commit()
    conn.close()
    return saved


def _get_dividend_from_db():
    """DB에서 당일 배당 데이터 조회"""
    import sqlite3
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        conn = connect_branch_db("stock_metrics", allow_create=False)
    except BranchDbMissingError:
        return None
    conn.row_factory = sqlite3.Row
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM dividend_ranking WHERE date=? ORDER BY rank", (today,)).fetchall()
    conn.close()
    if not rows:
        return None
    return [dict(r) for r in rows]


def refresh_daily_data() -> None:
    """하루 1회 ETF 시세 + 배당 순위 데이터를 API에서 가져와 DB에 저장"""
    import logging
    _log = logging.getLogger(__name__)

    # ETF 데이터 갱신
    import requests as _req
    try:
        resp = _req.get("https://finance.naver.com/api/sise/etfItemList.nhn", timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        items = resp.json().get("result", {}).get("etfItemList", [])
        if items:
            saved = _save_etf_to_db(items)
            _log.info(f"[일일갱신] ETF {saved}/{len(items)}건 저장")
    except Exception as e:
        _log.error(f"[일일갱신] ETF 실패: {e}")

    # 배당 데이터 갱신
    try:
        from bs4 import BeautifulSoup as _BS
        resp = _req.get("https://m.seibro.or.kr/cnts/company/selectDiv50.do", timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        soup = _BS(resp.text, "html.parser")
        rows = soup.select("table tr")
        result = []
        for row in rows[1:]:
            cols = row.select("td")
            if len(cols) >= 4:
                try:
                    result.append({
                        "rank": int(cols[0].get_text(strip=True)),
                        "name": cols[1].get_text(strip=True),
                        "dividend_yield": float(cols[2].get_text(strip=True)),
                        "dividend_per_share": int(cols[3].get_text(strip=True).replace(",", "")),
                    })
                except (ValueError, TypeError):
                    continue
        if result:
            saved = _save_dividend_to_db(result)
            _log.info(f"[일일갱신] 배당 {saved}/{len(result)}건 저장")
    except Exception as e:
        _log.error(f"[일일갱신] 배당 실패: {e}")

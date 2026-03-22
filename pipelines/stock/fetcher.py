import os
import requests
import logging
import sqlite3
from datetime import datetime, timedelta

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
    r = requests.get(f"{DART_BASE}/fnlttSinglAcntAll.json", params={
        "crtfc_key": key,
        "corp_code": corp_code,
        "bsns_year": year,
        "reprt_code": report_code,
        "fs_div": "CFS",
    }, timeout=15)
    data = r.json()
    if data.get("status") == "000":
        return data.get("list", [])
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
    conn = sqlite3.connect(DB_PATH)
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
    try:
        resp = _req.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        data = resp.json()
        items = data.get("result", {}).get("etfItemList", [])
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"ETF fetch 실패: {e}")
        return None

    if not items:
        return None

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

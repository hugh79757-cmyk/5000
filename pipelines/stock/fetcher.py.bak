import os
import requests
import logging
import sqlite3
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

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
        return data
    return None


def fetch_financial_summary(corp_code, year="2024", report_code="11011"):
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


def fetch_dividend_info(corp_code, year="2024"):
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
    rows = conn.execute(
        "SELECT corp_code, corp_name, stock_code, sector FROM corps WHERE is_listed=1 ORDER BY modify_date DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

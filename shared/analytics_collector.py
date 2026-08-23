"""
5000 Analytics Collector — GA4/GSC/AdSense/Bing 수집기

analytics.db 테이블을 GA4/GSC/AdSense/Bing API로 채웁니다.
blogdex의 daily_sync.py/adsense.py 패턴을 5000/shared/로 포팅.

사용법:
    python -c "from shared.analytics_collector import AnalyticsCollector; c = AnalyticsCollector(); print(c.collect_all())"

의존성 (시스템 python3에 설치 완료):
    - google-auth
    - google-analytics-data
    - google-api-python-client
    - google-analytics-admin
    - requests
"""

import json
import logging
import os
import re
import sqlite3
import sys
import time as _time
from datetime import datetime, timedelta
from pathlib import Path

import requests
from googleapiclient.errors import HttpError

# ── Path setup (shared/ 기준 상대 경로) ──
_SHARED_DIR = Path(__file__).parent
_FIVEK_DIR = _SHARED_DIR.parent
_DATA_DIR = _FIVEK_DIR / "data"
sys.path.insert(0, str(_FIVEK_DIR))

from shared.env_loader import load_env

load_env()

# ── 로거 ──
logger = logging.getLogger(__name__)

# ── DB 경로 ──
ANALYTICS_DB = _DATA_DIR / "analytics.db"

# ── Google OAuth ──
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

# blogdex와 token/credential 파일 공유
_BLOGDEX_DIR = Path.home() / "Projects" / "blogdex"
_BLOGDEX_CLI = _BLOGDEX_DIR / "cli"
_CREDENTIALS_DIR = _BLOGDEX_DIR / "credentials"

_PRIMARY_CLIENT_SECRET = _BLOGDEX_CLI / "client_secret_hugh7973.json"

GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/analytics.readonly",
    "https://www.googleapis.com/auth/webmasters",
    "https://www.googleapis.com/auth/adsense.readonly",
]

# ── GA4 속성 매핑 (blog_id → property_id) ──
# blogdex GA4_PROPERTIES + SAP/aikorea24 수동 추가
GA4_PROPERTIES = {
    # 5000 — Travel
    "travel-hugo": "520459800",
    "travel1-hugo": None,  # 미등록
    "travel2-hugo": None,
    "travel3-hugo": None,
    "travel4-hugo": None,
    "heritage-hugo": None,
    # 5000 — Senior
    "senior-hugo": None,
    "senior-blogger": None,
    # 5000 — Stock
    "stock-hugo": "518365064",
    "etf-hugo": None,
    "dividend-hugo": None,
    "sector-hugo": None,
    "ipo-hugo": None,
    "finance-hugo": None,
    # 5000 — RAP (rotcha.kr subdomains → shared rotcha.kr GA4)
    "rap-hugo": "407323015",
    "rap2-hugo": "407323015",
    "rap3-hugo": "407323015",
    "rap4-hugo": "407323015",
    "rap5-hugo": "407323015",
    # 5000 — CAP (CUAP)
    "appliance-hugo": None,
    "baby-hugo": None,
    "fitness-hugo": None,
    "interior-hugo": None,
    "laptop-hugo": None,
    # 5000 — LAP/ETAP
    "ev-hugo": None,
    "compare-hugo": None,
    "deal-hugo": None,
    "guide-hugo": None,
    "tco-hugo": None,
    # 5000 — Track C ETAP 34 (ga4_measurement_map.yaml 기준, 2026-08-22 등록)
    "adventure-hugo": "531123457",
    "airlines-hugo": "531035921",
    "airports-hugo": "531044776",
    "bus-hugo": "531065834",
    "cruise-hugo": "531006370",
    "culture-hugo": "531065835",
    "daytrips-hugo": "531054102",
    "deals-hugo": "531065294",
    "dining-hugo": "531047182",
    "esim-hugo": "531068317",
    "ferry-hugo": "531123458",
    "flights-hugo": "531065272",
    "foodtour-hugo": "531167909",
    "michelin-hugo": "531066288",
    "multiday-hugo": "531139671",
    "nature-hugo": "531055811",
    "tour-hugo": "531055776",
    "tours-hugo": "531081222",
    "trains-hugo": "531082945",
    "transfers-hugo": "531012256",
    "visa-hugo": "531039430",
    "visafree-hugo": "531135786",
    "walking-hugo": "531135787",
    "watersports-hugo": "531139672",
    "luxury-hugo": "533565769",
    "citytours-hugo": "533547904",
    "watertours-hugo": "533560944",
    "hiking-hugo": "533501468",
    "escape-hugo": "533557099",
    "extreme-hugo": "533528727",
    "nightlife-hugo": "533501469",
    "ghost-hugo": "533502285",
    "layover-hugo": "533564578",
    "nomad-hugo": "533489259",
    # 5000 — Info
    "hotissue-hugo": "520232186",
    "info-hugo": None,
    "rank-hugo": None,
    "pick-hugo": None,
    # 5000 — Legacy
    "kuta-wordpress": None,
    "gap-kuta": None,
    "gap-hugo": None,
    "tvshow-blogger": None,
    "ud-blogger": None,
    # SAP
    "kboplayer": None,
    "kboteam": None,
    "kboschedule": None,
    "proto": None,
    "protostats": None,
    "fstats": None,
    "fsched": None,
    "betguide": None,
    "protoking": None,
    "sports-rotcha": None,
    "kbo-rotcha": None,
    # AI Korea
    "aikorea24": None,
    "persona-aikorea24": None,
}

# ── GSC 사이트 목록 (blogdex 기준 + SAP 추가) ──
GSC_SITES = [
    # 5000 — Travel
    "https://travel.rotcha.kr/",
    "https://tour1.rotcha.kr/",
    "https://travel1.rotcha.kr/",
    "https://travel2.rotcha.kr/",
    "https://tour2.rotcha.kr/",
    "https://tour3.rotcha.kr/",
    # 5000 — Stock
    "https://stock.informationhot.kr/",
    "https://etf.techpawz.com/",
    "https://dividend.techpawz.com/",
    "https://sector.techpawz.com/",
    "https://ipo.techpawz.com/",
    "https://finance.techpawz.com/",
    # 5000 — RAP
    "https://rap.rotcha.kr/",
    # 5000 — LAP/ETAP
    "https://tco.rotcha.kr/",
    "https://deal.rotcha.kr/",
    "https://compare.rotcha.kr/",
    "https://guide.rotcha.kr/",
    "https://ev.rotcha.kr/",
    # 5000 — Legacy
    "https://kuta.informationhot.kr/",
    # 5000 — Info
    "https://hotissue.rotcha.kr/",
    # SAP (informationhot.kr subdomains)
    "https://kboplayer.informationhot.kr/",
    "https://kboteam.informationhot.kr/",
    "https://kboschedule.informationhot.kr/",
    "https://proto.informationhot.kr/",
    "https://protostats.informationhot.kr/",
    "https://fstats.informationhot.kr/",
    "https://fsched.informationhot.kr/",
    "https://betguide.informationhot.kr/",
    "https://protoking.informationhot.kr/",
    # SAP — Blogger (rotcha subdomains)
    "https://sports.rotcha.kr/",
    "https://kbo.rotcha.kr/",
    # AI Korea
    "https://aikorea24.kr/",
    "https://persona.aikorea24.kr/",
    # Techpawz — 보유 도메인
    "https://techpawz.com/",
    "https://senior.techpawz.com/",
    "https://ev.techpawz.com/",
    # Rotcha root
    "https://rotcha.kr/",
    # ETAP 36 (Track C — 2026-08-22, GSC 도메인 전부 등록 확인됨)
    "https://adventure.techpawz.com/",
    "https://airlines.techpawz.com/",
    "https://airports.techpawz.com/",
    "https://bus.techpawz.com/",
    "https://citytours.techpawz.com/",
    "https://cruise.techpawz.com/",
    "https://culture.techpawz.com/",
    "https://daytrips.techpawz.com/",
    "https://deals.techpawz.com/",
    "https://dining.techpawz.com/",
    "https://escape.techpawz.com/",
    "https://esim.techpawz.com/",
    "https://eurail.techpawz.com/",
    "https://extreme.techpawz.com/",
    "https://ferry.techpawz.com/",
    "https://flights.techpawz.com/",
    "https://foodtour.techpawz.com/",
    "https://ghost.techpawz.com/",
    "https://hiking.techpawz.com/",
    "https://layover.techpawz.com/",
    "https://luxury.techpawz.com/",
    "https://michelin.techpawz.com/",
    "https://multiday.techpawz.com/",
    "https://nature.techpawz.com/",
    "https://nightlife.techpawz.com/",
    "https://nomad.techpawz.com/",
    "https://phototour.techpawz.com/",
    "https://tour.techpawz.com/",
    "https://tours.techpawz.com/",
    "https://trains.techpawz.com/",
    "https://transfers.techpawz.com/",
    "https://visa.techpawz.com/",
    "https://visafree.techpawz.com/",
    "https://walking.techpawz.com/",
    "https://watersports.techpawz.com/",
    "https://watertours.techpawz.com/",
]

# ── URL → blog_id 매핑 (GSC 결과 blog_id 변환용) ──
URL_TO_BLOG_ID = {
    # Travel
    "travel.rotcha.kr": "travel-hugo",
    "tour1.rotcha.kr": "travel1-hugo",
    "travel1.rotcha.kr": "travel1-hugo",
    "travel2.rotcha.kr": "travel2-hugo",
    "tour2.rotcha.kr": "travel2-hugo",
    "tour3.rotcha.kr": "travel3-hugo",
    "travel3.rotcha.kr": "travel3-hugo",
    "travel4.rotcha.kr": "travel4-hugo",
    # Stock
    "stock.informationhot.kr": "stock-hugo",
    "etf.techpawz.com": "etf-hugo",
    "dividend.techpawz.com": "dividend-hugo",
    "sector.techpawz.com": "sector-hugo",
    "ipo.techpawz.com": "ipo-hugo",
    "finance.techpawz.com": "finance-hugo",
    # RAP
    "rap.rotcha.kr": "rap-hugo",
    # LAP
    "tco.rotcha.kr": "tco-hugo",
    "deal.rotcha.kr": "deal-hugo",
    "compare.rotcha.kr": "compare-hugo",
    "guide.rotcha.kr": "guide-hugo",
    "ev.rotcha.kr": "ev-hugo",
    # Legacy
    "kuta.informationhot.kr": "kuta-wordpress",
    # Info
    "hotissue.rotcha.kr": "hotissue-hugo",
    # SAP
    "kboplayer.informationhot.kr": "kboplayer",
    "kboteam.informationhot.kr": "kboteam",
    "kboschedule.informationhot.kr": "kboschedule",
    "proto.informationhot.kr": "proto",
    "protostats.informationhot.kr": "protostats",
    "fstats.informationhot.kr": "fstats",
    "fsched.informationhot.kr": "fsched",
    "betguide.informationhot.kr": "betguide",
    "protoking.informationhot.kr": "protoking",
    "sports.rotcha.kr": "sports-rotcha",
    "kbo.rotcha.kr": "kbo-rotcha",
    # AI Korea
    "aikorea24.kr": "aikorea24",
    "persona.aikorea24.kr": "persona-aikorea24",
    # ETAP 36 (Track C — 2026-08-22, gsc_pages 수집용)
    "adventure.techpawz.com": "adventure-hugo",
    "airlines.techpawz.com": "airlines-hugo",
    "airports.techpawz.com": "airports-hugo",
    "bus.techpawz.com": "bus-hugo",
    "citytours.techpawz.com": "citytours-hugo",
    "cruise.techpawz.com": "cruise-hugo",
    "culture.techpawz.com": "culture-hugo",
    "daytrips.techpawz.com": "daytrips-hugo",
    "deals.techpawz.com": "deals-hugo",
    "dining.techpawz.com": "dining-hugo",
    "escape.techpawz.com": "escape-hugo",
    "esim.techpawz.com": "esim-hugo",
    "eurail.techpawz.com": "eurail-hugo",
    "extreme.techpawz.com": "extreme-hugo",
    "ferry.techpawz.com": "ferry-hugo",
    "flights.techpawz.com": "flights-hugo",
    "foodtour.techpawz.com": "foodtour-hugo",
    "ghost.techpawz.com": "ghost-hugo",
    "hiking.techpawz.com": "hiking-hugo",
    "layover.techpawz.com": "layover-hugo",
    "luxury.techpawz.com": "luxury-hugo",
    "michelin.techpawz.com": "michelin-hugo",
    "multiday.techpawz.com": "multiday-hugo",
    "nature.techpawz.com": "nature-hugo",
    "nightlife.techpawz.com": "nightlife-hugo",
    "nomad.techpawz.com": "nomad-hugo",
    "phototour.techpawz.com": "phototour-hugo",
    "tour.techpawz.com": "tour-hugo",
    "tours.techpawz.com": "tours-hugo",
    "trains.techpawz.com": "trains-hugo",
    "transfers.techpawz.com": "transfers-hugo",
    "visa.techpawz.com": "visa-hugo",
    "visafree.techpawz.com": "visafree-hugo",
    "walking.techpawz.com": "walking-hugo",
    "watersports.techpawz.com": "watersports-hugo",
    "watertours.techpawz.com": "watertours-hugo",
}

# ── Bing API 키 ──
_BING_KEY_1 = os.getenv("BING_WEBMASTER_API_KEY")
_BING_KEY_2 = os.getenv("BING_WEBMASTER_API_KEY_2")
_BING_KEY_3 = os.getenv("BING_WEBMASTER_API_KEY_3")
BING_KEYS = [k for k in [_BING_KEY_1, _BING_KEY_2, _BING_KEY_3] if k]


# ═══════════════════════════════════════════════════════════════
#  Helper: Google OAuth
# ═══════════════════════════════════════════════════════════════


def _get_oauth_token(label: str = "default", account: int = 1) -> Credentials:
    """
    GA4/GSC 공용 OAuth Credentials 반환.
    account: 1=twinssn, 2=informationhot, 3=aikorea24
    """
    suffix = {1: "1_twinssn", 2: "2_informationhot", 3: "3_aikorea24"}.get(account, "1_twinssn")
    token_path = _CREDENTIALS_DIR / f"token_{suffix}.json"
    creds = None

    if token_path.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_path), GOOGLE_SCOPES)
        except Exception as e:
            logger.warning(f"[{label}] 토큰 로드 실패: {e}")

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            return creds
        except Exception as e:
            logger.warning(f"[{label}] 토큰 갱신 실패: {e}")

    # 새 OAuth 인증 (최초 1회 필요)
    if not _PRIMARY_CLIENT_SECRET.exists():
        raise FileNotFoundError(
            f"Client secret not found: {_PRIMARY_CLIENT_SECRET}"
        )
    flow = InstalledAppFlow.from_client_secrets_file(
        str(_PRIMARY_CLIENT_SECRET), GOOGLE_SCOPES
    )
    creds = flow.run_local_server(port=0)
    _CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
    with open(token_path, "w") as f:
        f.write(creds.to_json())
    return creds


def _get_adsense_token(account: int = 1) -> Credentials:
    """AdSense 전용 OAuth Credentials 반환."""
    suffix = {1: "1_twinssn", 2: "2_informationhot", 3: "3_aikorea24"}.get(account, "1_twinssn")
    token_path = _CREDENTIALS_DIR / f"token_{suffix}.json"
    secret_path = _CREDENTIALS_DIR / f"ADSENSE_CREDENTIALS_{account}twinssn.json"

    adsense_scopes = ["https://www.googleapis.com/auth/adsense.readonly"]

    creds = None
    if token_path.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_path), adsense_scopes)
        except Exception:
            pass

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            return creds
        except Exception:
            pass

    if not secret_path.exists():
        raise FileNotFoundError(f"AdSense client secret not found: {secret_path}")

    flow = InstalledAppFlow.from_client_secrets_file(str(secret_path), adsense_scopes)
    creds = flow.run_local_server(port=0)
    _CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
    with open(token_path, "w") as f:
        f.write(creds.to_json())
    return creds


# ═══════════════════════════════════════════════════════════════
#  Helper: DB
# ═══════════════════════════════════════════════════════════════


def _db() -> sqlite3.Connection:
    """DB 연결. WAL 모드 + 타임아웃 30초로 경합 완화."""
    conn = sqlite3.connect(str(ANALYTICS_DB), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


# ═══════════════════════════════════════════════════════════════
#  Helper: retry decorator
# ═══════════════════════════════════════════════════════════════

import functools


def _is_auth_error(e: Exception) -> bool:
    """인증/권한 오류(재시도 금지 대상): 401/403."""
    if isinstance(e, HttpError):
        return e.status_code in (401, 403)
    return False


def retry(max_attempts=3, delay_seconds=5):
    """일시 네트워크/DNS 오류에만 제한된 재시도 (bounded exponential backoff).

    인증/권한 오류(HttpError 401/403)는 재시도하지 않고 즉시 상위로 전파.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if _is_auth_error(e):
                        logger.error(
                            f"[RETRY] {func.__name__} 인증/권한 오류 — 재시도 안 함: {e}"
                        )
                        raise
                    if attempt < max_attempts:
                        wait = delay_seconds * (2 ** (attempt - 1))
                        logger.warning(
                            f"[RETRY] {func.__name__} ({attempt}/{max_attempts}) "
                            f"일시 오류: {e}. {wait:.0f}초 후 재시도..."
                        )
                        _time.sleep(wait)
                    else:
                        logger.error(
                            f"[RETRY] {func.__name__} 최종 실패 "
                            f"({max_attempts}/{max_attempts}): {e}"
                        )
                        raise
            raise last_exception  # type: ignore
        return wrapper
    return decorator


# ═══════════════════════════════════════════════════════════════
#  GA4 Collector
# ═══════════════════════════════════════════════════════════════


def collect_ga4(days: int = 3) -> dict:
    """
    GA4 페이지뷰/세션/수익 데이터 수집 → ga4_daily 테이블에 INSERT.
    """
    from google.analytics.data_v1beta import BetaAnalyticsDataClient
    from google.analytics.data_v1beta.types import (
        DateRange,
        Dimension,
        Metric,
        RunReportRequest,
    )
    from google.analytics.admin import AnalyticsAdminServiceClient

    logger.info("=== GA4 수집 시작 ===")
    creds = _get_oauth_token("ga4")
    client = BetaAnalyticsDataClient(credentials=creds)
    admin = AnalyticsAdminServiceClient(credentials=creds)

    KRW_PER_USD = 1350.0  # 고정 환율
    end_date = datetime.now() - timedelta(days=1)
    start_date = end_date - timedelta(days=days - 1)
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    total_rows = 0
    total_pv = 0
    total_rev = 0.0
    total_sites = 0
    errors = []

    conn = _db()

    for blog_id, prop_id in GA4_PROPERTIES.items():
        if not prop_id:
            logger.info(f"  [{blog_id}] GA4 속성 미등록, 스킵")
            continue

        try:
            # 통화 확인
            try:
                prop = admin.get_property(name=f"properties/{prop_id}")
                currency = prop.currency_code
            except Exception:
                currency = "USD"
            to_usd = 1.0 / KRW_PER_USD if currency == "KRW" else 1.0

            request = RunReportRequest(
                property=f"properties/{prop_id}",
                date_ranges=[DateRange(start_date=start_str, end_date=end_str)],
                dimensions=[
                    Dimension(name="date"),
                    Dimension(name="sessionDefaultChannelGroup"),
                ],
                metrics=[
                    Metric(name="screenPageViews"),
                    Metric(name="sessions"),
                    Metric(name="totalUsers"),
                    Metric(name="bounceRate"),
                    Metric(name="engagementRate"),
                    Metric(name="totalAdRevenue"),
                    Metric(name="advertiserAdImpressions"),
                ],
                limit=10000,
            )
            response = client.run_report(request=request)

            site_rows = 0
            for row in response.rows:
                date_str = row.dimension_values[0].value
                channel = row.dimension_values[1].value
                date_fmt = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"

                pv = int(row.metric_values[0].value)
                sessions = int(row.metric_values[1].value)
                users = int(row.metric_values[2].value)
                bounce = float(row.metric_values[3].value or 0)
                engagement = float(row.metric_values[4].value or 0)
                revenue = float(row.metric_values[5].value or 0) * to_usd
                impressions = int(row.metric_values[6].value or 0)

                rpm = (revenue / sessions * 1000) if sessions > 0 else 0

                conn.execute(
                    """INSERT OR REPLACE INTO ga4_daily
                       (blog_id, date, sessions, total_users, new_users, page_views,
                        avg_session_duration, bounce_rate, engaged_sessions,
                        engagement_rate, ad_revenue, ad_impressions, ad_clicks,
                        rpm, collected_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?, datetime('now','localtime'))""",
                    (
                        blog_id, date_fmt,
                        sessions, users, 0, pv,
                        0.0, round(bounce, 2), 0,
                        round(engagement, 2), round(revenue, 6), impressions, 0,
                        round(rpm, 4),
                    ),
                )
                site_rows += 1
                total_pv += pv
                total_rev += revenue

            conn.commit()
            total_rows += site_rows
            total_sites += 1
            logger.info(f"  [{blog_id}] {site_rows}건 (PV {pv:,}, Rev ${revenue:.2f})")

        except Exception as e:
            if _is_auth_error(e):
                logger.error(
                    f"ANALYTICS_AUTH_ERROR: GA4 {blog_id} "
                    f"status={getattr(e, 'status_code', '?')} — 사이트 skip"
                )
            errors.append(f"{blog_id}: {e}")
            logger.error(f"  [{blog_id}] 오류: {e}")

    conn.close()
    logger.info(
        f"GA4 완료: {total_sites}개 사이트, {total_rows}건, "
        f"{total_pv:,} PV, ${total_rev:.2f}"
    )
    if errors:
        logger.warning(f"GA4 오류 발생 사이트: {errors}")
    return {
        "status": "ok",
        "source": "ga4",
        "sites": total_sites,
        "rows": total_rows,
        "total_pv": total_pv,
        "total_revenue": round(total_rev, 2),
        "errors": errors,
    }


# ═══════════════════════════════════════════════════════════════
#  GSC Collector
# ═══════════════════════════════════════════════════════════════


@retry(max_attempts=3, delay_seconds=5)
def collect_gsc(days: int = 1) -> dict:
    """
    GSC 검색 성과 데이터 수집 → gsc_daily_summary + gsc_keywords INSERT.
    3개 계정(twinssn/informationhot/aikorea24) 순차 조회.
    """
    from googleapiclient.discovery import build

    logger.info("=== GSC 수집 시작 ===")
    target_date = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
    total_clicks = 0
    total_impressions = 0
    total_sites = 0
    total_keywords = 0
    errors = []

    conn = _db()

    for account_num in [1, 2, 3]:
        try:
            creds = _get_oauth_token("gsc", account=account_num)
            service = build("webmasters", "v3", credentials=creds)
        except Exception as e:
            logger.warning(f"  GSC 계정 {account_num} 토큰 실패: {e}")
            continue

        for site_url in GSC_SITES:
            name = site_url.replace("https://", "").rstrip("/")
            blog_id = URL_TO_BLOG_ID.get(name, name)

            try:
                resp = service.searchanalytics().query(
                    siteUrl=site_url,
                    body={
                        "startDate": target_date,
                        "endDate": target_date,
                        "dimensions": ["query", "page"],
                        "rowLimit": 500,
                    },
                ).execute()

                rows = resp.get("rows", [])
                clicks = sum(r["clicks"] for r in rows)
                impressions = sum(r["impressions"] for r in rows)
                ctr = (clicks / impressions * 100) if impressions > 0 else 0
                pos = (
                    sum(r["impressions"] * r["position"] for r in rows) / impressions
                    if impressions > 0
                    else 0
                )

                total_clicks += clicks
                total_impressions += impressions

                # gsc_daily_summary INSERT
                conn.execute(
                    """INSERT OR REPLACE INTO gsc_daily_summary
                       (blog_id, date, total_clicks, total_impressions,
                        avg_ctr, avg_position, page_count, collected_at)
                       VALUES (?,?,?,?,?,?,?, datetime('now','localtime'))""",
                    (
                        blog_id, target_date,
                        int(clicks), int(impressions),
                        round(ctr, 2), round(pos, 1),
                        len(rows),
                    ),
                )

                # gsc_keywords INSERT (상위 100개)
                sorted_rows = sorted(rows, key=lambda r: r["impressions"], reverse=True)[:100]
                for row in sorted_rows:
                    kw_query = row["keys"][0]
                    kw_page = row["keys"][1] if len(row["keys"]) > 1 else ""
                    conn.execute(
                        """INSERT OR REPLACE INTO gsc_keywords
                           (blog_id, date, query, page, clicks, impressions,
                            ctr, position, collected_at)
                           VALUES (?,?,?,?,?,?,?,?, datetime('now','localtime'))""",
                        (
                            blog_id, target_date, kw_query, kw_page,
                            int(row["clicks"]), int(row["impressions"]),
                            round(row["ctr"] * 100, 2), round(row["position"], 1),
                        ),
                    )

                total_keywords += len(sorted_rows)
                total_sites += 1
                logger.info(
                    f"  [{blog_id}] 계정{account_num} 클릭 {clicks}, 노출 {impressions}, "
                    f"키워드 {len(sorted_rows)}개"
                )

                # ── gsc_pages INSERT (Track C — 2026-08-22) ──
                # 페이지 단위 조회: 색인/노출 per page 확인용 (charter: GSC 노출/클릭 우선순위)
                try:
                    page_resp = service.searchanalytics().query(
                        siteUrl=site_url,
                        body={
                            "startDate": target_date,
                            "endDate": target_date,
                            "dimensions": ["page"],
                            "rowLimit": 1000,
                        },
                    ).execute()
                    for prow in page_resp.get("rows", []):
                        page_url = prow["keys"][0]
                        conn.execute(
                            """INSERT OR REPLACE INTO gsc_pages
                               (blog_id, date, page, clicks, impressions, ctr, position, collected_at)
                               VALUES (?,?,?,?,?,?,?, datetime('now','localtime'))""",
                            (
                                blog_id, target_date, page_url,
                                int(prow["clicks"]), int(prow["impressions"]),
                                round(prow["ctr"] * 100, 2), round(prow["position"], 1),
                            ),
                        )
                except Exception as page_e:
                    logger.warning(
                        f"  gsc_pages 수집 실패 [{blog_id}]: {str(page_e)[:80]}"
                    )

            except Exception as e:
                if _is_auth_error(e):
                    # 사이트 권한/인증 오류(403 등): 해당 사이트만 skip + 분류 마커
                    logger.error(
                        f"ANALYTICS_AUTH_ERROR: GSC {blog_id} "
                        f"status={getattr(e, 'status_code', '?')} — 사이트 skip"
                    )
                errors.append(f"계정{account_num}/{blog_id}: {str(e)[:100]}")
                # 권한 오류는 재시도하지 않고 다음 사이트로 진행
                continue

    conn.commit()
    conn.close()
    logger.info(
        f"GSC 완료: {total_sites}개 사이트, "
        f"클릭 {total_clicks}, 노출 {total_impressions}, 키워드 {total_keywords}"
    )
    if errors:
        logger.warning(f"GSC 오류 발생 ({len(errors)}건): {errors[:5]}")
    return {
        "status": "ok",
        "source": "gsc",
        "date": target_date,
        "sites": total_sites,
        "clicks": total_clicks,
        "impressions": total_impressions,
        "keywords": total_keywords,
        "errors": errors,
    }


# ═══════════════════════════════════════════════════════════════
#  AdSense Collector
# ═══════════════════════════════════════════════════════════════


@retry(max_attempts=2, delay_seconds=5)
def collect_adsense(days: int = 3) -> dict:
    """
    Google AdSense 수익 데이터 수집 → adsense_daily INSERT.

    계정 1(twinssn)과 계정 2(informationhot)를 순차 조회.
    """
    from googleapiclient.discovery import build

    logger.info("=== AdSense 수집 시작 ===")
    end_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days - 1)).strftime("%Y-%m-%d")

    total_rows = 0
    total_earnings = 0.0
    errors = []
    conn = _db()

    # 계정 1 (twinssn): primary AdSense
    for account_num in [1, 2]:
        try:
            creds = _get_adsense_token(account_num)
            adsense = build("adsense", "v2", credentials=creds)

            # 계정 목록
            accounts = adsense.accounts().list().execute()
            for acct in accounts.get("accounts", []):
                acct_name = acct["name"]  # "accounts/pub-xxx"

                # 데일리 리포트
                report = (
                    adsense.accounts()
                    .reports()
                    .generate(
                        account=acct_name,
                        dateRange="CUSTOM",
                        startDate_year=int(start_date[:4]),
                        startDate_month=int(start_date[5:7]),
                        startDate_day=int(start_date[8:10]),
                        endDate_year=int(end_date[:4]),
                        endDate_month=int(end_date[5:7]),
                        endDate_day=int(end_date[8:10]),
                        dimensions=["DATE", "DOMAIN_NAME"],
                        metrics=[
                            "ESTIMATED_EARNINGS",
                            "PAGE_VIEWS",
                            "CLICKS",
"PAGE_VIEWS_RPM",
"PAGE_VIEWS_CTR",
                        ],
                    )
                ).execute()

                for row in report.get("rows", []):
                    cells = row.get("cells", [])
                    if len(cells) < 6:
                        continue
                    date_str = cells[0].get("value", "")
                    domain = cells[1].get("value", "unknown")
                    earnings = float(cells[2].get("value", 0))
                    pv = int(float(cells[3].get("value", 0)))
                    clicks = int(float(cells[4].get("value", 0)))
                    rpm = float(cells[5].get("value", 0))
                    ctr = float(cells[6].get("value", 0)) if len(cells) > 6 else 0

                    conn.execute(
                        """INSERT OR REPLACE INTO adsense_daily
                           (account, domain, date, page_views, clicks,
                            estimated_earnings, rpm, ctr, collected_at)
                           VALUES (?,?,?,?,?,?,?,?, datetime('now','localtime'))""",
                        (
                            f"account-{account_num}",
                            domain,
                            date_str,
                            pv,
                            clicks,
                            round(earnings, 6),
                            round(rpm, 2),
                            round(ctr, 4),
                        ),
                    )
                    total_rows += 1
                    total_earnings += earnings

        except Exception as e:
            if _is_auth_error(e):
                # 인증/권한 오류: 재시도 불가 → 분류 마커 + rc=23 로 shell 전달
                logger.error(
                    f"ANALYTICS_AUTH_ERROR: AdSense account-{account_num} "
                    f"status={getattr(e, 'status_code', '?')} — 재시도 안 함"
                )
                sys.exit(23)
            err_msg = f"account-{account_num}: {e}"
            errors.append(err_msg)
            logger.error(f"  AdSense 계정 {account_num} 오류: {e}")

    conn.commit()
    conn.close()
    logger.info(
        f"AdSense 완료: {total_rows}건, ${total_earnings:.2f}"
    )
    if errors:
        logger.warning(f"AdSense 오류: {errors}")
    return {
        "status": "ok",
        "source": "adsense",
        "rows": total_rows,
        "total_earnings": round(total_earnings, 2),
        "errors": errors,
    }


# ═══════════════════════════════════════════════════════════════
#  Bing Collector
# ═══════════════════════════════════════════════════════════════


def collect_bing() -> dict:
    """
    Bing Webmaster API 키워드/트래픽 데이터 수집 → bing_daily_summary INSERT.
    """
    logger.info("=== Bing 수집 시작 ===")

    if not BING_KEYS:
        logger.warning("Bing API 키 없음, 스킵")
        return {"status": "skipped", "source": "bing", "rows": 0}

    total_sites = 0
    total_keywords = 0
    all_daily = {}
    errors = []

    for api_key in BING_KEYS:
        # 사이트 목록
        try:
            r = requests.get(
                f"https://ssl.bing.com/webmaster/api.svc/json/GetUserSites?apikey={api_key}",
                timeout=15,
            )
            sites = r.json().get("d", [])
        except Exception as e:
            errors.append(f"사이트목록({api_key[:8]}): {e}")
            logger.error(f"  Bing 사이트 목록 실패: {e}")
            continue

        for site_info in sites:
            site_url = site_info.get("Url", "")
            name = site_url.replace("https://", "").replace("http://", "").rstrip("/")
            blog_id = URL_TO_BLOG_ID.get(name, name)

            # 트래픽 통계
            try:
                r = requests.get(
                    f"https://ssl.bing.com/webmaster/api.svc/json/GetRankAndTrafficStats"
                    f"?siteUrl={site_url}&apikey={api_key}",
                    timeout=15,
                )
                stats = r.json().get("d", [])
                for s in stats[-7:]:
                    ts_match = re.search(r"\d+", s["Date"])
                    if not ts_match:
                        continue
                    ts = int(ts_match.group()) / 1000
                    date_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")

                    key = (blog_id, date_str)
                    if key not in all_daily:
                        all_daily[key] = {"clicks": 0, "impressions": 0}
                    all_daily[key]["clicks"] += s.get("Clicks", 0)
                    all_daily[key]["impressions"] += s.get("Impressions", 0)
            except Exception as e:
                errors.append(f"{name} 트래픽: {e}")
                logger.error(f"  {name} 트래픽: {e}")

            # 키워드 통계
            try:
                r = requests.get(
                    f"https://ssl.bing.com/webmaster/api.svc/json/GetQueryStats"
                    f"?siteUrl={site_url}&apikey={api_key}",
                    timeout=15,
                )
                kws = r.json().get("d", [])
                total_keywords += len(kws)
            except Exception as e:
                errors.append(f"{name} 키워드: {e}")

            total_sites += 1

    # DB 저장
    conn = _db()
    row_count = 0
    for (blog_id, date_str), data in all_daily.items():
        conn.execute(
            """INSERT OR REPLACE INTO bing_daily_summary
               (blog_id, date, clicks, impressions, collected_at)
               VALUES (?,?,?,?, datetime('now','localtime'))""",
            (blog_id, date_str, data["clicks"], data["impressions"]),
        )
        row_count += 1
    conn.commit()
    conn.close()

    logger.info(
        f"Bing 완료: {total_sites}개 사이트, {row_count}건 일별, {total_keywords}개 키워드"
    )
    if errors:
        logger.warning(f"Bing 오류: {errors[:3]}")
    return {
        "status": "ok",
        "source": "bing",
        "sites": total_sites,
        "daily_rows": row_count,
        "total_keywords": total_keywords,
        "errors": errors,
    }


# ═══════════════════════════════════════════════════════════════
#  Blog Efficiency Calculator
# ═══════════════════════════════════════════════════════════════


def compute_efficiency() -> dict:
    """
    blog_efficiency 점수 계산:
    (GSC clicks + impressions) / posts_count * 100
    → efficiency_score 0~100 + grade A/B/C/D/F
    """
    logger.info("=== 효율성 점수 계산 시작 ===")
    conn = _db()

    # content.db에서 블로그별 발행 수
    try:
        from shared.db_paths import ARTICLES_DB
    except ImportError:
        ARTICLES_DB = _DATA_DIR / "stap_content.db"

    content_conn = sqlite3.connect(str(ARTICLES_DB))
    rows = content_conn.execute(
        """SELECT blog_id, COUNT(*) as cnt
           FROM articles WHERE status='published'
           GROUP BY blog_id"""
    ).fetchall()
    posts_count = {r[0]: r[1] for r in rows}
    content_conn.close()

    updated = 0
    today = datetime.now().strftime("%Y-%m-%d")

    for blog_id, total_posts in posts_count.items():
        gsc_data = conn.execute(
            """SELECT COALESCE(SUM(total_clicks), 0) as clicks,
                      COALESCE(SUM(total_impressions), 0) as impressions
               FROM gsc_daily_summary
               WHERE blog_id = ? AND date > ?
               GROUP BY blog_id""",
            (blog_id, (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")),
        ).fetchone()

        clicks = gsc_data[0] if gsc_data else 0
        impressions = gsc_data[1] if gsc_data else 0

        # 효율성 점수 = (clicks + impressions*0.01) / posts
        if total_posts > 0:
            score = min(100, (clicks + impressions * 0.01) / total_posts * 100)
        else:
            score = 0

        # 등급
        if score >= 80:
            grade = "A"
        elif score >= 60:
            grade = "B"
        elif score >= 40:
            grade = "C"
        elif score >= 20:
            grade = "D"
        else:
            grade = "F"

        conn.execute(
            """INSERT OR REPLACE INTO blog_efficiency
               (blog_id, date, total_posts, gsc_clicks, gsc_impressions,
                efficiency_score, grade)
               VALUES (?,?,?,?,?,?,?)""",
            (blog_id, today, total_posts, clicks, impressions,
             round(score, 1), grade),
        )
        updated += 1

    conn.commit()
    conn.close()
    logger.info(f"효율성 점수: {updated}개 블로그 업데이트")
    return {"status": "ok", "source": "efficiency", "blog_count": updated}


# ═══════════════════════════════════════════════════════════════
#  Unified Collector
# ═══════════════════════════════════════════════════════════════


class AnalyticsCollector:
    """
    통합 애널리틱스 수집기 — GA4/GSC/AdSense/Bing/efficiency 한 번에 실행.

    사용법:
        from shared.analytics_collector import AnalyticsCollector
        c = AnalyticsCollector()
        results = c.collect_all()
    """

    def collect_ga4(self, days: int = 3) -> dict:
        return collect_ga4(days=days)

    def collect_gsc(self, days: int = 1) -> dict:
        return collect_gsc(days=days)

    def collect_adsense(self, days: int = 3) -> dict:
        return collect_adsense(days=days)

    def collect_bing(self) -> dict:
        return collect_bing()

    def compute_efficiency(self) -> dict:
        return compute_efficiency()

    def collect_all(self, with_efficiency: bool = True) -> dict:
        """
        모든 수집기를 순차 실행. 각 수집기는 독립적 (한 개 실패해도 나머지 계속).
        """
        results = {}
        steps = [
            ("ga4", lambda: self.collect_ga4()),
            ("gsc", lambda: self.collect_gsc()),
            ("adsense", lambda: self.collect_adsense()),
            ("bing", lambda: self.collect_bing()),
        ]

        if with_efficiency:
            steps.append(("efficiency", lambda: self.compute_efficiency()))

        for name, fn in steps:
            try:
                logger.info(f"▶▶▶ {name.upper()} 시작")
                results[name] = fn()
                logger.info(f"✅ {name.upper()} 완료: {results[name].get('status', '?')}")
            except Exception as e:
                logger.error(f"❌ {name.upper()} 실패: {e}")
                results[name] = {"status": "error", "message": str(e)}

        summary = {k: v.get("status", "?") for k, v in results.items()}
        logger.info(f"=== Analytics 수집 완료 === {summary}")
        return results


# ═══════════════════════════════════════════════════════════════
#  CLI Entry Point
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import re as _re

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.StreamHandler(),
        ],
    )

    collector = AnalyticsCollector()

    # CLI 인자로 특정 수집기 선택 가능
    if len(sys.argv) > 1:
        target = sys.argv[1]
        if target == "ga4":
            r = collector.collect_ga4()
        elif target == "gsc":
            r = collector.collect_gsc()
        elif target == "adsense":
            r = collector.collect_adsense()
        elif target == "bing":
            r = collector.collect_bing()
        elif target == "efficiency":
            r = collector.compute_efficiency()
        else:
            print(f"Unknown target: {target}")
            print("Usage: python shared/analytics_collector.py [ga4|gsc|adsense|bing|efficiency]")
            sys.exit(1)
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        r = collector.collect_all()
        print(json.dumps(r, ensure_ascii=False, indent=2))

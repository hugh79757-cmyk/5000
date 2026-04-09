"""Google API 인증 — 3계정 피클 지원 (GSC + AdSense 통합)"""
import os
import pickle
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CRED_DIR = "/Users/twinssn/Projects/blogdex/credentials"

ACCOUNTS = {
    "twinssn": os.path.join(CRED_DIR, "token_1_twinssn.pickle"),
    "informationhot": os.path.join(CRED_DIR, "token_2_informationhot.pickle"),
    "aikorea24": os.path.join(CRED_DIR, "token_3_aikorea24.pickle"),
}

SC_DOMAIN_ACCOUNT = {
    "sc-domain:rotcha.kr": "twinssn",
    "sc-domain:techpawz.com": "twinssn",
    "sc-domain:informationhot.kr": "informationhot",
    "sc-domain:aikorea24.kr": "aikorea24",
}


def get_credentials(account="twinssn"):
    """지정 계정의 OAuth2 credentials 반환."""
    token_path = ACCOUNTS[account]
    with open(token_path, "rb") as f:
        creds = pickle.load(f)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(token_path, "wb") as f:
            pickle.dump(creds, f)
    return creds


def get_gsc_service(account="twinssn"):
    """Search Console API 서비스 객체"""
    return build("searchconsole", "v1", credentials=get_credentials(account))


def get_gsc_service_for_domain(sc_domain):
    """sc-domain에 맞는 계정으로 GSC 서비스 반환"""
    account = SC_DOMAIN_ACCOUNT.get(sc_domain, "twinssn")
    return get_gsc_service(account)


def get_ga4_service(account="twinssn"):
    """GA4 Data API 서비스 객체"""
    return build("analyticsdata", "v1beta", credentials=get_credentials(account))

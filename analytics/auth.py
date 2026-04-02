"""Google API 인증 — GSC + GA4 공용"""
import os
import pickle
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/webmasters.readonly",
    "https://www.googleapis.com/auth/analytics.readonly",
]

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN_PATH = os.path.join(PROJECT_ROOT, "data", "google_token.pickle")
CLIENT_SECRET = os.path.join(PROJECT_ROOT, "config", "client_secret_hugh7973.json")


def get_credentials():
    """OAuth2 credentials 반환. 토큰 없으면 브라우저 인증."""
    creds = None
    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH, "rb") as f:
            creds = pickle.load(f)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, "wb") as f:
            pickle.dump(creds, f)
    return creds


def get_gsc_service():
    """Search Console API 서비스 객체"""
    return build("searchconsole", "v1", credentials=get_credentials())


def get_ga4_service():
    """GA4 Data API 서비스 객체 (REST)"""
    return build("analyticsdata", "v1beta", credentials=get_credentials())

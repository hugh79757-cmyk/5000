from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import json

SCOPES = ['https://www.googleapis.com/auth/webmasters.readonly']
SITE_URL = 'https://rotcha.kr/'

# 인증 (처음 실행 시 브라우저 열림)
flow = InstalledAppFlow.from_client_secrets_file(
    '/Users/twinssn/Desktop/client_secret_801186388273-58sb9uc6af7mh27tnl2jfspnvdgmune4.apps.googleusercontent.com.json',  # Google Cloud Console에서 다운로드
    SCOPES
)
creds = flow.run_local_server(port=0)

service = build('searchconsole', 'v1', credentials=creds)

# 최근 3개월 데이터
request = {
    'startDate': '2025-10-15',
    'endDate': '2026-01-15',
    'dimensions': ['page'],
    'rowLimit': 1000
}

response = service.searchanalytics().query(siteUrl=SITE_URL, body=request).execute()

# 클릭수 기준 정렬
pages = response.get('rows', [])
pages.sort(key=lambda x: x['clicks'])

print("=== 클릭 0인 페이지 (삭제 후보) ===")
zero_clicks = [p for p in pages if p['clicks'] == 0]
for p in zero_clicks[:20]:
    print(p['keys'][0])

print(f"\n총 {len(zero_clicks)}개 페이지가 클릭 0")

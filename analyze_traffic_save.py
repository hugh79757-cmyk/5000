from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/webmasters.readonly']
SITE_URL = 'https://rotcha.kr/'

flow = InstalledAppFlow.from_client_secrets_file(
    '/Users/twinssn/Desktop/client_secret_801186388273-58sb9uc6af7mh27tnl2jfspnvdgmune4.apps.googleusercontent.com.json',
    SCOPES
)
creds = flow.run_local_server(port=0)
service = build('searchconsole', 'v1', credentials=creds)

request = {
    'startDate': '2025-10-15',
    'endDate': '2026-01-15',
    'dimensions': ['page'],
    'rowLimit': 1000
}

response = service.searchanalytics().query(siteUrl=SITE_URL, body=request).execute()
pages = response.get('rows', [])

# 클릭 0인 페이지 저장
zero_clicks = [p for p in pages if p['clicks'] == 0]

with open('/Users/twinssn/Desktop/rotcha-hugo/zero_clicks.txt', 'w') as f:
    for p in zero_clicks:
        f.write(p['keys'][0] + '\n')

print(f"✅ {len(zero_clicks)}개 클릭 0 페이지 저장 완료!")
print("📁 /Users/twinssn/Desktop/rotcha-hugo/zero_clicks.txt")

"""부동산 API 승인 상태 체크 스크립트"""
import os, requests
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
API_KEY = os.getenv("DATA_GO_KR_API_KEY", "")

tests = [
    {
        "name": "아파트 매매 실거래가",
        "url": "https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev",
        "params": {"LAWD_CD": "11680", "DEAL_YMD": "202602", "pageNo": "1", "numOfRows": "3"},
    },
    {
        "name": "청약홈 분양정보",
        "url": "http://apis.data.go.kr/B552555/lhLeaseNoticeInfo1/lhLeaseNoticeInfo1",
        "params": {"PG_SZ": "3", "PAGE": "1", "CNP_CD": "11"},
    },
    {
        "name": "LH 공공임대주택 단지정보",
        "url": "https://apis.data.go.kr/B552555/lhLeaseInfo1/lhLeaseInfo1",
        "params": {"PG_SZ": "3", "PAGE": "1", "CNP_CD": "11"},
    },
    {
        "name": "LH 분양임대공고문",
        "url": "https://apis.data.go.kr/B552555/lhNoticeInfo1/lhNoticeInfo1",
        "params": {"PG_SZ": "3", "PAGE": "1"},
    },
]

for t in tests:
    t["params"]["serviceKey"] = API_KEY
    try:
        r = requests.get(t["url"], params=t["params"], timeout=15)
        if r.status_code == 200:
            body = r.text[:300]
            if "SERVICE_KEY_IS_NOT_REGISTERED_ERROR" in body:
                status = "미승인 (키 미등록)"
            elif "dsList" in body or "item" in body or "resultCode" in body:
                status = "승인완료"
                # 데이터 건수 확인
                try:
                    import json
                    data = json.loads(r.text) if r.text.startswith("[") or r.text.startswith("{") else None
                    if isinstance(data, list) and len(data) > 1:
                        items = data[1].get("dsList", [])
                        status += f" ({len(items)}건)"
                except:
                    pass
            else:
                status = f"응답확인필요: {body[:100]}"
        elif r.status_code == 403:
            status = "미승인 (403)"
        else:
            status = f"HTTP {r.status_code}: {r.text[:100]}"
    except Exception as e:
        status = f"접속실패: {str(e)[:60]}"
    
    mark = "✓" if "승인완료" in status else "✗"
    print(f"  {mark} {t['name']}: {status}")

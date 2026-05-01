"""RAP fetcher — 부동산 공공데이터 API 수집"""
import os
import logging
import requests
import xml.etree.ElementTree as ET
from datetime import datetime

logger = logging.getLogger(__name__)

API_KEY = None

def _get_key():
    global API_KEY
    if not API_KEY:
        API_KEY = os.getenv("DATA_GO_KR_API_KEY", "")
    return API_KEY


# ─── 아파트 매매 실거래가 ───

def fetch_apt_trade(lawd_cd, deal_ymd=None, rows=30):
    """아파트 매매 실거래가 조회
    Args:
        lawd_cd: 법정동코드 앞5자리 (예: 11680=강남구)
        deal_ymd: 거래년월 YYYYMM (기본: 이번달)
        rows: 조회건수
    Returns:
        list of dict (aptNm, dealAmount, excluUseAr, floor, umdNm, buildYear, dealYear, dealMonth, dealDay, ...)
    """
    if not deal_ymd:
        deal_ymd = datetime.now().strftime("%Y%m")
    
    url = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade"
    try:
        r = requests.get(url, params={
            "serviceKey": _get_key(),
            "LAWD_CD": lawd_cd,
            "DEAL_YMD": deal_ymd,
            "pageNo": "1",
            "numOfRows": str(rows),
        }, timeout=20)
        r.raise_for_status()
        
        root = ET.fromstring(r.text)
        result_code = root.findtext('.//resultCode', '')
        if result_code != '000':
            logger.error(f"실거래가 API 오류: {root.findtext('.//resultMsg', '')}")
            return []
        
        items = []
        for item in root.findall('.//item'):
            data = {}
            for child in item:
                data[child.tag] = (child.text or "").strip()
            # 가격 정규화 (쉼표 제거, 정수 변환)
            if data.get("dealAmount"):
                try:
                    data["dealAmountInt"] = int(data["dealAmount"].replace(",", ""))
                except ValueError:
                    data["dealAmountInt"] = 0
            items.append(data)
        
        logger.info(f"실거래가 조회: {lawd_cd}/{deal_ymd} → {len(items)}건")
        return items
    except Exception as e:
        logger.error(f"실거래가 API 실패: {e}")
        return []


def fetch_apt_trade_multi(lawd_cd, months=3, rows=50):
    """최근 N개월 실거래가 조회"""
    from datetime import datetime
    from dateutil.relativedelta import relativedelta
    
    all_items = []
    now = datetime.now()
    for i in range(months):
        ym = (now - relativedelta(months=i)).strftime("%Y%m")
        items = fetch_apt_trade(lawd_cd, ym, rows)
        all_items.extend(items)
    return all_items


# ─── 청약홈 분양정보 ───


def fetch_apt_rent(lawd_cd: str, deal_ymd: str, rows: int = 30) -> list:
    """아파트 전월세 실거래 데이터 조회"""
    url = "https://apis.data.go.kr/1613000/RTMSDataSvcAptRent/getRTMSDataSvcAptRent"
    params = {
        "serviceKey": _get_key(),
        "LAWD_CD": lawd_cd,
        "DEAL_YMD": deal_ymd,
        "pageNo": "1",
        "numOfRows": str(rows),
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        if resp.status_code == 403:
            logger.warning(f"전월세 API 403 (미승인 또는 반영대기): {lawd_cd}/{deal_ymd}")
            return []
        resp.raise_for_status()
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "xml")
        items = soup.select("item")
        results = []
        for it in items:
            deposit = it.select_one("deposit")
            monthly = it.select_one("monthlyRent")
            deposit_val = deposit.text.strip().replace(",", "") if deposit else "0"
            monthly_val = monthly.text.strip().replace(",", "") if monthly else "0"
            try:
                deposit_int = int(deposit_val)
            except ValueError:
                deposit_int = 0
            try:
                monthly_int = int(monthly_val)
            except ValueError:
                monthly_int = 0
            rent_type = "월세" if monthly_int > 0 else "전세"
            entry = {
                "aptNm": it.select_one("aptNm").text.strip() if it.select_one("aptNm") else "",
                "excluUseAr": it.select_one("excluUseAr").text.strip() if it.select_one("excluUseAr") else "",
                "floor": it.select_one("floor").text.strip() if it.select_one("floor") else "",
                "buildYear": it.select_one("buildYear").text.strip() if it.select_one("buildYear") else "",
                "umdNm": it.select_one("umdNm").text.strip() if it.select_one("umdNm") else "",
                "dealYear": it.select_one("dealYear").text.strip() if it.select_one("dealYear") else "",
                "dealMonth": it.select_one("dealMonth").text.strip() if it.select_one("dealMonth") else "",
                "dealDay": it.select_one("dealDay").text.strip() if it.select_one("dealDay") else "",
                "deposit": deposit_val,
                "depositInt": deposit_int,
                "monthlyRent": monthly_val,
                "monthlyRentInt": monthly_int,
                "rentType": rent_type,
            }
            results.append(entry)
        logger.info(f"전월세 조회: {lawd_cd}/{deal_ymd} → {len(results)}건 (전세 {sum(1 for r in results if r['rentType']=='전세')}, 월세 {sum(1 for r in results if r['rentType']=='월세')})")
        return results
    except Exception as e:
        logger.error(f"전월세 API 실패: {e}")
        return []

def fetch_subscription_info(region_cd=None, page_size=10):
    """청약홈 분양/임대 공고 조회
    Args:
        region_cd: 지역코드 (11=서울, 26=부산, 27=대구, 28=인천, 29=광주, 30=대전, 31=울산, 36=세종, 41=경기, ...)
        page_size: 조회건수
    Returns:
        list of dict (PAN_NM, CNP_CD_NM, PAN_NT_ST_DT, CLSG_DT, AIS_TP_CD_NM, PAN_SS, DTL_URL, ...)
    """
    url = "http://apis.data.go.kr/B552555/lhLeaseNoticeInfo1/lhLeaseNoticeInfo1"
    params = {
        "serviceKey": _get_key(),
        "PG_SZ": str(page_size),
        "PAGE": "1",
    }
    if region_cd:
        params["CNP_CD"] = region_cd
    
    try:
        r = requests.get(url, params=params, timeout=20)
        r.raise_for_status()
        data = r.json()
        
        if isinstance(data, list) and len(data) > 1:
            items = data[1].get("dsList", [])
            logger.info(f"청약홈 조회: region={region_cd} → {len(items)}건")
            return items
        return []
    except Exception as e:
        logger.error(f"청약홈 API 실패: {e}")
        return []


# ─── 법정동코드 매핑 ───

LAWD_MAP = {
    "서울": {"강남구": "11680", "서초구": "11650", "송파구": "11710", "강동구": "11740",
             "마포구": "11440", "용산구": "11170", "성동구": "11200", "광진구": "11215",
             "영등포구": "11560", "동작구": "11590", "관악구": "11620", "양천구": "11470",
             "강서구": "11500", "구로구": "11530", "금천구": "11545", "노원구": "11350",
             "도봉구": "11320", "강북구": "11305", "성북구": "11290", "동대문구": "11230",
             "중랑구": "11260", "종로구": "11110", "중구": "11140", "서대문구": "11410",
             "은평구": "11380"},
    "부산": {"해운대구": "26350", "수영구": "26410", "남구": "26290", "동래구": "26260"},
    "대구": {"수성구": "27260", "달서구": "27290", "중구": "27110", "동구": "27140"},
    "인천": {"연수구": "28185", "남동구": "28200", "서구": "28260", "부평구": "28237"},
    "광주": {"서구": "29140", "북구": "29110", "남구": "29155", "광산구": "29200"},
    "대전": {"서구": "30170", "유성구": "30200", "중구": "30110", "동구": "30140"},
    "울산": {"남구": "31140", "중구": "31110", "동구": "31170", "북구": "31200", "울주군": "31710"},
    "세종": {"세종시": "36110"},
    "경기": {"수원시장안구": "41111", "수원시권선구": "41113", "수원시팔달구": "41115", "수원시영통구": "41117", "성남시수정구": "41131", "성남시중원구": "41133", "성남시분당구": "41135", "고양시덕양구": "41281", "고양시일산동구": "41285", "고양시일산서구": "41287", "용인시처인구": "41461", "용인시기흥구": "41463", "용인시수지구": "41465",
             "화성시": "41590", "평택시": "41220", "안양시만안구": "41171", "안양시동안구": "41173", "안산시상록구": "41271", "안산시단원구": "41273",
             "파주시": "41480", "김포시": "41570", "광주시": "41610", "하남시": "41450",
             "광명시": "41210", "군포시": "41410", "시흥시": "41390", "오산시": "41370"},
    "강원": {"춘천시": "42110", "원주시": "42130", "강릉시": "42150"},
    "충북": {"청주시상당구": "43111", "청주시서원구": "43112", "청주시흥덕구": "43113", "청주시청원구": "43114", "충주시": "43130"},
    "충남": {"천안시동남구": "44131", "천안시서북구": "44133", "아산시": "44200"},
    "전북": {"전주시완산구": "45111", "전주시덕진구": "45113", "익산시": "45130"},
    "전남": {"여수시": "46130", "순천시": "46150"},
    "경북": {"포항시남구": "47111", "포항시북구": "47113", "구미시": "47190", "경주시": "47130"},
    "경남": {"창원시의창구": "48121", "창원시성산구": "48123", "창원시마산합포구": "48125", "창원시마산회원구": "48127", "창원시진해구": "48129", "김해시": "48250", "거제시": "48310"},
    "제주": {"제주시": "50110", "서귀포시": "50130"},
}

# 지역코드 매핑 (청약홈용)
REGION_CD_MAP = {
    "서울": "11", "부산": "26", "대구": "27", "인천": "28",
    "광주": "29", "대전": "30", "울산": "31", "세종": "36",
    "경기": "41", "강원": "42", "충북": "43", "충남": "44",
    "전북": "45", "전남": "46", "경북": "47", "경남": "48", "제주": "50",
}



# 브랜드 아파트 / 단지명 → 법정동코드 매핑
BRAND_LAWD_MAP = {
    # ─── 래미안 (삼성물산) ───
    "래미안": ("11680", "서울", "강남구"),
    "래미안원베일리": ("11650", "서울", "서초구"),
    "래미안원펜타스": ("11650", "서울", "서초구"),
    "래미안퍼스티지": ("11650", "서울", "서초구"),
    "래미안라클래시": ("11710", "서울", "송파구"),
    "마포래미안": ("11440", "서울", "마포구"),
    "래미안목동": ("11500", "서울", "양천구"),
    "래미안위브": ("11200", "서울", "성동구"),
    "래미안블레스티지": ("11710", "서울", "송파구"),
    # ─── 자이 (GS건설) ───
    "반포자이": ("11650", "서울", "서초구"),
    "영등포자이": ("11560", "서울", "영등포구"),
    "영등포자이디그니티": ("11560", "서울", "영등포구"),
    "철산자이": ("41210", "경기", "광명시"),
    "자이안테나": ("11380", "서울", "은평구"),
    "자이르네": ("11560", "서울", "영등포구"),
    "신반포자이": ("11650", "서울", "서초구"),
    "목동자이": ("11500", "서울", "양천구"),
    "둔촌자이": ("11740", "서울", "강동구"),
    # ─── 힐스테이트 (현대건설) ───
    "힐스테이트": ("11680", "서울", "강남구"),
    "힐스테이트갈현": ("10390", "경기", "고양시 덕양구"),
    "힐스테이트광교": ("41117", "경기", "수원시 영통구"),
    "힐스테이트더운정": ("41480", "경기", "파주시"),
    "힐스테이트삼송": ("10390", "경기", "고양시 덕양구"),
    "힐스테이트범어": ("27200", "대구", "수성구"),
    # ─── 푸르지오 (대우건설) ───
    "푸르지오": ("11590", "서울", "동작구"),
    "푸르지오시티": ("21170", "인천", "연수구"),
    "푸르지오벨라르테": ("11305", "서울", "강북구"),
    "광교푸르지오": ("41117", "경기", "수원시 영통구"),
    # ─── 더샵 (포스코이앤씨) ───
    "더샵": ("11440", "서울", "마포구"),
    "더샵포레스트시티": ("11740", "서울", "강동구"),
    "더샵센트럴파크": ("21140", "인천", "남동구"),
    "더샵갤러리": ("11650", "서울", "서초구"),
    "더샵스타리버": ("11200", "서울", "성동구"),
    # ─── 아크로 / 르엘 (DL이앤씨) ───
    "아크로리버파크": ("11650", "서울", "서초구"),
    "아크로서울포레스트": ("11200", "서울", "성동구"),
    "르엘신반포": ("11650", "서울", "서초구"),
    "이촌르엘": ("11170", "서울", "용산구"),
    "잠실르엘": ("11710", "서울", "송파구"),
    # ─── 롯데캐슬 (롯데건설) ───
    "롯데캐슬": ("11590", "서울", "동작구"),
    "롯데캐슬골드파크": ("41285", "경기", "안양시 만안구"),
    "롯데캐슬클라시아": ("11530", "서울", "구로구"),
    # ─── 아이파크 (HDC현대산업개발) ───
    "아이파크": ("11170", "서울", "용산구"),
    "아이파크삼성": ("11680", "서울", "강남구"),
    "부산아이파크": ("26440", "부산", "해운대구"),
    # ─── e편한세상 (DL이앤씨) ───
    "e편한세상": ("11350", "서울", "노원구"),
    "e편한세상시티": ("41135", "경기", "성남시 분당구"),
    # ─── 대단지 / 랜드마크 ───
    "헬리오시티": ("11710", "서울", "송파구"),
    "올림픽파크포레온": ("11740", "서울", "강동구"),
    "둔촌": ("11740", "서울", "강동구"),
    "파크리오": ("11710", "서울", "송파구"),
    "잠실엘스": ("11710", "서울", "송파구"),
    "은마": ("11680", "서울", "강남구"),
    "은마아파트": ("11680", "서울", "강남구"),
    "이촌": ("11170", "서울", "용산구"),
    "구의현대": ("11215", "서울", "광진구"),
    "디에이치자이개포": ("11680", "서울", "강남구"),
    # ─── 수도권 주요 단지 ───
    "동탄": ("41590", "경기", "화성시"),
    "매교역": ("41113", "경기", "수원시 권선구"),
    "수원": ("41117", "경기", "수원시 영통구"),
    "판교": ("41135", "경기", "성남시 분당구"),
    "위례": ("41135", "경기", "성남시 분당구"),
    "과천": ("41290", "경기", "과천시"),
    "하남미사": ("41450", "경기", "하남시"),
    "김포한강": ("41570", "경기", "김포시"),
    # ─── 지방 주요 ───
    "대연": ("26350", "부산", "남구"),
    "드파인광안": ("26410", "부산", "수영구"),
    "진천풍림": ("43750", "충북", "진천군"),
    "해운대엘시티": ("26440", "부산", "해운대구"),
    "세종": ("36110", "세종", "세종시"),
}

def find_lawd_cd(keyword):
    """키워드에서 법정동코드 추출 — 브랜드명 우선, 지역명 차순"""
    # 1) 브랜드/단지명 매칭 (정확도 높음)
    for brand, (code, city, district) in BRAND_LAWD_MAP.items():
        if brand in keyword:
            return code, city, district
    # 2) 지역명 매칭
    for city, districts in LAWD_MAP.items():
        for district, code in districts.items():
            if district in keyword or city in keyword:
                return code, city, district
    return None, None, None

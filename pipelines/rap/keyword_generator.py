"""RAP 키워드 동적 생성기 — 국토부 실거래 API 기반
매일 새벽 실행하여 최근 거래 많은 지역/단지 키워드 자동 생성
"""
import logging
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from pipelines.rap.fetcher import get_apt_trade_list

logger = logging.getLogger(__name__)

def generate_keywords_from_api():
    """국토부 API 실거래 데이터 기반 키워드 생성"""
    # 최근 1개월 실거래 데이터 수집
    now = datetime.now()
    targets = []

    # 서울 25개 구 + 경기 주요 5개 시
    REGIONS = {
        "11680": "강남구", "11650": "서초구", "11710": "송파구", "11740": "강동구",
        "11590": "동작구", "11620": "관악구", "11500": "중구", "11470": "양천구",
        "11530": "영등포구", "11545": "금천구", "11560": "강서구", "11215": "광진구",
        "11230": "성동구", "11305": "용산구", "11440": "마포구", "11410": "서대문구",
        "11380": "은평구", "11350": "노원구", "11320": "도봉구", "11290": "강북구",
        "11260": "성북구", "11170": "용산구", "11200": "동대문구", "11140": "중랑구",
        "11110": "종로구",
        "41130": "수원", "41210": "성남", "41190": "안양", "41110": "고양", "41281": "용인",
    }

    for month_ago in range(2):  # 최근 2개월
        deal_date = (now - timedelta(days=30*month_ago)).strftime("%Y%m")
        for lawd_cd, region in REGIONS.items():
            targets.append((lawd_cd, region, deal_date))

    # 거래 데이터 수집 및 키워드 생성
    keywords = {}

    for lawd_cd, region, deal_date in targets:
        try:
            trades = get_apt_trade_list(lawd_cd, deal_date)
            if not trades:
                continue

            # 지역별 키워드 (거래 10건 이상)
            if len(trades) >= 10:
                key = f"{region} 실거래가"
                keywords[key] = keywords.get(key, 0) + len(trades)

            # 단지별 키워드 (거래 3건 이상)
            complex_counts = {}
            for t in trades:
                apt_name = t.get("aptNm", "").strip()
                if apt_name:
                    complex_counts[apt_name] = complex_counts.get(apt_name, 0) + 1

            for apt_name, count in complex_counts.items():
                if count >= 3:
                    key = f"{apt_name} {region} 실거래가"
                    keywords[key] = keywords.get(key, 0) + count

            logger.info(f"{region} {deal_date}: {len(trades)}건 수집")

        except Exception as e:
            logger.exception(f"{region} {deal_date} 수집 실패: {e}")
            continue

    # content.db에 저장
    from shared.content_store import get_conn
    conn = get_conn()

    # 키워드 테이블 생성
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rap_keywords (
            keyword TEXT PRIMARY KEY,
            type TEXT DEFAULT 'trade',
            priority INTEGER DEFAULT 0,
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # 기존 키워드 삭제 (30일 이상 된 것만)
    conn.execute("DELETE FROM rap_keywords WHERE updated_at < datetime('now', '-30 days')")

    # 새 키워드 저장
    for keyword, priority in keywords.items():
        conn.execute(
            "INSERT OR REPLACE INTO rap_keywords (keyword, type, priority, updated_at) VALUES (?, 'trade', ?, datetime('now'))",
            (keyword, priority)
        )

    conn.commit()
    conn.close()

    logger.info(f"✅ 키워드 생성 완료: {len(keywords)}개")
    return {"success": True, "count": len(keywords)}

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    from dotenv import load_dotenv
    load_dotenv()
    result = generate_keywords_from_api()
    print(result)

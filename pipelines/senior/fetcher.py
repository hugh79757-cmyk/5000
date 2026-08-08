"""시니어 복지 데이터 수집 — 공공서비스(혜택) API + 노인일자리 API"""

import logging
import os
from datetime import datetime

import requests

logger = logging.getLogger(__name__)

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"))
API_KEY = os.getenv("DATA_GO_KR_API_KEY", "")
SERVICE_LIST_URL = "https://api.odcloud.kr/api/gov24/v3/serviceList"
SERVICE_DETAIL_URL = "https://api.odcloud.kr/api/gov24/v3/serviceDetail"
SENIOR_JOB_URL = "http://apis.data.go.kr/B490007/sjfd100/sjfd100"

SENIOR_KEYWORDS = [
    "노인", "고령", "65세", "어르신", "시니어", "기초연금", "장기요양",
    "경로", "치매", "임플란트", "틀니", "요양원", "요양급여",
    "국민연금", "에너지바우처", "난방비", "주거급여", "경로우대",
    "노인맞춤돌봄", "노인일자리", "배회감지기", "치매안심",
    "개안수술", "인공관절",
]

# 시니어와 무관한 항목을 걸러내는 제외 키워드
EXCLUDE_KEYWORDS = [
    "유아", "영유아", "어린이", "유치원", "누리과정", "임산부", "임신부",
    "발달장애", "청소년", "아동", "어선", "어업", "어선안전", "원양",
    "귀어", "귀산촌", "목조주택", "국산목재", "수목원", "산림복지",
    "국가유공자", "상병수당", "감염병", "한센", "스포츠 강좌 이용권",
    "월세자금보증", "공동생활가정", "해산급여", "HIV", "AIDS",
    "자활근로", "출산크레딧", "장애인 활동지원", "차상위 본인부담",
    "영아", "태아", "신생아", "모자보건", "산후조리",
    "귀농", "귀촌", "청년창업", "청년농업", "후계농",
    "18세 이상 65세 이하", "18세~65세", "만 65세 이하",
    "사회복지시설", "노인복지시설", "복지시설", "급식소",
    "경로당", "농업법인", "영농조합",
]

CATEGORIES = {
    "의료지원": ["임플란트", "틀니", "건강검진", "치매", "의료", "진료", "백신", "건강보험", "수술", "검진", "안검진", "실명"],
    "돌봄서비스": ["돌봄", "장기요양", "방문요양", "주간보호", "재가", "시설급여", "요양급여", "요양원", "방문건강", "방문간호"],
    "연금생활지원": ["기초연금", "에너지", "난방", "주거급여", "생계급여", "보조금", "연금", "수급자"],
    "교통복지": ["교통", "지하철", "버스", "KTX", "경로우대"],
    "일자리금융": ["일자리", "고용", "취업", "대출", "금융", "보험"],
    "문화여가": ["문화", "여가", "바우처", "누리카드", "관광", "박물관", "스포츠", "체육"],
}


def classify_category(text):
    text = str(text).lower()
    for cat, keywords in CATEGORIES.items():
        for kw in keywords:
            if kw in text:
                return cat
    return "생활지원"


def fetch_senior_services(page=1, per_page=100, max_pages=110):
    """공공서비스(혜택) API에서 시니어 관련 서비스 조회"""
    logger.info("공공서비스 혜택 API 조회 시작 (최대 %d페이지)" % max_pages)
    all_services = []

    try:
        for p in range(1, max_pages + 1):
            params = {
                "page": p,
                "perPage": per_page,
                "serviceKey": API_KEY,
            }
            resp = requests.get(SERVICE_LIST_URL, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            items = data.get("data", [])
            if not items:
                break
            all_services.extend(items)
            logger.info(f"  페이지 {p}: {len(items)}건 수집")
    except Exception as e:
        logger.exception(f"공공서비스 API 오류: {e}")
        return []

    # 시니어 관련 필터링
    senior_services = []
    for svc in all_services:
        name = svc.get("서비스명", svc.get("svcNm", ""))
        desc = svc.get("서비스목적요약", svc.get("svcPurpsCn", ""))
        target = svc.get("지원대상", svc.get("trgterIndvdlArray", ""))
        full_text = f"{name} {desc} {target}"

        if any(ex in full_text for ex in EXCLUDE_KEYWORDS):
            continue
        if any(kw in full_text for kw in SENIOR_KEYWORDS):
            senior_services.append({
                "service_name": name,
                "description": str(desc)[:500],
                "target": str(target)[:300],
                "category": classify_category(full_text),
                "apply_method": svc.get("신청방법", svc.get("aplyMtdCn", "")),
                "apply_url": svc.get("온라인신청사이트URL", svc.get("inqPlCtadrList", "")),
                "department": svc.get("소관기관명", svc.get("jurMnofNm", "")),
                "service_id": svc.get("서비스ID", svc.get("svcId", "")),
            })

    logger.info(f"시니어 관련 서비스: {len(senior_services)}건 (전체 {len(all_services)}건 중)")
    return senior_services


def fetch_senior_jobs():
    """한국노인인력개발원 노인 일자리 조회"""
    logger.info("노인 일자리 API 조회")
    try:
        params = {
            "serviceKey": API_KEY,
            "numOfRows": 50,
            "pageNo": 1,
            "type": "json",
        }
        resp = requests.get(SENIOR_JOB_URL, params=params, timeout=15)
        if resp.status_code != 200:
            logger.warning(f"노인일자리 API 응답: {resp.status_code}")
            return []
        data = resp.json()
        items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
        if isinstance(items, dict):
            items = [items]
        logger.info(f"노인 일자리: {len(items)}건")
        return items
    except Exception as e:
        logger.warning(f"노인일자리 API 오류 (무시): {e}")
        return []



import sqlite3

# 시니어(SEAP) 전용 DB path는 shared/db.py 중앙 해석으로 배선 (Phase 61, D-06).
# get_db_path("senior") 은 기존 data/senior.db 와 동일 경로를 반환하므로 동작 불변.
from shared.db import get_db_path

SENIOR_DB_PATH = get_db_path("senior")


def init_senior_db() -> None:
    """senior.db 초기화 — services 테이블 생성"""
    os.makedirs(os.path.dirname(SENIOR_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(SENIOR_DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_id TEXT UNIQUE,
            service_name TEXT NOT NULL,
            description TEXT,
            target TEXT,
            category TEXT,
            apply_method TEXT,
            apply_url TEXT,
            department TEXT,
            support_content TEXT,
            purpose TEXT,
            selection_criteria TEXT,
            documents TEXT,
            contact TEXT,
            law_basis TEXT,
            deadline TEXT,
            status TEXT DEFAULT 'pending',
            collected_at TEXT,
            published_at TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_services_status ON services(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_services_category ON services(category, status)")
    conn.commit()
    conn.close()
    logger.info(f"senior.db 초기화 완료: {SENIOR_DB_PATH}")


def sync_services():
    """API에서 서비스 수집 후 senior.db에 저장 (신규만 INSERT, 기존 무시)"""
    init_senior_db()
    raw = fetch_senior_services(page=1, per_page=100, max_pages=10)
    if not raw:
        logger.error("sync_services: API 수집 실패")
        return 0

    # 만료 필터 (fetch_all 로직 재사용)
    import re as _re
    now_str = datetime.now().strftime("%Y-%m-%d")
    now_year = datetime.now().year
    filtered = []
    for s in raw:
        dl = str(s.get("deadline", "")).strip()
        skip = False
        for y in range(2018, now_year):
            if str(y) in dl:
                skip = True
                break
        if any(x in dl for x in ["마감", "신규신청 불가", "접수 마감"]):
            skip = True
        m = _re.search(r"(\d{4})[.\-](\d{2})[.\-](\d{2})\s*$", dl)
        if m and f"{m.group(1)}-{m.group(2)}-{m.group(3)}" < now_str:
            skip = True
        if not skip:
            m2 = _re.search(r"[~∼]\s*(\d{4})[.\-](\d{1,2})[.\-](\d{1,2})", dl)
            if m2:
                if f"{m2.group(1)}-{int(m2.group(2)):02d}-{int(m2.group(3)):02d}" < now_str:
                    skip = True
        if not skip:
            filtered.append(s)

    conn = sqlite3.connect(SENIOR_DB_PATH)
    inserted = 0
    for s in filtered:
        try:
            conn.execute("""
                INSERT OR IGNORE INTO services
                (service_id, service_name, description, target, category,
                 apply_method, apply_url, department, deadline, status, collected_at)
                VALUES (?,?,?,?,?,?,?,?,?,'pending',?)
            """, (
                s.get("service_id", ""),
                s.get("service_name", ""),
                s.get("description", ""),
                s.get("target", ""),
                s.get("category", "생활지원"),
                s.get("apply_method", ""),
                s.get("apply_url", ""),
                s.get("department", ""),
                s.get("deadline", ""),
                datetime.now().isoformat(),
            ))
            if conn.execute("SELECT changes()").fetchone()[0] > 0:
                inserted += 1
        except Exception as e:
            logger.warning(f"services INSERT 실패: {e}")
    conn.commit()
    conn.close()
    logger.info(f"sync_services 완료: {len(filtered)}건 처리, {inserted}건 신규 저장")
    return inserted


def get_pending_service(category=None, blog_id=None):
    """senior.db에서 pending 서비스 1건 반환 (category 우선, 없음면 전체).
    blog_id가 주어지면 content.db articles에 이미 발행된 source_id를 제외한다."""
    init_senior_db()
    conn = sqlite3.connect(SENIOR_DB_PATH)
    try:
        # content.db에서 이미 발행된 source_id 목록 조회 (중복 방지)
        published_source_ids = set()
        if blog_id:
            try:
                from shared.content_store import get_conn as _get_content_conn
                cconn = _get_content_conn()
                pub_rows = cconn.execute(
                    "SELECT DISTINCT source_id FROM articles "
                    "WHERE blog_id=? AND status='published' AND data_source='gov24_api'",
                    (blog_id,)
                ).fetchall()
                published_source_ids = {r[0] for r in pub_rows if r[0]}
                cconn.close()
            except Exception as _e:
                logger.warning(f"발행 source_id 조회 실패 (무시): {_e}")

        if category:
            if published_source_ids:
                placeholders = ','.join(['?' for _ in published_source_ids])
                row = conn.execute(
                    f"SELECT * FROM services WHERE status='pending' AND category=? "
                    f"AND service_id NOT IN ({placeholders}) ORDER BY id ASC LIMIT 1",
                    [category] + list(published_source_ids)
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM services WHERE status='pending' AND category=? ORDER BY id ASC LIMIT 1",
                    (category,)
                ).fetchone()
        else:
            if published_source_ids:
                placeholders = ','.join(['?' for _ in published_source_ids])
                row = conn.execute(
                    f"SELECT * FROM services WHERE status='pending' "
                    f"AND service_id NOT IN ({placeholders}) ORDER BY id ASC LIMIT 1",
                    list(published_source_ids)
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM services WHERE status='pending' ORDER BY id ASC LIMIT 1"
                ).fetchone()
        if not row:
            return None
        cols = [d[0] for d in conn.execute("SELECT * FROM services LIMIT 0").description]
        # description 재조회
        cols = ["id","service_id","service_name","description","target","category",
                "apply_method","apply_url","department","support_content","purpose",
                "selection_criteria","documents","contact","law_basis","deadline",
                "status","collected_at","published_at"]
        return dict(zip(cols, row, strict=False))
    finally:
        conn.close()


def mark_published(service_id) -> None:
    """서비스 발행 완료 처리"""
    conn = sqlite3.connect(SENIOR_DB_PATH)
    conn.execute(
        "UPDATE services SET status='published', published_at=? WHERE service_id=?",
        (datetime.now().isoformat(), service_id)
    )
    conn.commit()
    conn.close()


def get_pending_count():
    """Pending 서비스 수 반환"""
    try:
        conn = sqlite3.connect(SENIOR_DB_PATH)
        count = conn.execute("SELECT COUNT(*) FROM services WHERE status='pending'").fetchone()[0]
        conn.close()
        return count
    except Exception:
        return 0

CACHE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "senior_services.json")


def _load_cache():
    """오늘 날짜 캐시가 있으면 로드"""
    import json
    if not os.path.exists(CACHE_PATH):
        return None
    try:
        with open(CACHE_PATH, encoding="utf-8") as f:
            data = json.load(f)
        updated = data.get("updated_at", "")[:10]
        today = datetime.now().strftime("%Y-%m-%d")
        if updated == today:
            logger.info("캐시 로드: %s (%d건)" % (CACHE_PATH, data.get("total", 0)))
            return data.get("services", [])
        logger.info(f"캐시 만료: {updated} (갱신 필요)")
        return None
    except Exception as e:
        logger.warning(f"캐시 로드 실패: {e}")
        return None


def _save_cache(services) -> None:
    """캐시 저장"""
    import json
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    data = {
        "updated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "total": len(services),
        "services": services,
    }
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    logger.info("캐시 저장: %d건 -> %s" % (len(services), CACHE_PATH))




def enrich_service_detail(service):
    """gov24 상세 API로 서비스 데이터 보강"""
    svc_id = service.get("service_id", "")
    if not svc_id:
        return service
    try:
        params = {
            "serviceKey": API_KEY,
            "cond[서비스ID::EQ]": svc_id,
            "perPage": 1,
        }
        resp = requests.get(SERVICE_DETAIL_URL, params=params, timeout=10)
        if resp.status_code != 200:
            return service
        items = resp.json().get("data", [])
        if not items:
            return service
        detail = items[0]
        if detail.get("서비스목적"):
            service["purpose"] = str(detail["서비스목적"])[:500]
        if detail.get("지원내용"):
            service["support_content"] = str(detail["지원내용"])[:500]
        if detail.get("선정기준") and str(detail["선정기준"]).strip():
            service["selection_criteria"] = str(detail["선정기준"])[:300]
        if detail.get("구비서류") and detail["구비서류"] != "해당없음":
            service["documents"] = str(detail["구비서류"])[:300]
        if detail.get("문의처"):
            service["contact"] = str(detail["문의처"])[:200]
        if detail.get("법령"):
            service["law_basis"] = str(detail["법령"])[:200]
        if detail.get("신청기한"):
            service["deadline"] = str(detail["신청기한"])[:100]
        if detail.get("온라인신청사이트URL"):
            service["apply_url"] = str(detail["온라인신청사이트URL"])[:300]
        if detail.get("신청방법"):
            service["apply_method"] = str(detail["신청방법"])[:200]
        logger.debug(f"상세 보강 완료: {service.get('service_name')}")
    except Exception as e:
        logger.debug(f"상세 API 실패 ({svc_id}): {e}")
    return service


def enrich_naver_blog(service):
    """네이버 블로그 검색으로 실제 후기/팁 보강"""
    naver_id = os.getenv("NAVER_CLIENT_ID", "")
    naver_secret = os.getenv("NAVER_CLIENT_SECRET", "")
    if not naver_id or not naver_secret:
        return service
    name = service.get("service_name", "")
    if not name:
        return service
    try:
        headers = {
            "X-Naver-Client-Id": naver_id,
            "X-Naver-Client-Secret": naver_secret,
        }
        queries = [f"{name} 신청방법", f"{name} 후기"]
        snippets = []
        for q in queries:
            resp = requests.get(
                "https://openapi.naver.com/v1/search/blog.json",
                params={"query": q, "display": 3, "sort": "sim"},
                headers=headers, timeout=8,
            )
            if resp.status_code == 200:
                for item in resp.json().get("items", []):
                    desc = item.get("description", "").replace("<b>", "").replace("</b>", "")
                    if desc and len(desc) > 30:
                        snippets.append(desc[:200])
        if snippets:
            service["blog_snippets"] = snippets[:4]
            logger.debug(f"네이버 보강: {name} -> {len(snippets)}개 스니펫")
    except Exception as e:
        logger.debug(f"네이버 검색 실패 ({name}): {e}")
    return service


def fetch_all(max_pages=10):
    """모든 시니어 데이터 수집 — 캐시 우선, 없으면 API 호출"""
    cached = _load_cache()
    if cached:
        services = cached
    else:
        raw_services = fetch_senior_services(page=1, per_page=100, max_pages=110)
        seen = set()
        services = []
        for s in raw_services:
            name = s.get("service_name", "")
            if name not in seen:
                seen.add(name)
                services.append(s)
        _save_cache(services)
    # 만료 서비스 필터링
    import re as _re
    now_str = datetime.now().strftime("%Y-%m-%d")
    now_year = datetime.now().year
    filtered = []
    for s in services:
        dl = str(s.get("deadline", "")).strip()
        # 명확히 과거 연도가 포함된 경우 제외
        skip = False
        for y in range(2018, now_year):
            if str(y) in dl:
                skip = True
                break
        # "마감", "신규신청 불가", "금년 접수 마감" 제외
        if any(x in dl for x in ["마감", "신규신청 불가", "접수 마감"]):
            skip = True
        # [PATCH] 다양한 날짜 형식의 종료일 추출
        # 패턴1: YYYY.MM.DD 또는 YYYY-MM-DD (끝부분)
        m = _re.search(r"(\d{4})[.\-](\d{2})[.\-](\d{2})\s*$", dl)
        if m:
            end_date = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
            if end_date < now_str:
                skip = True
        # 패턴2: ~YYYY.MM.DD 또는 ~YYYY-MM-DD (물결 뒤 종료일)
        if not skip:
            m2 = _re.search(r"[~∼]\s*(\d{4})[.\-](\d{1,2})[.\-](\d{1,2})", dl)
            if m2:
                end_date2 = f"{m2.group(1)}-{int(m2.group(2)):02d}-{int(m2.group(3)):02d}"
                if end_date2 < now_str:
                    skip = True
        # 패턴3: "YYYY년 MM월 DD일" 한글 형식
        if not skip:
            m3 = _re.findall(r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일", dl)
            if m3:
                last = m3[-1]  # 마지막 날짜가 종료일
                end_date3 = f"{last[0]}-{int(last[1]):02d}-{int(last[2]):02d}"
                if end_date3 < now_str:
                    skip = True
        # 패턴4: "MM.DD~MM.DD" (올해로 간주)
        if not skip:
            m4 = _re.search(r"(\d{1,2})[.](\d{1,2})\s*[~∼]\s*(\d{1,2})[.](\d{1,2})", dl)
            if m4 and not _re.search(r"\d{4}", dl):
                end_date4 = f"{now_year}-{int(m4.group(3)):02d}-{int(m4.group(4)):02d}"
                if end_date4 < now_str:
                    skip = True
        # 패턴5: deadline이 비어있지만 service 데이터에 접수 마감 날짜가 있는 경우
        if not skip and not dl:
            apply_end = str(s.get("apply_end_date", s.get("rceptEndDe", ""))).strip()
            if apply_end:
                m5 = _re.search(r"(\d{4})[.\-](\d{1,2})[.\-](\d{1,2})", apply_end)
                if m5:
                    end5 = f"{m5.group(1)}-{int(m5.group(2)):02d}-{int(m5.group(3)):02d}"
                    if end5 < now_str:
                        skip = True
        if not skip:
            filtered.append(s)
    logger.info(f"만료 필터: {len(services)}건 -> {len(filtered)}건 ({len(services)-len(filtered)}건 제외)")
    services = filtered

    jobs = fetch_senior_jobs()
    today = datetime.now().strftime("%Y년 %m월 %d일")

    return {
        "services": services,
        "jobs": jobs,
        "today": today,
        "total_services": len(services),
        "total_jobs": len(jobs),
        "categories": list(CATEGORIES.keys()),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = fetch_all()
    print(f"\n수집 결과: 서비스 {result['total_services']}건, 일자리 {result['total_jobs']}건")
    for svc in result["services"][:5]:
        print(f"  [{svc['category']}] {svc['service_name']}")

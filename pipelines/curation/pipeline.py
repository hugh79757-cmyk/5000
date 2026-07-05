"""curation 파이프라인 — 상품 큐레이션 글 자동 발행

흐름: 키워드 선택 → 상품 수집(캐시) → AI 글 생성 → Hugo 발행
"""
import logging
import os
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv

load_dotenv(os.path.expanduser("~/.env.common"))
load_dotenv("/Users/twinssn/Projects/5000/.env")

import requests as _requests

from pipelines.curation.collector import collect_keyword, get_products
from pipelines.curation.enricher import enrich_products
from pipelines.curation.keywords import get_keywords
from pipelines.curation.keyword_health import KeywordHealthStore
from pipelines.curation.writer import generate_curation_article
from shared.content_store import get_today_count
from shared.image_handler import process_and_upload
from shared.publisher import publish
from shared.telegram_notifier import send_error as _tg_error
from shared.validators import assert_korean_or_reject, sanitize_title
from shared.relevance_scorer import migrate_publish_log, score_products, passes_gate
from shared.alert_thresholds import ThresholdChecker

logger = logging.getLogger(__name__)

# -- 동시실행 방지 락 --
import fcntl


def _acquire_lock(blog_id):
    """블로그별 파일 락 - 동시 실행 방지"""
    lock_dir = PROJECT_DIR / "data"
    lock_dir.mkdir(exist_ok=True)
    lock_path = lock_dir / f".lock_{blog_id}"
    lock_file = open(lock_path, "w")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return lock_file
    except BlockingIOError:
        lock_file.close()
        return None

def _release_lock(lock_file) -> None:
    if lock_file:
        try:
            fcntl.flock(lock_file, fcntl.LOCK_UN)
            lock_file.close()
        except Exception:
            pass

PROJECT_DIR = Path(__file__).parent.parent.parent
DB_PATH = PROJECT_DIR / "data" / "curation.db"

def _init_db() -> None:
    """DB 테이블이 없으면 자동 생성 (DB 초기화 복구용)"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS publish_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            blog_id TEXT NOT NULL,
            keyword TEXT NOT NULL,
            title TEXT,
            slug TEXT,
            published_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_publog_blog_keyword
        ON publish_log(blog_id, keyword, published_at)
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS published_products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            blog_id TEXT NOT NULL,
            product_id INTEGER NOT NULL,
            keyword TEXT NOT NULL,
            published_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_pub_products_blog
        ON published_products(blog_id, product_id)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_pub_products_date
        ON published_products(blog_id, published_at)
    """)
    conn.commit()
    conn.close()

_init_db()
migrate_publish_log(str(DB_PATH))

# ── Keyword health store ──
health_store = KeywordHealthStore(str(DB_PATH))
health_store.ensure_table()

# ── Threshold-based alert checker ──
_alert_checker = ThresholdChecker()
_consecutive_failures: dict[str, int] = {}



def _extract_category(keyword):
    """키워드 첫 토큰을 카테고리로 사용 (동적 추출, keywords.py 수정 불필요)"""
    tokens = keyword.split()
    return tokens[0] if tokens else keyword


def _select_keyword(blog_id):
    """키워드 선택 - 30일 TTL + 카테고리 14일 중복 억제

    모든 키워드가 소진되면 None 반환 (강제 fallback 금지).
    dispatcher가 no_keyword 사유로 텔레그램 알림 전송 → 사용자 수동 재시작.
    """
    keywords = get_keywords(blog_id)
    if not keywords:
        return None

    import sqlite3 as _sq
    conn = _sq.connect(str(DB_PATH))

    used_rows = conn.execute(
        "SELECT keyword FROM publish_log"
        " WHERE blog_id=? AND published_at > datetime('now', '-30 days')",
        (blog_id,)
    ).fetchall()

    recent_rows = conn.execute(
        "SELECT keyword FROM publish_log"
        " WHERE blog_id=? AND published_at > datetime('now', '-14 days')",
        (blog_id,)
    ).fetchall()

    used_set = {r[0] for r in used_rows}
    recent_cats = {_extract_category(r[0]) for r in recent_rows}

    available = [k for k in keywords if k not in used_set]
    # 격리된 키워드 제외
    available = [k for k in available if not health_store.is_quarantined(blog_id, k)]
    if not available:
        conn.close()
        if len(keywords) > 0:
            logger.warning(f"[{blog_id}] 모든 키워드 30일 내 사용 완료 또는 격리 중 — 발행 중단")
        else:
            logger.warning(f"[{blog_id}] 모든 키워드 30일 내 사용 완료 — 발행 중단")
        return None  # 강제 fallback 금지, 사용자 알림 대기

    cat_filtered = [k for k in available if _extract_category(k) not in recent_cats]
    candidates = cat_filtered or available

    conn = _sq.connect(str(DB_PATH))
    # candidates → available → 전체 순으로 상품 3개 이상인 키워드 탐색
    for pool in [candidates, available]:
        for kw in pool:
            cnt = conn.execute(
                "SELECT COUNT(*) FROM products WHERE keyword=?", (kw,)
            ).fetchone()[0]
            if cnt >= 3:
                # Relevance gate: 샘플 제품 3개의 평균 relevance가 threshold 미만이면 스킵
                from shared.relevance_scorer import score_products, passes_gate
                sample = get_products(kw, limit=3)
                if sample:
                    scores = score_products(sample, blog_id)
                    if not passes_gate(scores)[0]:
                        logger.debug(f"[{blog_id}] relevance gate 통과 실패: {kw} (avg={scores['avg']:.2f} < threshold={scores['threshold']:.2f})")
                        continue
                conn.close()
                return kw
    conn.close()
    # 상품 있는 키워드가 하나도 없음
    logger.warning(f"[{blog_id}] 모든 키워드 상품 부족 — 발행 중단")
    return None


def _upload_thumbnail(image_url):
    """쿠팡 상품 이미지를 R2에 업로드하여 썸네일로 사용"""
    try:
        resp = _requests.get(image_url, timeout=10)
        if resp.status_code == 200 and len(resp.content) > 1000:
            return process_and_upload(resp.content, key_prefix="curation-images")
    except Exception as e:
        logger.warning(f"썸네일 업로드 실패: {e}")
    return ""



# ── 카테고리별 허용/차단 키워드 (상품 필터) ──
CATEGORY_FILTERS = {
    "laptop-hugo": {
        "allowed": ["노트북", "laptop", "랩탑", "맥북", "macbook", "그램", "gram",
                     "갤럭시북", "thinkpad", "씽크패드", "victus", "오멘", "vivobook",
                     "비보북", "zenbook", "젠북", "ideapad", "아이디어패드",
                     "크롬북", "chromebook", "울트라북", "서피스",
                     "컴퓨터", "전자기기"],
        "blocked": ["도서", "교재", "필기", "실기", "기능사", "자격증",
                     "스티커", "마우스패드", "장패드", "키보드", "마우스",
                     "가방", "파우치", "거치대", "받침대", "쿨링패드",
                     "모니터", "데스크탑", "태블릿", "아이패드", "갤럭시탭",
                     "헤드셋", "이어폰", "이어버드", "스피커",
                     "웹캠", "캡쳐보드", "캡처보드",
                     "책상", "의자", "케이블", "HDMI", "USB허브",
                     "dock", "어댑터", "충전기", "보호필름", "스킨",
                     "서류가방", "노트북가방", "CrowPi", "크롤파이",
                     "중고", "트레이딩",
                     "생활용품", "가구", "홈인테리어", "주방용품", "문구/오피스",
                     "식품", "출산/유아", "반려동물"],
    },
    "appliance-hugo": {
        "allowed": ["청소기", "에어프라이어", "공기청정기", "제습기", "가습기",
                     "냉장고", "세탁기", "건조기", "식기세척기", "전자레인지",
                     "오븐", "밥솥", "정수기", "선풍기", "히터", "난방기",
                     "로봇청소기", "스팀청소기", "물걸레", "다리미",
                     "가전", "디지털"],
        "blocked": ["도서", "교재", "스티커", "인형", "장난감",
                     "의류", "패션", "화장품",
                     "생활용품", "출산/유아", "반려동물", "식품", "완구"],
    },
    "interior-hugo": {
        "allowed": ["의자", "책상", "소파", "매트리스", "침대", "선반", "수납",
                     "커튼", "블라인드", "조명", "램프", "러그", "카페트",
                     "테이블", "화장대", "옷장", "행거", "거울",
                     "가구", "인테리어"],
        "blocked": ["도서", "교재", "식품", "화장품", "의류", "패션",
                     "장난감", "완구",
                     "생활용품", "전자기기", "가전", "출산/유아", "반려동물",
                     "주방용품", "스포츠"],
    },
    "baby-hugo": {
        "allowed": ["카시트", "유모차", "아기띠", "바운서", "젖병", "분유",
                     "기저귀", "보행기", "범퍼침대", "아기침대", "수유",
                     "이유식", "체온계", "멸균기", "신생아", "유아",
                     "아기", "베이비", "유아용", "영아",
                     "육아", "출산"],
        "blocked": ["강아지", "반려견", "반려동물", "개모차", "pet", "여성의류", "남성의류", "패션의류", "여성패션", "남성패션",
                     "고양이", "강아지용", "도그", "dog",
                     "도서", "교재", "성인용",
                     "장난감", "완구", "블록", "보드게임", "퍼즐",
                     "유모차 가방", "유모차 후크", "유모차 고리", "유모차 걸이",
                     "유모차 정리함", "유모차 양산", "유모차 액세서리",
                     "핸들장난감", "드라이빙", "모빌",
                      "생활용품", "가전", "가구", "홈인테리어"],
    },
    "fitness-hugo": {
        "allowed": ["덤벨", "아령", "바벨", "케틀벨", "런닝머신", "러닝머신",
                     "트레드밀", "워킹머신", "실내자전거", "스핀바이크",
                     "풀업바", "철봉", "푸쉬업바", "요가매트", "폼롤러",
                     "헬스", "운동", "피트니스", "스텝퍼", "로잉머신",
                     "근력", "스트레칭", "밴드", "트램폴린", "훌라후프", "줄넘기",
                     "레깅스", "타이즈", "운동복", "스포츠브라", "요가복", "트레이닝",
                     "런닝화", "운동화", "워킹화", "트레일러닝",
                     "스마트워치", "스마트밴드", "가민", "핏빗",
                     "단백질", "프로틴", "크레아틴", "BCAA", "보충제", "쉐이커",
                     "보호대", "헬스장갑", "헬스벨트",
                     "마사지건", "짐볼", "필라테스", "ab롤러", "복근",
                     "홈짐", "홈트", "파워랙", "스쿼트랙", "스미스머신", "딥스바",
                      "스포츠", "레저", "다이어트", "논슬립", "괄약근"],
        "blocked": ["도서", "교재", "인형", "장난감", "화장품",
                     "생활용품", "출산/유아", "반려동물", "가전",
                     "패션의류", "여성의류", "남성의류"],
    },
    "health-hugo": {
        "allowed": ["건강", "영양", "비타민", "유산균", "루테인", "오메가", "콜라겐",
                     "홍삼", "프로폴리스", "마그네슘", "아연", "철분", "칼슘",
                     "단백질", "보충제", "크레아틴", "글루타치온", "비오틴",
                     "코엔자임", "밀크씨슬", "프로바이오틱스", "엽산",
                     "면역", "혈행", "혈압", "혈당", "장건강", "간건강",
                     "관절", "뼈", "갱년기", "전립선", "피로",
                     "건강식품", "영양제"],
        "blocked": ["생활용품", "주방", "반려동물", "패션", "전자기기", "장난감", "완구",
                     "가전", "출산/유아"],
        "required": [],
    },
    "pet-hugo": {
        "allowed": ["강아지", "고양이", "반려동물", "개", "dog", "cat", "pet",
                     "사료", "간식", "캣타워", "스크래쳐", "하네스", "리드줄",
                     "배변", "화장실", "모래", "이동장", "켄넬", "방석",
                     "급식기", "정수기", "드라이룸", "샴푸", "치약",
                     "유모차", "노즈워크", "그루밍", "영양제"],
        "blocked": ["의류", "전자기기", "가전", "주방", "완구",
                     "생활용품", "출산/유아", "가구", "홈인테리어", "스포츠/레저", "패션"],
        "required": [],
    },
    "kitchen-hugo": {
        "allowed": ["냄비", "프라이팬", "주방", "식기", "칼", "도마", "용기",
                     "텀블러", "도시락", "밀폐", "보관", "조리도구",
                     "가위", "저울", "타이머", "주걱", "냄비받침",
                     "에어프라이어", "전기냄비", "밥솥", "믹서기", "전기포트",
                     "커피머신", "식기세척기", "찜기", "와플", "토스터",
                     "블렌더", "착즙기", "그릴", "인덕션", "세제",
                     "주방용품", "조리"],
        "blocked": ["패션", "의류", "반려동물", "완구", "장난감", "건강식품", "영양제",
                     "생활용품", "가전디지털", "출산/유아", "스포츠/레저", "식품"],
        "required": [],
    },
    "beauty-hugo": {
        "allowed": ["크림", "에센스", "토너", "세럼", "앰플", "클렌저", "클렌징",
                     "마스크팩", "선크림", "자외선차단", "쿠션", "파운데이션",
                     "립스틱", "립밤", "아이크림", "마스카라", "아이라이너",
                     "블러셔", "하이라이터", "파우더", "컨실러", "향수",
                     "헤어", "샴푸", "린스", "트리트먼트", "바디로션",
                     "바디워시", "핸드크림", "미스트", "여드름", "각질",
                     "고데기", "드라이어",
                     "뷰티", "화장품", "스킨케어"],
        "blocked": ["식품", "전자기기", "가전", "완구", "반려동물", "주방", "캠핑", "생활용품", "위생용품", "음료",
                     "출산/유아", "스포츠/레저", "문구/오피스", "가구"],
        "required": [],
    },
    "camping-hugo": {
        "allowed": ["텐트", "타프", "침낭", "캠핑", "랜턴", "버너", "코펠",
                     "매트", "쿨러", "아이스박스", "화로대", "그릴", "식기",
                     "헤드랜턴", "해먹", "모기장", "선풍기", "난로", "조명",
                     "카트", "가스통", "방수포", "멀티툴", "배낭", "등산화",
                     "트레킹폴", "폴대", "페그", "우비", "모자",
                     "백패킹", "스노우피크", "정리함",
                     "아웃도어", "레저"],
        "blocked": ["식품", "건강식품", "완구", "장난감", "주방가전", "뷰티", "화장품",
                     "생활용품", "출산/유아", "가전", "패션", "의류", "문구/오피스"],
        "required": [],
    },
}

# 제목 검증용 blocked 키워드 (AI 생성 제목에 이게 포함되면 발행 차단)
TITLE_BLOCKED = {
    "laptop-hugo": ["마우스", "키보드", "헤드셋", "웹캠", "캡쳐보드", "캡처보드",
                    "태블릿", "아이패드", "갤럭시탭", "서류가방", "장패드",
                    "CrowPi", "크롤파이", "이어폰", "스피커"],
    "baby-hugo":   ["강아지", "반려견", "반려동물", "개모차", "고양이"],
    "camping-hugo": ["침실"],
    "appliance-hugo": [],
    "interior-hugo": [],
    "fitness-hugo": [],
}

# 제목 문맥 확인용 allowed 키워드 (blocked 키워드가 있어도 allowed 키워드가 제목에 있으면 차단 스킵)
ALLOWED_PRODUCT = {
    "camping-hugo": {"allowed": ["텐트", "캠핑", "침낭", "랜턴", "야영", "등산"]},
}


def _filter_irrelevant_products(blog_id, keyword, products):
    """카테고리와 무관한 상품 제거 (코드 레벨 필터)"""
    filters = CATEGORY_FILTERS.get(blog_id)
    if not filters:
        return products

    allowed = filters["allowed"]
    blocked = filters["blocked"]
    keyword.lower()

    filtered = []
    for p in products:
        name = p.get("product_name", "").lower()
        cat = p.get("category_name", "").lower()
        combined = name + " " + cat

        # 상품명이 allowed 키워드를 포함하면 카테고리 blocked 무시 (context-aware)
        name_has_allowed = any(aw in name for aw in allowed)

        # 차단 키워드 — category_name + product_name 모두 확인
        is_blocked = False
        for bw in blocked:
            bw_lower = bw.lower()
            if (bw_lower in cat and not name_has_allowed) or (bw_lower in name and not name_has_allowed):
                logger.info(f"[필터] 차단: '{p.get('product_name', '')[:40]}' (차단어: {bw}, 대상: {'카테고리' if bw_lower in cat else '상품명'})")
                is_blocked = True
                break
        if is_blocked:
            continue

        # 허용 키워드 중 하나라도 포함되어야 통과 (product_name + category_name)
        has_allowed = False
        for aw in allowed:
            if aw in combined:
                has_allowed = True
                break
        if not has_allowed:
            logger.info(f"[필터] 미허용: '{p.get('product_name', '')[:40]}' (허용어 미포함)")
            continue

        filtered.append(p)

    if len(filtered) < 3:
        if len(filtered) >= 1:
            logger.warning(f"[{blog_id}] 필터 후 상품 부족 ({len(filtered)}개), 부족하지만 발행 진행")
            return filtered
        logger.warning(f"[{blog_id}] 필터 후 상품 0개 — 발행 중단")
        return []

    return filtered


def _filter_used_products(blog_id, products):
    """발행된 적 있는 상품 제외 — 시간+횟수 복합 기준

    기준:
    - 30일 이내 사용된 상품 ID 차단 (시간 기반)
    - 최근 15회 발행에 등장한 상품 ID 추가 차단 (횟수 기반)
    → 두 조건 중 하나라도 해당되면 차단
    → 필터 후 3개 미만이면 원본에서 가장 오래된 상품 보충 (차단 없이 발행 허용)
    """
    if not products:
        return products
    conn = sqlite3.connect(str(DB_PATH))

    # ① 30일 이내 사용 상품
    time_used = conn.execute(
        "SELECT product_id FROM published_products WHERE blog_id=? AND published_at > datetime('now', '-30 days')",
        (blog_id,)
    ).fetchall()
    time_used_ids = {str(r[0]) for r in time_used}

    # ② 최근 15회 발행에 등장한 상품 (횟수 기반)
    recent_pubs = conn.execute(
        """SELECT pp.product_id FROM published_products pp
           INNER JOIN (
               SELECT published_at FROM published_products
               WHERE blog_id=?
               ORDER BY published_at DESC LIMIT 15
           ) recent ON pp.published_at = recent.published_at
           WHERE pp.blog_id=?""",
        (blog_id, blog_id)
    ).fetchall()
    recent_ids = {str(r[0]) for r in recent_pubs}
    conn.close()

    used_ids = time_used_ids | recent_ids

    filtered = [p for p in products if str(p["product_id"]) not in used_ids]
    if len(filtered) < 3:
        # 필터 후 부족하면: 원본에서 used_ids 제외 후 오래된 순으로 보충
        logger.warning(f"[{blog_id}] 미사용 상품 부족 ({len(filtered)}개), 원본에서 보충")
        fallback = [p for p in products if str(p["product_id"]) not in recent_ids]
        if len(fallback) >= 3:
            return fallback[:5]
        # 최후 수단: 원본 그대로 (중복 허용)
        logger.warning(f"[{blog_id}] 상품 보충 실패 — 원본 유지 (중복 가능)")
        return products[:5]
    return filtered[:5]


def _record_products(blog_id, keyword, products) -> None:
    """발행에 사용된 상품 ID 기록"""
    conn = sqlite3.connect(str(DB_PATH))
    now = datetime.utcnow().isoformat()
    for p in products:
        conn.execute(
            "INSERT OR IGNORE INTO published_products (blog_id, product_id, keyword, published_at) VALUES (?,?,?,?)",
            (blog_id, p["product_id"], keyword, now)
        )
    conn.commit()
    conn.close()



def _title_is_duplicate(blog_id, title):
    """publish_log에서 유사 제목 체크 (3일 이내, 다중 기준)"""
    import re as _re
    conn = sqlite3.connect(str(DB_PATH))

    # 방법1: 핵심 20자 LIKE 비교
    normalized = _re.sub(
        r"[0-9]곳|[0-9]선|총정리|정리|한눈에 보기|추천 리스트|추천|비교|체크리스트|및|과|와|vs|VS|TOP[0-9]+|[0-9]{4}년?",
        "", title
    ).strip()
    normalized = _re.sub(r"\s+", " ", normalized).strip()
    core = normalized[:20] if len(normalized) >= 20 else normalized[:12]

    found = False
    if core and len(core) >= 5:
        row = conn.execute(
            """SELECT title FROM publish_log
               WHERE blog_id=? AND title LIKE ? AND published_at > datetime('now', '-3 days')""",
            (blog_id, "%" + core + "%"),
        ).fetchone()
        if row:
            logger.info(f"[중복체크] 핵심어 일치: core='{core}' -> '{row[0][:40]}'")
            found = True

    # 방법2: 주요 단어 3개 이상 겹치면 중복
    if not found:
        title_words = set(_re.findall(r"[가-힣a-zA-Z0-9]{2,}", title))
        stop_words = {"추천", "비교", "가성비", "인기", "순위", "정리", "선택", "소개", "vs", "년", "월", "위"}
        title_words -= stop_words
        if len(title_words) >= 3:
            recent = conn.execute(
                """SELECT title FROM publish_log
                   WHERE blog_id=? AND published_at > datetime('now', '-3 days')""",
                (blog_id,),
            ).fetchall()
            for (prev_title,) in recent:
                prev_words = set(_re.findall(r"[가-힣a-zA-Z0-9]{2,}", prev_title))
                prev_words -= stop_words
                overlap = title_words & prev_words
                if len(overlap) >= 3:
                    logger.info(f"[중복체크] 단어 겹침: {overlap} -> '{prev_title[:40]}'")
                    found = True
                    break

    conn.close()
    return found


def _make_slug(keyword) -> str:
    slug = keyword.replace(" ", "-").lower()
    slug = re.sub(r"[^a-z0-9가-힣\-]", "", slug)
    date_prefix = datetime.now().strftime("%Y%m%d")
    return f"{date_prefix}-{slug}"


def _record_publish(blog_id, keyword, title, slug) -> None:
    """publish_log에 발행 기록"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        "INSERT INTO publish_log (blog_id, keyword, title, slug, published_at) VALUES (?,?,?,?,?)",
        (blog_id, keyword, title, slug, datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()


LEDGER_DB = PROJECT_DIR / "data" / "content.db"

def _record_failure(blog_id: str, stage: str, error_msg: str, keyword: str = "") -> None:
    """publish_ledger에 발행 실패 기록 (예외를 삼켜 파이프라인 중단 방지)"""
    try:
        con = sqlite3.connect(str(LEDGER_DB))
        con.execute(
            """INSERT INTO publish_ledger
               (blog_id, title, status, stage, error_msg, created_at)
               VALUES (?, ?, 'failed', ?, ?, ?)""",
            (blog_id, keyword or stage, stage, error_msg, datetime.now().isoformat())
        )
        con.commit()
        con.close()
    except Exception as e:
        logger.warning(f"[ledger] 실패 기록 오류: {e}")

    # 키워드 건강 기록 (curation.db)
    if keyword:
        try:
            health_store.record_failure(blog_id, keyword, stage)
        except Exception as e:
            logger.warning(f"[keyword_health] 기록 오류: {e}")


def run(cfg):
    """Curation 파이프라인 메인 — dispatcher에서 호출"""
    blog_id = cfg.get("id", "")
    daily_quota = cfg.get("daily_quota", 5)

    # 동시실행 방지
    lock_file = _acquire_lock(blog_id)
    if lock_file is None:
        logger.warning(f"[{blog_id}] 이미 실행 중 (락 획득 실패)")
        return {"success": False, "reason": "already_running"}

    try:
        result = _run_inner(cfg, blog_id, daily_quota)

        # 연속 실패 추적 + 임계값 알림
        if result.get("success"):
            _consecutive_failures[blog_id] = 0
        else:
            reason = result.get("reason", "unknown")
            # 조용한 실패(할당량/중복)는 알림 제외, 나머지는 텔레그램 전송
            if reason not in ("quota_met", "already_running", "similar_title"):
                _tg_error(blog_id, reason, f"[curation] 발행 실패: {reason}")

            # 임계값 기반 추가 알림 (쿨다운, dry_run 지원)
            if reason not in ("quota_met", "already_running"):
                _consecutive_failures[blog_id] = _consecutive_failures.get(blog_id, 0) + 1
                _alert_checker.maybe_alert(blog_id, reason, {"keyword": result.get("keyword", "")})

        return result
    finally:
        _release_lock(lock_file)


def _run_inner(cfg, blog_id, daily_quota):
    """실제 파이프라인 로직 (락 내부에서 실행)"""
    # 할당량 체크
    today_count = get_today_count(blog_id)
    if today_count >= daily_quota:
        logger.info(f"[{blog_id}] 할당량 도달 ({today_count}/{daily_quota})")
        return {"success": False, "reason": "quota_met"}

    # 키워드 선택
    keyword = _select_keyword(blog_id)
    if not keyword:
        logger.error(f"[{blog_id}] 사용 가능한 키워드 없음")
        _record_failure(blog_id, "no_keyword", "사용 가능한 키워드 없음")
        return {"success": False, "reason": "no_keyword"}

    # 상품 수집 (캐시 또는 API)
    collected = collect_keyword(keyword)
    if not collected:
        from pipelines.curation.collector import _check_rate_limit
        if not _check_rate_limit():
            logger.warning(f"[{blog_id}] 쿠팡 API 차단 중 — 다음 실행 시 재시도")
            _record_failure(blog_id, "rate_limited", "쿠팡 API 차단", keyword)
            return {"success": False, "reason": "rate_limited"}
        logger.error(f"[{blog_id}] 상품 수집 실패: {keyword}")
        _record_failure(blog_id, "collect_error", f"쿠팡 API 수집 실패: {keyword}", keyword)
        return {"success": False, "reason": "collect_error"}

    products = get_products(keyword, limit=10)
    products = _filter_used_products(blog_id, products)
    if len(products) < 3:
        logger.warning(f"[{blog_id}] 상품 부족: {keyword} ({len(products)}개) — 다음 키워드 시도")
        # 해당 키워드 캐시 삭제 후 다음 키워드로 재시도
        try:
            conn = sqlite3.connect(str(DB_PATH))
            conn.execute("DELETE FROM products WHERE keyword=?", (keyword,))
            conn.commit()
            conn.close()
        except Exception:
            pass
        # 다음 키워드 선택 (현재 키워드 제외)
        all_kws = get_keywords(blog_id)
        used_conn = sqlite3.connect(str(DB_PATH))
        used = used_conn.execute(
            """SELECT keyword FROM publish_log
               WHERE blog_id=? AND published_at > datetime('now', '-7 days')""",
            (blog_id,)
        ).fetchall()
        used_conn.close()
        used_set = {r[0] for r in used} | {keyword}
        fallback_kws = [k for k in all_kws if k not in used_set]
        if not fallback_kws:
            _record_failure(blog_id, "insufficient_products", "모든 키워드 사용 완료", keyword)
            return {"success": False, "reason": "insufficient_products"}
        keyword = fallback_kws[0]
        logger.info(f"[{blog_id}] 대체 키워드 사용: {keyword}")
        collect_keyword(keyword)
        products = get_products(keyword, limit=10)
        products = _filter_used_products(blog_id, products)
        if len(products) < 3:
            logger.error(f"[{blog_id}] 대체 키워드도 상품 부족: {keyword} ({len(products)}개)")
            _record_failure(blog_id, "insufficient_products", f"대체 키워드도 상품 부족: {keyword}", keyword)
            return {"success": False, "reason": "insufficient_products"}

    # 카테고리 무관 상품 필터링 (코드 레벨)
    # ── 3회 재시도: 불량 키워드로 인한 단일 실패가 전체 pipeline을 죽이지 않도록 ──
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        products = _filter_irrelevant_products(blog_id, keyword, products)
        if len(products) >= 3:
            break
        if attempt == max_retries:
            logger.error(f"[{blog_id}] {max_retries}회 재시도 후 필터 실패: {keyword} ({len(products)}개)")
            _record_failure(blog_id, "irrelevant_products", f"{max_retries}회 재시도 후 필터 실패: {keyword}", keyword)
            return {"success": False, "reason": "irrelevant_products", "keyword": keyword}
        logger.warning(f"[{blog_id}] 필터 후 상품 부족 ({len(products)}개), 대체 키워드 시도 ({attempt}/{max_retries})")
        # 해당 키워드 캐시 삭제
        try:
            conn = sqlite3.connect(str(DB_PATH))
            conn.execute("DELETE FROM products WHERE keyword=?", (keyword,))
            conn.commit()
            conn.close()
        except Exception:
            pass
        # 다음 키워드 선택
        all_kws = get_keywords(blog_id)
        used_conn = sqlite3.connect(str(DB_PATH))
        used = used_conn.execute(
            """SELECT keyword FROM publish_log
               WHERE blog_id=? AND published_at > datetime('now', '-7 days')""",
            (blog_id,)
        ).fetchall()
        used_conn.close()
        used_set = {r[0] for r in used} | {keyword}
        fallback_kws = [k for k in all_kws if k not in used_set]
        if not fallback_kws:
            logger.error(f"[{blog_id}] 대체 키워드 없음 — 발행 중단")
            _record_failure(blog_id, "irrelevant_products", "대체 키워드 없음", keyword)
            return {"success": False, "reason": "irrelevant_products", "keyword": keyword}
        keyword = fallback_kws[0]
        logger.info(f"[{blog_id}] 대체 키워드 사용 ({attempt}/{max_retries}): {keyword}")
        collect_keyword(keyword)
        products = get_products(keyword, limit=10)
        products = _filter_used_products(blog_id, products)

    # ── 관련성 점수 검증 게이트 ──
    try:
        scores = score_products(products, blog_id)
        passed, reason = passes_gate(scores)
        if not passed:
            logger.warning(f"[{blog_id}] 관련성 점수 미달: {scores['avg']:.2f} < {scores['threshold']}")
            _record_failure(blog_id, "low_relevance", f"관련성 점수 {scores['avg']:.2f} < 임계값 {scores['threshold']}", keyword)
            return {"success": False, "reason": "low_relevance", "keyword": keyword}
        logger.info(f"[{blog_id}] 관련성 점수: avg={scores['avg']:.2f}, min={scores['min']:.2f}, 임계값={scores['threshold']}")
    except Exception as e:
        # Fail open: scoring exception should not block publication
        logger.warning(f"[{blog_id}] 관련성 점수 계산 실패 (fail-open): {e}")
        scores = {"avg": 1.0, "min": 1.0, "scores": [], "blog_id": blog_id, "threshold": 1.0}

    # 상품 데이터 인리치 (스펙 파싱 + 네이버 brand)
    products = enrich_products(products, blog_id)

    # AI 글 생성
    article = generate_curation_article(keyword, products, blog_id=blog_id)
    if not article:
        _record_failure(blog_id, "write_error", "AI 글 생성 실패", keyword)
        return {"success": False, "reason": "write_error"}

    # 언어 검증 — 중국어 생성 차단
    _lang_err = assert_korean_or_reject(article.get("title", ""), article.get("body_md", ""), blog_id)
    if _lang_err:
        _record_failure(blog_id, "language_error", _lang_err, keyword)
        logger.error(f"[{blog_id}] {_lang_err}")
        return {"success": False, "reason": "language_error"}

    title = sanitize_title(article["title"])
    body_md = article["body_md"]
    description = article.get("description", "")
    if description:
        body_md = f"<!-- DESC: {description} -->\n\n{body_md}"
    slug = _make_slug(keyword)

    # 제목 품질 검증 — 문맥 확인 후 blocked 키워드 차단
    # 제목에 allowed 키워드가 하나라도 있으면 (캠핑 맥락) 차단 스킵
    _allowed_for_context = ALLOWED_PRODUCT.get(blog_id, {}).get("allowed", [])
    _has_context = any(aw.lower() in title.lower() for aw in _allowed_for_context)
    title_blocked = TITLE_BLOCKED.get(blog_id, [])
    for bw in title_blocked:
        if bw.lower() in title.lower() and not _has_context:
            logger.warning(f"[{blog_id}] 제목에 blocked 키워드 감지: '{bw}' in '{title}'")
            _record_failure(blog_id, "title_blocked", f"제목 blocked 키워드: {bw}", keyword)
            return {"success": False, "reason": "title_blocked"}

    # 썸네일: 첫 번째 상품 이미지를 R2에 업로드
    thumbnail_url = ""
    if products and products[0].get("product_image"):
        thumbnail_url = _upload_thumbnail(products[0]["product_image"])

    # 유사 제목 체크
    if _title_is_duplicate(blog_id, title):
        logger.warning(f"[{blog_id}] 유사 제목 존재: {title}")
        _record_failure(blog_id, "similar_title", f"유사 제목 중복: {title}", keyword)
        return {"success": False, "reason": "similar_title"}

    # 발행
    # 태그 생성: 키워드 + 제목에서 브랜드명 추출
    tag_set = set()
    # 키워드 자체
    tag_set.add(keyword)
    # 키워드 토큰 (2자 이상)
    for tok in keyword.split():
        if len(tok) >= 2:
            tag_set.add(tok)
    # 제목에서 브랜드명 추출 (영문 대문자 시작 단어 + 한글 브랜드)
    brand_patterns = [
                     "레노버", "삼성", "LG", "애플", "MSI", "델", "에이수스", "ASUS", "HP", "Apple",
                     "아이디어패드", "씽크패드", "갤럭시북", "그램", "맥북",
                     "다이슨", "샤오미", "필립스", "쿠쿠", "테팔", "신일", "대웅", "미라스", "제니퍼룸",
                     "한샘", "이케아", "퍼시스", "까사미아", "삼익가구", "베드리움", "비투스", "시디즈", "일룸",
                     "맥킹덤", "베어블리", "코코유", "순성", "다이치", "조이", "브라이텍스", "뉴나",
                     "숀리", "이고진", "엑사이더", "코멧",
                     "젝시미시", "안다르", "뮬라웨어", "나이키", "아식스", "호카", "뉴발란스", "미즈노", "가민", "핏빗"]
    for bp in brand_patterns:
        if bp.lower() in title.lower():
            tag_set.add(bp)
    # 상품 데이터의 brand/maker 필드에서도 태그 추가
    for p in products[:5]:
        for field in ["brand", "maker"]:
            bv = (p.get(field) or "").strip()
            if bv and len(bv) >= 2:
                tag_set.add(bv)
    tags_str = ",".join(list(tag_set)[:6])  # 최대 6개

    result = publish(blog_id, title, body_md, category="추천", tags=tags_str, thumbnail_url=thumbnail_url)
    if not result or not result.get("success"):
        logger.error(f"[{blog_id}] 발행 실패: {title}")
        _record_failure(blog_id, "publish_error", f"Hugo 발행 실패: {title}", keyword)
        return {"success": False, "reason": "publish_error"}

    # 발행 기록 (관련성 점수 포함)
    from shared.relevance_scorer import log_publish_audit
    final_scores = score_products(products, blog_id)
    log_publish_audit(
        str(DB_PATH),
        blog_id, keyword, title, slug,
        scores=final_scores,
        passed=True,
    )
    _record_products(blog_id, keyword, products[:5])
    # 키워드 건강 — 성공 기록 (격리 해제)
    try:
        health_store.record_success(blog_id, keyword)
    except Exception as e:
        logger.warning(f"[keyword_health] 성공 기록 오류: {e}")
    logger.info(f"[{blog_id}] 발행 완료: {title}")

    return {
        "success": True,
        "title": title,
        "keyword": keyword,
        "product_count": article["product_count"],
    }

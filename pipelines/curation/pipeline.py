"""curation 파이프라인 — 상품 큐레이션 글 자동 발행

흐름: 키워드 선택 → 상품 수집(캐시) → AI 글 생성 → Hugo 발행
"""
import os
import sys
import re
import sqlite3
import logging
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv("/Users/twinssn/Projects/5000/.env")

from shared.content_store import get_today_count, title_similar_exists
from shared.publisher import publish
from shared.validators import sanitize_title
from shared.image_handler import process_and_upload
import requests as _requests
from shared.telegram_notifier import send_error as _tg_error
from pipelines.curation.keywords import get_keywords
from pipelines.curation.collector import collect_keyword, get_products
from pipelines.curation.writer import generate_curation_article
from pipelines.curation.enricher import enrich_products

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

def _release_lock(lock_file):
    if lock_file:
        try:
            fcntl.flock(lock_file, fcntl.LOCK_UN)
            lock_file.close()
        except Exception:
            pass

PROJECT_DIR = Path(__file__).parent.parent.parent
DB_PATH = PROJECT_DIR / "data" / "curation.db"

def _init_db():
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




def _select_keyword(blog_id):
    """7일 내 미사용 키워드 중 하나 선택"""
    keywords = get_keywords(blog_id)
    if not keywords:
        return None

    conn = sqlite3.connect(str(DB_PATH))
    used = conn.execute(
        """SELECT keyword FROM publish_log
           WHERE blog_id=? AND published_at > datetime('now', '-7 days')""",
        (blog_id,)
    ).fetchall()
    conn.close()

    used_set = {r[0] for r in used}
    available = [k for k in keywords if k not in used_set]

    if not available:
        conn = sqlite3.connect(str(DB_PATH))
        oldest = conn.execute(
            """SELECT keyword FROM publish_log
               WHERE blog_id=? ORDER BY published_at ASC LIMIT 1""",
            (blog_id,)
        ).fetchone()
        conn.close()
        return oldest[0] if oldest else keywords[0]

    return available[0]


def _upload_thumbnail(image_url):
    """쿠팡 상품 이미지를 R2에 업로드하여 썸네일로 사용"""
    try:
        resp = _requests.get(image_url, timeout=10)
        if resp.status_code == 200 and len(resp.content) > 1000:
            r2_url = process_and_upload(resp.content, key_prefix="curation-images")
            return r2_url
    except Exception as e:
        logger.warning(f"썸네일 업로드 실패: {e}")
    return ""



# ── 카테고리별 허용/차단 키워드 (상품 필터) ──
CATEGORY_FILTERS = {
    "laptop-hugo": {
        "allowed": ["노트북", "laptop", "랩탑", "맥북", "macbook", "그램", "gram",
                     "갤럭시북", "thinkpad", "씽크패드", "victus", "오멘", "vivobook",
                     "비보북", "zenbook", "젠북", "ideapad", "아이디어패드",
                     "크롬북", "chromebook", "울트라북", "서피스"],
        "blocked": ["도서", "책", "교재", "필기", "실기", "기능사", "자격증",
                     "스티커", "마우스패드", "장패드", "키보드", "마우스",
                     "가방", "파우치", "거치대", "받침대", "쿨링패드",
                     "모니터", "데스크탑", "태블릿", "아이패드", "갤럭시탭",
                     "헤드셋", "이어폰", "이어버드", "스피커",
                     "웹캠", "캡쳐보드", "캡처보드",
                     "책상", "의자", "케이블", "HDMI", "USB허브",
                     "독", "dock", "어댑터", "충전기", "보호필름", "스킨",
                     "서류가방", "노트북가방", "CrowPi", "크롤파이",
                     "중고", "트레이딩"],
    },
    "appliance-hugo": {
        "allowed": ["청소기", "에어프라이어", "공기청정기", "제습기", "가습기",
                     "냉장고", "세탁기", "건조기", "식기세척기", "전자레인지",
                     "오븐", "밥솥", "정수기", "선풍기", "히터", "난방기",
                     "로봇청소기", "스팀청소기", "물걸레", "다리미"],
        "blocked": ["도서", "책", "교재", "스티커", "인형", "장난감",
                     "의류", "패션", "화장품"],
    },
    "interior-hugo": {
        "allowed": ["의자", "책상", "소파", "매트리스", "침대", "선반", "수납",
                     "커튼", "블라인드", "조명", "램프", "러그", "카페트",
                     "테이블", "화장대", "옷장", "행거", "거울"],
        "blocked": ["도서", "책", "교재", "식품", "화장품", "의류", "패션",
                     "장난감", "완구"],
    },
    "baby-hugo": {
        "allowed": ["카시트", "유모차", "아기띠", "바운서", "젖병", "분유",
                     "기저귀", "보행기", "범퍼침대", "아기침대", "수유",
                     "이유식", "체온계", "멸균기", "신생아", "유아",
                     "아기", "베이비", "유아용", "영아"],
        "blocked": ["강아지", "반려견", "반려동물", "펫", "개모차", "pet",
                     "고양이", "강아지용", "도그", "dog",
                     "도서", "책", "교재", "성인용"],
    },
    "fitness-hugo": {
        "allowed": ["덤벨", "아령", "바벨", "케틀벨", "런닝머신", "러닝머신",
                     "트레드밀", "워킹머신", "워킹패드", "실내자전거", "스핀바이크",
                     "풀업바", "철봉", "푸쉬업바", "요가매트", "폼롤러",
                     "헬스", "운동", "피트니스", "스텝퍼", "로잉머신",
                     "근력", "스트레칭", "밴드"],
        "blocked": ["도서", "책", "교재", "의류", "신발", "보호대",
                     "영양제", "프로틴", "식품"],
    },
}

# 제목 검증용 blocked 키워드 (AI 생성 제목에 이게 포함되면 발행 차단)
TITLE_BLOCKED = {
    "laptop-hugo": ["마우스", "키보드", "헤드셋", "웹캠", "캡쳐보드", "캡처보드",
                    "태블릿", "아이패드", "갤럭시탭", "서류가방", "장패드",
                    "CrowPi", "크롤파이", "이어폰", "스피커"],
    "baby-hugo":   ["강아지", "반려견", "반려동물", "펫", "개모차", "고양이"],
    "appliance-hugo": [],
    "interior-hugo": [],
    "fitness-hugo": [],
}


def _filter_irrelevant_products(blog_id, keyword, products):
    """카테고리와 무관한 상품 제거 (코드 레벨 필터)"""
    filters = CATEGORY_FILTERS.get(blog_id)
    if not filters:
        return products

    allowed = filters["allowed"]
    blocked = filters["blocked"]
    keyword_lower = keyword.lower()

    filtered = []
    for p in products:
        name = p.get("product_name", "").lower()
        cat = p.get("category_name", "").lower()
        combined = name + " " + cat

        # 차단 키워드 포함 시 제외
        is_blocked = False
        for bw in blocked:
            if bw in combined:
                logger.info(f"[필터] 차단: '{p.get('product_name', '')[:40]}' (차단어: {bw})")
                is_blocked = True
                break
        if is_blocked:
            continue

        # 허용 키워드 중 하나라도 포함되어야 통과
        has_allowed = False
        for aw in allowed:
            if aw in combined or aw in keyword_lower:
                has_allowed = True
                break
        if not has_allowed:
            logger.info(f"[필터] 미허용: '{p.get('product_name', '')[:40]}' (허용어 미포함)")
            continue

        filtered.append(p)

    if len(filtered) < 3:
        logger.warning(f"[{blog_id}] 필터 후 상품 부족 ({len(filtered)}개), 원본 유지")
        return products[:5]

    return filtered


def _filter_used_products(blog_id, products):
    """발행된 적 있는 상품 제외 (blog_id 기준 전체 기간)"""
    if not products:
        return products
    conn = sqlite3.connect(str(DB_PATH))
    used = conn.execute(
        "SELECT product_id FROM published_products WHERE blog_id=? AND published_at > datetime('now', '-90 days')",
        (blog_id,)
    ).fetchall()
    conn.close()
    used_ids = {str(r[0]) for r in used}

    # 현재 상품 product_id를 str로 통일
    current_ids = {str(p["product_id"]) for p in products}
    overlap = current_ids & used_ids
    overlap_ratio = len(overlap) / len(current_ids) if current_ids else 0

    if overlap_ratio >= 0.8:
        logger.info(f"[{blog_id}] 상품 겹침 {overlap_ratio:.0%} ({len(overlap)}/{len(current_ids)}) — 발행 차단")
        return []  # insufficient_products로 처리

    filtered = [p for p in products if str(p["product_id"]) not in used_ids]
    if len(filtered) < 3:
        logger.warning(f"[{blog_id}] 미사용 상품 부족 ({len(filtered)}개), 원본 유지")
        return products[:5]
    return filtered[:5]


def _record_products(blog_id, keyword, products):
    """발행에 사용된 상품 ID 기록"""
    conn = sqlite3.connect(str(DB_PATH))
    now = datetime.now().isoformat()
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
        stop_words = {"추천", "비교", "가성비", "인기", "순위", "정리", "선택", "소개"}
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


def _make_slug(keyword):
    slug = keyword.replace(" ", "-").lower()
    slug = re.sub(r'[^a-z0-9가-힣\-]', '', slug)
    date_prefix = datetime.now().strftime("%Y%m%d")
    return f"{date_prefix}-{slug}"


def _record_publish(blog_id, keyword, title, slug):
    """publish_log에 발행 기록"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        "INSERT INTO publish_log (blog_id, keyword, title, slug, published_at) VALUES (?,?,?,?,?)",
        (blog_id, keyword, title, slug, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


def run(cfg):
    """curation 파이프라인 메인 — dispatcher에서 호출"""
    blog_id = cfg.get("id", "")
    daily_quota = cfg.get("daily_quota", 5)

    # 동시실행 방지
    lock_file = _acquire_lock(blog_id)
    if lock_file is None:
        logger.warning(f"[{blog_id}] 이미 실행 중 (락 획득 실패)")
        return {"success": False, "reason": "already_running"}

    try:
        result = _run_inner(cfg, blog_id, daily_quota)
        if not result.get("success"):
            reason = result.get("reason", "unknown")
            # 조용한 실패(할당량/중복)는 알림 제외, 나머지는 텔레그램 전송
            if reason not in ("quota_met", "already_running", "similar_title"):
                _tg_error(blog_id, reason, f"[curation] 발행 실패: {reason}")
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
        return {"success": False, "reason": "no_keyword"}

    # 상품 수집 (캐시 또는 API)
    collected = collect_keyword(keyword)
    if not collected:
        logger.error(f"[{blog_id}] 상품 수집 실패: {keyword}")
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
            return {"success": False, "reason": "insufficient_products"}
        keyword = fallback_kws[0]
        logger.info(f"[{blog_id}] 대체 키워드 사용: {keyword}")
        collect_keyword(keyword)
        products = get_products(keyword, limit=10)
        products = _filter_used_products(blog_id, products)
        if len(products) < 3:
            logger.error(f"[{blog_id}] 대체 키워드도 상품 부족: {keyword} ({len(products)}개)")
            return {"success": False, "reason": "insufficient_products"}

    # 카테고리 무관 상품 필터링 (코드 레벨)
    products = _filter_irrelevant_products(blog_id, keyword, products)
    if len(products) < 3:
        logger.error(f"[{blog_id}] 필터 후 상품 부족: {keyword} ({len(products)}개)")
        return {"success": False, "reason": "irrelevant_products"}

    # 상품 데이터 인리치 (스펙 파싱 + 네이버 brand)
    products = enrich_products(products, blog_id)

    # AI 글 생성
    article = generate_curation_article(keyword, products, blog_id=blog_id)
    if not article:
        return {"success": False, "reason": "write_error"}

    title = sanitize_title(article["title"])
    body_md = article["body_md"]
    description = article.get("description", "")
    if description:
        body_md = f"<!-- DESC: {description} -->\n\n{body_md}"
    slug = _make_slug(keyword)

    # 제목 품질 검증 — blocked 키워드가 제목에 있으면 발행 차단
    title_blocked = TITLE_BLOCKED.get(blog_id, [])
    for bw in title_blocked:
        if bw.lower() in title.lower():
            logger.warning(f"[{blog_id}] 제목에 blocked 키워드 감지: '{bw}' in '{title}'")
            return {"success": False, "reason": "title_blocked"}

    # 썸네일: 첫 번째 상품 이미지를 R2에 업로드
    thumbnail_url = ""
    if products and products[0].get("product_image"):
        thumbnail_url = _upload_thumbnail(products[0]["product_image"])

    # 유사 제목 체크
    if _title_is_duplicate(blog_id, title):
        logger.warning(f"[{blog_id}] 유사 제목 존재: {title}")
        return {"success": False, "reason": "similar_title"}

    # 발행
    result = publish(blog_id, title, body_md, category="추천", tags=keyword, thumbnail_url=thumbnail_url)
    if not result or not result.get("success"):
        logger.error(f"[{blog_id}] 발행 실패: {title}")
        return {"success": False, "reason": "publish_error"}

    # 발행 기록
    _record_publish(blog_id, keyword, title, slug)
    _record_products(blog_id, keyword, products[:5])
    logger.info(f"[{blog_id}] 발행 완료: {title}")

    return {
        "success": True,
        "title": title,
        "keyword": keyword,
        "product_count": article["product_count"],
    }

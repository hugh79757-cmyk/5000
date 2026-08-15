"""curation 파이프라인 — 상품 큐레이션 글 자동 발행

흐름: 키워드 선택 → 상품 수집(캐시) → AI 글 생성 → Hugo 발행
"""
import logging
import os
import re
import sqlite3
import sys
import hashlib
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
from pipelines.curation.writer import _TITLE_TEMPLATE_PATTERNS as TITLE_TEMPLATE_PATTERNS

# CoT/지시문 유출 감지용 패턴 (정상 본문 오탐 방지: 소제목·리뷰 단어 제외)
WRITING_INSTRUCTION_PATTERNS = [
    re.compile(r"AIDA", re.I),
    re.compile(r"퍼널"),
    re.compile(r"H[23]\s*헤딩"),
    re.compile(r"(다음|아래|출력)\s*형식"),
    re.compile(r"작성(하세요|해\s*주세요|하라)"),
    re.compile(r"프롬프트|지시\s*사항"),
]
COT_BODY_PATTERNS = [
    re.compile(r"사용자\s*요청"),
    re.compile(r"제목\s*(규칙|예시)"),
    re.compile(r"Here'?s\b", re.I),
    re.compile(r"다음은\s*요청하신"),
    re.compile(r"먼저\s*.*을\s*분석"),
]
from pipelines.curation.keyword_health import KeywordHealthStore
from pipelines.curation.writer import generate_curation_article
from shared.content_store import get_today_count
from shared.image_handler import process_and_upload
from shared.publisher import publish
from shared.telegram_notifier import send_error as _tg_error
from shared.validators import assert_korean_or_reject, sanitize_title
from shared.relevance_scorer import migrate_publish_log, score_products, passes_gate
from shared.alert_thresholds import ThresholdChecker
from shared.db import get_db_path
from shared.cuap_entity_linker import (
    inject_cross_blog_links,
    build_cross_sell_card,
    build_funnel_header,
    init_cuap_tables,
    register_cuap_entity,
)

# CUAP 거미줄 테이블 초기화 (한 번만)
try:
    init_cuap_tables()
except Exception as _e:
    logger.warning(f"[cuap] 테이블 초기화 실패 (fail-open): {_e}")

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
DB_PATH = Path(get_db_path("curation"))

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
    # 최근 14일 내 low_relevance 실패 키워드 제외 (Phase 10-1 pre-collect gate)
    try:
        low_relevance_failed = health_store.get_recent_failed_keywords(blog_id, "low_relevance", days=14)
        available = [k for k in available if k not in set(low_relevance_failed)]
    except Exception:
        pass
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


def _upload_thumbnail(image_url, product_id=None):
    """쿠팡 상품 이미지를 R2에 업로드하여 썸네일로 사용 — product_id 기반 해시로 고유 파일명"""
    try:
        resp = _requests.get(image_url, timeout=10)
        if resp.status_code == 200 and len(resp.content) > 1000:
            extra_tag = ""
            if product_id:
                id_hash = hashlib.md5(str(product_id).encode()).hexdigest()[:8]
                extra_tag = f"hash/{id_hash}/"
            return process_and_upload(resp.content, key_prefix=f"curation-images/{extra_tag}")
    except Exception as e:
        logger.warning(f"썸네일 업로드 실패: {e}")
    return ""



# ── 카테고리별 허용/차단 키워드 (상품 필터) ──
CATEGORY_FILTERS = {
    "massage-hugo": {
        "allowed": ["안마의자", "마사지건", "발마사지기", "안마기", "목마사지기", "종아리마사지기", "두피마사지기", "눈마사지기", "어깨마사지기", "전신안마기", "마사지쿠션", "온열안마기", "안마", "마사지", "안마의자"],
        "blocked": ["도서", "교재", "인형", "장난감", "식품", "완구"],
    },
    "car-hugo": {
        "allowed": ["블랙박스", "차량용청소기", "하이패스", "차량용공기청정기", "타이어공기주입기", "트렁크정리함", "차량용거치대", "차량용방향제", "차량용냉장고", "핸들커버", "차량용무선충전기", "자동차매트", "차량용", "자동차", "카", "블박"],
        "blocked": ["도서", "교재", "인형", "장난감", "식품", "완구", "의류"],
    },
    "homeappliance-hugo": {
        "allowed": ["김치냉장고", "의류관리기", "식기세척기", "인덕션", "전기레인지", "벽걸이에어컨", "스탠드에어컨", "워시타워", "드럼세탁기", "건조기", "양문형냉장고", "광파오븐", "가전", "냉장고", "세탁기", "에어컨"],
        "blocked": ["도서", "교재", "인형", "장난감", "식품", "완구", "의류"],
    },
    "golf-hugo": {
        "allowed": ["골프클럽", "골프드라이버", "아이언세트", "골프백", "골프거리측정기", "골프화", "퍼터", "골프공", "골프장갑", "골프의류", "골프우산", "스윙연습기", "골프", "스윙"],
        "blocked": ["도서", "교재", "인형", "장난감", "식품", "완구"],
    },
    "bike-hugo": {
        "allowed": ["전기자전거", "접이식자전거", "로드자전거", "MTB자전거", "미니벨로", "하이브리드자전거", "자전거헬멧", "전동킥보드", "자전거자물쇠", "자전거라이트", "아동자전거", "자전거거치대", "자전거", "바이크", "킥보드"],
        "blocked": ["도서", "교재", "인형", "장난감", "식품", "완구"],
    },
    "laptop-hugo": {
        "allowed": ["노트북", "laptop", "랩탑", "맥북", "macbook", "그램", "gram",
                     "갤럭시북", "thinkpad", "씽크패드", "victus", "오멘", "vivobook",
                     "비보북", "zenbook", "젠북", "ideapad", "아이디어패드",
                     "크롬북", "chromebook", "울트라북", "서피스",
                     "컴퓨터", "전자기기",
                     "ASUS", "HP", "레노버", "MSI", "에이수스", "DELL", "델",
                     "SSD", "RAM", "CPU", "GPU", "그래픽", "메모리", "저장장치",
                     "가방", "케이스", "거치대", "쿨러", "도킹스테이션", "파우치",
                     "모니터", "키보드", "마우스", "프린터", "스캐너",
                     "태블릿", "아이패드", "2in1", "컨버터블",
                     "게이밍", "사무용", "학생용", "개발자", "프로그래밍"],
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
                     "가전", "디지털",
                     "다이슨", "쿠첸", "쿠쿠", "에어컨", "TV", "스타일러",
                     "면도기", "제모기", "헤어드라이어",
                     "커피머신", "에스프레소", "제빵기", "음식물처리기",
                     "공기청정기필터", "두피케어", "안마의자", "비데"],
        "blocked": ["도서", "교재", "스티커", "인형", "장난감",
                     "의류", "패션", "화장품",
                     "생활용품", "출산/유아", "반려동물", "식품", "완구"],
    },
    "interior-hugo": {
        "allowed": ["의자", "책상", "소파", "매트리스", "침대", "선반", "수납",
                     "커튼", "블라인드", "조명", "램프", "러그", "카페트",
                     "테이블", "화장대", "옷장", "행거", "거울",
                     "가구", "인테리어",
                     "모던", "북유럽", "미니멀", "빈티지", "클래식",
                     "거실", "침실", "욕실", "베란다", "사무실", "서재",
                     "원목", "철제", "유리", "대리석",
                     "액자", "쿠션", "담요", "벽시계", "화병", "캔들", "식물", "스탠드",
                     "다운라이트", "led등", "천장등", "다운라이트조명", "매입등"],
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
                     "육아", "출산",
                     "물티슈", "아기세제", "로션", "아기오일", "아기비누",
                     "아기옷", "배넷저고리", "우주복", "아기양말", "아기모자",
                     "아기욕조", "유아변기", "아기안전문",
                     "아기장난감", "촉감놀이", "아기블록", "딸랑이",
                     "이유식용기", "유아식기", "아기빨대컵", "분유포트",
                     "모서리보호대", "임산부"],
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
                      "스포츠", "레저", "다이어트", "논슬립", "괄약근",
                     "마사지볼", "릴렉스", "회복",
                     "아미노산", "글루타민", "프리워크아웃",
                     "기능성티셔츠", "스포츠양말",
                     "로프", "역도", "크로스핏", "케이블", "런지", "스쿼트", "데드리프트"],
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
                     "건강식품", "영양제",
                     "혈관", "콜레스테롤", "다이어트", "탈모", "스트레스",
                     "수면", "소화", "건강기능식품", "건강차", "약초", "한방",
                     "고려은단", "나우푸드", "쏜리서치",
                     "프리미엄", "프리바이오틱스", "비건", "유기농"],
        "blocked": ["생활용품", "주방", "반려동물", "패션", "전자기기", "장난감", "완구",
                     "가전", "출산/유아"],
        "required": [],
    },
    "pet-hugo": {
        "allowed": ["강아지", "고양이", "반려동물", "개", "dog", "cat", "pet",
                     "사료", "간식", "캣타워", "스크래쳐", "하네스", "리드줄",
                     "배변", "화장실", "모래", "이동장", "켄넬", "방석",
                     "급식기", "정수기", "드라이룸", "샴푸", "치약",
                     "유모차", "노즈워크", "그루밍", "영양제",
                     "장난감", "간식토이",
                     "미용", "클리퍼", "브러쉬", "발톱",
                     "관절", "눈물자국", "치석",
                     "야외", "이동가방", "캐리어",
                     "의류", "넥카라", "인식표", "패드", "담요", "케이지", "울타리",
                     "침대", "쿨매트", "계단", "우비",
                     "칫솔", "덴탈껌", "구강",
                     "동결건조", "화식", "수제간식", "유산균", "오메가3",
                     "드라이기", "타월", "목욕", "귀세정제",
                     "훈련", "클리커",
                     "식기", "물그릇", "자동급수기", "분수",
                     "안전벨트", "카시트", "크레이트",
                     "보호대", "신발", "수영복", "구명조끼",
                     "배변봉투", "배변판", "기저귀",
                     "캣닢", "캣그라스", "캣휠", "터널", "해먹",
                     "펫캠", "CCTV",
                     "생일", "캠핑", "파티",
                     "피부", "알러지", "헤어볼",
                     "분유", "우유", "파우치", "츄르", "캔",
                     "덴탈", "관리", "브랜드"],
        "blocked": ["전자기기", "가전", "주방", "완구",
                     "생활용품", "출산/유아", "가구", "홈인테리어", "스포츠/레저"],
        "required": [],
    },
    "kitchen-hugo": {
        "allowed": ["냄비", "프라이팬", "주방", "식기", "칼", "도마", "용기",
                     "텀블러", "도시락", "밀폐", "보관", "조리도구",
                     "가위", "저울", "타이머", "주걱", "냄비받침",
                     "에어프라이어", "전기냄비", "밥솥", "믹서기", "전기포트",
                     "커피머신", "식기세척기", "찜기", "와플", "토스터",
                     "블렌더", "착즙기", "그릴", "인덕션", "세제",
                     "주방용품", "조리",
                     "베이킹", "제빵", "케이크",
                     "그릇", "접시", "머그", "컵", "유리잔", "수저",
                     "밀폐용기", "진공", "보온병", "런치박스", "반찬통",
                     "뒤집개", "국자", "스테인리스", "세라믹", "실리콘"],
        "blocked": ["패션", "의류", "반려동물", "완구", "장난감", "건강식품", "영양제",
                     "생활용품", "가전디지털", "출산/유아", "스포츠/레저", "식품",
                     "가정용"],
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
                     "뷰티", "화장품", "스킨케어",
                     "라네즈", "헤라", "설화수", "아모레", "미샤", "이니스프리",
                     "브러쉬", "퍼프", "거울", "화장품정리함",
                     "네일", "속눈썹", "눈썹", "남성화장품",
                     "비비크림", "선스틱", "립글로스", "아이섀도우"],
        "blocked": ["식품", "전자기기", "가전", "완구", "반려동물", "주방", "캠핑", "생활용품", "위생용품", "음료",
                     "출산/유아", "스포츠/레저", "문구/오피스", "가구",
                     "가구", "인테리어", "소파", "침대", "책상", "의자",
                     "노트북", "컴퓨터", "태블릿", "모니터",
                     "냉장고", "세탁기", "건조기", "청소기",
                     "공기청정기", "에어컨",
                     "덤벨", "데스크", "운동", "헬스"],
        "required": [],
    },
    "camping-hugo": {
        "allowed": ["텐트", "타프", "침낭", "캠핑", "랜턴", "버너", "코펠",
                     "매트", "쿨러", "아이스박스", "화로대", "그릴", "식기",
                     "헤드랜턴", "해먹", "모기장", "선풍기", "난로", "조명",
                     "카트", "가스통", "방수포", "멀티툴", "배낭", "등산화",
                     "트레킹폴", "폴대", "페그", "우비", "모자",
                     "백패킹", "스노우피크", "정리함",
                     "아웃도어", "레저",
                     "트레킹", "등산", "백패킹", "낚시",
                     "콜맨", "코베아", "블랙야크", "노스페이스",
                     "등산복", "아웃도어의류", "방수자켓",
                     "캠핑의자", "접이식테이블", "캠핑웨건"],
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

# 하드 차단 카테고리 — 상품명 allowed 여부와 무관하게 무조건 차단
# 단, 자기 주제 블로그는 예외 (예: pet-hugo는 반려동물 상품 허용)
HARD_BLOCK = {"반려동물", "펫", "pet", "dog", "cat", "강아지", "고양이"}
HARD_BLOCK_EXCEPTIONS = {"pet-hugo"}  # 자기 주제 키워드는 면제

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

        # 하드 차단 — 예외 블로그(pet-hugo 등)는 면제
        cat_hard_blocked = False
        if blog_id not in HARD_BLOCK_EXCEPTIONS:
            cat_hard_blocked = any(hb in cat for hb in HARD_BLOCK)

        # 상품명이 allowed 키워드를 포함하면 일반 차단 무시 (context-aware)
        # 단, 하드 차단은 예외 블로그가 아닌 한 적용
        name_has_allowed = any(aw in name for aw in allowed)

        # 차단 키워드 — category_name + product_name 모두 확인
        is_blocked = False
        if cat_hard_blocked:
            logger.info(f"[필터] 하드차단: '{p.get('product_name', '')[:40]}' (카테고리: {cat[:30]})")
            is_blocked = True
        else:
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
    """publish_log에서 유사 제목 체크 (3일 이내, SequenceMatcher + 단어 겹침)"""
    import re as _re
    from difflib import SequenceMatcher
    conn = sqlite3.connect(str(DB_PATH))

    normalized = _re.sub(
        r"[0-9]곳|[0-9]선|총정리|정리|한눈에 보기|추천 리스트|추천|비교|체크리스트|및|과|와|vs|VS|TOP[0-9]+|[0-9]{4}년?",
        "", title
    ).strip()
    normalized = _re.sub(r"\s+", " ", normalized).strip()

    found = False
    if len(normalized) >= 5:
        recent = conn.execute(
            """SELECT title FROM publish_log
               WHERE blog_id=? AND published_at > datetime('now', '-3 days')""",
            (blog_id,),
        ).fetchall()
        for (prev_title,) in recent:
            if not prev_title:
                continue
            prev_norm = _re.sub(
                r"[0-9]곳|[0-9]선|총정리|정리|한눈에 보기|추천 리스트|추천|비교|체크리스트|및|과|와|vs|VS|TOP[0-9]+|[0-9]{4}년?",
                "", prev_title
            ).strip()
            prev_norm = _re.sub(r"\s+", " ", prev_norm).strip()
            ratio = SequenceMatcher(None, normalized, prev_norm).ratio()
            if ratio >= 0.85:
                logger.info(f"[중복체크] 유사 제목: '{title[:30]}' ≈ '{prev_title[:30]}' ({ratio:.0%})")
                found = True
                break

    if not found:
        title_words = set(_re.findall(r"[가-힣a-zA-Z0-9]{2,}", title))
        stop_words = {
            # 기존
            "추천", "비교", "가성비", "인기", "순위", "정리", "선택", "소개", "vs", "년", "월", "위",
# 연도/월 (Tier 1)
        "2024", "2025", "2026", "2024년", "2025년", "2026년", "7월", "6월", "5월", "4월", "3월",
            # 범용 속성 (Tier 2)
            "1위", "2위", "대용량", "가정용", "프리미엄", "사무용", "저소음",
            "가벼운", "최고의", "필수템", "아이템", "다용도", "위한", "기준", "자동",
            # 동물/펫 카테고리 (Tier 3 - pet-hugo 등)
            "강아지", "고양이", "반려견", "반려묘", "펫", "애완",
            # 제품 유형 (Tier 4)
            "사료", "간식", "방석", "매트", "계단", "유모차", "쿨매트", "캣타워", "하우스", "장난감",
            "목줄", "가슴줄", "리드줄", "배변패드", "샴푸", "브러시", "발톱깎이",
            # 브랜드/시리즈 (Tier 5) - 공통 패턴
            "TOP", "BEST", "순위", "비교", "선택", "이유", "엄선", "고민", "해결", "고르는", "법",
            "최신", "가이드", "실제", "써본", "사람", "말하는", "실사용", "후기", "어떤", "게", "나을까",
            "메모리폼", "에어네트", "노령견", "곡선형", "쾌적", "실속", "롤매트", "폴딩", "가수분해",
            "그리니즈", "말티즈", "뉴트리나", "네스펫", "멍보스", "아스쿠", "마이펫닥터", "더독",
            "슬로울리라이프", "EHEYCIGA", "몽제", "로하우스", "디팡", "BUNIO", "오해", "가지",
            "바로잡기", "건강백서", "순", "인기", "추천", "이유", "기준", "바로잡기",
        }
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
    consecutive = 0
    if keyword:
        try:
            health_store.record_failure(blog_id, keyword, stage)
            row = health_store._get_row(blog_id, keyword)
            if row:
                consecutive = row.get("consecutive_failures", 0)
        except Exception as e:
            logger.warning(f"[keyword_health] 기록 오류: {e}")
    
    # 연속 3회 이상 실패 시 Telegram 알림 (Phase 10-1)
    if consecutive >= 3:
        try:
            from shared.telegram_notifier import send_error as _tg_error
            _tg_error(blog_id, stage, f"연속 {consecutive}회 실패: {error_msg} ({keyword})")
        except Exception as e:
            logger.warning(f"[telegram] 알림 전송 오류: {e}")


def _title_gate(blog_id: str, keyword: str, article: dict):
    """발행 전 제목 품질 게이트 — 템플릿/재생성 실패 제목 차단 (thin wrapper).

    Returns:
        (title, None) — 통과 (title은 article["title"] 그대로)
        (None, {"success": False, "reason": "title_blocked"}) — 차단
    """
    article = article or {}
    title = article.get("title", "")
    if article.get("title_generation_failed") or not title:
        _record_failure(blog_id, "title_regenerate_failed", f"제목 재생성 실패 (2회 소진): {keyword}", keyword)
        return None, {"success": False, "reason": "title_blocked"}
    for pat in TITLE_TEMPLATE_PATTERNS:
        if pat.search(title):
            _record_failure(blog_id, "title_blocked", f"템플릿 제목 패턴: {title}", keyword)
            return None, {"success": False, "reason": "title_blocked"}
    return title, None


def _content_quality_gate(blog_id: str, keyword: str, article: dict):
    """발행 전 전체 아티팩트 품질 게이트 — title + description + body 종합 검증.

    신호 5종:
    1) title 템플릿 패턴 (TITLE_TEMPLATE_PATTERNS)
    2) description CoT 마커 ("우선", "사용자 요청", "제목 규칙", "제목 예시")
    3) body 영어 문장 비율 > 30%
    4) body 글쓰기 지시어 3개 이상 (WRITING_INSTRUCTION_PATTERNS)
    5) body CoT 마커 2개 이상 (COT_BODY_PATTERNS)

    판정:
    - 신호 2개 이상 충족 시 fail-closed 차단
    - 예외: 신호 3+4+5 모두 충족(명백한 CoT body) → 즉시 차단 (신호 수 무관)
    - 단일 신호는 오탐 가능성 있어 통과

    Returns:
        (article, None) — 통과
        (None, {"success": False, "reason": "content_quality_gate"}) — 차단
    """
    article = article or {}
    title = article.get("title", "") or ""
    description = article.get("description", "") or ""
    body = article.get("body_md", "") or ""

    signals_met = []
    signal_details = []

    # 신호 1: title 템플릿 패턴
    if any(pat.search(title) for pat in TITLE_TEMPLATE_PATTERNS):
        signals_met.append(1)
        signal_details.append("title_template")

    # 신호 2: description CoT 마커
    desc_cot_markers = ["사용자 요청", "제목 규칙는", "제목 예시:"]
    if any(marker in description for marker in desc_cot_markers):
        signals_met.append(2)
        signal_details.append("desc_cot")

    # 신호 3: body 영어 문장 비율 > 30%
    if body:
        total_chars = len(body)
        if total_chars > 0:
            english_chars = sum(1 for c in body if c.isascii() and c.isalpha())
            english_ratio = english_chars / total_chars
            if english_ratio > 0.30:
                signals_met.append(3)
                signal_details.append(f"body_english_ratio={english_ratio:.2f}")

    # 신호 4: body 글쓰기 지시어 3개 이상
    writing_matches = sum(1 for pat in WRITING_INSTRUCTION_PATTERNS if pat.search(body))
    if writing_matches >= 3:
        signals_met.append(4)
        signal_details.append(f"writing_instructions={writing_matches}")

    # 신호 5: body CoT 마커 2개 이상
    cot_body_matches = sum(1 for pat in COT_BODY_PATTERNS if pat.search(body))
    if cot_body_matches >= 2:
        signals_met.append(5)
        signal_details.append(f"cot_body={cot_body_matches}")

    # 판정
    # 명백한 CoT body (신호 3+4+5 모두) → 즉시 차단
    if all(s in signals_met for s in (3, 4, 5)):
        _record_failure(blog_id, "content_quality_gate", f"명백한 CoT body 차단: {signal_details}", keyword)
        return None, {"success": False, "reason": "content_quality_gate"}

    # 일반: 2개 이상 신호 충족 시 차단
    if len(signals_met) >= 2:
        _record_failure(blog_id, "content_quality_gate", f"콘텐츠 품질 게이트 차단: 신호 {signal_details}", keyword)
        return None, {"success": False, "reason": "content_quality_gate"}

    # 단일 신호 또는 신호 없음 → 통과
    return article, None


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

            # ── Phase 58 모니터 통합 (additive — reason → spec.hook 매핑, 기존 알림과 병렬) ──
            # phase는 lookup_reason()로 매핑된 spec.hook 그대로 사용 (deploy_error → post_deploy).
            # 하드코딩 금지 — monitor가 hook 불일치를 차단함.
            try:
                from shared.problem_registry import lookup_reason
                from shared.problem_monitor import get_monitor
                _spec = lookup_reason(reason)
                if _spec is not None:
                    get_monitor().report(
                        blog_id,
                        {"reason": reason},
                        phase=_spec.hook,
                        extra={"consecutive_failures": _consecutive_failures.get(blog_id, 0) + 1},
                    )
                else:
                    logger.warning(f"[problem_monitor] 미등록 reason (curation run): {reason}")
            except Exception as _me:
                logger.error(f"[problem_monitor] curation run() 보고 실패: {_me}")

            # 임계값 기반 추가 알림 (쿨다운, dry_run 지원)
            if reason not in ("quota_met", "already_running"):
                _consecutive_failures[blog_id] = _consecutive_failures.get(blog_id, 0) + 1
                _alert_checker.maybe_alert(blog_id, reason, {
                    "keyword": result.get("keyword", ""),
                    "consecutive_failures": _consecutive_failures[blog_id],
                })

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

    # ── 관련성 점수 검증 게이트 (3-retry fallback — Phase 10) ──
    # Note: low_relevance previously had zero retry. Now mirrors irrelevant_products logic.
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            scores = score_products(products, blog_id)
            # adaptive threshold 적용 (Phase 10-1) — 최근 성공 평균 기반으로 과도한 탈락 방지
            try:
                from shared.relevance_scorer import get_adaptive_threshold
                scores["threshold"] = get_adaptive_threshold(DB_PATH, blog_id, scores["threshold"])
            except Exception:
                pass
            # 개별 상품 drop — 임계값 미달 상품 제거 후 평균 재산출
            threshold = scores["threshold"]
            paired = list(zip(products, scores["scores"]))
            dropped_individual = [(p, s) for p, s in paired if s < threshold]
            passed_individual = [(p, s) for p, s in paired if s >= threshold]
            if dropped_individual:
                for p, s in dropped_individual:
                    logger.info(f"[{blog_id}] 개별 drop: '{p.get('product_name', '')[:30]}' (score={s:.2f} < {threshold})")
                if len(passed_individual) >= 3:
                    products = [p for p, _ in passed_individual]
                    scores["scores"] = [s for _, s in passed_individual]
                    scores["avg"] = sum(scores["scores"]) / len(scores["scores"])
                    scores["min"] = min(scores["scores"])
                else:
                    logger.warning(f"[{blog_id}] 개별 drop 후 상품 부족 ({len(passed_individual)}개 < 3)")
            passed, reason = passes_gate(scores)
            if passed:
                logger.info(f"[{blog_id}] 관련성 점수: avg={scores['avg']:.2f}, min={scores['min']:.2f}, 임계값={scores['threshold']}")
                break
            logger.warning(f"[{blog_id}] 관련성 점수 미달 ({attempt}/{max_retries}): avg={scores['avg']:.2f} < {scores['threshold']}")
            if attempt == max_retries:
                _record_failure(blog_id, "low_relevance", f"{max_retries}회 재시도 후 점수 미달: avg={scores['avg']:.2f}", keyword)
                return {"success": False, "reason": "low_relevance", "keyword": keyword}
            # Fallback: pick another keyword and retry (category-aware — Phase 10-1)
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
            fallback_kws = [k for k in fallback_kws if not health_store.is_quarantined(blog_id, k)]
            
            # Category-aware fallback: 실패 키워드와 다른 카테고리 우선
            failed_cat = _extract_category(keyword)
            cat_fallback = [k for k in fallback_kws if _extract_category(k) != failed_cat]
            
            if cat_fallback:
                keyword = cat_fallback[0]
            elif fallback_kws:
                keyword = fallback_kws[0]
            else:
                _record_failure(blog_id, "low_relevance", "대체 키워드 없음", keyword)
                return {"success": False, "reason": "low_relevance", "keyword": keyword}
            logger.info(f"[{blog_id}] low_relevance 대체 키워드 ({attempt}/{max_retries}): {keyword}")
            collect_keyword(keyword)
            products = get_products(keyword, limit=10)
            products = _filter_used_products(blog_id, products)
            products = _filter_irrelevant_products(blog_id, keyword, products)
            if len(products) < 3:
                logger.warning(f"[{blog_id}] 대체 키워드 상품 부족 ({len(products)}개), 다음 fallback 시도")
                continue
        except Exception as e:
            # Fail open: scoring exception should not block publication
            logger.warning(f"[{blog_id}] 관련성 점수 계산 실패 (fail-open): {e}")
            scores = {"avg": 1.0, "min": 1.0, "scores": [], "blog_id": blog_id, "threshold": 1.0}
            break

    # 상품 데이터 인리치 (스펙 파싱 + 네이버 brand)
    products = enrich_products(products, blog_id)

    # AI 글 생성
    article = generate_curation_article(keyword, products, blog_id=blog_id)
    if not article:
        _record_failure(blog_id, "write_error", "AI 글 생성 실패", keyword)
        return {"success": False, "reason": "write_error"}

    # 제목 품질 게이트 — 템플릿/재생성 실패 제목 차단 (fail-closed, 언어 검증 이전)
    _gated_title, _gate_err = _title_gate(blog_id, keyword, article)
    if _gate_err is not None:
        return _gate_err

    # 전체 아티팩트 품질 게이트 — title + description + body 종합 검증 (Task 4)
    _gated_article, _content_err = _content_quality_gate(blog_id, keyword, article)
    if _content_err is not None:
        return _content_err

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

    # 썸네일: 첫 번째 상품 이미지를 R2에 업로드 — product_id 해시 기반 고유 파일명
    thumbnail_url = ""
    if products and products[0].get("product_image"):
        thumbnail_url = _upload_thumbnail(
            products[0]["product_image"],
            product_id=products[0].get("product_id")
        )

    # 유사 제목 체크 — 실패 시 최대 3회 fallback 키워드 재시도
    _st_attempt = 0
    _st_max = 3
    while _title_is_duplicate(blog_id, title):
        _st_attempt += 1
        if _st_attempt > _st_max:
            logger.warning(f"[{blog_id}] {_st_max}회 fallback 후에도 유사 제목 — 포기")
            _record_failure(blog_id, "similar_title", f"유사 제목 중복 (fallback 소진): {title}", keyword)
            return {"success": False, "reason": "similar_title", "keyword": keyword}

        logger.warning(f"[{blog_id}] 유사 제목 존재: {title} — fallback 키워드 시도 ({_st_attempt}/{_st_max})")
        _record_failure(blog_id, "similar_title", f"유사 제목 중복: {title}", keyword)
        # fallback 키워드 선택
        all_kws = get_keywords(blog_id)
        _conn_st = sqlite3.connect(str(DB_PATH))
        _used_st = _conn_st.execute(
            "SELECT keyword FROM publish_log WHERE blog_id=? AND published_at > datetime('now', '-7 days')",
            (blog_id,),
        ).fetchall()
        _conn_st.close()
        _used_set = {r[0] for r in _used_st} | {keyword}
        _fallback_kws = [k for k in all_kws if k not in _used_set]
        # quarantine 제외
        _fallback_kws = [k for k in _fallback_kws if not health_store.is_quarantined(blog_id, k)]
        if not _fallback_kws:
            logger.warning(f"[{blog_id}] fallback 키워드 없음 — 유사 제목 포기")
            _record_failure(blog_id, "similar_title", "fallback 키워드 없음", keyword)
            return {"success": False, "reason": "similar_title", "keyword": keyword}

        keyword = _fallback_kws[0]
        logger.info(f"[{blog_id}] fallback 키워드: {keyword}")
        collect_keyword(keyword)
        products = get_products(keyword, limit=10)
        products = _filter_used_products(blog_id, products)
        if len(products) < 3:
            logger.warning(f"[{blog_id}] fallback 키워드 상품 부족 ({len(products)}개) — 다음 시도")
            continue
        # fallback 키워드로 AI 재생성
        article = generate_curation_article(keyword, products, blog_id=blog_id)
        if not article:
            logger.warning(f"[{blog_id}] fallback AI 생성 실패 — 다음 시도")
            continue
        # 제목 품질 게이트 — 실패 시 다음 fallback 키워드 진행 (_record_failure는 wrapper 내부 처리)
        _gated_title, _gate_err = _title_gate(blog_id, keyword, article)
        if _gate_err is not None:
            logger.warning(f"[{blog_id}] fallback 제목 게이트 차단 — 다음 시도")
            continue
        _lang_err = assert_korean_or_reject(article.get("title", ""), article.get("body_md", ""), blog_id)
        if _lang_err:
            logger.warning(f"[{blog_id}] fallback 언어 오류 — 다음 시도")
            continue
        title = sanitize_title(article["title"])
        body_md = article["body_md"]
        description = article.get("description", "")
        if description:
            body_md = f"<!-- DESC: {description} -->\n\n{body_md}"
        slug = _make_slug(keyword)
        # while 루프 재진입 → _title_is_duplicate 재검사

    # === 본문 구조 정규화 (결정론적 후처리) ===
    def _normalize_product_blocks(md: str, products=None) -> str:
        """빈 불릿 제거 + 제휴문구 위치 정규화 + CTA 구조 복원."""
        DISCLOSURE = "이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다."

        # (1) 값 없는 라벨 불릿 제거:  "- 배송:" / "- 이미지:" 등 콜론 뒤 공백뿐인 줄
        lines = md.split("\n")
        cleaned = []
        for ln in lines:
            s = ln.strip()
            # "- 라벨:" 뒤에 값이 없는 경우 (또는 "-" 만 남은 줄) 제거
            if re.match(r"^-\s*[^:]{0,20}:\s*$", s):
                continue
            if s == "-":
                continue
            # "- 이미지: <url>" 라벨 불릿은 본문에 노출 불필요 → 제거 (썸네일은 featureimage로 처리)
            if re.match(r"^-\s*이미지:\s*\S", s):
                continue
            cleaned.append(ln)
        md = "\n".join(cleaned)

        # (2) 상품 블록 안(불릿과 CTA 사이)에 끼어든 제휴문구 제거 → 전부 삭제 후 재삽입
        md = md.replace(DISCLOSURE, "")

        # (3) CTA div가 여러 줄로 쪼개진 경우 한 줄로 복원
        #     "<div ...>" \n (빈줄/문단) \n "<a ...>...</a></div>" → 한 줄로 병합
        md = re.sub(
            r'(<div style="text-align:center;margin:1\.5rem 0">)\s*\n\s*\n?(<a class="btn-price-check".*?</a></div>)',
            r'\1\2',
            md,
            flags=re.DOTALL,
        )
        # (3-b) 리스트 항목(- )에 붙은 CTA 버튼을 독립 블록으로 분리
        #       "- <div ...btn-price-check...></div>" → 앞의 "- " 제거 + 앞뒤 빈 줄
        md = re.sub(
            r'^-\s*(<div style="text-align:center;margin:1\.5rem 0"><a class="btn-price-check".*?</a></div>)\s*$',
            r'\n\1\n',
            md,
            flags=re.MULTILINE,
        )
        # 혹시 마크다운 CTA 링크가 div 안에서 쪼개진 잔재 정리 (연속 빈줄 축소)
        md = re.sub(r"\n{3,}", "\n\n", md)

        # (4) 제휴문구를 첫 상품(## 상품별 상세 비교) 직전 1회 + 글 맨 끝 1회 삽입
        disc_block = "\n\n" + DISCLOSURE + "\n\n"
        # 상단: "## 상품별 상세 비교" 앞
        m = re.search(r"^##\s*상품별 상세", md, flags=re.MULTILINE)
        if m:
            md = md[:m.start()] + DISCLOSURE + "\n\n" + md[m.start():]
        # 하단: 맨 끝에 1회 (cross-sell/cta-box보다 뒤가 아니라, 본문 마지막 문단 뒤)
        md = md.rstrip() + "\n\n" + DISCLOSURE + "\n"
        # (4-b) "상품별 상세 비교" 소제목을 H2로 강제 (AI가 strong/bold로 출력하는 문제)
        md = re.sub(r"^\s*<strong>\s*(상품별 상세 비교)\s*</strong>\s*$", r"## \1", md, flags=re.MULTILINE)
        md = re.sub(r"^\s*\*\*\s*(상품별 상세 비교)\s*\*\*\s*$", r"## \1", md, flags=re.MULTILINE)
        # (4-c) 첫 상품 H3 앞에 "상품별 상세 비교" H2가 없으면 삽입
        if "## 상품별 상세" not in md:
            m = re.search(r"^###\s+", md, flags=re.MULTILINE)
            if m:
                md = md[:m.start()] + "## 상품별 상세 비교\n\n" + md[m.start():]

        # (5) 각 H3 상품 제목 아래에 상품 이미지 삽입 (상품명 앞토큰 매칭)
        if products:
            def _key(name):
                return re.sub(r"[\s\W]+","",(name or "")[:12]).lower()
            imgmap=[(_key(p.get("product_name","")),p.get("product_image","")) for p in products if p.get("product_image")]
            out=[]
            for ln in md.split("\n"):
                out.append(ln)
                m=re.match(r"^###\s+(.*)",ln)
                if m:
                    hk=re.sub(r"[\s\W]+","",m.group(1)[:12]).lower()
                    for k,url in imgmap:
                        if k and k in hk or hk and hk in k:
                            out.append("")
                            out.append(f'{{{{< figure src="{url}" alt="{m.group(1)}" >}}}}')
                            out.append("")
                            break
            md="\n".join(out)
        md=re.sub(r"\n{3,}","\n\n",md)
        return md

    # 큐레이션 CTA markdown 링크 → HTML 버튼 변환
    # 재정의: AI 생성 마크다운 CTA 링크를 HTML 버튼으로 변환
    def fix_markdown_cta_links(body_md: str) -> str:
        """AI가 생성한 markdown CTA 링크를 HTML 버튼으로 변환."""
        # Coupang affiliate 링크만 대상
        CTA_PATTERN = r'\[([^\]]+)\]\((https?://(?:link\.coupang\.com|www\.coupang\.com)[^)]+)\)'
        replacement = r'<div style="text-align:center;margin:1.5rem 0"><a class="btn-price-check" href="\2">🛒 \1</a></div>'
        return re.sub(CTA_PATTERN, replacement, body_md)

    # 큐레이션 CTA fallback — AI가 CTA를 생성하지 않은 경우 자동 삽입
    _HAS_CTA = "cta-box" in body_md or "cta_box" in body_md
    if not _HAS_CTA:
        _FALLBACK_CTA = (
            '\n\n<div class="cta-box">\n'
            '<p>💡 구매 팁</p>\n'
            '<p>위 상품들의 가격은 변동될 수 있으니 최신 가격을 꼭 확인해보세요.<br>'
            '아래 링크에서 자세한 정보와 후기를 확인할 수 있습니다.</p>\n'
            '</div>'
        )
        body_md += _FALLBACK_CTA
        logger.info(f"[{blog_id}] 큐레이션 CTA fallback 삽입")

    # CTA markdown → HTML post-processing
    body_md = fix_markdown_cta_links(body_md)
    body_md = _normalize_product_blocks(body_md, products)

    # CUAP 거미줄 크로스 링크 삽입 (fail-open)
    try:
        body_md = inject_cross_blog_links(body_md, blog_id, max_links=3)
        cross_card = build_cross_sell_card(blog_id, max_items=4)
        if cross_card:
            body_md += "\n\n" + cross_card
        funnel = build_funnel_header(blog_id)
        if funnel:
            body_md = funnel + "\n\n" + body_md
        logger.info(f"[{blog_id}] CUAP 거미줄 링크 삽입 완료")
    except Exception as _e:
        logger.warning(f"[{blog_id}] CUAP 거미줄 링크 삽입 실패 (fail-open): {_e}")

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

    is_draft = cfg.get("force_draft", False) or article.get("is_draft", False)
    result = publish(blog_id, title, body_md, category="추천", tags=tags_str, thumbnail_url=thumbnail_url, is_draft=is_draft)
    if not result or not result.get("success"):
        error = result.get("error", "") if result else ""
        if "leak_detected" in error:
            _record_failure(blog_id, "leak_detected", error[:200], keyword)
            return {"success": False, "reason": "leak_detected"}
        elif "C09" in error:
            _record_failure(blog_id, "c09_violation", error[:200], keyword)
            return {"success": False, "reason": "c09_violation"}
        else:
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

    # CUAP 엔티티 등록 (fail-open) — 다음 발행분부터 크로스 링크 대상
    try:
        # 2026-08-07: draft 글은 링커 Entities에서 제외 (404 방지)
        # draft:true 글은 Hugo 빌드에서 제외되어 public/에 없음 → 링커가 참조하면 404
        if is_draft:
            logger.info(f"[{blog_id}] draft 글이라 CUAP 엔티티 등록 스킵: {keyword}")
        else:
            # 2026-07-26: result["url"] (hugo_writer._write_hugo_post) > result["file"] (on-disk path) > _make_slug(keyword)
            if result.get("url"):
                _actual_slug = result["url"].rstrip("/").split("/")[-1]
            elif result.get("file"):
                # result["file"] = "/path/to/content/posts/{slug}/index.md" or "/path/to/content/posts/{date}-{slug}.md"
                _file_slug = Path(result["file"]).parent.name
                # PaperMod format: file_path = posts/{date}-{slug}.md → extract from filename
                if not _file_slug or _file_slug == "posts":
                    _file_slug = Path(result["file"]).stem
                    if "-" in _file_slug:
                        _file_slug = _file_slug.split("-", 1)[1] if _file_slug.split("-", 1)[0].isdigit() else _file_slug
                _actual_slug = _file_slug
            else:
                _actual_slug = slug
            # 추천추천 중복 방지: keyword가 이미 "추천"으로 끝나면 한 번만
            _link_label = keyword.strip() if keyword.strip().endswith("추천") else f"{keyword.strip()} 추천"
            _link_label = _link_label.strip() or "추천"
            register_cuap_entity(
                entity_type="category",
                entity_name=keyword,
                blog_id=blog_id,
                post_slug=_actual_slug,
                link_label=_link_label,
                priority=50,
                published=1,
            )
            logger.info(f"[{blog_id}] CUAP 엔티티 등록: {keyword}")
    except Exception as _e:
        logger.warning(f"[{blog_id}] CUAP 엔티티 등록 실패 (fail-open): {_e}")

    # 품질 메트릭 기록
    try:
        from shared.quality_recorder import record_quality
        from shared.post_validator import validate_post_html, _readability_score, _keyword_coverage
        body_html = result.get("body_html", body_md)
        body_text = re.sub(r"<[^>]+>", "", body_html)
        body_text = re.sub(r"\s+", " ", body_text).strip()

        readability = _readability_score(body_text)

        issue_checks = {i["check"] for i in validate_post_html(body_html, blog_id).get("issues", [])}

        metrics = {
            "readability_score": readability,
            "keyword_coverage_ratio": 0,
            "content_length": len(body_md),
            "paragraph_count": body_md.count("\n\n") + 1,
            "has_cta": "cta_html" not in issue_checks and "curation_cta" not in issue_checks,
            "has_og_image": bool(thumbnail_url),
            "has_map_text": "map_text" in issue_checks,
            "min_length_pass": "min_length" not in issue_checks,
            "empty_template_count": sum(1 for i in validate_post_html(body_html, blog_id).get("issues", []) if i["check"] == "empty_template"),
        }
        record_quality(blog_id, slug, title, datetime.now().isoformat(), metrics)
    except Exception as e:
        logger.warning(f"[{blog_id}] 품질 메트릭 기록 실패: {e}")

    return {
        "success": True,
        "title": title,
        "keyword": keyword,
        "product_count": article["product_count"],
    }

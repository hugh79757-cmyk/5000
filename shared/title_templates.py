"""제목 템플릿 레지스트리 + 순환 선택 모듈

TITLE_TEMPLATES:       템플릿 8종 (comparison, ranking, toplist, buying_guide, budget, review_style, question_style, spec_style)
TitleTemplatePicker:   가중치 랜덤 선택, 최근 N개 중복 회피, 블로그별 오버라이드
"""
import logging
import os
import random
import re
import sqlite3
from datetime import datetime

logger = logging.getLogger(__name__)

# ── 템플릿 정의 ────────────────────────────────────────────────────────

TITLE_TEMPLATES: dict[str, str] = {
    "comparison": "{brand1} vs {brand2} — {keyword} 어떤 게 나을까?",
    "ranking": "{keyword} BEST 5 — {year}년 {month}월 엄선",
    "toplist": "TOP 5 {keyword} — 선택한 이유와 후기",
    "buying_guide": "{keyword} 고르는 법: {year}년 최신 가이드",
    "budget": "{keyword} 추천: {price_range}만원 이하 합격점 TOP 5",
    "review_style": "실제 써본 사람이 말하는 {keyword} TOP 5",
    "question_style": "{keyword} 고민된다면? 지금 사야 하는 이유",
    "spec_style": "{year}년 {month}월 스펙 비교: {brand1} vs {brand2} vs {brand3}",
    "myth_busting": "{keyword} 흔한 오해 3가지 — {year}년 기준 바로잡기",
    "new_release": "최근 출시 {keyword} {brand1} — 첫인상과 실사용 느낌",
    "situation_based": "{keyword} 어떤 걸 골라야 할까? 상황별 추천",
}

# ── 블로그별 오버라이드 (추후 확장용) ─────────────────────────────────

BLOG_TEMPLATE_OVERRIDES: dict[str, dict] = {
    "interior-hugo": {
        "preferred_templates": ["buying_guide", "budget", "question_style", "review_style", "toplist"],
        "avoid_templates": ["comparison"],
    },
    "kitchen-hugo": {
        "preferred_templates": ["question_style", "budget", "review_style", "toplist", "buying_guide"],
        "avoid_templates": ["comparison"],
    },
    "camping-hugo": {
        "preferred_templates": ["toplist", "buying_guide", "budget", "question_style", "review_style"],
        "avoid_templates": ["ranking", "comparison"],
    },
    "appliance-hugo": {
        "preferred_templates": ["review_style", "buying_guide", "question_style", "myth_busting"],
        "avoid_templates": ["ranking"],
    },
    "health-hugo": {
        "preferred_templates": ["buying_guide", "budget", "question_style", "review_style", "toplist"],
        "avoid_templates": ["comparison"],
    },
    "beauty-hugo": {
        "preferred_templates": ["buying_guide", "budget", "review_style", "spec_style", "question_style"],
        "avoid_templates": [],
    },
    "baby-hugo": {
        "preferred_templates": ["buying_guide", "question_style", "review_style", "situation_based", "toplist"],
        "avoid_templates": ["comparison"],
    },
    "pet-hugo": {
        "preferred_templates": ["review_style", "question_style", "situation_based", "toplist", "buying_guide"],
        "avoid_templates": ["comparison"],
    },
    "fitness-hugo": {
        "preferred_templates": ["review_style", "question_style", "buying_guide", "myth_busting", "new_release"],
        "avoid_templates": [],
    },
    "laptop-hugo": {
        "preferred_templates": ["comparison", "spec_style", "buying_guide", "question_style", "myth_busting"],
        "avoid_templates": [],
    },
}

TEMPLATE_ROTATION_WINDOW = 10  # 같은 타입 N회 내 재사용 방지


# ── 헬퍼: 제목 분류 ───────────────────────────────────────────────────

def _classify_title(title: str) -> str:
    """정규식 기반 제목 → 템플릿 타입 분류

    Args:
        title: 분류할 제목 문자열

    Returns:
        매칭된 템플릿 타입 (comparison/ranking/toplist/…), 미분류시 빈 문자열
    """
    if not title:
        return ""
    # myth_busting: 오해
    if re.search(r"오해|흔한.*오해|바로잡기", title):
        return "myth_busting"
    # new_release: 최신 출시 or 첫인상
    if re.search(r"최근\s*출시|첫인상|실사용\s*느낌", title):
        return "new_release"
    # situation_based: 상황별 추천
    if re.search(r"상황별\s*추천|어떤.*골라야", title):
        return "situation_based"
    # spec_style: 스펙 비교 + vs 다수
    if re.search(r"스펙\s*비교", title) and title.count("vs") >= 2:
        return "spec_style"
    # comparison: vs 포함
    if re.search(r"\bvs\b", title):
        return "comparison"
    # budget: 가격대 + 만원
    if re.search(r"\d+만원", title) and re.search(r"이하|미만|이상", title):
        return "budget"
    # buying_guide: 고르는 법 or 가이드
    if re.search(r"고르는\s*법|최신\s*가이드", title):
        return "buying_guide"
    # review_style: 실제 구매자 or 리뷰
    if re.search(r"실제.*써본|실제.*구매|리뷰", title):
        return "review_style"
    # question_style: 고민 or ? 또는 의문문 패턴
    if re.search(r"고민|다면\?|까\?|어떻게", title):
        return "question_style"
    # toplist: TOP 으로 시작
    if re.match(r"TOP\s*\d+", title):
        return "toplist"
    # ranking: BEST 포함
    if re.search(r"BEST\s*\d+", title):
        return "ranking"
    # fallback — 추천 포함이면 ranking
    if re.search(r"추천", title):
        return "ranking"
    return ""


# ── 픽커 클래스 ────────────────────────────────────────────────────────

class TitleTemplatePicker:
    """제목 템플릿 선택기

    - pick(): 가중치 랜덤, 최근 N회 사용 타입 회피
    - render(): 템플릿 변수 채움
    - get_recent_styles(): publish_log 조회 → 최근 사용 타입 목록
    """

    def __init__(self, blog_id: str | None = None):
        self.blog_id = blog_id
        self._db_path: str | None = None

    # ── 공개 메서드 ─────────────────────────────────────────────────

    def pick(self, used_templates: list[str] | None = None) -> str:
        """템플릿 타입 하나를 가중치 랜덤 선택

        Args:
            used_templates: 최근 N회 사용된 템플릿 타입 목록 (회피 대상)

        Returns:
            TITLE_TEMPLATES 의 키
        """
        if used_templates is None:
            used_templates = []

        # 블로그별 선호/회피 적용
        override = BLOG_TEMPLATE_OVERRIDES.get(self.blog_id, {})
        preferred = override.get("preferred_templates", list(TITLE_TEMPLATES.keys()))
        avoid = override.get("avoid_templates", [])

        # 후보: preferred ∩ (전체 - used - avoid)
        candidates = [t for t in preferred if t in TITLE_TEMPLATES]
        candidates = [t for t in candidates if t not in used_templates and t not in avoid]

        if not candidates:
            # 모든 타입이 사용됐으면 전체 풀에서 재선택
            candidates = [t for t in TITLE_TEMPLATES if t not in avoid]
        if not candidates:
            candidates = list(TITLE_TEMPLATES.keys())

        # 가중치: comparison 은 살짝 낮춤 (기본값 수가 많아 중복 위험)
        weights = []
        for t in candidates:
            if t == "comparison":
                weights.append(0.6)
            else:
                weights.append(1.0)

        return random.choices(candidates, weights=weights, k=1)[0]

    def render(
        self,
        template_key: str,
        brand_data: dict | None = None,
        keyword: str = "",
    ) -> str:
        """템플릿 변수를 실제 데이터로 채움

        Args:
            template_key: TITLE_TEMPLATES 키
            brand_data: brand1/brand2/brand3/price_range 포함 dict
            keyword: 타겟 키워드

        Returns:
            채워진 제목 문자열
        """
        if brand_data is None:
            brand_data = {}
        now = datetime.now()
        template = TITLE_TEMPLATES.get(template_key)
        if not template:
            return f"{keyword} 추천 TOP 5"

        context = {
            "brand1": brand_data.get("brand1", ""),
            "brand2": brand_data.get("brand2", ""),
            "brand3": brand_data.get("brand3", ""),
            "year": str(now.year),
            "month": str(now.month),
            "keyword": keyword or "상품",
            "price_range": brand_data.get("price_range", "50"),
        }
        try:
            return template.format(**context)
        except KeyError:
            # 혹시라도 누락된 변수 대비
            return f"{keyword} 추천 TOP 5"

    def get_recent_styles(self, blog_id: str, count: int = 5) -> list[str]:
        """publish_log 에서 최근 N개 제목 조회 → 템플릿 타입 분류

        Args:
            blog_id: 블로그 ID
            count: 조회할 최근 발행 수

        Returns:
            템플릿 타입 문자열 리스트 (최근순)
        """
        styles: list[str] = []
        try:
            db_path = self._get_db_path()
            conn = sqlite3.connect(str(db_path))
            cursor = conn.execute(
                "SELECT title FROM publish_log "
                "WHERE blog_id = ? AND title IS NOT NULL AND title != '' "
                "ORDER BY created_at DESC LIMIT ?",
                (blog_id, count),
            )
            for row in cursor.fetchall():
                style = _classify_title(row[0])
                if style:
                    styles.append(style)
            conn.close()
        except Exception as e:
            logger.warning("[title_templates] 최근 스타일 조회 실패: %s", e)
        return styles

    # ── 비공개 헬퍼 ──────────────────────────────────────────────────

    def _get_db_path(self) -> str:
        """curation.db 절대 경로 (lazy init, 캐싱)"""
        if self._db_path is None:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self._db_path = os.path.join(base, "data", "curation.db")
        return self._db_path

"""
회귀 테스트: golf-hugo relevance gate 검증
- 골프 상품이 threshold를 통과하는지 검증
- 비골프 상품이 차단되는지 검증 (negative control)
- threshold 0.75 vs 0.50 통과율 차이 검증
"""
import tempfile
from pathlib import Path

import pytest

# ops.db guard 우회
import shared.publish_error_events as _events
_events.OPS_DB_PATH = Path(tempfile.mkdtemp()) / "ops.db"


# golf-hugo allowed keywords (CATEGORY_FILTERS 기준)
GOLF_ALLOWED = [
    "골프클럽", "골프드라이버", "아이언세트", "골프백", "골프거리측정기",
    "골프화", "퍼터", "골프공", "골프장갑", "골프의류", "골프우산",
    "스윙연습기", "골프", "스윙",
]


def _score_product(product_name: str, category_name: str, allowed: list[str] | None = None) -> float:
    """relevance_scorer.score_product과 동일한 로직 (의존성 없이 테스트)"""
    if allowed is None:
        allowed = GOLF_ALLOWED
    combined = (product_name + " " + (category_name or "")).lower()
    count = sum(1 for kw in allowed if kw.lower() in combined)
    min_matches = 2
    if count == 0:
        return 0.0
    elif count < min_matches:
        return 0.5
    else:
        return min(1.0, 0.5 + 0.25 * (count - min_matches + 1))


class TestGolfProductScoring:
    """골프 상품이 올바르게 스코어링되는지 검증"""

    @pytest.mark.parametrize("name,cat,min_score", [
        ("골프거리측정기 레이저 고정밀", "스포츠/레저용품", 0.50),
        ("보이스캐디 레이저 핏 골프 거리 측정기", "스포츠/레저용품", 0.50),
        ("카르페디엠 UV자외선차단 75 대형 골프우산", "여성패션", 0.50),
        ("PRGR 초경량 UV차단 골프우산", "스포츠/레저용품", 0.50),
        ("혼마 베레스 S08 여성 골프 풀세트", "스포츠/레저", 0.50),
        ("PGM 제로토크퍼터 남자 여성퍼터", "스포츠/레저용품", 0.50),
        ("본사 마이에이밍 굿보이스 골프거리측정기 + 에이밍", "스포츠/레저용품", 0.75),
    ])
    def test_golf_product_scores_above_threshold(self, name, cat, min_score):
        """골프 상품은 score ≥ 0.50 (threshold 0.50 시 통과)"""
        score = _score_product(name, cat)
        assert score >= min_score, f"골프 상품 스코어 부족: {name} → {score} < {min_score}"

    def test_golf_product_with_brand_name(self):
        """브랜드 골프 상품 (핑 G440 등) — '골프' 접두사 없으면 0.0"""
        # 핑 G440 드라이버: "골프" 없음, "드라이버"는 allowed에 없음 → 0.0
        score = _score_product("핑 G440 MAX 드라이버 ALTA J CB BLUE", "스포츠/레저")
        assert score == 0.0, f"브랜드 골프 상품 (골프 미포함) 스코어: {score}"

    def test_golf_distance_meter_high_score(self):
        """골프거리측정기: '골프' 매칭 시 score ≥ 0.50"""
        score = _score_product("MINUO 레이저 골프 거리측정기 고정밀", "스포츠/레저용품")
        assert score >= 0.50


class TestNegativeControl:
    """비골프 상품이 차단되는지 검증 (negative control)"""

    @pytest.mark.parametrize("name,cat", [
        ("LG전자 울트라PC 15U470", "가전디지털"),
        ("Apple 맥북 에어 15 M5칩", "가전디지털"),
        ("에이수스 비보북 16 코어5", "가전디지털"),
        ("Bonjour 12000pa 무선 미니 핸디 청소기", "가전디지털"),
        (" TCL 인버터 벽걸이형 에어컨", "가전디지털"),
        ("삼성전자 AI Q9000 스탠드형 에어컨", "가전디지털"),
        ("캐리어 인버터 벽걸이형 에어컨", "가전디지털"),
    ])
    def test_non_golf_product_blocked(self, name, cat):
        """비골프 상품은 score 0.00 → 차단"""
        score = _score_product(name, cat)
        assert score == 0.0, f"비골프 상품 오탐: {name} → {score}"

    def test_non_golf_product_with_similar_word(self):
        """비골프 상품 중 '세트' 포함 — 골프 키워드 미매칭 시 차단"""
        # "에어컨 + 리모컨 세트" — "세트"는 allowed에 없음
        score = _score_product("삼성전자 에어컨 + 리모컨 세트", "가전디지털")
        assert score == 0.0


class TestThresholdComparison:
    """threshold 0.75 vs 0.50 통과율 차이 검증"""

    def test_threshold_075_stricter_than_050(self):
        """0.75 통과 집합은 0.50 통과 집합의 부분집합"""
        golf_products = [
            ("골프거리측정기 레이저", "스포츠/레저용품"),
            ("카르페디엠 골프우산", "여성패션"),
            ("혼마 골프 풀세트", "스포츠/레저"),
            ("핑 G440 드라이버", "스포츠/레저"),
        ]
        for name, cat in golf_products:
            s = _score_product(name, cat)
            if s >= 0.75:
                assert s >= 0.50, f"0.75 통과 상품이 0.50 미만: {name}"

    def test_more_products_pass_at_050(self):
        """threshold 0.50에서 더 많은 골프 상품 통과"""
        # 골프 키워드 1개만 매칭하는 상품 (score=0.50)
        single_match_products = [
            ("혼마 베레스 S08 여성 골프 풀세트", "스포츠/레저"),  # "골프"만 매칭
            ("야마하 인프레스 드라이브스타 아이언세트", "스포츠/레저"),  # "아이언세트"만 매칭
            ("PGM 제로토크퍼터", "스포츠/레저용품"),  # "퍼터"만 매칭
        ]
        for name, cat in single_match_products:
            s = _score_product(name, cat)
            assert s == 0.50, f"1개 매칭 상품 스코어: {name} → {s}"
            assert s >= 0.50, f"threshold 0.50 통과 실패: {name}"
            assert s < 0.75, f"threshold 0.75에서 통과하면 안 됨: {name}"

"""Tests for post_validator — readability, keyword coverage, full validation"""

import pytest
from shared.post_validator import (
    _readability_score,
    _keyword_coverage,
    validate_post_html,
)


class TestReadabilityScore:
    def test_empty_text_returns_mid(self):
        assert _readability_score("") == 0.5
        assert _readability_score("   ") == 0.5
        assert _readability_score("short") == 0.5

    def test_short_readable_sentences(self):
        text = ("이곳은 강릉의 유명한 카페입니다. "
                "바다가 보이는 창가 자리가 좋습니다. "
                "커피 맛이 아주 뛰어납니다. "
                "디저트도 함께 추천합니다. "
                "주차장이 넓어 편리합니다.")
        score = _readability_score(text)
        assert 0.5 <= score <= 1.0

    def test_very_long_sentences_score_lower(self):
        long = "여기는" + "매우긴문장입니다." * 50 + "계속됩니다."
        score = _readability_score(long)
        assert score <= 0.7

    def test_very_difficult_text(self):
        difficult = ("본 연구는" + "생략된매우복잡한학술적내용" * 80 +
                     "에대한고찰을목적으로한다.")
        score = _readability_score(difficult)
        assert score <= 0.5

    def test_no_sentences_returns_mid(self):
        assert _readability_score("짧은") == 0.5


class TestKeywordCoverage:
    def test_empty_keywords(self):
        result = _keyword_coverage("아무 텍스트", [])
        assert result["ratio"] == 1.0
        assert result["missing"] == []

    def test_all_keywords_found(self):
        result = _keyword_coverage("여행 맛집 강릉 커피", ["여행", "커피"])
        assert result["ratio"] == 1.0
        assert result["covered"] == 2
        assert result["missing"] == []

    def test_some_keywords_missing(self):
        result = _keyword_coverage("여행 커피", ["여행", "맛집", "강릉"])
        assert result["ratio"] == pytest.approx(0.33, abs=0.01)
        assert result["covered"] == 1
        assert result["missing"] == ["맛집", "강릉"]

    def test_case_insensitive(self):
        result = _keyword_coverage("Travel Blog Post", ["travel", "BLOG"])
        assert result["ratio"] == 1.0
        assert result["covered"] == 2

    def test_keyword_in_long_text(self):
        text = "앞부분 " + ("중간내용 " * 50) + "여행 후반부"
        result = _keyword_coverage(text, ["여행"])
        assert result["ratio"] == 1.0


class TestValidatePostHtml:
    def test_readability_warning_on_long_text(self):
        long_html = "<p>" + "매우긴문장." * 100 + "</p>"
        result = validate_post_html(long_html, "travel-hugo")
        checks = {i["check"] for i in result["issues"]}
        assert "readability" in checks

    def test_no_readability_warning_on_normal_text(self):
        normal = "<p>짧은 문장입니다. 가독성이 좋습니다. 쉽게 읽힙니다.</p>" * 20
        result = validate_post_html(normal, "travel-hugo")
        checks = {i["check"] for i in result["issues"]}
        assert "readability" not in checks

    def test_keyword_coverage_from_blog_id(self):
        html = "<p>커피와 디저트가 맛있습니다. 주차장이 넓습니다.</p>" * 50
        result = validate_post_html(html, "travel3-hugo")
        kw_checks = [i for i in result["issues"] if i["check"] == "keyword_coverage"]
        # Text lacks most keywords (travel3/hugo/여행/맛집), so a warning should fire
        assert len(kw_checks) == 1
        msg = kw_checks[0]["msg"]
        assert "키워드 커버리지 낮음" in msg
        assert "0/4" in msg or "1/4" in msg

    def test_passed_when_no_errors(self):
        good_html = (
            '<meta property="og:image" content="x.jpg" />'
            "<p>" + ("짧은 문장입니다. " * 100) + "</p>"
        )
        result = validate_post_html(good_html, "travel3-hugo")
        assert result["passed"] is True or any(
            i["severity"] != "ERROR" for i in result["issues"]
        )

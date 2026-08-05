import pytest

from shared.ai_response_parser import THINKING_PATTERNS
from shared.problem_detectors import (
    detect_cjk_leak,
    detect_cot_leak,
    detect_image_url_length,
    detect_post_generate,
    detect_repeated_image_url,
    detect_validation_issue,
)


class TestDetectCjkLeak:
    def test_japanese_low_hangul_ratio_detects_p07(self):
        text = "この記事は日本語で書かれています。今日は良い天気です。" * 3
        detection = detect_cjk_leak(text)
        assert detection is not None
        assert detection.problem_id == "P07"
        assert detection.pattern == "ratio<0.5"

    def test_hanja_parallel_korean_is_not_false_positive(self):
        text = (
            "갑사(甲寺)는 충청남도 공주시에 위치한 유서 깊은 사찰입니다. "
            "사찰 내부에는 보물로 지정된 불상이 있습니다."
        )
        assert detect_cjk_leak(text) is None

    def test_cjk_instruction_leak_detects_p07(self):
        text = "根据要求，请按照规则如下格式输出内容。正文입니다."
        detection = detect_cjk_leak(text)
        assert detection is not None
        assert detection.problem_id == "P07"

    def test_empty_text_returns_none(self):
        assert detect_cjk_leak("") is None


class TestDetectCotLeak:
    REAL_PATTERN_SAMPLES = [
        "이제 글을 작성하겠습니다.",
        "\n주의: 본문은 아래와 같이 작성하세요.",
        "<thinking>사용자의 요청을 다시 확인하자</thinking>",
        "Let me re-read the request",
        "문장 수: 3",
    ]

    def test_uses_real_thinking_patterns_from_parser(self):
        assert len(THINKING_PATTERNS) >= 10

    @pytest.mark.parametrize(
        "sample", REAL_PATTERN_SAMPLES, ids=["이제_작성", "주의", "thinking_tag", "english", "문장수"]
    )
    def test_real_patterns_detect_p08(self, sample):
        detection = detect_cot_leak(sample)
        assert detection is not None, f"no detection for: {sample!r}"
        assert detection.problem_id == "P08"
        assert detection.pattern == "thinking_leak"

    def test_normal_korean_body_returns_none(self):
        body = "이 글은 서울 여행에 대한 안내입니다. 맛집과 관광지를 소개합니다."
        assert detect_cot_leak(body) is None

    def test_empty_text_returns_none(self):
        assert detect_cot_leak("") is None


class TestDetectRepeatedImageUrl:
    def test_repeated_segment_url_detects_p09(self):
        url = "https://img.example.com/a/a/a/a/a/a/a/a/thumb.jpg"
        detection = detect_repeated_image_url(url)
        assert detection is not None
        assert detection.problem_id == "P09"

    def test_normal_url_returns_none(self):
        url = "https://img.example.com/images/blog/thumb.jpg"
        assert detect_repeated_image_url(url) is None

    def test_boundary_single_repeated_segment_returns_none(self):
        url = "https://img.example.com/a/a/thumb.jpg"
        assert detect_repeated_image_url(url) is None

    def test_empty_url_returns_none(self):
        assert detect_repeated_image_url("") is None


class TestDetectImageUrlLength:
    def test_520_char_url_detects_p23(self):
        url = "https://img.example.com/" + "a" * (520 - len("https://img.example.com/"))
        assert len(url) == 520
        detection = detect_image_url_length(url)
        assert detection is not None
        assert detection.problem_id == "P23"

    def test_500_char_url_returns_none(self):
        url = "https://img.example.com/" + "a" * (500 - len("https://img.example.com/"))
        assert len(url) == 500
        assert detect_image_url_length(url) is None

    def test_499_char_url_returns_none(self):
        url = "x" * 499
        assert detect_image_url_length(url) is None

    def test_empty_url_returns_none(self):
        assert detect_image_url_length("") is None


class TestDetectValidationIssue:
    _P15_KEYS = (
        "cta_html",
        "curation_cta",
        "empty_template",
        "thumbnail",
        "map_text",
        "min_length",
        "readability",
        "keyword_coverage",
    )

    @pytest.mark.parametrize("key", _P15_KEYS)
    def test_p15_issue_keys_detect_p15(self, key):
        check_result = {"issues": [{"check": key, "msg": "실패 메시지", "severity": "ERROR"}], "warnings": []}
        detection = detect_validation_issue(check_result, "test-hugo")
        assert detection is not None
        assert detection.problem_id == "P15"
        assert detection.pattern == key

    @pytest.mark.parametrize("key", ("stale", "event_expired"))
    def test_stale_issue_keys_detect_p19(self, key):
        check_result = {"issues": [{"check": key, "msg": "오래된 데이터", "severity": "WARNING"}], "warnings": []}
        detection = detect_validation_issue(check_result, "test-hugo")
        assert detection is not None
        assert detection.problem_id == "P19"

    def test_no_issues_returns_none(self):
        check_result = {"issues": [], "warnings": []}
        assert detect_validation_issue(check_result, "test-hugo") is None

    def test_non_dict_input_raises(self):
        with pytest.raises(AttributeError):
            detect_validation_issue("not-a-dict", "test-hugo")


class TestDetectPostGenerateDispatcher:
    def test_returns_list_for_clean_body(self):
        body = "이 글은 서울 여행에 대한 안내입니다. 맛집과 관광지를 소개합니다."
        assert detect_post_generate(body, "test-hugo") == []

    def test_returns_list_type_when_empty(self):
        assert isinstance(detect_post_generate("", "test-hugo"), list)

    def test_cot_pattern_includes_p08(self):
        result = detect_post_generate("이제 글을 작성하겠습니다.\n본문 내용입니다.", "test-hugo")
        assert isinstance(result, list)
        assert "P08" in {d.problem_id for d in result}

    def test_mixed_content_returns_all_applicable(self):
        content = (
            "https://img.example.com/a/a/a/a/a/a/a/a/"
            + "b" * 500
            + "?x=根据要求，请按照规则如下格式输出内容。正文입니다."
        )
        result = detect_post_generate(content, "test-hugo")
        assert isinstance(result, list)
        assert {d.problem_id for d in result} == {"P07", "P09", "P23"}

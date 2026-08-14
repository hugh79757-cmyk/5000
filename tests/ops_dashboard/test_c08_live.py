"""Wave 3 (SC-2) — C08 라이브 대조 단위 테스트 (오프라인 검증).

라이브 HTTP 크롤은 샌드박스에서 불가하므로, (a)(b)(c)(d) 위반 판정 로직과
사이트 미존재 경로를 오프라인으로 검증한다. 실제 크롤 경로는 배포 후 라이브에서 동작.
"""

from ops_dashboard.checks.content_integrity import (  # noqa: E402
    _check_c08,
    _compare_live_vs_local,
)


GOOD_HTML = """
<html><head>
<title>서울 맛집 TOP5</title>
<meta property="og:title" content="서울 맛집 TOP5">
<meta name="description" content="서울 추천 맛집">
<meta property="og:image" content="https://pub-x.r2.dev/img/thumb.webp">
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js"></script>
</head><body>
<h1>서울 맛집 TOP5</h1>
<p>서울 추천 맛집 소개</p>
<h2>1. 을지로 돈까스</h2>
<p>맛있음</p>
</body></html>
"""

TITLE_MISMATCH_HTML = GOOD_HTML.replace(
    "서울 맛집 TOP5", "부산 해변 명소"
)

NO_AD_HTML = GOOD_HTML.replace(
    "https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js", ""
)

COT_LEAK_HTML = GOOD_HTML.replace(
    "</h2>", "</h2>\n<p>생각해보자, 이 코스는 다음과 같다.</p>"
)


def test_compare_clean_html_has_no_violations():
    probs = _compare_live_vs_local(
        {"title": "서울 맛집 TOP5", "og_image": "https://pub-x.r2.dev/img/thumb.webp"},
        GOOD_HTML,
    )
    assert probs == [], f"깨끗한 HTML은 위반 없음: {probs}"


def test_compare_title_mismatch_detected():
    probs = _compare_live_vs_local(
        {"title": "서울 맛집 TOP5", "og_image": "https://pub-x.r2.dev/img/thumb.webp"},
        TITLE_MISMATCH_HTML,
    )
    assert "C08_TITLE_MISMATCH" in probs, probs


def test_compare_ad_not_rendered_detected():
    probs = _compare_live_vs_local(
        {"title": "서울 맛집 TOP5", "og_image": "https://pub-x.r2.dev/img/thumb.webp"},
        NO_AD_HTML,
    )
    assert "C08_AD_NOT_RENDERED" in probs, probs


def test_compare_cot_leak_detected():
    probs = _compare_live_vs_local(
        {"title": "서울 맛집 TOP5", "og_image": "https://pub-x.r2.dev/img/thumb.webp"},
        COT_LEAK_HTML,
    )
    assert "C08_COT_LEAK" in probs, probs


def test_check_c08_no_site_returns_error_not_pass():
    ok, detail = _check_c08(None, "fixture-blog")
    assert ok is False, "site 없음은 통과가 아닌 명시적 에러"
    assert "C08_" in detail, f"detail 에 problem_id 형태 포함: {detail}"

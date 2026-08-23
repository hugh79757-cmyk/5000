"""2026-08-20 검사기 교정 패치 회귀 테스트 (독립 fixture).

사용자 m0128 요청 ②③: c08 / FM-MISSINGKEYS / CQ03-CQ05 / c01 / c06
최소 패치 각각에 대한 독립 회귀 fixture. 오프라인 검증 (라이브 크롤 없음).
"""
from pathlib import Path

import pytest

# conftest autouse guard: 운영 ops.db 접근 차단. 순수 함수 테스트이므로
# events.OPS_DB_PATH 를 tmp 경로로 override 하여 통과시킨다.
@pytest.fixture(autouse=True)
def _guard_prod_ops_db(monkeypatch, tmp_path):
    from shared import publish_error_events as events

    monkeypatch.setattr(events, "OPS_DB_PATH", tmp_path / "ops_test.db")
    yield

from ops_dashboard.checks.content_integrity import (  # noqa: E402
    C06_GRACE_HOURS,
    _check_c01,
    _check_c06,
    _compare_live_vs_local,
    _parse_frontmatter,
)
from ops_dashboard.checks.content_quality import _analyze  # noqa: E402


# ---------- 1) _parse_frontmatter: title 내 콜론 잘림 (c08 FP 근본) ----------

def test_parse_frontmatter_colon_title():
    """title 값에 콜론이 포함되면 첫 콜론 split으로 잘리던 버그."""
    content = (
        "---\n"
        "title: 'Brazil Passport: Visa Requirements…'\n"
        "slug: brazil-visa-free\n"
        "date: '2026-04-13T18:20:33+09:00'\n"
        "draft: false\n"
        "---\n"
        "본문\n"
    )
    _, fm = _parse_frontmatter(content)
    assert fm["title"] == "Brazil Passport: Visa Requirements…"
    assert fm["slug"] == "brazil-visa-free"


def test_parse_frontmatter_multiline_description():
    """multiline description(YAML plain scalar)이 이어붙여져야 한다."""
    content = (
        "---\n"
        "title: 포스트\n"
        "description: 첫 줄,\n"
        "  두 번째 줄\n"
        "slug: post\n"
        "---\n"
    )
    _, fm = _parse_frontmatter(content)
    assert "첫 줄" in fm["description"]
    assert "두 번째 줄" in fm["description"]


def test_parse_frontmatter_bool_normalized():
    """draft: false → 'false' 문자열 (기존 호출부 .strip() 호환)."""
    content = "---\ntitle: t\ndraft: false\n---\n"
    _, fm = _parse_frontmatter(content)
    assert fm["draft"] == "false"


# ---------- 2) c01: 자연어 필드 제외 (47건 FP 해소) ----------

def test_c01_natural_lang_fields_exempt():
    """title/description 내 곡선따옴표는 자연어 — 통과."""
    fm = {
        "title": "Island of the Gods: 발리 여행",
        "description": "사용자가 '그립스와니'를 좋아합니다.",
        "slug": "bali-guide",
    }
    passed, _ = _check_c01(fm)
    assert passed is True


def test_c01_machine_field_flagged():
    """기계 필드(slug) 곡선따옴표는 여전히 위반."""
    fm = {"slug": "bali\u2019s-guide"}
    passed, detail = _check_c01(fm)
    assert passed is False
    assert "slug" in detail


# ---------- 3) c08: <title> suffix 오탐 + 404 오인 방지 ----------

def test_c08_title_suffix_only_is_ok():
    """og:title 부재 시 <title> 이 local prefix + 사이트 suffix → 정상."""
    fm = {"title": "서울 맛집 TOP5", "featureimage": "https://pub-x.r2.dev/a.webp"}
    live = (
        "<html><head><title>서울 맛집 TOP5 &#183; 추천 가이드</title>"
        '<meta property="og:image" content="https://pub-x.r2.dev/a.webp">'
        "</head><body><h1>서울 맛집 TOP5</h1></body></html>"
    )
    probs = _compare_live_vs_local(fm, live)
    assert "C08_TITLE_MISMATCH" not in probs


def test_c08_title_real_mismatch_still_fails():
    """실제 제목 불일치(og:title 존재, 값 다름)는 여전히 위반."""
    fm = {"title": "서울 맛집 TOP5"}
    live = (
        "<html><head>"
        '<meta property="og:title" content="부산 해변 명소">'
        "</head><body><h1>부산 해변 명소</h1></body></html>"
    )
    probs = _compare_live_vs_local(fm, live)
    assert "C08_TITLE_MISMATCH" in probs


# ---------- 4) c06: grace-window PENDING ----------

def test_c06_grace_pending(monkeypatch, tmp_path):
    """grace 내 + live 증거 없음 → PENDING(False, C06_PENDING)."""
    f = tmp_path / "posts" / "recent-post" / "index.md"
    f.parent.mkdir(parents=True)
    f.write_text("---\ntitle: t\n---\n")
    monkeypatch.setattr("ops_dashboard.checks.content_integrity._live_post_ok",
                        lambda domain, slug: False)
    passed, detail = _check_c06(f, "test-hugo", "example.com")
    assert passed is False
    assert "C06_PENDING" in detail


def test_c06_grace_expired_fails(monkeypatch, tmp_path):
    """grace 초과 + live 증거 없음 → FAIL (기존 TP 비은닉)."""
    import os
    import time

    f = tmp_path / "posts" / "old-post" / "index.md"
    f.parent.mkdir(parents=True)
    f.write_text("---\ntitle: t\n---\n")
    old = (C06_GRACE_HOURS + 1) * 3600
    now = time.time()
    os.utime(f, (now - old, now - old))
    monkeypatch.setattr("ops_dashboard.checks.content_integrity._live_post_ok",
                        lambda domain, slug: False)
    passed, detail = _check_c06(f, "test-hugo", "example.com")
    assert passed is False
    assert "C06_PENDING" not in detail


def test_c06_live_evidence_passes(monkeypatch, tmp_path):
    """live 증거(200+본문) 있으면 grace 내라도 통과."""
    f = tmp_path / "posts" / "live-post" / "index.md"
    f.parent.mkdir(parents=True)
    f.write_text("---\ntitle: t\n---\n")
    monkeypatch.setattr("ops_dashboard.checks.content_integrity._live_post_ok",
                        lambda domain, slug: True)
    passed, detail = _check_c06(f, "test-hugo", "example.com")
    assert passed is True
    assert "live 반영" in detail


# ---------- 5) CQ: STAP 비제휴 블로그 skip_product_rules ----------

def test_cq_skip_product_rules_stap():
    """skip_product_rules=True → CQ03(제휴문구)/CQ05(상품이미지) 미발화."""
    html = "<html><body><h1>금융 분석</h1><p>배당 수익률 5%</p></body></html>"
    issues = _analyze(html, skip_product_rules=True)
    assert not any("CQ03" in i for i in issues)
    assert not any("CQ05" in i for i in issues)


def test_cq_product_rules_still_fire_without_skip():
    """skip 없으면 CQ03(제휴문구 누락) 발화 유지."""
    html = "<html><body><h1>상품 비교</h1><p>내용</p></body></html>"
    issues = _analyze(html, skip_product_rules=False)
    assert any("CQ03" in i for i in issues)
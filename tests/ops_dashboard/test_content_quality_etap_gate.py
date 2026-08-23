"""Tests for content_quality ETAP 게이트 (2026-08-16).

cuap 상품 전제 룰(CQ02~08)이 상품 없는 영문 브랜드(ETAP)에 오탐을 만든다:
CQ03은 "쿠팡 파트너스" 0회라 모든 영문 글을 fail로 만든다.
→ _analyze(skip_product_rules=True)로 CQ02~08 생략, CQ01(빈 불릿)만 유지.
"""
import pytest

from ops_dashboard.checks.content_quality import _analyze, DISCLOSURE

# ETAP 스타일 샘플: 영문 정보성 가이드, 상품 없음, r2.dev 이미지 보유
ETAP_HTML = """<html><body>
<h1>Abruzzo Airport (PSR) Guide</h1>
<p>How to get from Pescara airport to the city center.</p>
<p><img src="https://pub-2f5c7af1c303419a933069212bc25874.r2.dev/etap/x/body_1.jpg"></p>
<h2>Overview</h2><p>Short paragraph about the airport.</p>
</body></html>"""

# ETAP 샘플 + 완전 빈 <li> (CQ01은 게이트 후에도 유지되어야 함)
ETAP_HTML_EMPTY_LI = """<html><body>
<h1>Abruzzo Airport (PSR) Guide</h1>
<ul><li></li></ul>
<p><img src="https://pub-2f5c7af1c303419a933069212bc25874.r2.dev/etap/x/body_1.jpg"></p>
</body></html>"""

# cuap 스타일 샘플: '상품별 상세 비교'가 h2가 아님(strong), 상품 h3 2개, 설명 문단 소실, CQ03 1회
CUAP_HTML = f"""<html><body>
<h1>테스트 상품 추천</h1>
<p><strong>상품별 상세 비교</strong></p>
<p>{DISCLOSURE}</p>
<h3>상품 A</h3>
<p><img src="https://ads-partners.coupang.com/image1.jpg"></p>
<h3>상품 B</h3>
<p><img src="https://ads-partners.coupang.com/image2.jpg"></p>
</body></html>"""

# CQ03 과다(3회) 샘플
CUAP_HTML_DISCLOSURE_3 = f"""<html><body>
<h1>테스트</h1>
<p>{DISCLOSURE}</p><p>{DISCLOSURE}</p><p>{DISCLOSURE}</p>
</body></html>"""


class TestEtapGate:
    def test_etap_skip_product_rules_no_cq03_false_positive(self):
        # 게이트 없이(기본) ETAP 글 → CQ03 오탐 1건
        issues_before = _analyze(ETAP_HTML)
        assert any("[CQ03]" in i for i in issues_before)
        # 게이트 적용 → 상품 전제 룰 0건
        issues = _analyze(ETAP_HTML, skip_product_rules=True)
        assert issues == []

    def test_etap_cq01_kept_after_gate(self):
        issues = _analyze(ETAP_HTML_EMPTY_LI, skip_product_rules=True)
        assert issues == ["[CQ01] 빈 리스트 항목"]


class TestCuapRegression:
    """cuap 샘플은 skip_product_rules=False(기본값)에서 기존 룰 그대로 동작."""

    def test_cq04_cq07_triggered_as_before(self):
        issues = _analyze(CUAP_HTML)
        assert any("[CQ04]" in i for i in issues)          # 상품별 상세 비교 h2 아님
        assert any("[CQ07]" in i for i in issues)          # 상품 설명 문단 소실
        assert "[CQ03]" not in " ".join(issues)            # 제휴문구 1회 → pass

    def test_cq03_over_count_unchanged(self):
        issues = _analyze(CUAP_HTML_DISCLOSURE_3)
        assert any("[CQ03] 제휴문구 과다(3회)" == i for i in issues)

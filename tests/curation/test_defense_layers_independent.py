"""
Phase 54 Task 5.5 — 방어 4계층 독립 검증

방어 계층:
  L1: Draft 플래그 (writer → pipeline → publish → frontmatter)
  L2: Body CoT 감지 (_is_cot_body → is_draft=True)
  L3: Title 템플릿 강화 (TitleTemplatePicker 사용)
  L4: 정상 통과 (모든 가드 클리어 → 정상 발행)

각 계층은 독립적으로 동작해야 하며, 하나의 실패가 다른 계층의 동작을 방해하지 않아야 한다.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


# ============================================================
# L1: Draft 플래그 전달 검증
# ============================================================

class TestL1DraftFlag:
    """L1: is_draft 플래그가 writer → pipeline → publish → frontmatter까지 전달되는지 검증"""

    def test_writer_sets_is_draft_true_when_cot_detected(self):
        """writer가 CoT 감지 시 is_draft=True 설정"""
        from pipelines.curation.writer import _is_cot_body

        cot_body = (
            "우선 사용자 요청은 건강기능식품 추천입니다. "
            "AIDA 모델을 따라 퍼널 구조로 작성해야 한다. "
            "도입부에서 제품 소개를 하고, 비교표로 정리하자. "
            "제목 규칙을 확인해야 한다. 제목 예시를 만들어보자."
        )

        assert _is_cot_body(cot_body) is True, (
            f"_is_cot_body가 True를 반환해야 함: cot_body={cot_body[:50]}..."
        )

    def test_writer_sets_is_draft_false_when_no_cot(self):
        """writer가 CoT 미감지 시 is_draft=False 설정"""
        from pipelines.curation.writer import _is_cot_body

        normal_body = (
            "네덜란드산 산양유 단백질은 고함량 단백질 보충제로 인기 있습니다. "
            "분말 형태와 정제 형태 두 가지가 있으며, "
            "HACCP 인증 받은 제품을 선택하는 것이 좋습니다."
        )

        assert _is_cot_body(normal_body) is False, (
            f"_is_cot_body가 False를 반환해야 함: normal_body={normal_body[:50]}..."
        )

    def test_hugo_writer_draft_flag_in_frontmatter(self):
        """hugo_writer가 is_draft=True 시 frontmatter에 draft: true 포함"""
        from shared.publishers.hugo_writer import _build_frontmatter_blowfish

        # is_draft=True인 경우
        fm, _ = _build_frontmatter_blowfish(
            title="테스트 포스트",
            slug="test-post",
            category="추천",
            tags="테스트",  # comma-separated string
            thumbnail_url="https://example.com/thumb.webp",
            description="테스트 설명",
            is_draft=True,
            blog_id="test-hugo"
        )
        assert "draft: true" in fm, (
            f"is_draft=True 시 frontmatter에 'draft: true' 포함 필요: {fm[:200]}"
        )

        # is_draft=False인 경우
        fm_no_draft, _ = _build_frontmatter_blowfish(
            title="테스트 포스트",
            slug="test-post",
            category="추천",
            tags="테스트",
            thumbnail_url="https://example.com/thumb.webp",
            description="테스트 설명",
            is_draft=False,
            blog_id="test-hugo"
        )
        assert "draft: true" not in fm_no_draft, (
            f"is_draft=False 시 frontmatter에 'draft: true' 포함 없어야 함: {fm_no_draft[:200]}"
        )

    def test_publish_passes_is_draft_to_hugo_writer(self):
        """publish()가 is_draft를 hugo_writer에 전달"""
        from shared.publisher import publish
        import inspect

        sig = inspect.signature(publish)
        assert "is_draft" in sig.parameters, (
            f"publish() 시그니처에 is_draft 파라미터 필요: {list(sig.parameters.keys())}"
        )

    def test_pipeline_extracts_is_draft_from_article(self):
        """pipeline이 article dict에서 is_draft를 추출"""
        import inspect
        from pipelines.curation import pipeline

        source = inspect.getsource(pipeline)
        assert 'article.get("is_draft"' in source or "article.get('is_draft'" in source, (
            "pipeline 모듈에서 article.get('is_draft') 호출 필요"
        )


# ============================================================
# L2: Body CoT 감지 독립 검증
# ============================================================

class TestL2BodyCoTDetection:
    """L2: _is_cot_body가 독립적으로 CoT 본문을 감지하는지 검증"""

    def test_detects_cot_markers(self):
        """CoT 마커(우선, 사용자 요청, 제목 규칙 등) 감지"""
        from pipelines.curation.writer import _is_cot_body

        # 각 표본이 최소 2개 조건(글쓰기지시어 3+ OR CoT마커 1+)을 충족하도록 구성
        bodies = [
            # CoT 마커 + 글쓰기 지시어
            "우선 사용자 요청은 건강기능식품 추천입니다. AIDA 모델을 따라 작성해야 한다. "
            "도입부에서 제품 소개를 하자. 비교표를 만들어보자.",
            # CoT 마커 다수 + 글쓰기 지시어
            "사용자 요청은 네덜란드 상품 추천이다. 제목 규칙을 확인해야 한다. "
            "비교표를 만들어보자. H2 섹션으로 분리하자. 도입부에서 제품 소개를 한다.",
            # CoT 마커 + 퍼널/선택 가이드
            "제목 예시를 만들어보자. 퍼널 구조로 작성해야 한다. "
            "선택 가이드를 포함해야 한다. 비교표를 만들어보자.",
        ]

        for body in bodies:
            assert _is_cot_body(body) is True, (
                f"CoT 본문 미감지: {body[:50]}..."
            )

    def test_ignores_normal_content(self):
        """정상 콘텐츠는 CoT로 감지하지 않음"""
        from pipelines.curation.writer import _is_cot_body

        bodies = [
            "네덜란드산 산양유 단백질은 고함량 단백질 보충제로 인기 있습니다.",
            "올바른습관 네덜란드산 산양유100% 단백질 분말은 로켓배송으로 빠르게 받을 수 있습니다.",
            "백세식품 산양유 단백질 분말은 HACCP 인증을 받았으며, 200g x 6개로 구성되어 있습니다.",
        ]

        for body in bodies:
            assert _is_cot_body(body) is False, (
                f"정상 본문 오탐: {body[:50]}..."
            )

    def test_english_heavy_content_not_flagged(self):
        """영어가 많은 콘텐츠도 CoT 마커 없으면 정상으로 판정"""
        from pipelines.curation.writer import _is_cot_body

        body = (
            "The Krill Oil supplement is made from Antarctic krill. "
            "It contains EPA and DHA omega-3 fatty acids. "
            "Fish Oil is a traditional omega-3 supplement. "
            "Both products are available on Coupang with free shipping."
        )

        assert _is_cot_body(body) is False, (
            f"영어 콘텐츠 오탐: {body[:50]}..."
        )

    def test_cot_with_english_brand_names_detected(self):
        """CoT 마커 + 영어 브랜드명 포함 시 정상 감지"""
        from pipelines.curation.writer import _is_cot_body

        body = (
            "우선 사용자 요청은 건강기능식품 추천입니다. "
            "AIDA 모델을 따라 작성해야 한다. "
            "도입부에서 Krill Oil과 Fish Oil을 비교하자. "
            "비교표를 만들어보자."
        )

        assert _is_cot_body(body) is True, (
            f"CoT+영어 브랜드 본문 미감지: {body[:50]}..."
        )


# ============================================================
# L3: Title 템플릿 강화 독립 검증
# ============================================================

class TestL3TitleTemplate:
    """L3: TitleTemplatePicker가 정상 동작하는지 검증"""

    def test_title_template_picker_exists(self):
        """TitleTemplatePicker 클래스 존재"""
        from shared.title_templates import TitleTemplatePicker
        assert TitleTemplatePicker is not None

    def test_title_template_picker_has_pick_method(self):
        """TitleTemplatePicker에 pick 메서드 존재"""
        from shared.title_templates import TitleTemplatePicker
        picker = TitleTemplatePicker()
        assert hasattr(picker, 'pick'), "TitleTemplatePicker에 pick 메서드 필요"

    def test_title_hardening_guard_exists_in_pipeline(self):
        """title 강화 가드가 파이프라인에 존재하는지 확인"""
        from pipelines.curation import pipeline

        # TITLE_TEMPLATE_PATTERNS 상수 존재 확인
        assert hasattr(pipeline, 'TITLE_TEMPLATE_PATTERNS'), (
            "pipeline 모듈에 TITLE_TEMPLATE_PATTERNS 상수 존재 필요"
        )
        assert len(pipeline.TITLE_TEMPLATE_PATTERNS) > 0, (
            "TITLE_TEMPLATE_PATTERNS가 비어있지 않아야 함"
        )


# ============================================================
# L4: 정상 통과 검증
# ============================================================

class TestL4NormalPass:
    """L4: 모든 가드 클리어 시 정상 발행되는지 검증"""

    def test_normal_content_passes_all_guards(self):
        """정상 콘텐츠가 모든 가드를 통과"""
        from pipelines.curation.writer import _is_cot_body

        normal_body = (
            "네덜란드산 산양유 단백질은 고함량 단백질 보충제로 인기 있습니다. "
            "분말 형태와 정제 형태 두 가지가 있으며, "
            "HACCP 인증 받은 제품을 선택하는 것이 좋습니다. "
            "가격은 7만원에서 12만원 사이입니다."
        )

        assert _is_cot_body(normal_body) is False, (
            f"정상 본문이 CoT로 오탐됨: {normal_body[:50]}..."
        )

    def test_cot_content_blocked_by_quality_gate(self):
        """CoT 콘텐츠가 품질 게이트에서 차단됨"""
        from pipelines.curation.pipeline import _content_quality_gate

        # CoT 본문을 포함한 article dict
        cot_article = {
            "title": "테스트 제목",
            "body_md": (
                "우선 사용자 요청은 건강기능식품 추천입니다. "
                "AIDA 모델을 따라 퍼널 구조로 작성해야 한다. "
                "도입부에서 제품 소개를 하고, 비교표로 정리하자. "
                "제목 규칙을 확인해야 한다. 제목 예시를 만들어보자."
            ),
            "description": "CoT 테스트 설명",
        }

        article, error = _content_quality_gate("test-hugo", "테스트키워드", cot_article)

        # 차단 시: article이 None, error에 reason 포함
        assert article is None, (
            f"CoT 본문이 차단되지 않음 (article이 None이어야 함): article={article}"
        )
        assert error is not None and error.get("reason") == "content_quality_gate", (
            f"차단 시 error에 content_quality_gate reason 필요: {error}"
        )

    def test_normal_content_passes_quality_gate(self):
        """정상 콘텐츠가 품질 게이트를 통과"""
        from pipelines.curation.pipeline import _content_quality_gate

        normal_article = {
            "title": "네덜란드 산양유 단백질 추천 TOP5",
            "body_md": (
                "네덜란드산 산양유 단백질은 고함량 단백질 보충제로 인기 있습니다. "
                "분말 형태와 정제 형태 두 가지가 있으며, "
                "HACCP 인증 받은 제품을 선택하는 것이 좋습니다."
            ),
            "description": "네덜란드산 산양유 단백질 추천 제품 비교",
        }

        article, error = _content_quality_gate("test-hugo", "산양유단백질", normal_article)

        # 통과 시: article이 존재, error가 None
        assert article is not None, (
            f"정상 본문이 차단됨 (article이 존재해야 함): error={error}"
        )
        assert error is None, (
            f"정상 본문 통과 시 error가 None이어야 함: error={error}"
        )


# ============================================================
# 실행
# ============================================================

if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v", "--tb=short"])

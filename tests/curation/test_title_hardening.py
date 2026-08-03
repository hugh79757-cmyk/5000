"""Phase 54 회귀 테스트 — Curation Title Generation Hardening.

커버: H1 누락 → 제목 재생성 (SC-2), 재생성 2회 실패 → 차단 마커 (결정 3),
description CoT 누출 차단 (SC-3), pipeline _title_gate 차단 (SC-4).

모든 LLM 호출은 mock — 실제 HTTP/LLM API 호출 없음 (실제 호출 금지 계약).
mock 전략: side_effect 시퀀스가 아니라 tier kwargs 분기
(tier=="economy" → 재생성 응답, 그 외 → 본문 응답) — 본문 글자수 재시도
루프가 시퀀스를 소모하는 문제 회피 (MINOR-5).

본문 mock 응답은 반드시 800자 이상 (INFO-4: 미만이면 return None 경로로
테스트가 오해 가능).
"""
from unittest.mock import patch

import pytest

from pipelines.curation.writer import generate_curation_article

# 본문 mock 응답 (H1 없음, CoT 시작) — 800자 이상 보장 (~1200자)
BODY_WITHOUT_H1 = (
    "우선 사용자 요청은 네덜란드 산양유 단백질 추천입니다.\n\n"
    + ("네덜란드산 산양유 단백질 제품을 비교하는 내용입니다. " * 40)
)
assert len(BODY_WITHOUT_H1) >= 800, "본문 mock 응답은 800자 이상이어야 함"

# 본문 mock 응답 (H1 정상) — description CoT 차단 테스트용
BODY_WITH_H1 = (
    "# 네덜란드 산양유 단백질 추천 가이드\n\n"
    "우선 사용자 요청은 네덜란드 산양유 단백질 추천입니다.\n\n"
    + ("네덜란드산 산양유 단백질 제품을 비교하는 내용입니다. " * 40)
)
assert len(BODY_WITH_H1) >= 800, "본문 mock 응답은 800자 이상이어야 함"

VALID_REGEN_TITLE = "# 네덜란드 산양유 단백질 추천"
TEMPLATE_REGEN_TITLE = "# 네덜란드 추천 TOP5 (2026년)"


def _kwargs_branching_fake(body_response, regen_response=None, regen_raise=None, regen_calls=None):
    """tier kwargs 분기 mock — 본문 생성(default)과 재생성(economy)을 분기한다."""
    def fake(system_prompt, user_prompt, tier="default", temperature=None, max_tokens=None):
        if tier == "economy":
            if regen_calls is not None:
                regen_calls["count"] = regen_calls.get("count", 0) + 1
                regen_calls["last_kwargs"] = {
                    "tier": tier, "temperature": temperature, "max_tokens": max_tokens,
                }
            if regen_raise is not None:
                raise regen_raise
            return regen_response
        return body_response
    return fake


def test_h1_missing_triggers_regeneration(sample_products):
    """SC-2 — H1 누락 시 재생성 경로 발동, 유효 제목 사용, (2026년) 미종결.

    재생성 파라미터 계약(결정 2)도 함께 검증: tier=="economy",
    temperature==0.5, max_tokens==200.
    """
    regen_calls = {}
    fake = _kwargs_branching_fake(
        BODY_WITHOUT_H1, regen_response=VALID_REGEN_TITLE, regen_calls=regen_calls,
    )
    with patch("pipelines.curation.writer.ai_generate", side_effect=fake):
        r = generate_curation_article("네덜란드", sample_products, blog_id=None)

    assert r["title"] == "네덜란드 산양유 단백질 추천", r["title"]
    assert not r["title"].endswith("(2026년)"), r["title"]
    assert "(2026년)" not in r["title"]
    assert "title_generation_failed" not in r, r

    # 재생성 호출 파라미터 계약 검증
    assert regen_calls["count"] == 1, regen_calls
    assert regen_calls["last_kwargs"] == {"tier": "economy", "temperature": 0.5, "max_tokens": 200}, regen_calls


def test_regeneration_failure_returns_marker(sample_products):
    """결정 3 — 재생성 2회 모두 템플릿 제목 → 차단 마커, 템플릿 제목 부재."""
    fake = _kwargs_branching_fake(BODY_WITHOUT_H1, regen_response=TEMPLATE_REGEN_TITLE)
    with patch("pipelines.curation.writer.ai_generate", side_effect=fake):
        r = generate_curation_article("네덜란드", sample_products, blog_id=None)

    assert r["title"] == "", r["title"]
    assert r["title_generation_failed"] is True, r
    assert "추천 TOP5" not in r["title"]
    assert "(2026년)" not in r["title"]
    assert "추천 TOP" not in r["title"]
    assert r["body_md"], "본문은 유지되어야 함"
    assert r["keyword"] == "네덜란드"
    assert r["product_count"] == min(len(sample_products), 5)


def test_regeneration_runtime_error_returns_marker(sample_products):
    """MINOR-4 — ai_generate가 RuntimeError(전 tier 실패)를 raise해도
    무효로 취급되어 재시도 후 차단 마커 반환."""
    fake = _kwargs_branching_fake(
        BODY_WITHOUT_H1, regen_raise=RuntimeError("모든 LLM tier 실패: test"),
    )
    with patch("pipelines.curation.writer.ai_generate", side_effect=fake):
        r = generate_curation_article("네덜란드", sample_products, blog_id=None)

    assert r["title"] == "", r["title"]
    assert r["title_generation_failed"] is True, r
    assert "추천 TOP" not in r["title"]


def test_description_rejects_cot_first_line(sample_products):
    """SC-3 — 본문 첫 줄 CoT('우선 사용자 요청은...')는 description에서 제외."""
    fake = _kwargs_branching_fake(BODY_WITH_H1)
    with patch("pipelines.curation.writer.ai_generate", side_effect=fake):
        r = generate_curation_article("네덜란드", sample_products, blog_id=None)

    assert "우선 사용자 요청" not in r["description"], r["description"]
    assert "네덜란드산 산양유 단백질 제품을 비교" in r["description"], r["description"]
    assert len(r["description"]) <= 150, len(r["description"])


def test_title_gate_blocks_template_title():
    """SC-4 — _title_gate가 템플릿 제목 패턴을 차단하고 stage='title_blocked' 기록."""
    from pipelines.curation.pipeline import _title_gate

    article = {"title": "네덜란드 추천 TOP5 (2026년)", "body_md": "본문"}
    with patch("pipelines.curation.pipeline._record_failure") as mock_rf:
        title, err = _title_gate("health-hugo", "네덜란드", article)

    assert title is None
    assert err == {"success": False, "reason": "title_blocked"}, err
    assert mock_rf.call_count == 1
    args = mock_rf.call_args[0]
    assert args[1] == "title_blocked", args
    assert "템플릿 제목 패턴" in args[2], args


def test_title_gate_blocks_generation_failed():
    """결정 3 보강 — title_generation_failed=True → 차단 + stage='title_regenerate_failed'."""
    from pipelines.curation.pipeline import _title_gate

    article = {"title": "", "body_md": "본문", "title_generation_failed": True}
    with patch("pipelines.curation.pipeline._record_failure") as mock_rf:
        title, err = _title_gate("health-hugo", "네덜란드", article)

    assert title is None
    assert err == {"success": False, "reason": "title_blocked"}, err
    assert mock_rf.call_count == 1
    args = mock_rf.call_args[0]
    assert args[1] == "title_regenerate_failed", args
    assert "제목 재생성 실패" in args[2], args

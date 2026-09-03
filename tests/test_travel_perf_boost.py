"""Phase 77 travel 지역 boost 테스트 (_perf_boosted_sigungu).

기본 OFF passthrough / env ON boost / 게이트 실패 경로 검증.
OPS_TEST_MODE pytest로 실행.
"""
import json
import os
import random
from pathlib import Path

import pytest

from pipelines.travel.fetcher import _perf_boosted_sigungu
from pipelines.travel.area_codes import FOOD_AREA_SIGUNGU_WEIGHTED


def _all_names():
    return [x[2] for x in FOOD_AREA_SIGUNGU_WEIGHTED]


def test_gate_off_matches_original_distribution():
    """PERF_SIGNALS 미설정 → 기존 가중치 선택과 통계적으로 동일."""
    calls = [
        _perf_boosted_sigungu(exclude_sigungus=None) for _ in range(200)
    ]
    names = [c[2] for c in calls]
    valid = set(_all_names())
    assert all(n in valid for n in names), "게이트 OFF인데 유효하지 않은 지역 반환"
    # 다양성 확인 — 200회에 1종류만 나오면 기존 로직 아님
    assert len(set(names)) > 10


def test_boost_on_prefers_signaled_region(tmp_path, monkeypatch):
    """env ON + 신호에 '대전' 계열 지역 → 해당 지역 선택 빈도 급증."""
    sig_file = tmp_path / "keyword_performance.json"
    sig_file.write_text(
        json.dumps({"travel3-hugo": ["대전 드라이브 코스"]}, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setenv("PERF_SIGNALS", "1")
    monkeypatch.setenv("PERF_BLOG_ID", "travel3-hugo")
    monkeypatch.setenv("PERF_SIGNALS_PATH", str(sig_file))

    random.seed(42)
    picks = [
        _perf_boosted_sigungu(exclude_sigungus=None)[2] for _ in range(100)
    ]
    daejeon = {"동구", "중구", "서구", "유성구", "대덕구"}
    hit = sum(1 for p in picks if p in daejeon)
    # weight 2~3 → boost 3배 → 기존 대비 3배. 대전 5구 비중이 크게 상승해야 함
    assert hit >= 30, f"대전 계열 선택 {hit}/100 — boost 미작동 의심"

    random.seed(42)
    base_picks = []
    monkeypatch.delenv("PERF_SIGNALS")
    for _ in range(100):
        base_picks.append(_perf_boosted_sigungu(exclude_sigungus=None)[2])
    base_hit = sum(1 for p in base_picks if p in daejeon)
    # boost 3배 → 대전 합산 weight가 전체에서 차지하는 비중 ~3배 상승 기대
    assert hit >= base_hit * 1.8, f"boost 효과 미미: {hit} vs baseline {base_hit}"


def test_boost_excluded_region_passthrough(tmp_path, monkeypatch):
    """boost 대상 지역이 exclude_sigungus에 있으면 boost 적용 안 됨."""
    sig_file = tmp_path / "keyword_performance.json"
    sig_file.write_text(
        json.dumps({"travel3-hugo": ["대전 드라이브 코스"]}, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setenv("PERF_SIGNALS", "1")
    monkeypatch.setenv("PERF_BLOG_ID", "travel3-hugo")
    monkeypatch.setenv("PERF_SIGNALS_PATH", str(sig_file))
    daejeon = {"동구", "중구", "서구", "유성구", "대덕구"}
    exclude = set(_all_names()) - daejeon  # 대전만 남기고 전부 제외

    picks = [_perf_boosted_sigungu(exclude_sigungus=exclude)[2] for _ in range(50)]
    assert all(p in daejeon for p in picks), "제외 로직 깨짐"


def test_corrupt_json_passthrough(tmp_path, monkeypatch):
    """손상 JSON → 예외 없이 기존 선택으로 passthrough."""
    sig_file = tmp_path / "keyword_performance.json"
    sig_file.write_text("{{{broken", encoding="utf-8")
    monkeypatch.setenv("PERF_SIGNALS", "1")
    monkeypatch.setenv("PERF_BLOG_ID", "travel3-hugo")
    monkeypatch.setenv("PERF_SIGNALS_PATH", str(sig_file))
    picks = [_perf_boosted_sigungu(exclude_sigungus=None)[2] for _ in range(20)]
    assert all(p in set(_all_names()) for p in picks)


def test_no_signals_for_blog_passthrough(tmp_path, monkeypatch):
    """타 블로그 신호만 있음 → KeyError → passthrough."""
    sig_file = tmp_path / "keyword_performance.json"
    sig_file.write_text(
        json.dumps({"deal-hugo": ["gr86 유지비"]}, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setenv("PERF_SIGNALS", "1")
    monkeypatch.setenv("PERF_BLOG_ID", "travel3-hugo")
    monkeypatch.setenv("PERF_SIGNALS_PATH", str(sig_file))
    picks = [_perf_boosted_sigungu(exclude_sigungus=None)[2] for _ in range(20)]
    assert all(p in set(_all_names()) for p in picks)

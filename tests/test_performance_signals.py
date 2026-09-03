"""Phase 77 W2 — _select_keyword perf-signal boost (env-gated, default OFF).

_boost_by_signals: pure reorder (matched-first, stable).
_apply_perf_signal_boost: env/file/gate wrapper — any failure → passthrough.
"""
import os
import json

import pytest

from pipelines.curation.pipeline import _boost_by_signals, _apply_perf_signal_boost

CANDIDATES = ["AAA BBB", "XXX 유지비", "CCC DDD"]


def test_boost_moves_matching_candidate_first():
    assert _boost_by_signals(CANDIDATES, ["그랜드랜지 유지비"]) == [
        "XXX 유지비", "AAA BBB", "CCC DDD",
    ]


def test_boost_no_match_order_unchanged():
    assert _boost_by_signals(CANDIDATES, ["드라이브 코스"]) == CANDIDATES


def test_boost_stable_sort_multiple_matches():
    assert _boost_by_signals(
        ["에어컨 설치", "유지비 절약 팁", "BBB", "전기 유지비"],
        ["m4 유지비"],
    ) == ["유지비 절약 팁", "전기 유지비", "에어컨 설치", "BBB"]


def test_env_off_order_unchanged(monkeypatch, tmp_path):
    monkeypatch.delenv("PERF_SIGNALS", raising=False)
    monkeypatch.setattr(
        "pipelines.curation.pipeline.PROJECT_DIR", tmp_path
    )
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "keyword_performance.json").write_text(
        json.dumps({"blog": ["그랜드랜지 유지비"]}), encoding="utf-8"
    )
    assert _apply_perf_signal_boost(CANDIDATES, "blog") == CANDIDATES


def test_env_explicit_zero_order_unchanged(monkeypatch, tmp_path):
    monkeypatch.setenv("PERF_SIGNALS", "0")
    monkeypatch.setattr(
        "pipelines.curation.pipeline.PROJECT_DIR", tmp_path
    )
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "keyword_performance.json").write_text(
        json.dumps({"blog": ["그랜드랜지 유지비"]}), encoding="utf-8"
    )
    assert _apply_perf_signal_boost(CANDIDATES, "blog") == CANDIDATES


def test_missing_json_order_unchanged(monkeypatch, tmp_path):
    monkeypatch.setenv("PERF_SIGNALS", "1")
    monkeypatch.setattr(
        "pipelines.curation.pipeline.PROJECT_DIR", tmp_path
    )  # data/keyword_performance.json 부재
    assert _apply_perf_signal_boost(CANDIDATES, "blog") == CANDIDATES


def test_corrupt_json_passthrough_no_exception(monkeypatch, tmp_path):
    monkeypatch.setenv("PERF_SIGNALS", "1")
    monkeypatch.setattr(
        "pipelines.curation.pipeline.PROJECT_DIR", tmp_path
    )
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "keyword_performance.json").write_text(
        "{corrupt garbage!!", encoding="utf-8"
    )
    assert _apply_perf_signal_boost(CANDIDATES, "blog") == CANDIDATES


def test_no_signals_for_blog_order_unchanged(monkeypatch, tmp_path):
    monkeypatch.setenv("PERF_SIGNALS", "1")
    monkeypatch.setattr(
        "pipelines.curation.pipeline.PROJECT_DIR", tmp_path
    )
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "keyword_performance.json").write_text(
        json.dumps({"other-blog": ["그랜드랜지 유지비"]}), encoding="utf-8"
    )
    assert _apply_perf_signal_boost(CANDIDATES, "blog") == CANDIDATES


def test_env_on_with_signals_boosts(monkeypatch, tmp_path):
    monkeypatch.setenv("PERF_SIGNALS", "1")
    monkeypatch.setattr(
        "pipelines.curation.pipeline.PROJECT_DIR", tmp_path
    )
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "keyword_performance.json").write_text(
        json.dumps({"blog": ["그랜드랜지 유지비"]}), encoding="utf-8"
    )
    assert _apply_perf_signal_boost(CANDIDATES, "blog") == [
        "XXX 유지비", "AAA BBB", "CCC DDD",
    ]

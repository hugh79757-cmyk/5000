"""Unit tests for keyword_harvester + rate_limiter. Mock-only, no real API."""

import time
from unittest.mock import patch

import pytest

from pipelines.curation.keyword_harvester import (
    HOURLY_SEARCH_LIMIT,
    KeywordHarvester,
    SafetyGuard,
)
from pipelines.curation.rate_limiter import RateLimiter


@pytest.fixture(autouse=True)
def _tmp_ops_db(tmp_path, monkeypatch):
    """conftest guard 요구 — 운영 ops.db 대신 tmp 경로 사용 (harvester는 DB 안 쓰지만 guard가 전역 적용)."""
    from shared import publish_error_events as events
    monkeypatch.setattr(events, "OPS_DB_PATH", tmp_path / "ops.db")


# ── 1. rate limiter blocks the 9th call within the hourly window ──

def test_hourly_limiter_blocks_9th_call():
    limiter = RateLimiter(limit=HOURLY_SEARCH_LIMIT, window_seconds=3600)
    for _ in range(HOURLY_SEARCH_LIMIT):
        assert limiter.allowed()
        limiter.record()
    # 9th call must be blocked
    assert not limiter.allowed()


def test_wait_if_needed_uses_time_sleep_and_unblocks():
    limiter = RateLimiter(limit=1, window_seconds=0.5)
    limiter.record()
    with patch("time.sleep") as mock_sleep:
        limiter.wait_if_needed()  # window full -> should sleep
        assert mock_sleep.called
    # after window expiry it unblocks without sleeping
    time.sleep(0.55)
    with patch("time.sleep") as mock_sleep2:
        limiter.wait_if_needed()
        assert not mock_sleep2.called


# ── 2. SafetyGuard HARD_STOP on single 403 ──

def test_safety_guard_hard_stop_on_http_403(capsys):
    guard = SafetyGuard(cooldown_hours=12)
    assert not guard.is_stopped
    guard.on_response(403)
    out = capsys.readouterr().out
    assert "[CRITICAL] COUPANG_RATE_EXCEEDED" in out
    assert guard.is_stopped


def test_safety_guard_hard_stop_on_rcode_403():
    guard = SafetyGuard(cooldown_hours=12)
    guard.on_response(200, body_rcode="403")  # Coupang embeds 403 in JSON rCode
    assert guard.is_stopped


def test_harvester_stops_all_calls_after_403():
    calls = []

    def fetch_fn(source):
        calls.append(source)
        if len(calls) == 1:
            return {"status_code": 200, "rcode": "0", "keywords": ["k1"]}
        return {"status_code": 403, "rcode": "", "keywords": []}

    h = KeywordHarvester(fetch_fn=fetch_fn)
    result = h.harvest(max_new=10)
    assert len(calls) == 2            # second call tripped the guard
    assert result == ["k1"]           # pre-trip results kept
    # subsequent harvest cycles are fully blocked
    assert h.harvest() == []
    assert len(calls) == 2


def test_cooldown_expires():
    guard = SafetyGuard(cooldown_hours=12)
    guard._tripped_until = time.time() - 1
    assert not guard.is_stopped


# ── 3. duplicate keyword filtering ──

def test_dedup_filters_existing_and_intra_batch():
    def fetch_fn(source):
        return {"status_code": 200, "rcode": "0",
                "keywords": ["물티슈", "요가매트", "물티슈", "", None, "물티슈 "]}

    h = KeywordHarvester(fetch_fn=fetch_fn, existing_keywords={"요가매트"})
    result = h.harvest()
    assert result == ["물티슈"]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))

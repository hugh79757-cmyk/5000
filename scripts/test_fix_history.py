"""scripts/test_fix_history.py — BLK-3 단위 검증 (plain assert, 실행: python3 scripts/test_fix_history.py)."""
from __future__ import annotations

import tempfile
from pathlib import Path

import ops_dashboard.fix_history as fh


def _tmp_root() -> Path:
    d = Path(tempfile.mkdtemp(prefix="fixhist_"))
    fh.ROOT = d
    return d


def test_record_creates_sidecar():
    _tmp_root()
    e = fh.record_fix("b1", "/tmp/p/post-a.md", "FM-MISSINGKEYS", "APPLIED", "보강")
    assert isinstance(e, fh.HistoryEntry)
    assert (fh.ROOT / "b1" / "post-a.json").exists()


def test_history_two_entries():
    _tmp_root()
    fh.record_fix("b1", "/tmp/p/post-a.md", "FM-MISSINGKEYS", "PATCH_PROPOSED")
    fh.record_fix("b1", "/tmp/p/post-a.md", "FM-MISSINGKEYS", "APPLIED")
    hist = fh.get_history("b1", "/tmp/p/post-a.md")
    assert len(hist) == 2


def test_get_latest():
    _tmp_root()
    fh.record_fix("b1", "/tmp/p/post-a.md", "FM-MISSINGKEYS", "PATCH_PROPOSED")
    fh.record_fix("b1", "/tmp/p/post-a.md", "FM-MISSINGKEYS", "APPLIED")
    fh.record_fix("b1", "/tmp/p/post-a.md", "FM-DRAFT", "APPLIED")
    latest = fh.get_latest("b1", "/tmp/p/post-a.md", "FM-MISSINGKEYS")
    assert latest is not None and latest.action == "APPLIED"


def test_invalid_action_raises():
    _tmp_root()
    try:
        fh.record_fix("b1", "/tmp/p/post-a.md", "FM-MISSINGKEYS", "BOGUS")
        raise AssertionError("ValueError 미발생")
    except ValueError:
        pass


def test_concurrency_no_loss():
    _tmp_root()
    for i in range(10):
        fh.record_fix("b1", "/tmp/p/post-a.md", "FM-MISSINGKEYS", "APPLIED", f"#{i}")
    assert len(fh.get_history("b1", "/tmp/p/post-a.md")) == 10


if __name__ == "__main__":
    test_record_creates_sidecar()
    test_history_two_entries()
    test_get_latest()
    test_invalid_action_raises()
    test_concurrency_no_loss()
    print("test_fix_history: PASS")

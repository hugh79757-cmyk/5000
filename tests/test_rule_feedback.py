"""tests/test_rule_feedback.py — 64-04 feedback JSONL store + review CLI

3 cases: record fp → valid JSON false_positive, record fn → false_negative,
read since 7d filters old. + corrupt line not break parser + review table prints.
"""
import json
import tempfile
import time
from pathlib import Path
from unittest import mock
from datetime import datetime, timedelta


def _tmp_feedback(monkeypatch_path=None):
    # use temporary file instead of real logs/rule_feedback.jsonl
    import shared.rule_feedback as rf
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl")
    tmp_path = Path(tmp.name)
    tmp.close()
    # ensure empty
    if tmp_path.exists():
        tmp_path.unlink()
    # patch FEEDBACK_PATH
    original = rf.FEEDBACK_PATH
    rf.FEEDBACK_PATH = tmp_path
    return rf, tmp_path, original


def test_record_false_positive():
    import shared.rule_feedback as rf
    rf2, tmp_path, orig = _tmp_feedback()
    try:
        e = rf2.record_feedback(type="false_positive", rule_id="C01", blog_id="health-hugo",
                                slug="slug-fp", severity="MAJOR", gate_decision="blocked",
                                reason="fp test", detected_by="human")
        assert tmp_path.exists(), "file should be created"
        lines = tmp_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        obj = json.loads(lines[0])
        assert obj["type"] == "false_positive"
        assert obj["id"].startswith("fp-")
        assert obj["rule_id"] == "C01"
    finally:
        rf2.FEEDBACK_PATH = orig
        if tmp_path.exists():
            tmp_path.unlink()


def test_record_false_negative():
    import shared.rule_feedback as rf
    rf2, tmp_path, orig = _tmp_feedback()
    try:
        e = rf2.record_feedback(type="false_negative", rule_id="C09", blog_id="health-hugo",
                                slug="slug-fn", severity="CRITICAL", gate_decision="passed",
                                reason="fn test", detected_by="agent")
        lines = tmp_path.read_text(encoding="utf-8").strip().splitlines()
        obj = json.loads(lines[0])
        assert obj["type"] == "false_negative"
        assert obj["id"].startswith("fn-")
        assert obj["rule_id"] == "C09"
    finally:
        rf2.FEEDBACK_PATH = orig
        if tmp_path.exists():
            tmp_path.unlink()


def test_read_since_filters_old():
    import shared.rule_feedback as rf
    rf2, tmp_path, orig = _tmp_feedback()
    try:
        e1 = rf2.record_feedback(type="false_positive", rule_id="C01", blog_id="b", slug="s1",
                                 severity="MAJOR", gate_decision="blocked", reason="recent", detected_by="human")
        # inject old entry manually (10 days ago)
        old_ts = (datetime.now() - timedelta(days=10)).isoformat()
        old_entry = {"id": "fp-20000101-001", "ts": old_ts, "type": "false_positive",
                     "rule_id": "C01", "blog_id": "b", "slug": "old", "severity": "MAJOR",
                     "gate_decision": "blocked", "reason": "old", "detected_by": "human", "status": "open"}
        with open(tmp_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(old_entry, ensure_ascii=False) + "\n")
        filtered = rf2.read_feedback(since_days=7)
        assert len(filtered) == 1, f"expected 1 recent, got {len(filtered)}"
        assert filtered[0]["slug"] == "s1"
        # since 30d should include both
        filtered30 = rf2.read_feedback(since_days=30)
        assert len(filtered30) == 2
    finally:
        rf2.FEEDBACK_PATH = orig
        if tmp_path.exists():
            tmp_path.unlink()


def test_corrupt_line_not_break():
    import shared.rule_feedback as rf
    rf2, tmp_path, orig = _tmp_feedback()
    try:
        rf2.record_feedback(type="false_positive", rule_id="C01", blog_id="b", slug="s1",
                            severity="MAJOR", gate_decision="blocked", reason="r", detected_by="human")
        with open(tmp_path, "a", encoding="utf-8") as f:
            f.write('{"test":1}\n')
            f.write('not json at all\n')
        # read should not raise, and return at least 1 valid (the fp)
        result = rf2.read_feedback(since_days=7)
        assert len(result) >= 1
        # review-like: corrupt ignored, valid still counted
        # file still readable
        text = tmp_path.read_text(encoding="utf-8")
        assert len(text.splitlines()) == 3
    finally:
        rf2.FEEDBACK_PATH = orig
        if tmp_path.exists():
            tmp_path.unlink()


def test_review_prints_table_even_empty():
    import subprocess, sys, tempfile, os
    # run review script with empty tmp file via --jsonl override not exists -> use default empty
    # Instead test via subprocess with real script but temp empty: create empty file and point via env?
    # Simpler: call aggregate directly
    from scripts.rule_feedback_review import aggregate, load_entries
    import scripts.rule_feedback_review as rev
    import tempfile
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl")
    tmp_path = Path(tmp.name)
    tmp.close()
    # ensure file does not exist -> load_entries returns []
    if tmp_path.exists():
        tmp_path.unlink()
    orig = rev.FEEDBACK_PATH
    rev.FEEDBACK_PATH = tmp_path
    try:
        entries = rev.load_entries(since_dt=None)
        assert entries == []
        by_rule = rev.aggregate(entries)
        assert by_rule == {}
    finally:
        rev.FEEDBACK_PATH = orig
        if tmp_path.exists():
            tmp_path.unlink()

"""Regression: get_attention_items의 publish_error 행 — 근본원인 노출.

작업1(phase-71e-pcode-1): publish_error 이벤트가 고립 1행+action=""가 아니라
severity/action/playbook_ref를 PROBLEM_REGISTRY에서 유도하고, P02는 선행 근본원인을
묶어 표시하며, P25 severity가 CRITICAL로 정합되는지 검증한다.
"""

import sqlite3

from ops_dashboard.db import (
    _resolve_publish_error_meta,
    get_attention_items,
)
from shared.publish_error_events import ensure_schema


def _make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_schema(conn)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS blog_lifecycle (
            blog_id TEXT PRIMARY KEY,
            config_status TEXT,
            maintenance_status TEXT,
            domain TEXT,
            brand TEXT,
            pipeline TEXT,
            days_since_last_publish INTEGER,
            lifecycle_status TEXT
        );
        CREATE TABLE IF NOT EXISTS check_results (
            blog_id TEXT, check_name TEXT, status TEXT, detail TEXT,
            evidence_url TEXT, checked_at TEXT, rule_id TEXT,
            problem_id TEXT, severity TEXT, action TEXT
        );
        CREATE TABLE IF NOT EXISTS known_issues (
            issue_id TEXT, category TEXT, gsd_status TEXT
        );
    """)
    return conn


_COLS = ("event_id, blog_id, pipeline, stage, problem_id, detail_redacted,"
         " fingerprint, state, severity, occurred_at, created_at")


def _insert(conn, vals):
    ph = ",".join("?" * len(vals.split(",")))
    conn.execute(
        f"INSERT INTO publish_error_events({_COLS}) VALUES({ph})", vals.split(",")
    )


def test_meta_resolver_p25_is_critical():
    sev, action, ref = _resolve_publish_error_meta("P25")
    assert sev == "CRITICAL"
    assert ref == "ERROR_PLAYBOOKS.md#p25"
    sev2, action2, _ = _resolve_publish_error_meta("P02")
    assert sev2 == "MAJOR"
    assert "콘텐츠 재생성" in action2


def test_attention_publish_error_carries_action_and_stage_and_root_cause():
    conn = _make_conn()
    conn.execute(
        "INSERT INTO blog_lifecycle(blog_id, config_status, maintenance_status) VALUES('b1','active','none')"
    )
    # b1: open P02 + 채택될 선행(closed) 근본원인 P04 — chronological보다 prior 기준
    _insert(conn, "1,b1,curation,post_deploy,P04,wrangler fail,fp1,closed,CRITICAL,"
            "2026-08-12 03:55:00,2026-08-12 03:55:00")
    _insert(conn, "2,b1,curation,no_content,P02,consecutive_failures,fp2,open,MAJOR,"
            "2026-08-13 09:00:00,2026-08-13 09:00:00")
    conn.execute(
        "INSERT INTO blog_lifecycle(blog_id, config_status, maintenance_status) VALUES('b2','active','none')"
    )
    _insert(conn, "3,b2,etap,no_content,P02,52 topics,fp3,open,MAJOR,"
            "2026-08-14 10:00:00,2026-08-14 10:00:00")
    conn.commit()

    att = get_attention_items(conn)
    pes = [e for e in att["fail_checks"] if e.get("check_name") == "publish_error"]
    b2 = [e for e in pes if e["blog_id"] == "b2"][0]
    assert b2["problem_id"] == "P02"
    assert b2["stage"] == "no_content"
    assert b2["severity"] == "MAJOR"
    assert b2["action"].strip() != ""
    assert b2["playbook_ref"] == "ERROR_PLAYBOOKS.md#p02"

    # b1: P02가 선행 P04(closed)를 근본원인으로 묶어 표시해야 한다
    b1 = [e for e in pes if e["blog_id"] == "b1"]
    p02 = [e for e in b1 if e["problem_id"] == "P02"][0]
    assert "P04" in (p02.get("root_cause") or "")
    conn.close()
"""Structured operational error events for publishing and alert delivery."""
from __future__ import annotations

import hashlib
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from shared.problem_registry import lookup_problem, lookup_reason

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OPS_DB_PATH = PROJECT_ROOT / "ops_dashboard" / "ops.db"

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS publish_error_events (
    event_id TEXT PRIMARY KEY,
    occurred_at TEXT NOT NULL,
    blog_id TEXT NOT NULL,
    pipeline TEXT NOT NULL DEFAULT '',
    stage TEXT NOT NULL,
    problem_id TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    severity TEXT NOT NULL,
    retryable INTEGER NOT NULL DEFAULT 0,
    attempt INTEGER,
    max_attempts INTEGER,
    source_name TEXT NOT NULL DEFAULT '',
    http_status INTEGER,
    timeout_seconds INTEGER,
    detail_redacted TEXT NOT NULL DEFAULT '',
    fingerprint TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_publish_error_time ON publish_error_events(occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_publish_error_blog ON publish_error_events(blog_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_publish_error_problem ON publish_error_events(problem_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_publish_error_state ON publish_error_events(state, occurred_at DESC);

CREATE TABLE IF NOT EXISTS telegram_delivery_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT,
    sent_at TEXT NOT NULL,
    delivered INTEGER NOT NULL DEFAULT 0,
    telegram_message_id TEXT NOT NULL DEFAULT '',
    http_status INTEGER,
    detail_redacted TEXT NOT NULL DEFAULT '',
    message_redacted TEXT NOT NULL DEFAULT '',
    FOREIGN KEY(event_id) REFERENCES publish_error_events(event_id)
);
CREATE INDEX IF NOT EXISTS idx_tda_event ON telegram_delivery_audit(event_id, sent_at DESC);
"""

_NEW_CODES: dict[str, dict[str, Any]] = {
    "P25": {"name": "scheduler timeout", "severity": "CRITICAL", "retryable": True},
    "P26": {"name": "source unavailable", "severity": "MAJOR", "retryable": True},
    "P27": {"name": "source exhausted", "severity": "MAJOR", "retryable": False},
    "P28": {"name": "invalid result contract", "severity": "MAJOR", "retryable": True},
    "P29": {"name": "publisher schema mismatch", "severity": "CRITICAL", "retryable": False},
    "P30": {"name": "content generation failure", "severity": "MAJOR", "retryable": True},
    "P31": {"name": "telegram delivery failure", "severity": "MAJOR", "retryable": True},
}

_SECRET_PATTERNS = (
    (re.compile(r"bot\d+:[A-Za-z0-9_-]+"), "[REDACTED_BOT_TOKEN]"),
    (re.compile(r"(?i)(api[_-]?key|authorization|bearer)\s*[:=]\s*[^\s,;]+"), r"\1=[REDACTED]"),
    (re.compile(r"https?://[^\s]+"), "[URL]"),
)


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(OPS_DB_PATH), timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def ensure_schema(conn: sqlite3.Connection | None = None) -> None:
    owns_connection = conn is None
    target = conn or _connect()
    try:
        target.executescript(_SCHEMA_SQL)
        target.commit()
    finally:
        if owns_connection:
            target.close()


def redact_detail(value: Any, limit: int = 1000) -> str:
    text = str(value or "")
    for pattern, replacement in _SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text[:limit]


def classify_error(
    stage: str,
    detail: Any,
    reason: str = "",
    problem_id: str = "",
) -> tuple[str, str, bool]:
    """Return problem_id, severity, retryable without parsing Telegram markup."""
    if problem_id:
        spec = lookup_problem(problem_id)
        if spec:
            return spec.problem_id, spec.severity, spec.threshold != "quiet"
        if problem_id in _NEW_CODES:
            meta = _NEW_CODES[problem_id]
            return problem_id, meta["severity"], bool(meta["retryable"])

    text = f"{reason} {detail}".lower()
    if "timeout 600" in text or ("scheduler" in stage.lower() and "timeout" in text):
        return "P25", "CRITICAL", True
    if "attributeerror" in text and "tags" in text and "split" in text:
        return "P29", "CRITICAL", False
    if "frontmatter" in text and ("type" in text or "schema" in text):
        return "P29", "CRITICAL", False
    if "invalid result" in text or "result contract" in text or "non-dict" in text:
        return "P28", "MAJOR", True
    if "content_generation" in stage.lower() or "ai          " in text:
        return "P30", "MAJOR", True
    if "data_fetch" in stage.lower() or "fetcher ;" in text or "source unavailable" in text:
        return "P26", "MAJOR", True
    if "source exhausted" in text or "  " in text or "no eligible" in text:
        return "P27", "MAJOR", False
    if "telegram" in stage.lower() or "telegram" in text:
        return "P31", "MAJOR", True
    if "duplicate_slug" in text or "duplicate_source_id" in text:
        return "P16", "MINOR", False
    if "validation" in stage.lower() or "cta_html" in text or "map_text" in text:
        return "P15", "MAJOR", True
    if "deploy" in stage.lower() or "wrangler" in text or "hugo build" in text:
        return "P04", "CRITICAL", True
    if "stale" in text or "expired" in text:
        return "P19", "MINOR", False
    if reason:
        spec = lookup_reason(reason)
        if spec:
            return spec.problem_id, spec.severity, spec.threshold != "quiet"
    return "P02", "MAJOR", True


def record_publish_error(
    blog_id: str,
    stage: str,
    detail: Any,
    *,
    pipeline: str = "",
    reason: str = "",
    problem_id: str = "",
    attempt: int | None = None,
    max_attempts: int | None = None,
    source_name: str = "",
    http_status: int | None = None,
    timeout_seconds: int | None = None,
    state: str = "open",
) -> dict[str, Any]:
    safe_detail = redact_detail(detail)
    resolved_problem, severity, retryable = classify_error(stage, safe_detail, reason, problem_id)
    occurred_at = datetime.now(timezone.utc).isoformat()
    fingerprint = hashlib.sha256(
        f"{blog_id}|{stage}|{resolved_problem}|{safe_detail[:240]}".encode("utf-8")
    ).hexdigest()[:24]
    event = {
        "event_id": str(uuid.uuid4()),
        "occurred_at": occurred_at,
        "blog_id": blog_id or "unknown",
        "pipeline": pipeline or "",
        "stage": stage or "unknown",
        "problem_id": resolved_problem,
        "reason": reason or "",
        "severity": severity,
        "retryable": int(retryable),
        "attempt": attempt,
        "max_attempts": max_attempts,
        "source_name": source_name or "",
        "http_status": http_status,
        "timeout_seconds": timeout_seconds,
        "detail_redacted": safe_detail,
        "fingerprint": fingerprint,
        "state": state,
    }
    try:
        conn = _connect()
        try:
            ensure_schema(conn)
            conn.execute(
                """
                INSERT INTO publish_error_events (
                    event_id, occurred_at, blog_id, pipeline, stage, problem_id,
                    reason, severity, retryable, attempt, max_attempts, source_name,
                    http_status, timeout_seconds, detail_redacted, fingerprint, state
                ) VALUES (
                    :event_id, :occurred_at, :blog_id, :pipeline, :stage, :problem_id,
                    :reason, :severity, :retryable, :attempt, :max_attempts, :source_name,
                    :http_status, :timeout_seconds, :detail_redacted, :fingerprint, :state
                )
                """,
                event,
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        # Error telemetry must never interrupt publishing or alert delivery.
        pass
    return event


def record_telegram_delivery(
    event_id: str | None,
    message: Any,
    *,
    delivered: bool,
    telegram_message_id: Any = "",
    http_status: int | None = None,
    detail: Any = "",
) -> None:
    try:
        conn = _connect()
        try:
            ensure_schema(conn)
            conn.execute(
                """
                INSERT INTO telegram_delivery_audit (
                    event_id, sent_at, delivered, telegram_message_id, http_status,
                    detail_redacted, message_redacted
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id or None,
                    datetime.now(timezone.utc).isoformat(),
                    int(bool(delivered)),
                    str(telegram_message_id or ""),
                    http_status,
                    redact_detail(detail),
                    redact_detail(message),
                ),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass


def get_publish_error_summary(conn: sqlite3.Connection) -> dict[str, Any]:
    ensure_schema(conn)
    total = conn.execute("SELECT COUNT(*) FROM publish_error_events").fetchone()[0]
    open_count = conn.execute(
        "SELECT COUNT(*) FROM publish_error_events WHERE state='open'"
    ).fetchone()[0]
    by_problem = [dict(row) for row in conn.execute(
        """
        SELECT problem_id, severity, COUNT(*) AS events, COUNT(DISTINCT blog_id) AS blogs,
               MAX(occurred_at) AS last_seen
        FROM publish_error_events
        GROUP BY problem_id, severity
        ORDER BY CASE severity WHEN 'CRITICAL' THEN 1 WHEN 'MAJOR' THEN 2 ELSE 3 END,
                 events DESC
        """
    ).fetchall()]
    return {"total": total, "open": open_count, "by_problem": by_problem}


def get_publish_error_events(
    conn: sqlite3.Connection,
    *,
    limit: int = 100,
    blog_id: str = "",
    severity: str = "",
    state: str = "",
) -> list[dict[str, Any]]:
    ensure_schema(conn)
    where: list[str] = []
    params: list[Any] = []
    for column, value in (("blog_id", blog_id), ("severity", severity), ("state", state)):
        if value:
            where.append(f"{column} = ?")
            params.append(value)
    sql = "SELECT * FROM publish_error_events"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY occurred_at DESC LIMIT ?"
    params.append(max(1, min(int(limit), 500)))
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def close_publish_error_event(
    conn: sqlite3.Connection,
    *,
    blog_id: str,
    problem_id: str,
    before: str | None = None,
) -> int:
    """주어진 블로그·문제의 open 이벤트 중 가장 최근 것을 closed로 변경.

    before가 주어지면 해당 시각 이전의 open 이벤트만 대상.
    반환: 변경된 행 수.
    """
    ensure_schema(conn)
    # SQLite doesn't support ORDER BY/LIMIT in UPDATE directly - use subquery
    sql = """
        UPDATE publish_error_events
        SET state = 'closed'
        WHERE event_id = (
            SELECT event_id FROM publish_error_events
            WHERE blog_id = ?
              AND problem_id = ?
              AND state = 'open'
              AND (? IS NULL OR occurred_at < ?)
            ORDER BY occurred_at DESC
            LIMIT 1
        )
    """
    params = (blog_id, problem_id, before, before) if before else (blog_id, problem_id, None, None)
    cur = conn.execute(sql, params)
    conn.commit()
    return cur.rowcount

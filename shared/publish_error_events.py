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
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    incident_key TEXT,
    key_version INTEGER NOT NULL DEFAULT 2,
    occurrence_count INTEGER NOT NULL DEFAULT 1,
    first_seen_at TEXT,
    last_seen_at TEXT,
    resolved_at TEXT
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


# PR1: incident 단위 집계 컬럼. 기존 행은 incident_key NULL로 유지(자동 삭제/병합 없음).
# canonical key(v2) = sha256("v2|blog|" + blog_id + "|" + stage + "|" + problem_id + "|" + normalized_reason [+ "|" + resource_id])
# detail/occurred_at/consecutive는 key에서 제외. 기존 fingerprint(detail 포함)는 호환용으로 유지.
_INCIDENT_COLUMNS: dict[str, str] = {
    "incident_key": "TEXT",
    "key_version": "INTEGER NOT NULL DEFAULT 2",
    "occurrence_count": "INTEGER NOT NULL DEFAULT 1",
    "first_seen_at": "TEXT",
    "last_seen_at": "TEXT",
    "resolved_at": "TEXT",
}

# 동시성 안전성: open 상태의 동일 incident는 partial UNIQUE index가 1행으로 강제한다.
# closed 행은 인덱스에서 빠지므로 재발 시 새 incident 행 생성이 가능하다.
_OPEN_INCIDENT_INDEX_SQL = (
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_publish_error_open_incident "
    "ON publish_error_events(incident_key) "
    "WHERE state='open' AND incident_key IS NOT NULL"
)

_REASON_ALIASES = {
    "no_topic": "no_topics",  # 단수/복수 표현 통일
}


def _normalize_reason(reason: str) -> str:
    """reason alias 정규화 — 소문자+strip 후 알려진 alias만 통일.

    problem_id로 매핑하지 않는다(no_result/no_topics가 모두 P01이어도
    본질이 다르므로 서로 다른 incident로 유지한다).
    """
    normalized = (reason or "").strip().lower()
    return _REASON_ALIASES.get(normalized, normalized)


def compute_incident_key(
    blog_id: str,
    stage: str,
    problem_id: str,
    reason: str = "",
    resource_id: str = "",
    key_version: int = 2,
) -> str:
    """canonical incident key (v2) — 안정적 필드만 사용.

    detail/occurred_at/consecutive는 제외되므로 동일 장애는 항상 같은 key를 가진다.
    resource_id가 주어지면(공용 소스/파이프라인 단위 root) key에 포함한다.
    """
    parts = [
        f"v{key_version}",
        "blog",
        blog_id or "unknown",
        stage or "unknown",
        problem_id,
        _normalize_reason(reason),
    ]
    if resource_id:
        parts.append(resource_id)
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:24]


def _migrate_schema(conn: sqlite3.Connection) -> None:
    """PRAGMA table_info + ALTER TABLE 기반 증분 migration — 여러 번 실행해도 안전.

    기존 행은 incident_key=NULL로 남는다(삭제/병합 없음). NULL은 partial index
    WHERE 절(incident_key IS NOT NULL) 밖이므로 기존 중복과 충돌하지 않는다.
    """
    columns = {row[1] for row in conn.execute("PRAGMA table_info(publish_error_events)")}
    for name, ddl in _INCIDENT_COLUMNS.items():
        if name not in columns:
            conn.execute(f"ALTER TABLE publish_error_events ADD COLUMN {name} {ddl}")
    conn.execute(_OPEN_INCIDENT_INDEX_SQL)


def ensure_schema(conn: sqlite3.Connection | None = None) -> None:
    owns_connection = conn is None
    target = conn or _connect()
    try:
        target.executescript(_SCHEMA_SQL)
        _migrate_schema(target)
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
    resource_id: str = "",
) -> dict[str, Any]:
    safe_detail = redact_detail(detail)
    resolved_problem, severity, retryable = classify_error(stage, safe_detail, reason, problem_id)
    occurred_at = datetime.now(timezone.utc).isoformat()
    # 기존 fingerprint(detail 포함)는 호환용으로 유지 — incident key로 사용하지 않는다.
    fingerprint = hashlib.sha256(
        f"{blog_id}|{stage}|{resolved_problem}|{safe_detail[:240]}".encode("utf-8")
    ).hexdigest()[:24]
    incident_key = compute_incident_key(
        blog_id, stage, resolved_problem, reason=reason, resource_id=resource_id
    )
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
        "incident_key": incident_key,
        "key_version": 2,
        "occurrence_count": 1,
        "first_seen_at": occurred_at,
        "last_seen_at": occurred_at,
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
                    http_status, timeout_seconds, detail_redacted, fingerprint, state,
                    incident_key, key_version, occurrence_count, first_seen_at, last_seen_at
                ) VALUES (
                    :event_id, :occurred_at, :blog_id, :pipeline, :stage, :problem_id,
                    :reason, :severity, :retryable, :attempt, :max_attempts, :source_name,
                    :http_status, :timeout_seconds, :detail_redacted, :fingerprint, :state,
                    :incident_key, :key_version, :occurrence_count, :first_seen_at, :last_seen_at
                )
                ON CONFLICT(incident_key) WHERE state='open' AND incident_key IS NOT NULL
                DO UPDATE SET
                    occurrence_count = occurrence_count + 1,
                    occurred_at = excluded.occurred_at,
                    last_seen_at = excluded.occurred_at,
                    detail_redacted = excluded.detail_redacted,
                    severity = excluded.severity,
                    retryable = excluded.retryable,
                    pipeline = excluded.pipeline,
                    reason = excluded.reason,
                    source_name = excluded.source_name,
                    http_status = excluded.http_status,
                    timeout_seconds = excluded.timeout_seconds,
                    attempt = excluded.attempt,
                    max_attempts = excluded.max_attempts
                """,
                event,
            )
            conn.commit()
            # 반환 event는 실제 DB 행과 일치시킨다 (telegram_delivery_audit FK 정합).
            # open 행은 partial UNIQUE index로 incident_key당 최대 1개가 보장되므로,
            # state='open' 필터 + rowid 정렬로 "현재 upsert 대상 open 행"을 결정적으로
            # 조회한다 (closed/open 이력이 공존해도 closed 행은 반환되지 않는다).
            row = conn.execute(
                "SELECT event_id, occurrence_count, first_seen_at, last_seen_at "
                "FROM publish_error_events "
                "WHERE incident_key = ? AND state = 'open' "
                "ORDER BY rowid DESC LIMIT 1",
                (incident_key,),
            ).fetchone()
            if row:
                event["event_id"] = row["event_id"]
                event["occurrence_count"] = row["occurrence_count"]
                event["first_seen_at"] = row["first_seen_at"]
                event["last_seen_at"] = row["last_seen_at"]
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
    incident_key: str | None = None,
) -> int:
    """조건에 맞는 open incident를 모두 closed로 전환.

    - incident_key가 주어지면 해당 incident만 닫는다 (무관한 problem/root를 함께 닫지 않음).
    - incident_key가 없으면 blog_id+problem_id(+before)에 해당하는 open 전부를 닫는다
      (기존 caller 호환 — LIMIT 1에 의존하지 않는다).
    - resolved_at을 함께 갱신하고, occurrence_count/first_seen_at은 보존한다.
    - 이미 closed인 행은 state='open' 조건으로 제외되므로 재호출이 안전하다.
    반환: 변경된 행 수.
    """
    ensure_schema(conn)
    now = datetime.now(timezone.utc).isoformat()
    if incident_key:
        sql = """
            UPDATE publish_error_events
            SET state = 'closed', resolved_at = ?
            WHERE state = 'open' AND incident_key = ?
        """
        params: tuple[Any, ...] = (now, incident_key)
    else:
        sql = """
            UPDATE publish_error_events
            SET state = 'closed', resolved_at = ?
            WHERE state = 'open'
              AND blog_id = ?
              AND problem_id = ?
              AND (? IS NULL OR occurred_at < ?)
        """
        params = (now, blog_id, problem_id, before, before) if before else (
            now, blog_id, problem_id, None, None)
    cur = conn.execute(sql, params)
    conn.commit()
    return cur.rowcount

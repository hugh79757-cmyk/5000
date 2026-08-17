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

CREATE TABLE IF NOT EXISTS resource_health (
    resource_id TEXT PRIMARY KEY,
    job_name TEXT NOT NULL DEFAULT '',
    last_started_at TEXT,
    last_completed_at TEXT,
    last_success_at TEXT,
    last_failure_at TEXT,
    last_error_reason TEXT NOT NULL DEFAULT '',
    duration_seconds REAL,
    rows_inserted INTEGER,
    heartbeat_at TEXT,
    state TEXT NOT NULL DEFAULT 'unknown'
);

-- Catchup 재시도 횟수 영속화: scheduler 재시작 시에도 일일 블로그별 시도 횟수 유지.
-- attempt_date 키로 새 날짜가 되면 자동으로 새 window (리셋 효과).
CREATE TABLE IF NOT EXISTS catchup_attempts (
    blog_id TEXT NOT NULL,
    attempt_date TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (blog_id, attempt_date)
);

-- PR3: 후보 가용성 SSOT (candidate availability).
-- key = blog_id + pipeline + resource_id + candidate_type. 중복 상태 저장소 없이
-- ops.db 한 곳에서 healthy/waiting_for_candidates/blocked_by_source/recovering/unknown 관리.
CREATE TABLE IF NOT EXISTS pipeline_availability (
    blog_id TEXT NOT NULL,
    pipeline TEXT NOT NULL DEFAULT '',
    resource_id TEXT NOT NULL DEFAULT '',
    candidate_type TEXT NOT NULL DEFAULT '',
    state TEXT NOT NULL DEFAULT 'unknown',
    available_count INTEGER NOT NULL DEFAULT 0,
    reason TEXT NOT NULL DEFAULT '',
    source_health_state TEXT NOT NULL DEFAULT '',
    linked_incident_key TEXT NOT NULL DEFAULT '',
    checked_at TEXT NOT NULL,
    next_check_at TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (blog_id, pipeline, resource_id, candidate_type)
);
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
    # busy_timeout을 먼저 설정해야 WAL 전환 pragma가 lock 대기를 할 수 있다.
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except sqlite3.OperationalError:
        # DB가 이미 WAL이거나 다른 연결이 쓰기 중이면 전환 요청이 lock으로
        # 실패할 수 있다 — WAL 유지 상태에서는 무해하므로 무시한다.
        pass
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

# PR2 (Phase 74): root/symptom/amplifier 관계 + retry 제어. UI는 detail 파싱 대신
# 구조화 컬럼만 사용한다. retry_count/retry_blocked는 upsert(DO UPDATE)에서 제외 —
# 누적/제어 전용이며 record_publish_error 재호출로 초기화되지 않는다.
_PR2_COLUMNS: dict[str, str] = {
    "relation_type": "TEXT NOT NULL DEFAULT ''",
    "root_incident_key": "TEXT",
    "resource_id": "TEXT NOT NULL DEFAULT ''",
    "retry_blocked": "INTEGER NOT NULL DEFAULT 0",
    "retry_count": "INTEGER NOT NULL DEFAULT 0",
    "metadata_json": "TEXT",
}

# PR2 안정화: resource_health bootstrap 이력. first_observed_at/first_failure_at은
# 첫 관측 시각(COALESCE로 한 번만 기록) — 파일 mtime 등 비구조화 근거로 백필하지 않는다.
# health_confidence: unknown(이력 전무) / observed(실행 시작·실패 관측) / confirmed(성공 확인).
_RESOURCE_HEALTH_COLUMNS: dict[str, str] = {
    "first_observed_at": "TEXT",
    "first_failure_at": "TEXT",
    "evidence_source": "TEXT NOT NULL DEFAULT ''",
    "health_confidence": "TEXT NOT NULL DEFAULT 'unknown'",
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

# incident upsert의 일시적 lock/busy 실패 허용 횟수. busy_timeout(5s)이
# 대부분의 대기를 흡수하므로 재시도는 짧고 제한적으로만 둔다.
_MAX_RECORD_ATTEMPTS = 3


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


def _add_column_if_missing(
    conn: sqlite3.Connection, table: str, name: str, ddl: str
) -> None:
    """ALTER TABLE ADD COLUMN은 IF NOT EXISTS가 없다.

    병렬 migration에서 두 연결이 같은 컬럼을 동시에 추가하면
    "duplicate column name"이 난다 — 이미 다른 스레드가 추가한 것이므로
    그 경우만 무시하고, 다른 오류는 그대로 전파한다.
    """
    try:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")
    except sqlite3.OperationalError as exc:
        if "duplicate column" not in str(exc).lower():
            raise


def _migrate_schema(conn: sqlite3.Connection) -> None:
    """PRAGMA table_info + ALTER TABLE 기반 증분 migration — 여러 번 실행해도 안전.

    기존 행은 incident_key=NULL로 남는다(삭제/병합 없음). NULL은 partial index
    WHERE 절(incident_key IS NOT NULL) 밖이므로 기존 중복과 충돌하지 않는다.
    """
    columns = {row[1] for row in conn.execute("PRAGMA table_info(publish_error_events)")}
    for name, ddl in _INCIDENT_COLUMNS.items():
        if name not in columns:
            _add_column_if_missing(conn, "publish_error_events", name, ddl)
    for name, ddl in _PR2_COLUMNS.items():
        if name not in columns:
            _add_column_if_missing(conn, "publish_error_events", name, ddl)
    conn.execute(_OPEN_INCIDENT_INDEX_SQL)
    rh_columns = {row[1] for row in conn.execute("PRAGMA table_info(resource_health)")}
    for name, ddl in _RESOURCE_HEALTH_COLUMNS.items():
        if name not in rh_columns:
            _add_column_if_missing(conn, "resource_health", name, ddl)


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
    retryable: bool | None = None,
    relation_type: str = "",
    root_incident_key: str = "",
    retry_blocked: int = 0,
    metadata_json: str = "",
) -> dict[str, Any]:
    safe_detail = redact_detail(detail)
    resolved_problem, severity, resolved_retryable = classify_error(stage, safe_detail, reason, problem_id)
    if retryable is not None:
        resolved_retryable = retryable
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
        "retryable": int(resolved_retryable),
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
        "relation_type": relation_type or "",
        "root_incident_key": root_incident_key or "",
        "resource_id": resource_id or "",
        "retry_blocked": int(retry_blocked),
        "retry_count": 0,
        "metadata_json": metadata_json or "",
    }
    # identity는 DB가 최종 권위자다. caller가 미리 만든 uuid4를 성공 ID로
    # 반환하지 않는다 — upsert+commit 후 실제 open 행의 event_id로 교체하고,
    # 확정하지 못하면 event_id를 ""(명시적 실패 신호)로 둔다.
    persisted = False
    for _attempt in range(_MAX_RECORD_ATTEMPTS):
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
                        incident_key, key_version, occurrence_count, first_seen_at, last_seen_at,
                        relation_type, root_incident_key, resource_id, retry_blocked, retry_count, metadata_json
                    ) VALUES (
                        :event_id, :occurred_at, :blog_id, :pipeline, :stage, :problem_id,
                        :reason, :severity, :retryable, :attempt, :max_attempts, :source_name,
                        :http_status, :timeout_seconds, :detail_redacted, :fingerprint, :state,
                        :incident_key, :key_version, :occurrence_count, :first_seen_at, :last_seen_at,
                        :relation_type, :root_incident_key, :resource_id, :retry_blocked, :retry_count, :metadata_json
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
                        max_attempts = excluded.max_attempts,
                        relation_type = excluded.relation_type,
                        root_incident_key = excluded.root_incident_key,
                        resource_id = excluded.resource_id,
                        metadata_json = excluded.metadata_json
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
                    persisted = True
                # row가 없으면 upsert는 커밋됐으나 동시 close로 open 행이 소멸한 것 —
                # 성공 ID로 확정할 수 없으므로 persisted=False로 두고 event_id를 비운다.
            finally:
                conn.close()
            break
        except Exception:
            # 일시적 lock/busy는 짧고 제한적으로 재시도한다. 재시도 소진 시
            # phantom uuid4 대신 event_id=""로 명시적 실패를 반환한다
            # (Error telemetry must never interrupt publishing or alert delivery).
            continue
    if not persisted:
        event["event_id"] = ""
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


# --- PR2 (Phase 74): refresh health + root/symptom/amplifier 관계 + catchup retry 제어 ---

DEFAULT_STALLED_RESOURCE_ID = "car.db/daily_refresh"

# resource_health 이력의 근거 출처 — bootstrap/백필 시 근거 시각+source를 함께 남긴다.
EVIDENCE_SOURCE = "scheduler._run_car_refresh"


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def record_resource_start(resource_id: str, job_name: str = "") -> None:
    """refresh job 시작 기록 — state='running', last_started_at/heartbeat_at 갱신.

    first_observed_at는 최초 관측 시각만 유지(COALESCE), health_confidence='observed'.
    """
    try:
        conn = _connect()
        try:
            ensure_schema(conn)
            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                """
                INSERT INTO resource_health (
                    resource_id, job_name, last_started_at, heartbeat_at, state,
                    first_observed_at, evidence_source, health_confidence
                )
                VALUES (?, ?, ?, ?, 'running', ?, ?, 'observed')
                ON CONFLICT(resource_id) DO UPDATE SET
                    job_name = excluded.job_name,
                    last_started_at = excluded.last_started_at,
                    heartbeat_at = excluded.heartbeat_at,
                    state = 'running',
                    first_observed_at = COALESCE(resource_health.first_observed_at, excluded.first_observed_at),
                    evidence_source = excluded.evidence_source,
                    health_confidence = 'observed'
                """,
                (resource_id, job_name or "", now, now, now, EVIDENCE_SOURCE),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass


def record_resource_heartbeat(resource_id: str) -> None:
    """refresh 실행 중 heartbeat 갱신 (watchdog stale 방지 보조). 실패는 무시."""
    try:
        conn = _connect()
        try:
            ensure_schema(conn)
            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                "UPDATE resource_health SET heartbeat_at = ? WHERE resource_id = ?",
                (now, resource_id),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass


def _record_resource_finish(
    resource_id: str,
    state: str,
    *,
    rows_inserted: int | None = None,
    duration_seconds: float | None = None,
    error_reason: str = "",
) -> None:
    try:
        conn = _connect()
        try:
            ensure_schema(conn)
            now = datetime.now(timezone.utc).isoformat()
            sets = ["state = ?", "last_completed_at = ?", "heartbeat_at = ?", "last_error_reason = ?"]
            params: list[Any] = [state, now, now, (error_reason or "")[:500]]
            if state == "success":
                sets.append("last_success_at = ?")
                params.append(now)
                sets.append("health_confidence = 'confirmed'")
            else:
                # first_failure_at은 최초 실패 시각만 유지 (재실패로 갱신되지 않음).
                sets.append("last_failure_at = ?")
                params.append(now)
                sets.append("first_failure_at = COALESCE(first_failure_at, ?)")
                params.append(now)
                sets.append("health_confidence = 'observed'")
            if rows_inserted is not None:
                sets.append("rows_inserted = ?")
                params.append(int(rows_inserted))
            if duration_seconds is not None:
                sets.append("duration_seconds = ?")
                params.append(float(duration_seconds))
            params.append(resource_id)
            conn.execute(
                f"UPDATE resource_health SET {', '.join(sets)} WHERE resource_id = ?",
                params,
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass


def record_resource_success(
    resource_id: str, *, rows_inserted: int | None = None, duration_seconds: float | None = None
) -> None:
    _record_resource_finish(resource_id, "success", rows_inserted=rows_inserted, duration_seconds=duration_seconds)


def record_resource_failure(resource_id: str, *, error_reason: str = "", duration_seconds: float | None = None) -> None:
    _record_resource_finish(resource_id, "failed", error_reason=error_reason, duration_seconds=duration_seconds)


def record_resource_timeout(resource_id: str, *, duration_seconds: float | None = None) -> None:
    _record_resource_finish(resource_id, "timeout", error_reason="timeout", duration_seconds=duration_seconds)


def get_resource_health(resource_id: str) -> dict[str, Any] | None:
    """resource_health 행 반환 — 없으면 None. 읽기 전용."""
    try:
        conn = _connect()
        try:
            ensure_schema(conn)
            row = conn.execute(
                "SELECT * FROM resource_health WHERE resource_id = ?", (resource_id,)
            ).fetchone()
            return _row_to_dict(row)
        finally:
            conn.close()
    except Exception:
        return None


def get_resource_health_rows() -> list[dict[str, Any]]:
    """resource_health 전체 행 반환 — PR3 대시보드 refresh 상태 표시용. 읽기 전용."""
    try:
        conn = _connect()
        try:
            ensure_schema(conn)
            rows = conn.execute(
                "SELECT * FROM resource_health ORDER BY resource_id"
            ).fetchall()
            return [_row_to_dict(r) for r in rows]
        finally:
            conn.close()
    except Exception:
        return []


def get_open_incident(
    blog_id: str,
    problem_id: str,
    reason: str = "",
    resource_id: str = "",
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any] | None:
    """open 상태 incident 1건 조회 — 없으면 None. conn 미지정 시 자동 연결(읽기 전용)."""
    owns = conn is None
    target = conn or _connect()
    try:
        ensure_schema(target)
        where = ["state = 'open'", "blog_id = ?", "problem_id = ?"]
        params: list[Any] = [blog_id, problem_id]
        if reason:
            # 저장된 reason은 원본 그대로이므로 정규화 전/후 모두 매치한다 (no_topic/no_topics).
            norm = _normalize_reason(reason)
            where.append("(reason = ? OR reason = ?)")
            params.extend([norm, reason])
        if resource_id:
            where.append("resource_id = ?")
            params.append(resource_id)
        row = target.execute(
            f"SELECT * FROM publish_error_events WHERE {' AND '.join(where)} "
            "ORDER BY rowid DESC LIMIT 1",
            params,
        ).fetchone()
        return _row_to_dict(row)
    finally:
        if owns:
            target.close()


def get_open_root_incident(resource_id: str) -> dict[str, Any] | None:
    """resource 단위 공용 root open incident 조회 (blog별 3건 중복 방지)."""
    try:
        conn = _connect()
        try:
            ensure_schema(conn)
            row = conn.execute(
                "SELECT * FROM publish_error_events "
                "WHERE state = 'open' AND relation_type = 'root' AND resource_id = ? "
                "ORDER BY rowid DESC LIMIT 1",
                (resource_id,),
            ).fetchone()
            return _row_to_dict(row)
        finally:
            conn.close()
    except Exception:
        return None


def get_open_root_incidents() -> list[dict[str, Any]]:
    """전체 open root incident 목록 (P33 source_refresh_stalled 등).

    PR3 대시보드의 'OPEN ROOT INCIDENTS' 요약과 incident 화면에서 사용한다.
    """
    try:
        conn = _connect()
        try:
            ensure_schema(conn)
            rows = conn.execute(
                "SELECT * FROM publish_error_events "
                "WHERE state = 'open' AND relation_type = 'root' "
                "ORDER BY rowid DESC"
            ).fetchall()
            return [_row_to_dict(r) for r in rows]
        finally:
            conn.close()
    except Exception:
        return []


def get_linked_open_events(root_incident_key: str) -> list[dict[str, Any]]:
    """root incident에 연결된 open symptom/amplifier 목록.

    root_incident_key가 일치하는 open 이벤트를 relation_type(amplifier 우선) 순으로
    반환한다. legacy 행(relation_type NULL, incident_key 없음)은 제외된다.
    """
    try:
        conn = _connect()
        try:
            ensure_schema(conn)
            rows = conn.execute(
                "SELECT * FROM publish_error_events "
                "WHERE state = 'open' AND root_incident_key = ? "
                "ORDER BY CASE relation_type WHEN 'amplifier' THEN 0 ELSE 1 END, rowid",
                (root_incident_key,),
            ).fetchall()
            return [_row_to_dict(r) for r in rows]
        finally:
            conn.close()
    except Exception:
        return []


def get_retry_blocked_count() -> int:
    """retry_blocked=1인 open incident 수 (catchup 차단 중인 blog 규모)."""
    try:
        conn = _connect()
        try:
            ensure_schema(conn)
            row = conn.execute(
                "SELECT COUNT(*) FROM publish_error_events "
                "WHERE state = 'open' AND retry_blocked = 1"
            ).fetchone()
            return int(row[0]) if row else 0
        finally:
            conn.close()
    except Exception:
        return 0


def get_catchup_retry_state(blog_id: str) -> dict[str, Any] | None:
    """blog의 open no_topics symptom retry 상태 — 없으면 None.

    반환: incident_key / retry_count / retry_blocked / root_incident_key.
    ops.db SSOT 기반이라 scheduler 재시작 후에도 유지된다.

    같은 blog에 open no_topics incident가 여러 개여도(legacy/신규 incident_key
    분리로 retry_blocked가 행마다 다를 수 있음) retry_blocked=1인 행이 하나라도
    있으면 그 행을 우선 반환한다. 정규 schedule 실패가 새 incident(retry_blocked=0)를
    만들더라도 기존 차단이 무력화되지 않도록 blocked 행을 최신 행보다 우선한다.
    """
    try:
        conn = _connect()
        try:
            ensure_schema(conn)
            row = conn.execute(
                "SELECT incident_key, retry_count, retry_blocked, root_incident_key "
                "FROM publish_error_events "
                "WHERE state = 'open' AND blog_id = ? AND problem_id = 'P01' "
                "AND (reason = 'no_topics' OR reason = 'no_topic') "
                "ORDER BY retry_blocked DESC, rowid DESC LIMIT 1",
                (blog_id,),
            ).fetchone()
        finally:
            conn.close()
    except Exception:
        return None
    if not row:
        return None
    return {
        "incident_key": row["incident_key"],
        "retry_count": row["retry_count"] or 0,
        "retry_blocked": bool(row["retry_blocked"]),
        "root_incident_key": row["root_incident_key"] or "",
    }


def get_catchup_attempts(blog_id: str, attempt_date: str) -> int:
    """일일 블로그별 catchup 시도 횟수 — ops.db SSOT 기반이라 재시작 후에도 유지."""
    try:
        conn = _connect()
        try:
            ensure_schema(conn)
            row = conn.execute(
                "SELECT attempts FROM catchup_attempts WHERE blog_id=? AND attempt_date=?",
                (blog_id, attempt_date),
            ).fetchone()
        finally:
            conn.close()
    except Exception:
        return 0
    return int(row["attempts"]) if row else 0


def set_catchup_attempts(blog_id: str, attempt_date: str, attempts: int) -> None:
    """catchup 시도 횟수 기록 (UPSERT — 새 날짜면 자동으로 새 window)."""
    try:
        conn = _connect()
        try:
            ensure_schema(conn)
            conn.execute(
                "INSERT INTO catchup_attempts (blog_id, attempt_date, attempts) VALUES (?, ?, ?) "
                "ON CONFLICT(blog_id, attempt_date) DO UPDATE SET "
                "attempts=excluded.attempts, updated_at=CURRENT_TIMESTAMP",
                (blog_id, attempt_date, attempts),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        return None


def increment_incident_retry(blog_id: str, problem_id: str, reason: str = "") -> bool:
    """open incident의 retry_count를 1 증가 (catchup 재실행 횟수 — occurrence_count와 별개)."""
    incident = get_open_incident(blog_id, problem_id, reason=reason)
    if not incident or not incident.get("incident_key"):
        return False
    try:
        conn = _connect()
        try:
            ensure_schema(conn)
            conn.execute(
                "UPDATE publish_error_events SET retry_count = retry_count + 1 "
                "WHERE state = 'open' AND incident_key = ?",
                (incident["incident_key"],),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        return False
    return True


def set_incident_retry_blocked(blog_id: str, problem_id: str, blocked: bool, reason: str = "") -> bool:
    """open incident의 retry_blocked 설정 — pending 복구/symptom close 시 해제(False)."""
    incident = get_open_incident(blog_id, problem_id, reason=reason)
    if not incident or not incident.get("incident_key"):
        return False
    try:
        conn = _connect()
        try:
            ensure_schema(conn)
            conn.execute(
                "UPDATE publish_error_events SET retry_blocked = ? "
                "WHERE state = 'open' AND incident_key = ?",
                (int(bool(blocked)), incident["incident_key"]),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        return False
    return True


def link_incident_to_root(conn: sqlite3.Connection, incident_key: str, root_incident_key: str) -> None:
    """symptom/amplifier incident를 root incident key에 연결 (root 확인 후에만)."""
    try:
        conn.execute(
            "UPDATE publish_error_events SET root_incident_key = ? WHERE incident_key = ?",
            (root_incident_key or "", incident_key),
        )
        conn.commit()
    except Exception:
        pass


def record_retry_amplification(blog_id: str, root_incident_key: str = "") -> dict[str, Any]:
    """retry 제한 초과 시 amplifier(P34) incident upsert.

    incident_key는 blog_id 단위로 고정 → open 1행 유지 (매 5분 신규 행 생성 금지).
    """
    return record_publish_error(
        blog_id,
        "catchup",
        "retry_amplification: 동일 candidate_exhausted catchup 3회 초과 — 해당 incident 자동 제외",
        reason="retry_amplification",
        problem_id="P34",
        relation_type="amplifier",
        retry_blocked=1,
        root_incident_key=root_incident_key,
        retryable=False,
    )


def evaluate_and_open_root_stalled(
    resource_id: str = DEFAULT_STALLED_RESOURCE_ID,
    sla_hours: int = 36,
    now: str | None = None,
) -> dict[str, Any] | None:
    """SLA 위반 3조건(A+B+C) 모두 충족 시 P33 root incident upsert (멱등).

    A. 마지막 성공(last_success_at)이 sla_hours 초과 또는 성공 기록 없음
       - 성공 기록도 없고 실패 관측(first_failure_at)도 없으면(UNKNOWN) 판정 불가 → None
       - 성공 기록 없이 실패 관측만 있으면(OBSERVED) 실패 관측(first_failure_at)과
         마지막 실패(last_failure_at) 중 더 오래된 시각 기준으로 SLA 판정
    B. 마지막 실행이 success가 아님(running/failed/timeout) 또는 완료 증거(last_completed_at) 없음
    C. 마지막 성공 rows_inserted == 0 또는 NULL (신규 candidate 유입 0)
    실행 기록 자체가 없으면 None (단독 근거 금지 — 파일 mtime 등 비구조화 근거로 생성하지 않는다).
    """
    health = get_resource_health(resource_id)
    if health is None:
        return None
    now_dt = datetime.fromisoformat(now) if now else datetime.now(timezone.utc)
    last_success = health.get("last_success_at")
    first_failure = health.get("first_failure_at")
    condition_a = False
    if last_success:
        try:
            condition_a = (now_dt - datetime.fromisoformat(last_success)).total_seconds() > sla_hours * 3600
        except ValueError:
            condition_a = False
    elif first_failure:
        # bootstrap: 성공 이력 없는 자원은 실패 관측(first_failure_at)과 마지막
        # 실패(last_failure_at) 중 더 오래된 시각부터 정체로 간주 (둘 다 없을 수 없음 —
        # first_failure_at 존재가 전제). last_success가 없으면 그 사이 성공이 없었다는
        # 뜻이므로 first_failure_at이 오래됐으면 정체 지속으로 본다.
        stall_candidates = [
            ts for ts in (health.get("first_failure_at"), health.get("last_failure_at")) if ts
        ]
        stall_since = min(stall_candidates)
        try:
            condition_a = (now_dt - datetime.fromisoformat(stall_since)).total_seconds() > sla_hours * 3600
        except ValueError:
            condition_a = False
    else:
        # UNKNOWN — 이력 전무. 판정 불가 → root 생성 금지.
        return None
    state = health.get("state") or "unknown"
    condition_b = state != "success" or not health.get("last_completed_at")
    condition_c = (health.get("rows_inserted") or 0) == 0
    if not (condition_a and condition_b and condition_c):
        return None
    existing = get_open_root_incident(resource_id)
    if existing:
        return existing
    root = record_publish_error(
        "resource",
        "resource_refresh",
        f"source_refresh_stalled: {resource_id} last_success={last_success}, "
        f"state={state}, rows_inserted={health.get('rows_inserted')}",
        reason="source_refresh_stalled",
        problem_id="P33",
        resource_id=resource_id,
        relation_type="root",
        retryable=False,
    )
    if root:
        _link_open_symptoms_to_root(root.get("incident_key"))
    return root


def _link_open_symptoms_to_root(root_incident_key: str | None) -> None:
    """root 생성 시 open candidate_exhausted(P01) symptom들을 root_incident_key로 연결.

    root가 확인된 symptom만 연결한다 (아직 root가 없는 독립 symptom은 그대로 둔다).
    """
    if not root_incident_key:
        return
    try:
        conn = _connect()
        try:
            ensure_schema(conn)
            conn.execute(
                "UPDATE publish_error_events SET root_incident_key = ? "
                "WHERE state = 'open' AND problem_id = 'P01' "
                "AND (root_incident_key IS NULL OR root_incident_key = '')",
                (root_incident_key,),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass


def close_root_stalled_if_healthy(resource_id: str = DEFAULT_STALLED_RESOURCE_ID) -> int:
    """refresh 성공이 확인되면 open P33 root close (발행 성공과 무관 — refresh 성공 증거로만).

    rows_inserted=0이어도 close 가능(정상 소진) — candidate symptom은 별개로 유지된다.
    """
    health = get_resource_health(resource_id)
    if not health or health.get("state") != "success":
        return 0
    root = get_open_root_incident(resource_id)
    if not root:
        return 0
    try:
        conn = _connect()
        try:
            ensure_schema(conn)
            now = datetime.now(timezone.utc).isoformat()
            cur = conn.execute(
                "UPDATE publish_error_events SET state = 'closed', resolved_at = ? "
                "WHERE state = 'open' AND incident_key = ?",
                (now, root["incident_key"]),
            )
            conn.commit()
            return cur.rowcount
        finally:
            conn.close()
    except Exception:
        return 0


def set_incident_retry_count(blog_id: str, problem_id: str, count: int, reason: str = "") -> bool:
    """open incident의 retry_count 설정 (해제 시 0으로 리셋)."""
    incident = get_open_incident(blog_id, problem_id, reason=reason)
    if not incident or not incident.get("incident_key"):
        return False
    try:
        conn = _connect()
        try:
            ensure_schema(conn)
            conn.execute(
                "UPDATE publish_error_events SET retry_count = ? "
                "WHERE state = 'open' AND incident_key = ?",
                (max(0, int(count)), incident["incident_key"]),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        return False
    return True


def release_blog_retry_state(blog_id: str) -> bool:
    """해당 blog의 retry 제한 상태 해제 — P01 symptom close + P34 amplifier close +
    retry_blocked 해제 + retry_count 리셋.

    pending 복구(신규 candidate 유입) 또는 발행 성공 시에만 호출한다.
    root(P33)는 건드리지 않는다 — root close는 refresh 성공 증거로만 가능.
    """
    ok = True
    # setter들은 open incident를 대상으로 하므로 close 전에 먼저 해제한다.
    ok = set_incident_retry_blocked(blog_id, "P01", False) and ok
    ok = set_incident_retry_count(blog_id, "P01", 0) and ok
    try:
        conn = _connect()
        try:
            ensure_schema(conn)
            now = datetime.now(timezone.utc).isoformat()
            for problem_id in ("P01", "P34"):
                conn.execute(
                    "UPDATE publish_error_events SET state = 'closed', resolved_at = ? "
                    "WHERE state = 'open' AND blog_id = ? AND problem_id = ?",
                    (now, blog_id, problem_id),
                )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        ok = False
    return ok


# ─── PR3: pipeline_availability (candidate availability SSOT) ───

_AVAILABILITY_STATES = (
    "healthy", "waiting_for_candidates", "blocked_by_source",
    "recovering", "unknown", "checker_error",
)


def upsert_availability(
    blog_id: str,
    pipeline: str = "",
    resource_id: str = "",
    candidate_type: str = "",
    state: str = "unknown",
    available_count: int = 0,
    reason: str = "",
    source_health_state: str = "",
    linked_incident_key: str = "",
    next_check_at: str = "",
) -> bool:
    """pipeline_availability upsert — 반복 호출해도 행은 1개 유지 (멱등)."""
    if state not in _AVAILABILITY_STATES:
        state = "unknown"
    try:
        conn = _connect()
        try:
            ensure_schema(conn)
            conn.execute(
                """
                INSERT INTO pipeline_availability (
                    blog_id, pipeline, resource_id, candidate_type, state,
                    available_count, reason, source_health_state,
                    linked_incident_key, checked_at, next_check_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(blog_id, pipeline, resource_id, candidate_type) DO UPDATE SET
                    state = excluded.state,
                    available_count = excluded.available_count,
                    reason = excluded.reason,
                    source_health_state = excluded.source_health_state,
                    linked_incident_key = excluded.linked_incident_key,
                    checked_at = excluded.checked_at,
                    next_check_at = excluded.next_check_at
                """,
                (
                    blog_id, pipeline, resource_id, candidate_type, state,
                    int(available_count), reason, source_health_state,
                    linked_incident_key,
                    datetime.now(timezone.utc).isoformat(), next_check_at,
                ),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        return False
    return True


def get_availability(
    blog_id: str,
    pipeline: str = "",
    resource_id: str = "",
    candidate_type: str = "",
) -> dict | None:
    """pipeline_availability 1건 조회 (없으면 None)."""
    try:
        conn = _connect()
        try:
            ensure_schema(conn)
            row = conn.execute(
                "SELECT * FROM pipeline_availability "
                "WHERE blog_id = ? AND pipeline = ? AND resource_id = ? AND candidate_type = ?",
                (blog_id, pipeline, resource_id, candidate_type),
            ).fetchone()
        finally:
            conn.close()
    except Exception:
        return None
    return dict(row) if row else None


def get_availability_all() -> list[dict]:
    """전체 pipeline_availability 행 — 대시보드/API용 (blog_id 순)."""
    try:
        conn = _connect()
        try:
            ensure_schema(conn)
            rows = conn.execute(
                "SELECT * FROM pipeline_availability ORDER BY blog_id"
            ).fetchall()
        finally:
            conn.close()
    except Exception:
        return []
    return [dict(r) for r in rows]


def get_availability_summary() -> dict[str, int]:
    """상태별 행 수 요약 — healthy/waiting/blocked/recovering/unknown/checker_error."""
    summary = {s: 0 for s in _AVAILABILITY_STATES}
    try:
        conn = _connect()
        try:
            ensure_schema(conn)
            for row in conn.execute(
                "SELECT state, COUNT(*) AS c FROM pipeline_availability GROUP BY state"
            ):
                summary[row["state"]] = row["c"]
        finally:
            conn.close()
    except Exception:
        pass
    return summary

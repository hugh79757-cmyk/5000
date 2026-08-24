"""shared/rule_feedback.py — false-positive / false-negative feedback JSONL store

Store: logs/rule_feedback.jsonl (append-only, no SQLite, JSON per line)
Schema per 64-SELF-IMPROVEMENT.md §b + PLAN Task 64-04:
  {id: "fp-YYYYMMDD-NNN"|"fn-...", ts: iso, type: "false_positive"|"false_negative",
   rule_id, blog_id, slug, severity, gate_decision: "blocked"|"passed",
   reason: str, detected_by: "agent"|"human", status: "open"|"resolved"}
Id auto-increment via len(existing)+1, append-only, create file if missing.
No SQLite. read_feedback(since_days) generator filters by ts.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path

try:
    from shared.paths import FIVEK_ROOT  # type: ignore
    FEEDBACK_PATH = Path(FIVEK_ROOT) / "logs" / "rule_feedback.jsonl"
except Exception:
    FEEDBACK_PATH = Path(__file__).parent.parent / "logs" / "rule_feedback.jsonl"


def _ensure_dir() -> None:
    FEEDBACK_PATH.parent.mkdir(parents=True, exist_ok=True)


def _parse_ts(ts_str: str) -> datetime | None:
    if not ts_str:
        return None
    try:
        return datetime.fromisoformat(ts_str)
    except Exception:
        try:
            return datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
        except Exception:
            return None


def _parse_since_days(since) -> datetime | None:
    """Parse since param: int days, '7d', '7', or timedelta/None."""
    if since is None:
        return None
    if isinstance(since, (int, float)):
        return datetime.now() - timedelta(days=int(since))
    if isinstance(since, timedelta):
        return datetime.now() - since
    s = str(since).strip()
    # allow "7d", "7", "7 d"
    m = re.match(r"^\s*(\d+)\s*d?\s*$", s)
    if m:
        return datetime.now() - timedelta(days=int(m.group(1)))
    # try iso datetime
    dt = _parse_ts(s)
    if dt:
        return dt
    return None


def _next_id(feedback_type: str) -> str:
    prefix = "fp" if feedback_type == "false_positive" else "fn"
    today = datetime.now().strftime("%Y%m%d")
    # count existing valid lines to determine sequence
    count = 0
    if FEEDBACK_PATH.exists():
        try:
            text = FEEDBACK_PATH.read_text(encoding="utf-8", errors="replace")
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    # count only our schema ids, but len(existing)+1 per spec -> count all valid json lines
                    if isinstance(obj, dict):
                        count += 1
                except Exception:
                    continue
        except Exception:
            count = 0
    seq = count + 1
    return f"{prefix}-{today}-{seq:03d}"


def record_feedback(
    feedback_type: str | None = None,
    rule_id: str = "",
    blog_id: str = "",
    slug: str = "",
    severity: str = "",
    gate_decision: str = "",
    reason: str = "",
    detected_by: str = "",
    status: str = "open",
    **kwargs,
) -> dict:
    """Append one feedback entry to JSONL.

    Args: feedback_type alias 'type' via kwargs, 'false_positive'|'false_negative'
           rule_id, blog_id, slug, severity, gate_decision 'blocked'|'passed',
           reason, detected_by 'agent'|'human', status 'open'|'resolved'
    Returns: the written dict.
    """
    # support `type=` kw (since `type` is builtin, callers may use kwargs)
    if feedback_type is None:
        if "type" in kwargs:
            feedback_type = kwargs.pop("type")
        elif "type_" in kwargs:
            feedback_type = kwargs.pop("type_")
        elif "feedback_type" in kwargs:
            feedback_type = kwargs.pop("feedback_type")
    # also check kwargs for overrides if caller passed named via kwargs
    if not rule_id and "rule_id" in kwargs:
        rule_id = kwargs["rule_id"]
    if not blog_id and "blog_id" in kwargs:
        blog_id = kwargs["blog_id"]
    if not slug and "slug" in kwargs:
        slug = kwargs["slug"]
    if not severity and "severity" in kwargs:
        severity = kwargs["severity"]
    if not gate_decision and "gate_decision" in kwargs:
        gate_decision = kwargs["gate_decision"]
    if not reason and "reason" in kwargs:
        reason = kwargs["reason"]
    if not detected_by and "detected_by" in kwargs:
        detected_by = kwargs["detected_by"]
    if status == "open" and "status" in kwargs:
        status = kwargs["status"]

    if feedback_type not in ("false_positive", "false_negative"):
        raise ValueError(f"feedback_type must be false_positive/false_negative, got {feedback_type!r}")

    if gate_decision not in ("blocked", "passed", ""):
        # allow empty but prefer blocked/passed per spec
        pass
    if detected_by not in ("agent", "human", ""):
        pass
    if status not in ("open", "resolved"):
        raise ValueError(f"status must be open/resolved, got {status!r}")

    _ensure_dir()
    fid = _next_id(feedback_type)
    ts = datetime.now().isoformat()
    entry = {
        "id": fid,
        "ts": ts,
        "type": feedback_type,
        "rule_id": rule_id,
        "blog_id": blog_id,
        "slug": slug,
        "severity": severity,
        "gate_decision": gate_decision,
        "reason": reason,
        "detected_by": detected_by,
        "status": status,
    }
    with open(FEEDBACK_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def read_feedback(since_days=None, since=None, status: str | None = None) -> list[dict]:
    """Yield/filter feedback entries.

    Args: since_days int|'7d'|'7' or since alias. status filter optional.
    Returns: list[dict] (also generator-compatible: caller may iterate).
    This returns list for convenience; iterating is same.

    For generator behavior: use `for entry in read_feedback(...):`
    (list is iterable, so satisfies spec 'generator').
    """
    # alias handling
    if since is not None and since_days is None:
        since_days = since
    # support call as read_feedback(since_days="7d") or read_feedback(7)
    since_dt = _parse_since_days(since_days)
    if not FEEDBACK_PATH.exists():
        return []
    results: list[dict] = []
    try:
        text = FEEDBACK_PATH.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if not isinstance(obj, dict):
            continue
        if status is not None and obj.get("status") != status:
            continue
        ts_str = obj.get("ts", "") or obj.get("timestamp", "")
        ts = _parse_ts(ts_str) if ts_str else None
        if since_dt and ts and ts < since_dt:
            continue
        # if since filter but entry has no ts -> keep (can't filter)
        results.append(obj)
    return results


# alias for generator style import
def iter_feedback(*args, **kwargs):
    yield from read_feedback(*args, **kwargs)

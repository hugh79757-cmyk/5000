"""Daily summary of notification events sent as a single Telegram message at 23:00.

Records events throughout the day, aggregates by problem_id at send time,
and formats a severity-grouped summary message for Telegram.
"""

import sqlite3
from datetime import datetime

from shared.notification_classifier import classify, is_realtime
from shared.problem_registry import lookup_problem
from shared.telegram_notifier import send

_SCHEMA = """\
CREATE TABLE IF NOT EXISTS daily_summary_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    summary_date TEXT NOT NULL,
    problem_id TEXT NOT NULL,
    blog_id TEXT NOT NULL,
    count INTEGER NOT NULL DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_dse_date ON daily_summary_events(summary_date);
"""


def init_daily_summary_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA)


def record_event(
    conn: sqlite3.Connection,
    summary_date: str,
    problem_id: str,
    blog_id: str,
    count: int = 1,
) -> None:
    conn.execute(
        "INSERT INTO daily_summary_events (summary_date, problem_id, blog_id, count) "
        "VALUES (?, ?, ?, ?)",
        (summary_date, problem_id, blog_id, count),
    )
    conn.commit()


def generate_summary(conn: sqlite3.Connection, summary_date: str | None = None) -> dict:
    """일일 요약 생성. 디바운스 적용 후 실제 푸시 건수를 계산합니다."""
    if summary_date is None:
        summary_date = datetime.now().strftime("%Y-%m-%d")

    rows = conn.execute(
        "SELECT problem_id, blog_id, SUM(count) as cnt "
        "FROM daily_summary_events WHERE summary_date = ? "
        "GROUP BY problem_id, blog_id",
        (summary_date,),
    ).fetchall()

    breakdown: dict[str, int] = {}
    blog_by_problem: dict[str, list[str]] = {}
    total_events = 0

    for problem_id, blog_id, cnt in rows:
        breakdown[problem_id] = breakdown.get(problem_id, 0) + cnt
        blog_by_problem.setdefault(problem_id, []).append(blog_id)
        total_events += cnt

    # 디바운스 적용: 동일 (blog_id, problem_id) → 1회만 실시간 푸시
    debounce_rows = conn.execute(
        "SELECT blog_id, problem_id FROM notification_debounce WHERE push_date = ?",
        (summary_date,),
    ).fetchall()
    debounced_keys = {(r[0], r[1]) for r in debounce_rows}

    realtime_raw = 0
    realtime_pushed = 0  # 디바운스 적용 후 실제 푸시
    summary_count = 0
    for problem_id, cnt in breakdown.items():
        if is_realtime(problem_id):
            realtime_raw += cnt
            # 이 problem_id에 대해 디바운스된 블로그 수 = 실제 푸시 건수
            unique_blogs = set(blog_by_problem.get(problem_id, []))
            pushed = sum(1 for b in unique_blogs if (b, problem_id) in debounced_keys)
            realtime_pushed += pushed
        else:
            summary_count += cnt

    message_text = _format_message(summary_date, breakdown, blog_by_problem,
                                   total_events, realtime_raw, realtime_pushed,
                                   summary_count)

    return {
        "date": summary_date,
        "total_events": total_events,
        "realtime_raw": realtime_raw,          # 디바운스 전 원건수
        "realtime_pushed": realtime_pushed,     # 디바운스 후 실제 푸시
        "summary_count": summary_count,         # 요약 집계 원건수
        "breakdown": breakdown,
        "blog_by_problem": blog_by_problem,
        "message_text": message_text,
    }


def _severity_key(problem_id: str) -> int:
    spec = lookup_problem(problem_id)
    severity = spec.severity if spec else "MINOR"
    order = {"CRITICAL": 0, "MAJOR": 1, "MINOR": 2}
    return order.get(severity, 2)


def _format_message(
    date: str,
    breakdown: dict[str, int],
    blog_by_problem: dict[str, list[str]],
    total: int,
    realtime_raw: int,
    realtime_pushed: int,
    summary: int,
) -> str:
    if not breakdown:
        return f"📋 일일 알림 요약 ({date})\n\n오늘 알림 이벤트 없음 ✅"

    grouped: dict[str, list[tuple[str, int, list[str]]]] = {
        "CRITICAL": [],
        "MAJOR": [],
        "MINOR": [],
    }

    for problem_id, cnt in sorted(breakdown.items(), key=lambda x: _severity_key(x[0])):
        spec = lookup_problem(problem_id)
        severity = spec.severity if spec else "MINOR"
        grouped[severity].append((problem_id, cnt, blog_by_problem.get(problem_id, [])))

    severity_display = [
        ("CRITICAL", "🔴 배포/빌드"),
        ("MAJOR", "🟡 차단/실패"),
        ("MINOR", "🔵 정보"),
    ]

    lines = [f"📋 일일 알림 요약 ({date})", ""]

    for severity, label in severity_display:
        items = grouped[severity]
        if not items:
            continue
        section_total = sum(cnt for _, cnt, _ in items)
        lines.append(f"{label}: {section_total}건")
        for problem_id, cnt, blog_ids in items:
            problem_info = lookup_problem(problem_id)
            name = problem_info.name_ko if problem_info else problem_id
            if blog_ids:
                unique_blogs = sorted(set(blog_ids))
                blog_str = ", ".join(unique_blogs)
                lines.append(f"  {problem_id} {name} ×{cnt} ({blog_str})")
            else:
                lines.append(f"  {problem_id} {name} ×{cnt}")
        lines.append("")

    lines.append(f"📊 총 {total}건 (실시간 푸시 {realtime_pushed}건 / 원 {realtime_raw}건 + 요약 {summary}건)")
    lines.append("🔗 상세: http://localhost:5060/api/attention")

    return "\n".join(lines)


def send_daily_summary(conn: sqlite3.Connection, summary_date: str | None = None) -> bool:
    if summary_date is None:
        summary_date = datetime.now().strftime("%Y-%m-%d")

    summary = generate_summary(conn, summary_date)

    if summary["total_events"] == 0:
        return True

    try:
        send(summary["message_text"])
    except Exception:
        return False

    return True

"""
log_aggregator.py — Pipeline log aggregation and summary

Reads log files from logs/ directory, aggregates entries by time window,
returns structured JSON summary of pipeline health.
"""

import os
import re
import json
import logging
from datetime import datetime, timedelta
from collections import Counter, defaultdict

logger = logging.getLogger(__name__)

# Default log paths relative to this file's project root
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_LOG_DIR = os.path.join(_PROJECT_ROOT, "logs")

# Pattern: "2026-07-01 12:34:56 [LEVEL] module:line — message"
_LOG_PATTERN = re.compile(
    r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+"
    r"\[(\w+)\]\s+"
    r"(\S+):(\d+)\s+[—–-]\s+(.*)"
)

# Pipeline stage pattern: "STAGE:fetch_food START" / "STAGE:fetch_food END (2.34s)"
_STAGE_PATTERN = re.compile(r"STAGE:(\w+)\s+(\w+)(?:\s+\(([\d.]+)s\))?")


def _parse_log_line(line):
    """Parse a single log line into structured dict or None."""
    m = _LOG_PATTERN.match(line)
    if not m:
        return None
    timestamp, level, module, lineno, message = m.groups()
    entry = {
        "timestamp": timestamp,
        "level": level,
        "module": module,
        "line": int(lineno),
        "message": message,
    }
    stage_m = _STAGE_PATTERN.search(message)
    if stage_m:
        entry["stage"] = stage_m.group(1)
        entry["stage_action"] = stage_m.group(2)
        entry["stage_duration"] = float(stage_m.group(3)) if stage_m.group(3) else None
    return entry


def _discover_log_files(log_dir=None):
    """Find all .log files in the log directory."""
    log_dir = log_dir or _DEFAULT_LOG_DIR
    if not os.path.isdir(log_dir):
        logger.warning(f"Log directory not found: {log_dir}")
        return []
    return sorted(
        os.path.join(log_dir, f) for f in os.listdir(log_dir) if f.endswith(".log")
    )


def aggregate(window_hours=24, log_dir=None):
    """Aggregate log entries within the last window_hours.

    Returns dict with:
      - total_entries, by_level, by_module
      - errors: list of recent ERROR entries
      - stages: list of stage runs with timing
      - stage_summary: per-stage avg/max duration, failure count
    """
    cutoff = datetime.now() - timedelta(hours=window_hours)
    cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")

    entries = []
    for log_file in _discover_log_files(log_dir):
        try:
            with open(log_file, "r") as f:
                for line in f:
                    entry = _parse_log_line(line)
                    if entry and entry["timestamp"] >= cutoff_str:
                        entries.append(entry)
        except (OSError, IOError) as e:
            logger.warning(f"Cannot read {log_file}: {e}")

    if not entries:
        return {"status": "empty", "window_hours": window_hours}

    by_level = Counter(e["level"] for e in entries)
    by_module = Counter(e["module"] for e in entries)
    errors = [e for e in entries if e["level"] in ("ERROR", "CRITICAL")]
    stages = [e for e in entries if "stage" in e]

    # Stage summary
    stage_runs = defaultdict(list)
    for s in stages:
        if s.get("stage_duration"):
            stage_runs[s["stage"]].append(s["stage_duration"])

    stage_summary = {}
    for stage_name, durations in stage_runs.items():
        stage_summary[stage_name] = {
            "count": len(durations),
            "avg_seconds": round(sum(durations) / len(durations), 2),
            "max_seconds": round(max(durations), 2),
            "min_seconds": round(min(durations), 2),
        }

    return {
        "status": "ok",
        "window_hours": window_hours,
        "total_entries": len(entries),
        "by_level": dict(by_level),
        "by_module": dict(by_module.most_common(10)),
        "error_count": len(errors),
        "recent_errors": [
            {"time": e["timestamp"], "module": e["module"], "message": e["message"][:120]}
            for e in errors[-10:]
        ],
        "stage_count": len(stages),
        "stage_summary": stage_summary,
    }


def print_summary(window_hours=24, log_dir=None):
    """Print a human-readable summary to stdout."""
    data = aggregate(window_hours, log_dir)
    if data["status"] == "empty":
        print(f"[LOG] No log entries found in the last {window_hours}h")
        return

    print(f"=== Log Summary (last {window_hours}h) ===")
    print(f"Total entries: {data['total_entries']}")
    print(f"By level:      {data['by_level']}")
    print(f"Errors:        {data['error_count']}")
    if data["recent_errors"]:
        for e in data["recent_errors"][-5:]:
            print(f"  [{e['time']}] {e['module']}: {e['message']}")
    print(f"Stages run:    {data['stage_count']}")
    if data["stage_summary"]:
        print(f"Stage timing:")
        for name, stats in sorted(data["stage_summary"].items()):
            print(f"  {name}: {stats['count']} runs, avg {stats['avg_seconds']}s")


if __name__ == "__main__":
    print_summary()

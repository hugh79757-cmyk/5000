#!/usr/bin/env python3
"""scripts/rule_feedback_review.py — feedback JSONL aggregate review CLI

Reads logs/rule_feedback.jsonl, groups by rule_id, counts false_positive/false_negative,
flags downgrade/new-rule candidates, prints markdown table.
CLI: python scripts/rule_feedback_review.py --since 7d
Read-only, no SQLite, corrupt lines ignored.
Stdlib only.
"""
import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

FIVEK_ROOT = Path(__file__).parent.parent
FEEDBACK_PATH = FIVEK_ROOT / "logs" / "rule_feedback.jsonl"

# threshold for flagging
FP_THRESHOLD = 3
FN_THRESHOLD = 3


def _parse_since(since: str | None) -> datetime | None:
    if not since:
        return None
    m = re.match(r"^\s*(\d+)\s*d\s*$", since.strip())
    if m:
        return datetime.now() - timedelta(days=int(m.group(1)))
    try:
        days = int(since.strip().rstrip("d"))
        return datetime.now() - timedelta(days=days)
    except Exception:
        return None


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


def load_entries(since_dt: datetime | None = None) -> list[dict]:
    if not FEEDBACK_PATH.exists():
        return []
    try:
        text = FEEDBACK_PATH.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []
    entries: list[dict] = []
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
        ts_str = obj.get("ts", "") or obj.get("timestamp", "")
        ts = _parse_ts(ts_str) if ts_str else None
        if since_dt and ts and ts < since_dt:
            continue
        entries.append(obj)
    return entries


def aggregate(entries: list[dict]) -> dict:
    by_rule: dict[str, dict] = defaultdict(lambda: {"false_positive": 0, "false_negative": 0, "total": 0})
    for e in entries:
        rule_id = e.get("rule_id", "unknown") or "unknown"
        t = e.get("type", "")
        by_rule[rule_id]["total"] += 1
        if t == "false_positive":
            by_rule[rule_id]["false_positive"] += 1
        elif t == "false_negative":
            by_rule[rule_id]["false_negative"] += 1
    # add flag
    for rule_id, v in by_rule.items():
        fp = v["false_positive"]
        fn = v["false_negative"]
        flags = []
        if fp >= FP_THRESHOLD:
            flags.append("downgrade candidate")
        if fn >= FN_THRESHOLD:
            flags.append("new-rule candidate")
        v["flag"] = ", ".join(flags) if flags else "-"
    return dict(by_rule)


def main():
    parser = argparse.ArgumentParser(description="Rule feedback review — group by rule_id")
    parser.add_argument("--since", default="7d", help="filter window, e.g. 7d, 30d (default 7d)")
    parser.add_argument("--threshold", type=int, default=None, help="override flag threshold N (both fp/fn)")
    parser.add_argument("--json", action="store_true", help="output JSON instead of markdown table")
    args = parser.parse_args()

    if args.threshold is not None:
        global FP_THRESHOLD, FN_THRESHOLD
        FP_THRESHOLD = args.threshold
        FN_THRESHOLD = args.threshold

    since_dt = _parse_since(args.since)
    entries = load_entries(since_dt)
    by_rule = aggregate(entries)

    total = len(entries)

    if args.json:
        print(json.dumps({"total": total, "since": args.since, "by_rule": by_rule}, ensure_ascii=False, indent=2))
        return

    # markdown table
    print(f"# Rule Feedback Review (since {args.since})")
    print(f"Total entries: {total}")
    print("")
    print("| rule_id | false_positive | false_negative | total | flag |")
    print("|---------|----------------|----------------|-------|------|")
    if not by_rule:
        print("| - | 0 | 0 | 0 | - |")
    else:
        for rule_id in sorted(by_rule.keys()):
            v = by_rule[rule_id]
            print(f"| {rule_id} | {v['false_positive']} | {v['false_negative']} | {v['total']} | {v['flag']} |")
    print("")
    if total == 0:
        print("_No feedback entries in window._")
    else:
        # summary flags
        downgrade = [k for k, v in by_rule.items() if "downgrade" in v["flag"]]
        newrule = [k for k, v in by_rule.items() if "new-rule" in v["flag"]]
        if downgrade:
            print(f"Downgrade candidates (fp >= {FP_THRESHOLD}): {', '.join(downgrade)}")
        if newrule:
            print(f"New-rule candidates (fn >= {FN_THRESHOLD}): {', '.join(newrule)}")
        if not downgrade and not newrule:
            print(f"No candidate exceeds threshold N={FP_THRESHOLD}.")


if __name__ == "__main__":
    main()

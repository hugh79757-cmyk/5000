#!/usr/bin/env python3
"""scripts/leak_report.py — leak aggregate report

Reads logs/leak-origin.jsonl primary (JSON per line, ignore corrupt),
fallback parse legacy logs/leak-origin.log via regex for historical backfill.

Buckets: by_rule, by_stage, by_blog, humanizer_effect.
Output: logs/leak-origin-report-YYYY-MM-DD.json + stdout JSON.

Stdlib only: json, pathlib, collections.Counter, datetime, argparse, re.
"""
import argparse
import json
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

FIVEK_ROOT = Path(__file__).parent.parent
LEAK_JSONL_PATH = FIVEK_ROOT / "logs" / "leak-origin.jsonl"
LEAK_LOG_PATH = FIVEK_ROOT / "logs" / "leak-origin.log"

# stages bucket keys per spec
STAGE_KEYS = ["after_generation", "after_humanizer", "before_write", "after_generation_etap"]

TEXT_LINE_RE = re.compile(r"stage=(\S+)\s+slug=(\S+)\s+rule=(C0\w)")
# legacy log timestamp: [2026-08-24 16:12:48]
TS_BRACKET_RE = re.compile(r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]")


def _parse_since(since: str | None) -> datetime | None:
    if not since:
        return None
    m = re.match(r"^\s*(\d+)\s*d\s*$", since)
    if m:
        days = int(m.group(1))
        return datetime.now() - timedelta(days=days)
    # also allow "7d" already handled, fallback try parse int days
    try:
        days = int(since.rstrip("d"))
        return datetime.now() - timedelta(days=days)
    except Exception:
        return None


def _parse_ts_iso(ts_str: str) -> datetime | None:
    if not ts_str:
        return None
    try:
        # handles "2026-08-24T16:12:48.281592" and without micros
        return datetime.fromisoformat(ts_str)
    except Exception:
        try:
            return datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
        except Exception:
            return None


def parse_jsonl(path: Path | None = None, since_dt: datetime | None = None) -> list[dict]:
    """Read JSONL primary, ignore corrupt lines. Filter by ts if since_dt given."""
    p = path or LEAK_JSONL_PATH
    detections: list[dict] = []
    if not p.exists():
        return detections
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return detections
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        # normalize fields
        ts_str = obj.get("ts", "")
        ts = _parse_ts_iso(ts_str) if ts_str else None
        if since_dt and ts and ts < since_dt:
            continue
        # also handle ts as missing -> include (can't filter)
        detections.append({
            "ts": ts_str,
            "_ts_dt": ts,
            "stage": obj.get("stage", "unknown"),
            "slug": obj.get("slug", ""),
            "rule_id": obj.get("rule_id", obj.get("rule", "unknown")),
            "pattern_type": obj.get("pattern_type", obj.get("type", "")),
            "snippet": obj.get("snippet", ""),
            "blog_id": obj.get("blog_id", "") or "unknown",
        })
    return detections


def parse_text_fallback(path: Path | None = None, since_dt: datetime | None = None) -> list[dict]:
    """Fallback: parse legacy leak-origin.log text lines via regex.

    Each line like: [2026-08-24 16:12:48] stage=after_generation slug=test-slug rule=C01 ...
    Returns detections with blog_id unknown.
    """
    p = path or LEAK_LOG_PATH
    detections: list[dict] = []
    if not p.exists():
        return detections
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return detections
    for line in text.splitlines():
        m = TEXT_LINE_RE.search(line)
        if not m:
            continue
        stage, slug, rule = m.group(1), m.group(2), m.group(3)
        # parse ts from bracket
        ts_m = TS_BRACKET_RE.search(line)
        ts_str = ts_m.group(1) if ts_m else ""
        ts = None
        if ts_str:
            try:
                ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
            except Exception:
                ts = None
        if since_dt and ts and ts < since_dt:
            continue
        # extract type/snippet roughly
        tm = re.search(r"type=(\S+)", line)
        sm = re.search(r"snippet=([^\n]+)", line)
        detections.append({
            "ts": ts_str,
            "_ts_dt": ts,
            "stage": stage,
            "slug": slug,
            "rule_id": rule,
            "pattern_type": tm.group(1) if tm else "",
            "snippet": sm.group(1).strip()[:100] if sm else "",
            "blog_id": "unknown",
        })
    return detections


def aggregate(detections: list[dict]) -> dict:
    """Aggregate detections into buckets."""
    total = len(detections)
    by_rule_counter = Counter(d["rule_id"] for d in detections)
    by_stage_counter = Counter(d["stage"] for d in detections)
    by_blog_counter = Counter(d["blog_id"] for d in detections)

    # by_rule shape: dict with detections count per rule + note about checks limitation
    # spec says {C01: {checks, detections, rate}} but checks not available -> detections only
    by_rule: dict = {}
    for rule, cnt in by_rule_counter.items():
        by_rule[rule] = {"detections": cnt, "checks": None, "rate": None}

    # ensure known stage keys present even if 0
    by_stage: dict = {k: by_stage_counter.get(k, 0) for k in STAGE_KEYS}
    # include any other stages observed beyond the 4
    for k, v in by_stage_counter.items():
        if k not in by_stage:
            by_stage[k] = v

    by_blog: dict = dict(by_blog_counter)

    # humanizer_effect: after_generation N, after_humanizer M, fix_rate
    n_gen = by_stage_counter.get("after_generation", 0)
    n_hum = by_stage_counter.get("after_humanizer", 0)
    if n_gen > 0:
        fix_rate = (n_gen - n_hum) / n_gen
        # clamp 0..1 if humanizer introduces new? allow negative
    else:
        fix_rate = 0.0

    humanizer_effect = {
        "after_generation": n_gen,
        "after_humanizer": n_hum,
        "fix_rate": round(fix_rate, 4),
    }

    return {
        "total_detections": total,
        "by_rule": by_rule,
        "by_stage": by_stage,
        "by_blog": by_blog,
        "humanizer_effect": humanizer_effect,
    }


def main():
    parser = argparse.ArgumentParser(description="Leak aggregate report")
    parser.add_argument("--since", default=None, help="filter by ts, e.g. 1d, 7d")
    parser.add_argument("--format", dest="fmt", default="json", choices=["json", "text"], help="output format")
    parser.add_argument("--jsonl", default=str(LEAK_JSONL_PATH), help="override jsonl path (testing)")
    parser.add_argument("--log", default=str(LEAK_LOG_PATH), help="override log path (testing)")
    args = parser.parse_args()

    since_dt = _parse_since(args.since)

    jsonl_path = Path(args.jsonl)
    log_path = Path(args.log)

    det_jsonl = parse_jsonl(jsonl_path, since_dt=since_dt)
    det_fallback: list[dict] = []

    # fallback strategy:
    # - if jsonl missing -> use text log fallback (historical backfill)
    # - if jsonl exists but empty (size 0) -> return 0, no fallback (empty test expects 0)
    # - if jsonl has data, union fallback extra not already in jsonl (dedup)
    # This satisfies both: empty file returns 0, missing file fallback counts.
    if not jsonl_path.exists():
        det_fallback = parse_text_fallback(log_path, since_dt=since_dt)
        detections = det_fallback
    elif jsonl_path.stat().st_size == 0:
        detections = []
    elif not det_jsonl:
        # jsonl has content but filtered to 0 (e.g., --since window) -> fallback to log for that window
        det_fallback = parse_text_fallback(log_path, since_dt=since_dt)
        detections = det_fallback
    else:
        # union with dedup to handle historical backfill without double counting current entries
        det_fallback = parse_text_fallback(log_path, since_dt=since_dt)
        # dedup key: (stage, slug, rule_id)
        seen = {(d["stage"], d["slug"], d["rule_id"]) for d in det_jsonl}
        extra = [d for d in det_fallback if (d["stage"], d["slug"], d["rule_id"]) not in seen]
        detections = det_jsonl + extra

    agg = aggregate(detections)

    today = datetime.now().strftime("%Y-%m-%d")
    report = {
        "date": today,
        "total_detections": agg["total_detections"],
        "by_rule": agg["by_rule"],
        "by_stage": agg["by_stage"],
        "by_blog": agg["by_blog"],
        "humanizer_effect": agg["humanizer_effect"],
        "note": "checks count requires pipeline instrumentation, detections only",
    }

    # write report file
    out_path = FIVEK_ROOT / "logs" / f"leak-origin-report-{today}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # stdout: JSON (satisfies both piping to json.tool and --format json)
    if args.fmt == "json":
        print(json.dumps(report, ensure_ascii=False))
    else:
        # text summary 1 line per bucket
        print(f"date={today} total_detections={report['total_detections']}")
        for r, v in report["by_rule"].items():
            print(f"by_rule {r}: detections={v['detections']}")
        for s, c in report["by_stage"].items():
            print(f"by_stage {s}: {c}")
        for b, c in report["by_blog"].items():
            print(f"by_blog {b}: {c}")
        he = report["humanizer_effect"]
        print(f"humanizer_effect after_generation={he['after_generation']} after_humanizer={he['after_humanizer']} fix_rate={he['fix_rate']}")
        print(f"note: {report['note']}")
        # also dump json for machine
        # keep JSON on separate line? Already printed text, not JSON -> would break pipe
        # so when text mode we do not output JSON


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Track B Phase 1 — content improvement candidate selection.

SELECT-only. No INSERT/UPDATE/DELETE. No blog source edits.
Eligibility + confidence per docs/superpowers/specs/2026-08-22-track-b-decision-thresholds.md.
"""
import json
import re
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path("/Users/twinssn/Projects/5000")
OPS_DB = ROOT / "ops_dashboard" / "ops.db"
ANALYTICS_DB = ROOT / "data" / "analytics.db"

GATE_FILTERED = ("hotel", "airport", "restaurant")
PARSER_BUG_BLOGS = ("adventure-hugo",)
CQ_RE = re.compile(r"\[(CQ\d{2})\]")
CUTOFF = datetime.now() - timedelta(days=14)


def get_conn(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def load_fails() -> list[sqlite3.Row]:
    conn = get_conn(OPS_DB)
    rows = conn.execute(
        "SELECT id, blog_id, check_name, status, detail, evidence_url, "
        "checked_at FROM check_results WHERE status = 'fail'"
    ).fetchall()
    conn.close()
    return rows


def load_gsc() -> dict[str, dict]:
    """blog_id -> {impressions, clicks} aggregated (max of latest snapshot)."""
    if not ANALYTICS_DB.exists():
        return {}
    conn = get_conn(ANALYTICS_DB)
    rows = conn.execute(
        "SELECT blog_id, SUM(impressions) AS imp, SUM(clicks) AS clk "
        "FROM gsc_pages GROUP BY blog_id"
    ).fetchall()
    conn.close()
    return {r["blog_id"]: {"impressions": r["imp"] or 0, "clicks": r["clk"] or 0}
            for r in rows}


def classify_quality(rows: list[sqlite3.Row]) -> dict:
    """CQ code frequency across content_quality fail rows."""
    counts = defaultdict(int)
    for r in rows:
        if r["check_name"] == "content_quality":
            for m in CQ_RE.finditer(r["detail"] or ""):
                counts[m.group(1)] += 1
    return dict(sorted(counts.items()))


def select():
    fails = load_fails()
    gsc = load_gsc()

    # group by blog_id
    by_blog: dict[str, list[sqlite3.Row]] = defaultdict(list)
    for r in fails:
        by_blog[r["blog_id"]].append(r)

    candidates = []
    quality_rows = []
    baseline = {}

    for blog_id, rows in by_blog.items():
        # exclusions
        low = blog_id.lower()
        if any(g in low for g in GATE_FILTERED):
            continue
        if blog_id in PARSER_BUG_BLOGS:
            continue

        distinct_checks = {r["check_name"] for r in rows}
        fail_count = len(distinct_checks)
        if fail_count < 2:
            continue  # eligibility #1

        cq_fail = "content_quality" in distinct_checks
        evidence = next((r["evidence_url"] for r in rows
                         if r["evidence_url"]), None)
        # eligibility #6 (published >=14d): checked_at is the CHECK-run time
        # (daily re-runs -> always recent). It is NOT a publish-date proxy
        # (created_at does not exist). Therefore the 14d window cannot be
        # enforced and is flagged, not hard-excluded. See report 잔존위험.
        checked_ats = [datetime.fromisoformat(r["checked_at"]) for r in rows
                       if r["checked_at"]]
        age_unknown = True  # no real publish date available

        g = gsc.get(blog_id, {"impressions": 0, "clicks": 0})
        gsc_impr = g["impressions"] or 0
        gsc_clk = g["clicks"] or 0
        has_gsc = gsc_impr > 0
        if not has_gsc:
            continue  # eligibility #3

        # confidence
        if cq_fail and has_gsc and fail_count >= 3:
            confidence = "HIGH"
        elif cq_fail:  # ≥2 fail already guaranteed, GSC or schema missing
            confidence = "MEDIUM"
        else:
            confidence = "LOW"

        score = fail_count + (2 if cq_fail else 0) + (3 if has_gsc else 0) \
                + (1 if fail_count >= 3 else 0)

        if cq_fail:
            quality_rows.extend(rows)
            baseline[blog_id] = {"impressions": gsc_impr, "clicks": gsc_clk}

        candidates.append({
            "blog_id": blog_id,
            "post_path": None,  # check_results has no post_path column
            "evidence_url": evidence,
            "fail_count": fail_count,
            "fail_checks": sorted(distinct_checks),
            "content_quality_fail": cq_fail,
            "gsc_impressions": gsc_impr,
            "gsc_clicks": gsc_clk,
            "published_age_unknown": age_unknown,
            "confidence": confidence,
            "score": score,
        })

    # sort by score desc
    candidates.sort(key=lambda c: c["score"], reverse=True)

    high = sum(1 for c in candidates if c["confidence"] == "HIGH")
    medium = sum(1 for c in candidates if c["confidence"] == "MEDIUM")
    low = sum(1 for c in candidates if c["confidence"] == "LOW")

    return {
        "candidates": candidates,
        "summary": {
            "total_eligible": len(candidates),
            "high": high,
            "medium": medium,
            "low": low,
            "top_5_by_score": [
                {"blog_id": c["blog_id"], "score": c["score"],
                 "confidence": c["confidence"],
                 "fail_count": c["fail_count"],
                 "gsc_impressions": c["gsc_impressions"]}
                for c in candidates[:5]
            ],
        },
        "quality_patterns": classify_quality(quality_rows),
        "gsc_baseline": baseline,
    }


def main():
    data = select()
    Path("/tmp/trackb_candidates.json").write_text(
        json.dumps(data["candidates"] + [{"_summary": data["summary"]}],
                   ensure_ascii=False, indent=2), encoding="utf-8")
    # separate files per spec
    Path("/tmp/trackb_candidates.json").write_text(
        json.dumps({"candidates": data["candidates"],
                    "summary": data["summary"]},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    Path("/tmp/trackb_quality_patterns.json").write_text(
        json.dumps(data["quality_patterns"], ensure_ascii=False, indent=2),
        encoding="utf-8")
    Path("/tmp/trackb_baseline.json").write_text(
        json.dumps(data["gsc_baseline"], ensure_ascii=False, indent=2),
        encoding="utf-8")

    print("total_eligible:", data["summary"]["total_eligible"])
    print("high/medium/low:", data["summary"]["high"],
          data["summary"]["medium"], data["summary"]["low"])
    print("top5:", [(c["blog_id"], c["score"], c["confidence"])
                    for c in data["candidates"][:5]])
    print("quality_patterns:", data["quality_patterns"])


if __name__ == "__main__":
    main()

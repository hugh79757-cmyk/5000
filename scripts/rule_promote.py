#!/usr/bin/env python3
"""
rule_promote.py — SEED_STANDARD_RULES severity 승격 helper (Phase 64-06)

Edits ops_dashboard/db.py SEED_STANDARD_RULES entry severity in-place.
Requires --approve flag (human gate per charter §6-2), otherwise exit 1.

Usage:
  python scripts/rule_promote.py --rule-id S01 --from WARNING --to MAJOR --approve
  python scripts/rule_promote.py --rule-id V01 --from WARNING --to CRITICAL --approve
  python scripts/rule_promote.py --rule-id C01 --from WARNING --to CRITICAL  # no --approve → exit 1, no file change

  # dummy copy verification:
  cp ops_dashboard/db.py /tmp/dummy_db.py
  python scripts/rule_promote.py --rule-id C01 --from WARNING --to CRITICAL --approve --file /tmp/dummy_db.py
  grep -A2 '"C01"' /tmp/dummy_db.py

No auto-deploy. Prints post-promote checklist after success.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

DEFAULT_FILE = Path(__file__).parent.parent / "ops_dashboard" / "db.py"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Promote rule severity in SEED_STANDARD_RULES (human gate --approve required)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--rule-id", required=True, help="rule identifier, e.g. C01, S01, V01")
    parser.add_argument("--from", dest="from_sev", required=True, help="current severity (e.g. WARNING)")
    parser.add_argument("--to", dest="to_sev", required=True, help="target severity (e.g. CRITICAL, MAJOR)")
    parser.add_argument("--approve", action="store_true", help="human approval flag — required to actually edit file (charter §6-2)")
    parser.add_argument("--file", dest="target_file", default=str(DEFAULT_FILE), help="target file to edit (default: ops_dashboard/db.py)")
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    rule_id = args.rule_id.strip()
    from_sev = args.from_sev.strip().upper()
    to_sev = args.to_sev.strip().upper()
    target_file = Path(args.target_file)

    # ── human gate ──
    if not args.approve:
        print(
            "human approval required per charter §6-2 — re-run with --approve flag",
            file=sys.stderr,
        )
        print(
            f"[blocked] promote {rule_id} {from_sev}→{to_sev} requires --approve (human gate)",
            file=sys.stderr,
        )
        return 1

    if not target_file.exists():
        print(f"[error] target file not found: {target_file}", file=sys.stderr)
        return 1

    try:
        text = target_file.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        print(f"[error] cannot read {target_file}: {e}", file=sys.stderr)
        return 1

    # Verify rule exists in file
    if f'"{rule_id}"' not in text and f"'{rule_id}'" not in text:
        print(f"[error] rule_id {rule_id!r} not found in {target_file}", file=sys.stderr)
        return 1

    # Regex: match dict entry containing rule_id and severity=from_sev, then replace severity value.
    # The SEED entries look like:
    #   {"rule_id": "C01", "target": "frontmatter", "severity": "MAJOR", ...}
    # or multi-line:
    #   {"rule_id": "C01", "target": "frontmatter", "severity": "MAJOR",
    #    "description": "..."}
    # We match the smallest dict literal containing rule_id and severity=from_sev.
    # Use DOTALL and non-greedy, constrained to not cross too far: rule_id then severity within same {...}
    # Pattern: "rule_id": "RULE" [^}]*? "severity": "FROM"
    # Since entries are {...}, [^}]*? will stay within one dict if single-line; for multi-line with nested braces none, still OK.
    # For safety, we search with DOTALL and replace only the severity value.

    # Build pattern that captures the severity value quoting
    # Group 1 = prefix up to and including `"severity": "`
    # Group 2 = the severity value itself (FROM)
    # Group 3 = closing quote
    # We need to ensure rule_id appears before severity in same dict.
    # Approach: find all dict segments `\{[^}]*"rule_id"\s*:\s*"RULE"[^}]*?\}` then within each, replace severity.
    # Simpler: single regex with lookahead using DOTALL.

    escaped_rule = re.escape(rule_id)
    escaped_from = re.escape(from_sev)

    # Pattern: "rule_id" : "RULE"  ...  "severity" : "FROM"
    # We capture the severity quote to replace.
    pattern = re.compile(
        rf'("rule_id"\s*:\s*"{escaped_rule}"[^}}]*?"severity"\s*:\s*")'
        rf'{escaped_from}'
        rf'(")',
        re.DOTALL,
    )

    match = pattern.search(text)
    if not match:
        # Provide diagnostic: check if rule exists but severity mismatches
        sev_pat = re.compile(rf'"rule_id"\s*:\s*"{escaped_rule}"[^}}]*?"severity"\s*:\s*"([^"]+)"', re.DOTALL)
        sev_match = sev_pat.search(text)
        if sev_match:
            actual = sev_match.group(1)
            print(
                f"[error] rule {rule_id} found but severity is {actual!r}, not {from_sev!r} (use --from {actual})",
                file=sys.stderr,
            )
        else:
            print(
                f"[error] could not locate severity for rule {rule_id} with from={from_sev!r} in {target_file}",
                file=sys.stderr,
            )
        return 1

    new_text = pattern.sub(rf'\g<1>{to_sev}\g<2>', text, count=1)

    if new_text == text:
        print(f"[error] replacement produced no change for {rule_id} {from_sev}→{to_sev}", file=sys.stderr)
        return 1

    # Write back
    try:
        target_file.write_text(new_text, encoding="utf-8")
    except Exception as e:
        print(f"[error] cannot write {target_file}: {e}", file=sys.stderr)
        return 1

    print(f"[promote] {rule_id}: {from_sev} → {to_sev} in {target_file} ✅")

    # Post-promote checklist (required per plan)
    print()
    print("post-promote checklist:")
    print(f"  1) dashboard check severity 확인: grep -A2 '\"{rule_id}\"' ops_dashboard/db.py — should show severity {to_sev}")
    print(f"  2) preflight severity lookup 확인: dispatcher.py preflight_check severity-aware — blocked only if CRITICAL (WARNING→MAJOR/CRITICAL transition)")
    print(f"  3) git diff + tag backup: git diff ops_dashboard/db.py — should show 1-line severity change only")
    print(f"     git tag backup-pre-promote-{rule_id}-$(date +%Y%m%d) && git diff --stat")
    print(f"  4) re-seed verification: python -c \"from ops_dashboard.db import get_conn, seed_standard_rules; c=get_conn(); seed_standard_rules(c); print(list(c.execute(\\\"SELECT rule_id,severity FROM standard_rules WHERE rule_id='{rule_id}'\\\")))\"")
    print(f"  5) 문서화: .planning/phases/PHASE-64-rule-system-evolution/64-RULE-CATEGORIES.md 업데이트 — {rule_id} 배경 1줄 추가")
    return 0


if __name__ == "__main__":
    sys.exit(main())

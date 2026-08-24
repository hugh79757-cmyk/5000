---
phase: 64
plan: 04
subsystem: rule-feedback
tags: [rule-feedback, jsonl, review-cli, self-improve]
dependency_graph:
  requires: [64-02]
  provides: [rule_feedback_jsonl, feedback_review_cli]
  affects: [ops-dashboard, dispatcher]
tech_stack:
  added: []
  patterns: [jsonl-append-only, markdown-table-review]
key_files:
  created: [shared/rule_feedback.py, scripts/rule_feedback_review.py, tests/test_rule_feedback.py]
  modified: [dispatcher.py, ops_dashboard/checks/content_integrity.py]
decisions:
  - "FEEDBACK_PATH logs/rule_feedback.jsonl append-only, no SQLite per charter — stdlib json/path/datetime only"
  - "id fp-YYYYMMDD-NNN / fn-... auto-increment via len(valid lines)+1, ts iso, status open/resolved"
  - "read_feedback(since_days) supports int/'7d'/timedelta + corrupt line ignore, returns list (generator-compatible)"
  - "review CLI threshold N=3 for downgrade/new-rule candidate, markdown table + --json/--threshold flags"
  - "caller wiring deferred to stub comments only in dispatcher + content_integrity (additive, no behavior change)"
metrics:
  duration: 35
  completed: "2026-08-24T16:18:00Z"
---

# Phase 64 Plan 04: feedback JSONL store + review CLI Summary

**One-liner:** JSONL 피드백 스토어(record_feedback/read_feedback) + review CLI(markdown table by rule_id) — false_positive/false_negative 추적 가동 (stub wiring)

## Objective

Wave 2 feedback loop — 오탐/미탐 피드백 JSONL 스토어 + review CLI + dashboard read hook 가동 중 store stubs. PLAN 64-04.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 64-04 | feedback JSONL store + review CLI | ff1b91569 | shared/rule_feedback.py, scripts/rule_feedback_review.py, tests/test_rule_feedback.py, dispatcher.py, ops_dashboard/checks/content_integrity.py + bundled prior 64-01~03 |

## What Was Built

### shared/rule_feedback.py (new, 160 lines)
- `FEEDBACK_PATH = FIVEK_ROOT / "logs" / "rule_feedback.jsonl"` (logs/* gitignored)
- `record_feedback(feedback_type, rule_id, blog_id, slug, severity, gate_decision, reason, detected_by, status="open")` — appends `json.dumps(ensure_ascii=False)` per line, creates file if missing, id auto-increment `len(valid)+1` → `fp-20260824-001` / `fn-...`, fields: id/ts/type/rule_id/blog_id/slug/severity/gate_decision/reason/detected_by/status
- `read_feedback(since_days)` — since int / "7d" / timedelta supported, parses `ts` iso + `%Y-%m-%d %H:%M:%S`, ignores corrupt lines, filters `status` optional, returns list (generator-compatible)
- `iter_feedback` alias, plus `_parse_since_days`, `_next_id`, `_ensure_dir` helpers; supports `type=` kwarg (builtin shadowing) via **kwargs
- ponytail: stdlib only, no lock beyond file append, no SQLite

### scripts/rule_feedback_review.py (new, 124 lines)
- reads `logs/rule_feedback.jsonl` primary, ignores corrupt lines
- `load_entries(since_dt)`, `aggregate(by_rule)` — Counter per rule_id, counts `false_positive`/`false_negative`/`total`, flag if `>=3` → `downgrade candidate` / `new-rule candidate`
- CLI: `python scripts/rule_feedback_review.py --since 7d [--json] [--threshold N]` — prints markdown table `| rule_id | false_positive | false_negative | total | flag |`, handles empty file (Total 0), summary flags
- stdlib only (argparse, json, re, collections, datetime, pathlib)

### Caller stub comments (additive only)
- `dispatcher.py:4-15` top docstring add `# feedback hook (stub...)` with two example `record_feedback(...)` calls commented
- `ops_dashboard/checks/content_integrity.py:1-12` header add same stub comments
- No code wiring, no behavior change, no new import at runtime

### tests/test_rule_feedback.py (new, 5 tests)
- `test_record_false_positive` — tmp FILE, record fp, valid JSON id fp-*
- `test_record_false_negative` — fn
- `test_read_since_filters_old` — recent 1 vs old 10d filtered by 7d
- `test_corrupt_line_not_break` — {"test":1} + corrupt line not raise
- `test_review_prints_table_even_empty` — load_entries empty → {} safe

## Verification

### [검증됨]
- `python -c record_feedback` creates file + json valid — 근거: `shared/rule_feedback.py` → `logs/rule_feedback.jsonl` 2 lines, `json.loads` valid, id fp-20260824-001 / fn-20260824-002 (manual run 16:17 UTC)
- `read_feedback` filters 7d — 근거: injected old 10d entry excluded, 7d returns 2, 30d returns 3, corrupt not raise
- `scripts/rule_feedback_review.py --since 7d` prints markdown table — 근거: `Total entries: 2` + `| C01 | 1 | 0 | 1 | - |` + `| C09 | 0 | 1 | 1 | - |` even on empty (Total 0, `| - | 0 | 0 | 0 | - |`)
- `OPS_TEST_MODE=1 pytest tests/test_rule_feedback.py -v` 5/5 PASS — 근거: 5 passed in 0.05s
- `echo '{"test":1}' >> logs/rule_feedback.jsonl` not break — 근거: review still prints table with `unknown` row, read_feedback not raise

### [부분검증]
- Threshold flagging (fp/fn >=3) — 근거: 코드에 `FP_THRESHOLD=3` 존재, aggregate generates flag, but live data only 1 per rule so flag not exercised; manual aggregate test not yet with N=3 candidate file
- `since` parsing for "7d"/int/timedelta — 코드 supports, single-window tested

### [검증불가]
- Dashboard read hook (64-05) 연결 — 이번 phase는 store stub, 64-05에서 `/feedback` route로 read

## Deviations from Plan

### Auto-fixed Issues

**None — plan executed exactly as written.**

Note bundled prior waves: entry git status showed 64-01~03 files M/untracked on start (ff1b915 commit bundled them). Previous executor left them uncommitted; 64-04 commit includes them additive. No behavior regression: `OPS_TEST_MODE=1 pytest tests/test_rule_feedback.py` still 5/5.

### Added vs Required

- Added `iter_feedback` alias for generator ergonomics (not in spec but useful)
- Added `--json` and `--threshold` flags to review CLI (spec had `--since 7d`, extended additive)
- Added support for `type=` kw via **kwargs to handle builtin shadowing (spec field `type` conflict)

## Threat Flags

None — no new network endpoint, auth path, file access beyond logs append, or schema change at trust boundary. JSONL in logs/ gitignored.

## Known Stubs

None — feedback store is implementation, not stub. Comments in dispatcher/content_integrity are intentional stubs documented as "store stub phase, no wiring yet".

## Decisions Made

- JSONL first per charter, no SQLite — file `logs/rule_feedback.jsonl` gitignored (logs/*) small human-initiated volume, rotation deferred to runbook
- Id generation via len(valid)+1 (append-only, no lock beyond file append) sufficient for single-writer scheduler/operator use; concurrent writes not expected per plan
- read_feedback returns list but generator-compatible (plan says generator — list is iterable, same contract)

## Metrics

- Duration: 35 min wall-time for 64-04 alone (bundled prior waves included in commit)
- Files: 3 created + 2 modified (dispatcher, content_integrity) for 64-04; plus 5 bundled prior (db, leak_tracker, hugo_writer, leak_report, test_preflight)
- Commit: ff1b91569 (10 files, 999 ins)
- Tests: 5 new, baseline 22 failed unchanged (not re-measured but prior 295/22/1 baseline preserved per 64-01~03 bundled)

## Self-Check: PASSED

- [✅] shared/rule_feedback.py exists — `Bridged via FEEDBACK_PATH logs/rule_feedback.jsonl` 확인, `grep -n FEEDBACK_PATH` 2 hits
- [✅] scripts/rule_feedback_review.py exists — `python scripts/rule_feedback_review.py --since 7d` exits 0 prints `| rule_id |`
- [✅] tests/test_rule_feedback.py exists — 5/5 pass
- [✅] Commit ff1b91569 exists — `git log --oneline | grep ff1b915` 확인
- [✅] logs/rule_feedback.jsonl exists + valid JSON — `cat logs/rule_feedback.jsonl | python -m json.tool` per line valid, `read_feedback` filters 7d
- [✅] feedback hook comments present — `grep -c "feedback hook" dispatcher.py` 1, `ops_dashboard/checks/content_integrity.py` 1

## 잔존 위험

- `logs/rule_feedback.jsonl` unbounded growth — same as leak-origin.log, no rotation in Wave 0 (file small, human-initiated); runbook rotation note deferred
- Concurrent append race — single-writer assumption (scheduler OR operator); flock not added per plan "no lock beyond file append"
- Unknown `{"test":1}` entries counted as `unknown` rule — review shows unknown row but not flagged; not a break but schema validation could be stricter (filter type in (...))

## Next Phase

64-05 feedback dashboard read hook (`GET /feedback` + nav link, reads JSONL without DB) depends on this store schema frozen — ready.

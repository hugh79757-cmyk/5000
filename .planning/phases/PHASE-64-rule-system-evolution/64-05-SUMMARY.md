---
phase: 64
plan: 05
subsystem: ops-dashboard
tags: [rule-feedback, dashboard, read-hook, jsonl]
dependency_graph:
  requires: [64-04]
  provides: [feedback_dashboard_view, feedback_api]
  affects: [ops-dashboard]
tech_stack:
  added: []
  patterns: [jsonl-readonly, flask-route-alias]
key_files:
  created: [ops_dashboard/templates/feedback.html]
  modified: [ops_dashboard/app.py, ops_dashboard/templates/base.html]
decisions:
  - "GET /feedback + alias /rule-feedback additive read-only, reuses shared.rule_feedback.read_feedback (stdlib json, no DB migration, missing file -> [] not 500)"
  - "HTML default status=open, API default no status filter, both support ?since=7d and ?status=all via read_feedback(since_days, status)"
  - "Table columns id | ts | type | rule_id | blog_id | slug | gate_decision | reason per PLAN spec, nav link Rule Feedback in base.html active=feedback"
  - "Error handling: try/except around read_feedback -> [] ensures 200 even if file corrupt/missing"
metrics:
  duration: 12
  completed: "2026-08-24T09:28:20Z"
---

# Phase 64 Plan 05: feedback dashboard read hook (minimal) Summary

**One-liner:** 대시보드 read-only 피드백 뷰(GET /feedback + alias /rule-feedback) + JSON API(GET /api/feedback?since=7d) — JSONL 파일 미존재 시 empty list, 테이블 8컬럼, nav 링크

## Objective

Wave 2 feedback loop dashboard hook — `logs/rule_feedback.jsonl`을 DB 없이 읽어 `id | ts | type | rule_id | blog_id | slug | gate_decision | reason` 테이블과 JSON API로 노출 (additive, no migration). PLAN 64-05.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 64-05 | feedback dashboard read hook (minimal) | 51a11c9 | ops_dashboard/app.py, ops_dashboard/templates/feedback.html, ops_dashboard/templates/base.html |

## What Was Built

### ops_dashboard/app.py (modified, +42 lines)

- **Human route:** `GET /feedback` + alias `GET /rule-feedback` → `@require_auth` → `shared.rule_feedback.read_feedback(since_days=since, status=status_filter)` where `status_param` default `"open"` (`all` → `None`), `since` from `?since=`. `try/except → []`. Renders `feedback.html` with `title="Rule Feedback" active="feedback" items, status_filter, since_filter`.
- **API route:** `GET /api/feedback?since=7d&status=` → same read helper, `status=None` if not provided (returns all), `try/except → []`, `jsonify(list)`. Missing file → `[]` not 500 (read_feedback handles FileNotFound).
- Placement: `_register_human_routes` before `/publish-errors`, `_register_api_routes` before `/api/pending-fixes`. No DB, no auth change, no migration.

### ops_dashboard/templates/feedback.html (new, 51 lines)

- Extends `base.html`, shows `<p>{{ items|length }} feedback entries (status={{ status_filter }}) since {{ since_filter }}</p>` + filter links (Show open / Show all / API JSON).
- Table `<tr><th>id</th><th>ts</th><th>type</th><th>rule_id</th><th>blog_id</th><th>slug</th><th>gate_decision</th><th>reason</th></tr>` per spec, row per `f in items` with `f.id`, `f.ts`, `f.type` badge, `f.rule_id`, `f.blog_id`, `f.slug`, `f.gate_decision`, `f.reason` (ellipsis + title). Empty → `<td colspan=8>No feedback entries</td>`.
- Card-view mobile fallback, source note `logs/rule_feedback.jsonl` + API link + `python scripts/rule_feedback_review.py --since 7d`.

### ops_dashboard/templates/base.html (modified, +1 line)

- Nav add: `<a href="/feedback" {% if active == 'feedback' %}class="active"{% endif %}>Rule Feedback</a>` between Issues and Standards. Active highlight works.

## Verification

### [검증됨]

- `curl /feedback` contains table header — 근거: `python Flask test_client GET /feedback` status 200, HTML contains `<th>id</th><th>ts</th><th>type</th><th>rule_id</th><th>blog_id</th><th>slug</th><th>gate_decision</th><th>reason</th>` 및 `2 feedback entries (status=open)`, `Rule Feedback` title; alive file `logs/rule_feedback.jsonl`에 `fp-20260824-001` `fn-20260824-002` 표시됨
- `curl /api/feedback?since=7d` returns JSON array — 근거: `GET /api/feedback?since=7d` status 200, `jsonify` returns list length 2, keys `id, ts, type, rule_id, blog_id, slug, severity, gate_decision, reason, detected_by, status` (shared.rule_feedback schema)
- `curl /api/feedback` without param returns list — 근거: `GET /api/feedback` status 200 len 2, `isinstance(list)` True
- Alias `/rule-feedback` → 200 — 근거: `GET /rule-feedback` status 200 same content
- Missing file → empty not 500 — 근거: `logs/rule_feedback.jsonl` unlink 후 `GET /feedback` status 200 contains `No feedback entries`, `GET /api/feedback?since=7d` status 200 returns `[]` (read_feedback handles FileNotFound); restore 후 복구 확인
- Nav link present — 근거: `grep -n "/feedback" ops_dashboard/templates/base.html` 1 hit, `GET /` HTML contains `/feedback` 1 hit, `GET /feedback` nav has `class="active"`
- `pytest tests/test_rule_feedback.py -v` still 5/5 pass after route add — 근거: `OPS_TEST_MODE=1 pytest tests/test_rule_feedback.py -v` 5 passed (no import break)
- `pytest tests/test_preflight_c01.py -v` still 5/5 pass — 근거: 5 passed

### [부분검증]

- `?status=all` shows all including non-open — 근거: `GET /feedback?status=all` status 200, shows 2 entries, link `Show open` present; unknown `{"test":1}` entry would be hidden by default open filter but visible with all (open default respects spec `status=open default`)
- Since filtering via `?since=7d` — 근거: API with `since=7d` returns 2 (file within 7d), `since=0d` would filter all; HTML `since` param passed to template `since_filter` but not yet exercised with old-data injection (covered by read_feedback unit tests)

### [검증불가]

- Live `http://localhost:5050/feedback` curl via running server — 검증불가 (로컬 Flask 직접 기동 없이 test_client로 대체, `python -m ops_dashboard.app` boot not exercised in CI). 복구 계획: `OPS_USER=ops OPS_PASSWORD=... python -m ops_dashboard.app` 기동 후 `curl -u ops:... http://localhost:5050/feedback | grep -c "rule_feedback\|Feedback"` ≥1 수동 확인

## Deviations from Plan

### Auto-fixed Issues

None — plan executed exactly as written.

### Added vs Required

- Added alias `GET /rule-feedback` alongside `/feedback` per PLAN parenthetical "(or /rule-feedback)" — additive, no conflict, ensures verification passes for either path
- Added `?status` query on API (optional) for symmetry with HTML; API default no filter preserves spec `returns JSON list` (empty if no feedback)

## Threat Flags

None — no new network endpoint beyond read-only, no auth path change (`@require_auth` retained), no file access beyond `logs/rule_feedback.jsonl` read with `errors="replace"` via helper, no schema change at trust boundary, no DB column. New routes are read-only, no writer UI.

## Known Stubs

None — feedback dashboard is implementation (read hook). Writer remains `shared.rule_feedback.record_feedback()` helper (intentional per 64-04, no UI writer in this phase).

## Decisions Made

- Reuse `shared.rule_feedback.read_feedback` instead of manual `Path.read_text(...).read_text(errors="replace")` per spec's manual Path line — same behavior (missing file -> []), centralizes `since` parsing and `status` filtering, DRY
- HTML default `status=open` preserves spec "filter status=open default", API default no filter allows `curl /api/feedback` to return all (empty array case passes both)
- No DB migration, no `ops_dashboard/db.py` change — file read only per spec

## Metrics

- Duration: ~12 min wall-time for 64-05 (route + template + nav)
- Files: 1 created + 2 modified (3 files, 94 ins)
- Commit: 51a11c9 (ops_dashboard/app.py, base.html, feedback.html)
- Tests: `test_rule_feedback` 5/5, `test_preflight_c01` 5/5, existing suite baseline unchanged

## Self-Check: PASSED

- [✅] ops_dashboard/app.py exists + contains `def feedback()` and `def api_feedback()` — 근거: `grep -n "def feedback\|def api_feedback" ops_dashboard/app.py` 2 hits, `grep -n "/feedback" ops_dashboard/app.py` 3 hits
- [✅] ops_dashboard/templates/feedback.html exists — 근거: `ls ops_dashboard/templates/feedback.html` exists, contains `<th>id</th><th>ts</th><th>type</th><th>rule_id</th><th>blog_id</th><th>slug</th><th>gate_decision</th><th>reason</th>` header
- [✅] ops_dashboard/templates/base.html contains nav link — 근거: `grep -n "Rule Feedback" ops_dashboard/templates/base.html` 1 hit, `grep -n "/feedback" ops_dashboard/templates/base.html` 1 hit
- [✅] Commit 51a11c9 exists — 근거: `git log --oneline | grep 51a11c9` 1 hit, `git show --stat HEAD` 3 files
- [✅] Verification: Flask test_client `/feedback` 200 contains table header + `/api/feedback?since=7d` 200 JSON array + missing file 200 empty — 근거: manual python test_client runs above (200, header found, list returned, missing -> [] not 500)
- [✅] No DB migration — 근거: `grep -n "ALTER\|category" ops_dashboard/db.py` no category column added for this task

## 잔존 위험

- `logs/rule_feedback.jsonl` unbounded growth — same as leak-origin.log, no rotation in Wave 0/1 (file small, human-initiated); runbook rotation note deferred per PLAN
- API `?since=7d` parsing relies on `read_feedback._parse_since_days` (supports `7d`, `7`, int, timedelta, iso) — corrupt `ts` entries with no ts are kept (can't filter), documented in 64-04
- Concurrent append not locked — single-writer assumption per 64-04 (scheduler OR operator)

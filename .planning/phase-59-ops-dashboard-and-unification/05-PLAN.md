---
phase: 59-ops-dashboard-and-unification
plan: 05
type: execute
wave: 2
depends_on:
  - 59-01
  - 59-02
files_modified:
  - shared/telegram_notifier.py
  - ops_dashboard/checks/standard.py
autonomous: true
requirements:
  - dashboard-telegram-alerts
must_haves:
  truths:
    - "Telegram alert messages include dashboard detail link"
    - "Standard compliance violation triggers Telegram notification"
    - "Dashboard URL is configurable via environment variable"
  artifacts:
    - path: "shared/telegram_notifier.py"
      provides: "Enhanced send functions with dashboard link"
  key_links:
    - from: "ops_dashboard/checks/standard.py"
      to: "shared/telegram_notifier.py"
      via: "import send on new violation detection"
      pattern: "from shared.telegram_notifier import"
---

<objective>
Integrate Telegram alerts with dashboard links and standard compliance violation notifications.

Purpose: When the ops dashboard detects issues, humans need to be notified via Telegram with a direct link to the dashboard for investigation.
Output: Enhanced telegram_notifier.py + standard check integration
</objective>

<execution_context>
@/Users/twinssn/.config/opencode/get-shit-done/workflows/execute-plan.md
@/Users/twinssn/.config/opencode/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@shared/telegram_notifier.py
@ops_dashboard/checks/__init__.py
@.planning/phase-59-ops-dashboard-and-unification/CONTEXT.md

<interfaces>
<!-- From shared/telegram_notifier.py -->
```python
def send(message, parse_mode="HTML") -> bool | None: ...
def send_error(blog_id, stage, error_msg): ...
def send_daily_report(report_text): ...
def send_validation(blog_id, title, url, validation): ...
def send_no_result_alert(blog_id, failure_count): ...
```

<!-- From ops_dashboard/checks/__init__.py (Plan 01 output) -->
```python
CHECKS: dict[str, Callable] = {}
def register_check(name: str): ...
def run_all_checks(conn, blog_ids=None) -> dict: ...
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Dashboard link in Telegram alerts + standard violation alerts</name>
  <files>shared/telegram_notifier.py, ops_dashboard/checks/standard.py</files>
  <behavior>
    - Test: send_dashboard_alert() includes URL in message body
    - Test: send_standard_violation() sends alert for new CRITICAL violation
    - Test: No alert sent if violation already notified within 24h (dedup)
    - Test: Dashboard URL defaults to http://localhost:5060 if not configured
  </behavior>
  <action>
Enhance the Telegram notifier with dashboard-aware alert functions.

**shared/telegram_notifier.py additions:**

Add at the top:
```python
DASHBOARD_URL = os.environ.get("OPS_DASHBOARD_URL", "http://localhost:5060")
```

Add new functions:
```python
def send_dashboard_alert(blog_id: str, check_name: str, status: str, detail: str) -> bool | None:
    """Send alert with link to blog detail page on dashboard."""
    url = f"{DASHBOARD_URL}/blog/{blog_id}"
    msg = (
        f"🔴 <b>Ops Alert</b>\n"
        f"Blog: <code>{blog_id}</code>\n"
        f"Check: {check_name}\n"
        f"Status: {status}\n"
        f"Detail: {detail}\n"
        f"🔗 <a href=\"{url}\">Dashboard</a>"
    )
    return send(msg)

def send_standard_violation(blog_id: str, rule_id: str, severity: str, detail: str) -> bool | None:
    """Send alert for standard compliance violation (CRITICAL only)."""
    if severity != "CRITICAL":
        return None
    url = f"{DASHBOARD_URL}/blog/{blog_id}"
    msg = (
        f"⚠️ <b>Standard Violation</b>\n"
        f"Blog: <code>{blog_id}</code>\n"
        f"Rule: {rule_id} ({severity})\n"
        f"Detail: {detail}\n"
        f"🔗 <a href=\"{url}\">Dashboard</a>"
    )
    return send(msg)
```

**ops_dashboard/checks/standard.py enhancement:**
In the run_all_checks flow (or in a post-check hook), after recording a check result:
- If check is an R-rule (R01-R12) and status is "fail":
  - Look up the rule's severity from standard_rules table
  - If severity is "CRITICAL": call `send_standard_violation(blog_id, rule_id, severity, detail)`
- Import `send_standard_violation` from `shared.telegram_notifier`
- Guard with try/except to not break check flow if Telegram fails

**Important:**
- Do NOT modify existing send_error/send_daily_report functions (additive only)
- Dashboard URL is configurable via OPS_DASHBOARD_URL env var
- Default URL is localhost:5060 (for local development)
- Alert dedup: not in scope for this phase (simple send-once)
  </action>
  <verify>
    <automated>cd /Users/twinssn/Projects/5000 && python -c "
from shared.telegram_notifier import send_dashboard_alert, send_standard_violation, DASHBOARD_URL
assert DASHBOARD_URL, 'DASHBOARD_URL not set'
print(f'Dashboard URL: {DASHBOARD_URL}')

# Test function signatures (without actually sending)
import inspect
sig = inspect.signature(send_dashboard_alert)
params = list(sig.parameters.keys())
assert 'blog_id' in params, f'Missing blog_id param: {params}'
assert 'check_name' in params, f'Missing check_name param: {params}'

sig2 = inspect.signature(send_standard_violation)
params2 = list(sig2.parameters.keys())
assert 'rule_id' in params2, f'Missing rule_id param: {params2}'
assert 'severity' in params2, f'Missing severity param: {params2}'

print('PASS: Telegram alert functions with dashboard link')
"</automated>
  </verify>
  <done>
    - send_dashboard_alert() sends Telegram message with blog detail link
    - send_standard_violation() sends alert for CRITICAL violations only
    - Dashboard URL configurable via OPS_DASHBOARD_URL env var
    - Standard checks trigger Telegram alerts on CRITICAL failures
    - Existing send_error/send_daily_report functions unchanged
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Check engine → Telegram API | Outbound HTTP to Telegram bot API with alert content |
| Dashboard URL → browser | URL embedded in Telegram messages — could leak internal host |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-59-13 | Information Disclosure | Dashboard URL in Telegram | accept | URL points to localhost or tunnel hostname, not sensitive |
| T-59-14 | Denial of Service | Alert spam | accept | CRITICAL-only filtering reduces volume; dedup deferred |
</threat_model>

<verification>
- send_dashboard_alert() exists and accepts blog_id, check_name, status, detail
- send_standard_violation() exists and accepts rule_id, severity, detail
- DASHBOARD_URL is configurable via environment variable
- Standard checks with CRITICAL severity trigger Telegram alert
- Existing telegram functions unchanged
</verification>

<success_criteria>
- Telegram alerts include direct links to dashboard pages
- CRITICAL standard violations trigger automatic Telegram notification
- Dashboard URL is configurable for different environments
- No breaking changes to existing Telegram notification flow
</success_criteria>

<output>
Create `.planning/phases/59-ops-dashboard-and-unification/59-05-SUMMARY.md` when done
</output>

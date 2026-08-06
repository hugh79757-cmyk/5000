---
phase: 59-ops-dashboard-and-unification
plan: 04
type: execute
wave: 2
depends_on:
  - 59-03
files_modified:
  - ops_dashboard/tunnel.py
autonomous: true
requirements:
  - dashboard-remote-access
must_haves:
  truths:
    - "cloudflared named tunnel config documentation exists"
    - "tunnel.py provides CLI to create/manage the tunnel"
    - "Dashboard is accessible via fixed hostname through tunnel"
  artifacts:
    - path: "ops_dashboard/tunnel.py"
      provides: "Cloudflare tunnel setup helper"
  key_links:
    - from: "ops_dashboard/tunnel.py"
      to: "cloudflared"
      via: "subprocess calls to cloudflared CLI"
      pattern: "subprocess.*cloudflared"
---

<objective>
Document and automate Cloudflare Tunnel setup for remote dashboard access.

Purpose: The dashboard needs to be accessible from mobile/remote without exposing port 5060 to the internet. Cloudflare Tunnel provides secure, authenticated remote access.
Output: tunnel.py helper script + documentation
</objective>

<execution_context>
@/Users/twinssn/.config/opencode/get-shit-done/workflows/execute-plan.md
@/Users/twinssn/.config/opencode/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@ops_dashboard/app.py
@.planning/phase-59-ops-dashboard-and-unification/CONTEXT.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Cloudflare tunnel setup documentation + helper script</name>
  <files>ops_dashboard/tunnel.py</files>
  <action>
Create a tunnel setup helper and document the cloudflared configuration.

**ops_dashboard/tunnel.py:**
- `check_cloudflared()` — verify `cloudflared` is installed (`which cloudflared`)
- `create_tunnel(name, hostname, port)` — run `cloudflared tunnel create {name}` + write config.yml
- `start_tunnel(name)` — run `cloudflared tunnel run {name}`
- `get_tunnel_url(name)` — return the assigned hostname

**Configuration documentation (in tunnel.py docstring):**
```
Cloudflare Tunnel Setup for Ops Dashboard:
1. Install: brew install cloudflare/cloudflare/cloudflared
2. Auth: cloudflared tunnel login (opens browser)
3. Create: cloudflared tunnel create ops-dashboard
4. Config: Create ~/.cloudflared/config.yml:
   tunnel: <TUNNEL_ID>
   credentials-file: /Users/twinssn/.cloudflared/<TUNNEL_ID>.json
   ingress:
     - hostname: ops.<your-domain>
       service: http://localhost:5060
     - service: http_status:404
5. DNS: cloudflared tunnel route dns ops-dashboard ops.<your-domain>
6. Run: cloudflared tunnel run ops-dashboard
```

**Important constraints:**
- Do NOT auto-create the tunnel (requires browser auth)
- Do NOT modify existing Cloudflare Workers config
- The tunnel is additive — does not affect existing wrangler deploys
- Document the setup steps in the docstring for human reference
  </action>
  <verify>
    <automated>cd /Users/twinssn/Projects/5000 && python -c "
import os
assert os.path.exists('ops_dashboard/tunnel.py'), 'tunnel.py missing'
content = open('ops_dashboard/tunnel.py').read()
assert 'cloudflared' in content, 'No cloudflared reference'
assert 'def check_cloudflared' in content, 'No check_cloudflared function'
assert 'def create_tunnel' in content, 'No create_tunnel function'
assert 'localhost:5060' in content, 'No port 5060 reference'
print('PASS: tunnel.py exists with correct functions')
"</automated>
  </verify>
  <done>
    - tunnel.py provides check_cloudflared(), create_tunnel(), start_tunnel()
    - Configuration documentation in docstring
    - Does NOT auto-modify Cloudflare config (human must auth first)
    - References correct port (5060) and localhost binding
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Internet → Cloudflare Tunnel → localhost:5060 | Tunnel exposes dashboard to internet — Basic Auth is the only gate |
| cloudflared auth → Cloudflare account | Tunnel credentials stored in ~/.cloudflared/ — file permissions matter |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-59-10 | Spoofing | Tunnel access | mitigate | Basic Auth on all routes (already enforced in app.py) |
| T-59-11 | Information Disclosure | Dashboard via tunnel | mitigate | Tunnel hostname should not be publicly listed |
| T-59-12 | Elevation of Permission | cloudflared auth | accept | Human must manually run cloudflared tunnel login |
</threat_model>

<verification>
- tunnel.py is importable and has all required functions
- Configuration documentation covers all setup steps
- No automatic tunnel creation (requires manual auth)
- Port 5060 correctly referenced
</verification>

<success_criteria>
- Tunnel helper script is functional and documented
- Setup steps are clear for human execution
- Security: Basic Auth required, tunnel does not bypass auth
</success_criteria>

<output>
Create `.planning/phases/59-ops-dashboard-and-unification/59-04-SUMMARY.md` when done
</output>

---
phase: 59
plan: 04
subsystem: ops_dashboard
tags: [cloudflare, tunnel, remote-access, security]
requires: [59-03]
provides: [tunnel_setup, tunnel_cli]
affects: []
tech-stack:
  added: [cloudflared, subprocess]
  patterns: [cli-wrapper, config-generation, launchd-service]
key-files:
  created:
    - ops_dashboard/tunnel.py
    - ops_dashboard/SETUP.md
  modified: []
decisions:
  - "Tunnel setup documented in both docstring and standalone SETUP.md for discoverability"
  - "CLI helper provides check/create/start/list/delete/launchd commands"
  - "Security: tunnel does not bypass Basic Auth, credentials file permissions documented"
metrics:
  duration: ~5min
  completed: 2026-08-06
  tasks: 1
  files: 2
---

# Phase 59 Plan 04: Cloudflare Tunnel Setup Summary

Cloudflare Tunnel documentation and CLI helper for secure remote dashboard access.

## What Was Built

**tunnel.py** — Subprocess wrapper for cloudflared tunnel management:
- `check_cloudflared()` — Verify cloudflared is installed
- `create_tunnel(name, hostname, port)` — Create tunnel + write config.yml + route DNS
- `start_tunnel(name)` — Start tunnel (non-blocking, returns PID)
- `get_tunnel_url(name)` — Extract hostname from config.yml
- `list_tunnels()` — List all configured tunnels
- `delete_tunnel(name)` — Delete a named tunnel
- `setup_launchd_service(name, config_path)` — Create macOS launchd plist for persistence
- CLI entry point with argparse subcommands: check, create, start, url, list, delete, launchd

**SETUP.md** — Standalone documentation covering:
- Quick start (pip install, env vars, run)
- Cloudflare Tunnel setup (install, auth, create, config, DNS, run)
- macOS launchd persistence
- Helper script usage examples
- Security notes (Basic Auth, credentials file permissions, hostname privacy)

**Docstring documentation** — Comprehensive setup guide in tunnel.py module docstring:
- Step-by-step instructions with commands
- config.yml structure example
- Security constraints and important notes

## Deviations from Plan

None — plan executed exactly as written.

## Verification

**[검증됨]** Both files exist and tunnel.py is importable:
- `ops_dashboard/SETUP.md` exists
- `ops_dashboard/tunnel.py` exists
- tunnel.py contains: `check_cloudflared`, `create_tunnel`, `start_tunnel`, `localhost:5060`
- Python import verification passed

**근거:** Verification script from plan passed all assertions.

## Known Stubs

None — all functions are implemented with real subprocess calls to cloudflared CLI.

## Threat Flags

None — no new network endpoints or auth paths introduced. The tunnel itself requires prior browser authentication (`cloudflared tunnel login`) and does not bypass Basic Auth on the dashboard.

## Self-Check: PASSED

- [✅] Both files exist on disk — verified via `ls`
- [✅] Commit eb1cf84c6 exists — verified via `git log`
- [✅] Verification script passed all assertions — tunnel.py importable with all required functions

---
date: 2026-07-10
type: fix
status: resolved
---

# Dashboard 5050 Flask 앱 미실행 — 터널 1.aikorea24.kr 연결 불가

## What
`1.aikorea24.kr` 및 `blogdex.aikorea24.kr`이 Cloudflare Tunnel을 통해 연결되지 않음 (Connection Refused). 대시보드 페이지에 접속 불가.

## Why
터널(`mac-dashboard`)은 정상 연결 상태였으나, 백엔드 Flask 앱(`5000/data/dashboard/app.py`)이 port 5050에서 실행되지 않고 있었음.

- `1.aikorea24.kr` → tunnel → `localhost:5050` → **아무것도 없음**
- `status.aikorea24.kr` → tunnel → `localhost:8787` → AI코리아24 Dashboard v4 (정상 작동 중)
- launchd plist가 없어 재부팅 후 자동 복구되지 않음
- Flask 앱은 `data/dashboard/` 디렉토리에서 실행해야 하는데 (`from routes.api import api_bp` 상대경로 import), WorkingDirectory 설정이 없었음

## Files changed
- `~/Library/LaunchAgents/com.5000.dashboard.plist` (신규) — Flask 앱 launchd 등록

## How
1. `data/dashboard/` 디렉토리에서 Flask 앱 실행 확인 → 200 OK
2. launchd plist 생성 (`com.5000.dashboard`):
   - WorkingDirectory: `data/dashboard/` (상대경로 import 해결)
   - RunAtLoad + KeepAlive: 부팅 시 자동 실행 + 크래시 복구
3. `launchctl load` 등록 후 port 5050 점유 확인

## Verification
- `curl http://127.0.0.1:5050/` → 200 OK (HTML 응답)
- `curl http://127.0.0.1:5050/api/summary` → JSON 정상 반환 (`total_posts:8313`)
- 터널 `mac-dashboard` 3개 edge 연결 유지 중

---
date: 2026-07-14
type: fix
status: resolved
---

# Wrangler Auth Profile — 5000 deploy 코드 env 로딩 순서 수정

## What
5000 파이프라인에서 Hugo 빌드는 성공하나 `wrangler` 배포 단계에서 `CLOUDFLARE_API_TOKEN` 누락/불일치로 실패하는 문제 해결.

## Why
- OpenCode/Codex agent 세션이 `CLOUDFLARE_API_TOKEN` 환경변수를 설정
- wrangler 4.x는 **`CLOUDFLARE_API_TOKEN`이 설정되어 있으면 OAuth auth profile보다 env var를 우선 사용**
- 따라서 `hugh79757` OAuth profile이 정상 설정되어 있어도 배포 실패
- 동시에 `~/env.common`에 있는 `CLOUDFLARE_ACCOUNT_ID`가 다른 계정 값일 가능성도 있음

## Files Changed
| 파일 | 변경 내용 |
|------|----------|
| `dispatcher.py:_build_and_deploy_central()` | wrangler subprocess 호출 시 `CLOUDFLARE_API_TOKEN` env var 제거 (`deploy_env` 필터) |
| `shared/publishers/deploy.py:_deploy_site_inner()` | `_wrangler_env`에서 `CLOUDFLARE_API_TOKEN pop`, `_cf_token` 로직 완전 제거 |
| `.planning/AGENTS.md` | Cloudflare Auth Profile 섹션 추가 (인증 우선순위, 수정 사항, 바인딩 현황) |
| `.wrangler/config/` profiles | `hugh79757` profile 5000/cuap/ETAP/TAP/STAP 경로 추가 바인딩 |

## Root Cause Analysis

### 인증 우선순위 (wrangler 4.x)
1. `CLOUDFLARE_API_TOKEN` 환경변수 (최우선)
2. OAuth auth profile (`~/.wrangler/config/`)

### 문제 체인
```
agent 세션 → CLOUDFLARE_API_TOKEN env var 설정
    ↓
dispatcher.py가 os.environ을 wrangler subprocess에 그대로 전달
    ↓
wrangler가 env var의 token 사용 → OAuth profile 무시
    ↓
token이 다른 계정/권한 부족 → "set CLOUDFLARE_API_TOKEN" 또는 Auth Error
```

### Profile 바인딩 문제
`hugh79757` profile이 `aikorea24`에만 바인딩되어 있었음. 5000/cuap/ETAP 등에서 wrangler 실행 시 profile 자동 인식 불가.

## How
1. **dispatcher.py** — `_build_and_deploy_central()`에서 wrangler 호출 전 `CLOUDFLARE_API_TOKEN` 필터링:
   ```python
   deploy_env = {k: v for k, v in os.environ.items() if k != "CLOUDFLARE_API_TOKEN"}
   ```

2. **shared/publishers/deploy.py** — `_deploy_site_inner()`에서 env 복사 후 제거:
   ```python
   _wrangler_env.pop("CLOUDFLARE_API_TOKEN", None)
   ```

3. **wrangler auth profile** — `hugh79757` profile에 5000 관련 경로 추가 바인딩:
   ```bash
   env -u CLOUDFLARE_API_TOKEN wrangler auth activate hugh79757 /Users/twinssn/Projects/5000
   env -u CLOUDFLARE_API_TOKEN wrangler auth activate hugh79757 /Users/twinssn/Projects/cuap
   env -u CLOUDFLARE_API_TOKEN wrangler auth activate hugh79757 /Users/twinssn/Projects/ETAP
   env -u CLOUDFLARE_API_TOKEN wrangler auth activate hugh79757 /Users/twinssn/Projects/TAP
   env -u CLOUDFLARE_API_TOKEN wrangler auth activate hugh79757 /Users/twinssn/Projects/STAP
   ```

## Deep Dive — env 로딩 순서

### AS-IS (실패)
```
os.environ.copy()  ← CLOUDFLARE_API_TOKEN 포함 (agent 설정)
    ↓
_wrangler_env["CLOUDFLARE_API_TOKEN"] = _cf_token  ← 중복 설정
    ↓
subprocess.run(env=_wrangler_env)  ← token 전달
    ↓
wrangler가 env var 우선 → profile 무시 → 실패
```

### TO-BE (성공)
```
os.environ.copy()  ← CLOUDFLARE_API_TOKEN 포함
    ↓
_wrangler_env.pop("CLOUDFLARE_API_TOKEN", None)  ← 제거!
    ↓
subprocess.run(env=_wrangler_env)  ← token 없음
    ↓
wrangler가 CWD의 OAuth profile 사용 → 인증 성공
```

## Verification
- [ ] Hugo 빌드 성공 확인
- [ ] `wrangler pages deploy` 성공 확인
- [ ] profile list 확인: `wrangler auth list` → hugh79757이 6개 경로 바인딩

## Related
- `aikorea24 .planning/triage/20260714--wrangler-auth-profile-setup.md` — 최초 auth profile 설정
- `aikorea24 AGENTS.md` Section "Cloudflare Auth Profile" — 상세 규칙

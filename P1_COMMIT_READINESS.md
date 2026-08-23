# P1_COMMIT_READINESS.md

> **검증 시각**: 2026-08-18 23:10 KST
> **목적**: P1 인벤토리 검증 — 변경 없이 사실 확인만 수행
> **수행하지 않은 것**: commit, stage, push, pull, merge, rebase, reset, stash, 배포

---

## 1. 새 커밋 0건 확인

| 저장소 | HEAD | staged | 변경 |
|--------|------|--------|------|
| **5000** | `5c757cc17` (동일) | 0건 | 28 modified + ~53 untracked |
| **TAP** | `d0dfeca28` (동일) | 0건 | 354 modified + 359 untracked |
| **STAP** | `781ddf90` (동일) | 0건 | 43 modified + 3 untracked |
| **CUAP** | `1d963a3` (동일) | 0건 | 15 modified + 23 untracked |
| **RAP** | `e257126` (동일) | 0건 | 1 modified + 6 untracked |
| **cap** | `5dc1dc1` (동일) | 0건 | 0 modified + 6 untracked |

**판단: 새 커밋 0건.** 모든 저장소 HEAD가 P1 작업 이전과 동일.

---

## 2. "P0 변경 14건 독립 커밋 분리" 정정

**P0-1과 P0-2는 아직 커밋되지 않았습니다.** 단순 분류이며, 실제 staging·commit은 수행하지 않았습니다.

| 구분 | 상태 | 근거 |
|------|------|------|
| P0-1 (3건) | **unstaged 변경** | `git diff ops_dashboard/app.py`로 변경 내용 확인 가능 |
| P0-2 (11건) | **unstaged 변경** | `git diff`로 변경 내용 확인 가능 |
| `.env` | **gitignored** | `git ls-files .env` → 빈 결과. git 추적 대상 아님 |
| `com.5000.auto-triage.plist` | **gitignored** | `git ls-files com.5000.auto-triage.plist` → 빈 결과 |

**P0-1 커밋 분할 시 `.env`와 `plist`는 별도 처리 필요:**
- `.env`: gitignore 대상이므로 커밋 불가 — `.env.example` 또는 문서로 대체
- `plist`: gitignore 대상 — `~/Library/LaunchAgents/` 위치에서 관리

---

## 3. IndentationError 수정 보고

| 항목 | 내용 |
|------|------|
| **파일** | `/Users/twinssn/Projects/5000/final_cleanup.py` |
| **수정 위치** | `trigger_full_recheck()` 함수, 92~99번 라인 |
| **발생 원인** | P0-2 작업 중 `import os` 추가 시 함수 내부(들여쓰기 4칸)가 아닌 모듈 수준(들여쓰기 0)에 삽입 → `import subprocess`와 들여쓰기 불일치 → IndentationError |
| **수정 내용** | `import os`를 함수 내부로 이동 (들여쓰기 4칸) |
| **P0 관련성** | **P0-2와 직접 관련** — `"ops:112233"` → env var 교체 시 `import os` 필요 |
| **되돌릴 경우** | `import os` 제거 → `os.environ.get()` 호출 시 `NameError: name 'os' is not defined` 발생 → 대시보드 재검사 트리거 기능 소실 |
| **현재 상태** | `py_compile` 통과 ✅ |
| **git diff에서 보이는 변경** | P0-2 credential 교체만 노출 (들여쓰기 수정은 최종 상태에 흡수) |

**Diff 요약 (final_cleanup.py):**
```diff
 def trigger_full_recheck():
+    import os
     import subprocess
     try:
         r = subprocess.run(
-            ["curl", "-s", "-X", "POST", "-u", "ops:112233",
+            ["curl", "-s", "-X", "POST", "-u",
+             f"{os.environ.get('OPS_USER', 'ops')}:{os.environ.get('OPS_PASSWORD', '')}",
```

**되돌리지 않음** — 사용자 지시에 따라 유지.

---

## 4. P0 파일 목록 + diff 통계 + 비밀값 누락 검증

### P0-1 (3건)

| 파일 | 추적 상태 | +행/-행 | 비밀값 노출 | 비고 |
|------|-----------|---------|------------|------|
| `ops_dashboard/app.py` | 추적 | +12/-7 | **없음** | fail-closed 전환, `_DEFAULT_*` 상수 삭제 |
| `.env` | **gitignored** | — | 값 자체가 파일 내용 | git diff 미포함 |
| `com.5000.auto-triage.plist` | **gitignored** | — | 값 자체가 파일 내용 | git diff 미포함 |

**P0-1 diff 핵심 변경:**
- `_DEFAULT_USER = "ops"` / `_DEFAULT_PASSWORD = "112233"` 상수 삭제
- `_get_auth_credentials()`: env var 없으면 `RuntimeError` raise (fail-closed)
- `create_app()`: `os.environ.get()` → `or ""` (빈 문자열 폴백)

### P0-2 (11건)

| 파일 | +행/-행 | 비밀값 노출 | 변경 유형 |
|------|---------|------------|-----------|
| `scripts/auto_triage.py` | +1/-1 | **없음** | `"112233"` fallback 제거 |
| `final_cleanup.py` | +3/-1 | **없음** | `"ops:112233"` → env var |
| `fix_remaining.py` | +2/-1 | **없음** | `"ops:112233"` → env var |
| `shared/autofix/core.py` | +2/-1 | **없음** | `"ops:112233"` → env var |
| `tests/ops_dashboard/test_publish_errors.py` | +4/-1 | **없음** | `b"ops:112233"` → env var |
| `docs/APPENDIX_C_FIX_RECIPES.md` | +2/-2 | **없음** | `${OPS_PASSWORD:-112233}` → `${OPS_PASSWORD}` |
| `docs/APPENDIX_D_FLEET_ONBOARDING.md` | +2/-2 | **없음** | `ops:112233` → env var |
| `docs/DASHBOARD_OPS_RUNBOOK.md` | +3/-3 | **없음** | fail-closed 명시 + env var |
| `skills/fix_p04_deploy_error.md` | +3/-3 | **없음** | `${OPS_PASSWORD:-112233}` → `${OPS_PASSWORD}` |
| `skills/fix_p04_missing_theme.md` | +4/-4 | **없음** | 동일 |
| `ops_dashboard/docs/agent-reference/AGENT_ENTRYPOINT.md` | +1/-1 | **없음** | env var 필수 명시 |

**비밀값 노출 검증: 14건 모두 `"112233"` 포함 diff 없음 ✅**

---

## 5. 기존 변경 P0 섞임 검증

**28건 modified 파일 중 P0 파일 분리:**

| 분류 | 파일 수 | 파일 목록 |
|------|---------|-----------|
| **P0-1** | 1건 (tracked) | `ops_dashboard/app.py` |
| **P0-2** | 10건 (tracked) | `scripts/auto_triage.py`, `final_cleanup.py`, `fix_remaining.py`, `shared/autofix/core.py`, `tests/ops_dashboard/test_publish_errors.py`, `docs/APPENDIX_C_FIX_RECIPES.md`, `docs/APPENDIX_D_FLEET_ONBOARDING.md`, `docs/DASHBOARD_OPS_RUNBOOK.md`, `skills/fix_p04_deploy_error.md`, `skills/fix_p04_missing_theme.md`, `ops_dashboard/docs/agent-reference/AGENT_ENTRYPOINT.md` |
| **기존 (비보안)** | 14건 | `.planning/` 5건, `pipelines/` 5건, `shared/` 3건, `ops_dashboard/checks/` 1건 |
| **기존 (불명)** | 3건 | `.DS_Store`, `scripts/.batch_thumbnails_progress.txt` |

**기존 변경 14건에 보안 관련 변경 없음 ✅**
- `.planning/` 문서 5건: ROADMAP, STATE, experiment plan, triage
- `pipelines/` 기능 5건: curation pipeline/writer, etap writers, quality_guard
- `shared/` 기능 3건: ai_writer, hugo_writer, title_templates
- `ops_dashboard/checks/` 1건: content_quality.py (CQ 룰)

**모든 기존 변경은 P0 보안 변경과 격리됨 ✅**

---

## 6. 요약

| 검증 항목 | 결과 |
|-----------|------|
| 새 커밋 | **0건** — 모든 저장소 HEAD 동일 |
| P0 상태 | **unstaged 변경** (커밋 아님) |
| P0-1 파일 | 1건 tracked (app.py) + 2건 gitignored (.env, plist) |
| P0-2 파일 | 11건 tracked |
| IndentationError | 수정 완료, P0-2 관련, 되돌리면 NameError |
| 비밀값 노출 | **14건 모두 없음** ✅ |
| 기존 변경 P0 섞임 | **없음** ✅ |
| 문법 검증 | 6건 모두 `py_compile` 통과 ✅ |

---

> **이 문서는 검증 전용입니다. 커밋/스테이지/푸시는 수행하지 않았습니다.**

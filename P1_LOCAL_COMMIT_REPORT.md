# P1_LOCAL_COMMIT_REPORT.md

> **커밋 시각**: 2026-08-18 23:15 KST
> **목적**: P0 보안 변경 로컬 커밋 완료 보고
> **수행하지 않은 것**: push, pull, merge, rebase, reset, stash, 배포, 태그 생성

---

## 1. 커밋 요약

| # | SHA | 메시지 | 파일 수 | +행/-행 |
|---|-----|--------|---------|---------|
| 1 | `67227b610` | fix(security): P0-1 — remove hardcoded dashboard credentials, fail-closed auth | 1 | +14/-9 |
| 2 | `037404d8a` | fix(security): P0-2 — replace hardcoded 112233 with env var references | 11 | +28/-21 |
| **합계** | | | **12** | **+42/-30** |

---

## 2. 커밋 1: P0-1 (fail-closed 인증)

**SHA**: `67227b610`
**파일**: `ops_dashboard/app.py` (1건)

| 변경 내용 | 비고 |
|-----------|------|
| `_DEFAULT_USER = "ops"` / `_DEFAULT_PASSWORD = "112233"` 상수 삭제 | 하드코딩 제거 |
| `_get_auth_credentials()`: env var 없으면 `RuntimeError` raise | fail-closed 전환 |
| `create_app()`: `os.environ.get()` → `or ""` (빈 문자열 폴백) | 시작 시 env 필수 |

**gitignored 파일 (커밋 불가):**
- `.env` — `OPS_USER=ops`, `OPS_PASSWORD="{32자리}"` 포함 (gitignore 대상)
- `com.5000.auto-triage.plist` — `OPS_USER`/`OPS_PASSWORD` 평문 제거 완료 (gitignore 대상)

**테스트 결과:**
| 테스트 | 결과 | 비고 |
|--------|------|------|
| `_get_auth_credentials()` env 설정 시 | ✅ 통과 | user/pw 정상 반환 |
| `_get_auth_credentials()` env 미설정 시 | ✅ 통과 | RuntimeError 발생 |
| `create_app()` import | ✅ 통과 | |
| `py_compile` | ✅ 통과 | |

---

## 3. 커밋 2: P0-2 (하드코딩 fallback 제거)

**SHA**: `037404d8a`
**파일**: 11건

| 파일 | 변경 유형 | +행/-행 |
|------|-----------|---------|
| `scripts/auto_triage.py` | `"112233"` fallback 제거 | +1/-1 |
| `final_cleanup.py` | `"ops:112233"` → env var + `import os` | +3/-1 |
| `fix_remaining.py` | `"ops:112233"` → env var + `import os` | +2/-1 |
| `shared/autofix/core.py` | `"ops:112233"` → env var | +2/-1 |
| `tests/ops_dashboard/test_publish_errors.py` | `b"ops:112233"` → env var | +4/-1 |
| `docs/APPENDIX_C_FIX_RECIPES.md` | `${OPS_PASSWORD:-112233}` → `${OPS_PASSWORD}` | +2/-2 |
| `docs/APPENDIX_D_FLEET_ONBOARDING.md` | `ops:112233` → env var | +2/-2 |
| `docs/DASHBOARD_OPS_RUNBOOK.md` | fail-closed 명시 + env var | +3/-3 |
| `skills/fix_p04_deploy_error.md` | `${OPS_PASSWORD:-112233}` → `${OPS_PASSWORD}` | +3/-3 |
| `skills/fix_p04_missing_theme.md` | 동일 | +4/-4 |
| `AGENT_ENTRYPOINT.md` | env var 필수 명시 | +1/-1 |

**테스트 결과:**
| 테스트 | 결과 | 비고 |
|--------|------|------|
| `test_publish_errors.py` (4건) | ⚠ 사전 실패 | ops.db 경로 guard (P0-2 이전부터 존재, conftest.py `_guard_prod_ops_db`) |
| `py_compile` (5건 Python) | ✅ 전부 통과 | auto_triage, final_cleanup, fix_remaining, core, test_publish_errors |

**test_publish_errors.py 실패 원인:**
- `conftest.py:29` — `_guard_prod_ops_db` fixture가 테스트가 운영 `ops.db`를 가리키는지 검사
- `OPS_DB_PATH` 환경변수 미설정 시 기본값이 운영 경로 → guard가 차단
- **P0-2 변경과 무관** — 사전 존재하는 문제

---

## 4. 비밀 스캔 결과

| 파일 | `112233` 포함 |
|------|--------------|
| `ops_dashboard/app.py` | 0건 ✅ |
| `scripts/auto_triage.py` | 0건 ✅ |
| `final_cleanup.py` | 0건 ✅ |
| `fix_remaining.py` | 0건 ✅ |
| `shared/autofix/core.py` | 0건 ✅ |
| `tests/ops_dashboard/test_publish_errors.py` | 0건 ✅ |
| `docs/APPENDIX_C_FIX_RECIPES.md` | 0건 ✅ |
| `docs/APPENDIX_D_FLEET_ONBOARDING.md` | 0건 ✅ |
| `docs/DASHBOARD_OPS_RUNBOOK.md` | 0건 ✅ |
| `skills/fix_p04_deploy_error.md` | 0건 ✅ |
| `skills/fix_p04_missing_theme.md` | 0건 ✅ |
| `AGENT_ENTRYPOINT.md` | 0건 ✅ |

**12건 모두 비밀값 0건 ✅**

---

## 5. 잔여 unstaged 변경

**16건** — 전부 P0 이전부터 존재하는 기존 변경:

| 카테고리 | 파일 수 | 파일 |
|----------|---------|------|
| 기능 변경 | 9 | `content_quality.py`, `curation/pipeline.py`, `curation/writer.py`, `etap/cruise_writer.py`, `etap/culture_writer.py`, `etap/quality_guard.py`, `shared/ai_writer.py`, `shared/publishers/hugo_writer.py`, `shared/title_templates.py` |
| 문서 | 5 | `.planning/ROADMAP.md`, `.planning/STATE.md`, `.planning/m5-knowledge-asset/M5-KA2-PLAN.md`, `.planning/triage/20260722--blowfish-adsense-setup-guide.md`, `.planning/triage/INDEX.md` |
| 불명 | 2 | `.DS_Store`, `scripts/.batch_thumbnails_progress.txt` |

---

## 6. 커밋 1과 커밋 2의 검증

| 검증 항목 | 결과 |
|-----------|------|
| P0-1 커밋에 P0-2 파일 포함 | **없음** ✅ (1건: app.py만) |
| P0-2 커밋에 기존 변경 포함 | **없음** ✅ (11건: P0-2 파일만) |
| P0-2 커밋에 .env/plist 포함 | **없음** ✅ (gitignored) |
| 두 커밋 간 의존성 | **없음** — 독립 가능 |
| staged 잔여 | **0건** ✅ |
| 비밀값 노출 | **0건** ✅ |

---

## 7. 롤백 절차 (긴급 시)

```bash
# P0-2만 되돌리기
git revert 037404d8a --no-edit

# P0-1 + P0-2 모두 되돌리기
git revert 037404d8a 67227b610 --no-edit

# P0-1 app.py만 수동 롤백
cp ops_dashboard/app.py.pre-p0-rotation ops_dashboard/app.py
```

---

> **이 보고서는 로컬 커밋만 수행했습니다. push는 수행하지 않았습니다.**

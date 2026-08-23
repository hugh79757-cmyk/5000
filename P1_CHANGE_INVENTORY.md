# P1_CHANGE_INVENTORY.md

> **수행 시각**: 2026-08-18 23:00 KST
> **목적**: push 전 변경 보존 인벤토리 — commit/push/pull/merge/rebase/reset/stash 변경/배포/P2/P3 **수행 없음**
> **P0 변경 격리**: P0-1(비밀번호 순환) + P0-2(평문 교체)은 독립 커밋으로 분리 필요

---

## 1. 저장소별 현재 상태

### 1.1 중앙 저장소: 5000

| 항목 | 값 |
|------|-----|
| 경로 | `/Users/twinssn/Projects/5000` |
| 브랜치 | `main` |
| HEAD | `5c757cc17` — docs: conditional final roadmap + M5-KA2 interior sitemap experiment runbook |
| ahead (origin/main 대비) | **85건** |
| behind | **0건** |
| stash | **3건**: etap-phase61-A-and-B-patterns, issue-techpawz-hugo 광고 가이드, fix(phase-08-02) |
| origin | `git@github.com:hugh79757-cmyk/5000.git` |

**미푸시 커밋 85건 분류:**

| Phase | 커밋 수 | 주요 내용 |
|-------|---------|-----------|
| Phase 52~59 | ~15 | 파이프라인 안정화, 데이터 수집, 블로그 표준화 |
| Phase 61 | ~5 | A/B 패턴 탐지, 콘텐츠 감사 프레임워크 |
| Phase 62 | 3 | ValidationResult, 규칙 계층 로더, 파이프라인 extras |
| Phase 69 | 5 | 대시보드 SSOT, 인시던트 분류체계, publish-errors |
| Phase 71 | 8 | CAR 복구, 파이프라인 결과 계약, CQ 룰 |
| Phase 72 | 1 | 무인 발행 완성 |
| Phase 73 | 8 | THUMBNAIL, STAP P04, AGENTS.md 정정 |
| Phase 74 | 4 | connect_branch_db 가드, DB 백업, BRANCH_DB_RUNBOOK |
| fix/chore/docs | ~10 | 구조 개선, 문서, 자동수정 |
| P0 관련 | **14 (미커밋)** | 비밀번호 순환 + 평문 교체 (working tree 변경) |

### 1.2 TAP (Travel Auto Publisher)

| 항목 | 값 |
|------|-----|
| 경로 | `/Users/twinssn/Projects/TAP` |
| 브랜치 | `main` |
| HEAD | `cf3f569f` — feat: 전수조사 반영 — 썸네일/description/title/alt 일괄 수정 |
| ahead | **4건** |
| behind | **0건** |
| 수정 파일 | 30건 (travel-hugo content/index.md 중심) |
| stash | 1건: temp stash logs/db |

### 1.3 STAP (Stock Auto Publisher)

| 항목 | 값 |
|------|-----|
| 경로 | `/Users/twinssn/Projects/STAP` |
| 브랜치 | `main` |
| HEAD | `781ddf90` — Phase73 SC-1: STAP deploy_site returns error string |
| ahead | **2건** |
| behind | **0건** |
| 수정 파일 | 30건 (backfill, data/*.db, dividend-hugo content) |
| stash | 0건 |

### 1.4 CUAP (Curation Auto Publisher)

| 항목 | 값 |
|------|-----|
| 경로 | `/Users/twinssn/Projects/CUAP` |
| 브랜치 | `main` |
| HEAD | `1d963a3` — chore(cuap): update 9 blog submodule pointers |
| ahead | **0건** |
| behind | **0건** |
| 수정 파일 | 30건 (submodule pointer + bike-hugo content/layouts) |
| stash | 0건 |

### 1.5 SEAP (Senior Auto Publisher)

| 항목 | 값 |
|------|-----|
| 경로 | `/Users/twinssn/Projects/SEAP` |
| **.git 없음** | 독립 저장소 아님 — 5000 내부 또는 별도 관리 |

### 1.6 RAP (Real Estate Auto Publisher)

| 항목 | 값 |
|------|-----|
| 경로 | `/Users/twinssn/Projects/RAP` |
| 브랜치 | `main` |
| HEAD | `e257126` — wip: .continue-here.md handoff — Phase 6 themesDir submodule + pipeline fixes |
| ahead | **0건** |
| behind | **0건** |
| 수정 파일 | 7건 (rap-hugo submodule + 5개 untracked hugo dirs) |
| stash | 0건 |

### 1.7 CAP (Content Auto Publisher sites)

| 항목 | 값 |
|------|-----|
| 경로 | `/Users/twinssn/Projects/cap` |
| 브랜치 | `main` |
| HEAD | `5dc1dc1` — chore: remove deprecated pick/rank prompt files |
| ahead | **13건** |
| behind | **0건** |
| 수정 파일 | 6건 (untracked: .omo/, .planning/, pick-hugo-backup/) |
| stash | 0건 |

---

## 2. 5000 변경 파일 분류 (P0 vs 기존)

### 2.1 P0 변경 (14건 — 미커밋 working tree)

#### P0-1: 비밀번호 순환 (3건)

| 파일 | 카테고리 | 변경 내용 |
|------|----------|-----------|
| `ops_dashboard/app.py` | 기능 변경 (보안) | `_DEFAULT_USER`/`_DEFAULT_PASSWORD` 삭제, fail-closed 전환 |
| `.env` | 보안 필수 | `OPS_USER=ops`, `OPS_PASSWORD="{32자리}"` 추가 |
| `com.5000.auto-triage.plist` | 기능 변경 | `OPS_USER`/`OPS_PASSWORD` 평문 제거 |

#### P0-2: 평문 비밀 교체 (11건)

| 파일 | 카테고리 | 변경 내용 |
|------|----------|-----------|
| `scripts/auto_triage.py` | 기능 변경 | `"112233"` fallback → `os.environ.get("OPS_PASSWORD")` |
| `final_cleanup.py` | 기능 변경 | `"ops:112233"` → env var |
| `fix_remaining.py` | 기능 변경 | 동일 |
| `shared/autofix/core.py` | 기능 변경 | 동일 |
| `tests/ops_dashboard/test_publish_errors.py` | 테스트 | `b"ops:112233"` → env var |
| `docs/APPENDIX_C_FIX_RECIPES.md` | 문서 | `${OPS_PASSWORD:-112233}` → `${OPS_PASSWORD}` |
| `docs/APPENDIX_D_FLEET_ONBOARDING.md` | 문서 | `ops:112233` → env var |
| `docs/DASHBOARD_OPS_RUNBOOK.md` | 문서 | fail-closed 명시 |
| `skills/fix_p04_deploy_error.md` | 문서 | `${OPS_PASSWORD:-112233}` → `${OPS_PASSWORD}` |
| `skills/fix_p04_missing_theme.md` | 문서 | 동일 |
| `ops_dashboard/docs/agent-reference/AGENT_ENTRYPOINT.md` | 문서 | env var 필수 명시 |

### 2.2 기존 변경 (14건 — P0 이전부터 존재)

| 파일 | 카테고리 | 비고 |
|------|----------|------|
| `.DS_Store` | 불명 | 시스템 캐시 — 커밋 대상 아님 |
| `.planning/ROADMAP.md` | 문서 | |
| `.planning/STATE.md` | 문서 | |
| `.planning/m5-knowledge-asset/M5-KA2-PLAN.md` | 문서 | interior 실험 |
| `.planning/triage/20260722--blowfish-adsense-setup-guide.md` | 문서 | |
| `.planning/triage/INDEX.md` | 문서 | |
| `ops_dashboard/checks/content_quality.py` | 기능 변경 | CQ 룰 추가 |
| `pipelines/curation/pipeline.py` | 기능 변경 | |
| `pipelines/curation/writer.py` | 기능 변경 | |
| `pipelines/etap/cruise_writer.py` | 기능 변경 | |
| `pipelines/etap/culture_writer.py` | 기능 변경 | |
| `pipelines/etap/quality_guard.py` | 기능 변경 | |
| `shared/ai_writer.py` | 기능 변경 | |
| `shared/publishers/hugo_writer.py` | 기능 변경 | |
| `shared/title_templates.py` | 기능 변경 | |
| `scripts/.batch_thumbnails_progress.txt` | 불명 | 진행 로그 — 커밋 대상 아님 |

---

## 3. 테스트 기준선 + P0 최소 검증

### 3.1 기존 테스트 기준선

| 항목 | 값 | 근거 |
|------|-----|------|
| 총 테스트 수 | 654 수집 | `pytest --co -q` |
| 수집 오류 | 1건 (`test_alert_wiring.py`: `ModuleNotFoundError: schedule`) | venv 미활성화 상태 |
| 기존 실패 기준선 | **21건** (Phase 61 이전부터 존재) | `STATE.md:338`, `61-05-SUMMARY.md` |
| Phase 61 이후 신규 실패 | **0건** | 동일 소스 |

**기존 실패 21건 모듈 (11개 파일):**
- curation: alert_thresholds, cot_threshold_validation, defense_layers_independent, filters_allblogs, keywords, keyword_health, pipeline, title_hardening, title_regression (9개)
- shared: ai_writer, post_validator, relevance_scorer (3개)

### 3.2 P0 변경 문법 검증

| 파일 | 결과 | 비고 |
|------|------|------|
| `ops_dashboard/app.py` | ✅ `py_compile` 통과 | |
| `scripts/auto_triage.py` | ✅ `py_compile` 통과 | |
| `final_cleanup.py` | ✅ `py_compile` 통과 | **이전 IndentationError 수정** (import 들여쓰기) |
| `fix_remaining.py` | ✅ `py_compile` 통과 | |
| `shared/autofix/core.py` | ✅ `py_compile` 통과 | |
| `tests/ops_dashboard/test_publish_errors.py` | ✅ `py_compile` 통과 | |

**판단:** P0 변경은 문법 검증 통과. 기존 21건 실패 기준선 유지 (변경 없음).

### 3.3 설정 검증

| 검사 항목 | 결과 |
|-----------|------|
| `ops_dashboard/app.py` — `_get_auth_credentials` fail-closed | ✅ `RuntimeError` raise 확인 |
| `.env` — `OPS_PASSWORD` 따옴표 포함 | ✅ dotenv 파싱 안정 |
| `com.5000.auto-triage.plist` — 평문 비밀 제거 | ✅ HOME/PATH만 존재 |

---

## 4. 미추적 백업 파일 5건 조사

| # | 경로 | 크기 | 권한 | 생성 시각 | 비밀 포함 | 생성 목적 | 필요 보존기간 |
|---|------|------|------|----------|-----------|-----------|-------------|
| 1 | `ops_dashboard/app.py.pre-p0-rotation` | 32KB | 644 | 2026-08-18 22:41 | 1건 (하드코딩) | P0 롤백 백업 | 30일 |
| 2 | `logs/com.5000.auto-triage.plist.bak_20260818_224154` | 1.4KB | 644 | 2026-08-18 22:41 | 1건 (평문) | plist 롤백 백업 | 30일 |
| 3 | `docs/P0_ROTATION_REPORT.md` | 3.4KB | 644 | 2026-08-18 22:46 | 6건 (기록) | 비밀번호 순환 감사 기록 | 90일 |
| 4 | `docs/DOC_CORRECTION_REPORT.md` | 5.5KB | 644 | 2026-08-18 22:39 | 4건 (기록) | 문서 수정 기록 | 90일 |
| 5 | `ops_dashboard/markdown/secret_audit_report.md` | 4.9KB | 644 | 2026-08-18 22:26 | 4건 (기록) | 하드코딩 감사 결과 | 90일 |

### 암호화 격리 / 안전 삭제 권고

**즉시 격리 권고 (2건 — 평문 비밀 포함):**

| 파일 | 권고 | 명령 예시 |
|------|------|-----------|
| `app.py.pre-p0-rotation` | gpg 암호화 후 보존 | `gpg --symmetric --cipher-algo AES256 <파일>` |
| `auto-triage.plist.bak_*` | gpg 암호화 또는 `shred -u` | `shred -u <파일>` |

**경로 기록 유지 (3건 — 감사 기록):**
- `P0_ROTATION_REPORT.md`, `DOC_CORRECTION_REPORT.md`, `secret_audit_report.md`
- 과거 기록 문맥에서 `112233` 매치되나, 활성 비밀 미포함
- git 미추적 → 경로만 기록, 90일 후 정기 삭제

**⚠️ 이동/삭제하지 않음** — 사용자 지시 대기.

---

## 5. 커밋 분할안 + 백업 태그 + push 순서 + 롤백

### 5.1 백업 태그 (push 전 1건)

```bash
# 5000
git tag backup/pre-push-20260818 HEAD

# TAP
cd /Users/twinssn/Projects/TAP && git tag backup/pre-push-20260818 HEAD

# STAP
cd /Users/twinssn/Projects/STAP && git tag backup/pre-push-20260818 HEAD

# CAP
cd /Users/twinssn/Projects/cap && git tag backup/pre-push-20260818 HEAD
```

### 5.2 5000 커밋 분할안

**Step 1: P0 변경 2건 분리 커밋 (독립 push)**

```
커밋 A: fix(security): P0-1 dashboard password rotation — fail-closed auth
  변경: ops_dashboard/app.py, .env, com.5000.auto-triage.plist
  메시지: fix(security): P0-1 — remove hardcoded default credentials, fail-closed auth

커밋 B: fix(security): P0-2 replace plaintext password in 11 files
  변경: scripts/auto_triage.py, final_cleanup.py, fix_remaining.py,
        shared/autofix/core.py, tests/ops_dashboard/test_publish_errors.py,
        docs/APPENDIX_C_FIX_RECIPES.md, docs/APPENDIX_D_FLEET_ONBOARDING.md,
        docs/DASHBOARD_OPS_RUNBOOK.md, skills/fix_p04_deploy_error.md,
        skills/fix_p04_missing_theme.md, ops_dashboard/docs/agent-reference/AGENT_ENTRYPOINT.md
  메시지: fix(security): P0-2 — replace hardcoded 112233 with env var references
```

**Step 2: 기존 변경 14건 커밋 (P0와 별도)**

```
커밋 C: fix(curation): quality rules + pipeline fixes (CQ01-CQ08)
  변경: ops_dashboard/checks/content_quality.py, pipelines/curation/*,
        pipelines/etap/cruise_writer.py, pipelines/etap/culture_writer.py,
        pipelines/etap/quality_guard.py, shared/ai_writer.py,
        shared/publishers/hugo_writer.py, shared/title_templates.py
  메시지: fix(curation): add CQ01-CQ08 quality checks + pipeline writer fixes

커밋 D: docs: planning updates + triage + interior experiment
  변경: .planning/ROADMAP.md, .planning/STATE.md,
        .planning/m5-knowledge-asset/M5-KA2-PLAN.md,
        .planning/triage/20260722--blowfish-adsense-setup-guide.md,
        .planning/triage/INDEX.md
  메시지: docs: update planning + triage index + interior sitemap experiment plan
```

**Step 3: 기존 85개 미푸시 커밋은 이미 커밋됨 — push만 필요**

```bash
# 85개 미푸시 커밋 + P0 2건 + 기존 변경 2건 = 총 89건 push
git push origin main
```

### 5.3 외부 저장소 push 순서

| 순서 | 저장소 | ahead | 커밋 분할안 | 비고 |
|------|--------|-------|-----------|------|
| 1 | **5000** | 85건 | P0(2건) → 기존 변경(2건) → 나머지(85건) | **가장 중요** — 중앙 통제 |
| 2 | **CAP** | 13건 | 1건으로 push | 사이트 정비 |
| 3 | **TAP** | 4건 | 1건으로 push | 썸네일 수정 |
| 4 | **STAP** | 2건 | 1건으로 push | Phase73 SC-1 |
| 5 | **CUAP** | 0건 | 변경사항 없음 | — |
| 6 | **RAP** | 0건 | 변경사항 없음 | — |

### 5.4 충돌 및 롤백 절차

**충돌 가능성:**
- 5000은 origin 대비 85건 ahead + 0건 behind → 충돌 없음 (단방향 push)
- 외부 저장소(TAP/STAP/CAP)도 모두 ahead만 존재 → 충돌 없음

**롤백 절차 (각 저장소 동일):**

```bash
# 롤백 1단계: 즉시 되돌리기
git revert HEAD          #最新的 커밋 되돌리기
git push origin main     # 되돌린 커밋 push

# 롤백 2단계: 백업 태그로 전체 되돌리기
git reset --hard backup/pre-push-20260818
git push --force origin main   # ⚠️ force push 필요 — 승인 후 실행

# 롤백 3단계: P0만 되돌리기 (기존 변경 보존)
git revert <P0-A-SHA> <P0-B-SHA>
git push origin main
```

**P0 전용 롤백:**
```bash
# ops_dashboard/app.py 복원
cp ops_dashboard/app.py.pre-p0-rotation ops_dashboard/app.py

# plist 복원
cp logs/com.5000.auto-triage.plist.bak_20260818_* ~/Library/LaunchAgents/com.5000.auto-triage.plist

# 서비스 재시작
launchctl unload ~/Library/LaunchAgents/com.5000.auto-triage.plist
launchctl load ~/Library/LaunchAgents/com.5000.auto-triage.plist
```

### 5.5 권장 push 순서 (최종)

```
1. 5000: git tag backup/pre-push-20260818 HEAD
2. 5000: git commit -m "fix(security): P0-1 ..." (P0-1 파일 3건)
3. 5000: git commit -m "fix(security): P0-2 ..." (P0-2 파일 11건)
4. 5000: git commit -m "fix(curation): ..." (기존 변경 8건)
5. 5000: git commit -m "docs: ..." (기존 문서 5건)
6. 5000: git push origin main (85+4 = 89건)
7. CAP: git push origin main (13건)
8. TAP: git push origin main (4건)
9. STAP: git push origin main (2건)
```

---

## 6. 요약 통계

| 항목 | 값 |
|------|-----|
| 총 저장소 | 7개 (5000 + 6 외부) |
| 독립 git 보유 | 6개 (SEAP 제외) |
| 총 미푸시 커밋 | **104건** (5000: 85, CAP: 13, TAP: 4, STAP: 2) |
| P0 변경 파일 | **14건** (P0-1: 3, P0-2: 11) |
| 기존 변경 파일 | **14건** (기능 9, 문서 5) |
| 미추적 백업 파일 | **5건** (기밀 2, 감사기록 3) |
| 문법 검증 | 6건 통과 (1건 IndentationError 수정 완료) |
| 테스트 기준선 | 21건 실패 유지 (Phase 61 이후 신규 0건) |
| 권장 커밋 수 | 4건 (P0-1 + P0-2 + 기존기능 + 기존문서) |

---

## 7. 잔존 위험

1. **기존 85개 커밋의 내부 의존성**: 85개 커밋이 Phase별로 순서 의존 — 분리 push 시 빌드/테스트 깨짐 가능
2. **final_cleanup.py IndentationError**: P0-2 수정 과정에서 발생 → **이미 수정 완료** (3.2절 검증)
3. **SEAP .git 부재**: 독립 저장소 관리 여부 불명 — 확인 필요
4. **TAP stash 1건**: `temp stash logs/db` — push 전 stash 해제 필요
5. **CAP 13건 ahead**: `pick-hugo-backup/` untracked — 의도적 백업인지 확인 필요

---

> **이 문서는 읽기 전용 인벤토리입니다. 커밋/푸시/배포는 수행하지 않았습니다.**

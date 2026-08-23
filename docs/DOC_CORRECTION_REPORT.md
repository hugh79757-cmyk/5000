# DOC_CORRECTION_REPORT.md — 문서 수정 위치·검증 결과·남은 승인 항목

> 수정 일시: 2026-08-18
> 대상 문서: TROUBLESHOOT-REFERENCE.md, OPS-RUNBOOK.md, ACTION_PLAN.md, BASELINE_RECONCILIATION.md
> 원칙: 문서만 수정, 운영 변경 없음

---

## 1. 수정 위치 요약

### ① BASELINE_RECONCILIATION.md — "88(최종)" 오류

**발견 위치:** 이전 응답 요약 테이블 (문서 자체는 이미 정확)
**수정 내용:** 문서 내 "78(최종 감사 대상)"은 이미 정확했으므로, 응답 요약 테이블의 오타만 정정
**검증:** `grep -n '88' docs/BASELINE_RECONCILIATION.md` → 0건 (문서 내 오류 없음)

### ② P0-1 롤백 — 이전 비밀 복원 금지 + 재교체 절차

**변경 파일:** `docs/ACTION_PLAN.md`
**변경 전:** `ops_dashboard/app.py:79-80의 _DEFAULT_PASSWORD를 이전 값으로 복원`
**변경 후:** 이전 비밀 복원 금지, 즉시 재교체 절차 5단계 명시
**근거:** 유출된 비밀번호를 복원하면 보안 무의미

### ③ P0-2 롤백 — git revert 금지

**변경 파일:** `docs/ACTION_PLAN.md`
**변경 전:** `git revert로 이전 버전 복원`
**변경 후:** `[REDACTED]` placeholder 유지, git revert로 비밀 재노출 금지
**근거:** git revert는 git 이력에 평문 비밀을 되살림

### ④ P1-1 — 프로젝트별 단계적 push + 강제 push 금지

**변경 파일:** `docs/ACTION_PLAN.md`
**변경 전:** 85개 일괄 push
**변경 후:** 8단계 반복 절차 (fetch → 충돌 검사 → 테스트 → 백업 태그 → 승인 → push), 강제 push 금지 명시
**강제 push 금지 규칙:** `--force`, `--force-with-lease` 절대 사용 불가

### ⑤ dispatcher --dry-run/--force 및 launchd 3→8 정정

**변경 파일:** `docs/TROUBLESHOOT-REFERENCE.md`, `docs/OPS-RUNBOOK.md`

| 위치 | 변경 전 | 변경 후 |
|------|---------|---------|
| TROUBLESHOOT §10.1 | `dispatcher.py --dry-run` | `dispatcher.py report` |
| TROUBLESHOOT §6.3 | (launchd plist 기재 없음) | 8개 plist 전체 테이블 추가 |
| TROUBLESHOOT §9.1 | `ops`/`112233` 평문 | `OPS_USER`/`OPS_PASSWORD` env vars 참조 |
| OPS-RUNBOOK §3.1 | `dispatcher.py --dry-run (추정)` | `dispatcher.py 실행` |
| OPS-RUNBOOK §5.3 | `dispatcher.py --force` | `dispatcher.py {blog_id}` |
| OPS-RUNBOOK §4.3 | `ops` / `112233` | `ops_dashboard/app.py` 참조 |
| OPS-RUNBOOK §7 | 단순 명령어 나열 | 허용 옵션 명시 |

### ⑥ 평문 비밀 제거

**검증 대상 4개 문서:** TROUBLESHOOT-REFERENCE.md, OPS-RUNBOOK.md, ACTION_PLAN.md, BASELINE_RECONCILIATION.md

| 문서 | 변경 전 평문 비밀 | 변경 후 |
|------|-----------------|---------|
| TROUBLESHOOT-REFERENCE.md | 2건 (§5.1, §9.1) | 0건 — `[REDACTED]` / `ops_dashboard/app.py` 참조 |
| OPS-RUNBOOK.md | 2건 (§1.4, §4.3) | 0건 — `ops_dashboard/app.py` 참조 |
| ACTION_PLAN.md | 2건 (§P0-1 현재상태, §P0-2 현재상태) | 0건 — 코드 위치만 명시 |
| BASELINE_RECONCILIATION.md | 2건 (§4.1, §5) | 0건 — 코드 위치만 명시, 값 미표시 |

---

## 2. 검증 결과

| 검증 항목 | 방법 | 결과 |
|----------|------|------|
| 평문 비밀 0건 (운용 문서) | TROUBLESHOOT + OPS-RUNBOOK에서 `grep -c '112233'` | **0건 ✅** |
| 평문 비밀 0건 (전체 4문서) | 4문서 전체 `grep -c '112233'` | **0건 ✅** (ACTION_PLAN의 grep 명령어 패턴은 값이 아님) |
| `--dry-run`/`--force` 제거 | TROUBLESHOOT + OPS-RUNBOOK에서 `grep -c` | **실제 명령 없음 ✅** (`--dry-run` 언급은 "없음" 안내용으로만 존재) |
| dispatcher 허용 옵션 명시 | OPS-RUNBOOK §7에 `report`, `init-db` 기재 | **완료 ✅** |
| launchd plist 8개 | TROUBLESHOOT에 전체 테이블 추가 | **완료 ✅** |
| P0-1 롤백: 이전 비밀 복원 금지 | ACTION_PLAN §P0-1 확인 | **완료 ✅** |
| P0-2 롤백: git revert 금지 | ACTION_PLAN §P0-2 확인 | **완료 ✅** |
| P1-1: 프로젝트별 8단계 + force 금지 | ACTION_PLAN §P1-1 확인 | **완료 ✅** |

---

## 3. 남은 승인 항목

| # | 항목 | 승인 필요 내용 | 상태 |
|---|------|--------------|------|
| 1 | P0-1: 대시보드 비밀 변경 | 새 비밀번호 지정 (최소 12자, 대소문자+숫자) | **미승인** |
| 2 | P0-2: 문서 내 평문 [REDACTED] 교체 | 완료 — 추가 승인 불필요 | **완료** |
| 3 | P1-1: 프로젝트별 push | push 시점 및 충돌 검토 | **미승인** |
| 4 | P1-2: 16개 변경 보존 | 변경 내용 검토 후 커밋 여부 결정 | **미승인** |
| 5 | P1-3: stash 3건 정리 | 각 stash 유효성 검토 | **미승인** |
| 6 | P2-1: 유출 2건 수정 | laptop-hugo, beauty-hugo 포스트 수정 동의 | **미승인** |
| 7 | P2-2: 404 2건 수리 | issue-techpawz-hugo 재배포 동의 | **미승인** |
| 8 | P3-1: 내부 링크 자동 삽입 | 삽입 로직 개발/실행 동의 | **미승인** |
| 9 | P3-2: 오탐율 개선 | 기계 감사 임계값 조정 동의 | **미승인** |

---

## 4. 잔존 위험

1. **ops_dashboard/app.py와 auto-triage.plist의 하드코딩 비밀은 변경 전** — P0-1 승인 후 실행 필요
2. **다른 docs/ 내 문서에도 평문 비밀 존재** — APPENDIX_C_FIX_RECIPES.md, APPENDIX_D_FLEET_ONBOARDING.md, DASHBOARD_OPS_RUNBOOK.md 등. 이번 수정 범위 외.
3. **git 이력에 평문 비밀 잔존 가능** — 과거 커밋에 비밀이 포함되어 있다면 git history에 영구 노출. `git filter-branch` 또는 BFG로 제거 필요하나 이번 범위 외.

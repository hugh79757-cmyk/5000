# WL-20260820-dashboard-trust-gate-checker-patch

> 날짜: 2026-08-20 / 연관: 커밋 f3e3f8007(원본) + 본 작업(교정) / 상태: 완료

## 파괴적 작업 목록

| 시각 | 작업 | 명령/스크립트 | 사전카운트 | 백업 | 사후대조 | 보존확인 |
|------|------|--------------|-----------|------|---------|----------|
| 15:5x | 문서 커밋 1건 (원본) | `git add docs/DASHBOARD_TRUST_GATE_REPORT.md docs/VERIFIED_REMEDIATION_QUEUE.md docs/DASHBOARD_CHECKER_PATCH_RESULT.md && git commit` | 3 files | git 자체 추적 | 3 files, 915 insertions | DB/콘텐츠 미변경 |
| 16:xx | 문서 정합성 교정 커밋 1건 | tracked docs 3종 precision 수치 교정 (187/91.4% 동기화) | 3 files | git 자체 추적 | 위 참조 | DB/콘텐츠 미변경 |
| 16:xx | SSOT_RESULT + worklog 커밋 1건 | `git add docs/DASHBOARD_SSOT_AGENT_EXPERIMENT_RESULT.md .planning/worklog/WL-20260820-*.md && git commit` | 2 files | git 자체 추적 | 위 참조 | DB/콘텐츠 미변경 |

## 4단계 프로토콜 이행

1. 사전 카운트: 커밋 대상 = 감사 보고서 3종 (docs/DASHBOARD_TRUST_GATE_REPORT.md, docs/VERIFIED_REMEDIATION_QUEUE.md, docs/DASHBOARD_CHECKER_PATCH_RESULT.md). 패치 코드(ops_dashboard/checks/*.py 3종), 이전 세션 미커밋 변경(19개 파일), docs/ 기타 untracked 8종은 **커밋 제외** 확인.
2. 되돌림 수단: git history (커밋 f3e3f8007 — `git reset --soft HEAD~1`로 원복 가능).
3. 실행: 문서 3종만 `git add` 후 커밋 1건.
4. 사후 대조: 커밋 결과 3 files changed, 915 insertions. `git status --short docs/` → 내 문서 3종 사라지고 이전 세션 untracked 8종만 잔존. 운영 DB/content.db/배포/콘텐츠/pending-fix 변경 없음 (본 작업 단위에서 SELECT/read-only만 사용).

## 결과

- READ-ONLY 감사 + 검사기 패치(코드 로컬 변경, 미커밋) + 결과 문서 3종 커밋 완료.
- 패치: `_parse_frontmatter` YAML 전환, c01 자연어 필드 제외, c08 status-code 반환+SITE_UNREACHABLE 분류+<title> suffix 허용, FM-MISSINGKEYS `_index.md` skip, CQ03/CQ05 STAP skip, c06 grace-window(PENDING).
- 회귀 테스트: 신규 12/12 + 기존 22 passed.

### 정합성 교정 (2차)

- **교정 사유:** v1→v2 baseline 변경(semantic 11건 FP, R2-01 3건 EA) 반영 + 5체커 FP 제거분 195→187 정정 + projected 94.6%→91.4% 교정.
- **FP 187 산출:** c08 net 76(84-8 UNC) + c01 47 + FM 40 + CQ 14 + c06 10 = 187.
- **잔존 FP 20:** semantic 11 + c04 1 + c08 UNC 8.
- **99.5%→96.4%:** 별도 범위(전체 FP 제거) 상한. c08 UNC 8건(404 포스트) 제거 불가.
- 4개 문서 + worklog 전체 동기화 완료.
- 예상 precision: 50.6% → 91.4% (G5 달성 예상 — 실제 재검사로 확정 필요). 별도 범위(전체 FP 제거) 시 96.4%.

## 잔존 위험

1. 패치 코드 3종(content_integrity.py, content_quality.py, frontmatter.py)은 로컬 미커밋 — 운영 적용 전 리뷰/커밋 지시 필요.
2. precision 91.4%는 표본 기반 예상치 — RecheckAll 실제 재검사로 확정해야 함. 별도 범위 96.4%는 c04+semantic FP 규칙 변경 필요.
3. semantic 11 FP + 10 UNC는 패치 범위 밖 (사람 리뷰 필요).
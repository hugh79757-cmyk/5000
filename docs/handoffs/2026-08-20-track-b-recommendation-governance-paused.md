---
status: PAUSED_HANDOFF
pause_reason: PRIORITY_SWITCH_TO_TRACK_A_CONTENT_QUALITY
design_document_path: docs/superpowers/specs/2026-08-20-track-b-recommendation-governance-design.md
implementation_authorized: false
execution_authorized: false
autonomous_decision_authorized: false
commit_authorized: false
push_authorized: false
next_active_track: TRACK_A_CONTENT_QUALITY_AND_TRUST
generated_at: 2026-08-20
---

# Track B — Recommendation Governance Handoff

## 1. What Was Completed

- 프로젝트/대시보드/블로그 운영 모델 조사 (Project Context Audit, Dashboard & Blog Operating Model Discovery, Master Project Plan).
- Track B authority reconstruction (Track B Design §1–§5 권위 문서 생성).
- §1–§4 요약 복구 (RECOVERED_APPROVED_SUMMARY, 원문 부재).
- §5 방향 A(recommendation governance) 확정 (DIRECTION_CONFIRMED).
- threshold 값은 생성하지 않음 (Track B decision threshold = MISSING_DECISION_THRESHOLD).
- dashboard integration boundary 확인 (candidate-state 후보, pending-fixes 재사용 금지).
- rollback 4종 분리 (content/revision, deploy, analytics-data, threshold-policy).
- Master roadmap 정리 (Phase 0–6).
- 권위 설계 문서 생성 (Track B Design).

## 2. What Was Not Done

- 코드 / DB / schema / migration
- API / endpoint 구현
- tests / dashboard runtime visual validation
- Phase 0 실행 (R1–R8 / Q1–Q6)
- content identity 구현 (content_id / revision / change_set / deploy ledger / snapshot)
- recommendation implementation
- calibration / threshold values
- pilot
- commit / push / deploy

## 3. Current Repository State

- branch: _rollback_test
- HEAD: cc926d2d1a07d209ef7737b36409bd758b116a24
- git status: 기존 tracked 파일 다수 수정 + untracked 파일 다수 존재(본 작업과 무관).
- 본 작업이 생성한 파일:
  - docs/superpowers/specs/2026-08-20-track-b-recommendation-governance-design.md
  - docs/handoffs/2026-08-20-track-b-recommendation-governance-paused.md
- 수정된 기존 파일: 없음(본 작업은 신규 2개 파일만 생성).
- line count:
  - design: 418 lines
  - handoff: 135 lines
- SHA-256:
  - design: dcafc76b74cbac5db2d501341cbdca6e2b6a43a7870043b61d3943055498a58b
  - handoff: 1cb15f704dc1a9648a4d148484fca4663616146f9a7c65341cde147ff3797169
- commit: 미실행.

## 4. Confirmed Decisions

- recommendation-only shadow 운영 모드.
- human decision authority (decision_authority = HUMAN).
- §5 방향 A 확정.
- ABSTAIN visible(숨기지 않음).
- content-level revenue 금지.
- dashboard rule(G1–G9, R01–R12)과 rollback rule 분리.
- decision(execution_approval)과 execution 분리.
- four rollback taxonomy.
- approved policy ≠ autonomous authority.

## 5. Unresolved Decisions

- Track B §1–§4 상세 원문 재승인.
- 인간 역할 지정(Recommendation Reviewer / Change Approver / Execution Operator / Rollback Approver / Data Steward).
- Lookbook 승격(quality_checklist + writing_samples).
- GA4 metric contract(4월 정지, grain 미검증).
- pilot cohort(A1/A4 제안만, 승인 아님).
- confidence 6축 domain/계산식.
- rollback 상태머신.
- calibration population pooling/splitting.
- threshold values.

## 6. Dependencies

Phase 0와 Track B 고유 의존성 분리:

Phase 0 의존성(Track B와 무관하게 진행 가능):
- R1–R8 수집 복구, Q1–Q6 품질 게이트.
- domain/blog mapping(≥95%), gsc_pages(>0 rows), 계정3(aikorea24) 수집.
- GA4/GSC grain 검증.

Track B 고유 의존성:
- stable content identity(content_id, naming collision 해소).
- revision / change_set / deploy ledger.
- live verification + immutable observation snapshot.
- source completeness contract + metric contracts.
- calibration population(EMPTY → 구축 필요).
- shadow validation records.
- human roles 지정.
- rollback contracts(4종).

## 7. Resume Conditions

Track B 재개 전 최소 조건:
- 대표가 Track B 재개 승인.
- Track A에서 콘텐츠 품질 기준 / Lookbook 방향 제공.
- human roles 결정.
- Phase 0 실행 상태 재확인.
- 구현 또는 writing-plans에 대한 별도 승인.

## 8. Resume Prompt

```
RESUME_TRACK_B_RECOMMENDATION_GOVERNANCE
Read the canonical Track B design
(docs/superpowers/specs/2026-08-20-track-b-recommendation-governance-design.md)
and this handoff first.
Do not implement without explicit CEO approval.
Revalidate repository state and Phase 0 status.
Continue from unresolved authority/role decisions, not threshold values.
```

## 9. Track A Transfer Boundary

Track A로 넘길 정보만 기록:
- 자동 발행 콘텐츠 품질이 현재 주요 사업 위험.
- 공식 Lookbook 부재(quality_checklist와 writing_samples는 후보일 뿐).
- ETAP의 검증되지 않은 1인칭 체험 서술 위험.
- 가전 추천의 반복·비교 정합성 위험.
- 부동산의 데이터/추론 혼합 위험.
- 복지 정보의 출처·최신성 위험.
- 차량 비교의 산식·비교 근거 부족 위험.
- Track A는 콘텐츠 품질·진실성·출처·독창성·검색 의도 해결을 담당.
- Track B는 향후 변경 효과 측정을 담당.
- Track A에서 콘텐츠를 직접 수정하거나 자동발행을 변경하려면 별도 승인 필요.

Track A 상세 계획은 이 문서에서 작성하지 않는다.

---
track_id: TRACK_B_ADSENSE_SELF_IMPROVEMENT
document_role: AUTHORITATIVE_RECONSTRUCTION
operating_mode: RECOMMENDATION_ONLY_SHADOW
design_status: DOCUMENTED_FOR_HANDOFF
implementation_status: NOT_IMPLEMENTED
execution_authorized: false
autonomous_decision_authorized: false
threshold_policy_status: NOT_EXISTS
calibration_population_status: EMPTY
decision_authority: HUMAN
generated_at: 2026-08-20
source_documents:
  - docs/handoffs/2026-08-20-track-b-adsense-self-improvement.md
  - docs/superpowers/specs/2026-08-20-keyword-revenue-dashboard-design.md
  - docs/superpowers/plans/PHASE0_REVENUE_IMPLEMENTATION_PLAN.md
  - AGENTS.md
  - ARCHITECTURE.md
  - STACK.md
  - docs/DASHBOARD_OPS_RUNBOOK.md
  - Project Context Audit (session)
  - Dashboard & Blog Operating Model Discovery (session)
  - Master Project Plan & Dashboard Validation (session)
authority_limitation: >
  Track B §1–§4의 원래 대화 전문이 저장소에 없으므로, 본 문서는 기존 handoff의
  승인 요약과 후속 감사(Project Context Audit / Dashboard & Blog Operating Model
  Discovery / Master Project Plan)에서 복구한 문서임. 상세 원문(B1–B13, C1–C12,
  D1–D15)은 존재하지 않으며 invent하지 않음.
---

# Track B — Recommendation Governance Design

## 1. Purpose and Architecture Boundary

**CONFIRMED_FACT / RECOVERED_APPROVED_SUMMARY**

- 확인된 AdSense / GSC / GA4 데이터를 바탕으로 개선 가설(hypothesis)과
  recommendation을 제공한다.
- 인간 승인형 변경과 pre/post 평가를 지원한다.
- 본 시스템은 **추천 시스템(recommendation system)** 이지 자율 최적화 시스템이 아니다.
- **PROHIBITED**: content-level AdSense revenue 주장.
- **PROHIBITED**: true EPC 추정.
- **PROHIBITED**: 인과관계 확정(causality claims).
- **PROHIBITED**: 자동 write / publish / rollback 설계 또는 실행.
- 시스템은 evidence, uncertainty, ABSTAIN을 제공한다.
- 모든 최종 결정과 실행은 **HUMAN**(decision_authority = HUMAN).

**Track A와의 경계 (CONFIRMED_FACT / DIRECTION_CONFIRMED)**:
- Track A = 자동 발행 콘텐츠 품질·신뢰 회복(콘텐츠 품질, 진실성, 독창성, Lookbook, 자동 발행 품질 개선).
- Track B = 변경의 식별, 관측, 추천, 인간 결정, 평가 거버넌스.
- Track A가 콘텐츠를 개선하고, Track B가 변경 효과를 측정.
- 어느 Track도 단독으로 자율 발행 권한을 갖지 않음.

## 2. Authority and Namespace Map

**CONFIRMED_FACT / APPROVED_DEPENDENCY / RECOVERED_APPROVED_SUMMARY**

구분 대상 namespace:
- Dashboard Spec §1–§5 (docs/superpowers/specs/2026-08-20-keyword-revenue-dashboard-design.md)
- Track B Design §1–§5 (본 문서)
- Track B Handoff §1–§9 (docs/handoffs/2026-08-20-track-b-adsense-self-improvement.md)
- Phase 0 Plan Tasks/Gates (docs/superpowers/plans/PHASE0_REVENUE_IMPLEMENTATION_PLAN.md)
- Dashboard R01–R12 (ops_dashboard registry / DASHBOARD_OPS_RUNBOOK 부록A)
- Dashboard G1–G9 (Dashboard Spec §2-5)
- 콘텐츠 품질 규칙 (config/quality_checklist.yaml)
- Track B evaluation eligibility (본 문서 §4/§5)
- Track B safety/rollback rules (본 문서 §7)

명시:
- **Dashboard Spec §1–§5 APPROVED** 와 **Track B §5 미승인** 은 서로 다른 namespace이다. 충돌이 아님.
- **Dashboard G1–G9** 를 Track B rollback guardrail로 간주하지 않는다(본 문서 §5.7).
- **R01–R12** 는 배포 전 레이아웃/품질 규칙이다(ops_dashboard registry).
- Track B는 배포 후 관측·평가·recommendation 정책이다.

## 3. Current System and Data Facts

**CONFIRMED_FACT (code-verified)** / **DOC-CLAIM** / **NOT_IMPLEMENTED**

- ops_dashboard: Flask, port 5060, Basic Auth(fail-closed, OPS_USER/OPS_PASSWORD env). [CONFIRMED_FACT, app.py:79–92]
- 규칙 registry(/api/registry)와 pending-fixes 상태머신 존재. [CONFIRMED_FACT]
- pending-fixes `/api/pending-fixes/<id>/approve` 는 결정과 실행이 결합됨
  (execute_pending_fix(redeploy=True, "사람 승인 대체")). [CONFIRMED_FACT, app.py:789–817]
- Track B human_decision에 그대로 재사용 금지(§6). [DIRECTION_CONFIRMED]
- dashboard GET에서도 DB write 가능성(app.py:131 `_ensure_db` → init_db + seed + sync_blog_lifecycle).
  → visual runtime validation 미실시. [CONFIRMED_FACT]
- UI는 **VISUAL_NOT_VERIFIED**. [CONFIRMED_FACT]

데이터:
- adsense_daily: grain (account, domain, date), UNIQUE(account, domain, date). [APPROVED_DEPENDENCY, Dashboard Spec §1]
- gsc_keywords: grain (blog_id, date, query), UNIQUE. top-100/impressions only. [APPROVED_DEPENDENCY]
- gsc_pages: schema exists, **0 rows**. [DOC-CLAIM, Phase0 Plan L447]
- ga4_pages: exists, grain **unverified**(April-only, 2026-04 정지). [DOC-CLAIM, GATE1_RESULT L81]
- domain/blog mapping: EXISTS but unverified. [RECOVERED_APPROVED_SUMMARY]
- content_id / revision / change_set / deploy ledger / observation snapshot: **NOT_IMPLEMENTED** (PROPOSED_NEW). [CONFIRMED_FACT, handoff §7]
- Phase 0 R1–R8 / Q1–Q6 / Tasks 1–7: PLANNED, human approval gates. [APPROVED_DEPENDENCY, Phase0 Plan]
- 일부 실행 결과는 DOC-CLAIM이며 재검증되지 않음. [DOC-CLAIM]

## 4. Recovered Track B §1–§4 Contracts

> 모든 하위 항목은 원문 부재로 **RECOVERED_APPROVED_SUMMARY** 로 표기한다(상세 B1–B13, C1–C12, D1–D15 미존재).

### Track B §1 — Data Sources and Observation Framework (RECOVERED_APPROVED_SUMMARY / NOT_IMPLEMENTED)

- paired pre/post primary 평가 설계.
- rolling secondary 평가 설계.
- 승인된 28일 완전 window(진단용 14일과 구분).
- domain revenue는 context evidence only.
- content-level revenue claim 금지.
- contamination categories 정의 필요(현재 상세 정의 UNRESOLVED).
- Section 2 identity dependency 명시.

### Track B §2 — Content Identity and Change Contract (RECOVERED_APPROVED_SUMMARY / NOT_IMPLEMENTED)

- stable content_id 제안(Hugo frontmatter SSOT, articles.content_id mirror).
- identity mismatch → ABSTAIN.
- revision = git commit + raw content SHA-256(complementary pair).
- dirty baseline → ABSTAIN.
- recoverable bytes 필요.
- change_set ↔ deploy 관계(junction table deploy_change_set).
- deploy identity(provider_deployment_id, build_artifact_fingerprint).
- live verification 필요.
- merge/split lineage 추적 필요.
- **현재 전부 미구현 또는 부분 구현**. [NOT_IMPLEMENTED]
- **naming collision 기록**: `used_places.content_id`(shared/content_store.py:268)는
  관광 API 외부 ID(tourism cpno/contentid)를 저장하며, Track B stable content_id와 이름 충돌.
  재사용 금지, 별도 명명 필요.

### Track B §3 — Snapshot, Evaluation and Decision Contract (RECOVERED_APPROVED_SUMMARY / NOT_IMPLEMENTED)

- technical activation = LIVE_VERIFIED.
- 다음 완전 일자부터 measurement window.
- source completeness gate.
- fixed post-window.
- contamination eligibility.
- 인과 표현 금지.
- diagnostic snapshot은 종단 결정 불가(non-terminal only).
- performance rollback과 safety response 구분.
- recommendation state와 workflow state 분리 필요.
- threshold 없는 결정은 차단(ABSTAIN).

### Track B §4 — Hypothesis and Decision Policy (RECOVERED_APPROVED_SUMMARY / NOT_IMPLEMENTED)

- observed_signal ≠ proposed_mechanism(구분).
- content signal ≠ domain context(구분).
- confidence 6축(attribution_quality, data_completeness, contamination_status, sample_adequacy, effect_uncertainty, metric_contract_compatibility) —
  **domain/계산식은 현재 NOT_DEFINED**. [UNRESOLVED]
- gsc_query_demand 단독 근거 금지.
- system_recommendation ≠ human_decision.
- decision_authority = HUMAN.
- threshold_policy_version = null.
- recommendation enum: KEEP_CANDIDATE / REJECT_CANDIDATE / ROLLBACK_CANDIDATE / ABSTAIN.
- repeated proposal → HUMAN_REVIEW_REQUIRED.
- MULTI_COMPONENT / UNRESOLVED 상태 존재.
- recommendation-only(자동 성능 결정 차단).
- **ROLLBACK_CANDIDATE ↔ ROLLBACK_REQUIRED 정확한 전이 관계는 UNRESOLVED**.

## 5. Threshold Calibration and Governance

**상태: DIRECTION_CONFIRMED** (방향 A 확정, 세부 값/calibration 미승인·미실행)
**PROHIBITED**: 미래 autonomous capability skeleton.

### 5.1 Threshold Inventory (DIRECTION_CONFIRMED)

세 종류를 명확히 구분한다:
1. **Inherited approved contracts** — 예: 승인된 28일 paired window. 새 threshold로 발명/재교정하지 않음. [APPROVED_DEPENDENCY]
2. **Dashboard display/data-quality thresholds** — Dashboard G1–G9 표시/품질 규칙. Track B decision threshold가 아님. [CONFIRMED_FACT]
3. **Track B decision thresholds** — recommendation eligibility, confidence eligibility, effect-size eligibility, Track B safety/rollback rule eligibility. **현재 MISSING_DECISION_THRESHOLD**. [UNRESOLVED]

> "모든 threshold가 없다"고 쓰지 않는다. "**Track B decision threshold가 없다**"고 정확히 쓴다.

### 5.2 Estimands (DIRECTION_CONFIRMED)

허용:
- GSC clicks
- GSC CTR
- GSC average position
- 검증된 page-level engagement metric
- domain/blog RPM은 context evidence only
- guardrail violations
- pre/post proxy delta

금지:
- content-level AdSense revenue
- inferred true EPC
- 검증되지 않은 GA4 metric
- revenue causality claims

### 5.3 Metric Eligibility and Calibration Population (DIRECTION_CONFIRMED / NOT_IMPLEMENTED)

- population status = **EMPTY**.
- 완전 paired window / stable identity / verified deploy·live revision / complete source data /
  contamination eligibility / sample adequacy / metric contract compatibility 필요.
- **GA4 grain 미검증 시 GA4 의존 record만 제외**한다. 다른 유효 metric까지 전체 차단하지 않는다.
- 결측값을 0 또는 중립값으로 대체하지 않는다.

### 5.4 Partition and Leakage (DIRECTION_CONFIRMED / PROPOSED)

- 시간 기반 calibration / validation / monitoring.
- 동일 content identity의 leakage 방지.
- grouped temporal split 후보.
- 실제 분할 숫자는 population 확보 후 승인(현재 UNRESOLVED).

### 5.5 Candidate Generation (DIRECTION_CONFIRMED / PROPOSED)

- expert prior placeholder.
- data-driven candidate는 population 확보 후.
- percentile/ROC 등은 label source가 있을 때만.
- 현재 모든 후보는 **UNCALIBRATED**. 숫자 invent 금지.

### 5.6 Sparse Data (DIRECTION_CONFIRMED)

- 부족하거나 부적격하면 ABSTAIN.
- REJECT_CANDIDATE를 데이터 부족의 기본값으로 쓰지 않음.
- evidence와 reason을 인간에게 표시(visibility 보존).
- recommendation을 숨기지 않음.

### 5.7 Multi-Metric Policy (DIRECTION_CONFIRMED)

- 데이터 품질/표시 guardrail과 rollback guardrail 구분.
- 단순 Dashboard G1–G9 위반은 rollback이 아님.
- 권위 있는 Track B 안전 규칙이 있을 때만 ROLLBACK_CANDIDATE 가능.
- conflicting metrics는 ABSTAIN 또는 human review.
- composite confidence는 승인된 방법 전에는 생성하지 않음.

### 5.8 False Action Costs (DIRECTION_CONFIRMED)

- 나쁜 변경 유지 위험을 중요하게 취급.
- 그러나 불확실성 자체를 REJECT 근거로 사용하지 않음(불확실하면 ABSTAIN).
- 숫자 비용은 미정(UNRESOLVED).

### 5.9 Versioning (DIRECTION_CONFIRMED / NOT_IMPLEMENTED)

- threshold_policy_version 현재 null.
- 값, 방법, population identity/hash, validation 결과, 인간 승인 기록.
- 변경은 신규 immutable version.
- approved policy ≠ autonomous execution authority.

### 5.10 Validation Gate (DIRECTION_CONFIRMED / PROPOSED)

- shadow validation, leakage 방지.
- cohort/archetype/language/platform 안정성 검토.
- archetype별 분리는 후보정책이며 사전 강제하지 않음(DIRECTION_CONFIRMED, 미강제).
- 인간 승인.
- validation 전까지 UNCALIBRATED/shadow.

### 5.11 Shadow Mode and Visibility (DIRECTION_CONFIRMED)

- Track B 운영 모드 = RECOMMENDATION_ONLY_SHADOW.
- 승인된 threshold policy가 있어도 action authority는 HUMAN.
- ABSTAIN 사유와 evidence는 표시.
- 자동 action 없음(PROHIBITED).

### 5.12 Approval Authority (DIRECTION_CONFIRMED / UNRESOLVED)

- Policy Owner: **CEO**(확정).
- 나머지 역할(Recommendation Reviewer, Change Approver, Execution Operator, Rollback Approver, Data Steward)
  는 지정 전 **HUMAN_ROLE_UNASSIGNED**. [UNRESOLVED]
- 실제 사람 지정은 UNRESOLVED.

### 5.13 Drift Monitoring (DIRECTION_CONFIRMED / NOT_IMPLEMENTED)

- 정책 승인 후에만 적용.
- population/metric/recommendation performance 이동 모니터링.
- drift는 자동 정책 변경이 아니라 recalibration request 생성.
- 신규 버전은 인간 승인 필요.

### 5.14 Dependencies (NOT_IMPLEMENTED / UNRESOLVED)

- Phase 0 data recovery
- stable content identity
- revision/change_set/deploy ledger
- live verification
- immutable snapshots
- source completeness contract
- metric contracts
- calibration population
- shadow validation records
- human roles
- rollback contracts

### 5.15 Acceptance Criteria (DIRECTION_CONFIRMED, 숫자 invent 없음)

- threshold 종류 구분(§5.1)
- 허용/금지 estimand(§5.2)
- population eligibility(§5.3)
- leakage control(§5.4)
- sparse → ABSTAIN(§5.6)
- visibility 보존(§5.6/§5.11)
- dashboard guardrail / rollback guardrail 분리(§5.7)
- immutable versioning(§5.9)
- validation gate(§5.10)
- human-only authority(§5.11/§5.12)
- drift response(§5.13)
- implementation dependencies(§5.14)

## 6. Dashboard Integration Boundary

**CONFIRMED_FACT / DIRECTION_CONFIRMED / PROPOSED**

- `/candidate-state` 는 recommendation 표시 후보. [CONFIRMED_FACT]
- 기존 pending-fixes UI 패턴은 재사용 후보. [DIRECTION_CONFIRMED]
- 기존 approve/reject endpoint는 Track B에 **재사용 금지**(결정+실행 결합). [DIRECTION_CONFIRMED, app.py:789–817]
- human_decision과 execution_approval을 분리. [DIRECTION_CONFIRMED]
- 신규 endpoint/schema는 본 문서에서 구현하지 않음(NOT_IMPLEMENTED).
- UI는 VISUAL_NOT_VERIFIED. [CONFIRMED_FACT]

개념적 상태 흐름(**[PROPOSED]**, 구현 승인 아님):
```
observation
→ hypothesis
→ system_recommendation
→ human_decision
→ change_proposal
→ execution_approval
→ execution_result
→ live_verification
→ paired_evaluation
→ post_evaluation_human_decision
→ optional rollback_approval
→ rollback_result
```

## 7. Rollback Taxonomy

**CONFIRMED_FACT(필요성) / NOT_IMPLEMENTED(계약)** — 반드시 분리:

1. **content/revision rollback** — 발행 글 되돌림.
2. **deploy rollback** — 빌드/배포 되돌림(git tag/backup).
3. **analytics-data rollback** — `rollback_analytics.py` 전용 계획(Phase0 Task7, MANUAL_MISSING).
4. **threshold-policy rollback** — 정책 버전 되돌림(미설계).

명시:
- `rollback_analytics.py`는 analytics data rollback 전용. Track B content rollback 구현으로 간주하지 않음.
- 각 rollback의 approver/executor/evidence contract는 미확정(UNRESOLVED).
- 자동 rollback 금지(PROHIBITED).

## 8. Blog Portfolio and Pilot Boundary

**CONFIRMED_FACT / RECOVERED_APPROVED_SUMMARY / UNRESOLVED**

archetype 요약(A1–A9, Publisher account는 family alias 사용 — 전체값 기록 금지):
- A1 CAP-rotcha (Hugo, ko, ACCOUNT_FAMILY_A)
- A2 CUAP-info (Hugo Blowfish, ko, ACCOUNT_FAMILY_B)
- A3 ETAP-techpawz (Hugo, **en**, ACCOUNT_FAMILY_UNKNOWN — 매핑 미확정)
- A4 RAP-info (Hugo, ko, ACCOUNT_FAMILY_B)
- A5 SEAP-info (Hugo, ko, ACCOUNT_FAMILY_B)
- A6 STAP-external (Hugo ext, ACCOUNT_FAMILY_UNKNOWN)
- A7 TAP-external (Blogger, ACCOUNT_FAMILY_UNKNOWN)
- A8 Paused-parent (Hugo, paused)
- A9 Paused-blogger (Blogger, paused)

- A1/A4가 pilot 후보로 **제안**되었으나 승인된 pilot은 아님(PROPOSAL, not approved).
- ETAP account mapping 미확정(UNRESOLVED).
- account/language/archetype별 population 분리는 검증할 후보(DIRECTION_CONFIRMED, 미강제).
- content-level revenue attribution은 여전히 금지(PROHIBITED).

## 9. Operating Model

**CONFIRMED_FACT / UNRESOLVED**

현재 확정:
- Policy Owner = CEO.
- System = recommendation/evidence only.

미확정(UNRESOLVED):
- Recommendation Reviewer
- Change Approver
- Execution Operator
- Rollback Approver
- Data Steward

결정과 실행을 분리한다. 대표의 문서화 승인을 구현 승인으로 해석하지 않는다.

## 10. Readiness and Roadmap

**DOCUMENTED_STATUS_ONLY** (세부 구현 task/시간 추정 작성하지 않음)

- 0. Product/authority baseline — 상태: 문서화 완료(본 문서)
- 1. Phase 0 revenue data recovery — 상태: PLANNED, 별도 실행 승인 필요
- 2. Identity and observation foundation — 상태: NOT_IMPLEMENTED
- 3. Human decision workflow — 상태: NOT_IMPLEMENTED
- 4. Recommendation-only shadow pilot — 상태: NOT_IMPLEMENTED
- 5. Threshold calibration/governance — 상태: DIRECTION_CONFIRMED(값/calibration 미승인)
- 6. Dashboard integration/controlled expansion — 상태: NOT_IMPLEMENTED

현재 readiness:
- Master Plan documentation: READY_WITH_CONDITIONS
- Phase 0 execution: READY_WITH_CONDITIONS(별도 실행 승인 필요)
- Track B implementation: NOT_READY
- Shadow pilot: NOT_READY
- Threshold calibration: NOT_READY

## 11. Open Decisions and Known Risks

- Track B §1–§4 원래 대화 전문 부재(authority limitation).
- 6축 confidence domain/계산식 미정(UNRESOLVED).
- GA4 grain 미검증(4월 정지, DOC-CLAIM).
- gsc_pages 비어 있음(0 rows).
- content_id/ledger/snapshot 미구현(NOT_IMPLEMENTED).
- human roles 미지정(HUMAN_ROLE_UNASSIGNED).
- rollback state machine 미정(UNRESOLVED).
- official Lookbook 없음(NOT_FOUND, 후보만 존재).
- Dashboard GET side effect(DB write on GET).
- pending-fixes 결정/실행 결합.
- calibration population EMPTY.

## 12. Acceptance and Approval Record

**정확히 기록**:

- 이번 대표 승인은 "문서화 및 handoff 생성" 승인이다.
- Track B 구현 승인 아님.
- §5 threshold 값 승인 아님.
- calibration 승인 아님.
- dashboard 변경 승인 아님.
- writing-plans 승인 아님.
- autonomous capability 승인 아님.
- execution_authorized = false, autonomous_decision_authorized = false, threshold_policy_status = NOT_EXISTS.

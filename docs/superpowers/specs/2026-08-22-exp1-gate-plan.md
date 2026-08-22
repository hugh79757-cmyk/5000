# Track A — Exp1 Gate Assessment & Blocker Resolution Plan

> **상태**: DESIGN_ONLY (2026-08-22). 코드/DB/파일 수정 금지. 실행 금지.
> **입력**: docs/superpowers/specs/2026-08-22-section7-final-amendment.md
>   (residual_risks + g5_stance) + Exp0 배치 결과(/tmp/exp0_dryrun_batch5.md, 5/5 PATCH_PROPOSED)
> **목적**: Exp1(실제 APPLIED 전이) 진입 전 해소할 HIGH 블로커 + 해소 순서 + Exp1 초회 범위.

---

## Step 1 — Blocker Inventory (HIGH / BY_DESIGN)

```yaml
blockers:
  - id: BLK-1
    name: MANUAL_MISSING_체커_10+
    severity: HIGH
    description: "SAFE fixer 매핑 없는 10+ 체커(MANUAL_MISSING)는 패치 제안 불가 → ABSTAIN 유발"
    current_state: 회피가능(Exp0 스코핑으로 입증)
    exp1_block_reason: "Exp1 대상에 MANUAL_MISSING 행이 섞이면 fixer 부재로 APPLIED 실패"
    resolution:
      - "Exp1 대상 체커를 SAFE fixer 4종(FM-DRAFT/FM-FEATUREIMAGE/FM-MISSINGKEYS/THUMBNAIL-01)으로 한정"
      - "(향후) MANUAL_MISSING 매핑 보강은 Exp2 별도"
    difficulty: LOW
    dependencies: []

  - id: BLK-2
    name: RULE_VERSION_부재
    severity: HIGH
    description: "rule_id→rule_version DB 연결 부재로 rule 버전 구분 불가"
    current_state: NOT_IMPLEMENTED (version:'absent' 명시로 운영 수용)
    exp1_block_reason: "이론적(버전 추적 불가)이나 실제 Exp1는 version 없이 동작 가능 → 소프트 블로커"
    resolution:
      - "Exp1도 version:'absent' 유지(§6 설계 수용)"
      - "(Exp2) rule_version 컬럼 추가는 별도 작업"
    difficulty: LOW
    dependencies: []

  - id: BLK-3
    name: UPSERT_HISTORY_손실
    severity: HIGH
    description: "check_results UPSERT latest-only로 before-state 덮임 → before/after 비교 불가"
    current_state: IMPLEMENTED (fix_history.py JSON sidecar, Phase 3)
    exp1_block_reason: "해소됨 — APPLIED 전후 이력 sidecar 기록"
    resolution:
      - "immutable before/after sidecar 스냅샷 (ops_dashboard/fix_history/{blog_id}/{slug}.json)"
      - "APPLIED/RECHECK_PASS/ROLLED_BACK 등 상태머신 전이 기록"
    difficulty: MED
    dependencies: [BLK-5]

  - id: BLK-4
    name: TARGETED_RECHECK_인터페이스_부재
    severity: HIGH
    description: "recheck(blog_id,check_name,scope) 타깃 재검사 API 미존재(전체만 scheduler._run_recheck_all)"
    current_state: IMPLEMENTED (recheck.py targeted_recheck, Phase 2)
    exp1_block_reason: "해소됨 — 단일 포스트 rule_id(FM-*) 재검사 가능"
    resolution:
      - "recheck.py: blog_id+post_path+check_name 타깃 → RecheckResult 반환 (SELECT only)"
    difficulty: MED
    dependencies: []

  - id: BLK-5
    name: ROLLBACK_CHAIN_미완성
    severity: HIGH
    description: "backup_blog()만 존재, restore()/redeploy()/live-verify 체인 미완성(§9)"
    current_state: PARTIAL (restore 구현, redeploy/live-verify 미구현)
    exp1_block_reason: "restore() 구현으로 원복 경로 확보; redeploy/live-verify는 Exp1 런타임 별도"
    resolution:
      - "rollback.py: create_rollback_point + execute_rollback (hash 대조)"
    difficulty: MED
    dependencies: []

  - id: BLK-6
    name: NONDESTRUCTIVE_VERIFY_부재
    severity: HIGH
    description: "패치가 non-destructive임을 자동 검증하는 경로 부재(§4 zero-mutation 설계만)"
    current_state: IMPLEMENTED (verify_before_apply.py dry_apply, Phase 3)
    exp1_block_reason: "해소됨 — 적용 전 메모리 시뮬레이션 부작용 게이트"
    resolution:
      - "verify_before_apply.py: dry_apply() — side_effects(unexpected_field_removed/file_size_delta/encoding_changed/excessive_changes) 검사"
    difficulty: MED
    dependencies: [BLK-5]

  - id: BLK-7
    name: G5_PRODUCTION_GATE
    severity: BY_DESIGN
    description: "G5 = PENDING/BLOCKED — rule_version 연동 production gate"
    current_state: ACCEPTED_ABSENT (§6/g5_stance: version 부재와 무관하게 설계 완결)
    exp1_block_reason: "소프트 게이트 — Exp0·Exp1 모두 version:'absent'로 운영 가능"
    resolution:
      - "게이트 수용 선언 유지, Exp1 진행 허용"
    difficulty: LOW
    dependencies: []
```

---

## Step 2 — Resolution Sequence (Phases)

```yaml
phases:
  phase_1_no_code_soft:
    blockers: [BLK-1, BLK-2, BLK-7]
    actions: "Exp1 대상 SAFE-fixer 한정 + version:absent 유지 + G5 수용 선언"
    gates: "Exp1 진입 허용 (소프트 블로커 해소)"
    parallel: true

  phase_2_code_med:            # 구현 완료
    blockers: [BLK-4, BLK-5]
    actions: "recheck.py 타깃 구현 + rollback.py restore 구현"
    depends_on: phase_1_no_code_soft
    parallel: true

  phase_3_code_med:            # 구현 완료
    blockers: [BLK-3, BLK-6]
    actions: "fix_history.py sidecar + verify_before_apply.py 사전검증 게이트"
    depends_on: phase_2_code_med
    parallel: true
```

> 의존 그래프 정합: Phase1(무의존) → Phase2(BLK-4∥BLK-5) → Phase3(BLK-3∥BLK-6). ✅

---

## Step 3 — Exp1 Scope Proposal (가정: Phase1~3 해소 후)

```yaml
exp1_scope:
  target_rows: 3
  target_checkers: [FM-DRAFT, FM-MISSINGKEYS, THUMBNAIL-01]
  selection: "Exp0 배치에서 PATCH_PROPOSED 도달한 행 재사용(209638/130489/208208 등)"
  rollback_strategy:
    unit: "포스트 파일 단위 복원 (rollback.py execute_rollback)"
    chain: "create_rollback_point()(사전) → APPLIED → verify_before_apply 통과 → RECHECK → VERIFIED"
  success_criteria:
    transition_rate: "APPLIED→RECHECK→VERIFIED 전이율 100% (3/3)"
    recheck_api: "recheck.py 호출 성공 + status=fail→pass 전환 확인"
    sidecar: "fix_history.py before/after 스냅샷 기록됨"
  failure_stop_condition:
    - "RECHECK 실패 1건이라도 → 즉시 전체 중단(halt)"
    - "restore() 실패 → BLOCKED_NO_ROLLBACK → 수동 개입"
    - "verify_before_apply 안전 실패 → 적용 중단"
```

---

## Step 4 — Draft (relocated from /tmp, committed 2026-08-22)

> Phase 2+3 코드(recheck.py/rollback.py/fix_history.py/verify_before_apply.py + tests) 구현 완료.
> 실제 Exp1 실행(APPLIED 전이)은 별도 human 승인 필요.

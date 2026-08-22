# Track A — Section 7 Final Amendment Design

> **상태**: CHAT_APPROVED (2026-08-22)
> **작성 근거**: docs/handoffs/2026-08-20-track-a-dashboard-ssot-remediation.md §7 Required Next Design
> **제약**: 본 문서는 설계 산출물. 코드/DB/autofix 변경 금지. Experiment 0 실행은 Exp1 진입 전제(G5 등 HIGH 블로커 해소) 후.
> **Track B 재개 조건**: §11(콘텐츠 품질 기준 + Lookbook 방향) 산출물이 트랙B Phase 0 입력.

```yaml
section_7_design:

  §1_ssot_completeness: >-
    대시보드가 SSOT로 기능하기 위한 20필드 완전성 계약. 분류:
    VERIFIED_EXISTING(11) — check_results(blog_id,check_name,verdict,ts),
    known_issues, readiness(3 green), rule_registry(18), error_registry,
    problem_registry(P01-P34), ERROR_PLAYBOOKS, 4 SAFE fixers, pending_fixes,
    logs dir, telegram, deploy flow.
    DERIVABLE(4) — assertion_result=checker재현 vs expected(MATCH/MISMATCH),
    source mapping(rule→registry→manual), eligibility(§5), sidecar(§7).
    MISSING_CONTRACT(3) — rule_version, remediation_manual_version,
    immutable before/after. NOT_IMPLEMENTED(2) — targeted recheck API(§8),
    rollback/restore chain(§9).
    SSOT_INCOMPLETE 행은 Experiment 0에서 ABSTAIN 허용(Residual Risk #1).

  §2_rule_manual_matrix: >-
    해상도 체인: checker_name → rule_id → registry(ops_dashboard/registry/rules.py:18 UnifiedEntry)
    → manual(ERROR_PLAYBOOKS.md) → actionable.
    현황(문서 근거): SAFE fixer 4개(fix_draft_true, fix_featureimage_url_sanitize,
    fix_frontmatter_missing_keys, fix_thumbnail_r2), 3 partial, 10+ MANUAL_MISSING.
    version 부재 처리: rule_id만 매핑, rule_version 필드는 "absent" 명시(§6).
    MANUAL_MISSING 체커는 §5 자동제외 대상(패치 제안 불가 → ABSTAIN).

  §3_remediation_state_machine: |
    [진행 15] DETECTED → DIAGNOSED → PATCH_PROPOSED → HUMAN_REVIEW
      → APPROVED → APPLIED → RECHECK_TARGETED → VERIFIED → CLOSED
      (분기) DIAGNOSED → ABSTAINED (SSOT_INCOMPLETE/소스미검증)
      (분기) PATCH_PROPOSED → NEEDS_MANUAL (MANUAL_MISSING)
    [블로커/실패 16] BLOCKED_NO_VERSION(G5) / BLOCKED_NO_SOURCE_MAP
      / BLOCKED_NO_FIXER / BLOCKED_NO_TARGETED_RECHECK / BLOCKED_NO_ROLLBACK
      / BLOCKED_NO_HISTORY / BLOCKED_NONDESTRUCTIVE_UNVERIFIED
      / APPLIED_FAIL / RECHECK_FAIL / VERIFY_FAIL / ROLLBACK_FAIL
      / HUMAN_REJECT / REOPENED / STALE_UPSERT / AUDIT_GAP / COMPOUND_ISSUE
    Experiment 0는 DIAGNOSED→PATCH_PROPOSED(제안만, 미승인)까지만,
    APPLIED 이후 상태는 Exp1 범위.

  §4_exp0_readonly: >-
    READ_ONLY_RESOLUTION 설계. 입력: 1개 실제 대시보드 행(check_results 1-row).
    수행: (1) row + 연결 소스(스키마/런북/registry)만 읽기 조회,
    (2) 근거 기반 진단(어떤 rule 위반, 소스 매핑 추적),
    (3) 패치 제안서(chat 출력: 변경 diff 가상 + 적용 절차 + 롤백 계획),
    (4) zero mutation — autofix 호출 금지, pending_fixes 미기록, DB 미접근,
    파일 미수정(Resume Prompt 준수). 산출물은 사람 승인용 제안문.

  §5_eligibility:
    eleven_criteria:
      - "check_results 행 존재 (blog_id, check_name, verdict)"
      - "checker가 등록된 CHECKS dict 항목 (21개 중 하나)"
      - "assertion_type이 VERDICT/WORKFLOW 중 하나(DESIGN 제외)"
      - "source mapping 검증됨(rule→registry→manual 추적 가능)"
      - "fixer 존재(SAFE 4개 또는 pending_fix 제안 가능)"
      - "rule_version 불필요(absent 허용, §6)"
      - "blog_id가 활성 fleet에 속함"
      - "단일 근인(single-root-cause, compound>2 제외)"
      - "가역적(읽기전용이므로 롤백 계획만 산출, 미실행)"
      - "UPSERT history 불필요(Exp0는 before/after 비교 안 함)"
      - "human-approval 경로 정의됨(decision_authority=HUMAN)"
    ten_auto_exclusions:
      - "check_name ∈ MANUAL_MISSING 집합(패치 불가)"
      - "verdict=NOT_APPLICABLE"
      - "compound issue > 2개"
      - "DB schema/migration 필요"
      - "deploy/redeploy 필요"
      - "외부 live-verify 의존"
      - "rule_version 종속(G5)"
      - "source mapping 미검증"
      - "rollback chain 필요(Exp0 readonly 위반)"
      - "known_issues 미해결 blocker 연결"

  §6_rule_version: >-
    rule_id→rule_version DB 연결 부재를 명시적 Residual Risk로 선언.
    Exp0는 version 필드 없이 동작: rule_id만 사용, version="absent" 기록.
    Exp1 전제(블로커)로 분리 — Section 7 설계 자체는 version 부재와 무관하게 완결.

  §7_history: >-
    check_results는 UPSERT latest-only(DELETE+INSERT per (blog_id,check_name))로
    before-state 손실. Exp0는 before/after 비교 안 하므로 영향 없음.
    Exp1용 보완: immutable before/after sidecar 스냅샷(Experiment 1 only, 미구현).
    현 status: NOT_IMPLEMENTED(§1 MISSING_CONTRACT).

  §8_targeted_recheck: >-
    인터페이스 시그니처(설계만, 미구현):
    recheck(blog_id: str, check_name: str | None,
            scope: "targeted"|"affected-set"|"full-regression") -> CheckResult
    현状: app.py에 /api/recheck 없음, scheduler._run_recheck_all()만 존재(전체).
    Exp0는 이 인터페이스 없이 기존 row만 읽기 조회. Exp1 범위.

  §9_rollback_chain: >-
    패치 실패 원복 경로(설계, 미구현):
    (1) backup_blog() 존재(git tag/file copy, core.py) — 선행 보존
    (2) restore() — 부재 → 설계 필요(Exp1)
    (3) redeploy() — dispatcher.py 경유
    (4) live-verify — curl 기반(예: michelin 6항목)
    9요건 중 현재 구현된 것은 (1)뿐. (2)(3)(4) 체인 미완성 → Exp1 블로커.

  §10_source_mapping: >-
    완전성 검증 방법: 각 checker가 참조하는 소스(스키마 YAML, ERROR_PLAYBOOKS,
    rule_registry, problem_registry)를 자동 추적하여 매핑 표 생성.
    미검증 항목은 §5 자동제외(SSOT_INCOMPLETE → ABSTAIN).
    검증 산출물: checker→rule_id→manual 3단 매핑 표(§2 입력).

  §11_quality_criteria_lookbook:
    note_e1e5: >-
      문서상 E1~E5는 Viator 제휴 고지 검증(E1 commission 지급~E5 일반계약 원문)임.
      콘텐츠 품질 척도가 아님. §11은 michelin 파일럿 구조 + ETAP quality-overhaul
      S2 라이브검증 기준(문서 명시 수치)을 레퍼런스로 사용.
    quantitative_criteria:
      - metric: wordCount
        threshold: "하한 400 (quality_guard is_draft 게이트); michelin 목표밴드 900~1400"
        source: "etap-quality-overhaul S0/S2-3; Track C session-state(KDL 357 미달→noindex)"
      - metric: H2_count
        threshold: ">=3 (quality_guard H2<3 → is_draft)"
        source: "etap-quality-overhaul S0-1"
      - metric: structure_blocks
        threshold: "요약테이블(Answer) 존재 + 비교테이블 행>=5 + FAQ 3문항(+FAQPage JSON-LD) + H2 4개 고정(At a Glance/Where to Eat/Compare/FAQ)"
        source: "etap-quality-overhaul S2-1/S2-3"
      - metric: item_detail_length
        threshold: "항목별 H3 120~180단어"
        source: "etap-quality-overhaul S2-1"
      - metric: cta_count_position
        threshold: "2개(상단1+비교후1), 첫 CTA 요약테이블 직후, CTA간 >=600px(또는 400단어), 광고 교차금지"
        source: "etap-quality-overhaul S2-2(d)"
      - metric: ad_slots
        threshold: "ad-top 제거, ad 2슬롯(H2 2번째 직후+비교 후), 본문대비 <=30%, 상단300px 금지"
        source: "etap-quality-overhaul S2-2(e); michelin-deep-pass T4"
      - metric: internal_link_density
        threshold: "동도메인 우선, 외부교차<=1, 500단어당<=3"
        source: "etap-quality-overhaul S2-2(f)"
      - metric: trust_signals
        threshold: "author.name non-empty + 출처/갱신일 명시 + dateModified=lastmod"
        source: "etap-quality-overhaul S2-2(g); michelin-deep-pass 5항목"
      - metric: affiliate_disclosure
        threshold: "제휴링크 있으면 disclosure 1회(첫 제휴링크 위) + rel='sponsored noopener'"
        source: "michelin-deep-pass T6/T7; etap-quality-overhaul S1-4"
      - metric: adsense_render
        threshold: "adsbygoogle.js 1회, G-DEFAULT 0, 단일 G-XXXX"
        source: "michelin-deep-pass 2항목/6항목"
      - metric: stage1_pass
        threshold: "c08 required_frontmatter empty 0 + title_format + og_image_required 충족"
        source: "schema-as-code-design(Stage1 게이트)"
      - metric: zero_hallucination
        threshold: "빈 데이터 사실단정 0건 (S0 CRITICAL gate)"
        source: "etap-quality-overhaul S0-1/S0-2"
      - metric: no_duplicate_prose
        threshold: "동일 문단 반복 0 + 페이지전용 사실 밀도(문단당 >=1 전용)"
        source: "michelin-deep-pass 1~2단계(B1/B3)"
    lookbook_reference: >-
      michelin 파일럿 구조: 요약테이블(Answer) → 상세(H3 항목별 120~180단어,
      award/시그니처메뉴) → 비교테이블(행>=5) → FAQ(3문항+FAQPage).
      라이브 검증 6항목(G-DEFAULT 0 / adsbygoogle 1 / rel sponsored /
      disclosure 조건부 / author.name 채움 / ad-top 0)을 '좋은 콘텐츠'의
      렌더·신뢰 최소 기준으로 채택.
    b_handoff: >-
      B 재개 조건(콘텐츠 품질 기준/Lookbook 방향) 충족 산출:
      (1) 위 13지표를 pre-change 스냅샷으로 수집 → baseline 정의.
      (2) 개선 판정 임계값: wordCount 400→900 상향 비율, Stage1 PASS율,
          0허위 유지, 구조블록 4종 충족율, CTA/광고 규칙 준수율.
      (3) B는 이 baseline을 받아 '변경 전후 효과 측정' 설계의 입력으로 사용.
      (단, B 재개는 human roles 지정 + 별도 구현승인 필요 — track-b handoff §7)

residual_risks:
  - risk: "SSOT_INCOMPLETE 다수 행(source/action 무응답)"
    severity: MED
    addressed_in: "§1(VERIFIED/DERIVABLE/MISSING 분류), §4(ABSTAIN 허용)"
  - risk: "10+ MANUAL_MISSING 체커 → agent ABSTAIN"
    severity: HIGH
    addressed_in: "§2(해상도 체인), §5(자동제외 #1)"
  - risk: "rule_version 부재 → rule 버전 구분 불가"
    severity: HIGH
    addressed_in: "§6(version:absent 명시), G5_stance"
  - risk: "UPSERT history 손실(before state 덮임)"
    severity: HIGH
    addressed_in: "§7(sidecar Exp1 only)"
  - risk: "targeted recheck 인터페이스 부재"
    severity: HIGH
    addressed_in: "§8(설계 시그니처, Exp1)"
  - risk: "rollback/restore/redeploy/live-verify chain 미완성"
    severity: HIGH
    addressed_in: "§9(backup만 존재, 나머지 Exp1)"
  - risk: "logs 구조적 audit ledger 부재"
    severity: MED
    addressed_in: "§3(BLOCKED_AUDIT_GAP 상태), Exp1"
  - risk: "non-destructive patch verification 부재"
    severity: HIGH
    addressed_in: "§4(zero mutation 설계), §9(live-verify)"
  - risk: "source mapping 완전성 미검증 → ABSTAIN 유발"
    severity: MED
    addressed_in: "§10(추적 표), §5(자동제외 #8)"
  - risk: "G5 = PENDING/BLOCKED (production gate)"
    severity: BY_DESIGN
    addressed_in: "g5_stance (Exp1 전제)"

g5_stance: >-
  Section 7 설계에서는 rule_id→rule_version 연결 부재를 "version: absent"로 명시적 수용하며,
  Experiment 0는 version 없이 동작하도록 설계하고, G5는 Experiment 1 진입 전제(블로커)로 분리한다.
```

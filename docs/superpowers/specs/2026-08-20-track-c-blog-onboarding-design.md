# Track C — Cross-Branch Investigation & Synthesis (Design)

- **Status:** DESIGN_DRAFT (brainstorm confirmed 2026-08-20)
- **Implementation authorized:** false
- **Classification:** Documentation-based governance extension (no new subsystem code)
- **Depends on:** (none yet) — independent branch-investigation track; synthesizes findings across all branches
- **Correction:** prior "Blog / Vertical Onboarding Editorial Gate" framing was a misrecord and is removed (see §1)

---

## 1. Scope (corrected — 2026-08-20)

> **정정(governing correction):** 이 문서 초기 버전은 Track C를
> "신규 블로그 / vertical 온보딩 거버넌스(editorial onboarding gate)"로
> 기록했으나 **이는 잘못 기록된 것**이다. Track C는 온보딩 게이트가 아니다.

**Track C = 분기(branch) 조사의 종합 작업이다.**

- Track C는 각 파이프라인 분기(ETAP, car, rap, senior, curation, travel/TAP,
  stock/STAP, mde2, blogger)를 개별적으로 조사하고, 그 결과를 종합하여
  포트폴리오 전반의 거버넌스 결론을 도출한다.
- **현재 진행 중인 분기 조사 = ETAP (branch 1).** ETAP 분기 조사를 모두
  마친 후, 다른 분기들을 동일하게 조사하고, 모두 종합하여 Track C를 완성한다.
- ETAP 분기에서 산출된 design / discovery / verification 스펙 문서들은
  **전부 Track C에 속한다** (아래 §1b).

따라서 이 문서는 "온보딩 게이트 설계"가 아니라, **분기 조사 종합 컨테이너**로
재활용된다. §2~§10은 이전 온보딩 초안(잘못 기록된 범위) 그대로 남겨둔
**LEGACY 섹션**이며, 분기 조사 종합에 맞게 별도로 갱신된다.

### 1a. Confirmed boundaries (branch investigation)

| In scope | Out of scope |
|---|---|
| 각 분기 파이프라인 코드/DB/배포/제휴 흐름 정적 조사 | 코드/DB 수정·배포 |
| 분기별 affiliate / disclosure / entity-link / thumbnail 흐름 비교 | 신규 블로그 온보딩 승인 |
| 분기 조사 결과의 종합·거버넌스 결론 도출 | Track A/B 트랙 실행 |
| ETAP 분기 스펙(Design/Discovery/Verification) 작성·소속화 | |

### 1b. Track C 소속 ETAP 분기 스펙 (branch 1)

- `2026-08-20-etap-auto-branches-discovery.md` (DISCOVERY)
- `2026-08-20-etap-adventure-content-design.md` (DESIGN_DRAFT)
- `2026-08-20-etap-adventure-affiliate-disclosure-discovery.md` (DISCOVERY_DRAFT)
- `2026-08-20-etap-adventure-affiliate-disclosure-design.md` (DESIGN_DRAFT)
- `2026-08-20-etap-adventure-affiliate-relationship-verification.md` (VERIFICATION_ONLY)

---

## 2. Candidate types (all three reviewed)

1. **New domain / subdomain** — e.g. a new `*.rotcha.kr` or `*.informationhot.kr`.
2. **New content vertical within an existing blog** — a new topic/archetype branch
   inside a currently publishing blog.
3. **New derived operating unit from an existing pipeline** — e.g. splitting one
   pipeline's output into a separate managed unit.

Each is a **separate approval unit** — a vertical inside blog X is judged
independently of a new domain Y.

---

## 3. Review axes (4 mandatory)

Every candidate is reviewed on:

1. **Topic / search-intent validity** — is there a real, durable search need;
   is the intent clearly defined and not a vanity keyword.
2. **Portfolio overlap** — does it duplicate an existing blog/vertical's topic or
   search intent. (Appendix D only catches `blog_id`/`domain` collisions; it does
   **not** catch topic-intent overlap. This is the real gap Track C closes.)
3. **Track A quality-standard & source readiness** — is there an applicable
   archetype quality standard and authoritative source plan. If no Track A
   standard exists for the archetype → `BLOCKED_MISSING_QUALITY_STANDARD`.
4. **Operating / remediation ownership clarity** — who owns content, review, and
   maintenance; who is accountable if quality drops.

---

## 4. Mandatory proposal metadata (13 fields)

Track C introduction onward, every new proposal MUST carry at minimum **13
fields** (document/checklist-based — no new DB schema):

```
candidate_type:                 # new_domain | new_vertical | new_derived_unit
topic:
archetype:
target_audience:
primary_search_intent:
portfolio_overlap_candidates:   # explicit list of possibly-overlapping existing blogs/verticals
differentiation:
authoritative_sources:
quality_standard_reference:     # which Track A standard applies, or "NONE"
policy_risk:                    # factual / legal / advertising risk level
content_owner:
review_owner:
maintenance_owner:
```

These live in the **Track C proposal document / checklist**, not in a new DB.
No new persistence system is created in this design.

---

## 5. Judgment vocabulary (document-level, not a state machine)

Initial Track C uses only these editorial verdicts:

- `APPROVE_FOR_APPENDIX_D_REVIEW` — passes editorial gate; may proceed to
  Appendix D mechanical onboarding (which still needs its own separate human
  execution approval).
- `REVISION_REQUIRED` — gaps identified; resubmit after fix.
- `REJECT` — not suitable for the portfolio.
- `ABSTAIN` — insufficient evidence to judge; state exactly what evidence is
  missing.
- `BLOCKED_MISSING_QUALITY_STANDARD` — archetype has no Track A quality standard
  yet; do **not** auto-reject, hold until Track A defines the standard.

Note: `APPROVE_FOR_APPENDIX_D_REVIEW` is **not** approval to run Appendix D.
Appendix D entry requires its own separate human execution approval.

---

## 6. Relationship to Appendix D

```
Track C editorial proposal
  → manual / semi-auto overlap review (read-only survey of repo + public content)
  → human editorial verdict
  → (if APPROVE_FOR_APPENDIX_D_REVIEW) separate human approval to run Appendix D
  → Appendix D mechanical onboarding
  → existing register / verify / operate procedure
```

Track C does **not**:
- modify or replace Appendix D,
- execute YAML registration, DB sync, or dispatcher mapping,
- treat a Track C verdict as Appendix D execution approval.

---

## 7. Existing 81-blog handling

Full backfill of `topic`/`archetype` across the 81 existing blogs is **deferred**:

- `C-META-1: Existing Portfolio Metadata Normalization`
  - STATUS: DEFERRED
  - IMPLEMENTATION_APPROVED: false
  - DEPENDENCY: Track A archetype taxonomy
  - Reason: rework risk before Track A archetype is fixed; 81-blog normalization is
    a much larger data task than a lightweight gate; Track C's purpose is preventing
    *new* debt, not retrofitting the whole portfolio; Track A should first restore
    quality standards for the live portfolio.

Track C may still perform **read-only manual overlap surveys** of the existing
repo/public content when judging a new candidate.

---

## 8. Track A / B dependency (honest constraint)

Track A and Track B are both `PAUSED_HANDOFF` (no code, G5 BLOCKED, calibration
empty). Therefore:

- Track C cannot reference a finished Track A quality standard for most archetypes
  yet → those candidates route to `BLOCKED_MISSING_QUALITY_STANDARD`.
- Track C does **not** invent Track A standards.
- Track C does not depend on Track B's autonomous capability (explicitly out of
  scope).
- A new candidate that cannot be explicitly mapped to a Track A-approved quality
  standard is held as `BLOCKED_MISSING_QUALITY_STANDARD` — this is **not** an
  auto-reject.
- General evidence insufficiency (e.g. unknown overlap, unclear intent) is
  `ABSTAIN`, with the missing evidence stated — distinct from a missing quality
  standard.
- The actual count of reviewable candidates cannot be fixed until each candidate's
  archetype is explicitly mapped to a quality standard. Track C operates on that
  mapping basis, not on a fixed blog-count ceiling.

---

## 8b. Observed repository snapshot (evidence class)

The following numbers are an **OBSERVED_REPOSITORY_SNAPSHOT**, not permanent
design constants or policy thresholds. Observed at **2026-08-20**.

| Metric | Value | Evidence |
|---|---|---|
| Total blogs | 81 | `config/blogs.d/*.yaml` (8 brand YAMLs) |
| Active / paused | 76 / 4 | `status:` field count across brand YAMLs |
| Blogs with `topic` field | 23 / 81 | field-frequency survey of `config/blogs.d/*.yaml` |
| `archetype` field | absent | not present in any `config/blogs.d/*.yaml` entry |
| Quality-standard coverage | limited | `config/quality_checklist.yaml` (v44.1) covers a 6-blog subset; `data/writing_samples/` has 3 files (camping/festival/heritage) |

Interpretation rules:
- The coverage figure is a snapshot of current repo state, **not** a cap on how
  many candidates Track C can later review.
- Track C does **not** use the "6" value as a policy threshold or permanent
  limit. Quality-standard absence routes a candidate to
  `BLOCKED_MISSING_QUALITY_STANDARD`; it never auto-rejects.
- If an evidence path above is later found stale, do not re-invent or
  re-interpret the number — mark it `DOC-CLAIM` and re-survey.

---

## 9. Deliverable of this design phase

A single design document (this file). No implementation plan, no code, no
metadata backfill plan is written at this stage. The next step, if authorized,
is a writing-plans implementation plan — but only after Track A provides the
archetype taxonomy and quality-standard set that Track C gates on.

---

## 10. Non-goals (explicit)

- Auto domain generation
- Auto blog deploy
- Auto bulk content publish
- AdSense auto-link
- Revenue-based auto-promotion
- Content-level revenue attribution
- AI final quality approval
- Auto rollback
- Reuse of dashboard `approve` endpoint
- Track B autonomous capability

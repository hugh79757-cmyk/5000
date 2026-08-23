# ETAP — adventure Affiliate Disclosure Design

**Part of:** Track C (branch investigation — ETAP = branch 1 of N)

**Status:** DESIGN_DRAFT — NOT APPROVED
**Date:** 2026-08-20
**Scope:** `adventure-hugo` (adventure.techpawz.com) — single branch only
**Companion docs:**
- `2026-08-20-etap-adventure-content-design.md` (content design, §4 U1/U2)
- `2026-08-20-etap-adventure-affiliate-disclosure-discovery.md` (evidence, E1–E12)
**Method:** Design-only. No code change, no writing-plans, no implementation, no commit. Jurisdiction / Viator contract / tracking param remain **UNRESOLVED** (per Discovery). No "legal compliance guaranteed" phrasing.

---

## 1. Design principles (constrained)

| # | 원칙 | 근거 |
|---|---|---|
| P1 | affiliate 링크가 있는 글의 **첫 CTA·추천 근처**에 고지 | FTC: *"the closer the disclosure is to your recommendation, the better"* (Discovery E6) |
| P2 | 기존 가격·일정 면책문(`etap-disclaimer-card`)과 **분리** | Discovery E9: 정보 면책 ≠ affiliate 고지. 두 블록은 목적·내용 다름 |
| P3 | 본문과 **같은 영어**로, **명확하고 눈에 띄게** | FTC: clearly and conspicuously; body is English |
| P4 | FTC 공식 예문을 **원문 후보**로 제시 | Discovery §3: *"I get commissions for purchases made through links in this post."* |
| P5 | 변형 문구는 **`POLICY_DECISION_REQUIRED`** 표시 | 정확 문구·관할은 인력/법무 결정 대상 (Discovery E10/E11) |
| P6 | affiliate 링크가 **없는 글에는 고지 넣지 않음** | 고지 없는 링크가 없으면 고지 불필요 (게이팅) |
| P7 | 관할·Viator 계약·tracking parameter = **UNRESOLVED 유지** | Discovery E3/E4/E5/E7/E10/E12 |
| P8 | "법률 준수 보장" 표현 금지 | 설계는 FTC 정렬(intent)일 뿐 보장 아님 |

---

## 2. 현재 렌더링 구조 (삽입 지점 후보 파악)

adventure 파이프라인이 본문에 주입하는 블록 (b8/m0085, 코드 근거):

| 블록 | 삽입 위치 | 소스 |
|---|---|---|
| 자연어 CTA (ONE) | 본문 끝 근처 (프롬프트 강제) | adventure_writer.py:99-138 |
| **제휴 카드 "Top Tours & Activities"** (Book Now = Viator 링크) | 마지막 H2(Travel Tips/Budget/Getting Around) **앞**, 또는 본문 끝 | post_processor.insert_product_cards (9-82), 호출 adventure_pipeline.py:135 |
| 비교표 | "Top Things to Do"/"Top Tours" H2 뒤 또는 2번째 H2 뒤 | post_processor.insert_comparison_table (85-148) |
| 크로스셀 카드 | 본문 하단 | post_processor.insert_cross_sell_block (151-182) + hugo_writer cross_sell_config |
| **정보 면책문 `etap-disclaimer-card`** | 본문 내 (강제) | quality_guard.py:474-484 |

→ **실제 affiliate 링크(Viator Book Now)는 "Top Tours & Activities" 카드 블록에 처음 등장**한다. 따라서 고지의 이상적 위치는 이 카드 블록 바로 앞.

---

## 3. 삽입 위치 선택안 비교

| 안 | 위치 | FTC 근접성(P1) | 가시성(P3) | 분리(P2) | 평가 |
|---|---|---|---|---|---|
| **A (권장)** | "Top Tours & Activities" 카드 블록 **직전** 에 고지 블록 삽입 | 최우수 — 추천(링크) 바로 앞 | 우수 — 본문 흐름 내 명확 노출 | 우수 — 정보 면책과 별도 블록 | **권장** |
| B | 본문 최상단 (도입 H2 직후) | 보통 — 링크보다 위, 하지만 "근처" 기준 충족 | 최우수 — 놓치기 어려움 | 우수 | 수용 가능 대안 |
| C | 본문 끝 (자연어 CTA 이후) | 미흡 — FTC가 끝-only 비권장 | 보통 | 우수 | 비권장 (FTC 가이드 위배 소지) |
| D | 정보 면책문(`etap-disclaimer-card`)에 병합 | 우수 | 보통 | **위반(P2)** — 두 목적 혼재 금지 | 기각 |

---

## 4. 권장안 (A) 상세

- **트리거:** `insert_product_cards`가 Viator 카드를 실제로 삽입할 때만 고지 블록 생성. 카드가 없으면(빈 tours) 고지 없음 → P6 충족.
- **위치:** product-card 블록 직전. 즉 기존 `post_processor.insert_product_cards` 호출 전에 고지 블록을 선행 삽입 (현재 adventure_pipeline.py:135 호출부 기준).
- **분리:** `etap-disclaimer-card`(정보 면책)는 기존 위치 유지. affiliate 고지는 별도 블록. 두 블록은 동일 페이지에 공존하되 내용·라벨로 구분.
- **언어/가시성:** 영어, 본문과 동일 톤. 시각적으로 구분되는 블록(예: 별도 단락/라벨)로 "hard to miss" 기준 지향. 정확 마크업은 구현 단계 결정(본 설계 범위 아님).

---

## 5. 고지 문구 후보 (원문 + 변형)

### 5.1 FTC 공식 예문 — 원문 후보
> *"I get commissions for purchases made through links in this post."*
> — FTC Endorsement Guides "What People Are Asking" (Discovery E6 인용)

이 문구를 **기본 원문 후보**로 제시. 단, 이 문구가 techpawz.com(영문 여행, 관할 미확정)에 그대로 적합한지는 **POLICY_DECISION_REQUIRED**.

### 5.2 변형 후보 (POLICY_DECISION_REQUIRED)
아래는 대안 문구이며, 정확 선택·관할 적합성은 인력/법무 결정이 필요:

- `POLICY_DECISION_REQUIRED` — *"This post contains affiliate links. I may earn a commission from bookings made through them, at no extra cost to you."*
- `POLICY_DECISION`(표기: POLICY_DECISION_REQUIRED) — *"As a Viator affiliate, I earn a commission from qualifying tours booked via links on this page."*
- `POLICY_DECISION_REQUIRED` — *"Some links on this page are affiliate links; I may receive a commission if you book through them."*

> 어떤 문구를 확정하든 **"법률 준수를 보장한다"는 표현을 수반하지 않음**(P8). 설계는 FTC 정렬(intent)을 목표로 할 뿐.

---

## 6. 게이팅 규칙 (P6)

| 조건 | 동작 |
|---|---|
| 글에 Viator 제휴 카드( Book Now 링크) 존재 | affiliate 고지 블록 삽입 (A안 위치) |
| 제휴 카드 없음 (tours empty 등) | 고지 블록 **미삽입** |
| 정보 면책문 | 항상 기존대로 별도 블록 유지 (affiliate 고지와 무관하게) |

---

## 7. UNRESOLVED 유지 항목 (본 설계에서 해결 안 함)

| 항목 | 상태 | 비고 |
|---|---|---|
| 적용 관할 (FTC 단독 / 영국·EU 병행) | UNRESOLVED | Discovery E10/E11 — 인력 입력 필요 |
| Viator 일반 affiliate 계약 원문·의무 | UNRESOLVED / NOT_OBTAINED | Discovery E3/E4/E5 |
| tracking parameter(pid/mcid) 의무 여부 | UNRESOLVED | Discovery E3/E12 — POLICY_NOT_VERIFIED |
| 확정 고지 문구 | POLICY_DECISION_REQUIRED | §5.2 |

---

## 8. 잔존 위험 (설계만으로는)

- 권장안 A는 FTC "근접·명확" 원칙(P1/P3)에 정렬되나, **관할 미확정(E10)** 이므로 "어느 관할 법령 완전 충족"은 보장 불가 — P8 accordingly.
- 문구 확정 전까지는 실제 삽입 문구를 확정할 수 없음 (§5.2 POLICY_DECISION_REQUIRED).
- 본 문서는 **설계만** 한다. 코드 수정·writing-plans·구현·commit은 범위 외.

---

## 9. 다음 단계 (미수행)

1. **관할 확정** (인력) → §7 UNRESOLVED 해제.
2. **고지 문구 확정** (인력/법무) → §5.2 POLICY_DECISION_REQUIRED 해제.
3. **구현** — A안을 `post_processor`/`adventure_pipeline.py`에 반영. 본 설계 범위 아님.

**승인 요청:** 본 Design은 설계·비교·권장만 수행했다. 코드 변경·writing-plans·구현·새 문서 커밋은 하지 않았다. 승인 후 다음 단계(관할 확정 / 문구 확정 / 구현)를 진행할 수 있다.

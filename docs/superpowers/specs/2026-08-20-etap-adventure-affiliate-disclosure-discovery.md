# ETAP — adventure Affiliate Disclosure Discovery

**Status:** DISCOVERY_DRAFT — NOT APPROVED
**Date:** 2026-08-20 (revised)
**Scope:** `adventure-hugo` (adventure.techpawz.com) affiliate-disclosure obligation
**Companion docs:**
- `2026-08-20-etap-auto-branches-discovery.md` (branch map)
- `2026-08-20-etap-adventure-content-design.md` (content design, §4 U1/U2 unresolved)
**Method:** Official-source research (FTC.gov + partnerresources.viator.com) + prior live render observation (kusadasi-adventure, m0085). **No disclosure text designed, no code changed, no writing-plan, no commit.**

Official sources added this revision:
- https://partnerresources.viator.com/travel-content/
- https://partnerresources.viator.com/blog/affiliatelinks101/
- https://partnerresources.viator.com/terms-and-conditions/
- https://www.ftc.gov/business-guidance/resources/ftcs-endorsement-guides-what-people-are-asking

---

## 1. Viator affiliate 프로그램 판정 분리

이전 "Viator 약관 전체가 403으로 미확보" 표현은 아래 구분으로 정정한다. `partnerresources.viator.com` 하위 페이지는 **접근 가능**하며, 미확보인 것은 일반 affiliate 계약 원문뿐이다.

| # | 항목 | 판정 | 근거 (공식 출처) |
|---|---|---|---|
| 1 | Viator affiliate 프로그램이 commission을 지급함 | **CONFIRMED** | travel-content: *"They make any booking within 30 days … You earn 8% commission on each product they book."* affiliatelinks101(2024-09-05): *"As a Viator affiliate, you can earn commission by promoting travel experiences to your audience through your unique affiliate links."* |
| 2 | Viator 공식 예시가 `pid`/`mcid`/`medium`/`campaign` 파라미터를 사용함 | **CONFIRMED** | travel-content "Live example" 링크: `…d5408-11402P4?pid=P00037046&mcid=42383&medium=link&campaign=live-example` (다수). Sign-up 링크: `?mcid=65935`. |
| 3 | 이 파라미터가 Adventure 발행에 **의무**인지 | **UNRESOLVED** | Viator 공식 자료는 이 파라미터를 *예시/어트리뷰션* 용도로 사용할 뿐, "affiliate는 반드시 이 파라미터를 붙여야 한다"는 명시적 의무 조항을 찾지 못함. 추적/어트리뷰션 권고 vs 법적 의무 구분 불가. |
| 4 | Contributor 약관이 일반 affiliate 운영에 적용되는지 | **UNRESOLVED** | terms-and-conditions 페이지는 **"Viator Affiliate Sponsored Experiences"** — 2024-10-07~11-15 한정 프로모션의 Contributor Agreement. 일반 VPP 운영 계약과는 별도 문서. |
| 5 | 일반 affiliate 계약 원문 | **NOT_OBTAINED** | 일반 Viator Partner Program(VPP) 운영 약관 본문은 이번 조사에서 확보 못 함. 확보한 것은 Contributor/Sponsored Experiences 약관뿐. |
| 6 | FTC material connection·명확하고 근접한 고지 원칙 | **CONFIRMED** | FTC "What People Are Asking" (아래 §3). |
| 7 | techpawz.com의 확정 적용 관할 | **UNRESOLVED** | 운영자 법인 소재/주 관할 불명 (아래 §2). |

> 정정: "Viator 약관 전체 403 미확보"는 오표현. 실제로는 `partnerresources.viator.com` 3페이지 접근 가능(CONFIRMED 1·2), 미확보는 **일반 affiliate 계약 원문(NOT_OBTAINED, #5)** 및 그 적용범위(#3·#4)뿐.

---

## 2. 적용 가능한 관할과 불명확한 부분

| 항목 | 판정 | 근거 |
|---|---|---|
| 미국 FTC 관할 리치(reach) 원칙 | CONFIRMED | FTC "What People Are Asking": *"If it's reasonably foreseeable that your … videos will be seen by and impact U.S. consumers, U.S. law would apply and you would need a disclosure. Also, the U.K. and many other countries have similar laws …"* |
| techpawz.com 운영자 실체/주 사업장 관할 | UNRESOLVED (#7) | 운영자 법인 소재·주 관할 불명. FTC 리치 기준만 확인됨. |
| 영국 CMA/ASA, EU UCPD 병행 적용 여부 | UNRESOLVED | FTC가 "유사 법률 존재"만 언급. 각 관할 구체 요건은 미조사. |

---

## 3. 고지 위치·가시성·표현에 대한 공식 요구 (FTC)

| 요구 | 판정 | 공식 인용 (FTC) |
|---|---|---|
| 제휴/커미션 = "material connection" → 고지 의무 | CONFIRMED | *"if there's a connection between an endorser and the marketer that a significant minority of consumers wouldn't expect and it would affect how they evaluate the endorsement, that connection should be disclosed clearly and conspicuously."* |
| 제휴마케터 고지 예시 | CONFIRMED | *"I'm an affiliate marketer with links … I earn a commission … 'I get commissions for purchases made through links in this post.'"* |
| 위치: 추천 근처 | CONFIRMED | *"the closer the disclosure is to your recommendation, the better."* |
| 가시성: 숨김 금지 | CONFIRMED | *"Disclosures are likely to be missed if they appear only on an ABOUT ME or profile page, at the end of posts or videos, or anywhere that requires a person to click MORE."* |
| 표현: 명확성 | CONFIRMED | *"Consumers might not understand that 'affiliate link' means … getting paid … a 'buy now' button would not be adequate."* / *"'Paid link' right next to an affiliate link should be an adequate disclosure"* |
| 책임 주체 | CONFIRMED | *"As an influencer, it's your responsibility to make these disclosures … Don't rely on others to do it for you."* — 사이트 발행자(운영자) 책임. |

> Viator 자체 가이드(affiliatelinks101)도 "prominently displayed", "avoid hiding them in the middle of a long text block or in hard-to-find locations"를 권고하나, 이는 **배치/가시성** 지침이지 법적 고지 문구 의무는 아님. FTC 원칙이 법적 고지 기준의 유일한 CONFIRMED 출처.

---

## 4. 현재 Adventure 렌더링의 CTA · affiliate link · 면책문 위치

근거: live observation of `kusadasi-adventure` (b8/m0085).

| 요소 | 현재 상태 | 위치 | 추적파라미터 상태 |
|---|---|---|---|
| CTA (자연어) | 프롬프트 강제 ONE natural CTA (adventure_writer.py:99-138) | 본문 끝 근처 | — |
| CTA (제휴 카드) | `insert_product_cards` "Book Now" ×2 관측 | 본문 하단 (마지막 H2 앞/끝) | — |
| affiliate link | `viator.com` ×6, **추적파라미터 없음** (`?pid/?mcid/?campaign` 0건) | 제휴 카드 내 `[Book Now](deep_link)` | **POLICY_NOT_VERIFIED** — 공식 예시(#2)는 파라미터 사용하나 의무 여부(#3) 미확정이므로 "누락=위반"으로 판정하지 않음 |
| 면책문 (정보) | `etap-disclaimer-card` **존재** | 본문 내 (quality_guard.py:474-484 강제삽입) | — |
| affiliate 고지 (커미션) | **0건** — "commission/affiliate/earn" 텍스트 없음 | 없음 | — |
| AdSense | `ca-pub-8772455780561463` (rotcha/techpawz 계열 정상) | 레이아웃 파셜 | — |

---

## 5. 기존 면책문이 affiliate 고지를 대신할 수 있는지

| 판정 | 근거 |
|---|---|
| **CONFIRMED — 대신할 수 없음 (NO)** | `etap-disclaimer-card`(quality_guard.py:474-484) 문구: *"Prices, schedules … based on data at the time of writing … verify current details on the official website before booking."* — 가격/일정 정확성 정보 면책일 뿐, 금융 관계(커미션/제휴)를 언급하지 않음. FTC가 요구하는 "material connection(재정적 관계)" 고지는 재정 관계의 명시적 공개이므로, 정보 면책문과 목적·내용이 다름. |

---

## 6. 종합 증거표 (CONFIRMED / UNRESOLVED / NOT_OBTAINED / POLICY_NOT_VERIFIED)

| # | 주장/항목 | 판정 | 근거 출처 |
|---|---|---|---|
| E1 | Viator affiliate가 commission 지급 | CONFIRMED | travel-content (8%), affiliatelinks101 |
| E2 | Viator 공식 예시 링크가 pid/mcid/medium/campaign 사용 | CONFIRMED | travel-content live example |
| E3 | 위 파라미터가 Adventure 발행 의무 | UNRESOLVED | 명시적 의무 조항 미발견 (#3) |
| E4 | Contributor 약관이 일반 affiliate 운영 적용 | UNRESOLVED | Sponsored Experiences 한정 프로모 (#4) |
| E5 | 일반 affiliate 계약 원문 | NOT_OBTAINED | 일반 VPP 약관 미확보 (#5) |
| E6 | FTC material connection·근접 명확 고지 원칙 | CONFIRMED | FTC "What People Are Asking" |
| E7 | 미국 소비자 영향 예견 시 미국법 적용 | CONFIRMED | FTC reach 원칙 |
| E8 | Adventure 현재 affiliate 고지 텍스트 부재 | CONFIRMED | live kusadasi-adventure (b8/m0085) |
| E9 | 기존 정보 면책문 ≠ affiliate 고지 | CONFIRMED | quality_guard.py:474-484 분석 |
| E10 | techpawz.com 확정 적용 관할 | UNRESOLVED | 운영자 관할 불명 (#7) |
| E11 | 영국 CMA/ASA·EU UCPD 구체 고지 요건 | UNRESOLVED | FTC "유사 법률 존재" 외 미조사 |
| E12 | Adventure 링크 추적파라미터 누락의 성격 | **POLICY_NOT_VERIFIED** | 공식 예시는 파라미터 사용(E2)하나 의무 미확정(E3) → 누락을 위반으로 판정하지 않음 |

---

## 7. 잔존 위험 (이 Discovery만으로는)

- **E8+E9+E6** 가 결합되면: Adventure는 제휴(Viator) 링크를 발행하면서 **FTC 기준의 material-connection 고지가 전무**한 상태. 단, 적용 관할(E10) 미확정이므로 "위반 확정"이 아닌 "의무 발생 가능성 + 고지 부재 확인됨" 수준.
- **추적파라미터 누락(E12)** 은 **POLICY_NOT_VERIFIED** — Viator 공식 예시는 파라미터를 쓰나 의무 여부가 미확정(#3)이므로, 이를 "위반"으로 판정하지 않음. 어트리뷰션/추적 결핍은 별도 운영 이슈일 뿐 고지 의무와는 구분.
- Viator 일반 계약(E5) 및 그 적용범위(E3/E4) 미확인 → 별도 해제 필요.
- 본 문서는 **발견만** 한다. 고지 문구 설계·코드 변경·writing-plans는 범위 외.

---

## 8. 다음 단계 후보 (미수행)

1. **관할 확정** — 운영자 관할/타깃 독자 확인 → E10/E11 해제 (인력 입력 필요).
2. **Viator 일반 affiliate 계약 확보** — 일반 VPP 운영 약관 본문 확보 → E5 해제, E3/E4 판정 가능.
3. **affiliate 고지 설계** — E6 기준 충족하는 문구·삽입 위치 설계 (content-design §4 U1 해결). 본 문서 범위 아님.

**승인 요청:** 본 Discovery는 조사·기록만 수행했다. 고지 문구 설계·코드 변경·새 문서 커밋은 하지 않았다. 승인 후 다음 단계(관할 확정 / Viator 일반 계약 확보 / 고지 설계)를 진행할 수 있다.

---
title: "Track C — Cross-Branch Content-Change Discovery (본문 품질 불균형 규명)"
doc_type: DISCOVERY
status: DISCOVERY_DRAFT
approved: false
part_of: "Track C (Cross-Branch Investigation & Synthesis)"
branch_investigated: "ETAP (branch 1) + car / curation(CUAP) / rap(RAP) / senior(SEAP) / travel(TAP) / stock(STAP) / mde2 / blogger"
created: 2026-08-20
method: "read-only static investigation; first-published-same-type baseline; no pilot; no cause attribution"
last_synth_gate: "상세 실행계획 승인 전"
---

# Track C — 분기별 본문 변화 Discovery (첫 발행 글 대비)

> **Part of:** Track C (branch investigation — ETAP = branch 1 of N).
> 기존 Track C 문서: `2026-08-20-track-c-blog-onboarding-design.md` (Cross-Branch Investigation & Synthesis, §2~§10 LEGACY).
> ETAP 분기(branch 1)는 아래 5개 문서가 이미 정본 증거임:
> - `2026-08-20-etap-auto-branches-discovery.md` — 35 자동 발행 분기 아키텍처·deploy 위반·affiliate subgroup
> - `2026-08-20-etap-adventure-content-design.md` — adventure 본문 설계·고지문 부재 근거
> - `2026-08-20-etap-adventure-affiliate-disclosure-discovery.md` — FTC/Viator 약관·고지 의무 증거
> - `2026-08-20-etap-adventure-affiliate-disclosure-design.md` — 고지 삽입 설계(미승인)
> - `2026-08-20-etap-adventure-affiliate-relationship-verification.md` — Viator 제휴 귀속 미검증

> **문서 단계 고지 (Stage Notice):** 본 Discovery / Verification 문서는 **프로젝트 확장 산출물(project expansion deliverable)**이며, **공식 Superpowers Design 승인 전(pre-approval) 단계**이다. 본 문서는 승인되지 않았으며 실행계획·구현을 포함하지 않는다.

> **문서 흐름 (Document Flow):**
> `Master Discovery → Branch Evidence → Synthesis → Approved Design Spec → Implementation Plan → Execution`
> - 현재 위치: **Master Discovery / Branch Evidence** (본 문서). Synthesis 이후 단계는 미작성·미승인.

## GOAL (목표)

**본문 품질 불균형이 색인(Indexing)·체류(Dwell)·신뢰성(Trust)에 미치는 위험을 분기별로 규명한 뒤 상세 실행계획 승인 전까지 종합한다.**

이 Discovery는 "어떤 분기가 어떤 품질 불균형을 가지고 있는가"를 표본 조사로 확인하는 단계이다. 원인 규명(CAUSE)과 수정 설계는 이 문서 범위 밖이며, 상세 실행계획(Execution Plan) 승인 이후로 미룬다.

## 1. 범위 및 방법

- **비교 기준선**: 사용자 지시에 따라 6개월 고정 폐기 → **각 repo의 첫 발행된 동유형 글(first-published same-type article)** 대비.
- **윈도우**: 저장소가 2026-01~04에 초기화되어 실제 관측폭은 ~1~5개월. "2월쯤 만든 블로그는 글이 없을 수 있다"는 전제 하에 내용 없는 하위 블로그는 NOT_COMPARABLE 처리.
- **준수 사항**: read-only 정적 조사. 파일럿/설계/코드 수정 없음. 원인 추정 금지(**CAUSE_UNKNOWN**). 비교는 표본 기반(sample-based).
- **대상 8분기**: ETAP(36) / curation-CUAP(15) / car-cap(8) / rap-RAP(5) / senior-SEAP(1 repo) / travel-TAP(5) / stock-STAP(6) / mde2(5, paused) + blogger(4, 외부).

## 2. 전체 비교표

| 분기 | Recent ↔ First | 동유형 | 방향 | 신뢰 | 핵심 변화 |
|---|---|---|---|---|---|
| **ETAP** | 2026-05 ↔ 2026-04 | 3/4 (esim NC) | **IMPROVED** | CONFIRMED | 가격현실화(USD 2.4→$31), bus/cruise에 AdSense+Viator카드+disclaimer+cross-link 추가 |
| **CUAP** | 2026-08 ↔ 2026-03 | yes | **MIXED** | HIGH | +비교표/체크리스트/JSON-LD/funnel · 단 boilerplate↑·내부링크상실·disclosure중복 |
| **car** | 2026-06 ↔ 2026-03 | yes | **MIXED** | — | deal 쿠팡추가(긍정) · tco 유지비표 raw필드명노출(퇴행) · ev unchanged |
| **RAP** | 2026-08 ↔ 2026-03 | yes | **MIXED** | HIGH | +lead+funnel+JSON-LD · 쿠팡상품링크→note-only 축소 · affiliate note는 초기부터 존재 |
| **SEAP** | 2026-05/06 ↔ 2026-03 | yes | **MIXED/stable** | MED/LOW | template stable · 일부 transport에 cross-blog financial promo card 추가 · prompt artifact 잔여 |
| **STAP** | 2026-06 ↔ 2026-03 | yes | **IMPROVED(구체성)** | HIGH | +entity-link card+내부링크+구체썸네일 · DART skeleton stable · affiliate 없음 |
| **mde2** | 2026-08 ↔ | chain만 | **NEW FORMAT** | HIGH | mc_post_id+chain-card+영문카테고리 7-28부터 신규 · non-chain unchanged |
| **TAP** | 2026-08 ↔ 2026-03 (travel3 정독) | yes | **MIXED** | CONFIRMED(travel3) | +lead+funnel+JSON-LD+nearby-card+naverbtn · 단 지역불일치/미완성/pending링크/중복고지 |
| **blogger(4)** | — | — | **BLOCKED_REPOSITORY_NOT_AVAILABLE** | — | 로컬 repo 없음(Blogger.com 외부) → 비교 불가 |

## 3. CROSS_BRANCH_SAMPLE_OBSERVATION (반복 확인된 변화)

> 아래 5개는 8분기 표본 조사에서 일관되게 관측된 패턴. **CROSS_BRANCH_SAMPLE_OBSERVATION** 등급 — 표본 기반 관측이며, 원인(CAUSE)은 **CAUSE_UNKNOWN**.

1. **구조/monetization 레이어 일괄 추가** — 모든 메이저 분기에서 초기 "최소 구조" → 최근 비교표·체크리스트·JSON-LD·funnel/cross-link·entity card·nearby-card·AdSense/상품카드가 추가됨 (ETAP bus/cruise, CUAP, RAP, SEAP일부, STAP, TAP 공통).
2. **affiliate 고지문 — 초기부터 존재하나 "중복 삽입" 경향** — CUAP recent(2회), TAP recent(2회 중복)에서 disclosure가 본문에 2번 등장 = 퇴행. 쿠팡 고지는 대부분 분기 초기부터 있었음(ETAP Viator는 별도议题로 고지 없음).
3. **내부링크 상실 → 교차블로그 링크로 대체** — CUAP(`함께 읽어보기`→cross-sell), RAP(내부링크→funnel), TAP(`{{< article >}}`→funnel-card). STAP만 내부링크 카드 **추가**=긍정.
4. **퇴행/결함 군집** — `tco-hugo` 유지비표 raw 변수명 노출 / `TAP` 김포시 표지인데 본문 3곳 전부 용인시(지역불일치) + 산뜨락 "정보 확인 필요" 미완성 + `pending://travel1-hugo/...` 깨진 링크 + JSON-LD url이 tour2.rotcha.kr(블로그는 travel3) 도메인 불일치 / `SEAP` prompt 잔여(`제목: … [수정본]`) / `CUAP` boilerplate 증가.
5. **가격·사실 구체성 개선 방향** — ETAP 가격현실화, STAP 빈테이블(TBD)→구체테이블, CUAP 구체 스펙 추가.

## 4. 분기별 증거 (Per-Branch Evidence)

### 4.1 ETAP (branch 1 — 정본 증거 문서 참조)
- 정본: `2026-08-20-etap-auto-branches-discovery.md` (35 자동 분기, deploy 위반, affiliate subgroup SG-A~SG-E), `2026-08-20-etap-adventure-content-design.md`, `2026-08-20-etap-adventure-affiliate-disclosure-discovery.md`, `2026-08-20-etap-adventure-affiliate-disclosure-design.md`(미승인), `2026-08-20-etap-adventure-affiliate-relationship-verification.md`.
- 표본 비교(본 Discovery): adventure(가격현실화+monetization 추가=IMPROVED), bus/cruise(AdSense+Viator카드+disclaimer+cross-link 추가=IMPROVED), esim은 repo 초기 글이 generic guide여서 동유형 첫 글 미충족=**NOT_COMPARABLE**.
- 미해결(별도议题): Viator affiliate 고지문 부재(FTC 의무 vs 미삽입), deploy 경로 `env -u CLOUDFLARE_API_TOKEN` 누락 위반.

### 4.2 curation / CUAP
- +비교표/체크리스트/JSON-LD/funnel-card/cross-sell 추가(구조↑). 단 boilerplate 증가, 같은 블로그 내부링크(`함께 읽어보기`) 상실, disclosure 중복. 쿠팡 고지·링크는 양시기 존재.

### 4.3 car / cap
- deal-hugo: 초기 현대 공식링크만 → recent 쿠팡 2링크+파트너스 문구(added, 긍정).
- tco-hugo: 초기 `자동차세 | 29` → recent `자동차세 (tax_annual) | 13만원` (raw 필드명 노출, **regression**).
- ev-hugo: 양시기 쿠팡 파트너스 고지 동일, 변화 없음.

### 4.4 rap / RAP
- 초기부터 쿠팡 상품링크 리스트+파트너스 문구 존재 → prior "rap has NO affiliate" 오기 확인(초기부터 있었음).
- recent: 상품링크 리스트 사라지고 note-only로 축소 + lead/funnel-card/JSON-LD 추가.
- 내부링크 callout(`📌 놓치면 아쉬운 글`)·함께 읽으면 좋은 글 footer·MOLIT/청약홈 면책은 양시기 유지.

### 4.5 senior / SEAP
- template stable(affiliate+gov24 CTA+footer 초기부터 동일).
- 일부 transport 글에 cross-blog financial promo card(`stap-related`→techpawz/dividend) 추가(부분적).
- prompt artifact 잔여(`제목: … 블로그: senior-hugo [수정본]`) 관측.

### 4.6 stock / STAP
- entity-link card + 내부 "함께 읽어보기" + 구체 R2 썸네일 추가(초기엔 없음/기본썸네일/TBD테이블).
- DART 실적 글 골격 안정적·고구체. affiliate 링크 없음(기대대로).

### 4.7 mde2 (paused, 생성기 UNKNOWN)
- chain 포맷(`mc_post_id`+`chain-card`+영문카테고리)은 2026-07-28부터 등장, 그 이전/non-chain 글은 변화 없음 = **NEW FORMAT**(기존 글 인플레이스 재작성 아님).
- 5개 블로그 전부 paused, biz-techpawz-hugo는 0 포스트.

### 4.8 travel / TAP (travel3 정독)
- earliest(2026-03-11 한정식 5곳): prose 중심+비교표+내부 `article` 3건+쿠팡 2링크.
- recent(2026-08-20 김포시 3곳): lead+상단/하단 funnel-card+JSON-LD+nearby-card 5건+naver btn+쿠팡 3카드(고지 중복).
- **퇴행**: 제목 "김포시"이나 주소 3곳 모두 용인시 / 산뜨락 "정보 확인 필요" 미완성 / `pending://travel1-hugo/...` 깨진 링크 / JSON-LD url `tour2.rotcha.kr`(도메인 불일치). → **MIXED, CONFIRMED**.
- travel1/4는 이번 패스 정독 생략(쌍 확보, sample-based로 travel3만 확정).

### 4.9 blogger (4)
- **BLOCKED_REPOSITORY_NOT_AVAILABLE** — 로컬 repo 없음(Blogger.com 외부 발행). 5000 참조는 senior-blogger/tap-blogger 라우팅뿐. 비교 불가.

## 5. CAUSE (원인)

**CAUSE_UNKNOWN** — 본 Discovery는 read-only 표본 조사이며 파이프라인/prompt/생성 코드를 검사하지 않았음. 모든 "퇴행/결함/추가"는 관측 사실만 기록하며, 템플릿 업그레이드·스케줄러 타이밍·생성기 교체 등 구체 원인은 귀속하지 않음. 원인 규명은 상세 실행계획 단계에서 수행.

## 6. 한계 (Limitations / 잔존 위험)

- **표본 기반 + 기준선 1~5개월** — 저장소가 2026-01~04 초기화되어 "6개월 변화" 자체가 불가. 첫 발행 글 대비라도 관측폭 짧음.
- **CAUSE_UNKNOWN** — Discovery 전용, 파이프라인/prompt 미검사.
- **TAP travel1/4 미정독** — travel3만 정독 확정, 나머지 2개는 구조적 관찰만.
- **blogger(4) BLOCKED_REPOSITORY_NOT_AVAILABLE** — 로컬 repo 없음.
- **esim(ETAP) NOT_COMPARABLE** — repo 초기 글이 generic guide.
- **mde2 생성기 UNKNOWN** — 전부 paused.
- **원인 귀속 없음** — 모든 항목은 관측 사실, 수정 제안 없음(설계 단계 아님).

## 7. STATUS

- 문서 상태: **DISCOVERY_DRAFT** (승인되지 않음, 실행계획 미작성).
- 다음 게이트: 상세 실행계획(Execution Plan) 승인 → 분기별 수정 설계 → 구현.
- 커밋: 미수행 (이 문서는 작성만 함).

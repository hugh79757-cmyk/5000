---
title: "Track C — Branch Content-Change Discovery (PAUSED HANDOFF)"
doc_type: HANDOFF
status: PAUSED_HANDOFF
pause_reason: "Master Discovery / Branch Evidence 완료, 다음 단계(Cross-Branch Synthesis)는 미작성 — 사용자 승인 전"
implementation_authorized: false
execution_authorized: false
autonomous_decision_authorized: false
commit_authorized: false
push_authorized: false
next_active_track: "Track C — Cross-Branch Synthesis (미작성)"
canonical_discovery: "docs/superpowers/specs/2026-08-20-track-c-branch-content-change-discovery.md"
created: 2026-08-20
---

# Track C — 분기별 본문 변화 Discovery (PAUSED HANDOFF)

> **Part of:** Track C (Cross-Branch Investigation & Synthesis).
> 본 문서는 진입점(landing)이며, 실제 증거는 정본 Discovery 문서에 있음.

## ① Track C 목적 · 종료점

- **목적**: 본문 품질 불균형이 **색인(Indexing) · 체류(Dwell) · 신뢰성(Trust)** 에 미치는 위험을 **분기별로 규명**한 뒤 종합한다.
- **종료점(이 Discovery 단계)**: Cross-Branch **Synthesis** 완료 → **상세 실행계획**(Approved Design Spec → Implementation Plan) 작성·승인. Track C 전체 종료는 실행계획 승인(+필요시 구현)까지.
- **현재 위치**: `Master Discovery → Branch Evidence` (Synthesis 미작성, 미승인).

## ② 잘못된 온보딩 프레이밍 폐기

- 초기 Track C를 "신규 블로그 / vertical 온보딩 거버넌스"로 라벨링한 것은 **잘못 기록됨** → 폐기.
- Track C = **분기(branch) 조사의 종합 작업**. ETAP 조사를 마친 후 다른 분기(car/rap/senior/curation/travel/stock/mde2/blogger)를 조사·종합.
- 관련 설계 문서 `2026-08-20-track-c-blog-onboarding-design.md` 의 §2~§10은 **LEGACY** 표시로 보존하되, 온보딩 내용은 더 이상 Track C 범위 아님.
- ETAP 관련 design/discovery/verification 스펙 5개는 **전부 Track C 에 속함**(branch 1).

## ③ 정본 읽기 순서 (Recommended Reading Order)

1. **본 문서** (진입점)
2. `docs/superpowers/specs/2026-08-20-track-c-branch-content-change-discovery.md` — **Discovery 정본** (전체 비교표·CROSS_BRANCH_SAMPLE_OBSERVATION·분기별 증거·문서흐름)
3. `docs/superpowers/specs/2026-08-20-track-c-blog-onboarding-design.md` — LEGACY 프레이밍 참고용(**온보딩 내용은 무시**)
4. ETAP branch 1 정본 (순서):
   - `2026-08-20-etap-auto-branches-discovery.md`
   - `2026-08-20-etap-adventure-content-design.md`
   - `2026-08-20-etap-adventure-affiliate-disclosure-discovery.md`
   - `2026-08-20-etap-adventure-affiliate-disclosure-design.md` (미승인)
   - `2026-08-20-etap-adventure-affiliate-relationship-verification.md`

## ④ 분기별 상태 (DONE / PARTIAL / BLOCKED)

| 분기 | 상태 | 비고 |
|---|---|---|
| ETAP | **PARTIAL** | IMPROVED 확정 3/4, esim NOT_COMPARABLE; Viator 고지/배포위반 별도议题 미결 |
| curation (CUAP) | **PARTIAL** | MIXED, 표본 3/15 |
| car (cap) | **PARTIAL** | MIXED, 표본 3/8 |
| rap (RAP) | **PARTIAL** | MIXED, 표본 3/5 |
| senior (SEAP) | **PARTIAL** | MIXED/stable, 표본 3 types |
| stock (STAP) | **PARTIAL** | IMPROVED(구체성), 표본 3/6 |
| mde2 | **PARTIAL** | NEW FORMAT 확인, 생성기 UNKNOWN, 5/5 paused |
| travel (TAP) | **PARTIAL** | travel3 정독 MIXED CONFIRMED; travel1/4 미정독 |
| blogger (4) | **BLOCKED** | BLOCKED_REPOSITORY_NOT_AVAILABLE (로컬 repo 없음) |

> 모든 감사 분기는 **표본 기반**이며 어느 분기도 완전 감사(DONE) 아님. Blogger만 BLOCKED.

## ⑤ 첫 발행 동유형 글 비교 원칙 · CAUSE_UNKNOWN

- **비교 원칙**: 6개월 고정 폐기 → 각 repo의 **첫 발행된 동유형 글(first-published same-type article)** 대비. 2월쯤 생성된 블로그는 내용 없을 수 있음 → NOT_COMPARABLE 처리. 관측 윈도우 ~1~5개월(저장소 2026-01~04 초기화).
- **CAUSE_UNKNOWN**: read-only 정적 조사, 파이프라인/prompt/생성 코드 미검사. 모든 "추가/퇴행/결함"은 **관측 사실만** 기록하며 원인 귀속 금지. 원인 규명은 상세 실행계획(Execution Plan) 단계에서 수행.

## ⑥ 미결사항 (Open Items)

- **TAP**: travel1/4 정독 누락(쌍은 확보, 미정독). travel3 퇴행 관측됨 — 제목 "김포시"이나 본문 3곳 전부 용인시(지역불일치) / 산뜨락 "정보 확인 필요" 미완성 / `pending://travel1-hugo/...` 깨진 링크 / JSON-LD url `tour2.rotcha.kr` 도메인 불일치. 원인 미규명.
- **mde2**: 생성기 UNKNOWN(외부 md-editor/blogsmith 추정). chain 포맷(`mc_post_id`+`chain-card`+영문카테고리) 2026-07-28부터 신규, non-chain은 unchanged. biz-techpawz-hugo 0 포스트. 전부 paused.
- **Blogger**: 로컬 repo 없음(BLOCKED_REPOSITORY_NOT_AVAILABLE, Blogger.com 외부 발행). senior-blogger/tap-blogger는 5000 라우팅만 존재, 본문 비교 불가.
- **ETAP**: Viator affiliate 고지문 부재(FTC 의무 vs 미삽입) 별도议题. deploy 경로 `env -u CLOUDFLARE_API_TOKEN` 누락 위반. esim NOT_COMPARABLE(repo 초기 글이 generic guide).

## ⑦ 다음 세션 첫 작업

1. **미완료 증거 보완**: TAP travel1/4 정독, esim 같은 유형 첫 글 재탐색 등 표본 누락 보완.
2. 그 후 **Cross-Branch Synthesis** 작성 (분기별 불균형 → 색인/체류/신뢰성 리스크로 종합).
3. 그 후 **상세 실행계획**(Approved Design Spec → Implementation Plan) 작성.
4. **승인 전까지 구현 금지**.

## ⑧ untracked / 무관 변경 보호 규칙

- 워킹트리에 **타 세션 잔존 변경 23개 파일** 존재 (`.planning/*`, `config/blogs.d/*`, `ops_dashboard/checks/*`, `pipelines/*`, `shared/*`, 기타) — **본 Track C Discovery와 무관**.
- **보호 규칙**:
  - (a) 본 handoff/discovery 문서는 **untracked(`??`)** 상태, commit 금지 지시 준수 중.
  - (b) 새 세션은 본 작업과 무관한 23개 변경을 **건드리지 말 것**.
  - (c) Track C 관련 파일(`docs/superpowers/specs/2026-08-20-track-c-branch-content-change-discovery.md`, 본 handoff)만 편집 대상으로 한정.
  - (d) 다른 파일의 수정·커밋은 **명시적 사용자 승인 없이 수행하지 않음**.
  - (e) untracked discovery doc 유실 방지: 같은 머신에서만 안전 — 머신 교체/초기화 전 커밋 권고(단 오늘은 금지).

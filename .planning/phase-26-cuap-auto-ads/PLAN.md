# PLAN.md — Phase 26: CUAP Auto Ads (Anchor/Full-page) Activation

## Goal
CUAP의 10개 curation 블로그(`*.informationhot.kr`)에서 Google AdSense **오토 애드(앵커 광고 / 전면 광고)**가
정상 노출되도록 활성화한다. 현재 인아티클 슬롯은 떠 있으나 앵커/전면 광고가 안 뜨는 근본 원인을 해결한다.

## Root Cause (Confirmed)
Blowfish 테마는 `layouts/partials/head.html:225`에서
`.Site.Params.advertisement.adsense` 키를 읽어 `<meta name="google-adsense-account" content="...">`를
자동 주입한다. 이 메타가 있어야 AdSense가 오토 애드(앵커/전면)를 활성화한다.

- **tour1.rotcha.kr (참조 정상 사이트)**: `params.toml`에 `[advertisement] adsense = "ca-pub-8772455780561463"` → 메타 자동 주입 ✓
- **CUAP 10개 블로그 (현재)**: `params.toml`에 `[adsense] clientID = "..."` 형태 → Blowfish가 기대하는
  `[advertisement] adsense` 키가 아님 → 메타 미주입 → 오토 애드 비활성 ✗
- 추가로 CUAP 10개 모두 `layouts/partials/extend_head.html` 이 **MISSING** (tour1은 GA4+adsbygoogle.js 로더 있음)

→ 두 가지를 모두 교정한다.

## CRITICAL CONSTRAINTS (절대 위반 금지)
1. **도메인/퍼블리셔 ID 매핑**: CUAP은 `informationhot.kr` 계열 → `ca-pub-6677996696534146` ONLY.
   tour1/rotcha의 `ca-pub-8772455780561463` 과 **절대 섞지 말 것** (AGENTS.md §1 절대 규칙).
2. **점진적 롤아웃**: "한꺼번에 전체를 바꾸면 안 됨. CUAP부터 먼저 tour1에 맞추고, 검증한 뒤 다른 블로그로 확장"
   → 이 페이즈는 **CUAP 10개만** 대상. rotcha.kr / techpawz.com 확장은 이 페이즈 범위 밖(별도 페이즈).
3. **수동 wrangler 금지**: 배포는 반드시 `dispatcher.py` 경유 (AGENTS.md Deployment Rules).

## Scope
**IN:**
- CUAP 10개 블로그 `config/_default/params.toml`의 `[adsense]` → `[advertisement]` 섹션 교정
  (키: `adsense = "ca-pub-6677996696534146"`, 슬롯 키는 기존값 유지: `inArticleSlot`, `leaderboardSlot`)
- CUAP 10개 블로그 `layouts/partials/extend_head.html` 신규 생성 (GA4 + adsbygoogle.js?client=ca-pub-6677996696534146)
- beauty-hugo 먼저 빌드·검증 → 10개 일괄 적용 → 커밋

**OUT (이 페이즈 아님):**
- rotcha.kr 메인 / tour1 / travel1~4 오토 애드 (이미 정상, 건드리지 않음)
- techpawz.com 빌드 깨짐 재빌드 (별도 페이즈)
- rotcha.kr 앵커 광고 미노출 수정 (CUAP 검증 후 별도 페이즈)

## Reference Template (tour1.rotcha.kr = TAP/travel-hugo)
사용자 질문 3가지에 대한 실측 답변:
- **한글/영어 키**: 영어 키 사용 (`[advertisement]` 섹션, `adsense`/`inArticleSlot` 카멜케이스). 언어 토글 아님.
- **토글**: `[advertisement]` 섹션 자체가 on/off. `mobileStickySlot`은 tour1에도 있으나 앵커와 충돌 우려 —
  이 페이즈에서는 CUAP에 `mobileStickySlot` 추가 안 함 (AGENTS.md §: mobile-sticky 사용 금지). 인아티클/리더보드만.
- **리스트 형태**: 키=값 형태(TOML table), 슬롯은 문자열.

### tour1 `params.toml` (참조)
```toml
[advertisement]
  adsense = "ca-pub-8772455780561463"
  inArticleSlot = "3892531241"
  leaderboardSlot = "6262052368"
```

### tour1 `extend_head.html` (참조)
```html
<!-- GA4 -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-XXXX"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'G-XXXX');
</script>
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-8772455780561463"
     crossorigin="anonymous"></script>
```

## Tasks

### T1 — params.toml 섹션 교정 (CUAP 10개)
- 대상: `/Users/twinssn/Projects/cuap/{blog}-hugo/config/_default/params.toml` (10개)
- 변경: `[adsense]` 블록을 `[advertisement]` 로 rename, `clientID =` → `adsense =` 로 rename.
  값(`ca-pub-6677996696534146`) 및 슬롯 키(`inArticleSlot`, `leaderboardSlot`)는 기존값 유지.
- 10개 블로그 목록: beauty, (나머지 9개는 T2에서 일괄)

### T2 — extend_head.html 신규 생성 (CUAP 10개)
- 각 블로그 `layouts/partials/extend_head.html` 생성.
- 내용: GA4 (각 블로그 G-XXXX 유지/확인) + `adsbygoogle.js?client=ca-pub-6677996696534146`.
- 주의: client는 **반드시** `ca-pub-6677996696534146` (rotcha ID 아님).

### T3 — beauty-hugo 빌드·검증 (퍼스트 웨이브)
- `hugo --gc --minify --source /Users/twinssn/Projects/cuap/beauty-hugo`
- 검증: `public/index.html` (및 `public/posts/*/index.html`) 에
  `<meta name="google-adsense-account" content="ca-pub-6677996696534146">` 존재 확인
- 검증: 인아티클 `<ins class="adsbygoogle" data-ad-slot="2195212287">` 유지 확인
- 검증: client ID가 `ca-pub-6677996696534146` 인지 (rotcha ID 혼입 없음) 확인

### T4 — 10개 블로그 일괄 적용 + 커밋
- T1/T2를 나머지 9개 블로그에 동일 적용 (스크립트 또는 병렬 edit)
- 각 블로그 git commit (메시지: "fix: activate AdSense auto ads via [advertisement] + extend_head")
- 배포: `python3 /Users/twinssn/Projects/5000/dispatcher.py {blog_id}` 로 각 블로그 배포
  (dispatcher가 빌드+배포 일괄. CUAP은 Pages 블로그)

### T5 — 라이브 검증 (배포 후)
- 배포된 사이트 HTML에서 `google-adsense-account` 메타 노출 확인 (curl)
- AdSense 대시보드에서 해당 도메인 앵커 광고 승인/활성 상태 확인 (수동, 사용자)

## Verification Loop
- [ ] T3: beauty-hugo 빌드 성공, 메타 태그 `ca-pub-6677996696534146` 노출 확인
- [ ] T3: 인아티클 슬롯 기존과 동일(2195212287) 유지
- [ ] T4: 10개 블로그 모두 동일 패턴 적용, 빌드 에러 0
- [ ] T4: 배포 후 라이브 메타 노출 확인 (10/10)
- [ ] T4: pub ID 혼입 검증 — 어느 블로그에도 `ca-pub-8772455780561463` 이 들어가 있지 않음 (grep)
- [ ] 잔존 위험: AdSense 오토 애드 실제 수익 발생은 대시보드 승인 후 며칠 소요 — 모니터링 필요

## Out of Scope (다음 페이즈 후보)
- rotcha.kr 메인 앵커 광고 미노출 (동일 근본 원인 가능성 → 별도 페이즈)
- techpawz.com (ETAP, techpawz.com 도메인) 빌드 깨짐 재빌드+배포
- CUAP 배포 후 "며칠 모니터링 후 바꿀 거 또 바꾸자" (운영 피드백 반영)

# PLAN.md — Phase 29: CUAP 콘텐츠 오염 + 퍼널 카드 404 + 광고 공백 수정

**Mode:** standard (horizontal)
**Verified against:** `CONTEXT.md` (라이브 검증 + DB 쿼리 + 파일시스템 대조)

---

## Goal

1. Pet 블로그에 뷰티 글 발행 방지 (키워드 필터 강화)
2. `cuap_entities` 테이블의 잘못된 URL 정리 → 크로스셀 카드 404 해결
3. beauty-hugo 재배포 → 광고 공백 해결

---

## Scope

**IN**
- `keywords.py` — pet-hugo 키워드 검증 + 뷰티 키워드 제거
- `cuap_entities` DB — 오염 URL 삭제 또는 실제 slug로 업데이트
- beauty-hugo 재배포
- 광고 partial 파일 검증

**OUT**
- 기존 발행된 글 수정
- AdSense Publisher ID 변경

---

## Tasks

### 29-01 — Pet-hugo 키워드 검증 및 뷰티 키워드 제거
- **WHERE:** `pipelines/curation/keywords.py`
- **HOW:**
  1. `pet-hugo` 키워드 목록에서 뷰티/홈케어 관련 키워드 확인
  2. 의심 키워드: "홈케어", "마사지기", "괄사", "필링", "패드", "피부관리" 등
  3. `_filter_irrelevant_products()` 필터에서 pet-hugo와 무관한 카테고리 차단 확인
- **EXPECTED:** pet-hugo 키워드 목록에 뷰티 키워드 0개

### 29-02 — cuap_entities 테이블 URL 정리
- **WHERE:** `data/travel-en.db` (cuap_entities 테이블)
- **HOW:**
  1. 오염된 URL (`20260721-` 접두사) 가진 레코드 식별
  2. 실제 slug 존재 여부 파일시스템으로 확인
  3. 존재하지 않는 URL → 레코드 삭제 (해당 블로그의 실제 최신 글로 대체)
  4. `build_cross_sell_card()`가 올바른 URL을 반환하는지 확인
- **EXPECTED:** cuap_entities의 모든 URL이 실제 파일시스템 slug와 일치

### 29-03 — beauty-hugo 재배포
- **WHERE:** `/Users/twinssn/Projects/cuap/beauty-hugo`
- **HOW:**
  1. `deploy_site('/Users/twinssn/Projects/cuap/beauty-hugo', 'beauty-hugo')` 호출
  2. 배포 후 라이브 검증: 실제 포스트 200, missing 404
- **EXPECTED:** beauty.informationhot.kr 포스트 접근 시 404가 아닌 200 반환

### 29-04 — 광고 partial 검증
- **WHERE:** `/Users/twinssn/Projects/cuap/beauty-hugo/layouts/partials/adsense/`
- **HOW:**
  1. `in-article.html`, `leaderboard.html`, `lazy-load.html` 존재 확인
  2. `extend-head.html` 또는 `extend_head.html`에 AdSense 스크립트 포함 확인
  3. 브라우저 개발자 도구로 `adsbygoogle` 요소 로드 확인
- **EXPECTED:** 광고 스크립트 정상 로드, `adsbygoogle` 요소 존재

---

## Verification loop (goal-backward)

| Criterion | Source | Pass when |
|-----------|--------|-----------|
| pet-hugo 키워드에 뷰티 키워드 없음 | 29-01 | grep으로 뷰티 키워드 0건 |
| cuap_entities URL 모두 유효 | 29-02 | 모든 URL이 파일시스템과 일치 |
| beauty-hugo 라이브 200 | 29-03 | curl로 실제 포스트 200 |
| 광고 partial 존재 | 29-04 | 파일 존재 + 스크립트 로드 확인 |

---

## Residual risks
- **R1 (low):** cuap_entities 정리 후 크로스셀 카드에 빈 카드 표시 가능
- **R2 (low):** beauty-hugo 재배포 후 Hugo 빌드 에러 가능성 (이전 figure shortcode 이슈)

---

## Deliverables
- 정리된 `keywords.py` (pet-hugo 뷰티 키워드 제거)
- 정리된 `cuap_entities` DB (URL 정합성 확보)
- 재배포된 beauty-hugo
- 광고 partial 검증 결과

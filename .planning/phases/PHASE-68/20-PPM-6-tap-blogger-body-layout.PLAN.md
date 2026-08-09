---
wave: 1
depends_on: [67]
gap_closure: true
---

# PHASE-68: TAP 블로거 발행글 본문 레이아웃 보완

**Created:** 2026-08-09
**Gap closure for:** PHASE-68 발행글 레이아웃 보완

## Context

Phase 68에서 TAP 블로거(tap-blogger) 발행 시 생성된 글의 본문 레이아웃 보완 요청.

**리서치 핵심 발견 (2026-08-09):**
tap-blogger(travel.rotcha.kr, Blogger 플랫폼)는 5000의 `writer.py` 후처리 파이프라인을 **경유하지 않는다**. 5000 `dispatcher.py` → `_run_tap_subprocess()` → **TAP 프로젝트(`/Users/twinssn/Projects/TAP/`)** 자체 파이프라인으로 발행되며, 본문 생성·후처리는 전적으로 TAP 내부 모듈(`ai_writer.py`, `content_processor.py`)에 의존한다.

- 5000 `writer.py:_post_process()` (H2 제한, 쿠팡 여행용품 삽입, 엔티티 카드 등) → **Hugo 플랫폼 블로그 전용**, tap-blogger와 무관
- 5000 `coupang_travel.py:get_product_cards()` → 5000 `_post_process()`에서만 호출, tap-blogger 무관
- tap-blogger의 H2 구조는 TAP `ai_writer.py` 프롬프트가 결정 (camping 4개, heritage 3개, festival 2개, korservice 5개)
- tap-blogger의 본문 후처리는 TAP `content_processor.py`가 담당 (이미지 삽입, 네이버 지도 버튼, nearby 카드, 엔티티 카드 등)

**따라서** 5000 `writer.py`나 `coupang_travel.py` 수정은 tap-blogger 발행글에 영향을 주지 않으며, 실질적인 레이아웃 개선은 **TAP 프로젝트 내부 코드**에서 이루어져야 한다.

## 결정 사항

사용자 요청 내용 (https://travel.rotcha.kr/2026/08/3_01403288312.html 기준):

- "여행 준비에 도움되는 추천 용품" 섹션이 H2로 표시되도록
- 해당 섹션 위에 "마무리" H2 소제목 추가
- 네이버 지도에서 보기 버튼 가운데 정렬 + 위아래 여백 확보

**단, 리서치 결과 tap-blogger는 5000 writer.py를 거치지 않으므로, 위 항목은 TAP 프로젝트 코드에서 구현되어야 함.** 5000-side 코드 수정은 tap-blogger에 영향 없음.

## Acceptance Criteria

**⚠️ 주의: 아래 기준은 5000-side 코드 수정 기준이며, tap-blogger에는 영향 없음.**

- [x] `pipelines/travel/writer.py`에서 쿠팡 상품 리스트 섹션 제목이 `## `로 시작하도록 수정 (Hugo 블로그 전용)
- [x] 본문 마지막에 "마무리" H2가 "여행 준비에 도움되는 추천 용품" 위에 삽입되도록 로직 추가 (Hugo 블로그 전용)
- [x] 네이버 지도 버튼 스타일 가운데 정렬 적용 (Hugo 블로그 전용)
- [x] 기존 테스트 통과 확인

**tap-blogger 실제 적용을 위한 별도 기준 (TAP 프로젝트 코드):**
- [ ] TAP `ai_writer.py` 프롬프트에서 "마무리" H2 구조 포함 여부 확인
- [ ] TAP `content_processor.py:insert_images_and_links()`에서 네이버 지도 버튼 스타일 확인 (가운데 정렬, 여백)
- [ ] TAP 발행글 실제 확인 (travel.rotcha.kr)

## 범위 (Scope)

### 포함할 파일 (5000-side, Hugo 블로그 전용)

- `pipelines/travel/writer.py` — Hugo 여행 블로그용 본문 후처리
- `shared/coupang_travel.py` — Hugo 블로그용 쿠팡 상품 카드

### 포함할 파일 (TAP 프로젝트, tap-blogger 전용)

- `/Users/twinssn/Projects/TAP/core/ai_writer.py` — AI 본문 생성, H2 구조 결정
- `/Users/twinssn/Projects/TAP/core/content_processor.py` — 본문 후처리 (이미지, 지도 버튼, 카드 등)
- `/Users/twinssn/Projects/TAP/app.py` — 발행 파이프라인

### 포함하지 않을 파일

- 다른 파이프라인 코드
- Blogger 외 플랫폼 관련 코드

## 하위 작업

### Task 1: (5000-side) 추천 용품 섹션 H2화 — Hugo 블로그 전용

`pipelines/travel/writer.py`에서 쿠팡 상품 리스트 출력 부분의 제목 행을 `<p><strong>...</strong></p>`에서 `## ...`로 변경.

현재 코드 확인 필요: `_inject_coupang_products()` 또는 유사 함수에서 `<strong>여행 준비에 도움되는 추천 용품</strong>`를 `## 여행 준비에 도움되는 추천 용품`으로 변경.

**적용 대상:** travel-hugo, travel1-hugo, travel2-hugo, travel3-hugo, travel4-hugo (Hugo 플랫폼)
**미적용:** tap-blogger (Blogger 플랫폼, 5000 writer.py 미사용)

### Task 2: (5000-side) 마무리 H2 추가 — Hugo 블로그 전용

본문 마지막에 "마무리" H2 추가 로직 구현. 위치는 "여행 준비에 도움되는 추천 용품" 섹션 바로 위.

- 기존 본문 끝부분 감지 후 H2 삽입
- 또는 post-processing 단계에서 마지막 섹션 앞에 H2 추가

**적용 대상:** travel-hugo 등 Hugo 블로그
**미적용:** tap-blogger

### Task 3: (5000-side) 네이버 지도 버튼 가운데 정렬 + 여백 — Hugo 블로그 전용

`_inject_naver_map()` 함수에서 생성되는 버튼 HTML에 가운데 정렬 및 위아래 여백 스타일 추가:

```html
<div style="text-align:center; margin-top:24px; margin-bottom:24px;">
  <a href="..." ...>네이버 지도에서 보기</a>
</div>
```

- 기존 `margin-top:12px` → `margin-top:24px; margin-bottom:24px`로 변경
- 버튼 위아래 여백 확보로 가독성 개선 (고씨굴 등 장소명에서 버튼 간격이 좁았던 문제 해결)

**적용 대상:** travel-hugo 등 Hugo 블로그
**미적용:** tap-blogger

---

### Task 4: (TAP 프로젝트) tap-blogger 레이아웃 확인 및 개선 — 실제 적용 대상

**리서치 결과 tap-blogger의 레이아웃은 TAP 프로젝트 코드에서 결정됨.** 5000-side 코드는 tap-blogger에 영향 없음.

4-1. **네이버 지도 버튼 스타일 확인**
   - 파일: `/Users/twinssn/Projects/TAP/core/content_processor.py`
   - 함수: `insert_images_and_links()` (L185-259)
   - 버튼 HTML에 `text-align:center` 및 `margin` 스타일 적용 여부 확인
   - 미적용도면 수정 필요

4-2. **"마무리" H2 구조 확인**
   - 파일: `/Users/twinssn/Projects/TAP/core/ai_writer.py`
   - 캠핑 프롬프트 (L200-233): h2 구조에 "마무리" 포함 여부 확인
   - user가 요청한 "마무리" H2가 프롬프트에 명시되어 있는지 확인

4-3. **쿠팡 상품 섹션 (선택)**
   - tap-blogger에는 현재 쿠팡 상품 섹션이 없음 (TAP content_processor.py에 쿠팡 관련 코드 없음)
   - 필요시 TAP content_processor.py에 5000 CoupangTravel 연동 추가 검토
   - 단, 여행 테마(캠핑, 문화유산, 축제)에서는 Trip.com 제휴 박스도 삽입되지 않음 (AFFILIATE_INAPPROPRIATE_KEYWORDS)

## 완료 기준

**5000-side (Hugo 블로그 전용):**
- [x] travel-hugo 등에서 "여행 준비에 도움되는 추천 용품"이 H2로 표시됨
- [x] 해당 섹션 위에 "마무리" H2 존재
- [x] 네이버 지도 버튼 가운데 정렬 + 위아래 24px 여백 적용됨
- [x] 기존 기능 회귀 없음 (H2 개수 제한 등 영향 확인)

**TAP 프로젝트 (tap-blogger 실제 적용):**
- [ ] TAP content_processor.py의 네이버 지도 버튼 스타일 확인 및 필요시 수정
- [ ] TAP ai_writer.py 프롬프트의 "마무리" H2 구조 확인
- [ ] tap-blogger 실제 발행글(travel.rotcha.kr)에서 레이아웃 확인

## 검증 기준

**5000-side:**
- [x] writer.py 코드 수정 확인 (_inject_naver_map, _post_process)
- [x] coupang_travel.py 코드 수정 확인 (get_product_cards H2 출력)
- [x] 실제 발행글에서 H2 구조 확인 (또는 테스트로 검증)
- [x] 네이버 지도 버튼 스타일 확인 (test 스크립트로 검증)

**TAP 프로젝트:**
- [ ] content_processor.py:insert_images_and_links() 네이버 지도 버튼 HTML 확인
- [ ] ai_writer.py 프롬프트의 마무리 H2 구조 확인
- [ ] tap-blogger 실제 발행글 확인 (travel.rotcha.kr)

## 참고

- 기존 발행글 (강원도 영월 가족 캠핑장): https://travel.rotcha.kr/2026/08/3_01403288312.html
- TAP body layout spec: `.config/opencode/skills/tap-blog-spec/SKILL.md`
- writer.py H2 개수 제한: 최대 4개 (writer.py L695-698)
- **RESEARCH 결과:** tap-blogger는 5000 writer.py를 거치지 않음 — TAP 프로젝트 자체 파이프라인 사용
- RESEARCH 파일: `.planning/phases/68-tap-blogger-layout/68-RESEARCH.md`
- TAP ai_writer.py 프롬프트 h2 구조:
  - camping: 4개 (고르는 기준, 한눈에 비교, 방문 팁, 마무리)
  - heritage: 3개 (보는 포인트, 한눈에 비교, 마무리)
  - festival: 2개 (+ 도입부 p)
  - korservice: 5개 (고르는 기준, 한눈에 비교, 방문 팁, FAQ, 마무리)
- TAP content_processor.py:insert_images_and_links() — 네이버 지도 버튼 생성 (L185-259)

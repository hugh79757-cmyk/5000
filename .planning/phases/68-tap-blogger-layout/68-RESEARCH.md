# Phase 68: TAP 블로거(tap-blogger) 발행글 본문 레이아웃 보완 - Research

**Researched:** 2026-08-09
**Domain:** TAP 여행 파이프라인 본문 후처리 · Blogger 발행 레이아웃
**Confidence:** HIGH

## Summary

Phase 68의 대상인 **tap-blogger**(travel.rotcha.kr, Blogger 플랫폼)는 5000의 `writer.py` 후처리 파이프라인을 **경유하지 않는다**. tap-blogger는 5000 `dispatcher.py` → `_run_tap_subprocess()` → **TAP 프로젝트(`/Users/twinssn/Projects/TAP/app.py`)** 의 자체 파이프라인으로 발행되며, 본문 생성·후처리는 전적으로 TAP 내부 모듈에 의존한다.

**핵심 발견:** 5000 `writer.py`의 `_post_process()`(H2 개수 제한·쿠팡 여행용품 삽입·엔티티 카드 등)는 **Hugo 플랫폼 블로그 전용**이며, tap-blogger에는 적용되지 않는다. tap-blogger의 본문 레이아웃은 TAP `ai_writer.py`의 프롬프트 설계와 `content_processor.py`의 후처리 체인이 결정한다. 따라서 "H2 개수 제한"이나 "쿠팡 상품 섹션"은 tap-blogger 맥락에서는 **관련 없는 5000-side 코드**다.

---

## User Constraints (from CONTEXT.md)

### Locked Decisions
- 없음 (Phase 68 CONTEXT.md 미존재 — 최초 연구)

### the agent's Discretion
- tap-blogger 본문 레이아웃 개선 범위 결정
- Blogger 플랫폼의 HTML 렌더링 특성 고려

### Deferred Ideas (OUT OF SCOPE)
- 없음

---

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| (미지정) | TAP 블로거 발행글 본문 레이아웃 보완 | 아래 분석 결과 참고 |

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| tap-blogger 본문 생성 (AI) | TAP app.py (외부 프로젝트) | — | 5000이 subprocess로 호출하지만, 실제 AI 생성은 TAP `ai_writer.py`가 담당 |
| tap-blogger 본문 후처리 | TAP `content_processor.py` | — | 이미지 삽입, 근처 정보, 엔티티 카드, schema.org 등 모두 TAP 내부 |
| H2 구조 설계 | TAP `ai_writer.py` 프롬프트 | — | 프롬프트에서 h2/h3 구조를 명시 |
| 쿠팡 상품 카드 | 5000 `coupang_travel.py` | — | 5000 `writer.py:_post_process()`에서만 호출 — tap-blogger 무관 |
| H2 개수 제한 | 5000 `writer.py:_post_process()` | — | 5000 Hugo 블로그 전용 — tap-blogger 무관 |
| Blogger 발행 | TAP `blogger_publisher.py` | — | Google Blogger API v3 직접 호출 |
| 엔티티 카드 | TAP `tap_entity_manager.py` | — | 6개 블로그 교차 링크, TAP `content_processor.py`에서 호출 |

---

## Standard Stack

TAP 블로거 파이프라인은 5000의 Python 스택과 별도 가상 환경(TAP_ROOT/venv)을 사용한다. 관련 라이브러리:

| Library | Purpose | Notes |
|---------|---------|-------|
| `openai` | GPT-4.1-mini 호출 (TAP ai_writer.py) | TAP 자체 OpenAI 클라이언트 |
| `google-api-python-client` | Blogger API v3 발행 | TAP `blogger_publisher.py` |
| `sqlalchemy` | tap.db 세션 관리 (중복 방지) | TAP `database.py` |
| `requests` | 네이버 블로그 API, 근처 정보 | TAP `naver_blog_api.py`, `nearby_info.py` |

**5000-side에서 tap-blogger에 관여하는 유일한 접점:** `dispatcher.py:_run_tap_subprocess()` — subprocess 격리 실행 + 결과 dict 정규화. 본문 내용에는 관여하지 않음.

---

## Layout Flow Analysis

### tap-blogger 전체 흐름

```
5000 dispatcher.py
  └─ pipeline: "tap" → _run_tap_subprocess(cfg)
       └─ TAP venv python → app.py:run_publish()
            ├─ SourceManager: 소스 선택 (camping/heritage/festival)
            ├─ AIWriter.generate_full_content()
            │    ├─ system_msg (금지 표현, 중립성, anti-meta)
            │    └─ user_prompt (카테고리별 h2/h3 구조 지정)
            ├─ content_processor.process_content()
            │    ├─ insert_images_and_links() — ### → <h3> 변환 + 이미지/주소/지도 버튼
            │    ├─ heritage_card 삽입 (문화유산 테마만)
            │    ├─ inject_cards() — 엔티티 카드 (상/중)
            │    ├─ add_nearby_section() — 근처 맛집/관광지
            │    ├─ add_notice() — 고지문
            │    ├─ add_affiliate_box() — Trip.com (테마 부적합 시 스킵)
            │    ├─ add_schema_markup() — Schema.org JSON-LD
            │    └─ clean_content()
            └─ blogger_publisher.create_post() — Blogger API 발행
```

### 5000 writer.py (Hugo 전용) — tap-blogger 무관

```
shared/coupang_travel.py:CoupangTravel.get_product_cards()
  └─ ## {section_title} (H2) + 상품 그리드 HTML

5000 pipelines/travel/writer.py:_post_process()
  ├─ H2 개수 제한 (4개 초과 시 절단)
  ├─ "함께 읽어보기" 제거
  └─ 쿠팡 여행용품 삽입 (CoupangTravel.get_product_cards()
     → ## 마무리 + 상품 그리드)
```

**결정적 차이:** `_post_process()`의 H2 제한 로직(L699-703)과 쿠팡 삽입(L705-716)은 5000 `dispatcher.py`가 `pipeline: travel` + `platform: hugo`인 블로그를 발행할 때만 호출된다. tap-blogger는 `pipeline: tap`으로 routing되어 `_run_tap_subprocess()`로 분기하므로 **이 코드를 전혀 거치지 않는다.**

---

## H2 Layout in TAP ai_writer.py

TAP의 AI 생성 프롬프트는 **카테고리별로 h2/h3 구조를 명시**한다:

| 카테고리 | h2 구조 (프롬프트 지정) | h2 개수 |
|----------|------------------------|---------|
| camping | ① 고르는 기준, ② 한눈에 비교, ③ 방문 팁, ④ 마무리 | 4개 |
| heritage | ① 보는 포인트, ② 한눈에 비교, ③ 마무리 | 3개 |
| festival | ① ( 축제명 h2 ), ② 마무리 | 2개 (+ 도입부 p) |
| 기타 (korservice) | ① 고르는 기준, ② 한눈에 비교, ③ 방문 팁, ④ FAQ, ⑤ 마무리 | 5개 |

**주의:** korservice(일반 관광지) 카테고리는 h2가 **5개** 생성된다. TAP `content_processor.py`에는 H2 개수 제한 로직이 **없다**. 단, Blogger 플랫폼에서 h2 5개 노출이 문제되는지는 별도 확인이 필요하다.

---

## Coupang Product Card Analysis

### coupang_travel.py (5000-side, tap-blogger 무관)

```
get_product_cards(blog_id, count=3) → str
  ├─ 카테고리별 키워드 검색 (TRAVEL_KEYWORD_MAP)
  ├─ 중복 제거 (productId + 유사도 0.8)
  ├─ ## {section_title} — H2 섹션 제목
  │   (SECTION_TITLES: 블로그별 커스텀 제목)
  └─ <div style="display:flex;flex-wrap:wrap;gap:12px;">
       상품 카드 3개 (인라인 스타일)
       └─ 쿠팡 파트너스 고지문
```

- 이 함수는 5000 `writer.py:_post_process()`에서만 호출된다.
- tap-blogger 발행에는 **전혀 관여하지 않는다**.

### coupang_car.py (5000-side, car-hugo 전용, tap-blogger 무관)

```
get_car_product_links(segment, fuel_type, count=2) → str (markdown)
  ├─ ## 차량 관리에 도움되는 추천 용품 (H2)
  └─ 마크다운 링크 리스트 형태
```

- car-hugo 파이프라인에서 호출된다.
- tap-blogger와는 무관.

### tap-blogger에 쿠팡 상품 카드가 없는 이유

TAP `content_processor.py`에는 쿠팡 파트너스 관련 코드가 **없다**. TAP은 Trip.com 제휴 박스(`add_affiliate_box()`)만 있으며, 이마저도 `캠핑`, `문화유산 탐방`, `축제` 등 테마에서는 삽입되지 않는다 (`AFFILIATE_INAPPROPRIATE_KEYWORDS`).

---

## Blogger Platform Considerations

### tap-blogger의 Blogger 발행 특성

- TAP `blogger_publisher.py`가 Google Blogger API v3로 직접 발행
- 본문은 HTML 형식 (`ai_writer.py`가 `<h3>`, `<p>`, `<strong>` 등 HTML 태그로 생성)
- `content_processor.py:insert_images_and_links()`가 `###` 마크다운 헤딩을 `<h3>` HTML로 변환

### 5000 writer.py의 Blogger 호환성 고려 (참조용)

`coupang_travel.py` L310-313에 Blogger 호환성 관련 주석이 있다:
> "HTML 인라인 스타일 사용 (Blogger markdown parser가 리스트/이미지 크기 제어 못함)"
> "Blogger에서는 인라인 스타일로 동일 레이아웃 구현"
> "섹션 제목은 H2로 출력 (Blogger에서 H2 렌더링)"

**그러나 이는 5000의 Hugo 기반 writer.py 코드 내 주석일 뿐, tap-blogger 실제 발행 흐름과는 무관하다.**

---

## Root Cause Analysis: Why Coupang Section Wasn't H2 in tap-blogger

질문: "쿠평 상품 섹션이 H2로 출력되지 않던 근본 원인"

**답변: 애초에 tap-blogger에는 쿠팡 상품 섹션이 존재하지 않기 때문이다.**

1. 5000 `writer.py:_post_process()`는 tap-blogger 발행 시 **실행되지 않는다**.
2. `_post_process()` 내 `CoupangTravel.get_product_cards()` 호출(L707-716)은 `travel-hugo`, `travel1-hugo` 등 **Hugo 플랫폼 블로그에서만** 동작한다.
3. tap-blogger는 5000 dispatcher에서 `_run_tap_subprocess()`로 분기 → TAP app.py → 자체 파이프라인 → Blogger 발행. 5000의 `writer.py` 코드는 한 줄도 실행되지 않는다.

**따라서 "쿠평 상품 섹션이 H2로 안 나오던 문제"는 tap-blogger에는 해당하지 않는 환상적 문제(phantom issue)다.**

---

## H2 Count Limit Assessment

### 5000 writer.py의 H2 제한 (tap-blogger 무관)

```python
# writer.py L699-703
_h2_positions = [m.start() for m in re.finditer(r"^## ", content, re.MULTILINE)]
if len(_h2_positions) > 4:
    _cut_pos = _h2_positions[4]
    content = content[:_cut_pos].rstrip()
```

- H2가 4개 초과일 때 5번째 H2부터 끝까지 잘라냄
- 이 제한은 **Hugo 블로그 전용**. `_post_process()` 자체가 tap-blogger에서 호출되지 않음.

### tap-blogger의 실제 H2 상황

- TAP `ai_writer.py` 프롬프트가 h2 개수를 결정
- camping: 4개, heritage: 3개, festival: 1~2개, korservice: 5개
- TAP `content_processor.py`에는 H2 개수 제한 로직이 **없음**
- korservice(일반 관광) 카테고리에서 h2 5개 생성될 수 있음 — Blogger에서 5개 h2가 과도하게 느껴진다면, TAP `ai_writer.py` 프롬프트 조정 필요

---

## Related Code Locations

| 파일 | 역할 | tap-blogger 관련성 |
|------|------|-------------------|
| `dispatcher.py:473-493` | `_run_tap_subprocess()` — TAP subprocess 호출 | **5000-side 유일한 접점** |
| `dispatcher.py:457-461` | `_resolve_pipeline()` — pipeline: tap 분기 | routing만 담당 |
| `pipelines/travel/writer.py` | 5000 travel 파이프라인 본문 생성 + `_post_process()` | **tap-blogger와 무관** (Hugo 전용) |
| `shared/coupang_travel.py` | 쿠팡 여행용품 카드 HTML 생성 | **tap-blogger와 무관** (5000 `_post_process()`에서만 호출) |
| `shared/coupang_car.py` | 쿠팡 차량용품 카드 markdown 생성 | **tap-blogger와 무관** (car-hugo 전용) |
| `config/prompts/travel.yaml` | 5000 travel 프롬프트 맵핑 | **tap-blogger와 무관** |
| `TAP/app.py:601-655` | `run_publish()` — TAP 전체 파이프라인 | **tap-blogger 핵심** |
| `TAP/core/ai_writer.py:61-424` | `generate_full_content()` — AI 본문 생성 | **tap-blogger 본문 결정** |
| `TAP/core/ai_writer.py:200-233` | camping 프롬프트 (h2 구조 정의) | tap-blogger camping 글 |
| `TAP/core/ai_writer.py:268-320` | heritage 프롬프트 (h2 구조 정의) | tap-blogger heritage 글 |
| `TAP/core/ai_writer.py:323-372` | korservice 프롬프트 (h2 구조 정의) | tap-blogger 일반 관광 글 |
| `TAP/core/content_processor.py:384-481` | `process_content()` — 후처리 메인 | **tap-blogger 후처리** |
| `TAP/core/content_processor.py:185-259` | `insert_images_and_links()` — 이미지/지도 버튼 | tap-blogger 본문 구성 |
| `TAP/core/tap_entity_manager.py` | 엔티티 카드 (6개 블로그 교차 링크) | tap-blogger 교차 링크 |

---

## Additional Considerations

### 1. tap-blogger 레이아웃 개선 방향 (Phase 68 실질 범위)

5000의 `writer.py`나 `coupang_travel.py`는 tap-blogger에 영향을 주지 않으므로, 실질적인 레이아웃 개선은 **TAP 프로젝트 내부**에서 이루어져야 한다:

- **H2 구조 조정:** `TAP/core/ai_writer.py` 프롬프트의 `[STRUCTURE]` 섹션 수정
- **본문 스타일 보강:** `TAP/core/content_processor.py`의 `insert_images_and_links()` 또는 신규 후처리 함수 추가
- **쿠팡 상품 삽입 (희망 시):** TAP `content_processor.py`에 `CoupangTravel` 연동 추가 — 단, 이 경우 5000-shared 모듈을 TAP에서 import하는 구조 필요

### 2. 이중 스케줄링 위험 (참고)

보고서에 따르면 5000 scheduler(`com.5000.scheduler`)와 TAP scheduler(`com.tap.scheduler`)가 모두 `tap-blogger`를 스케줄할 수 있어 **이중 발행 위험**이 있다. 레이아웃 개선 작업 전 현재 스케줄 상태를 확인하는 것이 좋다.

### 3. Blogger HTML 렌더링 특이사항

TAP `ai_writer.py`는 본문을 HTML로 생성하고, `content_processor.py`가 `###` → `<h3>` 변환을 수행한다. Blogger에서 `<h2>`, `<h3>` 태그는 정상 렌더링되지만, Blogger 에디터의 자체 스타일링과 충돌할 수 있다. 인라인 스타일로 충분한 제어가 가능한지는 실제 발행글 확인 필요.

### 4. 프롬프트 변경 시 AI 품질 영향

`ai_writer.py`의 프롬프트에서 h2 개수나 구조를 변경하면 GPT 출력의 질과 일관성에 영향을 준다. 변경 후 최소 수 회 발행 결과를 검증하는 것이 안전하다.

---

## Sources

### Primary (HIGH confidence)
- `dispatcher.py` L460-493 — tap pipeline routing 및 `_run_tap_subprocess` 구현 [CITED: codebase]
- `pipelines/travel/writer.py` L644-718 — `_post_process()` H2 제한·쿠팡 삽입 [CITED: codebase]
- `shared/coupang_travel.py` L259-353 — `get_product_cards()` H2 출력 확인 [CITED: codebase]
- `shared/coupang_car.py` L169-236 — `get_car_product_links()` H2 출력 확인 [CITED: codebase]
- `TAP/app.py` L601-655 — `run_publish()` 전체 흐름 [CITED: codebase]
- `TAP/core/ai_writer.py` L200-372 — 카테고리별 프롬프트 h2 구조 [CITED: codebase]
- `TAP/core/content_processor.py` L384-481 — `process_content()` 후처리 체인 [CITED: codebase]

### Secondary (MEDIUM confidence)
- `config/blogs.d/tap.yaml` L2-15 — tap-blogger 설정 (blogger_blog_id 존재 확인) [CITED: codebase]
- `REPORT_verify.md` — 이중 스케줄링 위험 검증 기록 [CITED: codebase]

### Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | tap-blogger는 5000 `writer.py`를 거치지 않는다 | 전체 | 낮춤 — dispatcher.py L460-461에서 `_run_tap_subprocess()`로 분기하는 코드 경로로 확인됨 |
| A2 | TAP `content_processor.py`에 H2 개수 제한 로직이 없다 | H2 Count Limit Assessment | 낮춤 — 파일 전체(482줄) 읽은 결과 H2 카운터/제한 코드 없음 |
| A3 | tap-blogger에 쿠팡 상품 섹션이 없다 | Root Cause Analysis | 낮춤 — `_post_process()`가 호출되지 않으며, TAP `content_processor.py`에도 쿠팡 관련 코드 없음 |

**If this table is empty:** All claims in this research were verified or cited — no user confirmation needed.

---

## Open Questions

1. **tap-blogger 레이아웃 보완의 구체적 목표**
   - 어떤 부분이 "보완이 필요한 레이아웃"인지 특정되지 않음
   - H2 개수 조정? 쿠팡 상품 삽입? 이미지 배치? 네이버 지도 버튼?
   - **Recommendation:** Phase 68 discuss-step에서 구체적 목표를 명확히 할 것

2. **korservice 카테고리의 h2 5개 문제**
   - TAP `ai_writer.py` 프롬프트상 korservice(일반 관광)는 h2가 5개 생성됨
   - Blogger에서 5개 h2가 과도한지, 실제 발행글 확인이 필요한지
   - **Recommendation:** tap-blogger 최근 발행글 몇 건의 H2 개수를 실제로 확인할 것

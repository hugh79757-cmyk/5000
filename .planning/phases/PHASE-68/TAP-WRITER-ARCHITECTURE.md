# TAP 아키텍처: Writer 분리 구조

> **최종 갱신:** 2026-08-09
> **목적:** TAP 프로젝트 작업 시 Hugo Writer와 Blogger Writer를 혼동하지 않도록 한눈에 파악

---

## 한눈에 보기

```
                      ┌─────────────────────────────────────┐
                      │           TAP 프로젝트               │
                      │    /Users/twinssn/Projects/TAP/     │
                      └─────────────────────────────────────┘
                                 │
                    ┌────────────┴────────────┐
                    │                         │
          ┌─────────────────┐       ┌─────────────────┐
          │  Blogger Writer  │       │   Hugo Writer    │
          │  (5000 외주)     │       │   (5000 내장)    │
          └─────────────────┘       └─────────────────┘
                    │                         │
                    ▼                         ▼
              tap-blogger            travel-hugo 등
              travel.rotcha.kr       (5개 Hugo 블로그)
              (Blogger 플랫폼)       (Cloudflare Pages)
```

---

## 두 Writer의 정체성

| 구분 | **Blogger Writer** | **Hugo Writer** |
|------|-------------------|-----------------|
| **정체** | TAP 프로젝트 자체 파이프라인 | 5000 중앙 파이프라인 |
| **코드 위치** | `TAP/core/ai_writer.py`<br>`TAP/core/content_processor.py`<br>`TAP/core/tap_entity_manager.py` | `5000/pipelines/travel/writer.py`<br>`5000/shared/coupang_travel.py` |
| **호출 방식** | 5000 dispatcher → `_run_tap_subprocess()` → TAP venv python → `app.py:run_publish()` | 5000 dispatcher → `pipelines.travel.pipeline.run(cfg)` 직접 호출 |
| **대상 블로그** | `tap-blogger` (travel.rotcha.kr) | `travel-hugo`, `travel1-hugo`, `travel2-hugo`, `travel3-hugo`, `travel4-hugo` |
| **플랫폼** | Google Blogger (API v3) | Hugo 정적 사이트 + Cloudflare Pages |

---

## Blogger Writer (TAP/core/)

**특징:**
- AI 본문 생성: `ai_writer.py:generate_full_content()` — GPT-4.1-mini 호출
- 프롬프트에 H2/H3 구조 명시됨 (카테고리별 다름)
- 본문 후처리: `content_processor.py:process_content()` 체인
- 네이버 지도 버튼: `insert_images_and_links()`에서 `###` → `<h3>` 변환 + 버튼 삽입
- Nearby: `add_nearby_section()`에서 카드 + 버튼 생성
- 엔티티 카드: `tap_entity_manager.py`에서 6개 블로그 교차 링크
- 쿠팡: **없음** (Trip.com 제휴 박스만 있음, 여행 테마에서는 스킵)

**H2 구조 (프롬프트 지정):**

| 카테고리 | H2 개수 | H2 목록 |
|---------|--------|---------|
| camping | 4개 | 고르는 기준, 한눈에 비교, 방문 팁, 마무리 |
| heritage | 3개 | 보는 포인트, 한눈에 비교, 마무리 |
| festival | 2개 | (축제명), 마무리 |
| korservice | 5개 | 고르는 기준, 한눈에 비교, 방문 팁, FAQ, 마무리 |

---

## Hugo Writer (5000/pipelines/travel/)

**특징:**
- 본문 생성 + 후처리: `writer.py:_post_process()`에서 일괄 처리
- H2 개수 제한: 최대 4개 (초과 시 마지막 H2 섹션 제거)
- 네이버 지도 버튼: `_inject_naver_map()` — 본문 H3 끝 버튼
- Nearby: `_enrich_with_nearby()` / `_enrich_with_nearby_restaurants_only()`
- 쿠팡 상품: `coupang_travel.py:get_product_cards()` — `## 여행 준비에 도움되는 추천 용품` H2 섹션
- 엔티티 카드: 5000 `cuap_entity_linker.py` (CUAP 전용, 여행 파이프라인에서는 미사용 가능성)
- 발행: Hugo 빌드 → Cloudflare Pages 배포

**후처리 체인 (`_post_process`):**
```
1. "함께 읽어보기" 섹션 제거
2. H2 개수 제한 (4개 초과 시 절단)
3. 쿠팡 여행용품 삽입 (CoupangTravel.get_product_cards())
   → ## 마무리 H2 + 상품 그리드
4. 반환
```

---

## 네이버 지도 버튼: 두 Writer의 처리 방식

### Blogger Writer (TAP)
```
ai_writer.py (GPT 생성, HTML)
  → content_processor.py:insert_images_and_links()
    → ### 헤딩 → <h3> 변환
    → 각 H3 끝에 네이버 지도 버튼 삽입 (<a href="map.naver.com/...">)
    → 버튼 스타일: 인라인 style 속성으로 제어
```

### Hugo Writer (5000)
```
writer.py 본문 생성 (markdown)
  → _inject_naver_map(body_md, items)
    → ### 헤딩 찾기
    → 각 H3 본문 끝에 네이버 지도 버튼 HTML 삽입
    → wrapper div로 text-align:center + margin 제어
  → _enrich_with_nearby() / _enrich_with_nearby_restaurants_only()
    → nearby 카드 생성 (별도 버튼 포함)
```

---

## 쿠팡 상품 섹션: 두 Writer의 차이

| 구분 | Blogger Writer (TAP) | Hugo Writer (5000) |
|------|---------------------|-------------------|
| **존재 여부** | 없음 | 있음 |
| **코드** | — | `shared/coupang_travel.py` |
| **섹션 제목** | — | `## 여행 준비에 도움되는 추천 용품` (블로그별 커스텀) |
| **출력 형태** | — | HTML 인라인 스타일 (flexbox 그리드) |
| **제휴** | Trip.com (테마 부적합 시 스킵) | 쿠팡 파트너스 |

---

## 자주 하는 실수 (함정)

| 실수 | 올바른 이해 |
|------|------------|
| tap-blogger 레이아웃 고치려고 5000 writer.py 수정 | **안 됨.** tap-blogger는 TAP/code/ 코드 사용 |
| travel-hugo 쿠팡 섹션 고치려고 TAP ai_writer.py 수정 | **안 됨.** travel-hugo는 5000/pipelines/travel/writer.py 사용 |
| 두 Writer의 네이버 지도 버튼이 같은 코드라고 생각 | **별개.** Blogger는 `content_processor.py`, Hugo는 `writer.py:_inject_naver_map()` |
| TAP에 쿠팡 상품 넣으려면 ai_writer.py 수정 | **아님.** content_processor.py에 CoupangTravel 연동 추가해야 함 (5000-shared import) |

---

## 파일 위치 요약

```
TAP 프로젝트 (/Users/twinssn/Projects/TAP/)
├── app.py                    # run_publish() — 전체 파이프라인 진입점
├── core/
│   ├── ai_writer.py          # ★ Blogger Writer: AI 본문 생성 + 프롬프트
│   ├── content_processor.py  # ★ Blogger Writer: 본문 후처리 (이미지, 지도, nearby)
│   ├── tap_entity_manager.py # 엔티티 카드 (6개 블로그 교차 링크)
│   ├── blogger_publisher.py  # Blogger API v3 발행
│   └── ...

5000 프로젝트 (/Users/twinssn/Projects/5000/)
├── pipelines/travel/
│   ├── writer.py             # ★ Hugo Writer: 본문 생성 + 후처리
│   ├── pipeline.py           # run(cfg) — 파이프라인 진입점
│   └── fetcher.py            # 데이터 수집
├── shared/
│   ├── coupang_travel.py     # ★ 쿠팡 상품 카드 (Hugo 전용)
│   └── ...
```

---

## 관련 문서

- TAP body layout spec: `.config/opencode/skills/tap-blog-spec/SKILL.md`
- PHASE-68 PLAN: `.planning/phases/PHASE-68/20-PPM-6-tap-blogger-body-layout.PLAN.md`
- PHASE-68 RESEARCH: `.planning/phases/PHASE-68/68-RESEARCH.md`
- dispatcher.py routing: `5000/dispatcher.py` L460-461 (`pipeline: tap` → `_run_tap_subprocess`)

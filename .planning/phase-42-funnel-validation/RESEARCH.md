# Phase 42 RESEARCH — 퍼널(funnel) 설계 검증 (5개 블로그 연결)

> 조사일: 2026-07-24 | 대상: tap.yaml 5개 Hugo 블로그 + 1 Blogger

---

## 1. 크로스링크 3종 아키텍처

### 1.1 "함께 읽어보기" — Hugo `{{< article link="">}}` shortcode

**소스:** `pipelines/travel/writer.py` L1105-1123

```python
# 동적 내부링크 삽입 — 같은 블로그 내에서만
_blog_path_final = {
    "travel-hugo": "/Users/twinssn/Projects/TAP/travel-hugo",
    "travel1-hugo": "/Users/twinssn/Projects/TAP/travel1-hugo",
    "travel2-hugo": "/Users/twinssn/Projects/TAP/travel2-hugo",
    "travel3-hugo": "/Users/twinssn/Projects/TAP/travel3-hugo",
    "travel4-hugo": "/Users/twinssn/Projects/TAP/travel4-hugo",
}
_posts_dir_final = os.path.join(_blog_path_final[blog_id], "content", "posts")
```

- **같은 블로그 내에서만** 3개 랜덤 포스트 선택
- Hugo `{{< article link="/posts/{slug}/" >}}` shortcode 사용
- `themes/blowfish/layouts/shortcodes/article.html` 존재 → 정상 렌더링
- **크로스-블로그 연결 아님** (5개 블로그 순환 X)

**렌더링 방식:** Markdown 내 shortcode → Hugo Goldmark가 HTML로 변환
**raw 노출 위험:** 없음 (shortcode 등록됨)

### 1.2 nearby-card — raw HTML `<div class="nearby-card">`

**소스:** `pipelines/travel/writer.py` L515-580 (`_enrich_with_nearby`)

- TourAPI(한국관광공사) 지리적 주변 장소 검색
- `div.nearby-card` HTML을 body_md 끝에 추가
- Hugo Goldmark는 raw HTML을 통과시킴
- **블로그 간 연결이 아님** — 지리적 추천

**렌더링 방식:** Raw HTML이 Hugo 빌드 시 통과
**raw 노출 위험:** 없음 (HTML 태그, Hugo가 통과)

### 1.3 Funnel cards — `div.funnel-card` (크로스-블로그 연결)

**소스:** `shared/publishers/hugo_writer.py` L716-773 (`_build_funnel_cards_md`)

```python
def _build_funnel_cards_md(blog_cfg, body_md):
    depth_next = blog_cfg.get("depth_next") or []  # 같은 카테고리 다음 단계
    bridge_to = blog_cfg.get("bridge_to") or []     # 다른 카테고리 연결
```

- `depth_next`: 같은 주제의 다음 단계 블로그로 연결 (관심 심화)
- `bridge_to`: 다른 주제의 블로그로 연결 (주제 확장)
- `_resolve_funnel_card_post()`: content_store DB에서 최근 발행 글 조회
- 카드 HTML을 body_md 중간(50% 지점)과 끝에 삽입
- Hugo Goldmark로 raw HTML 통과

---

## 2. 블로그 간 연결 규칙 (tap.yaml)

### 도메인-블로그 매핑

| blog_id | 도메인 | Hugo 프로젝트 경로 |
|---------|--------|-------------------|
| travel-hugo | tour1.rotcha.kr | .../TAP/travel-hugo |
| travel1-hugo | travel1.rotcha.kr | .../TAP/travel1-hugo |
| travel2-hugo | travel2.rotcha.kr | .../TAP/travel2-hugo |
| travel3-hugo | tour2.rotcha.kr | .../TAP/travel3-hugo |
| travel4-hugo | tour3.rotcha.kr | .../TAP/travel4-hugo |
| tvshow-blogger | tv-show.informationhot.kr | Blogger |
| ud-blogger | ud.informationhot.kr | Blogger |

### 현재 퍼널 설정

| blog_id | funnel_stage | depth_next | bridge_to |
|---------|-------------|------------|-----------|
| travel-hugo (캠핑) | landing | → travel4-hugo | 없음 |
| travel1-hugo (축제) | landing | → travel4-hugo | 없음 |
| travel2-hugo (문화유산) | landing | → travel4-hugo | 없음 |
| travel3-hugo (맛집) | landing | → travel4-hugo | 없음 |
| travel4-hugo (코스) | bridge | 없음 | 없음 |

### 현재 연결 구조 그래프

```
travel-hugo (캠핑)     ─┐
travel1-hugo (축제)    ─┤
travel2-hugo (문화유산) ─┤→ travel4-hugo (코스)
travel3-hugo (맛집)    ─┘
```

**문제점:**
1. 모든 depth_next가 travel4-hugo 단방향 — **역방향 없음**
2. 4개 landing 블로그 간 **상호 연결 없음** (캠핑→맛집, 축제→코스 등)
3. travel4-hugo는 funnel_stage=bridge지만 bridge_to 미설정
4. 등록된 bridge_to가 하나도 없음

---

## 3. dry-run 크로스링크 실측 (Phase 41 산출물 재사용)

Phase 41 dry-run 본문 말미 확인:

```
## 함께 읽어보기

{{< article link="/posts/경상남도-캠핑-산청-지리산반달캠핑장부터-산청지막계곡캠핑장까지-2곳-정리/" >}}

{{< article link="/posts/..." >}}
{{< article link="/posts/..." >}}
```

- `{{< article link="">}}`: Hugo shortcode — 정상 렌더링 예상
- `div.nearby-card`: raw HTML — 정상 렌더링 예상
- **Shortcode/HTML raw 노출 확인되지 않음**

---

## 4. 링크 유효성: 포스트 선택 기준

| 메커니즘 | 선택 기준 | 소스 |
|----------|----------|------|
| 함께 읽어보기 | 같은 블로그 내 3개 랜덤 포스트 | `glob.glob(content/posts/*/index.md)` |
| nearby-card | TourAPI 지리적 검색 (반경 5~10km) | `core.content_processor.get_nearby_info()` |
| funnel cards | content_store DB `published_url` 최신 1건 | `_resolve_funnel_card_post()` |

**funnel card 유효성 조건:**
- target blog_id의 최근 발행 글이 있어야 함
- published_url IS NOT NULL
- source_keywords와 target_keywords 일정 수준 overlap 필요 (bridge_to only)
- 없으면 카드 생성 안 됨 (조용히 스킵)

---

## 5. RAW 노출 결함 이력

Phase 21에서 발견된 "크로스링크 raw 노출" 결함:
- `_post_process`에서 GPT 생성 "## 함께 읽어보기" 섹션을 선제 제거
- `_enrich_with_nearby` 후 다시 한번 "## 함께 읽어보기" 검사 및 제거
- 이후 동적 내부링크(`{{< article >}}`) 삽입
- 현재 dry-run에서 raw 텍스트 노출 확인되지 않음

---

## 6. 주요 발견사항 요약

| # | 발견 | 영향 | 조치 필요 |
|---|------|------|-----------|
| 1 | "함께 읽어보기"는 같은 블로그 내에서만 링크 | 5개 블로그 순환 안 됨 | 기획 이슈 (버그 아님) |
| 2 | funnel cards는 단방향(→ travel4-hugo)만 설정 | 역방향/상호 연결 없음 | 기획 이슈 (버그 아님) |
| 3 | bridge_to가 전혀 설정되지 않음 | funnel card 부족 | 기획 결정 필요 |
| 4 | shortcode/HTML raw 노출 없음 | 정상 렌더링 | 수정 불요 |
| 5 | entity_linker는 영문 블로그 전용 | 국문 블로그 미적용 | 의도된 설계 |

# Phase 12: Content Enrichment & Dwell Time Optimization — RESEARCH

## Research Question
How can we increase content length (+50%) and dwell time (+30%) for TAP travel blog posts by leveraging unused API fields and adding new content sections?

## Current State Analysis

### API Data Sources & Utilization

| API | Total Fields | Used Fields | Utilization |
|-----|-------------|-------------|-------------|
| Camping API | ~30 | ~18 | 60% |
| TourAPI | ~15 | ~7 | 47% |
| Durunubi | ~12 | ~6 | 50% |
| Blog Review | ~8 | ~5 | 63% |

### Current Content Structure (Camping)

```
[도입부] 5~7문장 ≈ 150~200자
[고르는 기준] 4~5문장 ≈ 120~150자
[각 캠핑장] 6~8문장 × 6곳 = 36~48문장 ≈ 1,200~1,800자
[한눈에 비교] 표 ≈ 200~300자
[마무리] 5~6문장 ≈ 150~200자

총 예상: 1,800~2,650자 (약 1.5~2페이지)
```

### Current AI Configuration

- Model: gpt-4.1-mini (configurable via OPENAI_MODEL env)
- max_tokens: 5000
- temperature: 0.7
- System prompt: Revenue-focused Korean travel blog editor

## Unused API Fields Analysis

### Camping API — High-Value Unused Fields

| Field | Description | Content Impact |
|-------|-------------|----------------|
| `operPdCl` | 운영기간 (4월~10월) | ★★★★★ 계절 정보 |
| `exprnProgrm` | 체험프로그램 (양념장 체험 등) | ★★★★★ 세부 활동 |
| `siteBottomCl1/2` | 바닥종류 (잔디/데크/자갈) | ★★★★☆ 캠핑장 특성 |
| `eqpmnLendCl` | 장비대여 가능 여부 | ★★★★☆ 편의 정보 |
| `gnrlSiteCo`, `autoSiteCo` 등 | 사이트 수 | ★★★☆☆ 규모 정보 |
| `themaEnvrnCl` | 테마환경 | ★★★☆☆ 분위기 정보 |
| `lctCl` | 입지구분 (산/해변/계곡) | ★★★★☆ 위치 특성 |
| `induty` | 업종 | ★★☆☆☆ 분류 정보 |

### TourAPI — High-Value Unused Fields

| Field | Description | Content Impact |
|-------|-------------|----------------|
| `overview` | 개요 (detailCommon2) | ★★★★★ 상세 설명 |
| `homepage` | 홈페이지 | ★★★☆☆ 예약 링크 |
| `cat1/2/3` | 카테고리 | ★★★☆☆ 분류 정보 |
| `sigungucode` | 시군구코드 | ★★☆☆☆ 지역 필터링 |

### Durunubi — High-Value Unused Fields

| Field | Description | Content Impact |
|-------|-------------|----------------|
| `crsDistance` | 거리 (km) | ★★★★★ 코스 정보 |
| `crsTime` | 소요시간 | ★★★★★ 계획 수립 |
| `crsDifficulty` | 난이도 | ★★★★☆ 준비물 안내 |
| `crsLevel` | 난이도 (상/중/하) | ★★★★☆ 난이도 표시 |

## Enhancement Opportunities

### 1. Content Length Increase (+50%)

| Approach | Implementation Difficulty | Expected Increase |
|----------|--------------------------|-------------------|
| API unused field utilization | Low | +30% |
| max_completion_tokens 7000 | Low | +40% |
| Blog review pros/cons section | Medium | +20% |
| Nearby attractions/restaurants section | Medium | +25% |

### 2. Dwell Time Increase (+30%)

| Approach | Implementation Difficulty | Expected Increase |
|----------|--------------------------|-------------------|
| FAQ section (AI-generated) | Medium | +25% |
| Seasonal tips section (using operPdCl) | Low | +15% |
| Linked travel course section | Medium | +30% |
| Comparison table expansion (3-4 → 5-6 items) | Low | +10% |

### 3. SEO & UX Improvements

| Approach | Implementation Difficulty | Expected Impact |
|----------|--------------------------|-----------------|
| Schema.org structured data (TravelAction, Place, FAQPage) | Medium | Search visibility |
| Image gallery expansion (1 → 2-3 per campground) | Low | Visual engagement |
| Naver map embed (vs simple link) | Medium | UX improvement |

## Technical Constraints

1. **AI Model**: gpt-4.1-mini has max context of 1M tokens, max output of 32K tokens
2. **API Rate Limits**: TourAPI has 2-second delay between requests
3. **Hugo Build**: Content must be valid Markdown/HTML
4. **Blowfish Theme**: Supports shortcodes (lead, figure, alert, badge, gallery, accordion, chart)
5. **Ad Integration**: Phase 10-05 added ad markers; new content must not break ad placement

## Recommendations

### Priority 1 (Immediate - 1-2 hours)
1. Expand AI max_completion_tokens to 7000
2. Add unused camping API fields to AI prompt (operPdCl, exprnProgrm, siteBottomCl1)
3. Add new section: "방문 팁" (seasonal tips, preparation items)

### Priority 2 (Short-term - 1-2 days)
1. Add blog review pros/cons section
2. Add nearby attractions/restaurants section (using nearby_info.py data)
3. Expand comparison table (add price, facilities, accessibility, scale)

### Priority 3 (Medium-term - 1 week)
1. Add FAQ section (AI-generated)
2. Add Schema.org structured data
3. Expand image gallery

## Source Files

- `/Users/twinssn/Projects/TAP/core/camping_data.py` — Camping data collection
- `/Users/twinssn/Projects/TAP/core/tour_api.py` — TourAPI client
- `/Users/twinssn/Projects/TAP/core/ai_writer.py` — AI content generation
- `/Users/twinssn/Projects/TAP/core/content_generator.py` — Content pipeline
- `/Users/twinssn/Projects/TAP/core/nearby_info.py` — Nearby attractions/restaurants
- `/Users/twinssn/Projects/TAP/core/blog_info_extractor.py` — Blog review extraction

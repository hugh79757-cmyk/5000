# Phase 12: Content Enrichment & Dwell Time Optimization — CONTEXT

## Phase Goal
Increase travel blog content length by +50% (from ~2,500 to ~3,750 characters) and dwell time by +30% by leveraging unused API fields and adding new content sections.

## Locked Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Primary target | TAP travel blogs (5 Hugo sites) | Highest traffic, most API data available |
| AI model | gpt-4.1-mini (existing) | Cost-effective, sufficient quality |
| max_completion_tokens | 7000 (from 5000) | +40% output capacity |
| New sections | FAQ, seasonal tips, linked courses | Highest dwell time impact |
| API fields to add | operPdCl, exprnProgrm, siteBottomCl1, crsDistance, crsTime | Highest content value |
| Schema.org | TravelAction + FAQPage | SEO improvement without breaking existing layout |
| Image expansion | 1 → 2 per campground (max) | Balance between engagement and API cost |

## Scope Boundaries

### In Scope
1. AI prompt expansion with unused API fields
2. New content sections (FAQ, seasonal tips, linked courses)
3. Blog review pros/cons integration
4. Comparison table expansion
5. Schema.org structured data
6. Image gallery expansion

### Out of Scope
1. New API integrations (only leverage existing APIs)
2. Blowfish theme modifications (use shortcodes only)
3. Ad integration changes (Phase 10-05 remains unchanged)
4. Content deduplication logic (Phase 11 remains unchanged)
5. Multi-language content

## Technical Context

### Current AI Configuration
```python
# ai_writer.py
model = os.getenv('OPENAI_MODEL', 'gpt-4.1-mini')
max_tokens = 5000  # → will become 7000
temperature = 0.7
```

### Current Content Structure
```
[도입부] 5~7문장 ≈ 150~200자
[고르는 기준] 4~5문장 ≈ 120~150자
[각 캠핑장] 6~8문장 × 6곳 ≈ 1,200~1,800자
[한눈에 비교] 표 ≈ 200~300자
[마무리] 5~6문장 ≈ 150~200자
총: 1,800~2,650자
```

### Target Content Structure
```
[도입부] 5~7문장 ≈ 150~200자
[고르는 기준] 4~5문장 ≈ 120~150자
[각 캠핑장] 8~10문장 × 6곳 ≈ 1,800~2,400자  ← +33% per place
[한눈에 비교] 표 (5~6항목) ≈ 300~400자  ← +33%
[방문 팁] 계절별/준비물 ≈ 200~300자  ← NEW
[연계 여행 코스] 주변 관광지 ≈ 200~300자  ← NEW
[FAQ] 자주 묻는 질문 3~5개 ≈ 300~500자  ← NEW
[마무리] 5~6문장 ≈ 150~200자
총: 3,200~4,450자 (+50%)
```

## Verification Strategy

1. **Content Length**: Compare word count before/after (target: +50%)
2. **Dwell Time**: Monitor via Plausible Analytics (target: +30%)
3. **SEO**: Check Google Search Console for impression/click changes
4. **Build**: Hugo build must succeed for all 5 blogs
5. **Ad Integration**: Phase 10-05 ad markers must remain functional

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| AI output quality degrades with longer content | Medium | High | Limit max_completion_tokens to 7000; add quality checks |
| API field data is sparse/incomplete | High | Medium | Graceful fallback; only include if data exists |
| FAQ section feels repetitive | Medium | Low | Generate unique FAQs per post; avoid generic questions |
| Schema.org validation errors | Low | Medium | Test with Google Rich Results Test |
| Hugo build time increases | Low | Low | Monitor build time; optimize if >10s |

## Dependencies

- Phase 10-05 (AdSense) — must not break ad placement
- Phase 11 (Coupang Import Fix) — unrelated, no conflict
- Phase 12 (Body Content Rescan) — CUAP-specific, no conflict

## Success Criteria

| # | Criterion | Measurement |
|---|-----------|-------------|
| SC-01 | Average content length ≥ 3,500 characters | Word count analysis |
| SC-02 | Average dwell time ≥ 3.5 minutes | Plausible Analytics |
| SC-03 | All 5 Hugo blogs build successfully | `hugo --minify` |
| SC-04 | Schema.org validates | Google Rich Results Test |
| SC-05 | Ad markers remain functional | DevTools inspection |
| SC-06 | No increase in AI API cost > 20% | OpenAI dashboard |

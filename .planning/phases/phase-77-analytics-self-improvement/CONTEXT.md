# Phase 77: Analytics 기반 셀프 개선 루프 — CONTEXT (RESEARCH.md 대체)

**Source:** 세션 조사 (2026-09-02~09-03 analytics.db 실측 + 코드 추적)
**Date:** 2026-09-03
**Status:** Final

## 배경 — 왜 이 phase가 존재하는가

사용자 질문: "스스로 조회수와 반응을 기준으로 판단하고 학습한 내용을 반영해서 개선하는 루프 로직이 없어?"

조사 확정: **조회수/반응 기반 학습 루프는 문서에도 코드에도 존재하지 않음.** Phase 64가 계획한 자기개선은 사람 기반(수동 피드백 JSONL, leak 집계)이며, 성과 데이터 기반 자동 학습은 미구현. 다만 데이터 수집 인프라는 6시간 주기로 이미 가동 중 — 부족한 것은 수집된 데이터를 **생성 파이프라인에 주입하는 루프**뿐.

## 조사 확정 사실 (근거 포함)

### 1. 데이터 자산 실측 (analytics.db)

| 테이블 | 행수 | 기간 | 판정 |
|---|---|---|---|
| adsense_daily | 3467 | 03-19~09-01 | 사용 가능 (domain 기준) |
| gsc_keywords | 852 | 07-05~08-30 | 사용 가능 (query별, 소규모) |
| gsc_pages | 2486 | 08-15~08-30 | 사용 가능 (URL별) |
| gsc_daily_summary | 1889 | 03-17~08-30 | 사용 가능 (98 blogs) |
| blog_efficiency | 1363 | 07-08~09-02 | 사용 가능 (61 blogs) |
| ga4_pages | 1519 | **04-03~04-17만** | **불가 — 4개월 전 데이터, 현재 미수집** |
| bing_* | 3935/5311/3029 | — | 보조 참고 |
| cannibalization_tracking | 80 | — | 미사용 |
| indexing_log / sync_log | 0 | — | 미사용 |

- 클릭 있는 쿼리 ~20개 (최대 단일 5클릭) — 신호는 실재하나 규모 작음
- 검증된 수요 키워드 패턴 발견: 자동차 유지비(gr86/m4/마이바흐), 드라이브 코스(대전), 예비군 훈련준비물, 스타일런 2026
- GA4 기반 체류시간/참여 분석 불가 — 현재 미수집 상태

### 2. 기존 인프라 (재사용 기반)

- `shared/analytics_collector.py` — `compute_efficiency()` (1015줄 근처): content.db articles(status='published') 블로그별 포스트수 × gsc_daily_summary 30일 클릭 → `efficiency_score=(clicks+imp*0.01)/posts*100` → grade A~F. **content.db↔GSC 조인 이미 존재**
- `scripts/collect_analytics.sh` — launchd 6시간 주기 수집 (GA4+GSC+AdSense+Efficiency), watchdog 별도 plist, hard timeout 600s
- content.db articles: 1500+행, `published_url` ↔ `gsc_pages.page` 조인 가능 (발행↔성과 매핑)
- publish_log (curation.db 계열): keyword, published_at, blog_id — 키워드 회피제에 사용 중

### 3. 생성 파이프라인 개입 지점 (학습 주입 후보)

- `pipelines/curation/pipeline.py:_select_keyword(blog_id)` (154줄) — 키워드 선택: get_keywords() → 30일 TTL 제외 → 격리 제외 → low_relevance 14일 실패 제외 → 카테고리 14일 중복 억제 → 상품 3개+ relevance gate. **성과 신호 전혀 미사용**
- `pipelines/travel/fetcher.py` — random.choice/sample 기반 장소 선택 (get_weighted_random_sigungu 등). 성과 미반영
- `pipelines/curation/keywords.py:get_keywords()` — pool-first → KEYWORD_MAP fallback (Phase 76 SSOT 이슈 연관)

### 4. Phase 76 연관 (선행 관계)

- keyword_pool DB가 SSOT가 아니라 KEYWORD_MAP(3397줄 하드코딩)이 사실상 SSOT — Phase 76에서 SSOT 전환 설계 완료 (SSOT-DESIGN.md, M1~M6), 실행은 별도 phase 예정
- **학습된 키워드가 주입되는 대상이 SSOT 전환 전후로 달라짐** — Phase 77 설계는 keyword_pool SSOT 전환 이후 상태를 가정하되, 전환 전 fallback 경로도 고려

## 사용자 요구사항 (원문)

1. "스스로 조회수와 반응을 기준으로 판단하고 학습한 내용을 반영해서 개선하는 루프 로직이 없어?"
2. 자기 개선 로직에 대한 설명
3. gsd 문서 확인 — 계획은 있는데 구현 안 됐는지 확인

## 범위 펜스 (in/out)

**In:**
- 성과 데이터 → 키워드 선택 개입 (curation `_select_keyword` 보강)
- 성과 데이터 → 주제 선택 개입 (travel 등 fetcher 보강)
- 학습 결과 저장소 설계 (analytics 신호의 스냅샷/롤백 가능 구조)
- GA4 수집 재개 여부 결정 (선택 사항)

**Out:**
- keyword_pool SSOT 마이그레이션 실행 (Phase 76 별도 phase, 파괴적)
- GA4 재수집 자체는 데이터 수집 인프라 수정 (별도 검토)
- 사이즈가 큰 LLM 프롬프트 개편 (성과 반영은 키워드/주제 선택 레이어에만)

## 핵심 제약

- **데이터 규모 작음**: 클릭 있는 쿼리 ~20개. 노이즈 과적합 방지 — 최소 임계값(예: 클릭≥1) + 신호 부재 시 기존 동작 유지
- **GA4 불가**: 체류시간/참여 기반 학습은 현재 데이터로 불가. GSC 클릭/노출 + AdSense 수익만 사용
- **파이프라인 계속 가동**: launchd 스케줄러가 6시간 주기로 이미 돌고 있음 — 학습 루프는 수집 격리(별도 프로세스/락) 후 적용
- **단일 개발자 + 증분**: 첫 단계는 read-only 관찰(가중치 제안만 출력) → 검증 후 반영 단계로 분리

# EXECUTE_ALL_BLOG_CONTENT_QUALITY_AUDIT — 요약

- 판정: **AUDIT_COMPLETE_WITH_GAPS**
- 블로그: 85개 registry (site_path 81 + Blogger 4)
- 게시글: sitemap 기준 22,685개 발견 / 기계적 검사 24,986개 (81개 블로그 전수)
- 의미 평가: 794개 표본 (블로그당 최신 5 + 랜덤 5, seed 5000) — 미평가분 UNVERIFIED
- 실패: 0건 / 누락: Blogger 4 (로컬 경로 없음), 의미 미평가 21,891개
- 평균 점수: 87.1 (90+ 488 / 80-89 180 / 70-79 113 / 60-69 8 / <60 5)
- 치명적 문제: 230건 (critical_in_sample) — TEMPLATE_LEAK/본문 부족 위주

## 주요 발견
1. **TEMPLATE_LEAK 5,097건 (20.4%)** — senior/travel 계열 집중 (senior-hugo 518, travel3 368, travel2 283, travel4 265, travel 263, travel1 237)
2. **내부 링크 0건 18,542건 (74.2%)** — 플릿 전체 크로스링크 전무 → 디스커버리 부족 원인
3. **본문 중복 263개** (body_md5 동일 그룹 68개) — 통합/noindex 후보 (실행 안 함)
4. **NO_H2 3,667건** — 구조 문제
5. **TOO_SHORT_BODY 1,396건** (SHORT 1,036 + TOO_SHORT 360)
6. **LONG_TITLE 352건** (>60자)

## 동결
- Interior sitemap 실험 FROZEN 20개 URL — 감사만 수행, remediation 금지 (FROZEN_UNTIL_SITEMAP_EXPERIMENT_COMPLETE)

## 우선 개선 후보
- priority_queue.csv (40건) 참조 — template 10 + too_short 8/4 + no_h2 3 + no_link 2 + long_title 1 가중치
- 블로그 수준 우선순위: senior-hugo, travel3-hugo, travel2-hugo, travel4-hugo, travel-hugo, travel1-hugo (TEMPLATE_LEAK 집중)

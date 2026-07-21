# CONTEXT — Phase 29: CUAP 콘텐츠 오염 + 퍼널 카드 404 + 광고 공백 수정

**Last updated:** 2026-07-22
**Author:** Sisyphus (orchestrator)

---

## 1. Objective

CUAP 파이프라인에서 발생한 3가지 문제를 수정:
1. **Pet 블로그에 Beauty 글 발행** — pet-hugo에 홈케어/뷰티 관련 글이 발행됨
2. **퍼널 크로스셀 카드 404** — `cuap_entities` 테이블의 URL이 실제 slug와 불일치
3. **광고 공백** — 중간중간 광고 슬롯이 비어 있음

---

## 2. 문제 상세 분석

### 2-1. Pet 블로그에 Beauty 글 발행

**발견:** `pet-hugo/content/posts/eranstar-vs-로즈온-2026년-7월-홈케어-관리-실속-선택/`
- **제목:** "ERANSTAR vs 로즈온 — 2026년 7월 홈케어 관리 실속 선택"
- **실제 내용:** 마사지기, 괄사, 필링 패드 등 뷰티/홈케어 제품 리뷰
- **tags:** `['뷰티맥스', '이케이', '관리']` — 뷰티 관련 태그
- **원인:** 파이프라인이 pet-hugo 키워드로 생성했으나, 실제 콘텐츠가 뷰티 카테고리에 해당

**근본 원인 가설:**
- `keywords.py`의 `pet-hugo` 키워드 목록에 뷰티/홈케어 관련 키워드가 포함되어 있음
- 또는 `_filter_irrelevant_products()` 필터가 "홈케어 관리"를 pet-hugo와 관련 있다고 판단

### 2-2. 퍼널 크로스셀 카드 404

**발견:** `cuap_entities` 테이블(travel-en.db)에 잘못된 URL 저장

**오염된 URL 패턴:**
```
blog_id: appliance-hugo
entity_name: 여름철 제습기 추천
post_url: https://appliance.informationhot.kr/posts/20260721-여름철-제습기-추천/
→ 실제 slug: 여름철-제습기-추천-21센추리-산업용-제습기와-hululu-미니 (존재 안 함)
```

**영향받는 블로그:**
| 블로그 | 오염 URL 예시 | 실제 slug 존재 여부 |
|--------|---------------|---------------------|
| appliance-hugo | `20260721-여름철-제습기-추천/` | ❌ 존재 안 함 |
| baby-hugo | `20260721-아기-카시트-추천/` | ❌ 존재 안 함 |
| beauty-hugo | `20260721-향수-추천/` | ❌ 존재 안 함 |
| camping-hugo | `20260721-캠핑-용품-수납-추천/` | ❌ 존재 안 함 |
| fitness-hugo | `20260721-스파인코렉터-추천/` | ❌ 존재 안 함 |
| health-hugo | `20260721-면역력-강화-영양제/` | ❌ 존재 안 함 |
| interior-hugo | `20260721-가성비/` | ❌ 존재 안 함 |
| kitchen-hugo | `20260721-핸드블렌더-추천/` | ❌ 존재 안 함 |
| laptop-hugo | `20260721-레노버-노트북-추천/` | ❌ 존재 안 함 |
| pet-hugo | `20260721-고양이쿨매트/` | ❌ 존재 안 함 |

**근본 원인:** Phase 25에서 `register_cuap_entity()`를 호출할 때, 테스트 데이터(가상의 slug)가 DB에 저장됨. 실제 발행 slug와 불일치.

### 2-3. 광고 공백

**현재 상태:** beauty-hugo 포스트들이 라이브에서 404 반환
- `https://beauty.informationhot.kr/posts/2026년-7월-블러셔-추천-3ce에뛰드-합격점-top-5/` → 404
- `https://beauty.informationhot.kr/posts/2026년-7월-캘빈클라인-씨케이-비-블루-옴므-실속-선택이-가능한-향수-추천-5가지/` → 404

**원인:** beauty-hugo가 아직 배포되지 않음 (로컬에만 존재)
- 광고 스크립트는 페이지에 포함되어 있으나, 페이지 자체가 404이므로 광고가 로드되지 않음
- 또한 `layouts/partials/adsense/` 파일 확인 필요 (in-article, leaderboard 등)

---

## 3. 제약 조건

- **배포는 반드시 `deploy_site()` 경유** (AGENTS.md)
- **Worker 블로그:** `wrangler deploy --config wrangler.toml`
- **Pages 블로그:** `wrangler pages deploy public --project-name={blog_id}`
- **CLOUDFLARE_API_TOKEN env var 제거** 후 OAuth profile 사용
- **AdSense:** CUAP = `ca-pub-6677996696534146` (informationhot.kr)

---

## 4. 범위

### IN
1. `keywords.py`에서 pet-hugo 키워드 검증 (뷰티 키워드 제거)
2. `cuap_entities` 테이블 URL 정리 (잘못된 URL 삭제 또는 실제 slug로 업데이트)
3. beauty-hugo 재배포 (404 해결)
4. 광고 partial 파일 검증 (in-article, leaderboard, lazy-load)

### OUT
- 기존 발행된 글 수정 (다음 발행분부터 적용)
- AdSense Publisher ID 변경 (이미 `ca-pub-6677996696534146`로 정상 설정)

---

## 5. 검증 방법

1. **Pet 키워드 검증:** `keywords.py`에서 `pet-hugo` 키워드 목록에 뷰티/홈케어 키워드 없는지 확인
2. **DB URL 검증:** `cuap_entities` 테이블에서 각 URL이 실제 파일시스템 slug와 일치하는지 확인
3. **라이브 검증:** 6개 Worker 블로그 + beauty-hugo에서 실제 포스트 200, missing 404 확인
4. **광고 검증:** 브라우저 개발자 도구로 `adsbygoogle` 요소 로드 확인

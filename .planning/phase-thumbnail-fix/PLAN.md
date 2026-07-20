# Phase: Thumbnail & Image Strategy — 통합 개선

**Status:** Research Complete — Plan Ready for Approval
**Scope:** cover-image fix + STAP/RAP/SEAP 신규 썸네일 방식
**TAP/CAP:** 제외 (현행 유지)
**Priority:** HIGH

---

## Part A — phase-thumbnail-fix: Cover Image 경로 수정

### 현재 상태 분석

| Task | 내용 | 상태 |
|------|------|------|
| Task 01 | `single.html` → PaperMod `cover.html` partial 사용 | ❌ 미완료 (informationhot-hugo/layouts/_default/single.html 확인 필요) |
| Task 02 | `cover.relative: true` 자동 추가 | ✅ **이미 완료** — `shared/publishers/hugo_writer.py` 3개 frontmatter builder 모두 `relative: true` 포함 |
| Task 03 | `_redirects` 간섭 확인 | ❌ 확인 필요 |

Task 02는 `shared/publishers/hugo_writer.py`의 `_build_frontmatter_papermod()`, `_build_frontmatter_blowfish()`, `_build_frontmatter_congo()`에 각각 `relative: true`가 이미 존재함. `shared/publisher.py:782`의 re-import로 인해 새 버전이 활성화됨.

### 남은 작업
1. informationhot-hugo `single.html` 확인 — PaperMod `cover.html` partial을 사용하는지
2. `_redirects`에서 이미지 경로 리디렉트 확인

---

## Part B — STAP/RAP/SEAP 신규 썸네일 방식

### 기존 방식 (비활성화 대상)

3개 파이프라인이 현재 동일한 `generate_thumbnail()` 사용:
- **STAP stock**: `pipelines/stock/pipeline.py:296` `_make_thumbnail()` → `generate_thumbnail(site_id="stock")`
- **RAP**: `pipelines/rap/pipeline.py:966` → `generate_thumbnail(site_id="rap")`
- **SEAP senior**: `pipelines/senior/pipeline.py:53` `_make_thumbnail()` → `generate_thumbnail(site_id="senior")`

공통: Playwright HTML/CSS → 600x600 정사각형 → WebP → R2 업로드
- 텍스트 기반 (title 2줄 분할 + category badge)
- 블로그별 색상 팔레트 사용 (stock/rap/senior는 colors.py에 등록됨)

### 신규 방식 제안

`shared/thumbnail_generator`는 유지하되, **template 다양화**와 **인터넷 이미지 활용**:

**Option 1 — 템플릿 업그레이드 (현재 인프라 활용)**
- `default.html` 외에 분기별 템플릿 추가 (`stock.html`, `rap.html`, `senior.html`)
- 각 분기 특성에 맞는 디자인: stock=차트/데이터 느낌, rap=아파트/건물, senior=부드러운 톤
- 여전히 텍스트 기반, 하드코딩된 CSS

**Option 2 — Unsplash 배경 이미지 활용 (추천)**
- 기존 `generate_thumbnail()` 구조 유지
- `image_fetcher.py` Unsplash 검색 로직 재사용
- 카테고리 키워드로 Unsplash 검색 → 배경 이미지 설정
- title 텍스트를 이미지 위에 오버레이
- **장점**: 시각적 품질 대폭 향상, 각 포스트의 주제와 관련된 이미지

**Option 3 — 하이브리드 (템플릿 + Unsplash fallback)**
- 기본: Option 2 (Unsplash)
- Unsplash 실패 시: Option 1 (분기별 템플릿 fallback)
- API 키 없거나 rate limit 시에도 항상 썸네일 생성 보장

### 비활성화 방법

기존 `generate_thumbnail()` 호출을 신규 방식 함수 호출로 대체:

**stock pipeline (STAP)**: `_make_thumbnail()` 내부 교체
**rap pipeline**: `generate_thumbnail()` 호출 → `_make_new_thumbnail()` 호출로 교체
**senior pipeline**: `_make_thumbnail()` 내부 교체

### STAP 5개 비-stock 블로그 (dividend, etf, sector, ipo, finance)
- 이들은 **STAP subprocess**로 실행됨 (`dispatcher.py:_run_stap()`)
- 별도의 `pipeline.py`가 없음 (STAP 프로젝트 내부)
- 이 블로그들의 썸네일은 **별도 계획** 필요 — 5000에서 직접 제어 불가
- **제안**: 이번 스코프에서 제외

### RAP/SEAP 블로그 설정
- **RAP**: 4개 블로그 (rap-hugo, rap2~rap4) — 모두 동일 `pipeline.py` 사용
- **SEAP**: senior-hugo — 단일 블로그
- 두 분기 모두 5000 내부 파이프라인이므로 직접 제어 가능

### colors.py 확장

신규 방식 적용 전, 아래 블로그 팔레트 추가 필요:
- STAP: dividend, etf, sector, ipo, finance, stock (stock만 등록됨, 나머지 5개 없음)
- RAP: rap (등록됨)
- SEAP: senior (등록됨)
- RAP 각 category용 accent (rap2~rap4)

---

## Part C — 본문 이미지 Unsplash 삽입 현황

### 현재 상태

`pipelines/etap/image_fetcher.py`에 Unsplash 검색 로직 존재:
```python
UNSPLASH_ACCESS_KEY (env) → _search_unsplash(query) → 
  url, thumb, credit, photographer, download_location
```

**단, ETAP 전용** — STAP/RAP/SEAP/CUAP/TAP/CAP에서는 사용하지 않음.

### 문제점

| 항목 | 상태 |
|------|------|
| API 키 필요 | `UNSPLASH_ACCESS_KEY` 환경변수 — `.env.common`에 있는지 확인 필요 |
| Rate limit | Free tier: 50 req/hour — STAP/RAP/SEAP 3개 분기에서만 사용 시 충분 |
| Download tracking | `_trigger_unsplash_download()`로 API 정책 준수 — 구현됨 |
| R2 캐싱 | ETAP은 R2에 업로드 후 사용 (`_upload_to_r2()`) — 중복 다운로드 방지 |
| 저작권 표시 | Photo by [photographer] on Unsplash — ETAP에 구현됨 |
| 검색 쿼리 | 카테고리/키워드 기반 — 신규 방식에서도 동일 로직 재사용 가능 |

### 1~2장 본문 이미지 Unsplash 삽입
- 기술적으로 문제 없음 (ETAP에서 이미 사용 중)
- rate limit 고려: STAP/RAP/SEAP 합계 약 15~20 posts/day → 15~40 Unsplash 요청 → 50/h 제한 이내
- 이미지 R2 캐싱으로 중복 요청 방지 필요

---

## Part D — 차트 생성 현황

### 현재 차트 생성 코드

`shared/publishers/hugo_writer.py:472` `_apply_chart_shortcode()`:
- `<!-- CHART: [{...}, {...}] -->` shortcode → Chart.js `<canvas>` HTML 변환
- **travel pipeline**만 사용 (`pipelines/travel/pipeline.py:315`)
- 막대 차트 형태 (camping site counts 비교)
- STAP(주식/금융)에서는 **차트 생성 안 함**

### STAP 차트 도입 검토
- STAP stock pipeline: 재무 데이터 기반으로 Chart.js 차트 생성 가능
- `_apply_chart_shortcode()`는 이미 구현되어 있음
- 필요한 것: stock pipeline에서 `<!-- CHART: ... -->` shortcode를 body_md에 삽입하는 로직
- **제안**: 이번 스코프에서 제외 (별도 phase)

---

## Part E — 실행 계획

### Wave 1: Cover Image Fix
- informationhot-hugo `single.html` → PaperMod `cover.html` partial 확인/수정
- `_redirects` 이미지 경로 리디렉트 확인
- 적용 사이트: informationhot-hugo (1차), 다른 Hugo 사이트로 확산

### Wave 2: colors.py 확장
- STAP 5개 블로그 팔레트 추가 (dividend, etf, sector, ipo, finance)
- RAP category별 accent 추가 확인

### Wave 3: STAP/RAP/SEAP 신규 썸네일 방식 적용
- **Option 1 or 2 or 3 선택 필요**
- 기존 `generate_thumbnail()` 호출을 신규 방식으로 교체
- stock/rap/senior pipeline 내 thumbnail 함수 교체

### Wave 4: 본문 Unsplash 이미지 삽입 (선택)
- STAP/RAP/SEAP에 1~2장 Unsplash 이미지 body_md 자동 삽입
- `image_fetcher.py` 로직 재사용 또는 통합

### Wave 5: 검증
- R2 URL 정상 확인
- 커버 이미지 경로 정상 확인
- Unsplash rate limit 초과 없음 확인

---

## 의사 결정 필요 항목

1. **신규 썸네일 방식**: Option 1 (템플릿) / Option 2 (Unsplash 배경) / Option 3 (하이브리드)?
2. **STAP 5개 비-stock 블로그**: 이번 스코프 포함 또는 제외?
3. **차트 생성**: Phase 22-c 완료 후 별도 phase로 진행?
4. **본문 Unsplash 이미지**: 이번 스코프에 포함?
5. **TAP/CAP**: 현행 유지 확인

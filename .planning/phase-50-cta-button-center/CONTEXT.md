# Phase 50: CTA 버튼 중앙 정렬 + 포스트 가독성 개선

## 배경
10개 CUAP 블로그의 모든 포스트에서 CTA(쿠팡 링크) 버튼을 시각적으로 눈에 띄게,
중앙 정렬로 개선하고, 크로스링크 섹션의 CSS를 표준화한다.

---

## 현재 상태 (2026-07-26 코드베이스 분석 결과)

### 상태 1: CTA 버튼 CSS는 존재하지만 적용되지 않음

**CSS (custom.css):** ✅ 존재 — 10개 CUAP 블로그 전부 `btn-price-check` 클래스 정의되어 있음
- `display: inline-block; padding: 0.625rem 1.25rem; background: #ea580c; color: #fff; border-radius: 0.5rem;`
- hover/active/dark mode 변형 모두 존재
- 단, `text-align: center`나 `margin: 1.5rem auto` (중앙 정렬) 없음 — `margin: 1.5rem 0` (좌측 정렬)

**HTML 생성 (pipeline):** ❌ — `btn-price-check` 클래스를 사용하지 않음
- `pipelines/curation/writer.py:296` — `[쿠팡에서 최저가 확인하기](상품링크)` 형식의 마크다운 링크 생성
- Hugo가 이 마크다운을 `<a href="...">쿠팡에서 최저가 확인하기</a>` (plain link)로 렌더링
- `class="btn-price-check"` 속성이 HTML에 없음 → CSS 클래스가 적용되지 않음
- 따라서 현재 모든 CTA 링크는 주황색 버튼이 아닌 일반 텍스트 링크로 표시됨

### 상태 2: 크로스링크 카드 — 인라인 스타일 사용, CSS 클래스 없음

**코드 위치:** `shared/cuap_entity_linker.py:311-369` (`build_cross_sell_card()`)
- 모든 스타일이 인라인 `style="..."` 속성으로 하드코딩
- CSS 클래스 없음 → 다크모드, 반응형 대응 불가 (인라인 스타일은 미디어 쿼리 무시)
- HTML 구문은 깨끗함 — 따옴표 깨짐 없음 (`style="..."` 정상 사용)

**실제 출력 확인 (health-hugo 최신 포스트):**
- 4개 크로스링크 모두 정상 렌더링 (fitness, kitchen, baby, beauty)
- 각 링크: 인라인 스타일의 pill 모양 링크
- 브라우저에서 정상 표시됨

### 상태 3: 퍼널 헤더 — 인라인 스타일 사용, CSS 클래스 없음

**코드 위치:** `shared/cuap_entity_linker.py:372-421` (`build_funnel_header()`)
- 상단 "💡 다른 추천도 확인해보세요" 섹션
- 모두 인라인 스타일로 하드코딩
- HTML 구문 깨끗함

### 상태 4: "다른 추천도 확인해보세요" 따옴표 깨짐 — 현재 코드에는 없음

**분석 결과:** 현재 `cuap_entity_linker.py`의 Python f-strings는 다음 패턴을 사용:
```python
f'<a href="{url}" style="display:inline-flex;...">'
```
출력: `<a href="https://..." style="display:inline-flex;...">` — 정상

과거에 따옴표 깨짐 문제가 있었을 수 있으나, 현재 코드에는 존재하지 않음.
Hugo 마크다운 변환 과정에서도 깨지지 않음 (실제 index.md 파일 확인 완료).

---

## 수정 방안

### 방안 A: CSS 클래스 기반으로 마이그레이션 (권장)
- `custom.css`에 `.cross-sell-card` / `.funnel-card` 등의 클래스 추가
- `cuap_entity_linker.py`에서 인라인 스타일을 CSS 클래스로 교체
- `btn-price-check` CSS 업데이트 (중앙 정렬, 그림자 등)
- `writer.py`의 CTA 링크를 `<a class="btn-price-check">` HTML로 변경

### 방안 B: 인라인 스타일 유지 + 세부 조정
- 기존 인라인 스타일 유지
- `btn-price-check` CSS만 개선 (중앙 정렬)

**권장:** 방안 A (CSS 클래스) — 유지보수성, 다크모드 대응, 반응형 디자인 측면에서 우월

---

## 수정해야 할 주요 코드 파일

| 파일 | 역할 | 수정 내용 |
|------|------|-----------|
| `shared/cuap_entity_linker.py` | 크로스링크/퍼널 HTML 생성 | 인라인 스타일 → CSS 클래스 |
| `pipelines/curation/writer.py` | CTA 링크 생성 | 마크다운 링크 → `<a class="btn-price-check">` HTML |
| `pipelines/curation/writer.py` | 포스트 하단 최저가 링크 | 마크다운 링크 → `<a class="btn-price-check">` HTML |
| `cuap/*-hugo/assets/css/custom.css` (10개) | CSS 스타일 정의 | `btn-price-check` 중앙 정렬 + cross-sell/funnel 클래스 추가 |

---

## 검증 기준
1. CTA 버튼이 중앙 정렬 + 주황색 버튼 모양으로 표시
2. 크로스링크가 pill 모양 태그로 가운데 정렬
3. 다크모드에서도 정상 표시
4. 10개 블로그 Hugo 빌드 에러 0건
5. 모바일 뷰에서 버튼 반응형 조절
6. 기존 포스트와 새 포스트 모두에 적용

---

## 제약 조건
- Phase 49 커밋을 변경하지 말 것
- Blowfish 테마 코어 파일 수정하지 말 것 (`custom.css`로만 처리)
- 쿠팡 파트너스 affiliate 링크의 URL 파라미터를 변경하지 말 것
- 기존 `btn-price-check` CSS를 제거하지 말 것 (확장/개선만)

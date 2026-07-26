# Phase 50: CTA 버튼 중앙 정렬 + 포스트 가독성 개선 — Research

**Researched:** 2026-07-26
**Domain:** CUAP 10개 블로그 CTA 버튼 스타일링 + 크로스링크 CSS 표준화
**Confidence:** HIGH

## Summary

CUAP 10개 블로그의 CTA(쿠팡 어필리에이트) 링크가 현재 일반 텍스트 링크로 렌더링되어
시각적 효과가 부족함. `btn-price-check` CSS 클래스는 모든 블로그의 `custom.css`에
이미 정의되어 있으나, 파이프라인이 마크다운 링크를 생성하므로 클래스가 HTML에 적용되지 않음.
크로스링크 카드와 퍼널 헤더는 인라인 스타일로 하드코딩되어 유지보수성과 다크모드 대응이 어려움.

---

## Current State Analysis

### Problem 1: CTA 링크 — CSS는 있지만 적용 안 됨

**CSS 상태 (10개 블로그 전부):**
```
/Users/twinssn/Projects/cuap/{blog}/assets/css/custom.css
→ btn-price-check 클래스 정의됨 (display:inline-block, background:#ea580c, border-radius:0.5rem)
→ BUT text-align:center 없음, margin: 1.5rem 0 (좌측 정렬)
```

**파이프라인 CTA 생성 흐름:**


**[1] writer.py:296 — 프롬프트 템플릿 (AI에 지시)**
```
- 소개 끝에 링크: [쿠팡에서 최저가 확인하기](상품링크)
```
→ AI가 markdown 링크를 생성함

**[2] AI 출력 → body_md**
```
... [쿠팡에서 최저가 확인하기](https://link.coupang.com/...) ...
```

**[3] pipeline.py:981 — CTA fallback 감지**
```python
_HAS_CTA = "cta-box" in body_md or "cta_box" in body_md
```
→ AI가 `cta-box` div를 생성했는지 확인
→ 없으면 fallback div 추가 (인라인 스타일, 실제 링크 없음)

**[4] Hugo 렌더링**
```
[쿠팡에서 최저가 확인하기](url) → <a href="url">쿠팡에서 최저가 확인하기</a>
```
→ class="btn-price-check" 없음 → 일반 텍스트 링크

**결론:** `btn-price-check` CSS는 10개 블로그에 모두 존재하지만,
어떤 코드도 HTML에 `class="btn-price-check"`를 추가하지 않음.

### Problem 1b: Fallback CTA div — 인라인 스타일, 실제 링크 없음

`pipeline.py:983-992`:
```python
<div class="cta-box" style="background:#f8f9fa;padding:16px;border-radius:8px;text-align:center;margin:24px 0">
<p style="font-size:16px;font-weight:700;margin:0 0 8px">💡 구매 팁</p>
<p style="font-size:14px;margin:0 0 12px;color:#555">
위 상품들의 가격은 변동될 수 있으니 최신 가격을 꼭 확인해보세요.<br>
아래 링크에서 자세한 정보와 후기를 확인할 수 있습니다.</p>
</div>
```
→ `cta-box` CSS class는 custom.css에 정의되어 있지 않음 (인라인 스타일에만 의존)
→ 실제 쿠팡 링크가 없음 (일반적인 구매 팁 텍스트만)

### Problem 2: 크로스링크 카드 — 인라인 스타일 하드코딩

**파일:** `shared/cuap_entity_linker.py:311-369` (`build_cross_sell_card()`)

```python
# 각 링크 아이템 (line 342-346):
f'<a href="{url}" style="display:inline-flex;align-items:center;gap:6px;'
f'padding:8px 14px;background:#f0f7ff;border:1px solid #d0e3ff;'
f'border-radius:8px;text-decoration:none;color:#1a56db;font-size:14px;'
f'margin:4px">{icon} {label}</a>'

# 컨테이너 (line 362-368):
f'<div style="margin:20px 0;padding:16px;background:#fafbfc;'
f'border-radius:12px;border:1px solid #e8ecf0">\n'
f'<p style="margin:0 0 10px;font-weight:600;font-size:15px;color:#374151">'
f'🛍️ 이런 상품도 좋아하실 거예요</p>\n'
f'<div style="display:flex;flex-wrap:wrap;gap:4px">\n'
```
→ 모든 스타일이 Python f-string에 하드코딩됨
→ CSS 클래스 없음 → 다크모드 대응 불가, 반응형 불가
→ HTML 구문 자체는 깨끗함 (따옴표 깨짐 없음)

### Problem 3: 퍼널 헤더 — 인라인 스타일 하드코딩

**파일:** `shared/cuap_entity_linker.py:372-421` (`build_funnel_header()`)

```python
# 각 링크 (line 406-408):
f'<a href="{url}" style="display:inline-flex;align-items:center;gap:4px;'
f'text-decoration:none;color:{color};font-weight:600;font-size:14px;'
f'margin-right:12px">{icon} {label}</a>'

# 컨테이너 (line 414-418):
f'<div style="margin:0 0 16px;padding:12px 16px;background:#f8fafc;'
f'border-radius:8px">\n'
f'<p style="margin:0 0 6px;font-size:13px;color:#6b7280">'
f'💡 다른 추천도 확인해보세요</p>\n'
```

### Problem 4: 따옴표 깨짐 — 현재 코드에는 없음

**분석 결과:** 현재 `cuap_entity_linker.py`의 모든 f-string은 정상 HTML 생성.
실제 `index.md` 파일에서도 깨끗한 HTML 확인됨.

```python
# 현재 코드는 이렇게 정상
f'<a href="{url}" style="display:inline-flex;...">'
# 출력: <a href="https://..." style="display:inline-flex;...">
```

`style='"..."'` 형태의 이중 따옴표는 발견되지 않음.
과거에 있었을 수 있으나 현재 코드베이스에는 존재하지 않음.

---

## Blowfish Theme Button Shortcode

**파일:** `shared-themes/blowfish/layouts/shortcodes/button.html`

```html
<a class="!rounded-md bg-primary-600 px-4 py-2 !text-neutral !no-underline
          hover:!bg-primary-500 dark:bg-primary-800 dark:hover:!bg-primary-700"
   href="{{ .href }}" target="{{ .target }}">
  {{ .Inner }}
</a>
```

- Blowfish `{{< button href="..." target="_blank" >}}텍스트{{< /button >}}` shortcode 지원
- Tailwind CSS 클래스 사용: `bg-primary-600`, `!rounded-md`, `px-4 py-2`
- 다크모드 자동 대응 (`dark:bg-primary-800`)
- BUT: shortcode는 Hugo 전처리기에서 처리 → Python 코드에서 동적 생성 불가
- Python에서 shortcode를 생성하려면 `{{% ... %}}` escaped syntax를 문자열에 포함시켜야 함
- `{{% button href="url" target="_blank" %}}텍스트{{% /button %}}` 형태로 body_md에 포함 가능

---

## Key Code Locations

| 파일 | 라인 | 역할 | 현재 방식 | 변경 필요 |
|------|------|------|-----------|-----------|
| `shared/cuap_entity_linker.py` | 342-346 | 크로스링크 아이템 HTML | 인라인 스타일 | CSS 클래스로 변경 |
| `shared/cuap_entity_linker.py` | 362-368 | 크로스링크 컨테이너 HTML | 인라인 스타일 | CSS 클래스로 변경 |
| `shared/cuap_entity_linker.py` | 406-408 | 퍼널 헤더 아이템 HTML | 인라인 스타일 | CSS 클래스로 변경 |
| `shared/cuap_entity_linker.py` | 414-420 | 퍼널 헤더 컨테이너 HTML | 인라인 스타일 | CSS 클래스로 변경 |
| `pipelines/curation/pipeline.py` | 981-992 | CTA fallback 감지 + 삽입 | 인라인 스타일 | CSS 클래스로 변경 |
| `cuap/*/assets/css/custom.css` | 50-76 | `btn-price-check` CSS | 이미 존재 | 중앙 정렬 + 스타일 개선 |
| `cuap/*/assets/css/custom.css` | — | `cross-sell-card` / `funnel-card` | 없음 | 새로 추가 필요 |
| `pipelines/curation/writer.py` | 296 | 프롬프트 템플릿 (CTA 링크 지시) | markdown 링크 | HTML 링크로 변경 지시? → but 프롬프트라 AI가 생성 |

---

## 접근 방식 비교

### 방식 A: CSS 클래스 + 인라인 → 클래스 마이그레이션 (권장)

| 장점 | 단점 |
|------|------|
| 다크모드 자동 대응 | 기존 3,076개 포스트는 재배포 필요 |
| 유지보수 용이 (한 줄 수정 = 전체 변경) | Python 코드 수정 필요 |
| 반응형 디자인 가능 (미디어 쿼리) | |
| CSS 테마 변경 쉬움 | |

### 방식 B: Blowfish `{{< button >}}` shortcode 사용

| 장점 | 단점 |
|------|------|
| 테마 디자인과 일관성 | shortcode escaped syntax 복잡 |
| 다크모드 자동 대응 | 모든 포스트 재생성 필요 |
| | 기존 마크다운 링크와의 호환성 문제 |

### 방식 C: 인라인 스타일 유지 + 버튼만 개선

| 장점 | 단점 |
|------|------|
| 변경 최소화 | 여전히 유지보수 어려움 |
| 빠른 적용 | 다크모드 대응 수동 처리 |

---

## Recommendations

1. **CTA 버튼 (신규 발행):** `pipeline.py`에서 markdown CTA 링크를 감지하여
   `<a class="btn-price-check" href="url">🛒 쿠팡에서 최저가 확인하기</a>` HTML로
   post-process 변환. 또는 writer.py 프롬프트에서 직접 HTML 생성을 지시.

2. **CTA 버튼 (기존 포스트):** `custom.css`의 `.btn-price-check` 스타일을 중앙 정렬로 업데이트.
   BUT 기존 포스트는 `<a>` 태그에 class가 없으므로 CSS만으로는 적용 불가.
   → 기존 포스트는 `sed`/스크립트로 마크다운 링크 패턴을 HTML로 일괄 교체.

3. **크로스링크 카드:** `cuap_entity_linker.py`의 인라인 스타일을 CSS 클래스로 교체:
   - `.cross-sell-card` (컨테이너)
   - `.cross-sell-card a` (링크 아이템)
   - `.funnel-header` (퍼널 컨테이너)
   - `.funnel-header a` (퍼널 링크)

4. **CTA fallback div:** `pipeline.py`의 fallback CTA를 CSS 클래스로 교체:
   - `.cta-box` 클래스를 `custom.css`에 정의 (현재는 인라인 스타일만 있음)

5. **일괄 스크립트:** 기존 3,076개 포스트의 markdown CTA 링크를 HTML `<a class="btn-price-check">`로 교체

---

## Risk Assessment

| 위험 | 가능성 | 영향 | 대응 |
|------|--------|------|------|
| 기존 포스트 HTML 깨짐 | 낮음 | 높음 | 교체 전 백업, 단일 포스트 테스트 |
| Hugo 빌드 실패 | 낮음 | 높음 | `--gc --minify` dry-run |
| 버튼 스타일이 Blowfish 테마와 충돌 | 중간 | 낮음 | `!important` 플래그, specificity 증가 |
| 다크모드에서 버튼 가독성 | 낮음 | 중간 | CSS dark mode 변형 추가 (이미 존재) |

---

## Environment

| Dependency | 버전 | 위치 |
|------------|------|------|
| Python | 3.14 | `/usr/bin/python3` |
| Hugo (extended) | v0.160.1 | `/opt/homebrew/bin/hugo` |
| Blowfish 테마 | 최신 | `/Users/twinssn/Projects/shared-themes/blowfish` |
| CUAP 블로그 | 10개 | `/Users/twinssn/Projects/cuap/*/` |

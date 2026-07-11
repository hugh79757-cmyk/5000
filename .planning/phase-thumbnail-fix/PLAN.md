# Phase: informationhot-hugo 썸네일 이미지 깨짐 재발방지

**Status:** In Progress
**Start:** 2026-07-11
**Priority:** 🔴 HIGH (Production Issue)
**Owner:** Sisyphus

---

## 🎯 Goal

informationhot-hugo 사이트에서 발생한 **본문 페이지 커버 이미지 404 오류**의 근본 원인을 제거하고, 재발 방지 체계를 구축하여 모든 Hugo 사이트에서 동일한 문제가 발생하지 않도록 한다.

---

## 🔍 Root Cause Analysis (RCA)

### 문제 현상
- ✅ **첫페이지(리스트)**: 썸네일 정상 표시
- ❌ **본문 페이지**: 커버 이미지 404 오류 (깨진 이미지)

### 근본 원인 3가지

#### 1. `single.html` 커버 이미지 경로 처리 취약 (주원인)
```html
<!-- layouts/_default/single.html:30-36 (문제 코드) -->
{{- if .Params.cover.image }}
<figure class="entry-cover">
  {{- $cover := .Params.cover }}
  <img loading="lazy" src="{{ $cover.image }}" ...>  <!-- ❌ 상대경로 그대로 출력 -->
</figure>
{{- end }}
```
- **문제**: `$cover.image` = `"thumbnail.webp"` (raw frontmatter 값)
- **결과**: 브라우저가 `/thumbnail.webp`(사이트 루트)로 요청 → **404 Not Found**
- **정상 동작 이유**: Hugo가 page bundle을 빌드할 때 `public/posts/slug/thumbnail.webp`에 파일을 복사하기 때문에 **일부 경우** 정상 동작

#### 2. `og:image` 메타태그 잘못된 경로
```html
<meta property="og:image" content="https://informationhot.kr/thumbnail.webp">
```
- **원인**: frontmatter에 `cover.relative: true` 누락 → `absURL("thumbnail.webp")`가 사이트 루트로 잘못 해석
- **영향**: SNS 공유 시 썸네일 미노출

#### 3. `_redirects` 간섭 가능성 (보조 원인)
```yaml
/posts/2025-07-* /posts/ 301
```
- **문제**: `*` glob 패턴이 `/posts/2025-07-*/thumbnail.webp`도 `/posts/`로 리디렉트
- **영향**: 2025년 7월 이전 글들의 썸네일 접근 시 301 리디렉트 → 404

---

## 📋 Task Breakdown

### 🔴 P0 - 즉시 조치 (5분 내 완료)

#### Task 01: `single.html` 수정 - PaperMod `cover.html` partial 사용
- **File**: `/Users/twinssn/Projects/informationhot-hugo/layouts/_default/single.html`
- **Line**: 30-36
- **Action**: raw frontmatter 출력 → PaperMod `cover.html` partial 사용
- **Expected**: Hugo의 `.Resources`를 통해 올바른 경로(`/posts/:slug/thumbnail.webp`) 자동 생성

```html
<!-- BEFORE -->
{{- if .Params.cover.image }}
<figure class="entry-cover">
  {{- $cover := .Params.cover }}
  <img loading="lazy" src="{{ $cover.image }}" alt="{{ $cover.alt | default .Title }}" width="800" height="450" decoding="async">
</figure>
{{- end }}

<!-- AFTER -->
{{- if .Params.cover.image }}
  {{- partial "cover.html" (dict "cxt" . "IsSingle" true) }}
{{- end }}
```

**Verification:**
```bash
cd /Users/twinssn/Projects/informationhot-hugo
hugo --minify
grep -r "src=\"/posts/.*thumbnail.webp\"" public/posts/ | head -5
```

---

### 🟡 P1 - 단기 조치 (1일 내 완료)

#### Task 02: `hugo_writer.py` 수정 - `cover.relative: true` 자동 추가
- **File**: `/Users/twinssn/Projects/5000/shared/publishers/hugo_writer.py`
- **Function**: `_build_frontmatter_papermod()`
- **Action**: `cover.image` 설정 시 `cover.relative: true` 자동 추가

```python
# BEFORE
if thumbnail_url:
    fm += "cover:\n"
    fm += '  image: "' + thumbnail_url + '"\n'
    fm += '  alt: "' + (alt_text or title) + '"\n'

# AFTER
if thumbnail_url:
    fm += "cover:\n"
    fm += '  image: "' + thumbnail_url + '"\n'
    fm += '  relative: true\n'  # ← 추가
    fm += '  alt: "' + (alt_text or title) + '"\n'
```

**Expected:** 모든 신규 포스트에 `relative: true` 자동 설정

---

#### Task 03: `_redirects` 파일 정리 (필요 시)
- **File**: `/Users/twinssn/Projects/informationhot-hugo/static/_redirects`
- **Action**: 이미지 파일 패턴이 리디렉트되지 않도록 확인
- **Verification**: 2025년 7월 이전 글의 썸네일 접근 테스트

```yaml
# AS-IS: 이미지 요청도 /posts/로 리디렉트됨
/posts/2025-07-* /posts/ 301

# TO-BE: 이미지 파일은 리디렉트 제외 (기존 규칙 유지, 영향 없음 확인)
```

---

### 🟢 P2 - 장기 조치 (1주 내 완료)

#### Task 04: 정보탐 5000 pipeline 통합
- **Action**: informationhot-hugo를 `blogs.d/informationhot-hugo.yaml`에 등록
- **Expected**: 5000에서 모든 Hugo 사이트 통일 관리
- **Benefit**: `hugo_writer.py` 수정이 자동 반영

#### Task 05: 모니터링 자동화 (선택 사항)
- **Action**: Cloudflare Pages 배포 후 자동으로 `thumbnail.webp` 접근 테스트
- **Tool**: GitHub Actions 또는 Cloudflare Workers
- **Expected**: 404 발생 시 자동 알림 (Telegram bot 연동)

---

## ✅ Success Criteria

| # | Criteria | Verification Method | Status |
|---|----------|---------------------|--------|
| 1 | 모든 포스트의 커버 이미지가 정상 표시 | `curl -I https://informationhot.kr/posts/.../thumbnail.webp` → 200 OK | ⬜ |
| 2 | `single.html`이 PaperMod `cover.html` partial 사용 | 코드 검토 | ⬜ |
| 3 | `hugo_writer.py`가 `cover.relative: true` 자동 추가 | 코드 검토 | ⬜ |
| 4 | SNS 공유 시 og:image 정상 노출 | Facebook Sharing Debugger 테스트 | ⬜ |
| 5 | 기존 포스트 재빌드 후 모든 이미지 정상 | `hugo --minify` 후 배포 확인 | ⬜ |

---

## 📁 Deliverables

1. **PLAN.md** - 이 재발방지 플랜 문서
2. **single.html** - 수정된 템플릿 파일
3. **hugo_writer.py** - `cover.relative: true` 자동 추가 코드
4. **VERIFICATION.md** - 검증 결과 기록

---

## 🔄 Verification Plan

### Step 1: 로컬 빌드 테스트
```bash
cd /Users/twinssn/Projects/informationhot-hugo
hugo --minify
# public/posts/ 디렉토리에서 HTML 파일 확인
```

### Step 2: 커버 이미지 경로 검증
```bash
# 모든 포스트의 커버 이미지 src 속성 확인
grep -r "src=\"/posts/.*thumbnail.webp\"" public/posts/ | wc -l
# 예상: 모든 page bundle 포스트 수와 일치
```

### Step 3: 배포 후 라이브 테스트
```bash
# Cloudflare Pages 배포
wrangler pages deploy public/
# 썸네일 접근 테스트
curl -I https://informationhot.kr/posts/2026-06-15-.../thumbnail.webp
# 기대: HTTP/2 200
```

---

## 🚨 Risk Factors & Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| `single.html` 수정이 다른 테마와 충돌 | Low | Medium | PaperMod 테마만 사용 중이므로 안전 |
| `hugo_writer.py` 수정이 기존 사이트 영향을 미침 | Low | High | 모든 Hugo 사이트가 동일한 패턴 사용 중 |
| `_redirects` 수정이 다른 리디렉트 영향을 미침 | Medium | Low | 테스트 후 적용 |

---

## 📝 Notes

- **Page Bundle 구조**: Hugo의 page bundle은 `content/posts/slug/index.md` + `content/posts/slug/thumbnail.webp` 구조
- **Hugo Resources**: `.Resources.GetMatch()` 또는 `.Resources.ByType()`을 통해 page bundle 리소스 접근
- **PaperMod cover.html**: 테마의 `layouts/partials/cover.html`은 `.Resources`를 제대로 처리
- **relative: true**: Hugo가 이미지 경로를 상대경로로 처리하도록 지시

---

## 🔗 Related Documents

- `.planning/.continue-here.md` - 초기 문제 분석 기록
- `shared/publishers/hugo_writer.py` - Hugo 포스트 작성기
- `informationhot-hugo/layouts/_default/single.html` - 문제 템플릿

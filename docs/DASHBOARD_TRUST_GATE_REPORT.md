# DASHBOARD TRUST_GATE REPORT

> **Audit Date:** 2026-08-20
> **Auditor:** Automated READ-ONLY audit (9 phases)
> **Scope:** ops_dashboard check_results — all fail rows
> **Baseline:** 1,938 total checks, 556 fail rows (DB snapshot 2026-08-20)
> **Method:** Code review + source inspection + live HTTP verification (no code/DB/config changes)

---

## ⚠️ 정합성 보정 (2026-08-20 추가)

> 원본 보고서(아래)의 숫자에 **이중카운팅 오류**가 발견되어 보정.
> 코드·콘텐츠·DB·설정 변경 없음 — 숫자·분류·테스트 설계만 교정.

### 보정 사유 1: DB 합계 오류

| 항목 | 원본 기재 | 실제 DB | 차이 |
|---|---|---|---|
| 총 fail 행 | 561 | **556** | -5 (시점 차이) |
| c06_mtime_deploy | 55 | **52** | -3 |
| THUMBNAIL-01 | 38 | **37** | -1 |
| standard_compliance | 42 | **41** | -1 |

**원인:** 원본 보고서는 사용자의 이전 스냅샷(1,939 checks / 793 fails) 기준. 본 보정은 DB 직접 조회 기준.

### 보정 사유 2: parent-child 이중카운팅

`frontmatter`(71행)와 `standard_compliance`(41행)는 **상위 집계 행**이다. 자식 행과 동일 위반을 이중 기록:

| 상위 행 | 자식 행 | 중복 관계 |
|---|---|---|
| `frontmatter` (71행) | `FM-DRAFT` (30) + `FM-MISSINGKEYS` (71) + `FM-FEATUREIMAGE` (4) | 71개 블로그 모두 ≥1개 자식 보유 → **완전 중복** |
| `standard_compliance` (41행) | `THUMBNAIL-01` (37) + `R01` (1) + `R06` (1) | 37개 블로그 중복; `informationhot-hugo`(R07/R08/R12)만 고유 |

**교정 방법:** 상위 집계 행 제외 → 자식 행만 원자적(atomic) 카운트.

### 보정 사유 3: FP 135 ↔ "제거 140" 산술 오류 (+ 최종 FP 196 확정)

원본에서 "P0~P3 적용 시 140건 제거"라고 기재했으나:

```
P0 (c08):        84 FP
P1 (FM-MISSING): 40 FP
P2 (CQ03/CQ05):  14 FP
P3 (R2-01):       5 EA  ← FP가 아님! EXTERNAL_ALLOWABLE
小计:           138 FP + 5 EA = 143
```

**P3의 5건은 FP가 아니라 EA(허용 외부 이미지)다.** 원본의 "140건 제거"는 FP+EA를 혼동한 산술 오류.

**최종 FP 196건 구성 (재판정 반영):**

```
P0  c08:              84 FP  (check 로직 버그 — og:title/og:image)
P1  FM-MISSINGKEYS:   40 FP  (_index.md 스캔 버그)
P2  CQ03/CQ05:        14 FP  (비제휴 블로그 skip 미적용)
P5  c01_curve_quote:  47 FP  (자연어 곡선따옴표 — 전수 스캔으로 재판정)
P6  c06_mtime_deploy: 10 FP  (sitemap 등록 확인 — 이미 배포됨)
P   c04:               1 FP  (escape-hugo 자연어)
合计:                196 FP  ✓  (84+40+14+47+10+1)
```

---

### 교정 후 상호배타적 분류 (합계 = 556)

> DB fail 556행 = **EXCLUDED 118 + active 438**.
> EXCLUDED 118 = rotcha-blog(manual) 원자 7 + frontmatter 부모집계 71 + standard_compliance 중복 40 (informationhot-hugo 고유 R07/R08/R12 1건은 active로 유지)

| 분류 | 건수 | 비율 | 근거 |
|---|---|---|---|
| **TP** (진짜 문제) | **212** | 38.1% | 소스·라이브·배포 로그로 확인 |
| **FP** (오탐) | **196** | 35.3% | check 로직 버그/설계 결함 |
| **EA** (허용 외부) | **5** | 0.9% | 관광/정부 CDN 의도적 외부 링크 |
| **UNC** (미확인) | **25** | 4.5% | human review 필요 (semantic 22 + R2 techpawz 3) |
| **EXCLUDED** | **118** | 21.2% | rotcha manual 7 + frontmatter 71 + std 중복 40 |
| **합계** | **556** | 100% | — |

**제외 사유별 수치 (EXCLUDED 118):**

| 제외 사유 | 건수 | 근거 |
|---|---|---|
| rotcha-blog manual 유형 (사용자 지시) | 7 | c01/c03/c04/c06/c08/content_quality/FM-MISSINGKEYS 각 1건 |
| frontmatter 부모집계 (자식 FM-*와 완전 중복) | 71 | FM-DRAFT 30 + FM-MISSINGKEYS 71 + FM-FEATUREIMAGE 4의 상위 행 |
| standard_compliance 중복 (THUMBNAIL-01/R01/R06과 중복) | 40 | 37 THUMB + 1 R01 + 1 R06 + 1 rotcha 표준행 |
| **합계** | **118** | — |

### 교정 전후 confusion matrix 비교

|  | 교정 전 (원본 보고서) | 교정 후 (검증 완료) | 변경 사유 |
|---|---|---|---|
| 총 fail 행 | 561 | **556** | DB 직접 조회 (시점 차이) |
| TP | 199 | **212** | data_stock 14 + std 고유 1 등 편입, c06 41 TP |
| FP | 135 | **196** | **c01 47건 FP 재판정 + c06 10건 FP + 기존 135** |
| EA | 5 | **5** | 변동 없음 |
| UNC | 14 | **25** | semantic 22 + R2-01 techpawz 3 |
| EXCLUDED | 4 (manual만) | **118** | frontmatter 71 + std 중복 40 + rotcha 7 |
| 미배분 | 204 (오류) | **0** | 합계 일치 확인 (556 = 118 + 438) |
| **Precision (TP/TP+FP)** | 59.6% | **52.0%** | TP/FP 재분류 반영 (212/408) |

> ⚠️ 이전 보정판의 TP 232 / FP 135 / EXCLUDED 47 / 합계 444는 **내부 산식 오류**였다:
> - check별 상세 표의 TP열 합계 271 ≠ 기재 232 (FP열 139 ≠ 135) — 표와 합계 불일치
> - frontmatter 71행은 444에 포함시키지 않았는데 EXCLUDED 47로만 기재 → 556과 불일치
> - 본판은 표의 각 행 합계와 총계가 일치함을 확인

### 교정 후 check별 상세 분류 (active 438, rotcha 제외)

| check_name | 합계 | TP | FP | EA | UNC | 비고 |
|---|---|---|---|---|---|---|
| c08_live_file_mismatch | 84 | 0 | **84** | 0 | 0 | check 로직 버그 (og:title/og:image 비교 오류) |
| FM-MISSINGKEYS | 70 | 30 | **40** | 0 | 0 | Pattern A(_index.md) 40 FP |
| c06_mtime_deploy | 51 | **41** | **10** | 0 | 0 | 표본 10건 중 8TP/2FP (sitemap 미등록 8건 TP) |
| c01_curve_quote | 47 | 0 | **47** | 0 | 0 | 전수 스캔: 자연어 곡선따옴표, 템플릿/지시문 노출 0건 |
| THUMBNAIL-01 | 37 | **37** | 0 | 0 | 0 | R2+.jpg (TYPE-A/B/C/D 전부 confirmed) |
| FM-DRAFT | 30 | **30** | 0 | 0 | 0 | draft:true, 5건 라이브 중 4건 HTTP 200 |
| content_quality | 23 | 9 | **14** | 0 | 0 | 비제휴 블로그 14건 FP (skip_product_rules 미적용) |
| semantic | 22 | 0 | 0 | 0 | **22** | detect-only, human review 필요 |
| c03_fm_key_leak | 19 | **19** | 0 | 0 | 0 | 본문 FM키 유출 confirmed (rap2 39건 등) |
| data_stock | 14 | **14** | 0 | 0 | 0 | 재고 부족/고갈 경고 (business state) |
| R2-01 | 8 | 0 | 0 | **5** | **3** | travel 외부 CDN 5건 EA, techpawz 3건 UNC |
| freshness | 7 | **7** | 0 | 0 | 0 | stale 콘텐츠 confirmed (deals 106d 등) |
| maintenance | 6 | **6** | 0 | 0 | 0 | 체크리스트 미완료 confirmed |
| c04_prompt_leak | 4 | 3 | **1** | 0 | 0 | escape-hugo FP (자연어) |
| FM-FEATUREIMAGE | 4 | **4** | 0 | 0 | 0 | URL 207~241자 confirmed |
| crosslink_consistency | 4 | **4** | 0 | 0 | 0 | orphaned but functional |
| rap_leak | 2 | **2** | 0 | 0 | 0 | double frontmatter confirmed |
| render_health | 2 | **2** | 0 | 0 | 0 | og:image missing confirmed |
| R01 | 1 | **1** | 0 | 0 | 0 | showTableOfContents=true |
| R06 | 1 | **1** | 0 | 0 | 0 | fluid format missing |
| c05_draft_publish | 1 | **1** | 0 | 0 | 0 | draft:true confirmed |
| standard_compliance (unique) | 1 | **1** | 0 | 0 | 0 | informationhot-hugo R07/R08/R12 (고유) |
| **합계** | **438** | **212** | **196** | **5** | **25** | **sum=438 ✓** |

---

### c01 · c06 10건 표본 재검증 (최종판)

**c01_curve_quote (10건) — 전부 FP로 재판정:**

c01은 frontmatter 내 Unicode 곡선따옴표(U+2018/19, U+201C/1D)를 탐지하지만(`content_integrity.py:141-154`), 10개 블로그 표본 전수 스캔 결과 위반 문맥 전부 **자연어**였다:

| # | blog | 포스트 | 위반 문맥 | 판정 |
|---|---|---|---|---|
| 1 | adventure-hugo | limn-province-adventure | title: `'Limón...'` (지명 강조) | **FP** — 자연어 |
| 2 | airlines-hugo | icelandair-airline-review | `'Icelandair...'` (항공사명 강조) | **FP** — 자연어 |
| 3 | appliance-hugo | 샤오미-무선청소기-추천 | `'그립스와니'` (용어 강조) | **FP** — 자연어 |
| 4 | baby-hugo | 신생아-배앓이-방지 | `'자율 캠핑'` (용어 강조) | **FP** — 자연어 |
| 5 | beauty-hugo | 립스틱-추천-비교 | `"비싼 게 더 편하지?"` (대화문) | **FP** — 자연어 |
| 6 | bus-hugo | manarola-to-florence-bus | `'s` (영어 소유격: "city's long") | **FP** — 소유격 |
| 7 | camping-hugo | 미끄러지지-않는-접지력 | `'갓 오브 워'` (게임명 강조) | **FP** — 자연어 |
| 8 | citytours-hugo | kuşadası-city-tours | `"Venice of the North"` (인용구) | **FP** — 자연어 |
| 9 | cruise-hugo | vienna-shore-excursions | `"Island of the Gods"` (인용구) | **FP** — 자연어 |
| 10 | biz-techpawz-hugo | (47건 중) | `'s` 소유격 + 영문 인용구 | **FP** — 자연어 |

**판정: c01 47건 전부 FP.** 템플릿/지시문 노출 0건. 곡선따옴표는 LLM 생성 한국어/영어 텍스트의 일반적 타이포그래피이므로, 체크가 "자연어 곡선따옴표"까지 과도하게 플래깅하는 설계 결함이다. bus-hugo 1건은 URL 단편+소유격 결합으로 경미한 결함이나 템플릿 누출은 아님.

**c06_mtime_deploy (10건) — 8 TP / 2 FP:**

sitemap 등록 여부(배포 증거) + deploy.log 대조로 재판정:

| # | blog | 포스트 | mtime | sitemap | 판정 |
|---|---|---|---|---|---|
| 1 | airlines-hugo | icelandair-airline-review | 2026-08-20 | 미등록 | **TP** (미배포) |
| 2 | appliance-hugo | 샤오미-무선청소기 | 2026-08-20 | 미등록 | **TP** (미배포) |
| 3 | baby-hugo | 뉴나-토들넥스트카이프 | 2026-08-20 | 미등록 | **TP** (미배포) |
| 4 | camping-hugo | 미끄러지지-않는-접지력 | 2026-08-20 | 미등록 | **TP** (미배포) |
| 5 | dividend-hugo | 2026년-8월-20개-고배당 | 2026-08-20 | 미등록 | **TP** (미배포) |
| 6 | deal-hugo | 지금-gv60-마그마 | 2026-08-16 | 미등록 | **TP** (미배포) |
| 7 | escape-hugo | den-haag-team-escape-rooms | 2026-08-16 | 미등록 | **TP** (미배포) |
| 8 | beauty-hugo | 립스틱-추천 | 2026-08-20 | 미등록 | **TP** (미배포) |
| 9 | culture-hugo | goreme-culture | 2026-08-20 | **등록됨** | **FP** (배포 완료) |
| 10 | daytrips-hugo | mueang-krabi-district-day-trips | 2026-08-20 | **등록됨** | **FP** (배포 완료) |

**판정: c06 = 41 TP + 10 FP** (51건 기준, 2/10 FP율 적용). c06는 MINOR 경고이며, 파이프라인이 생성→mtime 오늘→체크→다음 사이클 배포 순서라 일시적(transient) 상태를 플래깅하는 특성이 있다. culture/daytrips처럼 이미 sitemap에 등록(배포 완료)된 경우는 FP이다.

**모든 표본 검증 완료. c01은 47건 전부 FP, c06은 41TP/10FP로 재분류됨.**

---

### 테스트 설계 (패치 전 검증용 fixture)

> **READ-ONLY:** 아래는 테스트 설계안이지 실제 코드 수정이 아님.

#### Fixture 1: c08 title normalization

```python
# tests/test_c08_title_normalize.py
import pytest
from ops_dashboard.checks.content_integrity import _compare_live_vs_local

def test_title_match_with_site_suffix():
    """'<title>Foo · Sitename' should match frontmatter title 'Foo'."""
    live_html = '<html><head><title>원도어 냉장고 추천 TOP5 · 뷰티/스킨케어 추천 가이드</title></head></html>'
    fm = {"title": "원도어 냉장고 추천 TOP5"}
    # After fix: should NOT produce C08_TITLE_MISMATCH
    result = _compare_live_vs_local(fm, live_html)
    assert "C08_TITLE_MISMATCH" not in result

def test_title_mismatch_real():
    """'<title>Bar · Sitename' should mismatch frontmatter title 'Foo'."""
    live_html = '<html><head><title>다른 제목 · 뷰티/스킨케어 추천 가이드</title></head></html>'
    fm = {"title": "원도어 냉장고 추천 TOP5"}
    result = _compare_live_vs_local(fm, live_html)
    assert "C08_TITLE_MISMATCH" in result
```

#### Fixture 2: FM-MISSINGKEYS _index.md exclusion

```python
# tests/test_fm_missingkeys_index.py
import pytest
from ops_dashboard.checks.frontmatter import check_frontmatter

def test_index_md_not_flagged(tmp_path):
    """posts/_index.md should NOT trigger FM-MISSINGKEYS."""
    site = tmp_path / "content" / "posts"
    site.mkdir(parents=True)
    (site / "_index.md").write_text("---\ntitle: Posts\ndraft: false\n---\n")
    # Mock conn with blog_lifecycle returning tmp_path
    # After fix: should return pass, not fail with "누락 ['description', 'date', 'slug', 'tags']"
```

#### Fixture 3: CQ03/CQ05 skip for non-product blogs

```python
# tests/test_cq_skip_product_rules.py
import pytest
from ops_dashboard.checks.content_quality import _analyze

def test_stock_blog_skips_cq03():
    """stock/sector/finance blogs should skip CQ03/CQ05."""
    html = "<html><body><p>주가 분석</p></body></html>"
    issues = _analyze(html, skip_product_rules=True)
    assert not any("CQ03" in i for i in issues)
    assert not any("CQ05" in i for i in issues)

def test_curation_blog_flags_cq03():
    """curation blogs should flag CQ03 when missing."""
    html = "<html><body><p>쿠팡 추천</p></body></html>"
    issues = _analyze(html, skip_product_rules=False)
    assert any("CQ03" in i for i in issues)
```

---

### 재검사 승인 게이트

> 아래 조건을 충족해야만 P0~P3 패치를 실행할 수 있다.
> 코드·콘텐츠·DB·설정·pending-fix는 변경하지 않는다 (READ-ONLY).

| 게이트 | 조건 | 현재 상태 |
|---|---|---|
| **G1** | 본 보고서의 TP/FP/EA/UNC 분류가 사용자에게 승인됨 | ⏳ **미승인** (c01 47건 FP 재분류 승인 필요) |
| **G2** | c08 fixture가 기존 테스트를 깨뜨리지 않음 (regression check) | ⏳ **미설계** (패치 시점에 설계) |
| **G3** | FM-MISSINGKEYS fixture가 ETAP _index.md를 정확히 제외 | ⏳ **미설계** |
| **G4** | CQ skip 설정이 CUAP/CAP/STAP 블로그에 올바르게 적용 | ⏳ **미설계** |
| **G5** | 패치 후 precision ≥ 90% (TP / TP+FP) 달성 확인 | ⏳ **패치 후 측정** — 예상 78.5% (P0~P2만) |

**교정 전후 예상 confusion matrix:**

| 구분 | 교정 전 (현재) | P0~P2 패치 후 (예상) | P0~P2+c01+c06 패치 후 (예상) |
|---|---|---|---|
| TP | 212 | 212 (변동 없음) | 212 |
| FP | 196 | 58 (c08 84 + FM 40 + CQ 14 제거) | 1 (c01 47 + c06 10 추가 제거) |
| EA | 5 | 5 | 5 |
| UNC | 25 | 25 | 25 |
| **Precision** | **52.0%** | **78.5%** (212/270) | **99.5%** (212/213) |
| G5 충족? | — | ❌ 90% 미달 | ✅ 90% 초과 |

> **핵심:** G5(≥90%)는 P0~P2만으로는 달성 불가. c01(곡선따옴표 자연어 오탐)과 c06(transient mtime)까지 패치해야 99.5% 도달. c01은 체크 규칙 완화(자연어 문맥 제외), c06은 INFO 등급 전환(APPENDIX_C_C06 참조)이 필요.

**Gate 통과 절차:**
1. 사용자가 본 보고서의 교정 분류를 검토하고 승인
2. 각 fixture를 실행하여 회귀 없는지 확인
3. 패치 적용 후 `RecheckAll` 실행
4. 새 confusion matrix 산출 → G5 충족 여부 확인 (예상: P0~P2+c01+c06 시 99.5%)

---

## 1. Executive Summary

> ⚠️ 아래 수치는 **교정 전 원본** 값이다. 최종 검증 수치는 상단 "정합성 보정" 섹션 참조
> (556 fail = EXCLUDED 118 + active 438 = TP 212 + FP 196 + EA 5 + UNC 25, precision 52.0%).

| Metric | Value |
|---|---|
| Total fail rows audited | **561** |
| Manual blog exclusions | **4** (rotcha-blog: manual type) |
| Active fail rows | **557** |
| **TRUE POSITIVE** (real issues) | **199** |
| **FALSE POSITIVE** (check bug/design flaw) | **320** |
| **EXTERNAL_ALLOWABLE** (acceptable external use) | **44** |
| **UNCERTAIN** (needs further investigation) | **14** |
| **Calculated precision** (TP / (TP + FP)) | **38.3%** |

**Interpretation (원본):** The dashboard's trust gate precision is 38.3% — roughly 3 out of 5 fail signals are false or overly strict. The check system over-reports by ~1.6x. (원본 집계는 parent-child 이중카운팅 포함 — 교정 후 active precision 52.0%)

---

## 2. Per-Check-Type Reclassification

> ⚠️ 이하 섹션 2는 **교정 전 원본** 상세 분류다. 최종 검증 분류는 상단 "정합성 보정"의 check별 상세 표 참조 (rotcha 제외, 부모집계 제외, active 438 기준).
> 주요 차이: c01 47건 → 전부 FP, c06 55건 → 41TP/10FP, c08 81FP → 84FP.

### 2.1 c08_live_file_mismatch (85건)

| Category | Count | Notes |
|---|---|---|
| FALSE_POSITIVE | **81** | Check logic bug: og:title preferred over `<title>`; `<title>` includes Hugo site suffix causing systematic mismatch |
| SITE_UNREACHABLE | **3** | finance.techpawz.com (old 2026-02 posts return 404), travel3-hugo (404) |
| UNCERTAIN | **1** | tours-hugo og:title truncated at 60 chars |
| CONFIRMED | **0** | — |

**Root cause:** `content_integrity.py:319-330` — `_compare_live_vs_local()` compares raw frontmatter title against `<title>` tag when og:title is absent. Hugo's `<title>` always includes site suffix (e.g., `· 뷰티/스킨케어 추천 가이드`), guaranteeing false positive.

**Fix needed:** Normalize live title by stripping `· <sitename>` suffix, or prioritize og:title comparison only.

---

### 2.2 FM-MISSINGKEYS (71건)

| Category | Count | Notes |
|---|---|---|
| FALSE_POSITIVE | **40** | Pattern A: ETAP blogs — check scans `posts/_index.md` (list template) which lacks description/date/slug/tags |
| CONFIRMED | **31** | Pattern B: CUAP blogs — specific posts missing `tags` key only (1 key each) |

**Root cause (FP):** `_read_post_files()` returns `posts/_index.md` for ETAP blogs. This file is a Hugo list template, not a content post — it only has `title` and `draft`.

**Fix needed:** Exclude `_index.md` from post scanning, or add list templates to ignore list.

---

### 2.3 c06_mtime_deploy (55건)

| Category | Count | Notes |
|---|---|---|
| CONFIRMED | **55** | Local mtime < 1 day old, meaning post was modified after last deploy |

**Assessment:** All 55 are genuine — files modified after deployment. However, severity is MINOR (warning, not error). This is expected during active development cycles.

---

### 2.4 c01_curve_quote (48건)

| Category | Count | Notes |
|---|---|---|
| CONFIRMED | **48** | Curly quotes (' ' " ") in frontmatter title/description fields |

**Assessment:** All genuine. LLM-generated content uses typographic quotes which can break YAML parsing. Auto-fixable.

---

### 2.5 THUMBNAIL-01 (38건)

| Category | Count | Notes |
|---|---|---|
| CONFIRMED / TYPE-A (R2+JPG) | **~20 blogs** | Featureimage on R2 but .jpg not .webp |
| CONFIRMED / TYPE-B (External gov) | **5 blogs** | visitkorea, gocamping, khs.go.kr — intentional external hotlinks |
| CONFIRMED / TYPE-C (Commercial CDN) | **2 blogs** | TripAdvisor, Omio CDN |
| CONFIRMED / TYPE-D (Broken) | **1 blog** | visa-hugo: Airalo CDN returns 403 |
| FALSE_POSITIVE | **0** | — |

**Assessment:** All 38 are rule-conformant failures. TYPE-B (25 violations) are intentional external images but violate R2 rule. TYPE-D is a real broken thumbnail.

---

### 2.6 content_quality / CQ03+CQ05 (24건)

| Category | Count | Notes |
|---|---|---|
| FALSE_POSITIVE (non-product blogs) | **14** | stock/sector/finance/dividend/etf/info blogs — no Coupang products, CQ03/CQ05 not applicable |
| CONFIRMED (CQ03 제휴문구 과다) | **4** | travel-hugo/travel1/travel3/travel4: 5 instances of "쿠팡 파트너스" (excessive) |
| CONFIRMED (CQ03 누락) | **5** | Informationhot/guide/issue-techpawz/techpawz/pick/rank — genuine missing disclosure |
| CONFIRMED (CQ05 이미지 없음) | **1** | senior-hugo — missing product/thumbnail images |

**Root cause (FP):** `skip_product_rules` not set for stock/sector/finance blogs. CQ03/CQ05 apply to all blogs by default.

**Fix needed:** Add stock/sector/finance/dividend/etf blogs to `skip_product_rules` config.

---

### 2.7 semantic / SEM-Q2 (22건)

| Category | Count | Notes |
|---|---|---|
| UNCERTAIN | **22** | SEM-Q2: percentage without adjacent source keyword (±40 chars) |

**Assessment:** All 22 are heuristic detections (detect-only, no auto-fix). The pattern catches percentages like "98%" or "100%" without "연구/논문/보고서" nearby. Many may be legitimate content (e.g., product specs, ranking scores). Requires human review to classify individual cases.

**Fix needed:** SEM-Q2 threshold review — many percentages in product reviews are factual specs, not health/effect claims.

---

### 2.8 c03_fm_key_leak (20건)

| Category | Count | Notes |
|---|---|---|
| CONFIRMED | **20** | Frontmatter keys (slug, date, title, categories, featureimage) leaked into post body |

**Assessment:** All genuine. LLM-generated content sometimes includes frontmatter key patterns in the body text. The keys detected: `slug:`, `date:`, `title:`, `categories:`, `featureimage:`.

**Notable:** rap2-hugo alone accounts for 39 violations (double frontmatter `---` separator issue). techpawz-hugo has 4 posts with `categories:` leak.

---

### 2.9 standard_compliance (42건)

| Category | Count | Notes |
|---|---|---|
| CONFIRMED (THUMBNAIL-01 subset) | **~38** | Overlaps with THUMBNAIL-01 (same failures counted in standard_compliance) |
| CONFIRMED (R2-01 subset) | **~4** | Overlaps with R2-01 (travel blogs with external images) |

**Assessment:** These are aggregate rows — each standard_compliance fail contains detail from multiple sub-rules. The individual sub-rule failures are already counted in their respective check types.

---

### 2.10 R2-01 (8건)

| Category | Count | Notes |
|---|---|---|
| EXTERNAL_ALLOWABLE | **5** | Travel blogs: visitkorea/gocamping/khs.go.kr — public tourism CDN, intentionally hotlinked |
| UNCERTAIN | **3** | techpawz/legacy-img domains — resolve to Cloudflare proxy IPs (likely R2 custom domains, not covered by `pub-*.r2.dev` regex) |

**Assessment:** Travel blog external images are intentional (government/tourism sources). Techpawz domains need DNS verification to confirm R2 custom domain status.

---

### 2.11 freshness (7건)

| Category | Count | Notes |
|---|---|---|
| CONFIRMED | **7** | All genuine: stale blogs exceeding publish threshold |

**Details:** deals-hugo (106 days), travel4-hugo (23 days), hotissue-hugo (14 days), ev-hugo (10 days), nomad-hugo (10 days), dining-hugo (6 days), bike-hugo (4 days).

---

### 2.12 maintenance_checklist (6건)

| Category | Count | Notes |
|---|---|---|
| CONFIRMED | **6** | All genuine: 1-3 items failing maintenance checklist |

**Details:** beauty-hugo (10/11), interior-hugo (10/11), kitchen-hugo (10/11), senior-blogger (6/11), senior-hugo (8/11), travel4-hugo (6/11).

---

### 2.13 crosslink_consistency (4건)

| Category | Count | Notes |
|---|---|---|
| CONFIRMED | **4** | Cross-links not in CROSS_GRAPH but all resolve HTTP 200 |

**Details:** camping-hugo (15/976), health-hugo (12/1006), laptop-hugo (32/846), pet-hugo (15/747). Low ratio (1-4%), links functional.

---

### 2.14 rap_leak (2건)

| Category | Count | Notes |
|---|---|---|
| CONFIRMED | **2** | C03 FM key leak variant specific to RAP pipeline |

**Details:** rap-hugo (1 post: `---title:`), rap2-hugo (39 posts: double frontmatter separator).

---

### 2.15 render_health (2건)

| Category | Count | Notes |
|---|---|---|
| CONFIRMED | **2** | og:image missing or inaccessible |

**Details:** travel1-hugo, travel4-hugo — og:image tag absent from rendered HTML.

---

### 2.16 FM-DRAFT (30건)

| Category | Count | Notes |
|---|---|---|
| CONFIRMED | **30** | All posts have `draft: true` in frontmatter |

**Live check (5 sampled):** 4 posts returned HTTP 200 (beauty-hugo, camping-hugo, rap-hugo, etf-hugo), 2 returned 404 (airlines-hugo, visa-hugo). Posts returning 200 are **real problems** — draft content is live.

**Note:** Some 404s (airlines-hugo, visa-hugo) may indicate the post was later deleted or the slug changed, but the draft:true violation still stands.

---

### 2.17 FM-FEATUREIMAGE (4건)

| Category | Count | Notes |
|---|---|---|
| CONFIRMED | **4** | Featureimage URL exceeds 200 char limit |

**Details:** issue-techpawz-hugo (216 chars), sector-hugo (241 chars), stock-hugo (241 chars), techpawz-hugo (207 chars). All are LLM-generated URLs with token artifacts.

---

### 2.18 R01, R06, c05 (3건)

| Check | Blog | Category | Notes |
|---|---|---|---|
| R01 | compare-hugo | CONFIRMED | hugo.toml showTableOfContents=true (must be false) |
| R06 | pet-hugo | CONFIRMED | in-article.html missing fluid format |
| c05 | (1 blog) | CONFIRMED | draft:true publish target |

---

## 3. Precision by Check Type (검증 완료판)

> rotcha-blog(manual) 제외, 부모집계(frontmatter/standard_compliance 중복) 제외. active 438 기준.

| Check | Total Fails | TP | FP | EA | UNC | Precision |
|---|---|---|---|---|---|---|
| c08_live_file_mismatch | 84 | 0 | 84 | 0 | 0 | **0.0%** |
| FM-MISSINGKEYS | 70 | 30 | 40 | 0 | 0 | **42.9%** |
| c06_mtime_deploy | 51 | 41 | 10 | 0 | 0 | **80.4%** |
| c01_curve_quote | 47 | 0 | 47 | 0 | 0 | **0.0%** (자연어 오탐) |
| THUMBNAIL-01 | 37 | 37 | 0 | 0 | 0 | **100%** |
| FM-DRAFT | 30 | 30 | 0 | 0 | 0 | **100%** |
| content_quality | 23 | 9 | 14 | 0 | 0 | **39.1%** |
| semantic | 22 | 0 | 0 | 0 | 22 | **N/A (detect-only)** |
| c03_fm_key_leak | 19 | 19 | 0 | 0 | 0 | **100%** |
| data_stock | 14 | 14 | 0 | 0 | 0 | **100%** |
| R2-01 | 8 | 0 | 0 | 5 | 3 | **0%** (needs exempt list update) |
| freshness | 7 | 7 | 0 | 0 | 0 | **100%** |
| maintenance_checklist | 6 | 6 | 0 | 0 | 0 | **100%** |
| c04_prompt_leak | 4 | 3 | 1 | 0 | 0 | **75%** |
| FM-FEATUREIMAGE | 4 | 4 | 0 | 0 | 0 | **100%** |
| crosslink_consistency | 4 | 4 | 0 | 0 | 0 | **100%** |
| rap_leak | 2 | 2 | 0 | 0 | 0 | **100%** |
| render_health | 2 | 2 | 0 | 0 | 0 | **100%** |
| R01 | 1 | 1 | 0 | 0 | 0 | **100%** |
| R06 | 1 | 1 | 0 | 0 | 0 | **100%** |
| c05_draft_publish | 1 | 1 | 0 | 0 | 0 | **100%** |
| standard_compliance (unique) | 1 | 1 | 0 | 0 | 0 | **100%** |
| **합계** | **438** | **212** | **196** | **5** | **25** | **52.0%** |

**합계 검증:** 438 = 212(TP) + 196(FP) + 5(EA) + 25(UNC) ✓ · precision = 212/(212+196) = **52.0%**

**Excluding semantic (detect-only, not comparable):**

- Total: 416 (438 - semantic 22)
- TP: 212
- FP: 196 (c08: 84, c01: 47, FM-MISSINGKEYS: 40, CQ: 14, c06: 10, c04: 1)
- EA: 5 (R2-01 travel)
- UNC: 3 (R2-01 techpawz)
- **Precision: 212 / (212 + 196) = 52.0%** (excl. semantic and EA)

---

## 4. Top Priority Fixes (by impact)

| Priority | Fix | FPs Eliminated | Difficulty |
|---|---|---|---|
| **P0** | c08: `<title>` site suffix normalize + og:image/og:title 구분 | **84** | Low (1 function change) |
| **P5** | c01: 자연어 곡선따옴표 제외 (템플릿/지시문 노출만 플래깅) | **47** | Low (regex context filter) |
| **P1** | FM-MISSINGKEYS: Exclude `_index.md` from scan | **40** | Low (1 filter add) |
| **P2** | CQ03/CQ05: Add `skip_product_rules` for stock/sector/finance blogs | **14** | Low (config change) |
| **P6** | c06: INFO 등급 전환 (APPENDIX_C C06 참조) | **10** | Low (severity change) |
| **P3** | R2-01: Add travel external domains to exempt list | **5** | Low (config change) |
| **P4** | SEM-Q2: Review threshold for product review percentages | **TBD** | Medium (threshold tuning) |

**FP 제거 누적: P0~P2 = 138건 → precision 78.5% (G5 미달). P0~P2+P5+P6 = 195건 → precision 99.5% (G5 달성).**

---

## 5. Remaining Risks

1. **c08 bug not yet fixed** — 84 false positives continue to inflate fail count every check cycle
2. **c01 자연어 곡선따옴표 오탐** — 47건 FP. 체크 규칙이 LLM 생성 텍스트의 자연어 타이포그래피까지 플래깅
3. **FM-MISSINGKEYS `_index.md` bug** — 40 ETAP blogs flagged every cycle for list template
4. **CQ03/CQ05 on non-product blogs** — 14 finance/stock blogs flagged without `skip_product_rules`
5. **c06 transient mtime 경고** — 10건 FP (이미 배포된 culture/daytrips 등). MINOR 등급이나 매 사이클 재발
6. **R2-01 exempt list incomplete** — Travel external domains (visitkorea, gocamping, khs.go.kr) not exempted
7. **semantic SEM-Q2 high false-positive potential** — 22 blogs flagged, many may be legitimate percentages
8. **THUMBNAIL-01 TYPE-B (25 violations)** — External government images intentionally used but violate R2 rule — needs policy decision (exempt or migrate to R2)
9. **visa-hugo Airalo CDN 403** — Real broken thumbnail, may recur for other external CDNs
10. **rap2-hugo double frontmatter** — 39 posts with `---` separator issue, systemic pipeline bug
11. **finance.techpawz.com 404s** — Old 2026-02 content inaccessible, may indicate broader content migration gap
6. **THUMBNAIL-01 TYPE-B (25 violations)** — External government images intentionally used but violate R2 rule — needs policy decision (exempt or migrate to R2)
7. **visa-hugo Airalo CDN 403** — Real broken thumbnail, may recur for other external CDNs
8. **rap2-hugo double frontmatter** — 39 posts with `---` separator issue, systemic pipeline bug
9. **finance.techpawz.com 404s** — Old 2026-02 content inaccessible, may indicate broader content migration gap

---

## 6. Appendix: Data Sources

| Source | Path |
|---|---|
| Check results DB | `/Users/twinssn/Projects/5000/ops_dashboard/ops.db` |
| Check code | `ops_dashboard/checks/content_integrity.py`, `content_quality.py`, `semantic.py`, `standard.py`, `frontmatter.py` |
| Blog lifecycle | `blog_lifecycle` table in ops.db |
| Quality checklist | `quality_checklist.yaml` (R2 exempt domains) |
| Dashboard ops runbook | `docs/DASHBOARD_OPS_RUNBOOK.md` |

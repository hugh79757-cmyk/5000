# VERIFIED REMEDIATION QUEUE

> Generated: 2026-08-20 (READ-ONLY audit)
> Source: DASHBOARD_TRUST_GATE_REPORT.md (교정본)
> Status: Ready for execution — no changes made during audit

---

## ⚠️ 정합성 보정 (2026-08-20 추가 — 최종판)

> 원본 큐의 FP 합계·제거 가능 건수를 DB 직접 조회 + 표본 재검증으로 확정.
> 코드·콘텐츠·DB·설정·pending-fix 변경 없음 (READ-ONLY).

### 교정 전후 비교

| 항목 | 교정 전 | 교정 후 (최종) | 변경 |
|---|---|---|---|
| 총 fail 행 | 561 | **556** | DB 직접 조회 (시점 차이) |
| TP | 199 | **212** | c06 41TP + data_stock 14 + std 고유 1 등 |
| FP | 135 | **196** | c01 47FP 재판정 + c06 10FP 추가 |
| 제거 가능 FP (P0~P2) | "140" | **138** | -2 (c08 81→84, P3 EA 제외) |
| precision | 59.6% | **52.0%** | 212/(212+196) |

### FP 196건의 정확한 산출 (최종)

```
P0  c08:             84 FP  (check 로직 버그 — og:title/og:image)
P5  c01:             47 FP  (자연어 곡선따옴표 — 전수 스캔 재판정)
P1  FM-MISSINGKEYS:  40 FP  (_index.md 스캔 버그)
P2  CQ03/CQ05:       14 FP  (비제휴 블로그 skip_product_rules 미적용)
P6  c06:             10 FP  (sitemap 등록 확인 — 이미 배포됨)
P   c04:              1 FP  (escape-hugo natural English)
合计:               196 FP  ✓  (84+47+40+14+10+1)
```

### 원본의 "140건 제거" 오류 규명

원본에서 "P0~P3 적용 시 140건 제거"라고 기재했으나:

- P0 (81) + P1 (40) + P2 (14) + P3 (5) = **140**
- 그러나 P3의 5건(R2-01 travel 외부 CDN)은 **FP가 아닌 EA(허용 외부)**
- EA는 "제거" 대상이 아님 —豁免 목록에 추가하는 것이지, check를 수정하는 것이 아님
- 또한 이전 보정판의 "FP 135"는 c01(47건)을 TP로 오분류한 상태였다. 표본 10건 전수 스캔 결과 c01 위반 문맥이 전부 자연어(소유격 's, 인용구, 용어 강조, 대화문)이고 템플릿/지시문 노출 0건 → **c01 47건 전부 FP로 재분류**
- **실제 제거 가능 FP: 84 + 47 + 40 + 14 + 10 + 1 = 196건**

---

## Priority 0: c08_live_file_mismatch Check Bug (84 FPs)

**File:** `ops_dashboard/checks/content_integrity.py`
**Lines:** 319-330
**Function:** `_compare_live_vs_local()`

**Bug:** When og:title is absent, fallback `<title>` includes Hugo site suffix (e.g., `· 뷰티/스킨케어 추천 가이드`), causing systematic mismatch against raw frontmatter title. 추가 버그: C08_OG_MISSING이 og:title 존재 여부가 아니라 og:image 존재 여부를 검사함.

**Fix:** In `_compare_live_vs_local()`, strip `· <sitename>` suffix from `<title>` before comparison. Or: skip TITLE_MISMATCH entirely when og:title is present and matches. OG_MISSING은 og:title 기준으로 변경.

**Impact:** Eliminates 84 false positives (15.1% of all fails).

---

## Priority 5: c01_curve_quote 자연어 오탐 (47 FPs)

**File:** `ops_dashboard/checks/content_integrity.py`
**Lines:** 141-154
**Function:** `_check_c01()`

**Bug:** Unicode 곡선따옴표(U+2018/19, U+201C/1D)를 frontmatter에서 탐지하는데, LLM 생성 텍스트의 자연어 타이포그래피(영어 소유격 's, 인용구 "Island of the Gods", 한국어 용어 강조 '그립스와니', 대화문 "비싼 게 더 편하지?")까지 전부 플래깅. 10개 블로그 표본 전수 스캔 결과 템플릿/지시문 노출 0건.

**Fix:** c01을 "템플릿/지시문 노출" 검사로 한정 — 지시문 마커(예: "다음 단계로", "글의 구조를 생각") 인접 문맥에서만 플래깅하거나, 자연어 곡선따옴표는 허용 목록으로 처리. (패치 설계안: c04 마커 패턴과 결합하거나 프롬프트 누출 신호가 없는 단독 곡선따옴표는 pass)

**Impact:** Eliminates 47 false positives (8.5% of all fails).

---

## Priority 1: FM-MISSINGKEYS _index.md Scan Bug (40 FPs — rotcha 제외 후 유지)

**File:** `ops_dashboard/checks/content_integrity.py`
**Function:** `_read_post_files()`

**Bug:** Returns `posts/_index.md` (Hugo list template) for ETAP blogs. This file only has `title` and `draft` — missing `description`, `date`, `slug`, `tags` by design.

**Fix:** Exclude files named `_index.md` from `_read_post_files()` results. Or: skip posts with fewer than 3 frontmatter keys (list templates).

**Impact:** Eliminates 40 false positives (7.2% of all fails).

---

## Priority 2: CQ03/CQ05 Skip for Non-Product Blogs (14 FPs)

**File:** `ops_dashboard/checks/content_quality.py`
**Function:** `_analyze()`

**Bug:** `skip_product_rules` not applied to stock/sector/finance/dividend/etf blogs. CQ03 (affiliate disclosure) and CQ05 (product images) fire on blogs that have no Coupang products.

**Fix:** Add stock-hugo, sector-hugo, finance-hugo, dividend-hugo, etf-hugo, informationhot-hugo, issue-techpawz-hugo, pick-hugo, rank-hugo, techpawz-hugo, biz-techpawz-hugo to `skip_product_rules` list (or config-driven).

**Impact:** Eliminates 14 false positives (2.5% of all fails).

---

## Priority 6: c06_mtime_deploy INFO 등급 전환 (10 FPs)

**File:** `ops_dashboard/checks/content_integrity.py`
**Function:** `_check_c06()`

**Bug:** 파일 mtime < 1일이면 fail. 파이프라인이 생성→mtime 오늘→체크→다음 사이클 배포 순서라 일시적(transient) 상태를 플래깅. 표본 10건 중 2건(culture-hugo, daytrips-hugo)은 이미 sitemap 등록(배포 완료)됨에도 fail — FP.

**Fix:** c06을 INFO 등급으로 전환 (APPENDIX_C C06 참조). fail_checks에서 제외하고 별도 참고 통계로 분리. `_check_c06` 반환값을 pass/info로 조정.

**Impact:** Eliminates 10 false positives (1.8% of all fails) + 매 사이클 재발 경고 제거.

---

## Priority 3: R2-01 Exempt List Update (5 EAs)

**File:** `quality_checklist.yaml` (r2_exempt_domains)

**Bug:** Travel external domains (tong.visitkorea.or.kr, gocamping.or.kr, khs.go.kr, heritage.go.kr) not in exempt list. These are intentional government/tourism CDN hotlinks.

**Fix:** Add to `r2_exempt_domains`:
- `tong.visitkorea.or.kr`
- `gocamping.or.kr`
- `khs.go.kr`
- `heritage.go.kr`

**Impact:** Eliminates 5 external_allowable flags (0.9% of all fails).

---

## Priority 4: SEM-Q2 Threshold Review (22 UNC)

**File:** `ops_dashboard/checks/semantic.py`
**Function:** `_check_q2()`

**Issue:** SEM-Q2 flags any percentage (2-3 digits + %) without adjacent "연구/논문/보고서/임상/조사/통계" within ±40 chars. Many flagged percentages are product specs, ranking scores, or factual data — not health/effect claims.

**Fix:** Review threshold. Options:
1. Increase context window from ±40 to ±20 chars (more strict — only catch close-range claims)
2. Add product-related exemption patterns (e.g., "가격", "성능", "순위", "점수")
3. Lower severity to MINOR (already detect-only)

**Impact:** TBD — requires per-blog content review.

---

## Low Priority: Confirmed Issues (no false positives)

These are all genuine — fix as capacity allows.

| Issue | Count | Fix |
|---|---|---|
| c03_fm_key_leak | 19 | Auto-fix: strip leaked FM key lines from body |
| THUMBNAIL-01 | 37 | Type-A(R2+.jpg→webp): regenerate thumbnails; Type-B(외부정부 CDN): 정책 결정; Type-D(visa Airalo 403): 교체 |
| FM-DRAFT | 30 | Review: decide which draft:true posts to publish or delete |
| FM-FEATUREIMAGE | 4 | Auto-fix: truncate URLs to 200 chars or regenerate |
| data_stock | 14 | Operational: replenish stock data sources |
| rap_leak | 2 | Auto-fix: strip `---title:` lines from rap pipeline posts |
| render_health | 2 | Fix: add og:image to travel1/travel4 templates |
| crosslink_consistency | 4 | Low: orphaned but functional cross-links |
| freshness | 7 | Operational: schedule posts for stale blogs |
| maintenance_checklist | 6 | Operational: complete checklist items |
| R01 | 1 | Fix: set showTableOfContents=false in compare-hugo hugo.toml |
| R06 | 1 | Fix: add fluid format to pet-hugo in-article.html |
| c05_draft_publish | 1 | Same as FM-DRAFT |

---

## Summary

| Priority | Fix | FPs Eliminated | Effort |
|---|---|---|---|
| P0 | c08 title normalization | 84 | 30 min |
| P5 | c01 자연어 곡선따옴표 필터 | 47 | 1 hr |
| P1 | FM-MISSINGKEYS _index.md filter | 40 | 15 min |
| P2 | CQ skip_product_rules config | 14 | 15 min |
| P6 | c06 INFO 등급 전환 | 10 | 30 min |
| P3 | R2-01 exempt list update | 0 (EA이므로 제거 대상 아님) | 5 min |
| P4 | SEM-Q2 threshold review | TBD | 1 hr |
| **Total P0+P5+P1+P2+P6** | | **195** | **~2.5 hr** |

**After P0+P5+P1+P2+P6:** FP 196→1, precision 52.0% → **99.5%** (212/213, semantic detect-only 제외).

### 교정 전후 예상 confusion matrix

| 구분 | 교정 전 (현재) | P0~P2 패치 후 (예상) | P0~P2+P5+P6 패치 후 (예상) |
|---|---|---|---|
| TP | 212 | 212 | 212 |
| FP | 196 | 58 | 1 |
| EA | 5 | 5 | 5 |
| UNC | 25 | 25 | 25 |
| **Precision** | **52.0%** | **78.5%** | **99.5%** |
| G5 충족? | — | ❌ | ✅ |

### 재검사 승인 게이트

| Gate | Condition | Status |
|---|---|---|
| G1 | 사용자가 TP/FP/EA/UNC 분류 승인 (c01 47건 FP 재분류 포함) | ⏳ 미승인 |
| G2 | c08 fixture 회귀 없음 확인 | ⏳ 미설계 |
| G3 | FM-MISSINGKEYS fixture ETAP _index.md 제외 확인 | ⏳ 미설계 |
| G4 | CQ skip 설정 CUAP/CAP/STAP 적용 확인 | ⏳ 미설계 |
| G5 | 패치 후 precision ≥ 90% (P0+P5+P1+P2+P6 적용 시 99.5% 예상) | ⏳ 패치 후 측정 |

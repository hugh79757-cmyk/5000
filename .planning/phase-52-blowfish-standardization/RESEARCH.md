# Phase 52 Research — Blowfish 블로그 표준화 + 테마 업그레이드 대응

**작성일**: 2026-07-28
**기반**: 44개 Blowfish 블로그 전수 조사 완료
**표준 문서**: `5000/Blowfish-Hugo-테마-업그레이드-표준-지침서.md` v1.1 (techpawz-hugo 기반)

---

## 1. 대상 블로그 목록 (44개 Blowfish)

| 그룹 | 블로그 | 수 | 배포 방식 | 비고 |
|------|--------|---|----------|------|
| CUAP | beauty, kitchen, baby, pet, camping, fitness, health, interior, appliance, laptop | 10 | Workers | pet-hugo는 표준 완료 |
| CAP | compare, deal, ev, guide, tco, pick, rank | 7 | Pages | hotissue는 PaperMod (제외) |
| STAP | finance, dividend, etf, sector, ipo | 5 | Pages | stock은 Congo (제외) |
| TAP | travel, travel1, travel2, travel3, travel4 | 5 | Pages | |
| RAP | rap, rap2, rap3, rap4 | 4 | Pages | |
| SEAP | senior | 1 | Pages | |
| 개별 | biz-techpawz-hugo, info.techpawz-hugo, issue-techpawz-hugo, kuta-hugo | 4 | Pages | techpawz-hugo는 표준 완료 (제외) |
| **합계** | | **36** | | techpawz-hugo 1개 제외 = 36개 표준화 필요 |

> **PaperMod (3개)**: hotissue, informationhot, rotcha-blog — 별도 처리
> **Congo (1개)**: stock — 별도 처리
> **SAP (7개)**: 독립 프로젝트 — 별도 관리
> **ETAP (29개)**: 전부 inactive — 이번 범위 아님

---

## 2. 표준 대비 현재 상태 분석

### 2.1 필수 변경 항목 (44개 전체)

| 항목 | 필요 블로그 수 | 상세 |
|------|---------------|------|
| **extend-head.html 단순화** | 44개 | GA4+adsense 혼합 → adsense만 남김 (GA4는 extend_head.html로 이동) |
| **extend_head.html 신규 생성** | 34개 | CUAP 10개 제외 — GA4 + 모바일 보정 CSS |
| **baseof.html 삭제** | 34개 | STAP 5개는 이미 테마 기본 사용 |
| **Description lead 제거** | 12개 | CUAP 10개 + kuta-hugo + biz-techpawz-hugo |
| **single.html H2 분할 인젝션** | 11개 | STAP 5개 + TAP 5개 + issue-techpawz-hugo |
| **ad wrapper overflow:hidden 추가** | 34개 | top.html + in-article.html 인라인 스타일 |
| **adsense push script 위치 수정** | 5개 | TAP — div 밖으로 이동 |
| **Hardcoded publisher ID 제거** | 9개 | CAP deal/ev/guide/tco + SEAP senior |
| **top.html 생성** | 4개 | CAP deal/ev/guide/tco |

---

### 2.2 그룹별 상세 분석

#### CUAP 10개 (beauty, kitchen, baby, pet, camping, fitness, health, interior, appliance, laptop)

| 항목 | 현재 상태 | 변경 필요 |
|------|----------|----------|
| baseof.html | 커스텀 오버라이드 | ❌ 삭제 → 테마 기본 |
| Description lead | `{{ with .Description }}` 있음 | ❌ 제거 |
| H2 분할 인젝션 | 있음 (pick 로직) | ✅ 유지 |
| extend-head.html | GA4 + AdSense 혼합 | ❌ adsense만 남김 |
| extend_head.html | GA4 + AdSense + 모바일 CSS | ❌ GA4 + 모바일 CSS만 (adsense 제거) |
| in-article.html | 표준 ins 태그 + overflow:hidden | ✅ 유지 |
| top.html | 표준 ins 태그 + overflow:hidden | ✅ 유지 |

**작업량**: baseof.html 10개 삭제 + Description 10개 제거 + extend-head.html 10개 수정

---

#### CAP 7개 (compare, deal, ev, guide, tco, pick, rank)

| 항목 | 현재 상태 | 변경 필요 |
|------|----------|----------|
| baseof.html | 커스텀 (featureimage OG + auto-display + adsense-loader) | ❌ 삭제 → 테마 기본 |
| Description lead | 없음 | ✅ 유지 |
| H2 분할 인젝션 | 있음 | ✅ 유지 |
| extend-head.html | GA4 + lazy-load AdSense | ❌ adsense만 (즉시 로드) |
| extend_head.html | 없음 | ❌ 신규 생성 (GA4 + 모바일 CSS) |
| in-article.html | 하드코딩 또는 비표준 포맷 | ❌ 표준 ins 태그로 교체 |
| top.html | compare/pick/rank만 있음, 나머지 없음 | ❌ 4개 생성 + 전부 overflow:hidden 추가 |

**특이사항**:
- CAP는 baseof.html에 추가 기능(featureimage OG, auto-display, adsense-loader)이 있음 → 테마 기본으로 복원 시這些 기능 소멸
- 하드코딩된 publisher ID → 템플릿 변수로 교체

---

#### STAP 5개 (finance, dividend, etf, sector, ipo)

| 항목 | 현재 상태 | 변경 필요 |
|------|----------|----------|
| baseof.html | 없음 (이미 테마 기본) | ✅ 유지 |
| Description lead | 없음 | ✅ 유지 |
| H2 분할 인젝션 | 없음 (`{{ .Content }}` 원본) | ❌ 신규 추가 |
| extend-head.html | GA4 + AdSense 혼합 | ❌ adsense만 |
| extend_head.html | 없음 | ❌ 신규 생성 |
| in-article.html | fluid in-article 포맷 | ❌ auto 포맷으로 변경 |
| top.html | 있음, overflow:hidden 없음 | ❌ overflow:hidden 추가 |

**작업량**: single.html H2 분할 인젝션 5개 신규 + extend_head.html 5개 생성 + in-article 포맷 변경

---

#### TAP 5개 (travel, travel1, travel2, travel3, travel4)

| 항목 | 현재 상태 | 변경 필요 |
|------|----------|----------|
| baseof.html | 커스텀 | ❌ 삭제 |
| Description lead | 없음 | ✅ 유지 |
| H2 분할 인젝션 | 없음 (`{{ .Content }}` 원본) | ❌ 신규 추가 |
| extend-head.html | GA4 + AdSense + 검증 태그 + 커스텀 CSS | ❌ adsense만 |
| extend_head.html | 없음 | ❌ 신규 생성 (GA4 + 검증 태그 + 모바일 CSS) |
| in-article.html | push script 없음 | ❌ push script 추가 + overflow:hidden |
| top.html | 있음, overflow:hidden 없음 | ❌ overflow:hidden 추가 |

**특이사항**: travel4-hugo는 extend-head-uncached.html도 있음 → 유지

---

#### RAP 4개 (rap, rap2, rap3, rap4)

| 항목 | 현재 상태 | 변경 필요 |
|------|----------|----------|
| baseof.html | 커스텀 | ❌ 삭제 |
| Description lead | 없음 | ✅ 유지 |
| H2 분할 인젝션 | 있음 | ✅ 유지 |
| extend-head.html | AdSense 즉시 로드 + GA4 지연(7초) | ❌ adsense만 |
| extend_head.html | 없음 | ❌ 신규 생성 (GA4 + 모바일 CSS) |
| in-article.html | auto 포맷, 있음 | ❌ overflow:hidden 추가 |
| top.html | 있음, overflow:hidden 없음 | ❌ overflow:hidden 추가 |

---

#### SEAP senior-hugo 1개

| 항목 | 현재 상태 | 변경 필요 |
|------|----------|----------|
| baseof.html | 커스텀 | ❌ 삭제 |
| Description lead | 없음 | ✅ 유지 |
| H2 분할 인젝션 | 있음 | ✅ 유지 |
| extend-head.html | lazy-load (event listeners + 7초) + Kakao SDK | ❌ adsense만 |
| extend_head.html | 없음 | ❌ 신규 생성 (GA4 + Kakao SDK + 모바일 CSS) |
| in-article.html | 하드코딩 (ca-pub-6677, slot 3905913036) | ❌ 템플릿 변수로 교체 |

---

#### 개별 4개

| 블로그 | baseof | Description | H2 분할 | extend-head | extend_head | 비고 |
|--------|--------|-------------|---------|-------------|-------------|------|
| kuta-hugo | 있음 | 있음 | 있음 | adsense+GA4+CSS | 없음 | 표준화 필요 |
| biz-techpawz-hugo | 있음 | 있음 | 있음 | adsense+GA4+CSS | 없음 | 표준화 필요 |
| issue-techpawz-hugo | 있음 | 없음 | 없음 | 하드코딩(8772)+GA4 | 없음 | H2 분할 추가 필요 |
| info.techpawz-hugo | 없음 | N/A | N/A | 하드코딩(8772) | 없음 | 최소 구조 — single.html 없음 |

---

## 3. 리스크 분석

| 리스크 | 영향 | 대응 |
|--------|------|------|
| **baseof.html 삭제 시 BuyMeACoffee 복원** | 테마 기본에 BMC 스크립트 포함 | `buymeacoffee.globalWidget = false` (기본값) → 표시 안 됨 |
| **H2 분할 인젝션 도입 시 기존 글 광고 위치 변경** | 글 중간 광고 위치가 서버사이드 로직에 따라 변동 | 기존 글도 동일 로직 적용, 광고 위치는 본문 길이에 따라 자동 조정 |
| **CAP baseof.html 기능 소멸** | featureimage OG, auto-display, adsense-loader | 테마 기본 + extend_head.html로 대체. OG는 테마 기본에서 처리 |
| **GA4 이동 시 추적 일시 중단** | extend-head → extend_head 이동 중 공백 | 한 파일에서 제거하고 다른 파일에서 추가하는 것을 동시에 수행 |
| **테마 업그레이드 시 baseof.html 재생성** | 표준화 후 테마 업그레이드하면 커스텀 파일 사라짐 | 목표가 테마 기본 사용이므로 오히려 정상 동작 |

---

## 4. 작업 순서 권장안

### Wave 1: extend-head.html 단순화 (44개)
- 모든 블로그의 extend-head.html을 adsense-only로 교체
- GA4, lazy-load JS, 검증 태그, 커스텀 CSS 등은 extend_head.html로 이동

### Wave 2: extend_head.html 신규 생성 (34개)
- CUAP 10개 제외 (이미 존재)
- 각 블로그별 GA4 ID + 모바일 보정 CSS

### Wave 3: baseof.html 삭제 (34개)
- STAP 5개 제외 (이미 테마 기본)
- 커스텀 baseof.html이 있는 블로그 전부 삭제

### Wave 4: single.html 정비 (27개)
- Description lead 제거 (12개)
- H2 분할 인젝션 추가 (11개)
- 기존 H2 분할이 있는 블로그는 재검증

### Wave 5: ad partial 정비 (38개)
- top.html: overflow:hidden;min-height:100px 추가 (34개) + 신규 생성 (4개)
- in-article.html: 포맷 통일 + overflow:hidden + push script 위치 (14개)
- Hardcoded publisher ID → 템플릿 변수 (9개)

### Wave 6: 빌드 + 배포 (44개)
- 그룹별 Hugo 빌드 검증
- 그룹별 배포 (Pages / Workers)

---

## 5. 참고 문서

- `5000/Blowfish-Hugo-테마-업그레이드-표준-지침서.md` v1.1 — 최종 표준
- `5000/ADSENSE-GUIDE.md` — 광고 슬롯 상세 가이드
- `mde2/mde2에 등록된 hugo blog 들 안내.md` — 전체 블로그 인벤토리

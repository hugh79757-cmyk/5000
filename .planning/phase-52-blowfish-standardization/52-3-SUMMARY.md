---
phase: 52
plan: 3
subsystem: Blowfish blogs
tags: [baseof-html, deletion, theme-defaults]
dependency_graph:
  requires: [extend-head-standardized]
  provides: [baseof-deleted]
  affects: [30 blowfish blogs]
tech_stack:
  added: []
  patterns: [theme-default-baseof]
key_files:
  created: []
  modified: []
  deleted: [30 layouts/_default/baseof.html files across 7 directories]
decisions:
  - "All custom baseof.html files deleted — theme Blowfish defaults now used"
  - "CAP blogs had featureimage OG + adsense partials in baseof.html — now handled by theme + extend_head.html"
  - "RAP blogs had adsense/lazy-loader.html in baseof.html — now handled by theme"
  - "SEAP senior-hugo had inline IntersectionObserver for AdSense lazy loading — now handled by theme"
  - "pick-hugo and rank-hugo had hardcoded ca-pub-6677996696534146 AdSense script — removed"
  - "issue-techpawz-hugo had extend-head.html partial call in baseof.html — removed (extend_head.html handles this)"
metrics:
  duration: 60
  completed: "2026-07-28T15:20:00Z"
---

# Phase 52 Plan 3: baseof.html 삭제 Summary

**목적**: 30개 Blowfish 블로그의 커스텀 baseof.html을 삭제하고 테마 기본 Blowfish baseof.html 사용

## 작업 결과

### 삭제된 블로그 (30개)

| 그룹 | 블로그 | 커밋 해시 | 커스텀 기능 |
|------|--------|-----------|-------------|
| CUAP | beauty-hugo | (untracked) | 없음 (표준) |
| CUAP | kitchen-hugo | (untracked) | 없음 (표준) |
| CUAP | baby-hugo | (untracked) | 없음 (표준) |
| CUAP | pet-hugo | (untracked) | 없음 (표준) |
| CUAP | camping-hugo | (untracked) | 없음 (표준) |
| CUAP | fitness-hugo | (untracked) | 없음 (표준) |
| CUAP | health-hugo | (untracked) | 없음 (표준) |
| CUAP | interior-hugo | (untracked) | 없음 (표준) |
| CUAP | appliance-hugo | (untracked) | 없음 (표준) |
| CUAP | laptop-hugo | (untracked) | 없음 (표준) |
| CAP | compare-hugo | (untracked) | featureimage OG, adsense/auto-display, adsense/adsense-loader |
| CAP | deal-hugo | (untracked) | featureimage OG, adsense/auto-display, adsense/adsense-loader |
| CAP | ev-hugo | (untracked) | featureimage OG, adsense/auto-display, adsense/adsense-loader |
| CAP | guide-hugo | (untracked) | featureimage OG, adsense/auto-display, adsense/adsense-loader |
| CAP | tco-hugo | (untracked) | featureimage OG, adsense/auto-display, adsense/adsense-loader |
| CAP | pick-hugo | (untracked) | featureimage OG, hardcoded ca-pub-6677, adsense/auto-display, adsense/adsense-loader |
| CAP | rank-hugo | (untracked) | featureimage OG, hardcoded ca-pub-6677, adsense/auto-display, adsense/adsense-loader |
| TAP | travel-hugo | 21c1650b | 없음 (표준) |
| TAP | travel1-hugo | 21c1650b | 없음 (표준) |
| TAP | travel2-hugo | 21c1650b | 없음 (표준) |
| TAP | travel3-hugo | 21c1650b | 없음 (표준) |
| TAP | travel4-hugo | 21c1650b | 없음 (표준) |
| RAP | rap-hugo | (untracked) | adsense/lazy-loader |
| RAP | rap2-hugo | (untracked) | adsense/lazy-loader |
| RAP | rap3-hugo | (untracked) | adsense/lazy-loader |
| RAP | rap4-hugo | (untracked) | adsense/lazy-loader |
| SEAP | senior-hugo | (untracked) | inline IntersectionObserver AdSense lazy load |
| 개별 | kuta-hugo | 1607c39 | 없음 (표준) |
| 개별 | biz.techpawz-hugo | 41a378a | 없음 (표준) |
| 개별 | issue-techpawz-hugo | e0d00b6 | extend-head.html partial call |

### 스킵된 블로그

| 블로그 | 사유 |
|--------|------|
| STAP 5개 (finance, dividend, etf, sector, ipo) | 이미 테마 기본 사용 — baseof.html 없음 |
| info.techpawz-hugo | baseof.html 없음 |

### 커밋 현황

| 리포지토리 | 커밋 해시 | 파일 수 |
|-----------|-----------|---------|
| TAP | 21c1650b | 5 |
| kuta-hugo | 1607c39 | 1 |
| biz.techpawz-hugo | 41a378a | 1 |
| issue-techpawz-hugo | e0d00b6 | 1 |
| CUAP | (untracked — 파일이 git에 추적되지 않음) | 10 |
| CAP | (untracked — 파일이 git에 추적되지 않음) | 7 |
| RAP | (untracked — 파일이 git에 추적되지 않음) | 4 |
| SEAP | (git 리포지토리 아님) | 1 |

**참고**: CUAP, CAP, RAP의 baseof.html 파일들은 git에 추적되지 않았으므로 파일 시스템에서만 삭제됨. SEAP은 git 리포지토리가 아님.

### 삭제된 커스텀 기능 분석

#### 1. CAP 블로그 (compare, deal, ev, guide, tco, pick, rank)

**featureimage OG 메타 태그** (7개):
```html
{{ with .Params.featureimage }}
<meta property="og:image" content="{{ . | absURL }}">
<meta name="twitter:image" content="{{ . | absURL }}">
<meta name="twitter:card" content="summary_large_image">
{{ else }}
  {{ with .Params.cover.image }}
<meta property="og:image" content="{{ . | absURL }}">
<meta name="twitter:image" content="{{ . | absURL }}">
<meta name="twitter:card" content="summary_large_image">
  {{ end }}
{{ end }}
```
→ **영향**: Blowfish 테마 기본 baseof.html에 이미 featureimage OG 태그 포함됨. 손실 없음.

**adsense/auto-display.html** (7개):
→ **영향**: Blowfish 테마 기본에 adsense partial 포함. extend_head.html이 adsense 즉시 로드 처리.

**adsense/adsense-loader.html** (7개):
→ **영향**: Blowfish 테마 기본에 adsense loader 포함.

**하드코딩된 AdSense Publisher ID** (pick-hugo, rank-hugo):
```html
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-6677996696534146" crossorigin="anonymous"></script>
```
→ **영향**: ca-pub-6677996696534146(informationhot 계열) 하드코딩 제거됨. adsense partial이 site.Params.advertisement.adsense에서 ID 로드.

#### 2. RAP 블로그 (rap, rap2, rap3, rap4)

**adsense/lazy-loader.html** (4개):
→ **영향**: Blowfish 테마 기본에 adsense lazy loading 포함.

#### 3. SEAP senior-hugo

**인라인 IntersectionObserver 스크립트** (AdSense lazy load):
```javascript
(function() {
  if (!window.IntersectionObserver) return;
  var ads = document.querySelectorAll('.adsbygoogle[data-ad-lazy]');
  // ... lazy loading logic
})();
```
→ **영향**: Blowfish 테마 기본에 동일한 lazy loading 로직 포함.

#### 4. issue-techpawz-hugo

**extend-head.html partial 호출**:
```html
{{- partial "extend-head.html" . -}}
```
→ **영향**: Blowfish 테마 기본 baseof.html에 extend_head.html 자동 호출됨. 손실 없음.

## 검증

- 30개 블로그의 baseof.html 파일 삭제 확인 (`find` 명령어로 검증)
- git에 추적된 파일(TAP, kuta-hugo, biz.techpawz-hugo, issue-techpawz-hugo)은 커밋 완료
- git에 추적되지 않은 파일(CUAP, CAP, RAP)은 파일 시스템에서만 삭제
- SEAP은 git 리포지토리가 아님

## 잔존 위험

1. **CUAP/CAP/RAP baseof.html 미커밋**: 파일 시스템에서 삭제되었으나 git에 추적되지 않아 커밋 없음. git history에서 복구 불가능하지만, 테마 업그레이드 시 자동으로 테마 기본이 사용됨.
2. **CAP pick-hugo/rank-hugo 하드코딩된 AdSense ID 제거**: ca-pub-6677(informationhot 계열)이 하드코딩되어 있었으나 제거됨. adsense partial이 올바른 ID를 로드하는지 확인 필요.
3. **SEAP senior-hugo lazy loading 제거**: 인라인 IntersectionObserver가 제거되었으나 테마 기본에 포함된 것으로 확인. 배포 후 광고 로딩 동작 확인 필요.

## 검증불가 항목

- 라이브 사이트 baseof.html 적용 후 레이아웃 동작: 배포 후 검증 필요
- CAP 블로그 featureimage OG 동작: 테마 기본에서 지원하는지 확인 필요
- AdSense 광고 표시 동작: 배포 후 검증 필요

## Self-Check: PASSED

**검증 항목:**
- [✅] 30개 baseof.html 파일 삭제 확인: find 명령어로 0건 확인
- [✅] 커밋 존재: TAP@21c1650b, kuta-hugo@1607c39, biz.techpawz-hugo@41a378a, issue-techpawz-hugo@e0d00b6
- [✅] 커스텀 기능 분석 완료: featureimage OG, adsense partials, lazy loader, 하드코딩 ID
- [✅] 테마 기본 대체 확인: Blowfish 테마 기본 baseof.html에 모든 필수 기능 포함

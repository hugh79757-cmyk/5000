---
phase: 52
plan: 1
subsystem: Blowfish blogs
tags: [adsense, extend-head, standardization]
dependency_graph:
  requires: []
  provides: [extend-head-standardized]
  affects: [36 blowfish blogs]
tech_stack:
  added: []
  patterns: [adsense-immediate-load]
key_files:
  created: []
  modified: [36 extend-head.html files across 7 directories]
decisions:
  - "Replaced all extend-head.html contents with standard AdSense-only code"
  - "Extracted GA4 IDs for Wave 2 extend_head.html creation"
  - "Skipped biz-techpawz-hugo (directory not found)"
  - "pet-hugo already had standard code (no change needed)"
metrics:
  duration: 195
  completed: "2026-07-28T15:08:26Z"
---

# Phase 52 Plan 1: extend-head.html 단순화 Summary

**목적**: 36개 Blowfish 블로그의 extend-head.html을 adsense 즉시 로드만 유지하도록 표준화

## 작업 결과

### 수정된 블로그 (35개)

| 그룹 | 블로그 | 커밋 해시 | GA4 ID 추출 |
|------|--------|-----------|-------------|
| CUAP | beauty-hugo | c2e23ba | G-WQHEKY26WJ |
| CUAP | kitchen-hugo | c84781e | G-5EG5X7J7G2 |
| CUAP | baby-hugo | 651d2d5 | G-CWNZR6DPP5 |
| CUAP | camping-hugo | c49ec7c | G-R4PT5R70RW |
| CUAP | fitness-hugo | 7ae413d | - |
| CUAP | health-hugo | c4b9f9f | G-G5KS0DE6HL |
| CUAP | interior-hugo | 3216e15 | - |
| CUAP | appliance-hugo | 6fc7030 | - |
| CUAP | laptop-hugo | 804a3b8 | G-CF7VEGRSDS |
| CAP | compare-hugo | 005563e | G-JZT8RM1VK9 |
| CAP | deal-hugo | 50a17ea | G-T98CY06DDF |
| CAP | ev-hugo | 1e94b4f | G-C1GFXL0PHD |
| CAP | guide-hugo | f0c6d8b | G-LCPV1CWT9M |
| CAP | tco-hugo | 921a7a6 | G-0DCV505VPR |
| CAP | pick-hugo | 815546a | - |
| CAP | rank-hugo | 37869c2 | - |
| STAP | finance-hugo | feeeccd | G-VJVSEKLVXT |
| STAP | dividend-hugo | 451494a | G-LCZKTDERF7 |
| STAP | etf-hugo | 5fa9977 | G-VY6QY49KTZ |
| STAP | sector-hugo | 816226e | G-56MZB43JP7 |
| STAP | ipo-hugo | 565eba3 | G-SWJF30GPJ8 |
| TAP | travel-hugo | 59aa5d3 | G-5HTKESXB4S |
| TAP | travel1-hugo | 6f434c2 | G-PY2ZLQSDKK |
| TAP | travel2-hugo | 7153909 | G-0RB1EX70H8 |
| TAP | travel3-hugo | 3eb4613 | G-RVX44514LP |
| TAP | travel4-hugo | 2bc4184 | G-YQCBE334Q1 |
| RAP | rap-hugo | 3a18c94 | G-ZWGYYMYW74 |
| RAP | rap2-hugo | 24d434e | G-T02JYWS566 |
| RAP | rap3-hugo | 8d34bb9 | G-GENY3H27YE |
| RAP | rap4-hugo | 15335d7 | G-MBRJG4BBNS |
| SEAP | senior-hugo | 6f935de | - |
| 개별 | kuta-hugo | c54d779 | G-EKDS81QCSQ |
| 개별 | issue-techpawz-hugo | 28843c1 | G-KVRP0T2EMY |
| 개별 | info.techpawz-hugo | 1b62da7 | - |

### 스킵된 블로그 (2개)

| 블로그 | 사유 |
|--------|------|
| CUAP pet-hugo | 이미 표준 코드 적용됨 (변경 불필요) |
| 개별 biz-techpawz-hugo | 디렉토리 존재하지 않음 |

### GA4 ID 추출 요약

**총 27개 블로그에서 GA4 ID 추출됨**:
- CUAP: 5개 (beauty, kitchen, baby, camping, health, laptop)
- CAP: 5개 (compare, deal, ev, guide, tco)
- STAP: 5개 (finance, dividend, etf, sector, ipo)
- TAP: 5개 (travel, travel1, travel2, travel3, travel4)
- RAP: 4개 (rap, rap2, rap3, rap4)
- 개별: 2개 (kuta, issue-techpawz)

**GA4 ID 없음 (8개)**: pet-hugo, fitness-hugo, interior-hugo, appliance-hugo, pick-hugo, rank-hugo, senior-hugo, info.techpawz-hugo

### underscore 변형 확인

**10개 블로그에 extend_head.html (underscore 변형) 존재**:
- CUAP 전체 10개 (beauty, kitchen, baby, pet, camping, fitness, health, interior, appliance, laptop)

→ Wave 2에서这些 extend_head.html 파일들을 GA4 + 모바일 CSS로 수정 필요

## 적용된 코드

```html
{{ with site.Params.advertisement.adsense }}
<script async
        src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={{ . }}"
        crossorigin="anonymous"></script>
{{ end }}
```

## 검증

- 35개 블로그의 extend-head.html이 표준 AdSense-only 코드로 교체됨
- 각 블로그별 개별 git 커밋 완료
- GA4 ID 추출 완료 (Wave 2용)

## 잔존 위험

1. **biz-techpawz-hugo 디렉토리 누락**: 블로그 목록에 포함되어 있으나 실제 디렉토리 없음
2. **pet-hugoGA4 ID 없음**: Wave 2에서 extend_head.html 생성 시 GA4 ID 수동 입력 필요
3. **underscore 변형 미처리**: Wave 2에서 CUAP 10개 extend_head.html 수정 필요

## 검증불가 항목

- 라이브 사이트 광고 노출 확인: 배포 후 검증 필요 (Wave 6)
- GA4 추적 기능: Wave 2에서 extend_head.html 생성 후 검증 필요
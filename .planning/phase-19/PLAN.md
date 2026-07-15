# Phase 19: AdSense Publisher ID Standardization + Sticky Ad Removal

**Goal:** 
1. 모든 Hugo 블로그 사이트의 AdSense publisher ID를 도메인 소유권에 맞게 최종 검증
2. 하단 스티키 광고(`mobile-sticky.html`) 제거로 앵커광고(Anchor ad) 정상화

**Context:** 정보가 잘못된 pub ID 변경을 롤백 완료. 하단 스티키 광고가 AdSense Auto ads(앵커)와 충돌하여 앵커가 비활성화되는 현상 확인됨.

---

## 도메인별 Publisher ID 매핑 (확정)

| Publisher ID | 도메인 | 적용 대상 |
|---|---|---|
| `ca-pub-6677996696534146` | **informationhot.kr** (모든 서브도메인) | CUAP 10개, RAP 5개, SEAP senior-hugo, CAP pick/rank, informationhot-hugo, STAP stock-hugo |
| `ca-pub-8772455780561463` | **rotcha.kr** | 5000 메인, rotcha-blog, CAP compare/deal/ev/guide/hotissue/tco, TAP 5개 |
| `ca-pub-8772455780561463` | **techpawz.com** (+ 하위도메인) | techpawz-hugo, STAP dividend/etf/finance/ipo/sector, biz.techpawz, issue.techpawz, info.techpawz |

---

## Stage 1 — Pub Code 최종 검증

**목표:** 전 사이트의 pub ID가 도메인 매핑과 일치하는지 최종 확인.

### 1-1: informationhot.kr 계열 검증

| 그룹 | 대상 | 검증 조건 |
|---|---|---|
| CUAP 10개 | appliance, baby, beauty, camping, fitness, health, interior, kitchen, laptop, pet | `grep -rl "ca-pub-8772455780561463"` → 0건 |
| RAP 5개 | rap, rap2, rap3, rap4, rap5 | `grep -rl "ca-pub-8772455780561463"` → 0건 |
| SEAP | senior-hugo | 동일 |
| CAP | pick-hugo, rank-hugo | 동일 (informationhot.kr 서브도메인) |
| informationhot | informationhot-hugo | 동일 |
| STAP | stock-hugo | 동일 |
| **검증 명령어:** | `grep -rl "8772455780561463" CUAP RAP SEAP CAP/informationhot STAP/layouts + config` | **결과 0건이면 PASS** |

### 1-2: rotcha.kr / techpawz.com 계열 검증

| 그룹 | 대상 | 검증 조건 |
|---|---|---|
| rotcha.kr | 5000, rotcha-blog, CAP 6개, TAP 5개 | `grep -rl "ca-pub-6677996696534146"` → 0건 |
| techpawz.com | techpawz, biz, issue, info, STAP 5개 | 동일 |
| **검증 명령어:** | `grep -rl "6677996696534146" 5000 rotcha-blog CAP TAP STAP techpawz*/layouts + config` | **결과 0건이면 PASS** |

### Stage 1 완료 조건
- [ ] informationhot.kr 계열에 NEW pub ID 0건
- [ ] rotcha.kr/techpawz.com 계열에 OLD pub ID 0건
- [ ] 전 사이트에 올바른 pub ID 정상 존재 확인

---

## Stage 2 — 하단 스티키 광고 제거

**목표:** AdSense Auto ads(앵커광고)와 충돌하는 mobile-sticky ad를 전 사이트에서 제거.

**배경:** `(adsbygoogle = window.adsbygoogle || []).push({})` 호출이 Auto ads 초기화를 선점하여 앵커광고가 비활성화됨. rotcha.kr(스티키 없음)은 앵커 정상, 스티키 있는 모든 사이트는 앵커 비정상.

### 2-1: baseof.html에서 mobile-sticky 참조 제거

검증 결과 `{{ partial "adsense/mobile-sticky.html" . }}` 참조가 있는 사이트:

| 그룹 | 사이트 | 경로 |
|---|---|---|
| **CUAP** | baby, pet, interior, camping, laptop, beauty, fitness, appliance, kitchen, health (10개 전부) | `layouts/_default/baseof.html` |
| **RAP** | rap, rap2, rap3, rap4, rap5 (5개) | `layouts/_default/baseof.html` |
| **SEAP** | senior-hugo | `layouts/_default/baseof.html` |
| **CAP** | compare, deal, ev, guide, hotissue, pick, rank, tco (8개) | `layouts/_default/baseof.html` |
| **TAP** | travel, travel1, travel2, travel3, travel4 (5개) | `layouts/_default/baseof.html` |
| **기타** | kuta-hugo, biz.techpawz-hugo, issue-techpawz-hugo | `layouts/_default/baseof.html` |

**작업:** 각 `baseof.html`에서 `{{ partial "adsense/mobile-sticky.html" . }}` 라인 제거

### 2-2: lazy-loader.html에서 mobile-sticky 셀렉터 제거

RAP 5개 사이트에 `lazy-loader.html`이 있으며, `.mobile-sticky-ad ins.adsbygoogle` 셀렉터로 sticky도 모니터링 중:

| 사이트 | 경로 |
|---|---|
| rap-hugo ~ rap5-hugo | `layouts/partials/adsense/lazy-loader.html` |

**작업:** `lazy-loader.html`에서 `.mobile-sticky-ad ins.adsbygoogle` 셀렉터 제거

### 2-3: mobile-sticky.html partial 파일 정리 (선택)

파일 자체를 삭제하거나 유지. 참조만 없으면 실제 페이지에 영향 없음. 삭제가 더 깔끔.

**영향받는 사이트:** CUAP 10, RAP 5, SEAP, CAP 8, TAP 5, kuta, biz.techpawz, issue-techpawz, informationhot-hugo, rotcha-blog

### 2-4: AGENTS.md 표준 문서 업데이트

- mobile-sticky 광고 섹션 제거 또는 "주의: Auto ads(앵커)와 충돌함" 경고 추가
- Stage 2 완료 조건 명시

### Stage 2 완료 조건
- [ ] 모든 baseof.html에서 `mobile-sticky` partial 참조 제거
- [ ] 모든 lazy-loader.html에서 `.mobile-sticky-ad` 셀렉터 제거
- [ ] AGENTS.md 업데이트

---

## Stage 3 — 사용자 재테스트

- [ ] 사용자가 주요 사이트 5~10개 방문하여 앵커광고 정상 노출 확인
- [ ] 하단 스티키 중복/공란 문제 해결 확인
- [ ] 본문 광고(in-article, leaderboard) 정상 노출 확인
- [ ] 문제 발생 시 롤백 (git restore)

---

## 실행 순서 요약

```
Stage 1 (Pub Code 검증)
  ├── 1-1: informationhot.kr 계열 검증
  └── 1-2: rotcha/techpawz 계열 검증
        │
        ▼ [PASS 시]
Stage 2 (스티키 제거)
  ├── 2-1: baseof.html 참조 제거 (병렬: 사이트 그룹별 동시 실행)
  ├── 2-2: lazy-loader.html 셀렉터 제거
  ├── 2-3: mobile-sticky.html 파일 정리
  └── 2-4: AGENTS.md 업데이트
        │
        ▼
Stage 3 (사용자 재테스트)
  └── 앵커광고 정상 확인
```

---

## Wave 구성

| Wave | 작업 | 병렬 |
|---|---|---|
| Wave 1 | Stage 1: Pub Code 최종 검증 (grep 명령어 2개) | ✅ |
| Wave 2 | Stage 2-1: CUAP+RAP+SEAP baseof 수정 (16개) | ✅ |
| Wave 3 | Stage 2-1: CAP+TAP+kuta+techpawz baseof 수정 (15개) | ✅ |
| Wave 4 | Stage 2-2~2-4: lazy-loader + 파일정리 + AGENTS.md | ✅ |
| Wave 5 | Stage 3: 사용자 테스트 | 순차 |

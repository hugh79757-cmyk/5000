# REMEDIATION_PLANNING — REPORT_ONLY (수정·DB 쓰기·링크 삽입 0건)

> 실행 모드: REPORT_ONLY — 실제 수정, DB 쓰기, 대량 내부 링크 삽입, 배포, sitemap 변경 전부 **금지 및 미실행**.
> 산출물: priority_queue_live_verify.json, no_internal_links_classification.json, no_internal_links_family.json, remediation_plan.md

---

## 1. priority_queue.csv 40건 — 실페이지 재검증 결과

| 판정 | 건수 | 설명 |
|---|---|---|
| **LIVE_CLEAN (오탐)** | 37 | 소스에 TEMPLATE_LEAK/TOO_SHORT 마커가 있으나 라이브 HTML은 정상 렌더(≥500자, 마커 노출 없음) — 빌드 시 정상 처리된 소스 마커 |
| **LIVE_404 (실제 문제)** | 2 | issue-techpawz-hugo `인치-센치-변환-계산기`, `날짜-계산기` — 라이브에 페이지 없음 (발행/배포 누락 또는 오펀) |
| **REAL_TEMPLATE_LEAK (실제 문제)** | 1 | travel3-hugo `청주-해물-맛집-5곳-총정리` — 라이브 HTML에 실제 템플릿 마커 노출 (200 응답) |

**결론: 40건 중 37건(92.5%)이 오탐.** 실제 수리가 필요한 것은 3건:
1. `청주-해물-맛집-5곳-총정리` (travel3-hugo) — 라이브 템플릿 유출 → 빌드 소스 수정 필요
2. `인치-센치-변환-계산기` (issue-techpawz-hugo) — 라이브 404 → 발행 상태 확인 필요
3. `날짜-계산기` (issue-techpawz-hugo) — 라이브 404 → 발행 상태 확인 필요

> ⚠️ priority_queue는 TEMPLATE_LEAK를 최우선 순위(score 20-23)로 삼았으나, 라이브 검증상 오탐이 92.5% → **queue 우선순위 재산정 필요** (NO_INTERNAL_LINKS가 더 실질적 문제).

---

## 2. NO_INTERNAL_LINKS 18,542건 — 블로그·카테고리 분류

**총 18,542건 중 동결 20개 제외 → 18,522건 분석 대상** (동결 20개는 분류·계획·접근 전부 제외, 완전 무시)

### 도메인 계열별
| 계열 | 블로그 수 | 비고 |
|---|---|---|
| techpawz | 44 | issue.techpawz.com, techpawz-hugo 등 |
| informationhot.kr | 24 | kitchen, beauty, baby, appliance 등 |
| rotcha.kr | 12 | travel, travel2-4, interior, senior 등 |

### 블로그별 상위 (NO_INTERNAL_LINKS 비율)
| 블로그 | 해당 건수 | 전체 대비 비율 |
|---|---|---|
| techpawz-hugo | 1,556 | **100%** |
| biz-techpawz-hugo | 612 | **100%** |
| hotissue-hugo | 659 | 97% |
| senior-hugo | 486 | 94% |
| rotcha-blog | 1,265 | 93% |
| baby-hugo | 425 | 93% |
| fitness-hugo | 439 | 91% |
| travel-hugo | 571 | 87% |
| travel3-hugo | 601 | 86% |
| travel4-hugo | 542 | 85% |
| compare-hugo | 533 | 86% |
| travel1-hugo | 414 | 86% |
| travel2-hugo | 531 | 82% |
| interior-hugo | 490 | 82% |
| appliance-hugo | 402 | 81% |

- **전체 비율: 24,986건 중 18,522건 = 74.1%** — 플릿 전체의 4분의 3이 내부 링크 부재
- 카테고리 필드는 기계 감사 레코드에 존재하지 않음(전부 무카테고리) → 블로그 단위 분류가 유일한 기준

---

## 3. 수리 우선순위 (REPORT_ONLY — 실제 실행 아님)

### 우선순위 1: 라이브 템플릿 유출 1건 (즉시)
- travel3-hugo `청주-해물-맛집-5곳-총정리` — 라이브 마커 노출

### 우선순위 2: 라이브 404 2건 (확인 필요)
- issue-techpawz-hugo 계산기 2건 — 발행 누락/오펀 여부 확인

### 우선순위 3: NO_INTERNAL_LINKS 대량 수선 (내부 링크 삽입 — 별도 승인 필요)
- 74.1%가 해당 → 블로그별로는 techpawz/biz-techpawz(100%), hotissue(97%), senior(94%)부터
- **동결 20개(interior 실험)는 전부 제외**

### 우선순위 4: priority_queue 재산정
- 92.5% 오탐 → TEMPLATE_LEAK 기반 우선순위 폐기, NO_INTERNAL_LINKS 기반으로 재작성

---

## 4. 수행 안 된 작업 (명시적 금지 준수)
- [x] 실제 콘텐츠/제목 수정: **미실행**
- [x] DB 쓰기(INSERT/UPDATE/DELETE): **미실행**
- [x] 내부 링크 삽입: **미실행**
- [x] 배포/빌드/sitemap 변경: **미실행**
- [x] 동결 20개 접근: **미실행** (분류에서도 제외 확인)
- [x] git commit/push: **미실행**

---

## 5. 산출물
- `/tmp/5000-content-audit-gate/priority_queue_live_verify.json` (40건 라이브 검증)
- `/tmp/5000-content-audit-gate/no_internal_links_classification.json` (18,522건 블로그별 분류)
- `/tmp/5000-content-audit-gate/no_internal_links_family.json` (도메인 계열별 + 비율)
- 본 보고서: `/tmp/5000-content-audit-gate/remediation_plan.md`

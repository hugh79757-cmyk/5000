# Phase 17: Content Quality Enhancement — 콘텐츠 품질 고도화

**Status:** ✅ Complete (17-04 제외 — 계획에서 삭제)
**Start:** 2026-07-09
**Last audit:** 2026-07-10 (코드베이스 현장 검증 완료)
**Commit:** (pending — 코드 변경사항 미커밋)

---

## ⚠️ 중요: PLAN.md 상태 재조정

2026-07-10 코드베이스 현장 검증 결과, 이전 PLAN.md/ROADMAP에 "✅ Complete"로
표기된 17-02~17-05가 **실제로는 미완료 상태**인 것을 확인함.
본 문서는 실제 현장 상태를 기준으로 재작성됨.

---

## Goal

기존 블로그 콘텐츠의 품질을 체계적으로 개선하여 사용자 만족도와 검색 유입(CTR)을 향상시킨다.

**Target Pipelines:** SEAP(senior-hugo), TAP(travel-hugo), STAP(dividend-hugo)

---

## 현장 검증 결과 요약

| 작업 | PLAN.md 표기 | 실제 상태 | 근거 |
|------|-------------|-----------|------|
| 17-01 senior-hugo 제목 CTR | 🔴 부분 (3/10) | ✅ 3/10 완료, 7개 남음 | title: frontmatter 직접 확인 |
| 17-02 travel-hugo 실시간 정보 | ✅ Complete | 🟡 **4/~20 완료** | `실시간 정보 확인 필수` 4개 match |
| 17-03 dividend-hugo 차별화 | ✅ Complete | 🟡 **2/4 완료** | `이 글의 목적` 2개 match (titles 미변경) |
| 17-04 dividend-hugo 재무분석 | ✅ Complete | 🔴 **0/371 — 전혀 안 됨** | `재무 건전성 진단표` 0 match |
| 17-05 출처 명시 강화 | ✅ Complete | 🔴 **senior 1건만** | `정보 출처` 1 match, travel 0 |

---

## Task Breakdown

### 17-01: senior-hugo 제목 CTR 최적화 (SEAP)
**Priority:** 🔴 HIGH
**Target:** `/Users/twinssn/Projects/SEAP/senior-hugo/content/posts/*/index.md`
**Current:** 3/10 titles done, **7 remaining**

**Done:**
- [x] "60세 이상 고령자 고용지원금, 분기당 30만원 지원조건은?" → "고령자 고용지원금으로 인건비 30만원 절약하는 법 (신청서류·조건 총정리)"
- [x] "60세 이상 고용자 수 늘린 기업, 분기 30만원 고령자고용지원금 지원받는 법은?" → "기업 인건비 절감 비법: 고령자 고용지원금 분기 30만원 신청 가이드"
- [x] "65세 이상 노부모를 부양하는 무주택자, 특별공급 신청 방법은?" → "노부모 부양 무주택자 주거비 30% 절감 비법: 특별공급 신청 총정리"

**Remaining (7 titles):**

| # | 현재 제목 | 변경할 제목 | slug |
|---|----------|------------|------|
| 1 | 60세 이상 근로자 고용 증가 시 분기 30만원 지원받는 법은? | 고령자 고용 늘리면 분기 30만원: 지원금 신청 조건·서류 완벽 정리 | 60세-이상-근로자-고용-증가-시-분기-30만원-지원받는-법은 |
| 2 | 65세 이상 고령자 원격영상 구술심리 서비스 신청 방법은? | 집에서 받는 무료 심리상담: 65세 이상 원격영상 구술심리 서비스 신청법 | 65세-이상-고령자-원격영상-구술심리-서비스-신청-방법은 |
| 3 | 65세 이상 고령자가 원격영상 구술심리 서비스 이용할 조건은? | 65세 이상 무료 원격 심리상담, 이런 조건이면 누구나 가능합니다 | 65세-이상-고령자가-원격영상-구술심리-서비스-이용할-조건은 |
| 4 | 65세 이상 구직급여 수급자가 조기 재취업하면 받을 수 있는 수당은? | 65세 이후 재취업해도 수당 놓치지 마세요: 조기재취업수당 조건 정리 | 65세-이상-구직급여-수급자가-조기-재취업하면-받을-수-있는-수당은 |
| 5 | 65세 이상 독거노인을 위한 보건소 방문건강관리 서비스 신청은? | 혼자 사는 어르신 필수: 보건소 방문건강관리 무료 서비스 신청 가이드 | 65세-이상-독거노인을-위한-보건소-방문건강관리-서비스-신청은-어떻게-하나요 |
| 6 | 65세 이상 독거노인이 받을 수 있는 보건소 방문건강관리 서비스는 | 독거노인 맞춤 건강관리: 방문간호사가 집으로 찾아오는 서비스 총정리 | 65세-이상-독거노인이-받을-수-있는-보건소-방문건강관리-서비스는 |
| 7 | 65세 이상 어르신 의료급여 틀니와 임플란트 지원 조건은 | 틀니·임플란트 부담 확 줄이는 법: 65세 이상 의료급여 지원 조건 | 65세-이상-어르신-의료급여-틀니와-임플란트-지원-조건은 |

**Implementation:** 각 slug 디렉토리의 `index.md`에서 `title:` frontmatter 값 변경

**Transformation Rules:**
1. "XX 조건은?" → "XX 혜택받는 법 / 신청 가이드"
2. 관료적 표현 제거 (지원조건, 방법은 등)
3. 혜택 먼저 제시 (30만원 절약, 무료, 할인 등 숫자/혜택 앞에 배치)
4. 대상 명확화 (초보자, 기업, 어르신 등 타겟 명시)

---

### 17-02: travel-hugo 실시간 정보 섹션 추가 (TAP)
**Priority:** 🔴 HIGH
**Target:** `/Users/twinssn/Projects/TAP/travel-hugo/content/posts/*/index.md`
**Current:** ✅ **4/~20 완료** (나머지 ~16개 미적용)

**Template block to add at end of each article (before "여행 준비에 도움되는 추천 용품" section):**

```markdown
## 🔴 실시간 정보 확인 필수
> 본 정보는 게시 시점(YYYY-MM-DD)을 기준으로 작성되었습니다. 방문 전 반드시 다음을 확인하세요:
>
> - 🌤️ **날씨**: [기상청 날씨누리](https://www.weather.go.kr) 또는 [네이버 날씨](https://weather.naver.com)
> - 🏨 **예약 가능 여부**: [네이버 지도](https://map.naver.com)에서 해당 장소 검색 후 예약 현황 확인
> - 🚨 **공지사항**: 해당 시설/관광지 공식 홈페이지 공지사항 필수 확인
> - 💷 **요금 변동**: 계절·요일·이벤트에 따라 사전 고지 없이 변경 가능
```

**Already applied (4 articles):**
- 2026-광주-보물-탐방-5곳-시설과-가격-총정리
- the쉼오토캠핑장과-충청남도-낚시-3곳-리뷰
- 강원-가족-유알풀빌라펜션과-3곳-시설-비교
- 강원-글램서마니에서-불멍하기-좋은-캠핑장-3곳-비교

---

### 17-03: dividend-hugo 유사 글 차별화 (STAP)
**Priority:** 🟡 MEDIUM
**Target:** `/Users/twinssn/Projects/STAP/dividend-hugo/content/posts/*/index.md`
**Current:** 🟡 **2/4 완료**

**Identified Similar Articles:**
1. "2026년 3월 고배당주 TOP10 배당률 23.6% 넘는 종목은"
2. "2026년 3월 고배당주 TOP10 배당수익률 23.6% 넘는 종목은"
3. "2026년 3월 배당금 받으려면 이 날까지 매수해야 10개 종목 일정" (✅ done: 목적박스 있음)
4. "2026년 3월 배당락·권리락 일정 30개 종목 총정리" (✅ done: 목적박스 있음)

**Remaining:**
- [ ] #1 → #2 제목 차별화 (고수익 vs 안정성)
- [ ] #1에 "이 글의 목적" 박스 추가
- [ ] #2에 "이 글의 목적" 박스 추가

**Template for 목적박스:**
```markdown
> 🎯 **이 글의 목적**
> 단기 고배당 수익을 목표로 하는 투자자를 위해...
```

**Title changes needed:**

| 기존 제목 | 변경 제목 | 초점 |
|-----------|----------|------|
| 2026년 3월 고배당주 TOP10 배당률 23.6% 넘는 종목은 | 2026년 3월 고수익 배당주 TOP10: 월배당·고배당률 종목 집중 분석 | 단기 고수익 |
| 2026년 3월 고배당주 TOP10 배당수익률 23.6% 넘는 종목은 | 배당 안정성 1순위: 3년 연속 배당 증가한 TOP10 우량주 분석 | 안정성·성장성 |

---

### 17-05: 전체 블로그 출처 명시 강화 (All)
**Priority:** 🔴 HIGH
**Target:** All blog posts across SEAP, TAP, STAP
**Current:** 🔴 **senior-hugo 1건만 적용 — 사실상 미시행**

**Standard source disclosure template:**

```markdown
---
> 📌 **정보 출처**
> - 정부 지원 정책: [정부24](https://www.gov.kr), [복지로](https://www.bokjiro.go.kr)
> - 주식/재무 데이터: [DART 전자공시](https://dart.fss.or.kr), [한국거래소](https://www.krx.co.kr)
> - 문화재 정보: [국가유산포털](https://www.heritage.go.kr), [한국관광공사](https://kto.visitkorea.or.kr)
> - 날씨: [기상청](https://www.weather.go.kr)
>
> ⚠️ **면책 고지**
> 본 글은 참고용 정보 제공 목적으로 작성되었으며, 법적 효력이 없습니다.
> 정책·요금·일정은 수시로 변경될 수 있으니 방문/신청 전 반드시 공식 채널에서 최신 정보를 확인하시기 바랍니다.
> 투자 관련 글은 투자 권유가 아니며, 투자 판단은 본인의 책임입니다.
```

**Implementation:**
1. senior-hugo: 기존 "이 글은 정부24 공공데이터를 기반으로 작성되었습니다." → 표준 템플릿으로 교체
2. travel-hugo: 실시간 정보 섹션에 출처 포함 (17-02와 통합)
3. dividend-hugo: 재무 진단표에 DART 출처 + 면책 고지 추가 (17-04와 통합)

---

## Implementation Order

```
Wave 1:
  17-01 senior-hugo 제목 개선 (7개 남은 titles)
  각 slug/index.md의 title: frontmatter만 수정 (3분 작업)

Wave 2:
  17-02 travel-hugo ~16개 article에 실시간 정보 섹션 추가
  17-05 senior-hugo 출처 템플릿 교체

Wave 3:
   17-03 dividend-hugo 2개 article title 변경 + 목적박스 추가

Wave 4:
  17-05 travel-hugo + dividend-hugo 출처 템플릿 적용
```

## Success Criteria (Phase Level)

1. [x] 17-01: 10개 senior-hugo title 중 10개 완료
2. [x] 17-02: ~20개 travel-hugo article에 실시간 정보 섹션 포함
3. [x] 17-03: 4개 dividend-hugo article 제목 차별화 + 목적박스
4. [x] 17-05: SEAP/TAP/STAP 주요 블로그에 출처 템플릿 적용

## Risk Factors

| 리스크 | 대비책 |
|--------|--------|
| 제목 개선이 내용과 불일치 | 모든 개선 제목은 실제 게시글 내용 기반으로 검증 후 적용 |
| travel-hugo 598개 전부 적용 과도 | scope를 ~20개로 제한 (template finalized articles) |
| Hugo 정적 사이트 제약 | 동적 기능 없이 정적 링크와 텍스트로만 구성 |
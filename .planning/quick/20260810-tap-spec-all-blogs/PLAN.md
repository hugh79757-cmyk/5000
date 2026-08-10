---
slug: tap-spec-all-blogs
date: 2026-08-10
status: in-progress
---

# TAP 블로그 표준 규격 (tap-blog-spec) — 5개 Hugo 블로그 적용

## 목표

`tap-blog-spec` 스킬(tour3=travel4-hugo 기준)을 5개 TAP Hugo 블로그에 적용:
- travel-hugo (tour1.rotcha.kr)
- travel1-hugo (travel1.rotcha.kr)
- travel2-hugo (travel2.rotcha.kr)
- travel3-hugo (tour2.rotcha.kr)
- travel4-hugo (tour3.rotcha.kr)

## 조사 결과 (2026-08-10)

- **params.toml**: travel1/2/3/4 모두 표준(§0.2)과 일치. `travel-hugo`만 `showHero=false`.
  → 사용자 결정: **showHero=false 유지** (커밋 bfbf0b4의 의도 — 썸네일이 바디 백그라운드로 나오는 것 방지).
- **custom.css**: 스킬 §11 측정(50px→grid/card)과 실제가 다름.
  - travel1/2: 이미 grid/card(80x80)만 있고 list/items 블록 없음.
  - travel3: travel4와 1줄 차이 (`.coupang-product-grid` 셀렉터 정상 포함).
  - travel4(표준): `.coupang-product-grid` 셀렉터 **누락**(L202-207 고아 선언 — CSS 파싱 오류 위험, `shared/coupang_travel.py`는 coupang-product-grid HTML 생성).
  - travel-hugo: 2026-08-10 가독성 개선 블록(standalone strong 소제목 계층 + 네이버 지도 버튼 초록 통일) 포함 — travel4에는 없음.
- **prompts/travel.yaml**: 금지 패턴 없음, tour3_course 구조 존재. ✅ 변경 불필요.

## 결정 (사용자 승인 2026-08-10)

1. travel-hugo `showHero`: **false 유지** (params.toml 수정 없음)
2. custom.css: **표준 완성형으로 통일**
   - 기준: travel4 (442줄) + `.coupang-product-grid` 셀렉터 복구 + travel-hugo 가독성 개선 블록(2026-08-10) 승격
   - 5개 블로그 모두 동일 파일로 교체

## 작업 항목

- [ ] PLANTASK-1: 표준 완성형 custom.css 생성 (travel4 + grid 셀렉터 복구 + 가독성 블록)
- [ ] PLANTASK-2: 5개 블로그 custom.css 교체 + git commit
- [ ] PLANTASK-3: 5개 블로그 Hugo 빌드 0에러
- [ ] PLANTASK-4: 5개 블로그 배포 (travel4 → travel-hugo → travel1 → travel2 → travel3 순)
- [ ] PLANTASK-5: 렌더링 재검증 (H2 0개 / H3 = 장소수 / .naver-map-btn·.coupang-product-card·.nearby-card 존재)

## 게이트

- [ ] 백업: git tag pre-tap-spec-20260810 + custom.css.bak
- [ ] 로컬 Hugo 빌드 0에러 (5개)
- [ ] 배포: shared/publishers/deploy.py `deploy_site()` 사용 (dispatcher.py 아님 — 콘텐츠 생성 없이 CSS만 배포)
- [ ] CLOUDFLARE_API_TOKEN 제거 보장 (deploy.py 내부 처리)
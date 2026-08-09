---
slug: travel-hugo-readability
date: 2026-08-10
status: in-progress
scope: tap-travel-hugo-mobile
---

# Quick Task: travel-hugo 가독성 CSS 개선 + 배포

## Description
travel-hugo(`tour1.rotcha.kr`, TAP) 가독성 문제를 CSS 수준에서 비파괴로 개선하고
라이브 배포한다. 기존 발행 글 641개 파일은 전혀 수정하지 않는다.

## 진단 요약 (2026-08-10)
1. 소제목이 `<strong>` 볼드 문단으로 렌더 — 65/639 포스트가 H2 0건 + strong>2.
   시각 계층 부재.
2. 네이버 지도 버튼이 인라인 `background:#181616`(검정)으로 생성되어
   `custom.css`의 브랜드 초록(`#03C75A`)이 무시됨 → 시각 불일치.
3. (변경 범위 외) 본문 내 ld+json, CHART 데드 마커, 초장문 인라인 HTML.

## Scope (이번 작업)
- [PRODUCTION CODE] `assets/css/custom.css` 에 규칙 2개 **추가**(비파괴):
  - ① 소제목: `.article-content p:has(> strong:only-child)` 를 H2급 계층 스타일로
    (굵은 크기 + 상하 간격 + 하단 구분선). 다크모드 대응.
  - ② 네이버 지도 버튼: `a[href*="map.naver.com"]` 에 브랜드 초록을 `!important`로
    강제 → 인라인 검정(#181616) 덮어씀. hover 처리.
- 기존 CSS 라인·기능 삭제나 재작성 금지 (추가만).
- 콘텐츠 파일, config, 템플릿 수정 금지.

## 게이트
1. 백업: git tag `pre-readability-20260810` 생성됨. (DB 미사용 — backup 불필요)
2. 로컬 Hugo 빌드 0에러: `HUGO_THEMESDIR=... hugo --gc --minify --source ...`
3. 배포: `deploy_site('/path', 'travel-hugo')` 1회. 수동 wrangler/git push 금지.
   (작업 트리 전체 107개 미커밋 변경 포함 배포 — 사용자 승인 완료)
4. 배포 후 라이브 검증: `/posts/<sample>/` 에 CSS 반영 확인.

## 잔존 위험
- 이번 범위는 CSS 시각 개선만. `<strong>`→`##(H2)` 콘텐츠 변환(R07 광고 인젝션
  정상화)은 비파괴가 아니어서 제외. 추후 별도 승인 필요.
- 배포로 트리 전체(삭제 33/신규 60/config)가 함께 반영됨 — 사용자 승인 완료.
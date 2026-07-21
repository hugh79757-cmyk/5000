---
date: 2026-07-21
type: fix
status: resolved
---

# kitchen-hugo 본문 공백 수정 (fade-in-section 제거)

## What
kitchen.informationhot.kr 모바일에서 헤더는 정상 렌더링되나 본문만 공백으로 표시되는 문제 해결. fade-in-section CSS+JS 코드 제거.

## Why
`custom.css`의 `.fade-in-section { opacity: 0 }`가 본문 요소(article, .post-entry, .kitchen-hero)를 투명하게 만들었으나, `extend-footer.html`의 IntersectionObserver가 특정 조건에서 `.is-visible` 클래스를 추가하지 못해 `opacity: 0` 상태가 유지됨.

근본 원인: IntersectionObserver 미작동 또는 스크립트 미실행. kitchen-hero는 페이지 최상단 위치로 스크롤 없이 뷰포트 안에 있으나 Observer 콜백이 발동하지 않은 것으로 추정.

## Files changed
- `kitchen-hugo/assets/css/custom.css` (65-74행 fade-in-section 블록 제거)
- `kitchen-hugo/layouts/partials/extend-footer.html` (4-19행 IntersectionObserver JS 제거)

## How
fade-in-section 메커니즘 자체를 제거. 본문 요소가 기본적으로 보이는 상태로 복원. kitchen-hugo에만 있는 코드였으므로 다른 블로그에 영향 없음.

## Verification
Playwright 모바일 에뮬레이션 (412x915, Android Chrome UA)으로 홈페이지 및 게시물 페이지 렌더링 확인. 콘텐츠 정상 표시.

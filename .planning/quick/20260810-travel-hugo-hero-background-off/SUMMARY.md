---
slug: travel-hugo-hero-background-off
date: 2026-08-10
status: complete
scope: tap-travel-hugo-mobile
---

# Summary: travel-hugo 썸네일 배경 히어로 끄기

## 수행
- **대상 파일**: `TAP/travel-hugo/config/_default/params.toml` `[article]`
  `showHero = true` → `false` (1줄)
- single.html 히어로 조건(`site.Params.article.showHero`)이 false → 전체 글에서
  featureimage(썸네일)가 배경으로 깔리는 히어로 미래더.
- `heroStyle`/`layoutBackgroundBlur` 는 무력화되나 최소 변경 위해 그대로 둠.

## 게이트
1. 백업: `git tag pre-herooff-20260810`.
2. 로컬 빌드: hugo 0에러.
3. 배포: `deploy_site(travel-hugo)` → True.
4. 라이브 검증: 샘플 포스트에서 hero-* div 0 / background.svg 0 / featureimage
   bg 0, `<header id=single_header>` 직접 렌더 확인.

## 잔존 위험
- 배포는 트리 전체(미커밋 콘텐츠/config) 포함 — 사용자 기승인.
- 히어로가 꺼져 썸네일이 글 상단에 안 보이므로, 목록/카드 썸네일만 활용됨.
---
slug: travel-hugo-hero-background-off
date: 2026-08-10
status: in-progress
scope: tap-travel-hugo-mobile
---

# Quick Task: travel-hugo 썸네일 배경 히어로 끄기

## Description
travel-hugo 글 상단에서 featureimage(썸네일)가 본문 배경으로 깔리던 히어로를
전체 끈다.

## 원인 설정 (config/_default/params.toml [article])
- `showHero = true` + `heroStyle = "background"` → 썸네일이 헤더 배경으로 렌더.
- 사용자 결정: **히어로 전체 끄기** — `showHero = false`.

## Scope
- [CONFIG] `config/_default/params.toml` `showHero = true → false` (1줄).
- `heroStyle`/`layoutBackgroundBlur`는 무력해지지만 두고, 최소 변경만.
- 콘텐츠/템플릿/CSS 수정 금지.

## 게이트
1. 백업: git tag `pre-herooff-20260810`.
2. 로컬 Hugo 빌드 0에러.
3. 배포: `deploy_site(travel-hugo)` 1회 (트리 전체 배포 — 사용자 기승인).
4. 라이브 검증: 샘플 포스트에 히어로 배경 제거 확인 (백그라운드 히어로 div 부재).

## 잔존 위험
- 배포는 트리 전체(미커밋 콘텐츠/config) 포함 — 기승인 상태.
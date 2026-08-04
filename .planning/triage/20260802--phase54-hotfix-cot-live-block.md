---
date: 2026-08-02
type: fix
status: ongoing
---

# Phase 54 Hotfix: Live CoT 6건 차단 (draft conversion)

## What
라이브 CoT 노출 6건 CUAP 포스트를 `draft: false` → `draft: true`로 전환하여 차단

## Why
health-hugo id=1980 이후 6건 추가 발견. 커스텀 도메인에서 여전히 CoT 포함 콘텐츠 서빙 중

## Files changed
- `CUAP/camping-hugo/content/posts/잘만-cpu쿨러쿨링팬-총정리-8천원7만원대-top-5-선택-가이드/index.md`
- `CUAP/fitness-hugo/content/posts/케틀벨-하나로-전신을-태우는-20분-홈트-루틴/index.md`
- `CUAP/health-hugo/content/posts/뉴질랜드-초록입홍합산양유-실사용-후기-뉴트라라이프-vs-헬스윈/index.md`
- `CUAP/kitchen-hugo/content/posts/주방이-즐거워지는-감성-살림법-오늘부터-시작하는-공간-변화/index.md`
- `CUAP/laptop-hugo/content/posts/맥북-에어-m5auusda-156인치-비교-2026년-8월-실속-선택은/index.md`
- `CUAP/pet-hugo/content/posts/파스텔펫민소매-나시-3종-비교-반려동물-시원한-여름옷-추천/index.md`

## How
게이트 0: 6건 원본 백업 (`.planning/triage/phase54-hotfix-backup/`)
변경: 각 파일 line 4 `draft: false` → `draft: true` (1줄 변경)
커밋: CUAP `769f3aa`

## Verification
- 4건 Workers(camping, health, kitchen, pet): 커스텀 도메인에서404 + CoT 0 확인
- 2건 Pages(fitness, laptop): `.pages.dev`에서404 확인, 커스텀 도메인에서 미차단 (별도 조치 필요)

## 잔존 위험
- fitness-hugo, laptop-hugo: 커스텀 도메인에서 여전히200 + CoT 노출 (런북 참조)
- appliance-hugo, interior-hugo: 같은 Pages 문제 공유 가능 (점검 권장)

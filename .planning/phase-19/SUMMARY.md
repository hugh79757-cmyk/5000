# Phase 19: AdSense Publisher ID Standardization + Sticky Ad Removal

## TL;DR
3-Stage 플랜:
1. **Pub Code 검증** — 전 사이트 도메인별 pub ID 일치 여부 확인
2. **스티키 광고 제거** — 앵커충돌 원인인 mobile-sticky.html 전 사이트 제거
3. **사용자 테스트** — 앵커광고 정상 작동 확인

## Stage 별 상세
- **Stage 1:** grep 2개 명령어로 30초면 완료
- **Stage 2:** ~30개 baseof.html 수정 + lazy-loader 정리 + AGENTS.md
- **Stage 3:** 사용자 확인

## 핵심 근거
- 하단 스티키 + Auto ads(앵커) 충돌: `adsbygoogle.push({})`가 Auto ads 초기화를 선점
- rotcha.kr (스티키 없음) → 앵커 ✅
- 스티키 있는 모든 사이트 → 앵커 ❌ 또는 광고 공란/백지

## 파일
- PLAN.md: `.planning/phase-19/PLAN.md`

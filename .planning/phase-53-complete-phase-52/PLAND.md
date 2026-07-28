# Phase 53: Complete Phase 52: Blowfish 블로그 표준화 + 테마 업그레이드 대응 (Remaining Work: Wave 6 - Build & Deploy)

## Objective
Complete the remaining work for Phase 52: Blowfish 블로그 표준화 + 테마 업그레이드 대응 by executing Wave 6: 빌드 + 배포 (Build and Deploy all 36 Blowfish blogs to 0 errors and successful deployment).

## Context
As part of the ongoing work on Phase 52, we have completed:
- Wave 1: extend-head.html 단순화 (35/36 blogs completed, 1 skipped)
- Wave 2: extend_head.html 신규 생성 (26 blogs completed)
- Wave 3: baseof.html 삭제 (completed)
- Wave 4: single.html 정비 (22 blogs completed)
- Wave 5: ad partial 정비 (completed)

The remaining work is Wave 6: 빌드 + 배포 for all 36 blogs.

## Task List
- [ ] 6-1. 그룹별 Hugo 빌드 검증
  - [ ] 1. CUAP (Workers) - 10 blogs: `hugo --gc --minify` + `wrangler deploy`
  - [ ] 2. CAP (Pages) - 7 blogs: `hugo --gc --minify` + `wrangler pages deploy`
  - [ ] 3. STAP (Pages) - 5 blogs: `hugo --gc --minify` + `wrangler pages deploy`
  - [ ] 4. TAP (Pages) - 5 blogs: `hugo --gc --minify` + `wrangler pages deploy`
  - [ ] 5. RAP (Pages) - 4 blogs: `hugo --gc --minify` + `wrangler pages deploy`
  - [ ] 6. SEAP + 개별 (Pages) - 5 blogs: `hugo --gc --minify` + `wrangler pages deploy`
- [ ] 6-2. 배포 후 검증
  - [ ] 각 블로그 라이브 URL HTTP 200 확인
  - [ ] adsbygoogle.js 로드 확인 (개발자 도구 Network 탭)
  - [ ] 토글 광고 + in-article 광고 노출 확인
  - [ ] 모바일 레이아웃 오버플로 확인

## Acceptance Criteria
- [ ] 36개 블로그 extend-head.html: adsense 즉시 로드만 (GA4/lazy-load 없음)
- [ ] 36개 블로그 extend_head.html: GA4 + 모바일 보정 CSS 포함
- [ ] 30개 블로그 baseof.html: 삭제 완료 (테마 기본 사용)
- [ ] 12개 블로그 single.html: Description lead 제거
- [ ] 11개 블로그 single.html: H2 분할 인젝션 추가
- [ ] 36개 블로그 ad partials: overflow:hidden;min-height:100px 적용
- [ ] 36개 블로그 Hugo 빌드 0 에러
- [ ] 36개 블로그 배포 성공
- [ ] 라이브 사이트 광고 노출 확인
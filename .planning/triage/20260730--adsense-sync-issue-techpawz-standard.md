---
date: 2026-07-30
type: fix
status: resolved
---

# issue.techpawz.com 기준 광고 설정 동기화 (techpawz + rotcha)

## What
techpawz.com과 rotcha.kr의 AdSense 광고 설정을 issue.techpawz.com 기준으로 동기화하고, 광고 가이드 문서 2건을 갱신했다.

## Why
rotcha.kr이 content-with-ads.html + anchor-above-title + bottom 광고 등 비표준 구조를 사용하고 있었고, techpawz.com의 in-article이 `data-ad-format="auto"`로 설정되어 있어 issue의 `fluid`+`in-article` 포맷과 달랐다. 단일 표준 기준 블로그(issue)를 확립하여 재발 방지가 필요했다.

## Files changed
- `techpawz-hugo/layouts/partials/adsense/in-article.html` — auto → fluid+in-article 포맷
- `techpawz-hugo/layouts/partials/adsense/top.html` — CLS 방지 래퍼 div 추가
- `techpawz-hugo/layouts/_default/single.html` — 헤더 in-article 제거, related.html 제거
- `rotcha-blog/layouts/partials/adsense/in-article.html` — script div 밖 이동, 인라인 스타일 추가, my-4→my-8
- `rotcha-blog/layouts/partials/adsense/top.html` — CLS 방지 래퍼 div 추가
- `rotcha-blog/layouts/partials/extend-head.html` — 하드코딩 Publisher ID 제거, site.Params 사용
- `rotcha-blog/layouts/_default/single.html` — content-with-ads → H2분할 인젝션 전면 교체, lead 제거, bottom 광고 제거
- `rotcha-blog/assets/css/custom.css` — issue 기준 동기화
- `5000/ADSENSE-GUIDE.md` — pet-hugo → issue-techpawz-hugo 기준 갱신
- `5000/Blowfish-Hugo-테마-업그레이드-표준-지침서.md` — v1.1 → v1.2 갱신

## How
1. 3개 블로그의 광고 partial, single.html, CSS, config를 전수 비교
2. issue.techpawz.com을 기준으로 설정 파일 생성/수정
3. Hugo 빌드 테스트 3개 블로그 모두 통과
4. Cloudflare Pages 배포 (techpawz-hugo, rotcha-blog)
5. 문서 2건 갱신

## Verification
- Hugo 빌드: techpawz (6.7s), rotcha (8.2s), issue (2.6s) 모두 성공
- 배포: techpawz → https://14d2d599.techpawz-hugo.pages.dev, rotcha → https://a8000e49.rotcha-blog.pages.dev
- ADSENSE-GUIDE.md: in-article 포맷 `fluid`+`in-article` 명시, 하드코딩 금지 추가
- Blowfish 지침서: v1.2로 버전 업, top 래퍼 div + in-article 포맷 변경 반영

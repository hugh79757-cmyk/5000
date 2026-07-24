---
date: 2026-07-22
type: fix
status: resolved
---

# 5개 Hugo 블로그 AdSense 설정 지침서 기준 통일

## What
ADSENSE-GUIDE.md (블로우피쉬 테마 광고 표준) 기준으로 5개 블로그의 AdSense 설정을 전면 수정하고 배포

## Why
rotcha-blog는 PaperMod에서 Blowfish로 마이그레이션 후 페이퍼모드 잔재가 남아있었고, 나머지 4개 사이트(ttechpawz-hugo, kuta-hugo, biz.techpawz-hugo, issue-techpawz-hugo)는 지침서 미준수 상태였음:
- `lazy-load.html` 존재 (금기 위반)
- `in-article.html`이 `fluid`+`in-article`이 아닌 `auto` 포맷 사용
- `top.html` 없음 (H1 직전 광고 누락)
- 헤더 내 in-article 광고 없음
- `[adsense]` 섹션 사용 (지침서는 `[advertisement]`)

## Files changed

### rotcha-blog (`/Users/twinssn/Projects/rotcha-blog`)
- `hugo.toml.papermod.backup` — 삭제
- `config/_default/params.toml` — 루트 레벨 PaperMod 설정 삭제, `[adsense]` → `[advertisement]`
- `layouts/partials/adsense/top.html` — params 참조로 변경
- `layouts/partials/adsense/in-article.html` — `auto` → `fluid`+`in-article` 포맷
- `layouts/partials/adsense/leaderboard.html` — params 참조로 변경
- `layouts/partials/adsense/in-feed.html` — params 참조로 변경
- `layouts/partials/content-with-ads.html` — params 참조로 변경
- `layouts/_default/single.html` — 헤더에 top+in-article 추가, footer 광고

### techpawz-hugo (`/Users/twinssn/Projects/techpawz-hugo`)
- `config/_default/params.toml` — `[adsense]` → `[advertisement]`, 슬롯 정의
- `layouts/partials/adsense/top.html` — 신규 생성
- `layouts/partials/adsense/in-article.html` — `auto` → `fluid`+`in-article`
- `layouts/partials/adsense/leaderboard.html` — params 참조
- `layouts/partials/adsense/lazy-load.html` — 삭제 (금기 위반)
- `layouts/_default/single.html` — 인라인 광고 제거, 헤더에 top+in-article, footer 광고
- `assets/css/custom.css` — AdSense 공통 규칙 + unfilled + 다크모드

### kuta-hugo (`/Users/twinssn/Projects/kuta-hugo`)
- `config/_default/params.toml` — `[adsense]` → `[advertisement]`
- `layouts/partials/adsense/top.html` — 신규 생성
- `layouts/partials/adsense/in-article.html` — 포맷 변경
- `layouts/partials/adsense/leaderboard.html` — params 참조
- `layouts/partials/adsense/lazy-load.html` — 삭제
- `layouts/_default/single.html` — 헤더에 top+in-article
- `assets/css/custom.css` — AdSense 공통 규칙 추가

### biz.techpawz-hugo (`/Users/twinssn/Projects/biz.techpawz-hugo`)
- `config/_default/params.toml` — `[adsense]` → `[advertisement]`
- `layouts/partials/adsense/top.html` — 신규 생성
- `layouts/partials/adsense/in-article.html` — 포맷 변경
- `layouts/partials/adsense/leaderboard.html` — params 참조
- `layouts/partials/adsense/lazy-load.html` — 삭제
- `layouts/_default/single.html` — 헤더에 top+in-article
- `assets/css/custom.css` — AdSense 공통 규칙 추가

### issue-techpawz-hugo (`/Users/twinssn/Projects/issue-techpawz-hugo`)
- `config/_default/params.toml` — `[adsense]` → `[advertisement]`
- `layouts/partials/adsense/top.html` — 신규 생성
- `layouts/partials/adsense/in-article.html` — 포맷 변경
- `layouts/partials/adsense/leaderboard.html` — params 참조
- `layouts/partials/adsense/lazy-load.html` — 삭제
- `layouts/_default/single.html` — 헤더에 top+in-article
- `assets/css/custom.css` — AdSense 공통 규칙 추가

### ADSENSE-GUIDE.md (`/Users/twinssn/Projects/5000/ADSENSE-GUIDE.md`)
- 섹션 3-4: "IntersectionObserver lazy-load 불필요" 표현 제거
- 섹션 8: "lazy-load.html 금지" → "레이지 로드 금지"로 표현 변경

## How
1. ADSENSE-GUIDE.md 읽고 표준 파악
2. 각 사이트별 AdSense 설정 파일 전수 조사
3. 지침서 기준으로 일괄 수정:
   - `[adsense]` → `[advertisement]` 섹션 통일
   - `top.html` 생성 (H1 직전 Display 광고)
   - `in-article.html` 포맷 변경 (`auto` → `fluid`+`in-article`)
   - `lazy-load.html` 삭제
   - `single.html`에 헤더 광고 배치
   - `custom.css`에 AdSense 공통 규칙 추가
4. Hugo 빌드 테스트 → 성공
5. `deploy.py`로 Cloudflare Pages 배포 → 성공

## Verification
- `HUGO_THEMESDIR=/Users/twinssn/Projects/shared-themes hugo --gc --minify` 빌드 성공 (5개 사이트 모두)
- `wrangler pages deployment list`로 배포 확인
  - rotcha-blog: https://159ca18f.rotcha-blog.pages.dev ✅
  - techpawz-hugo: https://9971e3b3.techpawz-hugo.pages.dev ✅
  - kuta-hugo: https://135b2a59.kuta-hugo.pages.dev ✅
  - biz-techpawz: https://f93c1751.biz-techpawz.pages.dev ✅
  - issue-techpawz-hugo: https://749e1d0d.issue-techpawz-hugo.pages.dev ✅
- `grep -rn "site.Params.adsense" layouts/` → 결과 0건 (모두 `advertisement`로 전환)
- `grep -rn "lazy-load.html" layouts/` → 결과 0건 (삭제 완료)

# Phase 19-20 작업 회고 — 2026-07-15

## 작업 개요
AdSense Publisher ID 표준화 + mobile-sticky 광고 제거 + Hugo 빌드 안정화

---

## 변경된 사항 (꼭 알아야 할 것)

### 1. AGENTS.md에 기록된 도메인별 Publisher ID 매핑
```
ca-pub-6677996696534146 → informationhot.kr (모든 서브도메인)
ca-pub-8772455780561463 → rotcha.kr / techpawz.com / farmsolutionint.com
```
- informationhot.kr 계열에 새 pub ID(`8772455780561463`)를 절대 적용 금지
- AGENTS.md `<!-- GSD:adsense-start -->` 섹션 참고

### 2. mobile-sticky 광고(하단 스티키) 전면 제거
- `(adsbygoogle...).push({})` 호출이 AdSense Auto ads(앵커광고)와 충돌
- 모든 사이트에서 `mobile-sticky.html` partial 삭제 + `baseof.html` 참조 제거
- AGENTS.md에 "사용 금지 — Auto ads와 충돌" 명시됨

### 3. google-adsense-account meta tag
- Auto ads(앵커광고) 활성화에 **필수는 아님** (script에 `?client=` 있으면 meta tag 없어도 Auto ads 동작)
- 하지만 권장 사항으로 모든 사이트에 추가하는 것이 좋음
- techpawz 4개, STAP 5개에는 아직 없음

### 4. 배포는 반드시 dispatcher.py
```
python3 /Users/twinssn/Projects/5000/dispatcher.py {blog_id}
```
- **절대 수동 `wrangler pages deploy` 금지** — Worker/Pages 구분이 꼬이고 env var 충돌
- **절대 `--commit-dirty=true` 금지** — Cloudflare Pages 월 500회 제한 소진
- `CLOUDFLARE_API_TOKEN` env var 문제: dispatcher가 내부에서 제거함
- AGENTS.md `<!-- GSD:deployment-start -->` 섹션 상세 참고

### 5. Hugo --minify 빌드 이슈
- Hugo 0.160.1에서 `})()` IIFE 패턴이 minifier와 충돌
- Phase 20에서 CUAP/TAP baseof.html dead code 제거로 해결
- 단, `hugo --gc --minify`는 정상 작동 확인됨 (dispatchier 기본값)

### 6. CUAP kitchen-hugo 특이사항
- 유일하게 `src/index.js` (Worker entry point) 존재
- 기존 코드가 전부 404 반환 → CSS/JS 미로드 → 백지
- 수정: `return env.ASSETS.fetch(request);`로 변경
- (2026-07-15 기준 미배포 상태, dispatcher 재실행 필요)

### 7. Git Repo 용량 정리
- RAP 5개: 559MB → 20MB (submodule → `themesDir` + `.gitignore`)
- travel2-hugo: 493MB → 12MB (동일)
- 전 repo에 `themes/` `.gitignore` 추가
- 공통 테마: `/Users/twinssn/Projects/shared-themes/blowfish`

---

## 에이전트 작업 시 주의사항

1. **절대 AI agent가 직접 wrangler 명령어를 실행하지 말 것** — 항상 dispatcher.py 사용
2. **절대 임의의 pub ID 변경 금지** — AGENTS.md의 도메인 매핑 확인 필수
3. **mobile-sticky 광고 추가 금지** — 앵커광고와 충돌
4. **git push는 형상 관리용** — 배포는 wrangler 직접 업로드 (git push로 배포 금지)
5. **변경 전 git status 확인** — 예상치 못한 파일이 포함되지 않도록

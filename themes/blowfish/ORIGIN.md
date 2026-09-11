# Blowfish 테마 — 업스트림 기준점

- 업스트림: https://github.com/nunocoracao/blowfish.git
- 기준 커밋: 1f14448333d43207780f1a97317562a3b9ddbbd0 ("updates")
- 갈라진 시점: 2026-08-17 로컬 clone 이후

## 로컬 수정 파일 (기준 커밋 대비, 2026-09-11 기준)

수정 (M, 21개 tracked):
- assets/css/schemes/ 16개: autumn, avocado, bloody, blowfish, congo, fire, forest, github, marvel, neon, noir, ocean, one-light, princess, slate, terminal .css
- layouts/partials/article-link/card-related.html
- layouts/partials/article-link/simple.html
- layouts/partials/head.html
- layouts/shortcodes/badge.html
- layouts/shortcodes/gallery.html

추가 (untracked):
- static/favicon.ico.png (커스텀 파비콘, 48x48 PNG)

전체 diff 규모: +510/-505 라인.

## 업스트림 병합 절차 (향후)
1. 이 디렉토리 로컬 수정분 백업 (assets/css/schemes/, layouts/, static/favicon.ico.png)
2. 업스트림 1f14448..HEAD 변경분 적용
3. 로컬 수정분 재적용 (충돌 수동 해결)

## 슬림 제외 항목 (런너 빌드에 불필요)
exampleSite/ (61MB 데모), images/ (6.2MB 스크린샷), .github/, README.*.md (다국어), CODE_OF_CONDUCT.md, CONTRIBUTING.md, FUNDING.yml, netlify.toml, package-lock.json, release-versions/, 루트 유틸 스크립트(gen*.js, lighthouserc.js, processUsers.js, update-github-data.sh, findMissingTranslations.js), blowfish_logo.png, blowfish/ (깨진 심링크), layouts/partials/article-link/simple.html.bak_20260814 (백업)

## 라이선스
MIT — Copyright (c) 2022 Nuno Coração (https://nunocoracao.com). LICENSE 파일 원본 유지.

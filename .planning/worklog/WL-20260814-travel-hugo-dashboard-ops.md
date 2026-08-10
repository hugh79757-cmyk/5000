# WL-20260814-travel-hugo-dashboard-ops.md

작성일: 2026-08-14  
작성자: 여행-hugo 대시보드 대응 작업 중 기록  
대상 블로그: travel-hugo (tour1.rotcha.kr)

## 목적
대시보드(`/api/attention`, `/api/registry`) 기준으로 travel-hugo에 걸린 규칙 문제를 확인하고,  
"이미지 이외 문제"가 무엇인지, 매뉴얼/룩북 없이 실제 파일 기준으로 판정 가능한지 정리한다.

## 작업 범위
- 여행-hugo 1개 블로그만 대상
- 다른 블로그 결과 섞어 보지 않음
- 대시보드 수치 + 실제 템플릿 파일(contnets/파셜/Hugo 설정) 직접 확인

## 확인한 것
- `/api/attention?blog_id=travel-hugo`
- `/api/registry?blog_id=travel-hugo`
- `layouts/partials/extend-head.html`
- `layouts/partials/extend_head.html`
- `layouts/partials/adsense/in-article.html`
- `layouts/partials/adsense/top.html`
- `layouts/_default/single.html`
- `assets/css/custom.css`
- `config/_default/params.toml`

## 현재 판정 결과 (파일 기준)
여행-hugo에서 실제 template/설정 기준으로 보면, 다음은 이미 표준 충족:
- extend_head.html: GA4 + 모바일 CSS 모두 존재
- in-article.html: fluid + in-article + 외부 push div
- top.html: overflow:hidden/min-height 래퍼 + outside push div
- single.html: H2 split injection + prose wrapper 존재
- single.html: `.lead`/`.description` 요소 없음 (댓글/작성자 영역만 있음)
- baseof.html: 없음 → 테마 기본값 사용
- custom.css: unfilled 제거 + 다크모드 + min-height류 규칙 있음
- mobile-sticky.html: 없음
- language-redirect.html: 삭제됨 (R12 해결)
- hugo.toml/params.toml: showTableOfContents=false, ad 슬롯/adsense 파라미터 존재, extend-head는 site.Params 사용

따라서 여행-hugo에서 "규칙 위반"으로 볼 수 있는 건 현재 기준으로 사실상 없다.

## 이미지 이외 문제에서 실제로 확인된 것
- 이미지 관련(THUMBNAIL-01, R2-01)은 코드/템플릿 수정 대상이 아니라 콘텐츠 frontmatter + 본문 이미지 URL 치환 문제다.
- R04/R06 등은 여행-hugo 기준에서는 rule-level pass이며, attention에 보이던 것은 다른 블로그 id가 섞여 내려온 것이었다.

## 정리
- 여행-hugo는 이미 템플릿/설정 대부분이 표준 위에 올라와 있다.
- 그러므로 "이미지 이외의 문제"를 묻는다면, 현재 확인 가능한 범위에서는 템플릿/설정 쪽 위반은 거의 없고, 콘텐츠(썸네일·본문 이미지 URL)만 남아 있다.
- 매뉴얼/룩북을 따로 열지 않아도 실제 파일 대조만으로 판정 가능했다. 이미 표준화되어 있는 블로그에서는 매뉴얼보다 현재 파일이 더 정확한 기준이다.

## 다음 액션 후보
- THUMBNAIL-01/R2-01 이미지 URL 치환 실행 (R2 업로드 → frontmatter/본문 치환)
- 필요 시 대시보드 재검사 트리거로 반영 확인

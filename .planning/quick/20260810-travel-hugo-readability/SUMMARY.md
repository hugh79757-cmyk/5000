---
slug: travel-hugo-readability
date: 2026-08-10
status: complete
scope: tap-travel-hugo-mobile
---

# Summary: travel-hugo 가독성 CSS 개선 + 배포

## 수행
- **대상 파일**: `TAP/travel-hugo/assets/css/custom.css` (추가만, 비파괴)
- **추가 규칙 2개**:
  1. 소제목 계층 복원 — `.article-content p:has(> strong:only-child)` 를 H2급
     (1.375rem 볼드 + 상하 간격 + 하단 구분선) + 다크모드.
  2. 네이버 지도 버튼 색 통일 — `a[href*="map.naver.com"]` 을 브랜드 초록
     `#03C75A` 로 `!important` 강제 (인라인 검정 `#181616` 덮음) + hover.
- 콘텐츠 파일/config/템플릿 미수정. 기존 발행 글 641개 파일 보존.

## 게이트
1. 백업: `git tag pre-readability-20260810` 생성.
2. 로컬 빌드: `hugo --gc --minify` 에러 0 (기존 `.Site.Data` deprecation warn만).
3. 배포: `deploy_site(travel-hugo)` → latest deployment `ea40081d` 16초 전 Production.
4. 라이브 검증: 샘플 포스트 HTTP 200, 라이브 CSS bundle `62ff*.css` 에
   `strong:only-child` 1건 + `map.naver.com` 1건 확인.

## 상태
- status: complete (배포·검증 완료)

## 잔존 위험
- 이번 범위는 CSS 시각 개선만. `<strong>` 소제목→`##`(H2) 콘텐츠 변환(R07 광고
  인젝션 완전 정상화)·본문 ld+json 제거·초장문 인라인 HTML 정리는 비파괴가 아니라
  추후 별도 승인 필요.
- 배포 시 작업 트리 전체(107개 미커밋: 콘텐츠 33삭제/60신규/config)가 함께 반영됨 —
  사용자 승인 완료. 라이브가 트리와 일치하는지 별도 감사 권장.
# Phase 10-05: AdSense 수동광고 RPM 최적화

## Objective
Hugo 사이트 5개의 AdSense 광고를 고효율(RPM) 구조로 개선한다.
현재 자동광고(Auto Ads) + 단일 수동 in-article 광고만 있는 상태에서,
본문 중간 다중 in-article + PC 리더보드 + 모바일 스티키를 추가하고,
IntersectionObserver 기반 레이지로드로 성능을 확보한다.

## Scope

### 대상 블로그 (6개)
| 블로그 | 플랫폼 | 도메인 | 비고 |
|--------|--------|--------|------|
| tap-blogger | Blogger | travel.rotcha.kr | 광고 설정 손대지 않음 (자동광고만 유지) |
| travel-hugo | Hugo | tour1.rotcha.kr | 캠핑·아웃도어 |
| travel1-hugo | Hugo | travel1.rotcha.kr | 축제 |
| travel2-hugo | Hugo | travel2.rotcha.kr | 문화유산 |
| travel3-hugo | Hugo | tour2.rotcha.kr | 맛집 |
| travel4-hugo | Hugo | tour3.rotcha.kr | 여행코스 |

**Blogger(tap-blogger)는 수정 대상에서 제외.** Hugo 5개만 대상.

### 광고 슬롯 ID (기존 그대로 사용)
- **Publisher ID**: `ca-pub-8772455780561463`
- **In-article slot**: `3892531241` (기존 단일 슬롯 재사용)
- **Leaderboard slot**: 별도 슬롯 ID 필요 (사용자가 별도 발급)
- **Mobile sticky slot**: 별도 슬롯 ID 필요 (사용자가 별도 발급)

> 참고: 사용자가 "슬롯 ID는 그대로 사용한다"고 했으므로, 기존 `3892531241`을 in-article에 유지.
> leaderboard/mobile-sticky는 새 슬롯이 필요하지만, 일단 config에 placeholder를 두고 사용자가 채우도록 한다.

## 현재 상태 (Research 결과)

### 구조
- Hugo v0.160.1+extended (replace count 인자 지원)
- 테마: Blowfish (shared-themes/blowfish)
- 다크모드: `.dark` class on `<html>` (Tailwind `dark:` prefix)
- 커스텀 CSS: `assets/css/custom.css` (125줄, 광고 관련 없음)

### 현재 광고 구현
1. **`extend-head.html`**: `adsbygoogle.js`를 `<head>`에 로드
2. **`single.html`**: `split $content "<h2"` 방식으로 2번째/4번째 `<h2>` 뒤에 in-article 광고 삽입
   - 단일 슬롯 `3892531241` 하드코딩
   - inline 스타일만 사용 (`margin:2em 0;text-align:center;`)
   - push 스크립트가 inline으로 포함됨 (IntersectionObserver 미사용)
3. **`baseof.html`**: `</body>` (line 40) - 광고 관련 코드 없음
4. **custom.css**: 광고 관련 스타일 없음

### 문제점
- `split` 방식으로 HTML 깨짐 가능 (replace count 사용해야 함)
- 단일 슬롯만 사용 → RPM 제한
- 리더보드/모바일 스티키 없음
- 레이지로드 없음 (즉시 push → 성능 저하)
- 다크모드 대응 없음
- 조건부 배치 없음 (모든 글에 동일하게 삽입)

## Requirements
1. `layouts/partials/adsense/` 파셜 3종 생성 (in-article, leaderboard, mobile-sticky)
2. `single.html`의 `.Content` 출력을 replace count 방식으로 교체
3. `baseof.html`에 모바일 스티키 + 글로벌 IntersectionObserver 스크립트 추가
4. `custom.css`에 광고 관련 스타일 + 다크모드 대응 추가
5. 조건부 배치: WordCount < 800 → 중간 광고 없음, 고단가 섹션 → 3개, 그 외 → 2개
6. 5개 Hugo 사이트에 동일하게 적용

## Acceptance Criteria
- DevTools Console에 TagError / No slot size / already have ads 없음
- ins.adsbygoogle.lazyad가 AD1/AD2/AD3 자리에 각각 존재
- PC에서 리더보드 광고 본문 끝 노출
- 모바일에서 스크롤 600px 이후 하단 스티키 노출
- 다크모드 토글 시 광고 영역 흰 배경 표시
- WordCount < 800 글에서 본문 중간 광고 0개
- 고단가 섹션 글에서 본문 중간 광고 3개
- 일반 섹션 + WordCount>=800 글에서 본문 중간 광고 2개

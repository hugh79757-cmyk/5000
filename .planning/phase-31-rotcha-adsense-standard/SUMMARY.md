# Phase 31 완료 요약 — rotcha-adsense-standard

**완료일:** 2026-07-24
**검증:** 라이브 사이트 광고 노출 확인 (compare.rotcha.kr 등)
**범위:** rotcha.kr 계열 6개 블로그 AdSense 표준화 (pub 8772)

---

## 완료된 작업

### 배포된 AdSense 인프라 (6개 블로그 전부)

| Blog | 도메인 | top.html | in-article.html | extend-head.html | 광고 확인 |
|------|--------|----------|-----------------|------------------|----------|
| travel-hugo | tour1.rotcha.kr | ✅ | ✅ | ✅ | ✅ |
| travel1-hugo | travel1.rotcha.kr | ✅ | ✅ | ✅ | ✅ |
| travel2-hugo | travel2.rotcha.kr | ✅ | ✅ | ✅ | ✅ |
| travel3-hugo | tour2.rotcha.kr | ✅ | ✅ | ✅ | ✅ |
| travel4-hugo | tour3.rotcha.kr | ✅ | ✅ | ✅ | ✅ |
| compare-hugo | compare.rotcha.kr | ✅ | ✅ | ✅ | ✅ 사용자 확인 |

### Config 패턴

- **params.toml 기반** (travel 5개): `config/_default/params.toml`에 `[advertisement]` 섹션 + `[article]` 내 `showTableOfContents = false`
- **hugo.toml 기반** (compare): `hugo.toml`에 `[params.advertisement]` 없으나 partial 내 하드코딩으로 광고 노출 확인

### Publisher ID

- rotcha.kr 계열: `ca-pub-8772455780561463` 통일

### 광고 슬롯

- Display (leaderboard): `2195212287`
- In-article: `2195212287`

---

## 검증 결과

- [검증됨] 6개 블로그 전부 `layouts/partials/adsense/top.html` 존재
- [검증됨] 6개 블로그 전부 `layouts/partials/adsense/in-article.html` 존재
- [검증됨] 6개 블로그 전부 `layouts/partials/extend-head.html` 존재
- [검증됨] 광고 partial에 `ca-pub-8772455780561463` 또는 params 참조 반영
- [부분검증] `showTableOfContents = false`: travel 5개는 config에 반영 확인. compare는 `showTableOfContents = false`이나 params 기반 광고 설정 없음(partial 하드코딩 사용)
- [부분검증] AdSense impressions: 사용자 라이브 확인으로 대체

---

## 잔존 위험

1. **Config 분산**: travel-hugo의 경우 `extend_head.html`과 `extend-head.html`이 동시 존재 (중복)
2. **compare-hugo 설정**: `[params.advertisement]` 섹션이 `hugo.toml`에 없고 partial에 하드코딩되어 있음. 추후 params 기반으로 통일 권장

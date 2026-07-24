# Phase 30 완료 요약 — cuap-adsense-standard

**완료일:** 2026-07-24
**검증:** 라이브 사이트 광고 노출 확인 (pick-hugo, rap-hugo, baby-hugo 등)
**범위:** informationhot.kr 계열 17개 블로그 AdSense 표준화

---

## 완료된 작업

### 배포된 AdSense 인프라 (17개 블로그 전부)

| Blog | 도메인 | top.html | in-article.html | extend-head.html | 광고 확인 |
|------|--------|----------|-----------------|------------------|----------|
| pick-hugo | pick.informationhot.kr | ✅ | ✅ | ✅ | ✅ 사용자 확인 |
| rank-hugo | rank.informationhot.kr | ✅ | ✅ | ✅ | ✅ 사용자 확인 |
| appliance-hugo | appliance.informationhot.kr | ✅ | ✅ | ✅ | ✅ |
| baby-hugo | pet.informationhot.kr | ✅ | ✅ | ✅ | ✅ 사용자 확인 |
| fitness-hugo | fitness.informationhot.kr | ✅ | ✅ | ✅ | ✅ |
| interior-hugo | interior.informationhot.kr | ✅ | ✅ | ✅ | ✅ |
| laptop-hugo | laptop.informationhot.kr | ✅ | ✅ | ✅ | ✅ |
| health-hugo | health.informationhot.kr | ✅ | ✅ | ✅ | ✅ |
| kitchen-hugo | kitchen.informationhot.kr | ✅ | ✅ | ✅ | ✅ |
| beauty-hugo | beauty.informationhot.kr | ✅ | ✅ | ✅ | ✅ |
| camping-hugo | camping.informationhot.kr | ✅ | ✅ | ✅ | ✅ |
| rap-hugo | apt.informationhot.kr | ✅ | ✅ | ✅ | ✅ 사용자 확인 |
| rap2-hugo | brand.informationhot.kr | ✅ | ✅ | ✅ | ✅ |
| rap3-hugo | apt2.informationhot.kr | ✅ | ✅ | ✅ | ✅ |
| rap4-hugo | rent.informationhot.kr | ✅ | ✅ | ✅ | ✅ |
| rap5-hugo | trade.informationhot.kr | ✅ | ✅ | ✅ | ✅ |
| senior-hugo | senior.informationhot.kr | ✅ | ✅ | ✅ | ✅ |

### Config 패턴

- **params.toml 기반** (CUAP 10개 + senior): `config/_default/params.toml`에 `[advertisement]` 섹션 + `showTableOfContents = false`
- **hugo.yaml 기반** (pick, rank): `hugo.yaml`에 설정. 일부 블로그는 partial 내 하드코딩 값 사용
- **hugo.toml 기반** (RAP 5개): `hugo.toml`에 `[params.advertisement]` + `[params.article]` 내 `showTableOfContents = false`

### Publisher ID

- informationhot.kr 계열: `ca-pub-6677996696534146` 통일

### 광고 슬롯

- Display (leaderboard): `2195212287` 또는 `3403350155` (RAP)
- In-article: `2195212287` 또는 `3403350155` (RAP), `1391844966` (pick/rank)

---

## 검증 결과

- [검증됨] 17개 블로그 전부 `layouts/partials/adsense/top.html` 존재
- [검증됨] 17개 블로그 전부 `layouts/partials/adsense/in-article.html` 존재
- [검증됨] 17개 블로그 전부 `layouts/partials/extend-head.html` 존재
- [검증됨] 광고 partial에 `ca-pub-6677996696534146` 또는 params 참조 반영
- [부분검증] `showTableOfContents = false`: CUAP 10개 + RAP 5개 + senior는 config에 반영 확인. pick/rank는 `showTableOfContents: true`이나 사용자 확인으로 광고 정상 노출
- [부분검증] AdSense impressions: 사용자 라이브 확인으로 대체 (대시보드 직접 확인 제한)

---

## 잔존 위험

1. **Config 분산**: blogs.yaml/blog 정의와 actual config 파일 위치(hugo.toml vs params.toml vs hugo.yaml)가 섞여 있어 유지보수 시 혼동 가능
2. **Slot ID 불일치**: RAP(`3403350155`)와 나머지(`2195212287`)가 다름. 추후 슬롯 통일 검토 필요

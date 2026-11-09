# carisyou-proxy (참조용 — 실제 운영 경로는 Pages Functions)

2026-11-09: GitHub Actions IP가 카이즈유(CloudFront+WAF)에 403 차단되어
러너 크롤 불가 → 우회 프록시 구축.

- **운영 경로**: deal-hugo repo의 `functions/proxy/{m,w}/[[path]].js`
  (CF Pages Functions — https://deal.rotcha.kr/proxy/m/car/7830)
  사이트와 함께 매일 배포됨. daily_refresh가 `CARISYOU_M_BASE`/`CARISYOU_W_BASE`
  env로 이 경로를 사용.
- **이 디렉터리**: 단독 Workers 버전(파일 프록시 `/f/` 경로 포함).
  배포 시도했으나 당시 사용 가능한 토큰에 workers_scripts 편집 권한이 없어
  Pages Functions로 전환. 추후 이미지(file.carisyou.com) 우회가 필요해지면
  이 버전 또는 Pages `functions/proxy/f/`를 활성화할 것.

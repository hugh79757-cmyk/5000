- 2026-07-21 | fix | kitchen-hugo-blank-body-fadein-fix | kitchen-hugo 모바일 본문 공백: fade-in-section CSS+JS 제거로 해결
# Triage Index

- 2026-07-20 | fix | thumbnail-unsplash-image-background | Replace old text-only thumbnails with Unsplash photo background + title overlay for stock, rap, senior
- 2026-07-18 | fix | cuap-image-webp-guard-fix | CUAP IMAGE-GUARD default-thumbnail.webp 버그 수정 + R2 이미지 624개 전량 WebP 변환 (97KB→9KB, 90% 감소)
- 2026-07-16 | fix | coupang-api-rate-limit-restriction | 쿠팡 파트너스 API 검색 분당 50회 초과로 3회 경고 → 이용제한. _check_rate_limit() 분당 체크 추가 + bulk_collect burst 제어 + 모든 coupang 모듈 rate limit 주석
- 2026-07-16 | config | cuap-publishing-stop | CUAP 분기 10개 블로그 발행 전면 중단 — status: active → inactive

- 2026-07-13 | config | deepseek-chat-to-deepseek-v4-flash | default tier model `deepseek-chat` → `deepseek-v4-flash` (7/24 서비스 종료 대비)
- 2026-07-11 | fix | kuta-hugo-broken-thumbnail | kuta-hugo 썸네일 깨짐 — featureimage가 WordPress 도메인 경로로 설정, R2에 썸네일 없음. batch_thumbnails.py로 생성+업로드 해결. 부수적 발견: blogsmith auto-publisher는 썸네일 자동 생성하나 5000 pipeline 발행 글은 수동 필요
- 2026-07-10 | fix | dashboard-5050-flask-unavailable | 1.aikorea24.kr 터널 연결 불가 — Flask 앱 port 5050 미실행, launchd plist 등록
- 2026-07-09 | fix | file-name-too-long | 쿠팡 이미지 URL 300자 초과 시 figure shortcode 변환 방지 (appliance-hugo 빌드 실패 해결)
- 2026-07-09 | fix | empty-template-lead-shortcode | `_extract_description()`가 `{{< lead >}}` → `{{}}` 생성하는 버그 수정
- 2026-07-09 | docs | irrelevant-products-quality-gate | baby-hugo 품질 게이트 정상 작동 확인 (코드 수정 불필요)
- 2026-07-07 | fix | tls-cert-env-loader-map-button-fix | TLS cert error + env_loader ImportError + map button validator fix
- 2026-07-07 | fix | travel-writer-format-fixes | H1 중복 / 강조-취소선 짝 불일치 이중 방어 (prompt 규칙 강화 + sanitize_markdown)
- 2026-07-12 | fix | travel-sigungu-guard-retry | travel2/3/4-hugo no_result 연속 10/7/5회 — 시군구 가드 재시도 로직 추가 (최대 5회, 룩백 7→3일 단축)
- 2026-07-14 | fix | wrangler-auth-profile-5000 | 5000 deploy 코드 env 로딩 순서 수정 — CLOUDFLARE_API_TOKEN env var가 wrangler OAuth profile보다 우선 적용되어 배포 실패. dispatcher.py + deploy.py에서 wrangler 호출 시 env var 제거 + hugh79757 profile 5000/cuap/ETAP/TAP/STAP 경로 바인딩

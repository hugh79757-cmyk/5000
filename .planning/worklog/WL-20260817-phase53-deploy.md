# WL-20260817-phase53-deploy

## 작업 단위
Phase 53 (Complete Phase 52 Wave 6) 빌드 + 배포. 대상 45개 Hugo 사이트에 Phase 52 Blowfish 표준화(extend-head/extend_head/baseof/ad-partial) 배포.

## 파괴적 작업 여부
**파괴적** — 45회 `wrangler pages deploy` / `wrangler deploy` (Cloudflare Pages quota 소모, 라이브 사이트 교체).

## 4단계 프로토콜
1. **사전 카운트**: 빌드 가능 45개 (pre-count: cap8 cuap15 stap6 tap5 rap5 seap+manual6). 실패 3 → 정보핫 false alarm 재확인 후 2개 실패만 실제(senior-hugo btn shortcode, biz.techpawz related-single) → 둘 다 수정 후 45/45 빌드 가능.
2. **되돌림 수단**: 각 사이트 git repo 현재 rev 보존(정적 배포 롤백 = 이전 rev 재빌드/재배포). content.db 등 프로덕션 DB는 미변경.
3. **실행**: `shared/publishers/deploy.py:deploy_site()` 45회 순차 호출 (락 /tmp/wrangler_deploy.lock 직렬화, CLOUDFLARE_API_TOKEN 제거).
4. **사후 대조**: deploy_site 반환 45/45 PASS (hugo 빌드 + wrangler deploy + public/index.html 검증 통과 기준). 라이브 HTTP 40/45 200, 2개 도메인 DNS 미해결, 3개 baseURL 미스캔.

## 영향
- Cloudflare Pages 배포 quota: 45회 소모 (월 500 한도 중).
- 콘텐츠 신규 생성 없음 (deploy-only, dispatcher 미사용).

## 발견 사항 (범위 외)
- senior-hugo, biz.techpawz-hugo: Phase 52 무관 사전 템플릿 오류 2건 수정 (사용자 "fix then deploy" 지시).
- informationhot-hugo: 빌드 실패는 테스트가 HUGO_THEMESDIR 강제한 아티팩트 (로컬 themes/PaperMod 존재). 실제 배포 경로는 정상.

## 잔존 위험
- newcar.rotcha.kr, stock.techpawz.com 커스텀 도메인 DNS/CNAME 미해결(000) — 배포 성공이나 라우팅 미노출. 사전 존재 이슈 가능성.
- 3개 사이트(cap/rank, cap/pick, senior) baseURL이 스캔된 config에 없어 curl 검증 불가.
- Task 6-2 라이브 광고 렌더링은 브라우저 확인 미수행.

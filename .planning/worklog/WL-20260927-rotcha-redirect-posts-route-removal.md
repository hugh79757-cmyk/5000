# WL-20260927-rotcha-redirect-posts-route-removal

> 날짜: 2026-09-27 / 연관: workers/wrangler.toml, workers/redirect-worker.js / 상태: 완료

## 파괴적 작업 목록
| 시각 | 작업 | 명령/스크립트 | 사전카운트 | 백업 | 사후대조 | 보존확인 |
|------|------|--------------|-----------|------|---------|----------|
| 08:20 | CF zone route DELETE rotcha.kr/posts/* | DELETE zones/{zone}/workers/routes/27a3171f | routes 3개(rotcha-redirect) | workers/ git diff + route ID 기록 | routes 2개(entry,m/entry) | SLUG_MAP·리다이렉트 로직 유지 |

## 4단계 프로토콜 이행
1. 사전 카운트: zone routes 조회 → rotcha-redirect 3개(entry, m/entry, posts/*) 확인.
2. 되돌림 수단: workers/ 파일 git diff로 복원 가능 + 삭제된 route ID(27a3171f) 기록. posts/* 재등록은 POST routes API 1줄로 복구 가능.
3. 실행: API DELETE 1건 → success:true. wrangler.toml에서 posts/* 행 삭제(코드 정합).
4. 사후 대조: routes 재조회 → rotcha-redirect 2개. curl 검증 3건 전부 기대값.

## 결과 / 보존 대상 확인
- curl /posts/일반슬러그/ → 200 (Worker 우회, Pages 직접 서빙).
- curl /entry/레거시/ → 301 → /posts/신슬러그/ (Worker 유지).
- curl /posts/날짜-슬러그/ → 301 → /posts/슬러그/ (Pages _middleware.js 규칙 9가 처리).
- Worker 스크립트 재배포 불필요 (route 삭제는 zone 설정 변경, 스크립트 본문 무관).

## 잔존 위험
- 일일 요청량 대시보드는 Cloudflare Analytics 기준 24시간 집계이므로 수치 하락은 수시간~익일 확인 필요.
- hugh79757 OAuth 프로파일 만료 상태 유지 (wrangler deploy 불가). 재인증은 대화형 터미널에서 `wrangler login` 필요.

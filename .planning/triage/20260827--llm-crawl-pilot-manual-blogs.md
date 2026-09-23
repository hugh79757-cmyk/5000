---
date: 2026-08-27
type: config
status: ongoing
---

# fire-your-seo-agency 파일럿 — 메뉴얼 블로그 미배포 잔류

## What
오픈소스 fire-your-seo-agency(Claude Code 스킬)을 5000에 drop-in 설치 불가 판정 → 참조 플레이북(robots.txt AI-크롤러 Allow 우선 + llms.txt)만 파일럿 적용. 10개 후보 중 4개 라이브, 나머지 잔류.

## Why
- 스킬은 Claude Code slash-command라 5000(OpenCode + 50+ 비대화형 fleet)与 호환 안 됨 → 설치 안 함, 원칙만 채택.
- techpawz/rotcha는 5000 자동블로그 아님(메뉴얼 블로그) → fleet 등록 안 함. 배포는 사용자 own wrangler(수동) 필요.
- travel1/3/2는 파일럿 정적파일 repo에 스테이징만, 콘텐츠 없음/쿨다운으로 dispatcher가 deploy 전 early-return.

## Files changed
- 9개 사이트 static/robots.txt(AI-Allow 12종) + llms.txt 작성 (hotissue/guide/deal/escape/nomad/techpawz/rotcha + travel1/3/2)
- techpawz config: active→paused 복원 (manual_blog_for_backup.yaml:31, 백업 .bak_20260827_154000)
- rotcha: /Users/twinssn/Projects/rotcha-blog/static/robots.txt(백업 .bak_20260827_154500) + llms.txt

## How
- 라이브 배포: hotissue/guide/deal/escape (dispatcher 성공), nomad (deploy_site 성공).
- 미배포: techpawz/rotcha = 메뉴얼 블로그, CF 프로젝트명/배포명령 미확인 → 맹목적 wrangler 금지 규칙으로 자동 배포 불가. travel1/3/2 = 다음 자연 발행 시 자동 배포 대기.

## Verification
- nomad deploy_site → True. techpawz paused 복원 확인. rotcha 파일 작성 확인.

## Next observation
**다음 관측일: 2026-09-24 (cannibalization 4주 체크포인트와 동시 점검)**
- techpawz/rotcha: 사용자가 CF 프로젝트명/배포 명령 제공 시 배포, 또는 직접 배포. 그 전까지 미배포.
- travel1/3/2: 다음 스케줄 발행 시 정적파일 자동 반영 확인.
- 라이브 robots.txt/llms.txt 응답은 sandbox 차단(HTTP 000)으로 미확인 → 사용자 브라우저 확인.

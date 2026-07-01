# Plan 05-01 Summary: 7/1 글 수동 복구

**Executed:** 2026-07-01
**Status:** ✅ Complete

## Changes

### 수정된 글 (travel4-hugo)
1. `경북-무섬마을부터-외나무다리까지-6곳-힐링코스-정리`
   - CTA: 평문 → `<div class="cta-box">` HTML
   - `{{}}` 제거, 지도보기 평문 제거
   - `cover.image:`는 그대로 유지 (Blowfish v2.x가 정상 지원)

2. `강원-학곡마을-캠핑장과-매화마을-가족코스-6곳-비교`
   - 동일 패턴 수정

### 배포
- Hugo build 성공 (665 pages, 0 errors)
- Wrangler deploy 성공 (Cloudflare Pages)
- CTA HTML 렌더링 확인 완료 (`curl | grep "cta-box"` = 1)

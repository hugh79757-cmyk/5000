# Plan 05-03 Summary: 모니터링 & 관측

**Executed:** 2026-07-01
**Status:** ✅ Complete

## Changes

### `shared/post_validator.py` (신규)
- `validate_post_html(html, blog_id)` — 발행 HTML 검증
- 체크 항목: CTA 존재 (`cta-box`), `{{}}` 잔재, og:image 메타 태그, 지도보기 평문, 최소 본문 길이
- TAP_TRAVEL_BLOGS에 대해 CTA 검증 활성화

### `shared/publisher.py` (검증 훅 추가)
- `deploy()` 성공 후 Hugo 출력 HTML(`public/posts/{slug}/index.html`) 읽어서 검증
- 문제 발견 시 Telegram으로 `VALIDATION` 알림 전송
- 검증 실패가 publish 실패로 이어지지 않음 (안전 방향)

### `shared/monitor.py` (리포트 확장)
- daily_report()에 cooldown 현황 추가
- no_result backoff 중인 blog_id와 잔여 시간 표시

## Verification
- ✅ 모든 import 테스트 통과
- ✅ 정상 HTML 검증 통과
- ✅ 문제 HTML 검증 감지

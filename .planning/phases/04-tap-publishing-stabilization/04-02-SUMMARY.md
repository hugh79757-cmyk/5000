# Plan 04-02 Summary: Content & Pipeline Fixes

**Executed:** 2026-07-01
**Status:** ✅ Complete

## Changes

### Bug 2 — `{{}}` 빈 템플릿 제거
- **파일:** `shared/publishers/hugo_writer.py` (`_clean_body`)
- **추가:** `re.sub(r"\{\{.*?\}\}", "", body_md)` — AI 생성 빈 템플릿 제거

### Bug 3 — 지도보기 평문 regex 추가
- **파일:** `pipelines/travel/writer.py`
- **추가:** `re.sub(r"\s*지도에서\s*보기\s*", "", content)`
- **범위:** 마크다운 링크 + blockquote + 평문 모두 커버

### Bug 4 — no_result backoff 메커니즘
- **파일:** `dispatcher.py`
- **추가:** blog_id별 30분 쿨다운 (cooldown.json 파일 기반)
- **함수:** `_get_cooldowns()`, `_set_cooldown()`, `_is_on_cooldown()`

## Verification
- ✅ 지도보기 평문 regex 정상 동작 확인
- ✅ backoff 함수 단위 테스트 통과 (cooldown 있음/없음)
- ✅ travel4-hugo dispatcher 실행 정상 (quota 도달, GUARD 통과)

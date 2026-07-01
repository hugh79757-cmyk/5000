# Plan 04-01 Summary: Formatting Fixes — CTA + Thumbnail

**Executed:** 2026-07-01
**Status:** ✅ Complete

## Changes

### Bug 1 — `_clean_body()` HTML 태그 제거 regex 삭제
- **파일:** `shared/publishers/hugo_writer.py`
- **삭제:** `re.sub(r"</?[^>]+>", "", body_md)` — 모든 HTML 태그를 제거하던 regex 제거
- **추가:** DOTALL regex로 `## (함께|관련|추천) (읽어보기|읽을거리|글|포스트)` 섹션 제거 (AI 가짜 내부링크)

### Bug 5 — `_build_frontmatter_blowfish()` 썸네일 키 복원
- **파일:** `shared/publishers/hugo_writer.py`
- **변경:** `cover:`/`image:` → `featureimage:`
- **이유:** travel4-hugo Blowfish 테마가 `featureimage:` 키 사용

## Verification
- ✅ HTML CTA 보존 확인 (import 테스트)
- ✅ `featureimage:` 키 출력 확인
- ✅ DOTALL 섹션 제거 확인
- ✅ `{{}}` 템플릿 제거 확인

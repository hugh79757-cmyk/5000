# Plan 05-02 Summary: Blowfish 업그레이드 + DOTALL 확장

**Executed:** 2026-07-01
**Status:** ✅ Complete

## Changes

### Blowfish 테마 업그레이드
- **버전:** v2.103.0 (git submodule)
- **경로:** `/Users/twinssn/Projects/TAP/travel4-hugo/themes/blowfish`

### `_build_frontmatter_blowfish()` 복원
- **파일:** `shared/publishers/hugo_writer.py`
- **변경:** `featureimage:` → `cover:`/`image:` (Blowfish v2.x 정식 지원 포맷)
- Phase 4의 임시 fix를 원복

### DOTALL regex 확장
- **패턴:** `r"\n+##\s*(함께|관련|추천|더)\s*(읽어보기|읽을거리|글|포스트|게시물|기사).*"`
- **추가:** `더`, `게시물`, `기사` 패턴 커버
- **검증:** `## 더 읽어보기`, `## 추천 게시물` 모두 제거 확인

---
date: 2026-08-27
type: fix
status: resolved
---

# Dashboard 체커 거짓양성 2건 수정 (c08 + _index.md)

## What
대시보드 상태파악 오류의 대다수가 체커 거짓양성. c08_live_file_mismatch(permalink 오탐) + FM-MISSINGKEYS/FM-DRAFT/frontmatter(_index.md 스캔 오탐) 수정.

## Why
- c08: `_crawl_post`가 라이브 URL `https://{domain}/{slug}/`만 가정. 실제 Hugo permalink는 `https://{domain}/posts/{slug}/` → 전 85 블로그 TITLE_MISMATCH+OG_MISSING 오탐.
- FM: `_read_post_files`가 `content/posts/_index.md`(섹션 인덱스, 최소 frontmatter)를 포스트로 오인 → 전 블로그 키 누락 오탐.

## Files changed
- ops_dashboard/checks/content_integrity.py (`_post_url_candidates` 추가, `_read_post_files`에 `_index.md` 스킵)

## How
- c08: `/posts/{slug}/` 우선 후보 + fallback, slug 유니코드 인코딩, soft-404(og:title 404) 배제.
- FM: `if md_file.name == "_index.md": continue`.
- 부수: check_results 스테일 fail 행 갱신 (c08 85→0 삭제, frontmatter 41→5, FM-MISSINGKEYS 71→7, FM-DRAFT 7→0). 백업 ops_dashboard/ops.db.bak_*.

## Verification
- bus-hugo c08 위반 322→5 (실제 5건만 잔류). check_frontmatter 재실행으로 FM 대거 소거 확인. py_compile OK.
- c06_mtime_deploy는 대시보드 뷰에서 이미 INFO 버킷 분리 → 수정 불필요 확정.

## Next observation
해당 없음 (resolved). 다만 c08는 24h 캐시 → 다음 라이브 크롤에서 실제 위반 재출현 확인 가능.

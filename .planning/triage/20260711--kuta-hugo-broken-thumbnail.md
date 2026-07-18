---
date: 2026-07-11
type: fix
status: resolved
---

# kuta-hugo 썸네일 깨짐 — featureimage URL 미스매치

## What
kuta-hugo `부산 동래구 온천천 카페 추천 핫플레이스 5곳` 포스트의 썸네일이 브라우저에서 깨져 보임.

## Why
`featureimage`가 `img-kuta.informationhot.kr/images/kuta/{slug}/thumbnail.webp`로 설정돼 있었으나, 이 도메인(`img-kuta.informationhot.kr`)은 WordPress XML-RPC 용도로만 구성되어 `/wp-content/uploads/` 경로만 서빙 가능. `/images/` 경로에 해당하는 백엔드 인프라가 없어 404 발생.

**근본 원인**: 이 포스트는 5000 pipeline이 아닌 외부 경로로 발행되었고, `batch_thumbnails.py`가 실행되지 않아 R2에 썸네일이 없었음.

## How
1. `batch_thumbnails.py --slug "20260617-212002-부산-동래구-카페-추천-핫플레이스-5곳"` 실행
   - `thumbnail_generator/generator.py` → 썸네일 생성
   - `r2_uploader.py` → R2 업로드
   - `publishers/hugo_writer.py` → frontmatter `featureimage` 업데이트
2. R2 URL `https://pub-2f5c7af1c303419a933069212bc25874.r2.dev/thumbnails/kuta/20260617-212002-부산-동래구-카페-추천-핫플레이스-5곳.webp` → HTTP 200 확인
3. index.md의 `featureimage`가 올바른 R2 URL로 변경됨

## Investigation (부수적 발견)
Auto-publisher 시스템(`md-editor-nicegui`) 조사 결과:
- `core/publish/auto_scheduler.py`는 30분마다 blogsmith `output/` 폴더 MD 파일을 Hugo로 발행
- 발행 시 `make_thumb()` → `thumbnail_gen.py`(gradient overlay)로 썸네일 자동 생성
- `hugo.py:publish_to_hugo()` → R2 업로드 → `featureimage` 세팅 → wrangler deploy
- ✅ blogsmith 발행 글은 썸네일 자동 생성됨
- ❌ 5000 pipeline 발행 글은 `batch_thumbnails.py` 수동 실행 필요

## Files changed
- `content/posts/20260617-212002-부산-동래구-카페-추천-핫플레이스-5곳/index.md` — featureimage URL 수정

## Verification
- `curl -I "https://pub-2f5c7af1c303419a933069212bc25874.r2.dev/thumbnails/kuta/20260617-212002-부산-동래구-카페-추천-핫플레이스-5곳.webp"` → HTTP 200
- `index.md` frontmatter에서 `featureimage` R2 URL 정상 확인

---
date: 2026-07-18
type: fix
status: resolved
---

# CUAP 이미지 IMAGE-GUARD default-thumbnail.webp + WebP 변환

## What
- 기존 22개 CUAP 블로그 글의 이미지가 모두 `default-thumbnail.webp`로 보이는 버그 수정
- R2 이미지 624개 전량 WebP(format) 변환으로 용량 90% 감소

## Why
- `shared/publishers/hugo_writer.py` IMAGE-GUARD가 Coupang 이미지 URL(300~500자)이 macOS 255자 제한을 초과 시 `default-thumbnail.webp`로 강제 대체
- 원래 laptop-hugo 파일명 길이 문제 해결용이었으나 모든 CUAP 블로그에 부작용
- 기존 R2 이미지들은 원본 JPEG/PNG 포맷 그대로 업로드 (키만 `.webp`), 97KB~669KB

## Files changed
- `shared/publishers/hugo_writer.py` — `_upload_image_to_r2()` 추가: 긴 URL → R2 업로드(짧은 MD5 해시명, 16자). `_convert_to_webp()` 추가: Pillow quality=75 method=6 WebP 변환. `_download_image_bytes()`, `_save_image_static()` fallback helper 추가
- 7개 CUAP Worker 사이트 (`appliance/baby/beauty/camping/health/laptop/pet-hugo`) — `src/index.js` 생성 + wrangler deploy

## How
1. `hugo_writer.py` IMAGE-GUARD: 기존 `default-thumbnail.webp` 대체 로직을 R2 업로드로 변경
   - `_upload_image_to_r2(url, site_path)` — Coupang URL MD5[:16] → R2 `curation-images/thumbnails/{hash}.webw`
   - `_convert_to_webp(data, quality=75)` — Pillow Image.open → save WEBP quality=75
   - 실패 시 Hugo `static/img/{hash}.{ext}` fallback
2. 기존 R2 이미지 624개 전량 WebP 변환 스크립트
   - boto3 list_objects_v2 → curation.db products.product_image hash 매칭 → httpx 다운로드 → Pillow WebP 변환 → s3.put_object(ContentType=image/webp) 덮어쓰기
3. Workers + Assets 사이트 7개: `src/index.js` (env.ASSETS.fetch stub) 추가 + wrangler deploy

## Verification
- 배포 후 curl 확인: Content-Type `image/webp`, 97KB → 9KB (90%+ reduction)
- 향후 신규 글은 `_upload_image_to_r2()`가 자동 WebP 변환 후 R2 업로드

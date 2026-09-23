---
date: 2026-09-03
type: fix
status: resolved
---

# ETAP image_fetcher city pollution batch fix (24 pipelines)

## What
Watersports 본문 이미지 0건 장애 재발: `fetch_city_image(city + " water sport", ...)` 오염 → Pexels 쿼리 `Kampot water sport Cambodia skyline cityscape` 0건 → body 0. 동일 패턴이 ETAP 24개 pipeline 47줄에 확산. 일괄 수정 + 방어막 확장 + 대표 배포.

## Why
- watersports_pipeline 49건 복구 후 전수 grep 결과: `city + " ..."` 오염이 adventure/luxury/dining/daytrips/escape/extreme/multiday/citytours/cruise/culture/phototour/hiking/nomad/nature/nightlife/foodtour/ghost/layover/ferry/walking/watertours/transfers/bus/ferry/deals 24개에 동일 존재
- image_fetcher _clean_city 리스트 20개만 커버 → `hiking trail mountain`, `luxury private tour`, `food tour` 등 미커버 시 여전히 오염 → relevance 필터 전멸 → cover 0 / body 0
- body fallback은 generic `tropical beach...` 2차 추가로 최악 회피했으나 cover는 방어 약함

## Files changed
- pipelines/etap/image_fetcher.py: _clean_city 20→47 suffix 확장 (water sport~airplane 전수) + fetch_* 진입부 _clean_city 호출 유지
- pipelines/etap/adventure_pipeline.py, citytours_pipeline.py, cruise_pipeline.py, culture_pipeline.py, daytrips_pipeline.py, dining_pipeline.py, escape_pipeline.py, extreme_pipeline.py, foodtour_pipeline.py, ghost_pipeline.py, hiking_pipeline.py, layover_pipeline.py, luxury_pipeline.py, multiday_pipeline.py, nature_pipeline.py, nightlife_pipeline.py, nomad_pipeline.py, phototour_pipeline.py, transfers_pipeline.py, walking_pipeline.py, watertours_pipeline.py, bus_pipeline.py, ferry_pipeline.py, deals_pipeline.py: 각 2줄 `fetch_city_image/body_images(city + " ...")` → `fetch_city_image/body_images(city, ...)` pure
- (watersports_pipeline.py는 이전 커밋에서 선수정)

## How
1. `grep -o '" [a-z ]+"'` 로 오염 suffix 전수 추출 41 unique → _clean_city 리스트로 합침
2. sed 일괄 치환: `fetch_city_image(city + "[^"]+",` → `fetch_city_image(city,` / body 동일, search_term/_dest_for_cover도 동일 치환
3. `grep city+` 0건 확인
4. HUGO_THEMESDIR=/Users/twinssn/Projects/shared-themes hugo --gc --minify 24개 블로그 빌드 검증 (hiking 1119ms, extreme 1377ms 등 전수 pass)
5. `env -u CLOUDFLARE_API_TOKEN wrangler pages deploy` 대표 3개(hiking/extreme/bus) 배포 성공 확인

## Verification
- grep `fetch_.*city + "` / `search_term + "` / `_dest_for_cover + "` → 0건 (airlines만 의도적 airline suffix 잔존)
- Hugo 24개 빌드 Cleaned 0 / 에러 0
- Wrangler 3개 배포 Success (hiking 84a1741b, extreme 192ac519, bus b2d46eac)
- _clean_city 단위 방어: `Kampot water sport` → `Kampot` strip 확인

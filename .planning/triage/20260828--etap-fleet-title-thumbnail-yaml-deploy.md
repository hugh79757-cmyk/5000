---
date: 2026-08-28
type: fix
status: resolved
---

# ETAP Fleet: Title De-templating + Thumbnail Regeneration + YAML Repair + Deploy

## What

ETAP 36개 블로그 전수 조사 후 타이틀·썸네일·YAML frontmatter·광고 설정 일괄 수정 및 배포.

## Why

1. **타이틀 템플릿 반복**: LLM 생성 타이틀이 "X to Y by Bus:" 패턴 등 6~17개 블로그에서 반복 사용 → SEO 중복, 리더审美 저하
2. **썸네일 동일 이미지**: `fetch_city_image`의 first-pick 충돌 — 동일 origin 도시에서 검색 시 동일 Pexels 사진 반환 → bus(10개), extreme(20개), ghost(20개), ferry(17개), flights(9개) 등 28개 블로그에서 발생
3. **YAML frontmatter 파싱 실패**: LLM이 생성한 frontmatter에 미인용 콜론, 멀티라인 값, `%` 인코딩 슬러그 등 YAML-unsafe 패턴 존재 → Hugo 빌드 실패
4. **bus 블로그 광고 미노출**: stale 배포 (slot 값 미설정 상태), double loader (head/custom.html + extend-head.html)
5. **bus_pipeline.py:124 썸네일 근본 원인**: `search_term + " bus station"` + country="" → 관련성 필터reject → 폴백으로 동일 generic 사진 반복

## Files changed

### Pipeline code
- `pipelines/etap/bus_pipeline.py:124` — thumbnail 검색 쿼리 수정 (`search_term + " bus station"` → `f"{origin} {dest}.strip()"`)

### Blog content (36 blogs × N posts)
- `/Users/twinssn/Projects/ETAP/*-hugo/content/posts/*/index.md` — frontmatter title, featureimage, YAML 구조
- `bus-hugo/layouts/partials/head/custom.html` — double loader 제거 (deprecation no-op)

### Skill
- `.claude/skills/etap-blog-audit/SKILL.md` (135 lines) — 재사용 가능한 ETAP 감사 스킬

### Scripts (임시)
- `/tmp/etap_batch_fix.py` — 타이틀+썸네일 일괄 수정 스크립트
- `/tmp/regen_bus_covers.py` — bus 썸네일 재생성
- `/tmp/etap_deploy_all.py`, `/tmp/etap_deploy_resume.py` — 배포 스크립트
- `/tmp/fix_etap_yaml.py` — PyYAML parser 기반 frontmatter 수리

## How

### 1단계: 진단 (fleet audit)
- subagent로 34개 ETAP 블로그 전수 조사: 커버 md5 체크, 타이틀 스캐폴드 패턴 검사, ad 설정 grep
- bus.techpawz.com 라이브 사이트 광고 설정 분석 (ADSENSE-GUIDE.md 대조)
- worst offenders 식별: extreme(20+7), ghost(20), ferry(17), flights(17+9), deals(7+5)

### 2단계: 타이틀 디템플릿화
- `shared.ai_writer.generate` + anti-template 프롬프트 (temperature=0.85)
- regex 금지 패턴: `r'\bto\b.+\bby [Bb]us:'` 등 블로그별 토픽 adapt
- 스캐폴드 유니크 체크 (STOP words 제거 후 skeleton 비교)
- bus: 10개 전체, 나머지 34 블로그: 182개 — 총 192 타이틀

### 3단계: 썸네일 재생성
- `fetch_city_image` first-pick 회피: `_search_with_fallback(q, per_page=25)`로 후보 수집
- run-wide `seen` set으로 배치 내 유니크 보장
- `_upload_to_r2(force=True)` 필수 (force=False = 기존 URL 반환, no-op)
- bus: 10개, 나머지 34 블로그: 28개 — 총 38 커버

### 4단계: YAML frontmatter 수리
- 1차: regex 기반 수정 → 실패 (double-quote, orphan continuation 등 2차 오염)
- 2차: `yaml.safe_load()` → validate → `yaml.dump()` 파서 기반 재작성
- 추가 수정: `%` 인코딩 슬러그 인용, params 키 삭제, 중복 키 제거, nested quote 해소
- 결과: 36/36 Hugo 빌드 성공

### 5단계: bus 광고 수정 + 배포
- `head/custom.html` double loader 제거
- slot 값 확인 (6685009950, ca-pub-8772455780561463)
- `deploy_site()`로 bus-hugo 배포 + 라이브 검증

### 6단계: 전체 배포
- 36개 블로그 hugo build → wrangler pages deploy
- 2회 네트워크 타임아웃 후 재시도로 전체 완료

## Verification

- **슬러그 무변경**: 디렉토리명 = 프론트매터 slug, spot-check 확인
- **커버 유니크**: curl + md5로 상위 20포스트/블로그 검증, 0개 동일
- **타이틀 다양성**: 스캐폴드 패턴 repeat ≤ 2, exact-dup 0
- **YAML 구조**: 36/36 Hugo 빌드 성공 (ERROR 0건)
- **라이브 배포**: 36/36 wrangler pages deploy 성공
- **백업 존재**: `.bak_title_*`, `.bak_cover_*`, `.bak_yaml_*` 파일 확인
- **bus 라이브 검증**: ad slot 4개 렌더링, empty slot 0, single loader

## Residual risks

- `bus.techpawz.com` 도메인이 AdSense 8772 계정에 등록/승인되었는지 확인 필요 (코드로 검증 불가)
- 33개 블로그 `head/custom.html` double loader 잔존 (user 지시로 skip)
- `michelin-hugo` extend-head.html에 params loader 없음 (head/custom.html에만 의존)
- 배포 중 `pages` 카운트가 0으로 표시됨 (Hugo 출력 파싱 문제, 배포는 정상)

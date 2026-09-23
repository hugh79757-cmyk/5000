---
date: 2026-08-28
type: fix
status: ongoing
---

# ETAP YAML Frontmatter Repair (36 blogs)

## What
34개 ETAP 블로그 타이틀+썸네일 수정 후 배포 시도 → YAML frontmatter 깨짐 발견 → PyYAML 파서 기반 수리

## Why
타이틀 비템플릿화 + 썸네일 고유화 작업 후 배포过程中, `hugo --gc --minify`가 YAML 파서 에러로 실패.
원인: (1) unquoted colons in titles (2) multiline values without quotes (3) `categories: - X` → 한줄 합침 (4) percent-encoded slugs (`%E0%B8%AD...`)가 YAML 예약어 충돌 (5) `description: [Hook:...]` → YAML 리스트로 해석 (6) nested quotes (`"'text'"`) 파싱 실패

## Root Cause of the Fix Complexity
최초에 regex 기반 YAML 수정 스크립트를 4-5번 반복 적용 → 오히려 정상 파일까지 망가뜨림.
원래 YAML 파서(PsyAML)를 처음부터 썼어야 했음.

## Files changed
- `/Users/twinssn/Projects/ETAP/*-hugo/content/posts/*/index.md` — 36개 블로그 전체 프론트매터
- `/Users/twinssn/Projects/ETAP/airports-hugo/config/_default/hugo.toml` — themesDir 없음 확인 (build OK)

## Approach
1. **1차 시도 (regex 스크립트)**: unquoted colon → 따옴표 추가. 107건 성공.
2. **2차 시도**: multiline values 병합. 4,639건 수정. → orphan continuation 생성 부작용.
3. **3차 시도**: orphan 병합. 1,081건. → double-quoting 부작용 (`""text""`).
4. **4차 시도**: nested quote 해제 + 재인용. 9,820건. → `categories: - X` 합침 깨짐.
5. **5차 시도**: list-on-same-line 수정. 1,523건. → 19개 블로그 빌드 실패.
6. **최종 (PyYAML 파서)**: `yaml.safe_load()` → 실패 시 targeted repair → `yaml.dump()` 재작성.
   - percent-encoded slug 따옴표 추가 (9건)
   - `description: [Hook:...]` 따옴표 추가 (1건)
   - nested quotes `"'text'"` 해체 (3건: eurail 2, michelin 1)

## Verification
- 36개 블로그 모두 `hugo --gc --minify` 빌드 성공 확인 필요 (진행 중)
- 배포 대기 중

## 잔존 위험
- PyYAML `dump()`가 원본 frontmatter 순서/포맷을 변경했을 수 있음 (knowledge graph 등)
- `featureimage` URL이 일부 잘린 파일 존재 가능 (dining-hugo의 `michelin-makati` → URL 복원함)
- percent-encoded slug 따옴표 추가가 Hugo 빌드에 영향 있는지 추가 검증 필요

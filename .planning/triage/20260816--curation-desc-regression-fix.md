---
date: 2026-08-16
type: fix
status: resolved
---

# curation 상품 설명 문단 소실 회귀 수정 (imgmap-pagekey-fix 직후 회귀)

## What
appliance/pet 등 curation 계열 블로그에서 H3 상품 제목 아래 상품 설명 문단이 소실되는 회귀를 수정. 직전 커밋 `imgmap-pagekey-fix-20260816`(a1a2f0816)로 상품 이미지는 5/5 정상 삽입됐지만 H3 → figure → (설명 없음) → H3 패턴으로 설명 문단이 통째로 사라짐.

## Why
`pipelines/curation/pipeline.py` `_normalize_product_blocks()` (5) 이미지 삽입 블록의 `i = j - 1` 스킵이 H3~다음 헤딩 사이 본문(설명 문단·불릿·CTA)을 `out`에 append하지 않고 버림. url 매칭(방식A pageKey 역추적 / 방식B _norm·_tokens 매칭) 여부와 무관하게 모든 H3에서 발생.

## Files changed
- `pipelines/curation/pipeline.py` — `_normalize_product_blocks()` line 1293 `i = j - 1  # 처리한 구간 건너뛰기` 1줄 제거 (-1)

## How
루프가 라인별로 전부 append하도록 복귀 (커밋 a1a2f0816^ 구코드 방식). H3 다음 줄에 figure 삽입 유지 → `### 제목 → {{< figure >}} → 설명 문단 → CTA` 정상 구조 복원. figure 통일·pageKey 매핑 로직은 그대로 유지.

## Verification
- 백업 `pipeline.py.bak_descfix_20260816_014458` + git tag `pre-descfix-20260816` 생성
- 함수 단위 테스트 (재발행 없이 AST 추출 + curation.db SELECT만 사용): appliance/pet 각각 설명 보존 5/5, figure 5/5, src 정확(DB product_image 일치) 5/5, 마커 소실 diff []
- `py_compile` OK
- 커밋 `98d2b1b01` + tag `descfix-20260816`
- 실발행 2편 (appliance-hugo 10만원대 무선청소기 / pet-hugo 고양이 생일 케이크): 5/5 H3 블록에서 `### 제목 → figure → 설명 → CTA(pageKey) → H3` 라이브 구조 확인, VALIDATE ✅ 0 issues, 라이브 200 OK
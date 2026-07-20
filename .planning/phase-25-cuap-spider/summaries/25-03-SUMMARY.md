# Phase 25 Wave 3 Summary — Hugo layout integration

**Date:** 2026-07-20

## Tasks
- T5: Create `cuap-spider-links.html` partial (10 copies)
- T6: Update `single.html` to use cuap-spider-links.html (10 copies)

## Deliverables
- 10 × `cuap/{blog}-hugo/layouts/partials/cuap-spider-links.html`
  - Cross-blog data 있으면 `.Content` 렌더, 없으면 `related.html` fallback
- 10 × `cuap/{blog}-hugo/layouts/_default/single.html`
  - Line 85: `{{ partial "related.html" . }}` → `{{ partial "cuap-spider-links.html" . }}`

## Fix Applied
- 초기 작성 시 `{{/* ... */}}` 주석에 `*/` 문자열 포함으로 Hugo parse 에러 발생
- 주석을 `*/` 없는 영문으로 재작성 → 빌드 성공

## Verification
- T5: PASS (10 partials exist + content check)
- T6: PASS (10 single.html updated, no related.html remaining)
- Hugo build (appliance-hugo): PASS (Total in 781 ms, no errors)

## Committed in: 10 CUAP blog repos

## Status: ✓ COMPLETE

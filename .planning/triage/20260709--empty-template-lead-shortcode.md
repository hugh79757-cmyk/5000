---
date: 2026-07-09
type: fix
status: resolved
---

# Hugo 빈 템플릿 `{{}}` 오류 — `_extract_description`가 `{{< lead >}}` → `{{}}` 생성

## What
발행 검증 단계에서 `{{}}` 빈 템플릿이 발견되어 Hugo 빌드 실패 또는 경고 발생.
해당 현상이 interior-hugo, rap2-hugo에서 확인됨.

## Why
`_extract_description()`가 `_build_schema_json()`에서 호출될 때,
HTML 태그 제거 정규식 `re.sub(r"<[^>]+>", "", body_md)`가
`{{< lead >}}`에서 `< lead >` 부분만 제거하고 `{{}}`를 남김.
이 `{{}}`가 JSON-LD schema description에 기록되었고,
이후 Hugo가 `{{}}`를 빈 템플릿으로 해석하여 에러 발생.

## Files changed
- `shared/publishers/hugo_writer.py`

## How
1. `_extract_description()`에 Hugo shortcode 먼저 제거 로직 추가:
   ```python
   clean = re.sub(r"\{\{<[^>]*?>}}", "", clean)  # shortcode 제거 후
   clean = re.sub(r"<[^>]+>", "", clean)  # HTML 태그 제거
   ```
2. `_build_schema_json()`이 shortcode 변환 전에 추출한 description을 직접 전달받도록 수정:
   ```python
   schema_json = _build_schema_json(..., description=description)
   ```
   (shortcode 변환 후 body에서 재추출하지 않음, fallback 유지)

## Verification
코드 리뷰 완료. 실제 재발행 테스트 필요.

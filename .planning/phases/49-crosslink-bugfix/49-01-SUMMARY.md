# 49-01 SUMMARY — Root Cause Fix (Wave 1)

**Phase:** 49-crosslink-bugfix | **Plan:** 49-01 | **Wave:** 1
**Commit:** `4b33b43fd` — `fix(crosslink): add url return from _write_hugo_post() and file-based slug fallback`
**Executed:** 2026-07-26 | **Verified:** 2026-08-01 (이 세션 재검증)

---

## 근본 원인

크로스링크 URL slug 불일치(404)의 근본 원인은 `publisher.py`의 import override:

- `publisher.py:530` 로컬 `_write_hugo_post()`는 `{"success": True, "url": ..., "file_path": ...}`을 반환하지만,
- `publisher.py:762-770`에서 `hugo_writer._write_hugo_post()`로 **override**되며,
- `hugo_writer._write_hugo_post()`는 `{"success": True, "file": path}`만 반환 (**"url" 키 없음**).
- 결과적으로 `pipeline.py:1064`의 `result.get("url")`이 항상 None → `_make_slug(keyword)`의
  `20260726-{keyword}` 형식 date-prefixed slug가 fallback으로 사용 → 모든 크로스링크 404.

## 변경 내용

| 파일 | 변경 | 라인 |
|------|------|------|
| `shared/publishers/hugo_writer.py` | `_write_hugo_post()` return에 `"url"` 키 추가 (additive — `"file"` 키 보존) | ~978 |
| `pipelines/curation/pipeline.py` | slug 추출 3-tier fallback: `result["url"]` > `result["file"]` > keyword | 1075-1086 |
| `shared/cuap_entity_linker.py` | `build_cross_sell_card()` 희소 엔티티 경고 로깅 (`No published entity`, `len(items_html) < max_items`) | 334, 353 |

커밋 통계: 3 files, +26/-4 lines.

## 검증 결과

### [검증됨] — 코드 상태 (2026-08-01 재확인)

- `hugo_writer.py:978` — `return {"success": True, "file": file_path, "url": expected_url}` 존재.
  근거: `sed -n '970,980p'` 직접 확인. `"file"` 키 보존됨 (STAP/TAP 호출자 안전).
- `pipeline.py:1075-1086` — 3-tier fallback 완전 구현. 근거: 소스 직접 확인 + `from pathlib import Path` 이미 import (라인 12, 추가 import 없음).
- `cuap_entity_linker.py:334,353` — 경고 로깅 존재. 근거: `grep -n "No published entity\|len(items_html) < max_items"`.
- Python 문법: 3개 파일 `ast.parse` 통과.
- Phase 48 호환: 커밋 `4b33b43fd`의 hugo_writer.py diff는 return 문 1줄 변경뿐.
  근거: `git show 4b33b43fd -- shared/publishers/hugo_writer.py`에서 `_build_frontmatter_*` 함수 변경 0건.
- 커밋 메시지: `fix(crosslink): add url return from _write_hugo_post() and file-based slug fallback` — plan 요구사항 일치.
- 커밋이 `main` 및 현재 브랜치 HEAD의 조상 — 병합 완료.

### [부분검증] — 신규 발행 방지 효과

- Wave 1은 "다음 발행분부터" 올바른 slug로 등록하는 방지책. 신규 발행 후 크로스링크가
  올바른지의 라이브 확인은 2026-07-26 ~ 08-01 사이 발행된 포스트의 실제 데이터로 검증됨
  (49-02/49-B 검증과 동일 기간 데이터). 단, 대기 중인 신규 발행이 없는 상태에서
  "새 발행 시 동작"을 라이브로 재현한 것은 아님 — 코드 경로 검증만 수행.

### [검증불가] — 라이브 HTTP 200 (이 세션)

- 라이브 서버 응답 코드 검증은 이 세션에서 수행하지 않음 (파일시스템 ground truth 기반
  검증만 수행). 2026-07-26의 49-B SCAN-REPORT가 전수 검증(9,840/9,840)을 기록.
  복구 계획: `curl -sIL`로 대상 URL 200 확인 (SCAN-REPORT Step 3 커맨드 재사용).

## 잔존 위험

- **파이프라인 코드 최신 상태**: 현재 브랜치(`fix/rap-subscription-backfill`)의
  working tree에 phase-49 무관한 수정(pipeline.py camping-hugo 필터 등)이 uncommitted로 존재.
  phase-49 코드 자체는 커밋 상태와 일치 (`git diff` 0건).
- **unpublished stale row**: Wave 2 이후에도 `published=0` date-prefixed 잘못된 slug 10건이
  잔존 — 49-02 검증에서 정리 완료 (이 세션).

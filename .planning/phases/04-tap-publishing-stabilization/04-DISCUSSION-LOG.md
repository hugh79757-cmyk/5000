# Phase 4: TAP Publishing Stabilization — Post-Refactoring Bug Fixes (Discussion Log)

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-01
**Phase:** 4 — TAP Publishing Stabilization
**Areas discussed:** 5 post-refactoring regressions, root cause tracing, fix strategies

---

## Bug 발견 경위

사용자가 June 30일 발행 글(경기 양평)과 July 1일 발행 글(경북 무섬마을)을 비교하던 중
5가지 품질 저하 발견. 두 글 모두 travel4-hugo 블로그에서 발행되었으며,
commit `d722aab0b` (June 30 21:15 KST, shared/paths.py + publisher submodule) 사이에 리팩토링이 발생.

## 각 버그 분석

### Bug 1 — Trip.com CTA HTML 제거

| 항목 | 내용 |
|------|------|
| 증상 | CTA 영역(기존: `<div class="cta-box">...`, 현재: `  트립닷컴에서 최저가 확인하기` 평문) |
| 원인 | `_clean_body()`에 추가된 `re.sub(r"</?[^>]+>", "", body_md)` |
| 확정 | hugo_writer.py:96 — HTML 태그를 전부 제거 |
| 영향도 | 심각 — 수익 링크 손실, 사용자 경험 저하 |

### Bug 2 — `{{}}` 빈 템플릿 잔재

| 항목 | 내용 |
|------|------|
| 증상 | 발행 글 하단에 `{{}}`가 그대로 노출 |
| 원인 | writer.py:688-691에서 `## 함께 읽어보기` 섹션만 제거. |
| 확정 | 옛 `_clean_body`의 DOTALL regex(`## 함께 읽어보기` 섹션 통째로 제거)가 refactoring 후 사라짐. |
| 영향도 | 중간 — 미관상 문제, 기능적 영향 없음 |

### Bug 3 — "지도에서 보기" 평문 노출

| 항목 | 내용 |
|------|------|
| 증상 | "영주축협한우프라자 본점...지도에서 보기"로 평문 노출 |
| 원인 | AI가 마크다운 링크 대신 평문 생성. regex는 마크다운 링크만 매칭 |
| 확정 | writer.py:724 — `re.sub(r"\s*\[네이버 지도에서 보기\]\(https://map\.naver\.com[^)]*\)", "")`는 마크다운만 매칭 |
| 영향도 | 낮음 — 미관상 문제, 단 June 30일 글에도 존재하던 기존 이슈 |

### Bug 4 — `no_result` 무한 재시도

| 항목 | 내용 |
|------|------|
| 증상 | 파이프라인이 None 반환 시 계속 재시도 |
| 원인 | dispatcher.py:512 — `if result is None: status = "no_result"` |
| 확정 | backoff 메커니즘 부재 |
| 영향도 | 중간 — 리소스 낭비 + Telegram 알림 폭주 |

### Bug 5 — 썸네일 누락

| 항목 | 내용 |
|------|------|
| 증상 | 썸네일 이미지 미표시 |
| 원인 | `_build_frontmatter_blowfish()`의 썸네일 키: `featureimage:` → `cover:`/`image:` |
| 확정 | commit `d722aab0b`에서 변경. travel4-hugo Blowfish 테마는 아직 `featureimage:` 사용 |
| 영향도 | 심각 — 사용자 경험 저하, 클릭률 감소 |

---

## Fix 전략 비교

### _clean_body 수정

| Option | Description | Selected |
|--------|-------------|----------|
| HTML 태그 regex 제거 | `re.sub(r"</?[^>]+>", "")` 줄만 삭제 | ✓ |
| CTA 이후에만 적용 | CTA 삽입 후 clean 실행 → 순서 변경 | |
| 화이트리스트 방식 | 특정 태그만 허용 | |

**선택:** HTML 태그 regex 제거. body_md는 HTML을 포함할 수 있음.

### 썸네일 키

| Option | Description | Selected |
|--------|-------------|----------|
| `featureimage:`으로 복원 | Hugo 테마 변경 없이 즉시 해결 | ✓ |
| 테마 업데이트 | Blowfish 2.x로 업그레이드 후 `cover.image:` 사용 | |
| 둘 다 지원 | frontmatter에 두 키 모두 출력 | |

**선택:** `featureimage:`으로 복원. 테마 업그레이드는 별도 작업.

---

*Phase: 4 — TAP Publishing Stabilization*
*Discussion logged: 2026-07-01*

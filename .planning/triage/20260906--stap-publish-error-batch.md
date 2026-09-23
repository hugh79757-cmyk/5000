# 20260906 — STAP 발행 에러 배치 트리아지

## 알림 원문 요약

- stock-hugo SyntaxError (writer.py import 실패)
- laptop/fitness title_blocked (P10), kitchen duplicate_slug (P16), camping offtopic (P14)
- escape-hugo 단어수 372<400, ipo/nature no_content·연속실패 (P02)
- BC 큐 소진 (bc-aside)

## 분류

| 항목 | 분류 | 결과 |
|---|---|---|
| stock writer.py:962 nested quote | REAL, FIX #1 | stray `system_prompt=` 제거, ast.parse/py_compile OK |
| `** ` 제목 prefix 오염 (ipo 1건 라이브, finance 1건 title+tags+categories) | REAL, FIX #2 | 5개 writer 파서 정리 + 콘텐츠 2건 수정 + Pages 배포 2건 (rc=0) + 라이브 `<title>` 무열 확인 |
| laptop P10 3x | transient | 10:42-11:01 실패, 13:30 수동 재현 정상 — economy LLM 일시 불안 자가회복 |
| fitness P10 1x | transient | 11:23 성공 |
| kitchen P16 1x | transient | 11:33 성공 |
| escape 단어수 | transient | 13:28:52 발행 성공 |
| camping P14 식기/난로 | data-quality transient | CATEGORY_FILTERS `가전` substring가 가전디지털 난로 차단 → 식기 캐시 재수집 자가회복. 히터 allowed 추가는 승인 대기 |
| ipo P02 1x | transient | 같은 날 2건 발행 |
| nature P02 5x | fail-closed 정상 | S01/S02/S03 게이트 동일구조 제목 거부 후 13:39 통과 발행. 구조 다양성 개선은 긴급 아님 |
| BC 큐 소진 | REAL 미해결 | bc-seed-collection 스킬 실행 필요 — 별도 작업 |

## 함정 기록

STAP *-hugo 빌드 시 `-t PaperMod` 플래그 금지 — hugo.toml `theme=blowfish`를 덮어 `partial "hero/basic.html" not found` 에러. 플래그 없이 `hugo --gc --minify --source <site>` 사용.

## 잔존 위험

1. BC seed 큐 소진 미해결 (스킬 실행 필요)
2. camping 히터 allowed 추가 — 승인 대기
3. nature 구조 다양성 — 재발 가능, 긴급 아님
4. STAP 수정분 미커밋 (writer 5파일 + 콘텐츠 2건) — 커밋 요청 시 기존 미커밋 diff와 분리 권장

상세: `.planning/worklog/WL-20260906-stap-publish-error-triage.md`

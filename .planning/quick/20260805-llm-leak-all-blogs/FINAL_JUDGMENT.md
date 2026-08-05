# Phase D 최종 판정표 (실측 기반)

## 요약

| 항목 | 값 |
|------|-----|
| 검증 대상 | CAP 8 + TAP 5 = 13 블로그 |
| Phase A (dry-run) | 26/26 PASS (gemini-3.1-flash-lite) |
| 총 탐지 | 169건 (패턴별 173건 - 중복 4건) |
| 강한 오염 | 3건 (전부 hotissue-hugo, draft 처리됨) |
| CJK 오탐 | 116건 (한자 병기) |
| 스타일 이슈 | 54건 (과연/바랍니다 등) |
| draft 처리 | 8건 |

## 최종 판정표

| Blog | Phase A | 탐지 | 강한오염 | CJK오탐 | 스타일 | draft | 판정 | 근거 |
|------|---------|------|----------|---------|--------|-------|------|------|
| CAP/compare-hugo | PASS | 6 | 0 | 6 | 2 | 1 | **통과** | Chinese leak 1건 draft 처리됨 |
| CAP/deal-hugo | PASS | 10 | 0 | 0 | 10 | 0 | **통과** | 스타일 이슈만 |
| CAP/ev-hugo | PASS | 10 | 0 | 0 | 10 | 0 | **통과** | 스타일 이슈만 |
| CAP/guide-hugo | PASS | 10 | 0 | 0 | 10 | 0 | **통과** | 스타일 이슈만 |
| CAP/hotissue-hugo | PASS | 16 | 3 | 2 | 12 | 4 | **조건부** | 강한 오염 3건, 전부 draft 처리됨 |
| CAP/tco-hugo | PASS | 1 | 0 | 0 | 1 | 0 | **통과** | 스타일 이슈 1건 |
| CAP/rank-hugo | PASS | 0 | 0 | 0 | 0 | 0 | **통과** | 무탐지 |
| CAP/pick-hugo | PASS | 0 | 0 | 0 | 0 | 0 | **통과** | 무탐지 |
| TAP/travel-hugo | PASS | 9 | 0 | 3 | 6 | 1 | **통과** | Chinese leak 1건 draft 처리됨 |
| TAP/travel1-hugo | PASS | 0 | 0 | 0 | 0 | 0 | **통과** | 무탐지 |
| TAP/travel2-hugo | PASS | 85 | 0 | 86 | 0 | 0 | **통과** | 전부 CJK 오탐 (한자 병기) |
| TAP/travel3-hugo | PASS | 6 | 0 | 3 | 3 | 2 | **통과** | Chinese leak 2건 draft 처리됨 |
| TAP/travel4-hugo | PASS | 16 | 0 | 16 | 0 | 0 | **통과** | 전부 CJK 오탐 (한자 병기) |

## 판정 기준

- **통과**: Phase A PASS + 강한 오염 0건 (또는 전부 draft 처리됨)
- **조건부**: Phase A PASS + 강한 오염 > 0건이나 전부 draft 처리됨
- **보류**: Phase A FAIL 또는 강한 오염 > 0건且 draft 미처리

## 조건부 블로그 상세 (hotissue-hugo)

| 포스트 | 패턴 | 상태 |
|--------|------|------|
| E2E Test Post | test_dummy | draft: true |
| Test Title with Cover | test_dummy | draft: true |
| i5 감가 vs M5 | forbidden_word_reverse | draft: true |
| K9 감가 3,474만원 | ko_thinking | draft: true |

→ 강한 오염 3건 전부 draft 처리됨. 신규 생성은 깨끗함 (Phase A PASS).

## 숫자 정합화

```
169 (총 탐지) = 116 (CJK 오탐) + 3 (강한 오염) + 54 (스타일) - 4 (중복)
169 = 173 - 4 = 169 ✓
```

## 잔존 위험

1. **스타일 이슈 54건**: forbidden_word_reverse (과연/바랍니다) — 미해결이나 오염 아님
2. **CJK 오탐 116건**: heritage 한자 병기 — 정상 콘텐츠, 수정 불필요
3. **hotissue-hugo 조건부**: draft 4건이 재발행되려면 수동 리뷰 필요

## unpause 커맨드 (실행 금지)

```bash
# ⚠️ 위험: sed 's/status: paused/status: active/'는 원래부터 paused였던 블로그까지 변경할 수 있음
# 대신 블로그 ID를 명시한 라인 타겟 편집 사용:

# CAP 8개 블로그 unpause
cd /Users/twinssn/Projects/5000
for blog in compare-hugo deal-hugo ev-hugo guide-hugo hotissue-hugo tco-hugo rank-hugo pick-hugo; do
  sed -i '' "/id: $blog/{n;n;n;n;n;n;n;n;n;n;n;n;n;s/status: paused/status: active/}" config/blogs.d/cap.yaml
done

# TAP 5개 블로그 unpause
for blog in travel-hugo travel1-hugo travel2-hugo travel3-hugo travel4-hugo; do
  sed -i '' "/id: $blog/{n;n;n;n;n;n;n;n;n;n;n;n;n;s/status: paused/status: active/}" config/blogs.d/tap.yaml
done
```

> **참고**: sed 패턴이脆弱할 수 있음. 안전한 방법은 YAML 파서 사용 또는 수동 편집.

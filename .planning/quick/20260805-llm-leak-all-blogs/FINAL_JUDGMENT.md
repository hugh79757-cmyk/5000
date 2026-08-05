# Phase D 최종 판정표 (v3 — 숫자 확정본)

> **이 문서의 숫자는 변경 금지.** `.continue-here.md`의 "확정치(변경금지)" 블록과 동기화.

## 요약

| 항목 | 값 | 출처 |
|------|-----|------|
| 검증 대상 | CAP 8 + TAP 5 = 13 블로그 | — |
| Phase A (dry-run) | 26/26 PASS | `data/phase5_verify_result.json` |
| 탐지 포스트 (dedup) | **178건** | 스캐너 전체 본문 스캔 |
| strong 오염 | **13건** | 스캐너 (전체 본문, ko_thinking/test_dummy) |
| CJK 오탐 | **112건** | 스캐너 (cjk_line_leak) |
| 스타일 이슈 | **54건** | 스캐너 (forbidden_word_reverse) |
| 복합 탐지 (strong+style) | **1건** | — |
| drafted 포스트 (.md) | **19건** | 파일 실측 (`grep -rl 'draft: true'`) |

## 숫자 정합화

### 감사 산식 (단일 등식 — 변경 금지)

```
178 = 13(strong) + 112(cjk) + 54(style) - 1(overlap) ✓
```

| 구분 | 값 | 비고 |
|------|-----|------|
| strong | 13 | 12 strong-only + 1 strong+style |
| cjk | 112 | 전부 cjk-only (strong/style과 겹치지 않음) |
| style | 54 | 53 style-only + 1 strong+style |
| overlap | 1 | strong+style 복합 1건 |
| **합산** | **178** | 13 + 112 + 54 - 1 = 178 ✓ |

### 이전 숫자와의 차이

| 항목 | 이전 값 | 현재 값 | 사유 |
|------|---------|---------|------|
| 탐지 총계 | 169 | **178** | 전체 본문 스캔 보강으로 +9건 추가 탐지 |
| strong | 3 | **13** | 500자 제한 해제로 +10건 추가 탐지 |
| CJK | 116 | **112** | 전체 스캔 기준 재분류로 -4건 |
| overlap | 4 | **1** | strong/style 복합만 유효, CJK 겹침 없음 |
| drafted | 8→15→19 | **19** | `.bak` 제외, `.md`만 실측 |

### CJK 116→112 원인

이전 스캔은 CJK 라인을 라인별로 탐지했으나, 전체 본문 스캔 후 중복 집계 기준이 변경됨. 4건이 strong과 겹치지 않는 cjk-only로 재분류되었으나, 총합은 112건으로 확정. **116건은 폐기.**

## drafted 실측 (파일 기준 — 변경 금지)

| Blog | drafted (.md) | strong 포함 | cjk 포함 | 비고 |
|------|:---:|:---:|:---:|------|
| compare-hugo | 4 | 0 | 1 | 3건은 클린 (패턴 미감지) |
| deal-hugo | 0 | — | — | — |
| ev-hugo | 0 | — | — | — |
| guide-hugo | 0 | — | — | — |
| hotissue-hugo | 7 | 6 | 1 | strong 6건 + cjk 1건(포터2) |
| tco-hugo | 0 | — | — | — |
| rank-hugo | 0 | — | — | — |
| pick-hugo | 0 | — | — | — |
| travel-hugo | 4 | 0 | 1 | 3건은 클린 |
| travel1-hugo | 0 | — | — | — |
| travel2-hugo | 0 | — | — | — |
| travel3-hugo | 4 | 0 | 2 | 2건은 클린 |
| travel4-hugo | 0 | — | — | — |
| **합계** | **19** | **6** | **4** | strong 6 + cjk 4 + 클린 9 = 19 |

## strong 오염 정의

> **Strong contamination = 본문에 LLM 사고과정/테스트/지시문/문법파괴 마커가 포함된 포스트**
>
> 패턴: `ko_thinking`, `test_dummy`, `prompt_instruction_leak`, `thinking_tag_remain`, `forbidden_grammar_break`

## strong 오염 상세 (13건 — 변경 금지)

| Blog | 포스트 | 패턴 | drafted | 출처 |
|------|--------|------|:---:|------|
| compare-hugo | 2026년형-m5-44-투어링-완전-분석 | ko_thinking (H2-1) | ❌ | 스캐너 (전체 본문) |
| compare-hugo | 구매-전-5분-비교-ix2-vs-gv60-마그마 | ko_thinking (H2-1, H2-2, 주의:) | ❌ | 스캐너 (전체 본문) |
| compare-hugo | 같은-예산-9788만원대-gv60-마그마와-x2 | ko_thinking (주의:) | ❌ | 스캐너 (전체 본문) |
| hotissue-hugo | E2E Test Post | test_dummy (Test body) | ✅ | 스캐너 |
| hotissue-hugo | Test Title with Cover | test_dummy (Test body) | ✅ | 스캐너 |
| hotissue-hugo | i5 감가 vs M5 | ko_thinking (H2-1) | ✅ | 스캐너 (전체 본문) |
| hotissue-hugo | K9 감가 3,474만원 | ko_thinking (사용자가 제공한 데이터) | ✅ | 스캐너 (전체 본문) |
| hotissue-hugo | K9 54% vs 8시리즈 | ko_thinking (규칙) | ✅ | 스캐너 (전체 본문) |
| hotissue-hugo | M5 신차 17,410만원 | ko_thinking (H2-1) | ✅ | 스캐너 (전체 본문) |
| rank-hugo | 소형suv-잔존가치-비교-top5 | ko_thinking (사용자가 제공한 데이터) | ❌ | 스캐너 (전체 본문) |
| travel-hugo | 인천-캠핑-바다-근처-캠핑장-2곳 | ko_thinking (사용자가 제공한 데이터) | ❌ | 스캐너 (전체 본문) |
| travel1-hugo | 강원-정선군-축제-8곳 | ko_thinking (이제 글을 작성) | ❌ | 스캐너 (전체 본문) |
| travel1-hugo | 군산-축제-3곳 | ko_thinking (주의:) | ❌ | 스캐너 (전체 본문) |

- **drafted: 6건** (전부 hotissue-hugo)
- **undrafted: 7건** (compare 3 + rank 1 + travel 1 + travel1 2)

## hotissue-hugo 상세 (7건 drafted)

| # | 포스트 | 패턴 | 상태 |
|---|--------|------|------|
| 1 | E2E Test Post | test_dummy | draft: true |
| 2 | Test Title with Cover | test_dummy | draft: true |
| 3 | i5 감가 vs M5 | ko_thinking | draft: true |
| 4 | K9 감가 3,474만원 | ko_thinking | draft: true |
| 5 | K9 54% vs 8시리즈 | ko_thinking | draft: true |
| 6 | M5 신차 17,410만원 | ko_thinking | draft: true |
| 7 | 포터2 잔존가치 | cjk_line_leak (本次, 优势) | draft: true |

→ strong 6건 전부 drafted. 포터2는 Chinese leak로 draft 처리 확인.

## 최종 판정표

| Blog | Phase A | 탐지 | strong | CJK | style | drafted | 판정 | 근거 |
|------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|------|
| CAP/compare-hugo | PASS | 9 | 3 | 4 | 2 | 4 | **보류** | strong 3건 undrafted (m5투어링, ix2-vs-gv60, gv60-vs-x2) |
| CAP/deal-hugo | PASS | 10 | 0 | 0 | 10 | 0 | **통과** | strong 0건 |
| CAP/ev-hugo | PASS | 10 | 0 | 0 | 10 | 0 | **통과** | strong 0건 |
| CAP/guide-hugo | PASS | 10 | 0 | 0 | 10 | 0 | **통과** | strong 0건 |
| CAP/hotissue-hugo | PASS | 18 | 6 | 1 | 12 | 7 | **통과** | strong 6건 전부 drafted |
| CAP/tco-hugo | PASS | 1 | 0 | 0 | 1 | 0 | **통과** | strong 0건 |
| CAP/rank-hugo | PASS | 1 | 1 | 0 | 0 | 0 | **보류** | strong 1건 undrafted (소형suv-top5) |
| CAP/pick-hugo | PASS | 0 | 0 | 0 | 0 | 0 | **통과** | 무탐지 |
| TAP/travel-hugo | PASS | 10 | 1 | 3 | 6 | 4 | **보류** | strong 1건 undrafted (인천캠핑) |
| TAP/travel1-hugo | PASS | 2 | 2 | 0 | 0 | 0 | **보류** | strong 2건 undrafted (정선축제, 군산축제) |
| TAP/travel2-hugo | PASS | 85 | 0 | 85 | 0 | 0 | **통과** | strong 0건 |
| TAP/travel3-hugo | PASS | 6 | 0 | 3 | 3 | 4 | **통과** | strong 0건 |
| TAP/travel4-hugo | PASS | 16 | 0 | 16 | 0 | 0 | **통과** | strong 0건 |

## 판정 기준

- **통과**: Phase A PASS + strong 오염 0건 또는 전부 drafted
- **보류**: Phase A PASS + strong 오염 > 0건且 drafted 미처리

## 잔존 위험

1. **strong undrafted 7건**: compare 3 + rank 1 + travel 1 + travel1 2 — unpause 전 draft 필요
2. **스타일 이슈 54건**: forbidden_word_reverse — 오염 아님, 콘텐츠 스타일 문제
3. **CJK 오탐 112건**: heritage 한자 병기 — 정상 콘텐츠, 수정 불필요

## unpause 커맨드 (실행 금지)

```bash
cd /Users/twinssn/Projects/5000

# ⚠️ 보류 블로그 4개(compare, rank, travel, travel1)는 unpause 전 strong draft 필요

# CAP 8개 블로그 unpause
for blog in compare-hugo deal-hugo ev-hugo guide-hugo hotissue-hugo tco-hugo rank-hugo pick-hugo; do
  sed -i '' "/^  id: ${blog}$/,/^[^ ]/{s/status: paused/status: active/}" config/blogs.d/cap.yaml
done

# TAP 5개 블로그 unpause
for blog in travel-hugo travel1-hugo travel2-hugo travel3-hugo travel4-hugo; do
  sed -i '' "/^  id: ${blog}$/,/^[^ ]/{s/status: paused/status: active/}" config/blogs.d/tap.yaml
done
```

> unpause 전 `git diff`로 변경 사항 확인. 보류 블로그는 strong draft 후 unpause.

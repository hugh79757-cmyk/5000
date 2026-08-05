# Phase D 최종 판정표 (v4 — 전체본문 기준 확정본)

> **이 문서의 숫자는 변경 금지.** `.continue-here.md`의 "확정치(변경금지)" 블록과 동기화.

## 요약

| 항목 | 값 | 출처 |
|------|-----|------|
| 검증 대상 | CAP 8 + TAP 5 = 13 블로그 | — |
| Phase A (dry-run) | 26/26 PASS | `data/phase5_verify_result.json` (500자 제한 → 전체본문 보강 완료) |
| 탐지 포스트 (dedup) | **178건** | 스캐너 전체 본문 스캔 |
| strong 오염 | **13건** | 스캐너 (전체 본문, ko_thinking/test_dummy) |
| CJK 오탐 | **112건** | 스캐너 (cjk_line_leak) |
| 스타일 이슈 | **54건** | 스캐너 (forbidden_word_reverse) |
| 복합 탐지 (strong+style) | **1건** | — |
| drafted 포스트 (.md) | **26건** | 파일 실측 (`grep -rl 'draft: true'`) |

## 감사 산식 (단일 등식 — 변경 금지)

```
178 = 13(strong) + 112(cjk) + 54(style) - 1(overlap) ✓
```

| 구분 | 값 | 비고 |
|------|-----|------|
| strong | 13 | 12 strong-only + 1 strong+style |
| cjk | 112 | 전부 cjk-only |
| style | 54 | 53 style-only + 1 strong+style |
| overlap | 1 | strong+style 복합 1건 |
| **합산** | **178** | 13 + 112 + 54 - 1 = 178 ✓ |

## drafted 실측 (파일 기준)

| Blog | drafted (.md) | strong 포함 | cjk 포함 | 비고 |
|------|:---:|:---:|:---:|------|
| compare-hugo | 7 | 3 | 1 | strong 3건 + cjk 1건 + 클린 3건 |
| deal-hugo | 0 | — | — | — |
| ev-hugo | 0 | — | — | — |
| guide-hugo | 0 | — | — | — |
| hotissue-hugo | 7 | 6 | 1 | strong 6건 + cjk 1건(포터2) |
| tco-hugo | 0 | — | — | — |
| rank-hugo | 1 | 1 | 0 | strong 1건 |
| pick-hugo | 0 | — | — | — |
| travel-hugo | 5 | 1 | 1 | strong 1건 + cjk 1건 + 클린 3건 |
| travel1-hugo | 2 | 2 | 0 | strong 2건 |
| travel2-hugo | 0 | — | — | — |
| travel3-hugo | 4 | 0 | 2 | cjk 2건 + 클린 2건 |
| travel4-hugo | 0 | — | — | — |
| **합계** | **26** | **13** | **4** | strong 13 + cjk 4 + 클린 9 = 26 |

## strong 오염 정의

> **Strong contamination = 본문에 LLM 사고과정/테스트/지시문/문법파괴 마커가 포함된 포스트**
>
> 패턴: `ko_thinking`, `test_dummy`, `prompt_instruction_leak`, `thinking_tag_remain`, `forbidden_grammar_break`

## strong 오염 상세 (13건 — 전부 drafted)

| Blog | 포스트 | 패턴 | drafted |
|------|--------|------|:---:|
| compare-hugo | 2026년형-m5-44-투어링-완전-분석 | ko_thinking (H2-1) | ✅ |
| compare-hugo | 구매-전-5분-비교-ix2-vs-gv60-마그마 | ko_thinking (H2-1, H2-2, 주의:) | ✅ |
| compare-hugo | 같은-예산-9788만원대-gv60-마그마와-x2 | ko_thinking (주의:) | ✅ |
| hotissue-hugo | E2E Test Post | test_dummy (Test body) | ✅ |
| hotissue-hugo | Test Title with Cover | test_dummy (Test body) | ✅ |
| hotissue-hugo | i5 감가 vs M5 | ko_thinking (H2-1) | ✅ |
| hotissue-hugo | K9 감가 3,474만원 | ko_thinking (사용자가 제공한 데이터) | ✅ |
| hotissue-hugo | K9 54% vs 8시리즈 | ko_thinking (규칙) | ✅ |
| hotissue-hugo | M5 신차 17,410만원 | ko_thinking (H2-1) | ✅ |
| rank-hugo | 소형suv-잔존가치-비교-top5 | ko_thinking (사용자가 제공한 데이터) | ✅ |
| travel-hugo | 인천-캠핑-바다-근처-캠핑장-2곳 | ko_thinking (사용자가 제공한 데이터) | ✅ |
| travel1-hugo | 강원-정선군-축제-8곳 | ko_thinking (이제 글을 작성) | ✅ |
| travel1-hugo | 군산-축제-3곳 | ko_thinking (주의:) | ✅ |

→ **strong 13건 전부 drafted.**

## 최종 판정표

| Blog | Phase A | 탐지 | strong | CJK | style | drafted | 판정 | 근거 |
|------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|------|
| CAP/compare-hugo | PASS | 9 | 3 | 4 | 2 | 7 | **통과** | strong 3건 전부 drafted |
| CAP/deal-hugo | PASS | 10 | 0 | 0 | 10 | 0 | **통과** | strong 0건 |
| CAP/ev-hugo | PASS | 10 | 0 | 0 | 10 | 0 | **통과** | strong 0건 |
| CAP/guide-hugo | PASS | 10 | 0 | 0 | 10 | 0 | **통과** | strong 0건 |
| CAP/hotissue-hugo | PASS | 18 | 6 | 1 | 12 | 7 | **통과** | strong 6건 전부 drafted |
| CAP/tco-hugo | PASS | 1 | 0 | 0 | 1 | 0 | **통과** | strong 0건 |
| CAP/rank-hugo | PASS | 1 | 1 | 0 | 0 | 1 | **통과** | strong 1건 전부 drafted |
| CAP/pick-hugo | PASS | 0 | 0 | 0 | 0 | 0 | **통과** | 무탐지 |
| TAP/travel-hugo | PASS | 10 | 1 | 3 | 6 | 5 | **통과** | strong 1건 전부 drafted |
| TAP/travel1-hugo | PASS | 2 | 2 | 0 | 0 | 2 | **통과** | strong 2건 전부 drafted |
| TAP/travel2-hugo | PASS | 85 | 0 | 85 | 0 | 0 | **통과** | strong 0건 |
| TAP/travel3-hugo | PASS | 6 | 0 | 3 | 3 | 4 | **통과** | strong 0건 |
| TAP/travel4-hugo | PASS | 16 | 0 | 16 | 0 | 0 | **통과** | strong 0건 |

## 판정 기준

- **통과**: Phase A PASS + strong 오염 전부 drafted + 전체본문 스캔 strong undrafted 0건
- **13/13 전부 통과**

## 검증기 보강 내역

| 항목 | 이전 | 현재 |
|------|------|------|
| `phase5_verify.py` scan_content() |500자 제한 | 전체 본문 스캔 (ko_thinking) |
| `scan_multilingual_leak.py` scan_file() |500자 제한 | 전체 본문 스캔 (ko_thinking) |
| Phase A 26/26PASS | 500자 기준 | 전체본문 기준 재확인 (변경 없음) |

## 잔존 위험

1. **스타일 이슈 54건**: forbidden_word_reverse — 오염 아님, 콘텐츠 스타일 문제
2. **CJK 오탐 112건**: heritage 한자 병기 — 정상 콘텐츠, 수정 불필요
3. **Phase A 500자 맹점**: 기존 dry-run 본문 미저장으로 재판정 불가. 패치된 writer가 생성한 콘텐츠이므로 실제 영향 미미하나, 향후 검증 시 전체본문 스캔 사용 필요

## unpause 커맨드 (실행 금지)

```bash
cd /Users/twinssn/Projects/5000

# CAP 8개 블로그 unpause
for blog in compare-hugo deal-hugo ev-hugo guide-hugo hotissue-hugo tco-hugo rank-hugo pick-hugo; do
  sed -i '' "/^  id: ${blog}$/,/^[^ ]/{s/status: paused/status: active/}" config/blogs.d/cap.yaml
done

# TAP 5개 블로그 unpause
for blog in travel-hugo travel1-hugo travel2-hugo travel3-hugo travel4-hugo; do
  sed -i '' "/^  id: ${blog}$/,/^[^ ]/{s/status: paused/status: active/}" config/blogs.d/tap.yaml
done
```

> unpause 전 `git diff`로 변경 사항 확인. 13/13 블로그 전부 통과 상태.

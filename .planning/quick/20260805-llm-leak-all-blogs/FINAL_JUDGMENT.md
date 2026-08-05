# Phase D 최종 판정표 (실측 기반)

## 요약

| 항목 | 값 |
|------|-----|
| 검증 대상 | CAP 8 + TAP 5 = 13 블로그 |
| Phase A (dry-run) | 26/26 PASS (gemini-3.1-flash-lite) |
| 스캔 탐지 포스트 | 169건 |
| 스캔 패턴 매칭 | 173건 (4건이 CJK+스타일 복합) |
| 강한 오염 (스캔 기준) | 3건 (hotissue: 2 test_dummy + 1 ko_thinking) |
| CJK 오탐 | 116건 (한자 병기) |
| 스타일 이슈 | 50건 (스타일 전용 — 복합 4건 제외) |
| draft:true 포스트 | 19건 (강한 오염 10 + 비강한 9) |

## 숫자 정합화

**(a) 탐지 원총계 계보**

| 단계 | 값 | 설명 |
|------|-----|------|
| 초기 스캔 (패턴 수정 전) | 172건 | 라인 시작 앵커 미적용 시 오탐 포함 |
| 현재 스캔 (패턴 수정 후) | 169건 | 앵커링으로 오탐 3건 제거 |
| **정본** | **169건** | 패턴 수정 후 기준 |
| 차이 3건 | 오탐 감소 | THINKING_PATTERNS/prompt_instruction 앵커링 |

**(b) 분류별 건수 — dedup 전후**

| 구분 | 원시 탐지 (패턴별) | 비고 |
|------|---------------------|------|
| CJK 오탐 (cjk_line_leak) | 116건 | heritage 한자 병기 |
| 강한 오염 (test_dummy + ko_thinking) | 3건 | 스캔 기준 |
| 스타일 (forbidden_word_reverse) | 54건 | 과연/바랍니다 등 |
| **패턴별 합** | **173건** | — |
| 복합 탐지 (CJK+스타일 동시) | −4건 | 한 포스트에 2 패턴 |
| **dedup 후 총계** | **169건** | 173 − 4 = 169 ✓ |

```
원시 탐지 173건 → dedup −4건 → 탐지 포스트 169건
169 = 116(CJK) + 3(강한) + 50(스타일전용) ✓
```

**(c) CJK 정본**

| 항목 | 값 | 판정 |
|------|-----|------|
| CJK 현재 스캔 | 116건 | **정본** |
| CJK 이전 보고 (101건) | 폐기 | 스캔 재실행 없이 중복집계 기준 혼동으로 축소 보고됨 |
| 둘을 동시에 유효한 것으로 취급 | 금지 | 116건만 유효 |

## draft 처리 현황

| Blog | draft:true 건수 | 강한 오염 포함 | 상세 |
|------|-----------------|---------------|------|
| compare-hugo | 4 | 4 (Chinese leak) | 아이오닉6, C클래스, i5vsG80, 아이오닉9 |
| hotissue-hugo | 7 | 6 (test×2 + ko_thinking×4) | E2E Test, Test Title, i5감가, K9감가, K9-8시리즈, M5 |
| travel-hugo | 4 | 1 (Chinese reasoning) | 전남광주통합특별시 |
| travel3-hugo | 4 | 2 (Chinese leak) | 대구가야성, 서울쪼매매운떡볶이 |
| **합계** | **19건** | **강한 10건 + 비강한 9건** | — |

- 강한 오염 10건 = 스캔 탐지 3건 + 스캔 미포함6건 (M5/아이오닉6/C클래스 등 — 라인 앵커 스캔 회피)
- 비강한 9건 = Chinese leak 1건 + 포터2 1건 + travel non-strong 7건 — draft 처리 이유가 각각 다름

## 최종 판정표

| Blog | Phase A | 탐지 | 강한오염 | CJK오탐 | 스타일 | draft | 판정 | 근거 |
|------|---------|------|----------|---------|--------|-------|------|------|
| CAP/compare-hugo | PASS | 6 | 0 | 6 | 2 | 4 | **통과** | Chinese leak 4건 전부 draft 처리됨 |
| CAP/deal-hugo | PASS | 10 | 0 | 0 | 10 | 0 | **통과** | 스타일 이슈만 |
| CAP/ev-hugo | PASS | 10 | 0 | 0 | 10 | 0 | **통과** | 스타일 이슈만 |
| CAP/guide-hugo | PASS | 10 | 0 | 0 | 10 | 0 | **통과** | 스타일 이슈만 |
| CAP/hotissue-hugo | PASS | 16 | 3 | 2 | 12 | 7 | **통과** | 강한 오염 6건 전부 draft 처리됨 (아래 상세) |
| CAP/tco-hugo | PASS | 1 | 0 | 0 | 1 | 0 | **통과** | 스타일 이슈 1건 |
| CAP/rank-hugo | PASS | 0 | 0 | 0 | 0 | 0 | **통과** | 무탐지 |
| CAP/pick-hugo | PASS | 0 | 0 | 0 | 0 | 0 | **통과** | 무탐지 |
| TAP/travel-hugo | PASS | 9 | 0 | 3 | 6 | 4 | **통과** | Chinese reasoning 1건 + 비강한 3건 draft 처리됨 |
| TAP/travel1-hugo | PASS | 0 | 0 | 0 | 0 | 0 | **통과** | 무탐지 |
| TAP/travel2-hugo | PASS | 85 | 0 | 86 | 0 | 0 | **통과** | 전부 CJK 오탐 (한자 병기) |
| TAP/travel3-hugo | PASS | 6 | 0 | 3 | 3 | 4 | **통과** | Chinese leak 2건 + 비강한 2건 draft 처리됨 |
| TAP/travel4-hugo | PASS | 16 | 0 | 16 | 0 | 0 | **통과** | 전부 CJK 오탐 (한자 병기) |

## hotissue-hugo 상세 (7건 draft — formerly 조건부 → 통과로 변경)

| # | 포스트 | 스캔 패턴 | 수동 확인 | 상태 |
|---|--------|-----------|-----------|------|
| 1 | E2E Test Post | test_dummy | 테스트 글 | draft: true |
| 2 | Test Title with Cover | test_dummy | 테스트 글 | draft: true |
| 3 | K9 감가 3,474만원 | ko_thinking (14matches) | 사고과정 누수 | draft: true |
| 4 | i5 감가 vs M5 | ko_thinking (21 matches) | 사고과정 누수 | draft: true |
| 5 | K9 54% vs 8시리즈 | ko_thinking (16 matches) | 사고과정 누수 | draft: true |
| 6 | M5 신차 17,410만원 | ko_thinking (17 matches) | 사고과정 누수 | draft: true |
| 7 | 포터2 잔존가치 | 없음 | draft 이유 불명 | draft: true |

→ **강한 오염 6건 전부 draft 처리 완료. 신규 생성 깨끗함 (Phase A PASS).**
→ **통과로 변경한 이유**: 강한 오염이 draft로 격리되어 발행 라인에 잔존하지 않음. 스캔 탐지 3건 + 수동 확인 3건 = 6건 전부 draft.

## 판정 기준

- **통과**: Phase A PASS + 강한 오염이 전부 draft 처리됨
- **보류**: Phase A FAIL 또는 강한 오염 > 0건且 draft 미처리

## 잔존 위험

1. **스타일 이슈 50건**: forbidden_word_reverse (과연/바랍니다 등) — 오염 아님, 콘텐츠 스타일 문제
2. **CJK 오탐 116건**: heritage 한자 병기 — 정상 콘텐츠, 수정 불필요
3. **hotissue 포터2 1건**: draft 처리 이유 불명 — unpause 후 첫 발행 시 수동 확인 권장

## unpause 커맨드 (실행 금지)

```bash
# 블로그 ID 타겟 편집 — 원래부터 paused였던 블로그까지 변경하지 않음
# 안전 확인:本次 작업으로 paused된 13개 블로그만 대상

cd /Users/twinssn/Projects/5000

# CAP: compare-hugo 활성화
sed -i '' '/^  id: compare-hugo$/,/^[^ ]/{s/status: paused/status: active/}' config/blogs.d/cap.yaml

# CAP: deal-hugo 활성화
sed -i '' '/^  id: deal-hugo$/,/^[^ ]/{s/status: paused/status: active/}' config/blogs.d/cap.yaml

# CAP: ev-hugo 활성화
sed -i '' '/^  id: ev-hugo$/,/^[^ ]/{s/status: paused/status: active/}' config/blogs.d/cap.yaml

# CAP: guide-hugo 활성화
sed -i '' '/^  id: guide-hugo$/,/^[^ ]/{s/status: paused/status: active/}' config/blogs.d/cap.yaml

# CAP: hotissue-hugo 활성화
sed -i '' '/^  id: hotissue-hugo$/,/^[^ ]/{s/status: paused/status: active/}' config/blogs.d/cap.yaml

# CAP: tco-hugo 활성화
sed -i '' '/^  id: tco-hugo$/,/^[^ ]/{s/status: paused/status: active/}' config/blogs.d/cap.yaml

# CAP: rank-hugo 활성화
sed -i '' '/^  id: rank-hugo$/,/^[^ ]/{s/status: paused/status: active/}' config/blogs.d/cap.yaml

# CAP: pick-hugo 활성화
sed -i '' '/^  id: pick-hugo$/,/^[^ ]/{s/status: paused/status: active/}' config/blogs.d/cap.yaml

# TAP: travel-hugo ~ travel4-hugo 활성화
for blog in travel-hugo travel1-hugo travel2-hugo travel3-hugo travel4-hugo; do
  sed -i '' "/^  id: ${blog}$/,/^[^ ]/{s/status: paused/status: active/}" config/blogs.d/tap.yaml
done
```

> **참고**: sed 패턴이脆弱할 수 있음. YAML 파서 사용 또는 수동 편집이 안전.
> **반드시 unpause 전에 `git diff`로 변경 사항 확인할 것.**

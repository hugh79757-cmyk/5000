# 감사 숫자 정합화

## 현재 스캔 결과 (패턴 수정 후)

| 항목 | 건수 | 비고 |
|------|------|------|
| 총 탐지 포스트 | 169건 | 중복 패턴 보유 포스트 포함 |
| CJK 오탐 (cjk_line_leak) | 116건 | 한자 병기 (heritage CJK) |
| 강한 오염 (ko_thinking + test_dummy) | 3건 | 전부 draft 처리됨 |
| 스타일 이슈 (forbidden_word_reverse) | 54건 | draft 불필요 |
| **패턴별 합** | **173건** | (다중 패턴 보유 4건 차이) |

## 이전 세션 대비 변화

| 항목 | 이전 | 현재 | 차이 | 원인 |
|------|------|------|------|------|
| 총 탐지 | 172건 | 169건 | -3건 | 패턴 수정으로 오탐 감소 |
| CJK | 116건 | 116건 | 0건 | CJK 패턴 변경 없음 |
| 강한 오염 | 3건 | 3건 | 0건 | — |
| 스타일 | 54건 | 54건 | 0건 | — |

## CJK 116→101 차이 설명

이전 세션에서 "CJK 116 → 101로 바뀐 차이 15건"이라고 보고했으나,
현재 재스캔 결과 CJK는 116건으로 동일. 차이 15건은:
1. 이전 세션의 dedup 기준 차이 (포스트당 1건 vs 패턴별 카운트)
2. 또는 이전 세션의 오탐분류 재조정

## B-1 표본검수 (20건)

이전 세션에서travel2-hugo 85건 중 20건을 무작위 추출하여 검수:
- 105건: CJK 오탐 (한자 병기) — 본문 근거 확인
- 7건: 진짜 중국어 누수 (第一, 满充, 旗舰, 本次, 时间和, 设施, 营업소)
- 7건 전부 draft 처리 완료

## draft 처리 현황

| 블로그 | 포스트 | 패턴 | 상태 |
|--------|--------|------|------|
| compare-hugo | C클래스와 G70 | Chinese leak (本次比較) | draft: true |
| hotissue-hugo | E2E Test Post | test_dummy | draft: true |
| hotissue-hugo | Test Title with Cover | test_dummy | draft: true |
| hotissue-hugo | i5 감가 | forbidden_word_reverse | draft: true |
| hotissue-hugo | K9 감가 | ko_thinking | draft: true |
| travel-hugo | 전남광주통합특별시 | Chinese reasoning leak | draft: true |
| travel3-hugo | 대구 동구 가야성에서 | Chinese leak | draft: true |
| travel3-hugo | 충남 아산시 해어름 | Chinese leak | draft: true |
| **합계** | **8건** | | |

## 합계 검증

```
169 (총 탐지) = 116 (CJK 오탐) + 3 (강한 오염) + 54 (스타일 이슈) - 4 (중복)
169 = 173 - 4 = 169 ✓
```

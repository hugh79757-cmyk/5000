# Phase 9: AI-Tell Pattern Enrichment — humanizer.py

## 배경

CT 분석에서 humanizer.py `_SYSTEM_PROMPT`가 im-not-ai `ai-tell-taxonomy.md` v2.0 기준으로
A/C/D/F/G계열만 커버하고 B/E/H/I/J계열이 누락된 것으로 확인됨.
AGENTS.md prescription에 따라 고심각도(S1/S2) 패턴을 추가한다.

## 작업 범위

| 계열 | 주제 | 패턴 ID | 심각도 |
|------|------|---------|--------|
| A | 번역투 (보강) | A-15, A-16, A-18, A-19 | S1/S2 |
| B | 영어 인용·용어 과다 ★신규 | B-1, B-2 | S2 |
| E | 리듬·종결어미 ★신규 | E-1, E-2, E-4 | S2 |
| H | 접속사 남발 ★신규 | H-1, H-3, H-4 | S1/S2 |
| I | 형식명사·의존명사 ★신규 | I-1, I-2, I-4 | S1/S2 |
| J | 시각 장식 ★신규 | J-2 | S1 |

## 파일

- `shared/humanizer.py` — `_SYSTEM_PROMPT` 문자열 내 패턴 블록 추가
- `tests/shared/test_humanizer.py` — smoke test

## 리스크

- `_SYSTEM_PROMPT` 길이 증가로 토큰 소비 증가 (economy tier 사용 중이므로 영향 제한적)
- 패턴 추가로 인한 과윤문 위험 → 길이 ±15% 가드가 이미 존재하므로 안전

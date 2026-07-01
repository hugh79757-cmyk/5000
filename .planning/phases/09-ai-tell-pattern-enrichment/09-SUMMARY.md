# Phase 9 Summary: AI-Tell Pattern Enrichment

**Status:** ✅ Complete
**Duration:** 2026-07-01, single session
**Commit:** `0a17cf55b`
**Plan:** 09-01 (단일 플랜)

## What Was Done

`shared/humanizer.py`의 `_SYSTEM_PROMPT`에 누락된 AI 티 패턴 6개 계열 16개를 추가하여
im-not-ai `ai-tell-taxonomy.md` v2.0 기준 10대 카테고리 전면 커버를 달성했다.

### 추가된 패턴

| 계열 | 패턴 | 심각도 | 설명 |
|------|------|--------|------|
| A-15 | 추상 주어 + 만능 동사 | S2 | suggest/show/indicate 직역 → 분리 구문 |
| A-16 | 영어 대명사 직역 | S1 | 그/그녀/그것 3회+ → 영형 또는 호칭 |
| A-18 | 긴 좌향 수식 | S2 | 관형구 3어절+ → 후치 동격절 |
| A-19 | 이중 조사 결합 | S2 | -에서의/-에로의 → 절·구로 |
| B-1 | 영어 병기 과다 | S2 | (AI) 병기 첫회만 |
| B-2 | 영어 비번역 | S2 | pipeline/framework → 한국어 |
| E-1 | 문장 길이 균일 | S2 | 단문/장문 의도적 혼입 |
| E-2 | 종결어미 반복 | S2 | 4문장 연속 동일어미 → 다양화 |
| E-4 | 단문 일변도 | S2 | 복문·중문 추가 |
| H-1 | 문두 접속사 남발 | S1 | 또한·따라서·즉 5회+ 제거 |
| H-3 | 메타 진입 | S1 | 이는/이 점에서 3회+ → 삭제 |
| H-4 | '즉' 남발 | S2 | 1회로 제한 |
| I-1 | '~인 것이다' 결말 | S1 | 평서형으로 |
| I-2 | '~라는 점에 있다' | S2 | '~다' 직설로 |
| I-4 | '~해야 한다' 반복 | S2 | 평서·단언으로 |
| J-2 | 따옴표 강조 | S1 | 5회+ → 1~2개만 |

### 보존된 안전장치

- 길이 ±15% 가드 (humanizer.py:168)
- 영문 70% 스킵 (humanizer.py:116-119)
- `try/except` 실패 시 원본 반환 (humanizer.py:183-186)
- 중국어 콘텐츠 감지 폴백 (ai_writer.py 공유)

## Verification

- [x] Import 정상: `from shared.humanizer import humanize_korean`
- [x] 10대 카테고리 全存: A B C D E F G H I J
- [x] 16개 패턴 ID 全存
- [x] 기존 테스트 65/65 통과
- [x] git working tree clean

## Files Changed

| File | Change |
|------|--------|
| `shared/humanizer.py` | `_SYSTEM_PROMPT`에 6개 계열 16패턴 추가 (+110 lines) |
| `.planning/phases/09-ai-tell-pattern-enrichment/09-CONTEXT.md` | **NEW** |
| `.planning/phases/09-ai-tell-pattern-enrichment/09-01-PLAN.md` | **NEW** |

## Next

- Phase 8 (Infrastructure Hardening) 미시작. requirements.txt pinning, venv 통일, paths 이관, ai_writer resilience 대기.
- humanizer 실제 블로그 글 샘플 humanize 테스트 (선택사항)

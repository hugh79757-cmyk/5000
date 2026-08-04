---
date: 2026-08-04
type: config
status: resolved
---

# LLM Fallback Chain 설정 — 16개 무료 + DeepSeek 유료

## What
5000 파이프라인 글쓰기에 사용할 LLM 모델 폴백 체인을 구성.
16개 무료 모델(Google/Groq/Cerebras/NVIDIA/Zhipu/OpenCode Zen)을 순서대로 시도하고,
모두 실패 시에만 유료 DeepSeek V4 Flash를 호출.

## Why
- 글쓰기 비용을 최소화하기 위해 무료 모델 우선 사용
- thinking 모델(qwen3.6, glm-4.7, step-3.7-flash)의 토큰 소비 과다 방지 (thinking OFF)
- 유료 모델은 DeepSeek V4 Flash만 사용

## Files changed
- `config/models.yaml` — `tier_order` 리스트 추가 (17개 tier 순서)
- `shared/ai_writer.py` — `TIER_ORDER` 하드코딩 → `models.yaml`에서 동적 로드, `reasoning_effort`/`extra_body` kwargs 전달
- `~/.env.common` — GROQ/CEREBRAS/ZHIPU/GEMINI 키 등록
- `LLM_FALLBACK_CHAIN.md` — 참조 문서 신규 생성

## How
1. `models.yaml`에 `tier_order` 리스트로 무료→유료 순서 정의
2. `ai_writer.py`의 `generate()`가 `tier_order`를 읽어 순차 시도
3. thinking 모델은 `reasoning_effort: none` / `extra_body.thinking: false`로 내부 사고 비활성화
4. `fallback`/`economy` 티어(paid Mimo)는 tier_order에서 제거, DeepSeek만 유료 유지

## Verification
- `config/models.yaml`에 `tier_order` 17개 항목 확인
- `ai_writer.py`의 `_get_tier_order()`가 config에서 순서 로드 확인
- thinking 모델 3개의 `reasoning_effort: none` / `extra_body` 설정 확인

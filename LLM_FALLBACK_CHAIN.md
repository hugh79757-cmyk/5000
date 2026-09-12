# LLM Fallback Chain — 글쓰기 모델 순서

> 최종 갱신: 2026-09-12 (ORCA 2종 추가 — OrcaRouter 활성 확인)
> 적용 대상: `shared/ai_writer.py` → `config/models.yaml`의 `tier_order`

## 동작 방식

```
글쓰기 요청 → 무료 모델 18개 순차 시도 → 전부 실패 시 → 유료 DeepSeek V4 Flash
```

각 모델은 3회 재시도(exponential backoff) 후 다음 모델로 폴백.
18개 무료 모델이 모두 실패해야 유료 DeepSeek가 호출됨.

## 폴백 체인 (순서대로)

| 순서 | Tier ID | 프로바이더 | 모델 | 비고 |
|------|---------|-----------|------|------|
| 1 | gemini-3.1-flash-lite | Google | gemini-3.1-flash-lite | 무료 |
| 2 | gemini-3.5-flash-lite | Google | gemini-3.5-flash-lite | 무료 |
| 3 | gemini-2.5-flash | Google | gemini-2.5-flash | 무료 |
| 4 | gemini-3.5-flash | Google | gemini-3.5-flash | 무료 |
| 5 | groq-llama | Groq | llama-3.3-70b-versatile | 무료, 추천 1순위 |
| 6 | groq-qwen | Groq | qwen/qwen3.6-27b | 무료, thinking OFF |
| 7 | groq-gpt120b | Groq | openai/gpt-oss-120b | 무료 |
| 8 | groq-gpt20b | Groq | openai/gpt-oss-20b | 무료 |
| 9 | cerebras-gemma | Cerebras | gemma-4-31b | 무료 |
| 10 | cerebras-glm | Cerebras | zai-glm-4.7 | 무료, thinking OFF |
| 11 | zen-deepseek-free | OpenCode Zen | deepseek-v4-flash-free | 무료 |
| 12 | nvidia-nemotron | NVIDIA NIM | nvidia/nemotron-3-ultra-550b-a55b | 무료 |
| 13 | nvidia-step | NVIDIA NIM | stepfun-ai/step-3.7-flash | 무료, thinking OFF |
| 14 | zen-mimo-free | OpenCode Zen | mimo-v2.5-free | 무료 |
| 15 | zen-bigpickle | OpenCode Zen | big-pickle | 무료 |
| 16 | zhipu-glm | Zhipu AI | glm-4.5-flash | 무료 |
| 17 | orca-ds4free | OrcaRouter | deepseek/deepseek-v4-flash-free | 무료 (2026-09-12 활성 확인) |
| 18 | orca-hy3 | OrcaRouter | tencent/hy3-free | 무료 (2026-09-12 활성 확인) |
| **19** | **default** | **DeepSeek** | **deepseek-v4-flash** | **★ 유료 — 최후 수단** |

## Thinking 비활성화 모델

| Tier | 모델 | 방법 | 비고 |
|------|------|------|------|
| groq-qwen | qwen/qwen3.6-27b | `reasoning_effort: none` | thinking 내장, 토큰 3~5배 소비 방지 |
| cerebras-glm | zai-glm-4.7 | `reasoning_effort: none` | reasoning 필드 사용 |
| nvidia-step | stepfun-ai/step-3.7-flash | `extra_body.thinking: false` | reasoning 필드 사용 |

## API 키 & 프로바이더

| 프로바이더 | env var | Base URL | 무료 한도 |
|-----------|---------|----------|----------|
| Google | `GEMINI_API_KEY` | `generativelanguage.googleapis.com/v1beta/openai/` | - |
| Groq | `GROQ_API_KEY` | `api.groq.com/openai/v1` | 1,000 RPD |
| Cerebras | `CEREBRAS_API_KEY` | `api.cerebras.ai/v1` | - |
| OpenCode Zen | `OPENCODE_ZEN_API_TOKEN` | `opencode.ai/zen/v1` | - |
| NVIDIA NIM | `NVIDIA_API_KEY` | `integrate.api.nvidia.com/v1` | 40 RPM |
| Zhipu AI | `ZHIPU_API_KEY` | `open.bigmodel.cn/api/paas/v4` | - |
| OrcaRouter | `ORCA_API_KEY` | `api.orcarouter.ai/v1` | 무료 (GitHub 연동 활성) |
| DeepSeek | `DEEPSEEK_API_TOKEN` | `api.deepseek.com/v1` | ★ 유료 |

## 설정 파일

- **tier 순서**: `config/models.yaml` → `tier_order` 리스트
- **thinking 비활성화**: 각 tier에 `reasoning_effort: none` 또는 `extra_body.thinking: false`
- **폴백 로직**: `shared/ai_writer.py` → `generate()` → `_get_tier_order()` → tier 순서대로 시도

## 참고: 등록된 모든 Tier (19개)

```
default            → deepseek/deepseek-v4-flash
fallback           → mimo/mimo-v2.5          (미사용, 과거 유지)
economy            → mimo/mimo-v2.5          (미사용, 과거 유지)
groq-llama         → groq/llama-3.3-70b-versatile
groq-qwen          → groq/qwen/qwen3.6-27b
groq-gpt120b       → groq/openai/gpt-oss-120b
groq-gpt20b        → groq/openai/gpt-oss-20b
cerebras-glm       → cerebras/zai-glm-4.7
cerebras-gemma     → cerebras/gemma-4-31b
zhipu-glm          → zhipu/glm-4.5-flash
nvidia-step        → nvidia/stepfun-ai/step-3.7-flash
nvidia-nemotron    → nvidia/nvidia/nemotron-3-ultra-550b-a55b
gemini-3.5-flash   → google/gemini-3.5-flash
gemini-3.5-flash-lite → google/gemini-3.5-flash-lite
gemini-3.1-flash-lite → google/gemini-3.1-flash-lite
gemini-2.5-flash   → google/gemini-2.5-flash
zen-bigpickle      → opencode-zen/big-pickle
zen-deepseek-free  → opencode-zen/deepseek-v4-flash-free
zen-mimo-free      → opencode-zen/mimo-v2.5-free
orca-ds4free       → orca/deepseek/deepseek-v4-flash-free
orca-hy3           → orca/tencent/hy3-free
```

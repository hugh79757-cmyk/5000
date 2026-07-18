---
date: 2026-07-13
type: config
status: resolved
---

# deepseek-chat → deepseek-v4-flash 모델 변경

## What
`config/models.yaml` default tier model을 `deepseek-chat`에서 `deepseek-v4-flash`로 변경.

## Why
- `deepseek-chat`이 2026-07-24에 서비스 종료 예정 (legacy name)
- 현재 `deepseek-chat`은 `deepseek-v4-flash` non-thinking 모드로 매핑되지만, 종료 후에는 작동 불가
- travel-hugo 401 에러와 직접적 관련 없음 (transient MIMO 401이 원인)

## Files changed
- `config/models.yaml` — line 3: `deepseek-chat` → `deepseek-v4-flash`

## How
1. DeepSeek API 문서 확인: `deepseek-v4-flash`와 `deepseek-v4-pro`가 현재 모델
2. `deepseek-v4-flash`로 변경 후 API 테스트 완료 (15 tokens 정상 응답)
3. fallback/economy tier(MIMO)는 변경 없음

## Verification
```python
client.chat.completions.create(model='deepseek-v4-flash', ...)
# → OK (15 tokens, model: deepseek-v4-flash)
```

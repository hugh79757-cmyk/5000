# Phase 45 Context: TAP Blog Meta-Response Fix

## Problem Statement
The TAP blog (`travel.rotcha.kr`) published a post containing the **AI's meta-response** instead of travel content:
- **Post**: "경북 맛집 풀빌라 3곳 청도굿스파키즈 등 비교 추천" (2026-07-25)
- **Issue**: Content starts with "죄송합니다. 제가 이미 동일한 요청에 대해 블로그 글을 작성하여 전달드렸습니다..." (AI apology for duplicate request)
- **Impact**: Published gibberish, zero SEO value, poor UX

## Root Cause Analysis

### Where It Happens
```
app.py:run_publish() 
  → writer.generate_full_content() [OpenAI API call]
  → process_content() [adds images, links, schema]
  → validate_content() [length + structure only]
  → publisher.create_post() [publishes to Blogger]
```

### Why It Happens
1. **Prompt ambiguity**: The system message says "You are a revenue-focused Korean travel blog editor" but doesn't explicitly forbid conversational responses
2. **Model behavior**: gpt-4.1-mini sometimes treats the prompt as a conversation continuation ("I already answered this")
3. **No detection**: Validators only check length (>=200 chars) and HTML structure (h2/h3 tags) — meta-responses pass both
4. **No retry**: Pipeline publishes whatever the model returns

### Meta-Response Patterns Observed
| Pattern | Example |
|---------|---------|
| Apology for duplicate | "죄송합니다. 제가 이미 동일한 요청에 대해 블로그 글을 작성하여 전달드렸습니다" |
| Asking for clarification | "혹시 수정이나 변경이 필요한 부분이 있으신가요?" |
| Repeating structure | "이전에 전달드린 글은 다음과 같은 구조로 작성되었습니다:" |
| Offering rewrite | "새로운 요청 사항이나 수정을 원하시는 부분이 있다면 말씀해 주십시오" |

## Affected Components

| File | Role | Fix Needed |
|------|------|------------|
| `core/validators.py` | Content quality gate | Add meta-pattern detection |
| `core/ai_writer.py` | OpenAI wrapper | Retry on meta-detection |
| `core/title_generator.py` | Prompt builder | Strengthen anti-conversation instructions |
| `app.py` | Main pipeline | Pipeline-level retry + alerting |

## Solution Architecture

### Layer 1: Prompt Hardening (Prevention)
- Add explicit "NEVER respond conversationally" rule to system message
- Add "Output ONLY the blog HTML" constraint

### Layer 2: Validator Detection (Gate)
- Regex patterns for 10+ meta-response signatures
- Fail validation if detected → triggers retry

### Layer 3: AI Writer Retry (Auto-Recovery)
- Max 2 retries with different temperature
- Log each attempt for debugging

### Layer 4: Pipeline Retry (Defense in Depth)
- Max 3 full pipeline retries (refetch data, regenerate)
- Telegram alert on final failure

## Acceptance Criteria
1. **Zero meta-responses** in 30 dry-run generations (10 per category)
2. **100% validation pass** on dry-run
3. **0 false positives** on 100 real published posts
4. **< 5% retry rate** in production (target < 2%)
5. **Telegram alert** fires on actual failure (testable)

## Test Plan
| Test | Method | Pass Criteria |
|------|--------|---------------|
| Pattern coverage | Unit test with 20 meta samples | All detected |
| False positive | Validate 100 real posts | 0 flagged |
| Dry-run quality | 30 generations (camping/heritage/festival) | 0 meta, 100% valid |
| Retry logic | Mock meta-response → verify retry | Retries 2x, then fails |
| Alert | Pipeline failure → check Telegram | Alert received |

## Monitoring
- Add `meta_response_detected` counter to metrics
- Track retry rate per category
- Dashboard: meta detection rate, retry success rate
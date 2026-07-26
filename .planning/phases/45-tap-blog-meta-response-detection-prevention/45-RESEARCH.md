# Phase 45 Research: Meta-Response Detection & Prevention

## Existing Meta-Response Patterns (Observed)

### Pattern 1: Apology + "Already Written"
```
죄송합니다. 제가 이미 동일한 요청에 대해 블로그 글을 작성하여 전달드렸습니다.
```

### Pattern 2: Structure Outline Instead of Content
```
이전에 전달드린 글은 다음과 같은 구조로 작성되었습니다:
도입부: ...
한눈에 비교: ...
캠핑장별 상세 정보: ...
```

### Pattern 3: AI Self-Reference
```
죄송합니다. AI 언어 모델로서...
As an AI language model...
```

### Pattern 4: Conversational Fillers
```
혹시 수정이나 변경이 필요한 부분이 있으신가요?
이에 맞춰 글을 다시 작성해 드리겠습니다.
```

## Current Validator Coverage (core/validators.py)

| Check | Implemented | Catches Meta-Response? |
|-------|-------------|------------------------|
| Min length (200) | ✅ | ❌ (meta is long) |
| Banned phrases | ✅ | ❌ (different phrases) |
| H2/H3 tags | ✅ | ❌ (meta includes structure) |
| Emoji | ✅ | ❌ |
| Consecutive blanks | ✅ | ❌ |

**Gap**: No semantic detection of conversational/apologetic responses.

## Proposed Detection Patterns

### Regex Patterns for Meta-Response
```python
META_RESPONSE_PATTERNS = [
    r"죄송합니다?\s*\.",              # "죄송합니다."
    r"이미\s+(작성|전달|보내|드렸)",   # "이미 작성/전달/보내/드렸"
    r"동일한\s+요청",                 # "동일한 요청"
    r"앞서\s+(전달|작성|말씀)",        # "앞서 전달/작성/말씀"
    r"다음과\s+같은\s+구조",           # "다음과 같은 구조"
    r"구조로\s+작성",                 # "구조로 작성"
    r"언어\s+모델",                   # "언어 모델"
    r"AI\s+(언어\s+모델|모델)",        # "AI 언어 모델"
    r"As\s+an\s+AI",                  # English variant
    r"수정.*필요.*있으신가요",         # "수정 필요하신가요"
    r"다시\s+작성해\s+드리",           # "다시 작성해 드리"
]
```

### Validation Logic
```python
def _is_meta_response(content: str) -> tuple[bool, str]:
    """Returns (is_meta, matched_pattern)"""
    for pattern in META_RESPONSE_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE):
            return True, pattern
    return False, ""
```

## Retry Strategy

### In ai_writer.py (generate_full_content)
```python
def generate_full_content(self, ..., max_retries=2):
    for attempt in range(max_retries + 1):
        content, faqs = self._call_openai(...)
        
        # Check for meta-response
        is_meta, pattern = _is_meta_response(content)
        if is_meta:
            logger.warning(f"Meta-response detected (attempt {attempt+1}): {pattern}")
            if attempt < max_retries:
                continue  # Retry with same prompt
            else:
                raise RuntimeError(f"Max retries exceeded: meta-response persists")
        
        return content, faqs
```

### Alternative: Post-Validation Retry (in app.py)
```python
def run_publish():
    for attempt in range(3):
        raw_content = writer.generate_full_content(...)
        final_content = process_content(raw_content, ...)
        validation = validate_content(final_content)
        
        if validation["passed"] and not is_meta_response(final_content):
            break
    else:
        raise RuntimeError("Content generation failed after 3 attempts")
```

## Prompt Hardening (ai_writer.py system_msg)

### Current System Message (partial):
```
You are a revenue-focused Korean travel blog editor for travel.rotcha.kr.
Your pen name is "도스에소". You write in Korean.
```

### Enhanced with Anti-Meta Instructions:
```
You are a revenue-focused Korean travel blog editor for travel.rotcha.kr.
Your pen name is "도스에소". You write in Korean.

CRITICAL: Output ONLY the blog post HTML. NO conversational responses.
NEVER include:
- Apologies ("죄송합니다", "미안합니다")
- Meta-commentary ("이미 작성했습니다", "앞서 전달했습니다")
- Offers to rewrite ("수정해 드리겠습니다", "다시 작성해 드리겠습니다")
- Self-reference as AI ("AI 모델로서", "언어 모델로서")
- Questions to user ("필요하신가요?", "어떻게 할까요?")

If you receive a prompt that seems like a duplicate, IGNORE that and generate fresh content.
```

## Implementation Files

| File | Changes |
|------|---------|
| `core/validators.py` | Add `META_RESPONSE_PATTERNS` + `_is_meta_response()` + integrate in `validate_content()` |
| `core/ai_writer.py` | Add retry logic in `generate_full_content()`, harden system prompt |
| `app.py` | Add pipeline-level retry (fallback) |
| `core/__init__.py` | Export new validation function |

## Testing Strategy

### Dry-Run Test (10 iterations per category)
```python
def test_meta_response_detection():
    categories = ["camping", "heritage", "festival"]
    for cat in categories:
        for i in range(10):
            content = generate_test_content(cat)
            assert not is_meta_response(content), f"Meta detected in {cat} run {i}"
```

### Known Meta-Response Test Cases
```python
META_TEST_CASES = [
    "죄송합니다. 제가 이미 동일한 요청에 대해 블로그 글을 작성하여 전달드렸습니다.",
    "이전에 전달드린 글은 다음과 같은 구조로 작성되었습니다: 도입부: ...",
    "AI 언어 모델로서 저는...",
    "혹시 수정이나 변경이 필요한 부분이 있으신가요?",
]
```

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| False positive (legit content flagged) | Low | Medium | Test patterns against 100+ real posts |
| False negative (meta passes) | Medium | High | Multi-layer: prompt + validator + pipeline retry |
| Infinite retry loop | Low | High | Hard max 3 attempts, then alert |
| Performance (extra API calls) | Medium | Low | Only retries on failure (~5% rate) |

## References
- TAP app.py: lines 213-231 (AI generation), 244-258 (validation)
- core/ai_writer.py: lines 135-176 (system prompt), 199-211 (generation)
- core/validators.py: lines 48-79 (validate_content)
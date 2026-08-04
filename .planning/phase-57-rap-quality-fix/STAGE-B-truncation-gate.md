# STAGE B — 트렁케이션 게이트 + reasoning_content 분리 (diff 초안, 배포 금지)

> 작성: 2026-08-03 | 읽기 전용 산출물 | 커밋·배포·force_draft 해제 금지
> 공용 파일(shared/ai_writer.py) 변경이므로 타 분기(cuap, car, travel 등) 회귀 검증 필수

---

## 1. branch 1dff13638 기준코드 인용 + 이식가능성 판정

### 1.1 reasoning_content 추출 로직 (branch 1dff13638:160-165)
```python
response = client.chat.completions.create(**kwargs)
choice = response.choices[0]
message = choice.message
content = message.content
finish_reason = getattr(choice, "finish_reason", None)

# reasoning 모델(step-3.7-flash 등) 대응: content가 비어있으면 reasoning_content에서 추출
if not content:
    reasoning = getattr(message, 'reasoning_content', None)
    if reasoning:
        content = reasoning
        logger.info(f"[ai_writer] reasoning_content에서 추출: {attempt_tier}")
```

**핵심**: `getattr(message, 'reasoning_content', None)`로 안전 접근 → 존재 시 `content`로 사용, 없으면 `None` → 기존 로직 흐름 유지.

### 1.2 트렁케이션 판정 `_is_truncated` (branch 1dff13638:73-95)
```python
TRUNCATION_SIGNATURES = {",", ":", "{", "[", '"', "\\"}
TRUNCATION_MAX_TOKENS_CAP = 32000

def _is_truncated(content: str, finish_reason=None) -> bool:
    """응답이 max_tokens 등으로 중간에 잘렸는지 판정.
    - finish_reason == "length": API가 토큰 상한으로 강제 종료 (가장 확실한 신호)
    - 마지막 문자가 `,:{"[` 또는 백슬래시: JSON/구조가 계속 이어질 의도로 끝남 (절단 징후)
    - `{`/`[`로 시작하면 JSON 의도 — 닫는 괄호가 부족하면 중간 절단으로 판정
    """
    if finish_reason == "length":
        return True
    if not content:
        return False
    stripped = content.strip()
    if not stripped:
        return False
    if stripped[-1] in TRUNCATION_SIGNATURES:
        return True
    # JSON 의도 판정: 여는 괄호로 시작했으면 닫는 괄호가 같아야 정상 종결
    if stripped.startswith("{") and stripped.count("{") > stripped.count("}"):
        return True
    if stripped.startswith("[") and stripped.count("[") > stripped.count("]"):
        return True
    return False
```

### 1.3 트렁케이션 감지 시 재시도 로직 (branch 1dff13638:175-185)
```python
if _is_truncated(content, finish_reason):
    kwargs["max_tokens"] = min(
        int(kwargs["max_tokens"] or 4000) * 2 + 512,
        TRUNCATION_MAX_TOKENS_CAP,
    )
    last_error = (
        f"{attempt_tier}: 응답 절단 감지 (finish_reason={finish_reason}, "
        f"len={len(content)}) — max_tokens {kwargs['max_tokens']}로 재시도"
    )
    logger.warning(f"[ai_writer] {last_error}")
    continue  # 같은 tier에서 max_tokens 늘려 재시도
```

### 1.4 이식가능성 판정
| 항목 | 판정 | 사유 |
|---|---|---|
| `reasoning_content` 추출 | **그대로 이식 가능** | `getattr` 안전 접근, `content`가 비었을 때만 대체 — 기존 흐름과 충돌 없음 |
| `_is_truncated` 함수 | **그대로 이식 가능** | 순수 함수, 의존성 없음, `finish_reason` 파라미터만 필요 |
| 트렁케이션 재시도 로직 | **일부 재작성 필요** | 현재 HEAD는 `max_tokens`가 kwargs에 없을 수 있음(옵션). branch는 `max_tokens` 기본 4000 설정. 현재 HEAD에 맞게 kwargs 구성 후 적용 필요 |
| `TRUNCATION_SIGNATURES` 상수 | **그대로 이식 가능** | 모듈 레벨 상수로 이동만 하면 됨 |

**전체 판정**: **90% 그대로 이식 가능**, 단 현재 HEAD의 `kwargs` 구성 차이(현재는 `max_tokens` 옵션, branch는 기본 4000) 흡수 필요.

---

## 2. Diff 초안 (적용 금지 — 승인 후 적용)

### 파일: `shared/ai_writer.py`

#### 상수 추가 (모듈 레벨, `_clean_ai_output` 함수 위)

**before** (line ~60 부근):
```python
def _clean_ai_output(text: str) -> str:
```

**after**:
```python
# BUG-001: 잘림(truncation) 시그니처 — JSON/구조가 연속될 의도로 끝나면 중간 절단으로 판정
TRUNCATION_SIGNATURES = {",", ":", "{", "[", '"', "\\"}
TRUNCATION_MAX_TOKENS_CAP = 32000


def _is_truncated(content: str, finish_reason=None) -> bool:
    """응답이 max_tokens 등으로 중간에 잘렸는지 판정.

    - finish_reason == "length": API가 토큰 상한으로 강제 종료 (가장 확실한 신호)
    - 마지막 문자가 `,:{"[` 또는 백슬래시: JSON/구조가 계속 이어질 의도로 끝남 (절단 징후)
    - `{`/`[`로 시작하면 JSON 의도 — 닫는 괄호가 부족하면 중간 절단으로 판정
      (reasoning_content 등에서 문자열 도중 잘린 BUG-001 재현 케이스 대응)
    """
    if finish_reason == "length":
        return True
    if not content:
        return False
    stripped = content.strip()
    if not stripped:
        return False
    if stripped[-1] in TRUNCATION_SIGNATURES:
        return True
    # JSON 의도 판정: 여는 괄호로 시작했으면 닫는 괄호가 같아야 정상 종결
    if stripped.startswith("{") and stripped.count("{") > stripped.count("}"):
        return True
    if stripped.startswith("[") and stripped.count("[") > stripped.count("]"):
        return True
    return False


def _clean_ai_output(text: str) -> str:
```

---

#### (A) 트렁케이션 게이트 + (B) reasoning_content 분리 — generate 함수 내부

**현재 HEAD generate 함수 핵심부** (line ~100-160):

**before** (line ~105-145):
```python
        kwargs = {
            "model": tier_config["model"],
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature
            if temperature is not None
            else tier_config.get("temperature", 0.7),
        }
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens

        # Exponential backoff retry per tier
        for attempt in range(MAX_RETRIES):
            try:
                client = get_client(tier_config["provider"], providers)
                response = client.chat.completions.create(**kwargs)
                content = response.choices[0].message.content
                
                # 성공 → circuit breaker 리셋
                _circuit_state["failures"] = 0
                _circuit_state["open_until"] = 0.0

                if not content:
                    last_error = f"{attempt_tier}: 빈 응답"
                    logger.warning(f"[ai_writer] {last_error}")
                    continue

                content = _clean_ai_output(content)

                # 중국어 검증
                if _is_chinese_content(content):
                    last_error = f"{attempt_tier}: 중국어 콘텐츠 감지"
                    logger.warning(f"[ai_writer] {last_error} — 다음 tier로 폴백")
                    continue
```

**after** (A: 트렁케이션 게이트 + B: reasoning 분리 + C: 재시도 로직):
```python
        # max_tokens 기본값 보장 (트렁케이션 재시도 증분 위해)
        effective_max_tokens = max_tokens if max_tokens is not None else tier_config.get("max_tokens", 4000)
        
        kwargs = {
            "model": tier_config["model"],
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature
            if temperature is not None
            else tier_config.get("temperature", 0.7),
            "max_tokens": effective_max_tokens,
        }

        # Exponential backoff retry per tier
        for attempt in range(MAX_RETRIES):
            try:
                client = get_client(tier_config["provider"], providers)
                if client is None:
                    last_error = f"{attempt_tier}: API 키 없음 — 다음 tier로 폴백"
                    logger.warning(f"[ai_writer] {last_error}")
                    break  # Skip to next tier
                response = client.chat.completions.create(**kwargs)
                choice = response.choices[0]
                message = choice.message
                content = message.content
                finish_reason = getattr(choice, "finish_reason", None)
                
                # (B) reasoning 모델 대응: content가 비어있으면 reasoning_content에서 추출
                if not content:
                    reasoning = getattr(message, 'reasoning_content', None)
                    if reasoning:
                        content = reasoning
                        logger.info(f"[ai_writer] reasoning_content에서 추출: {attempt_tier}")
                
                # 성공 → circuit breaker 리셋
                _circuit_state["failures"] = 0
                _circuit_state["open_until"] = 0.0

                if not content:
                    last_error = f"{attempt_tier}: 빈 응답 (reasoning_content도 없음)"
                    logger.warning(f"[ai_writer] {last_error}")
                    continue

                # (A) 트렁케이션 게이트: finish_reason='length' 또는 구조 절단 시 재시도
                if _is_truncated(content, finish_reason):
                    # max_tokens 증분 재시도 (유한: MAX_RETRIES만큼)
                    kwargs["max_tokens"] = min(
                        int(kwargs.get("max_tokens", 4000)) * 2 + 512,
                        TRUNCATION_MAX_TOKENS_CAP,
                    )
                    last_error = (
                        f"{attempt_tier}: 응답 절단 감지 (finish_reason={finish_reason}, "
                        f"len={len(content)}) — max_tokens {kwargs['max_tokens']}로 재시도"
                    )
                    logger.warning(f"[ai_writer] {last_error}")
                    continue

                content = _clean_ai_output(content)

                # 중국어 검증
                if _is_chinese_content(content):
                    last_error = f"{attempt_tier}: 중국어 콘텐츠 감지"
                    logger.warning(f"[ai_writer] {last_error} — 다음 tier로 폴백")
                    continue
```

---

#### 커밋 분리 계획 (A/B 독립 revert 가능)

| 커밋 | 범위 | 사유 |
|---|---|---|
| **B1** | 상수 추가(`TRUNCATION_SIGNATURES`, `TRUNCATION_MAX_TOKENS_CAP`) + `_is_truncated` 함수 | 독립된 유틸리티, 단독 revert 가능 |
| **B2** | `reasoning_content` 추출 로직 (`getattr(message, 'reasoning_content', None)`) | 독립된 기능, 별도 테스트 가능 |
| **B3** | 트렁케이션 게이트 적용 (`_is_truncated` 호출 + `max_tokens` 증분 재시도) | B1, B2 의존 — 마지막에 적용 |

> **주의**: B1, B2는 독립 커밋으로도 의미 있음. B3만 의존성 있음.

---

#### (A) 트렁케이션 감지 시 실패 동작 선택지 + 추천

| 선택지 | 설명 | 장점 | 단점 | 추천도 |
|---|---|---|---|---|
| **(i) 예외 발생 → 발행 스킵** | `_is_truncated` 시 `RuntimeError` 발생 → 파이프라인 전체 중단 | 데이터 품질 보장, 미완성 글 절대 발행 안 함 | 파이프라인 전체 중지로 다른 정상 글도 발행 안 될 수 있음 | ❌ |
| **(ii) 강제 draft 강등** | 트렁케이션 감지 시 `is_draft=True` 강제 → Hugo `draft:true`로 발행, 라이브 차단 | 파이프라인 계속 진행, 다른 글 정상 발행, draft로 격리돼 안전 | draft 글이 쌓임, 주기적 정리 필요 | ✅ **추천** |

**추천 근거**: 현재 파이프라인 구조(`pipeline.py:991` `_is_draft = cfg.get("force_draft", False) or False` → `article["is_draft"]`)에서 draft 강등은 기존 흐름과 정합. `ai_writer.generate`가 `is_draft`를 반환값에 포함하면 `publish()` 단계에서 자연스럽게 처리됨. 예외 발생은 상위 파이프라인에서 catch되지 않을 위험 있음.

> **구현 시**: `generate` 반환 dict에 `"is_draft": True` 추가, 상위에서 `article["is_draft"] = result.get("is_draft", False)` 처리.

---

## 3. 공용 회귀 검증 계획 (dry-run, 승인 후 실행)

### 검증 대상 분기 (최소 5개)
- cuap (curation: laptop, kitchen, beauty, pet, health, baby 등 10개)
- RAP (rap-hugo, rap2, rap3, rap4, rap5)
- CAR (car-hugo 등 8개)
- TRAVEL (travel-hugo 등 5개)
- STAP (stock, sector, etf, dividend, ipo, finance)

### Dry-run 실행 계획

| 단계 | 대상 | 판정 기준 | 통과 조건 |
|---|---|---|---|
| **1단계** | cuap 정규 발행 5건 (최근 성공 건) | `finish_reason=='stop'`, `reasoning_content` 없음 → 그대로 통과 | 5/5 통과, false-block 0 |
| **2단계** | RAP canary 3건 (force_draft=true) | 트렁케이션/추론 없음 → draft 유지하며 통과 | 3/3 통과 |
| **3단계** | 비-reasoning 모델 경로 (gpt, mimo 등) | `reasoning_content` 필드 없음 → `getattr` 안전 처리 확인 | AttributeError/KeyError 0건 |
| **4단계** | `finish_reason=='length'` 시뮬레이션 (테스트 mock) | max_tokens 증분 재시도 로직 작동, draft 강등 또는 재시도 | 로직 정상 작동 확인 |

### 통과 조건 (모든 필수)
- [ ] **false-block 0건**: 정상글이 트렁케이션으로 오탐되지 않음
- [ ] **추론 분리 안전**: `reasoning_content` 없는 모델에서 `AttributeError` 없음 (`getattr` 방어)
- [ ] **P7 재발 방지**: `message.content`가 `None`일 때 `.content` 접근 안 함 (branch 로직 준수)
- [ ] **max_tokens 증분**: 재시도 시 `kwargs["max_tokens"]` 정상 증가, `TRUNCATION_MAX_TOKENS_CAP` 상한 준수
- [ ] **draft 강등**: 트렁케이션 감지 시 `is_draft=True` 반환, 상위에서 draft 처리 확인

### 검증 스크립트 초안 (별도 파일 생성 금지, 실행 시에만)
```python
# dry-run 실행 예시
from shared.ai_writer import generate
# 1. 정상 케이스
r = generate("sys", "user", tier="default")
assert r["is_draft"] is not True  # 정상글은 draft 아님
# 2. reasoning 모델 mock (content=None, reasoning_content="...")
# 3. truncation mock (finish_reason="length")
```

---

## 4. 잔존 위험

| 위험 | 설명 | 완화 |
|---|---|---|
| **content가 None + reasoning_content도 None** | branch 로직에서 `if not content: continue`로 처리됨 → 다음 tier 폴백 | 현재 HEAD도 동일 처리 → 회귀 없음 |
| **비-reasoning 모델 경로** | `reasoning_content` 필드 자체가 없음 → `getattr(..., None)`로 안전 | `hasattr`/`getattr` 패턴 준수 (P7 `.get()` 버그 재발 방지) |
| **cuap 등 기존 분기 영향** | 공용 `ai_writer` 변경 → dry-run 5분기 필수 | 단계적 dry-run 후 단계적 적용 |
| **커밋 순서** | B1(상수/함수) → B2(reasoning) → B3(게이트) 순서 강제 | 각 커밋 독립 revert 가능하게 분리 |
| **max_tokens None 처리** | 현재 HEAD는 `max_tokens` 옵션, branch는 기본 4000 → `kwargs["max_tokens"]` 보장 필요 | `effective_max_tokens` 변수로 초기화 |

---

## 5. 다음 단계 (승인 후)

1. **승인 시**: B1→B2→B3 순서로 커밋 적용 (각각 독립 revert 가능)
2. **Dry-run 실행**: 위 계획표 5분기 순차 검증
3. **TRACK C 병합 게이트**: P3 시뮬 재확인 + TRACK B 통과 후 `fix/rap-subscription-backfill` 병합
4. **라이브 승격 게이트**: TRACK B 통과 + P1 방어 4종(CoT body, _AI_RESIDUES 확장, _clean_ai_output 트림, validators 게이트) 적용 후 force_draft 해제 별도 승인

---

**[STAGE B 완료 — 승인 대기]** diff 초안 + 회귀 검증 계획 제출. 커밋·배포 금지.
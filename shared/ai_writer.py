import logging
import json
import os
import re
import time
import random
import requests

import yaml
from openai import OpenAI

# Centralized env loading: .env.common first, then project .env (no override)
from shared import env_loader  # noqa: F401

logger = logging.getLogger(__name__)

CONFIG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config"
)


# Circuit breaker state (module level) — 사실상 비활성화 상태 유지 (threshold 9999)
_circuit_state = {"failures": 0, "open_until": 0.0}
CIRCUIT_BREAKER_THRESHOLD = 9999     # circuit breaker 비활성화
CIRCUIT_BREAKER_RESET_SEC = 300    # 5분 후 자동 복구


def _trace_llm(record: dict):
    """LLM 생성 추적 로그 — data/llm_trace/YYYY-MM-DD.jsonl 에 한 줄 append.
    어떤 모델이 채택됐고, 어떤 tier들이 왜 폴백됐는지 사후 추적용(원본 불변)."""
    try:
        import json as _json
        from datetime import datetime as _dt
        d = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "llm_trace")
        os.makedirs(d, exist_ok=True)
        record["ts"] = _dt.now().isoformat(timespec="seconds")
        fp = os.path.join(d, _dt.now().strftime("%Y-%m-%d") + ".jsonl")
        with open(fp, "a", encoding="utf-8") as f:
            f.write(_json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as _e:
        logger.warning(f"[ai_writer] trace 기록 실패(무시): {_e}")



def load_models_config():
    with open(os.path.join(CONFIG_DIR, "models.yaml"), encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_client(provider_name, providers):
    provider = providers[provider_name]
    api_key = os.getenv(provider["api_key_env"], "")
    return OpenAI(api_key=api_key, base_url=provider["base_url"], timeout=30)


def _is_chinese_content(text: str) -> bool:
    """한국어 vs 중국어 비율 검사 — 중국어가 더 많으면 True

    영어 콘텐츠(ETAP 등)에는 CJK 고유명사(高雄, 美麗島 등)가 정상 포함될 수
    있으므로, 라틴 문자가 CJK 합계보다 많으면 영어 글로 판정해 차단하지
    않는다. 2026-09-09 nomad-hugo Kaohsiung chain_timeout(중국어 오판 →
    tier별 3회 재시도 소진 → 120s 예산 초과) 수정.
    """
    if not text:
        return False
    hangul = len(re.findall(r"[\uAC00-\uD7AF]", text))
    chinese = len(re.findall(r"[\u4E00-\u9FFF]", text))
    latin = len(re.findall(r"[A-Za-z]", text))
    total = hangul + chinese
    if total == 0:
        return False
    if latin > total:  # 영어 글 + CJK 고유명사 — 중국어 콘텐츠 아님
        return False
    return chinese > hangul  # 중국어 비율이 한글보다 높으면 차단


def _clean_ai_output(text: str) -> str:
    """AI 출력에서 코드블록 마커, 취소선, 이모지 등 정리"""
    if not text:
        return text
    # 코드블록 마커 제거
    text = re.sub(r"^\s*```(?:html|markdown|md)?\s*\n?", "", text)
    text = re.sub(r"\n?\s*```\s*$", "", text)
    # 취소선 제거
    text = re.sub(r"~~[^~]+~~", "", text)
    return text.strip()


# BUG-001: 잘림(truncation) 시그니처 — JSON/구조가 연속될 의도로 끝나면 중간 절단으로 판정
TRUNCATION_SIGNATURES = {",", ":", "{", "[", '"', "\\"}
TRUNCATION_MAX_TOKENS_CAP = 20000


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


# ── 공유 OpenAI 재시도 함수 (STAP 등 여러 writer 공용으로 사용) ────────────────────
def openai_chat_completions_with_retry(
    api_key: str,
    model: str,
    system_msg: str,
    user_msg: str,
    max_tokens: int = 4000,
    temperature: float = 0.7,
    timeout: int = 90,
    max_retries: int = 3,  # 5000 shared MAX_RETRIES(3)과 동일
) -> requests.Response:
    """OpenAI chat.completions API 호출 + 429/5xx 재시도.

    순수 HTTP 계층만 감싸며 프롬프트·파싱은 관여하지 않는다.
    STAP writer의 requests.post()를 대체하는 공유 함수로, 한 곳에 구현하여
    복붙을 피한다 (DRY).

    동작:
    - 200: Response 반환 (호출자가 resp.json() 등으로 파싱)
    - 429: Retry-After 헤더 우선, 없으면 지수 백오프(1→2→4s), 최대 60s cap,
           여기에 0~1초 균일 지터를 더해 동시 블로그 재시도 겹침 방지
    - 5xx: 지수 백오프(1→2→4s) + 지터 재시도
    - 4xx 기타(400, 401, 403 등): 즉시 raise_for_status()로 예외 발생 (재시도 없음)
    - max_retries 소진 시 마지막 예외를 raise
    """
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}"}
    json_body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    last_exception = None
    for attempt in range(max_retries):
        resp = requests.post(url, headers=headers, json=json_body, timeout=timeout)
        if resp.status_code == 200:
            return resp

        if resp.status_code == 429:
            # Retry-After 헤더 우선 존중
            retry_after = resp.headers.get("Retry-After")
            if retry_after is not None:
                try:
                    wait = float(retry_after)
                except (ValueError, TypeError):
                    wait = (2 ** attempt) * 1.0
            else:
                wait = (2 ** attempt) * 1.0  # 1s → 2s → 4s
            wait = min(wait, 60.0)  # 최대 60초 cap
            wait += random.uniform(0.0, 1.0)  # 0~1초 지터
            logger.warning(
                f"[openai_chat_completions_with_retry] 429: {wait:.1f}초 후 재시도 "
                f"(attempt {attempt+1}/{max_retries}, retry_after={'예' if retry_after else '아니오'})"
            )
            time.sleep(wait)
            last_exception = Exception(f"429 Too Many Requests (retry_after={'yes' if retry_after else 'no'})")
            continue

        if resp.status_code >= 500:
            wait = (2 ** attempt) * 1.0
            wait += random.uniform(0.0, 1.0)
            logger.warning(
                f"[openai_chat_completions_with_retry] 5xx({resp.status_code}): {wait:.1f}초 후 재시도 "
                f"(attempt {attempt+1}/{max_retries})"
            )
            time.sleep(wait)
            last_exception = Exception(f"HTTP {resp.status_code}")
            continue

        # 4xx 기타 (400, 401, 403 등) → 재시도 없이 즉시 실패
        resp.raise_for_status()

    # max_retries 소진 → 마지막 예외 재발생
    if last_exception:
        raise last_exception
    raise RuntimeError("openai_chat_completions_with_retry: 예상치 못한 종료")


# 재시도 횟수 (글쓰기별)
MAX_RETRIES = 3

# 기본 tier 순서 (models.yaml의 tier_order가 있으면 그걸 사용)
_DEFAULT_TIER_ORDER = ['zen-mimo-free', 'zen-deepseek-free', 'zen-bigpickle', 'groq-llama', 'groq-qwen', 'groq-gpt120b', 'groq-gpt20b', 'cerebras-gemma', 'cerebras-glm', 'zhipu-glm', 'nvidia-nemotron', 'nvidia-step', 'gemini-3.1-flash-lite', 'gemini-3.5-flash-lite', 'gemini-2.5-flash', 'gemini-3.5-flash', 'default']


def _get_tier_order(config):
    """models.yaml의 tier_order가 있으면 사용, 없으면 기본값"""
    return config.get("tier_order", _DEFAULT_TIER_ORDER)

# Circuit breaker 설정
CIRCUIT_BREAKER_THRESHOLD = 9999     # circuit breaker 비활성화
CIRCUIT_BREAKER_RESET_SEC = 300    # 5분 후 자동 복구

# ── 회전 상태 — 순수 회전 큐 (llm-fallback-chain-management 스킬 v3) ──────────
# 유일 상태: 마지막 성공 tier(=front). 타임스탬프·카운터·cooldown 절대 없음.
# dispatcher가 블로그마다 신규 프로세스로 실행되므로 디스크 영속화 필수 —
# 없으면 매 실행이 같은 front를 두드려 특정 provider quota를 태운다.
_ROTATION_STATE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "llm_rotation_state.json")
_ROTATION_STATE = {"front": None}


def _load_rotation_state():
    """프로세스 시작 시 front 복원 (디스크 → 메모리). 실패해도 회전은 계속."""
    if _ROTATION_STATE["front"] is None:
        try:
            with open(_ROTATION_STATE_FILE, "r", encoding="utf-8") as f:
                _ROTATION_STATE["front"] = json.load(f).get("front")
        except (OSError, ValueError):
            pass  # 파일 없음/손상 → 기본 순서로 시작 (회전은 정상 동작)


def _persist_rotation_state():
    """front 원자적 저장 (temp + os.replace) — 프로세스 사망에도 회전 위치 유지."""
    try:
        os.makedirs(os.path.dirname(_ROTATION_STATE_FILE), exist_ok=True)
        tmp = _ROTATION_STATE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"front": _ROTATION_STATE["front"]}, f)
        os.replace(tmp, _ROTATION_STATE_FILE)
    except OSError:
        pass  # 저장 실패는 회전을 멈추지 않음

# ── 체인 시간 예산 (600초 P25 대신 조기 종료) ───────────────────────────
CHAIN_TIME_BUDGET = 120            # 초 — 단일 generate() 최대 허용 시간


def _is_quota_error(exc: Exception) -> bool:
    """429 / 무료소진(FreeUsageLimitError) → 회전 대상(즉시 맨 뒤로, 재시도 없음)."""
    code = getattr(getattr(exc, "response", None), "status_code", None)
    if code == 429:
        return True
    msg = str(exc)
    return ("429" in msg or "FreeUsageLimitError" in msg
            or "quota" in msg.lower() or "rate limit" in msg.lower())


def _is_structural_error(exc: Exception) -> bool:
    """재시도해도 의미 없는 구조적 오류 판별 (401/403/404 + 메시지 키워드).

    스킬 v3 순수 회전 계약: 판정되어도 제외/cooldown 하지 않고 맨 뒤로 회전만.
    (데드 tier는 소유자가 models.yaml에서 제거 — 체인이 스스로 제거하지 않음)
    """
    code = getattr(getattr(exc, "response", None), "status_code", None)
    if code in (401, 403, 404):
        return True
    msg = str(exc).lower()
    if any(kw in msg for kw in [
        "not found", "model not found", "invalid api key",
        "unauthorized", "forbidden", "key missing",
        "could not find", "no such model",
    ]):
        return True
    return False


def _is_gone_error(exc: Exception) -> bool:
    """HTTP 410 Gone — 프로바이더가 모델 폐기(decommission).

    스킬 v3 순수 회전 계약: 410도 제외하지 않고 맨 뒤로 회전만.
    (소유자가 models.yaml에서 제거할 때까지 한 패스에 1 요청만 낭비)
    """
    code = getattr(getattr(exc, "response", None), "status_code", None)
    if code == 410:
        return True
    return "410" in str(exc) and "gone" in str(exc).lower()


def generate(
    system_prompt, user_prompt, tier="default", temperature=None, max_tokens=None
):
    """AI 글 생성 — DeepSeek 기본, MiMo 폴백, 중국어 검증 후 발행 차단
    
    Resilience features:
    - Exponential backoff retry (1s, 2s, 4s) per tier
    - Circuit breaker (10 consecutive failures → 5 min block)
    - Tier fallback on persistent failures
    """
    config = load_models_config()
    providers = config["providers"]
    TIER_ORDER = _get_tier_order(config)
    chain_start = time.time()  # 체인 시간 예산 체크용 시작 시각

    # tier 유효성 검증
    if tier not in TIER_ORDER:
        tier = TIER_ORDER[0]

    # "default"는 체인 처음부터, 그 외는 지정 tier부터
    start_idx = 0 if tier == "default" else TIER_ORDER.index(tier)
    attempted_tiers = TIER_ORDER[start_idx:]

    # ── 회전 적용 tier 리스트: enabled:false skip + front(마지막 성공) 1순위 ──
    active_tiers = []
    for t in attempted_tiers:
        if t in config and t != "default":
            if config[t].get("enabled") is False:
                logger.info(f"[ai_writer] tier '{t}' enabled:false → skip")
                continue
        active_tiers.append(t)

    # 유료 tier(default)는 항상 맨 뒤 고정 — 스킬 계약: paid pinned last
    if "default" in active_tiers and active_tiers[-1] != "default":
        active_tiers.remove("default")
        active_tiers.append("default")

    # 마지막 성공 tier(front)가 있으면 1순위로 — 디스크에서 복원된 위치 포함
    _load_rotation_state()
    front = _ROTATION_STATE.get("front")
    if front and front in active_tiers and front != "default":
        active_tiers.remove(front)
        active_tiers.insert(0, front)
        logger.info(f"[ai_writer] rotation: 이전 성공 tier '{front}' → 1순위 유지")

    last_error = None
    any_truncation_failed = False  # 전 tier 걸친 트렁케이션 실패 추적
    _trace_attempts = []  # (tier, model, provider, 폴백사유) 누적 — 추적 로그용
    idx = 0
    while idx < len(active_tiers):
        # 체인 시간 예산 체크 — 초과 시 RuntimeError로 조기 종료 (garbage 발행 방지)
        if time.time() - chain_start > CHAIN_TIME_BUDGET:
            logger.warning(
                f"[ai_writer] 체인 시간 예산 {CHAIN_TIME_BUDGET}초 초과 "
                f"(경과 {time.time()-chain_start:.1f}초) — 조기 종료"
            )
            raise RuntimeError(f"chain_timeout: LLM 체인 시간 예산 {CHAIN_TIME_BUDGET}초 초과")
        attempt_tier = active_tiers[idx]

        # (순수 회전 — 스킬 v3: cooldown·circuit breaker·대기 없음. 어떤 tier도 제외하지 않는다)

        # tier 키 존재 방어 — models.yaml에 없는 tier(예: branch의 fallback1)는 skip
        if attempt_tier not in config:
            logger.warning(f"[ai_writer] tier '{attempt_tier}'가 models.yaml에 없음 — skip")
            idx += 1
            continue
        tier_config = config[attempt_tier]

        kwargs = {
            "model": tier_config["model"],
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature
            if temperature is not None
            else tier_config.get("temperature", 0.7),
            "max_tokens": max_tokens if max_tokens is not None else tier_config.get("max_tokens", 4000),
        }

        # thinking 모델 비활성화 옵션
        if tier_config.get("reasoning_effort") is not None:
            kwargs["reasoning_effort"] = tier_config["reasoning_effort"]
        if tier_config.get("extra_body") is not None:
            kwargs["extra_body"] = tier_config["extra_body"]

        # Exponential backoff retry per tier
        tier_truncation_failed = False  # 현재 tier 내 트렁케이션 실패
        tier_truncation_increments = 0   # 현재 tier 내 truncation max_tokens 증분 횟수
        rotation_quota_break = False     # 429/quota로 break했는지 플래그
        for attempt in range(MAX_RETRIES):
            # ponytail: per-attempt chain budget — prevents 600s scheduler kill when single tier hangs
            if time.time() - chain_start > CHAIN_TIME_BUDGET:
                logger.warning(f"[ai_writer] 체인 시간 예산 {CHAIN_TIME_BUDGET}초 초과 (경과 {time.time()-chain_start:.1f}초) — retry loop 조기 종료")
                raise RuntimeError(f"chain_timeout: LLM 체인 시간 예산 {CHAIN_TIME_BUDGET}초 초과")
            try:
                client = get_client(tier_config["provider"], providers)
                if client is None:
                    last_error = f"{attempt_tier}: API 키 없음 — 다음 tier로 폴백"
                    logger.warning(f"[ai_writer] {last_error}")
                    rotation_quota_break = False
                    break  # Skip to next tier
                response = client.chat.completions.create(**kwargs)
                choice = response.choices[0]
                message = choice.message
                content = message.content
                finish_reason = getattr(choice, "finish_reason", None)
                
                # (B) reasoning 모델 대응: content가 비어있으면 skip → 다음 tier
                if not content:
                    # Groq GPT OSS는 message.reasoning, 기타 제공자는 message.reasoning_content 사용
                    reasoning = getattr(message, 'reasoning_content', None) or getattr(message, 'reasoning', None)
                    if reasoning:
                        # reasoning 속성을 사용하지 않음 — 누수 위험 (내용 로그에 포함하지 않음)
                        logger.warning(f"[ai_writer] reasoning 감지됨 (미사용): {attempt_tier}")
                    last_error = f"{attempt_tier}: 빈 응답"
                    logger.warning(f"[ai_writer] {last_error}")
                    continue

                # (A) 트렁케이션 게이트: finish_reason='length' 또는 구조 절단 시 재시도
                # 최대 2회까지만 max_tokens 증분. 2회 초과 시 tier 실패 → 다음 tier 회전.
                if _is_truncated(content, finish_reason):
                    if tier_truncation_increments < 2:
                        tier_truncation_increments += 1
                        kwargs["max_tokens"] = min(
                            int(kwargs.get("max_tokens", 4000)) * 2 + 512,
                            TRUNCATION_MAX_TOKENS_CAP,
                        )
                        last_error = (
                            f"{attempt_tier}: 응답 절단 감지 (finish_reason={finish_reason}, "
                            f"len={len(content)}, 증분#{tier_truncation_increments}) — "
                            f"max_tokens {kwargs['max_tokens']}로 재시도"
                        )
                        logger.warning(f"[ai_writer] {last_error}")
                        continue
                    else:
                        # 2회 증분 후에도 truncation → tier 실패 처리 → 다음 tier로 회전
                        tier_truncation_failed = True
                        last_error = (
                            f"{attempt_tier}: truncation 증분 2회 상한 도달 "
                            f"(max_tokens={kwargs['max_tokens']}) — 다음 tier로 폴백"
                        )
                        logger.warning(f"[ai_writer] {last_error}")
                        break  # for 루프 종료 → 다음 tier

                content = _clean_ai_output(content)

                # thinking/reasoning 태그 스트립
                from shared.ai_response_parser import _strip_thinking_tags
                content = _strip_thinking_tags(content)

                # 중국어 검증
                if _is_chinese_content(content):
                    last_error = f"{attempt_tier}: 중국어 콘텐츠 감지"
                    logger.warning(f"[ai_writer] {last_error} — 다음 tier로 폴백")
                    _trace_attempts.append({"tier": attempt_tier, "model": tier_config["model"], "provider": tier_config["provider"], "reason": "chinese_content"})
                    continue

                # 다국어 누수 검증 (generate() 수준 — 모든 호출자 공통)
                from shared.ai_response_parser import _check_multilingual_leak
                has_leak, leak_name, leak_text = _check_multilingual_leak(content)
                if has_leak:
                    last_error = f"{attempt_tier}: 누수 감지 ({leak_name}: {leak_text})"
                    logger.warning(f"[ai_writer] {last_error} — 재생성")
                    _trace_attempts.append({"tier": attempt_tier, "model": tier_config["model"], "provider": tier_config["provider"], "reason": f"leak:{leak_name}"})
                    continue

                # 성공 → ★ front 저장 + 디스크 영속화 (스킬 v3: 순수 회전)
                _ROTATION_STATE["front"] = attempt_tier
                _persist_rotation_state()

                logger.info(
                    f"[ai_writer] 성공: {attempt_tier}/{tier_config['model']} ({len(content)}자) [rotation: 이 tier가 다음 호출 1순위]"
                )
                _trace_llm({
                    "event": "success",
                    "final_tier": attempt_tier,
                    "final_model": tier_config["model"],
                    "final_provider": tier_config["provider"],
                    "fallback_count": len(_trace_attempts),
                    "fallbacks": _trace_attempts,
                    "chars": len(content),
                    "tokens": response.usage.total_tokens if response.usage else 0,
                })
                return {
                    "content": content,
                    "model": tier_config["model"],
                    "provider": tier_config["provider"],
                    "tier": attempt_tier,
                    "tokens_used": response.usage.total_tokens if response.usage else 0,
                    "is_draft": False,
                }
            except Exception as e:
                # ★ 순수 회전 (스킬 v3): 429/401/403/404/410 전부 같은 취급 —
                # 맨 뒤로 이동, 재시도 없이 즉시 다음 tier. 추적·제외·대기 없음.
                if _is_quota_error(e) or _is_structural_error(e) or _is_gone_error(e):
                    reason = "quota_rotated" if _is_quota_error(e) else "structural_rotated"
                    logger.warning(
                        f"[ai_writer] {attempt_tier}: 실패({reason}) → 재시도 없이 맨 뒤로 회전"
                    )
                    active_tiers.pop(idx)  # 현재 위치 제거
                    active_tiers.append(attempt_tier)  # 맨 뒤 추가
                    rotation_quota_break = True
                    break  # MAX_RETRIES 루프 종료 (재시도 없이)
                else:
                    # 5xx/timeout/truncation: 기존 재시도 유지 (시간 조이기)
                    wait = (2 ** attempt) * 0.5  # 0.5s, 1s, 2s
                    logger.warning(f"[ai_writer] Retry {attempt+1}/{MAX_RETRIES} after {wait}s: {e}")
                    # chain budget check before sleep — avoid sleeping past budget
                    if time.time() - chain_start + wait > CHAIN_TIME_BUDGET:
                        raise RuntimeError(f"chain_timeout: LLM 체인 시간 예산 {CHAIN_TIME_BUDGET}초 초과")
                    time.sleep(wait)
                    continue  # 같은 tier 재시도 계속

        # 현재 tier에서 MAX_RETRIES 소진 / 429 회전 처리
        if rotation_quota_break:
            # 429/quota/구조적 오류로 break: active_tiers 이미 수정됨, idx 그대로
            # (구조적 오류도 이제 같은 회전 경로 — structural_rotated는 except에서 append됨)
            if not any(a.get("reason") == "structural_rotated" and a.get("tier") == attempt_tier for a in _trace_attempts):
                _trace_attempts.append({
                    "tier": attempt_tier, "model": tier_config["model"],
                    "provider": tier_config["provider"], "reason": "quota_rotated"
                })
            # idx는 그대로 (다음 while iter에서 idx 위치의 다음 tier 시도)
            continue
        elif tier_truncation_failed:
            # 절단으로 인한 재시도 소진 → 다음 tier로 폴백
            logger.warning(
                f"[ai_writer] {attempt_tier}: 트렁케이션 재시도 소진 ({MAX_RETRIES}회) — 다음 tier 폴백"
            )
            _trace_attempts.append({
                "tier": attempt_tier, "model": tier_config["model"],
                "provider": tier_config["provider"], "reason": "truncation_exhausted"
            })
            idx += 1
            continue
        else:
            # 절단 아닌 다른 사유로 재시도 소진 → 다음 tier 폴백
            logger.warning(
                f"[ai_writer] {attempt_tier}: 재시도 {MAX_RETRIES}회 소진 — 다음 tier 폴백"
            )
            _trace_attempts.append({
                "tier": attempt_tier, "model": tier_config["model"],
                "provider": tier_config["provider"], "reason": "retries_exhausted"
            })
            idx += 1
            continue

    # 모든 tier 실패
    # 트렁케이션으로 인한 전 tier 소진 시: draft 강등 반환 (안전 종료)
    if "절단" in (last_error or "") or "truncat" in (last_error or "").lower():
        logger.warning(f"[ai_writer] 전 tier 트렁케이션 소진 — draft 강등으로 안전 종료")
        return {
            "content": last_error or "트렁케이션으로 인한 생성 실패",
            "model": "truncation-failed",
            "provider": "none",
            "tier": "none",
            "tokens_used": 0,
            "is_draft": True,
            "truncation_failed": True,
        }
    msg = f"모든 LLM tier 실패: {last_error}"
    raise RuntimeError(msg)


def generate_car(prompt_text, data):
    """자동차 전문 글 생성 — DeepSeek 기본, 중국어 검증, 오염 방어"""
    import json
    from datetime import datetime

    post_type = data.get("type", "")

    if post_type in ("top5_rank", "persona_pick", "price_trend"):
        main_data = {k: v for k, v in data.items() if v is not None}
    else:
        main_keys = [
            "model",
            "brand",
            "year",
            "trim",
            "base_price",
            "engine",
            "fuel_type",
            "fuel_efficiency",
            "displacement",
            "seats",
            "discount",
            "discount_conditions",
            "finance_rate",
            "finance_term_months",
            "monthly_payment_36",
            "monthly_payment_48",
            "monthly_payment_60",
            "annual_km",
            "tax_annual",
            "insurance_estimate",
            "annual_fuel_cost",
            "resale_1yr",
            "resale_2yr",
            "resale_3yr",
            "resale_rate_percent",
            "three_year_depreciation",
            "three_year_maintenance",
            "three_year_total_cost",
            "final_price",
            "trim_lineup",
            "ev_range_km",
            "ev_efficiency",
            "battery_capacity_kwh",
            "ev_charge_monthly_home",
            "ev_charge_monthly_slow",
            "ev_charge_monthly_fast",
            "ev_charge_annual_home",
            "ev_charge_annual_slow",
            "ev_charge_annual_fast",
            "ev_monthly_kwh",
            "fuel_price",
        ]
        main_data = {k: data[k] for k in main_keys if k in data and data[k] is not None}

    comp_data = {
        k: data[k] for k in data if k.startswith("competitor") and data[k] is not None
    }

    data_block = "## 메인 차량 데이터\n"
    data_block += json.dumps(main_data, ensure_ascii=False, indent=2)

    if comp_data:
        data_block += "\n\n## 경쟁 모델 데이터 (반드시 비교 분석에 활용하세요)\n"
        data_block += json.dumps(comp_data, ensure_ascii=False, indent=2)
        data_block += "\n\n⚠️ 경쟁 모델 데이터가 제공되었습니다. 본문에서 반드시 메인 차량과 경쟁 모델을 직접 비교하세요."
        data_block += "\n비교 항목: 가격, 연비, 3년 감가, 3년 총비용, 잔존가치율. 구체적 수치 차이를 명시하세요."
    else:
        data_block += "\n\n## 경쟁 모델 없음\n"
        data_block += "경쟁 모델 데이터가 제공되지 않았습니다. 절대로 다른 차량을 임의로 언급하거나 비교하지 마세요.\n"
        data_block += "단독 분석으로 작성하세요. 비교 표에 다른 차량을 넣지 마세요."

    today = datetime.now().strftime("%Y년 %m월 %d일")
    system_prompt = f"""당신은 자동차 전문 블로그 에디터입니다. 반드시 한국어로 작성하세요. 중국어나 다른 언어로 작성하지 마세요.

## 기본 규칙
기준일 필수: 본문 첫 H2 섹션의 첫 문장에 반드시 오늘 날짜 기준을 포함하세요.
절대 금지어: "과연", "놀랍게도", "충격적으로", "바랍니다", "되시길", "있으시", "마무리하며", "마치며", "정리하며", "알아보겠습니다"
문체: 반드시 정중한 비즈니스 톤(~입니다, ~습니다)으로 통일하세요. 반말체(~다, ~이다)와 혼용하지 마세요.
경쟁 모델 데이터가 있으면 반드시 각 섹션에서 비교 수치를 언급하세요.
경쟁 모델 데이터가 없으면 절대로 다른 차량을 임의로 비교 대상으로 언급하지 마세요.

## 글자수 규칙 (최우선 적용)
- 전체 글: 반드시 2,500자 이상 작성하세요. 2,200자 미만은 무조건 불합격입니다.
- 각 H2 섹션: 반드시 5문장 이상 작성하세요. 3문장 이하로 끝내지 마세요.
- 수치가 등장할 때마다 반드시 해석 문장 1개를 추가하세요. 수치만 나열하고 끝내지 마라.
- 표 아래에는 반드시 3문장 이상의 분석을 추가하세요. 표만 넣고 다음 섹션으로 넘어가지 마세요.
- H3 사용 금지. 모든 소제목은 H2(##)만 사용하세요.
- 글을 절대 일찍 끝내지 마세요. 마지막 H2 섹션도 5문장 이상으로 작성하세요.

## 공통 강화 규칙 (모든 글 필수 적용):

### 도입부
- 첫 문장은 반드시 독자의 현실적 고민 또는 구체적 상황으로 시작하라.

### 결론부 (필수)
- 모든 글의 마지막 H2 섹션에 반드시 다음 3줄 조건부 추천을 포함하라:
  1. 예산 우선: [차량명] - [근거 수치 포함 1문장]
  2. 보유기간 3년 이내: [차량명] - [잔존가치 근거 1문장]
  3. 유지비 최소화: [차량명] - [연간 유지비 근거 1문장]

## 절대 금지
- 중국어, 일본어 등 한국어 이외 언어 사용 금지
- 중국어 한자(漢字) 절대 사용 금지

오늘 날짜: {today}"""

    user_prompt = prompt_text + "\n\n" + data_block

    result = generate(system_prompt, user_prompt, tier="default")
    if result and result.get("content"):
        _body = result["content"]
        
        # 오염 방어: AI 응답 파싱 및 검증
        try:
            from shared.ai_response_parser import parse_ai_response
            parse_result = parse_ai_response(_body)
            
            # 사고과정 누수 시 발행 차단
            if parse_result['has_thinking_leak']:
                logger.error(f"[ai_writer] 사고과정 누수로 인한 발행 차단: {parse_result['leak_pattern']}")
                raise RuntimeError(f"사고과정 누수 감지: {parse_result['leak_pattern']}")
            
            # 폴백 사용 시 사유 로깅
            if parse_result['is_fallback']:
                logger.warning(f"[ai_writer] 폴백 응답 사용됨: {parse_result['title'] is None}")
                if not parse_result['title']:
                    logger.warning("[ai_writer] 명시적 제목 추출 실패 - H1 대체 시도")
            
            _title = parse_result['title']
            _body = parse_result['body']
            
        except ImportError:
            logger.warning("[ai_writer] ai_response_parser 미설치 - 기존 로직으로 진행")
            # 표 전후 빈 줄 보장 (Hugo Goldmark 호환)
            _lines = _body.split("\n")
            _out = []
            for _i, _ln in enumerate(_lines):
                if (
                    _ln.startswith("|")
                    and _i > 0
                    and _out
                    and not _out[-1].startswith("|")
                    and _out[-1].strip() != ""
                ):
                    _out.append("")
                _out.append(_ln)
                if (
                    _ln.startswith("|")
                    and _i + 1 < len(_lines)
                    and not _lines[_i + 1].startswith("|")
                    and _lines[_i + 1].strip() != ""
                ):
                    _out.append("")
            return "\n".join(_out)
        except Exception as e:
            logger.error(f"[ai_writer] 응답 파싱 중 오류: {e}")
            raise
        
        # 표 전후 빈 줄 보장 (Hugo Goldmark 호환)
        _lines = _body.split("\n")
        _out = []
        for _i, _ln in enumerate(_lines):
            if (
                _ln.startswith("|")
                and _i > 0
                and _out
                and not _out[-1].startswith("|")
                and _out[-1].strip() != ""
            ):
                _out.append("")
            _out.append(_ln)
            if (
                _ln.startswith("|")
                and _i + 1 < len(_lines)
                and not _lines[_i + 1].startswith("|")
                and _lines[_i + 1].strip() != ""
            ):
                _out.append("")
        return "\n".join(_out)
    return None

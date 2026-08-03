import logging
import os
import re
import time

import yaml
from openai import OpenAI

# Centralized env loading: .env.common first, then project .env (no override)
from shared import env_loader  # noqa: F401

logger = logging.getLogger(__name__)

CONFIG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config"
)


# Circuit breaker state (module level)
_circuit_state = {"failures": 0, "open_until": 0.0}
CIRCUIT_BREAKER_THRESHOLD = 10     # 연속 실패 N회 → 차단
CIRCUIT_BREAKER_RESET_SEC = 300    # 5분 후 자동 복구


def load_models_config():
    with open(os.path.join(CONFIG_DIR, "models.yaml"), encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_client(provider_name, providers):
    provider = providers[provider_name]
    api_key = os.getenv(provider["api_key_env"], "")
    return OpenAI(api_key=api_key, base_url=provider["base_url"], timeout=300)


def _is_chinese_content(text: str) -> bool:
    """한국어 vs 중국어 비율 검사 — 중국어가 더 많으면 True"""
    if not text:
        return False
    hangul = len(re.findall(r"[\uAC00-\uD7AF]", text))
    chinese = len(re.findall(r"[\u4E00-\u9FFF]", text))
    total = hangul + chinese
    if total == 0:
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


# 재시도 횟수 (글쓰기별)
MAX_RETRIES = 3

# 전체 tier 순서: default → fallback → economy
TIER_ORDER = ["default", "fallback", "economy"]

# Circuit breaker 설정
CIRCUIT_BREAKER_THRESHOLD = 10     # 연속 실패 N회 → 차단
CIRCUIT_BREAKER_RESET_SEC = 300    # 5분 후 자동 복구


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

    # tier 유효성 검증
    if tier not in TIER_ORDER:
        tier = "default"

    # tier 순서대로 시도
    start_idx = TIER_ORDER.index(tier)
    attempted_tiers = TIER_ORDER[start_idx:]

    last_error = None
    any_truncation_failed = False  # 전 tier 걸친 트렁케이션 실패 추적
    for attempt_tier in attempted_tiers:
        # Circuit breaker check
        if _circuit_state["open_until"] > time.time():
            logger.warning("[ai_writer] Circuit breaker OPEN — 5분 대기")
            time.sleep(60)
            continue

        # tier 키 존재 방어 — models.yaml에 없는 tier(예: branch의 fallback1)는 skip
        if attempt_tier not in config:
            logger.warning(f"[ai_writer] tier '{attempt_tier}'가 models.yaml에 없음 — skip")
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
<<<<<<< HEAD
            "max_tokens": max_tokens if max_tokens is not None else tier_config.get("max_tokens", 4000),
=======
            "max_tokens": max_tokens if max_tokens is not None else tier_config.get("max_tokens", 4000),
>>>>>>> fix/rap-subscription-backfill
        }

        # Exponential backoff retry per tier
        tier_truncation_failed = False  # 현재 tier 내 트렁케이션 실패
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
                
<<<<<<< HEAD
                # (B) reasoning 모델 대응: content가 비어있으면 reasoning_content에서 추출
=======
                # (B) reasoning 모델 대응: content가 비어있으면 reasoning_content에서 추출
>>>>>>> fix/rap-subscription-backfill
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
                    tier_truncation_failed = True
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

                # BUG-001: 잘린 조각을 결과로 쓰지 않고 max_tokens를 증분해 재요청 (유한: MAX_RETRIES만큼)
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
                    continue

                content = _clean_ai_output(content)

                # 중국어 검증
                if _is_chinese_content(content):
                    last_error = f"{attempt_tier}: 중국어 콘텐츠 감지"
                    logger.warning(f"[ai_writer] {last_error} — 다음 tier로 폴백")
                    continue

                logger.info(
                    f"[ai_writer] 성공: {attempt_tier}/{tier_config['model']} ({len(content)}자)"
                )
                return {
                    "content": content,
                    "model": tier_config["model"],
                    "provider": tier_config["provider"],
                    "tier": attempt_tier,
                    "tokens_used": response.usage.total_tokens if response.usage else 0,
                    "is_draft": False,
                }
            except Exception as e:
                _circuit_state["failures"] += 1
                if _circuit_state["failures"] >= CIRCUIT_BREAKER_THRESHOLD:
                    _circuit_state["open_until"] = time.time() + CIRCUIT_BREAKER_RESET_SEC
                    logger.critical(f"[ai_writer] Circuit breaker OPEN: {_circuit_state['failures']} failures")
                wait = (2 ** attempt) * 1.0  # 1s, 2s, 4s
                logger.warning(f"[ai_writer] Retry {attempt+1}/{MAX_RETRIES} after {wait}s: {e}")
                time.sleep(wait)
                continue

        # 현재 tier에서 MAX_RETRIES 소진
        if tier_truncation_failed:
            # 절단으로 인한 재시도 소진 → 다음 tier로 폴백
            logger.warning(f"[ai_writer] {attempt_tier}: 트렁케이션 재시도 소진 ({MAX_RETRIES}회) — 다음 tier 폴백")
            continue
        else:
            # 절단 아닌 다른 사유로 재시도 소진 → 다음 tier 폴백
            logger.warning(f"[ai_writer] {attempt_tier}: 재시도 {MAX_RETRIES}회 소진 — 다음 tier 폴백")
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
    """자동차 전문 글 생성 — DeepSeek 기본, 중국어 검증"""
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

## 공통 강화 규칙 (모든 글 필수 적용)

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

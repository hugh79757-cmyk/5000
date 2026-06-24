import os
import yaml
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
load_dotenv(os.path.expanduser("~/.env.common"))

CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")


def load_models_config():
    with open(os.path.join(CONFIG_DIR, "models.yaml"), "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_client(provider_name, providers):
    provider = providers[provider_name]
    api_key = os.getenv(provider["api_key_env"], "")
    return OpenAI(api_key=api_key, base_url=provider["base_url"])


def generate(system_prompt, user_prompt, tier="default", temperature=None, max_tokens=None):
    config = load_models_config()
    tiers = ["default", "fallback", "economy"]
    if tier not in tiers:
        tier = "default"

    tier_config = config[tier]
    providers = config["providers"]

    kwargs = dict(
        model=tier_config["model"],
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature if temperature is not None else tier_config.get("temperature", 0.7),
    )
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens

    try:
        client = get_client(tier_config["provider"], providers)
        response = client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content
        return {
            "content": content,
            "model": tier_config["model"],
            "provider": tier_config["provider"],
            "tier": tier,
            "tokens_used": response.usage.total_tokens if response.usage else 0,
        }
    except Exception:
        if tier == "default":
            return generate(system_prompt, user_prompt, tier="fallback")
        elif tier == "fallback":
            return generate(system_prompt, user_prompt, tier="economy")
        else:
            raise


def generate_car(prompt_text, data):
    import json
    from datetime import datetime

    # 메인 차량 데이터
    post_type = data.get("type", "")

    # top5_rank / persona_pick / price_trend 타입은 전체 데이터 그대로 사용
    if post_type in ("top5_rank", "persona_pick", "price_trend"):
        main_data = {k: v for k, v in data.items() if v is not None}
    else:
        main_keys = ["model", "brand", "year", "trim", "base_price", "engine", "fuel_type",
                     "fuel_efficiency", "displacement", "seats", "discount", "discount_conditions",
                     "finance_rate", "finance_term_months", "monthly_payment_36", "monthly_payment_48",
                     "monthly_payment_60", "annual_km", "tax_annual", "insurance_estimate",
                     "annual_fuel_cost", "resale_1yr", "resale_2yr", "resale_3yr", "resale_rate_percent",
                     "three_year_depreciation", "three_year_maintenance", "three_year_total_cost",
                     "final_price", "trim_lineup", "ev_range_km", "ev_efficiency", "battery_capacity_kwh",
                     "ev_charge_monthly_home", "ev_charge_monthly_slow", "ev_charge_monthly_fast",
                     "ev_charge_annual_home", "ev_charge_annual_slow", "ev_charge_annual_fast",
                     "ev_monthly_kwh", "fuel_price"]
        main_data = {k: data[k] for k in main_keys if k in data and data[k] is not None}

    # 경쟁 모델 데이터
    comp_data = {k: data[k] for k in data if k.startswith("competitor") and data[k] is not None}

    # 구조화된 데이터 블록
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
    system_prompt = f"""당신은 자동차 전문 블로그 에디터입니다. 한국어로 작성합니다.
오늘 날짜: {today}

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
  좋은 예: "월급 300만원 직장인이 8,490만원짜리 차를 유지하려면 매달 얼마가 나갈까."
  좋은 예: "1,655만원 캐스퍼와 1,575만원 모닝, 80만원 차이인데 3년 뒤 실제 비용은 어느 쪽이 더 클까."
  나쁜 예: 가격 나열로 시작하는 문장.
  나쁜 예: "~일 것입니다", "~궁금할 것입니다" 같은 추측형 존대 금지.

### 월 비용 맥락화 (필수)
- top5_rank 타입: DATA.top5[0]의 monthly_maintain(월 유지비)을 사용하라. 직접 계산하지 마라.
  형식: "연봉 [X]만원 기준 세후 월급 약 [Y]만원의 [Z]%에 해당하는 월 유지비다."
  [X]는 차량 가격대에 맞게 선택하세요. [Y] = X * 0.72 / 12. [Z] = monthly_maintain / Y * 100.
- persona_pick 타입: DATA.persona_monthly_net, DATA.persona_monthly_ratio를 그대로 사용하라. 직접 계산 금지.
  형식: "연봉 DATA.persona_salary만원 기준 세후 월급 약 DATA.persona_monthly_net만원의 DATA.persona_monthly_ratio%에 해당하는 비용이다."
  단, 비율이 100% 초과 시 "월 지출이 월급을 초과하는 수준으로, 자산 여력이 충분한 경우에 한해 고려할 만합니다"라는 문장을 추가하세요.
- 3년 총비용은 반드시 "신차 가격 대비 [X]%에 해당하는 비용"이라는 해석 1문장을 추가하세요.

### 결론부 (필수)
- 모든 글의 마지막 H2 섹션에 반드시 다음 3줄 조건부 추천을 포함하라:
  1. 예산 우선: [차량명] - [근거 수치 포함 1문장]
  2. 보유기간 3년 이내: [차량명] - [잔존가치 근거 1문장]
  3. 유지비 최소화: [차량명] - [연간 유지비 근거 1문장]

### 차별화 포인트 (필수)
- 각 글에 "다른 글에서 잘 다루지 않는 포인트" 1가지를 반드시 포함하세요.
  예: 연납 자동차세 10% 할인 시 실절감액, 보험료 직군별 차이, 초보할증 소멸 시점 등."""

    user_prompt = prompt_text + "\n\n" + data_block

    result = generate(system_prompt, user_prompt, tier="default")
    if result and result.get("content"):
        _body = result["content"]
        # 표 전후 빈 줄 보장 (Hugo Goldmark 호환)
        import re as _tbl
        _lines = _body.split("\n")
        _out = []
        for _i, _ln in enumerate(_lines):
            if _ln.startswith("|") and _i > 0 and _out and not _out[-1].startswith("|") and _out[-1].strip() != "":
                _out.append("")
            _out.append(_ln)
            if _ln.startswith("|") and _i + 1 < len(_lines) and not _lines[_i + 1].startswith("|") and _lines[_i + 1].strip() != "":
                _out.append("")
        return "\n".join(_out)
    return None

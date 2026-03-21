import os
import yaml
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")


def load_models_config():
    with open(os.path.join(CONFIG_DIR, "models.yaml"), "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_client(provider_name, providers):
    provider = providers[provider_name]
    api_key = os.getenv(provider["api_key_env"], "")
    return OpenAI(api_key=api_key, base_url=provider["base_url"])


def generate(system_prompt, user_prompt, tier="default"):
    config = load_models_config()
    tiers = ["default", "fallback", "economy"]
    if tier not in tiers:
        tier = "default"

    tier_config = config[tier]
    providers = config["providers"]

    try:
        client = get_client(tier_config["provider"], providers)
        response = client.chat.completions.create(
            model=tier_config["model"],
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=tier_config.get("max_tokens", 4096),
            temperature=tier_config.get("temperature", 0.7),
        )
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
    main_keys = ["model", "brand", "year", "trim", "base_price", "engine", "fuel_type",
                 "fuel_efficiency", "displacement", "seats", "discount", "discount_conditions",
                 "finance_rate", "finance_term_months", "monthly_payment_36", "monthly_payment_48",
                 "monthly_payment_60", "annual_km", "tax_annual", "insurance_estimate",
                 "annual_fuel_cost", "resale_1yr", "resale_2yr", "resale_3yr", "resale_rate_percent",
                 "three_year_depreciation", "three_year_maintenance", "three_year_total_cost",
                 "final_price", "trim_lineup", "ev_range_km", "ev_efficiency", "battery_capacity_kwh"]
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

    today = datetime.now().strftime("%Y년 %m월 %d일")
    system_prompt = f"""당신은 자동차 전문 블로그 에디터입니다. 한국어로 작성합니다.
오늘 날짜: {today}

절대 금지어: "과연", "놀랍게도", "충격적으로", "바랍니다", "되시길", "있으시", "마무리하며", "마치며", "정리하며", "알아보겠습니다"
글자수: 반드시 2,500자 이상 작성하세요. 2,200자 미만은 불합격입니다.
경쟁 모델 데이터가 있으면 반드시 각 섹션에서 비교 수치를 언급하세요."""

    user_prompt = prompt_text + "\n\n" + data_block

    result = generate(system_prompt, user_prompt, tier="default")
    if result and result.get("content"):
        return result["content"]
    return None

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
    data_block_lines = []
    for key, value in data.items():
        if key in ("notes", "sources", "cta_links", "thumbnail_url", "site_id"):
            continue
        data_block_lines.append(str(key) + ": " + str(value))
    data_block = "\n".join(data_block_lines)

    system_prompt = "당신은 자동차 전문 블로그 에디터입니다. 한국어로 작성합니다."
    user_prompt = prompt_text + "\n\n[DATA]\n" + data_block

    result = generate(system_prompt, user_prompt, tier="default")
    if result and result.get("content"):
        return result["content"]
    return None

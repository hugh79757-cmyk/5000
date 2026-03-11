import os
import yaml

CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")


def load_prompts():
    with open(os.path.join(CONFIG_DIR, "prompts.yaml"), "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build(prompt_id, data, extra_vars=None):
    prompts = load_prompts()
    if prompt_id not in prompts:
        raise ValueError("Unknown prompt_id: " + prompt_id)

    template = prompts[prompt_id]
    system_prompt = template["system"].strip()
    user_prompt = template["user"].strip()

    user_prompt = user_prompt.replace("{data}", data)

    if extra_vars:
        for key, value in extra_vars.items():
            user_prompt = user_prompt.replace("{" + key + "}", str(value))

    return {
        "system": system_prompt,
        "user": user_prompt,
        "prompt_id": prompt_id,
    }

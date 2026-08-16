"""config/{problems,rules}.yaml → PLAYBOOK_INDEX.yaml 재생성기 (Phase 72, Wave 2d).

PLAYBOOK_INDEX.yaml 을 코드/생성물에서 YAML 의 derived artifact 로 만든다.
단일 소스(config/*.yaml)가 바뀌면 이 스크립트로 agent-reference 인덱스를 재생성한다.

사용:
    python scripts/gen_playbook_index.py
"""
from __future__ import annotations

import os
from datetime import datetime

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROBLEMS_YAML = os.path.join(ROOT, "config", "problems.yaml")
RULES_YAML = os.path.join(ROOT, "config", "rules.yaml")
OUT = os.path.join(ROOT, "ops_dashboard", "docs", "agent-reference", "PLAYBOOK_INDEX.yaml")


def _code_record(item: dict) -> dict:
    rec = {
        "code": item.get("code"),
        "playbook_ref": item.get("playbook_ref", ""),
        "name_ko": item.get("name_ko", ""),
        "severity": item.get("severity", ""),
        "family": item.get("family", ""),
        "hook": item.get("hook", ""),
        "automation_level": item.get("automation_level", ""),
        "one_line_action": item.get("one_line_action", ""),
        "target_files": item.get("target_files", []) or [],
        "verify": item.get("verify", []) or [],
        "needs_human": bool(item.get("needs_human", False)),
    }
    return rec


def main() -> None:
    problems = yaml.safe_load(open(PROBLEMS_YAML, encoding="utf-8")).get("problems", [])
    rules = yaml.safe_load(open(RULES_YAML, encoding="utf-8")).get("rules", [])

    doc = {
        "version": "1.0",
        "generated": datetime.now().strftime("%Y-%m-%d"),
        "source_files": [
            "config/problems.yaml",
            "config/rules.yaml",
        ],
        "codes": [_code_record(p) for p in problems] + [_code_record(r) for r in rules],
    }

    with open(OUT, "w", encoding="utf-8") as f:
        yaml.safe_dump(
            doc,
            f,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
            width=1000,
        )

    print(f"PLAYBOOK_INDEX.yaml 재생성 완료: {len(doc['codes'])} codes "
          f"(problems={len(problems)}, rules={len(rules)}) -> {OUT}")


if __name__ == "__main__":
    main()

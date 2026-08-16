"""config/*.yaml 단일 소스 레지스트리 오버레이 로더 (Phase 72, Wave 2d).

목적: 오류/규칙 정의를 코드 dict 에서 YAML 로 단일 소스화하면서도, 라이브 프로세스를
절대 깨지 않게 한다.

- problems.yaml 은 PROBLEM_REGISTRY 를 **YAML 우선 오버라이드**한다 (코드 dict 는 fallback).
  YAML 에 없는 code 는 기존 코드 dict 그대로 유지.
- rules.yaml 은 RULES 에 **없는 신규 id 만 append** 한다 (idempotent skip — FM-*/C08 등
  코드 선언과 중복 방지). 기존 R01~R12 의 동작은 코드 RULES 가 주도, YAML 는 friendly 메타 소스.
- get_friendly(code) 는 YAML 캐시에서 friendly 메타(summary_human/summary_llm/how_to_add/
  automation_level) 를 조회 — 라이브 크래시 없음.

모든 진입점은 호출 측에서 try/except 로 감싸져 있으나, 이 모듈 내부에서도 YAML 누락/오류를
조용히 swallow 하여 라이브 import 경로가 절대 실패하지 않도록 한다.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_PROBLEMS_YAML = "config/problems.yaml"
DEFAULT_RULES_YAML = "config/rules.yaml"

# YAML 원본 캐시 (friendly 조회용). _ensure_loaded() 에서 한 번 채움.
_PROBLEMS_CACHE: dict[str, dict] = {}
_RULES_CACHE: dict[str, dict] = {}
_LOADED = False


def _load_yaml_file(path: str) -> dict:
    import yaml
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_problems_yaml(path: str = DEFAULT_PROBLEMS_YAML) -> dict:
    """YAML problems → {code: ProblemSpec}. 누락/오류 시 빈 dict 반환."""
    from shared.problem_registry import ProblemSpec

    out: dict[str, Any] = {}
    try:
        data = _load_yaml_file(path)
    except Exception as exc:
        logger.warning("[registry_loader] problems.yaml 로드 실패(%s): %s", path, exc)
        return out
    for item in data.get("problems", []) or []:
        code = item.get("code")
        if not code:
            continue
        try:
            out[code] = ProblemSpec(
                problem_id=code,
                name_ko=item.get("name_ko", ""),
                severity=item.get("severity", "MINOR"),
                reason_keys=tuple(item.get("reason_keys", []) or []),
                hook=item.get("hook", "result_parse"),
                threshold=item.get("threshold", "quiet"),
                alert_template=item.get("alert_template", ""),
                action=item.get("action", ""),
                playbook_ref=item.get("playbook_ref", ""),
                summary_human=item.get("summary_human", ""),
                summary_llm=item.get("summary_llm", ""),
                how_to_add=item.get("how_to_add", ""),
                reason_overrides=item.get("reason_overrides", {}) or {},
            )
        except Exception as exc:
            logger.warning("[registry_loader] problem 항목 파싱 실패 %s: %s", code, exc)
    return out


def apply_problem_yaml(path: str = DEFAULT_PROBLEMS_YAML) -> int:
    """PROBLEM_REGISTRY 를 YAML 우선 오버라이드. 반환: 오버라이드/등록된 코드 수.

    PR3: YAML spec 이 reason_overrides 를 갖고 있지 않으면 코드 dict 의 reason_overrides 를
    병합한다 — no_topics(WAITING) 같은 코드 전용 presentation override 가 YAML 오버라이드로
    유실되지 않도록 한다 (YAML 에 명시하면 YAML 값이 우선).
    """
    from dataclasses import replace

    from shared.problem_registry import PROBLEM_REGISTRY

    specs = load_problems_yaml(path)
    count = 0
    for code, spec in specs.items():
        existing = PROBLEM_REGISTRY.get(code)
        if (
            existing is not None
            and not spec.reason_overrides
            and getattr(existing, "reason_overrides", None)
        ):
            spec = replace(spec, reason_overrides=existing.reason_overrides)
        PROBLEM_REGISTRY[code] = spec  # 코드 dict 있든 없든 YAML 우선 (신규 P33 등 확장)
        count += 1
    return count


def load_rules_yaml(path: str = DEFAULT_RULES_YAML) -> list:
    """YAML rules → [UnifiedEntry]. 누락/오류 시 빈 list 반환."""
    from ops_dashboard.registry.schema import UnifiedEntry, validate_entry

    out: list = []
    try:
        data = _load_yaml_file(path)
    except Exception as exc:
        logger.warning("[registry_loader] rules.yaml 로드 실패(%s): %s", path, exc)
        return out
    for item in data.get("rules", []) or []:
        rid = item.get("code")
        if not rid:
            continue
        try:
            entry = UnifiedEntry(
                id=rid,
                kind="rule",
                target=item.get("target", item.get("name_ko", "")),
                severity=item.get("severity", "MINOR"),
                threshold=item.get("threshold", "always"),
                check_fn=item.get("check_fn", ""),
                action=item.get("action", item.get("one_line_action", "")),
                bucket=item.get("bucket", "actionable"),
            )
            validate_entry(entry)
            out.append(entry)
        except Exception as exc:
            logger.warning("[registry_loader] rule 항목 파싱 실패 %s: %s", rid, exc)
    return out


def apply_rule_yaml(path: str = DEFAULT_RULES_YAML) -> list:
    """RULES 에 없는 신규 id 만 append (idempotent). 반환: 추가된 entry 리스트."""
    from ops_dashboard.registry.rules import RULES

    existing = {e.id for e in RULES}
    new_entries = [e for e in load_rules_yaml(path) if e.id not in existing]
    RULES.extend(new_entries)
    return new_entries


def _ensure_loaded() -> None:
    global _LOADED
    if _LOADED:
        return
    try:
        data_p = _load_yaml_file(DEFAULT_PROBLEMS_YAML)
        for item in data_p.get("problems", []) or []:
            if item.get("code"):
                _PROBLEMS_CACHE[item["code"]] = item
    except Exception as exc:
        logger.warning("[registry_loader] problems 캐시 실패: %s", exc)
    try:
        data_r = _load_yaml_file(DEFAULT_RULES_YAML)
        for item in data_r.get("rules", []) or []:
            if item.get("code"):
                _RULES_CACHE[item["code"]] = item
    except Exception as exc:
        logger.warning("[registry_loader] rules 캐시 실패: %s", exc)
    _LOADED = True


def get_friendly(code: str) -> dict:
    """code → friendly 메타 dict. YAML 캐시 우선, 없으면 빈 dict (라이브 크래시 없음)."""
    _ensure_loaded()
    item = _PROBLEMS_CACHE.get(code) or _RULES_CACHE.get(code)
    if not item:
        return {}
    return {
        "summary_human": item.get("summary_human", ""),
        "summary_llm": item.get("summary_llm", ""),
        "how_to_add": item.get("how_to_add", ""),
        "automation_level": item.get("automation_level", ""),
    }

"""규칙 계층 로딩/조회 — Phase 62 (M5 Step 1).

global/family/blog 3계층 규칙 로딩과 해석 계약:
- global = config/rules.yaml 의 scope 미지정(기본 global) 항목 (기존 R01~R12 무변경 전부 global)
- family = scope="family" + family=<brand> 항목 (brand 판정은 ops_dashboard.get_blog_brand)
- blog   = blogs.d/*.yaml 의 선택적 "quality_rules:" 키 항목

우선순위: blog > family > global — 같은 code 가 여러 계층에 있으면 더 구체적 계층이 대체.
이 모듈은 순수 로딩/해석 계층 — DB(명시적 conn 제외)/네트워크/배포 부작용 없음.
"""

from dataclasses import dataclass

import yaml

from shared.paths import CONFIG_DIR

DEFAULT_RULES_YAML = f"{CONFIG_DIR}/rules.yaml"


@dataclass
class RuleSpec:
    """단일 규칙 스펙 (3계층 공용)."""

    code: str
    severity: str
    scope: str = "global"  # "global" | "family" | "blog"
    family: str | None = None  # brand — scope="family"일 때만 의미
    check: str = ""  # check_fn 또는 code


def load_rules(config_path: str | None = None) -> list[RuleSpec]:
    """config/rules.yaml 의 rules: 항목을 RuleSpec 목록으로 로드.

    - scope 미지정 → "global" (기존 R01~R12 무변경 전부 global)
    - scope="family" && family 미지정 → ValueError("scope=family requires family=<brand>")
    - 파일 없음/파싱 실패 → raise (조용한 실패 금지)
    """
    path = config_path or DEFAULT_RULES_YAML
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    out: list[RuleSpec] = []
    for item in data.get("rules", []) or []:
        if not isinstance(item, dict) or not item.get("code"):
            continue
        scope = str(item.get("scope", "global"))
        family = None
        if scope == "family":
            family = item.get("family")
            if not family:
                raise ValueError("scope=family requires family=<brand>")
            family = str(family)
        # 기존 rules.yaml 의 family="validation" 은 category — scope != family 일 때
        # brand 로 해석하지 않는다 (오버로드 방지, SUMMARY-DRAFT 잔존 위험 반영).
        out.append(
            RuleSpec(
                code=str(item["code"]),
                severity=str(item.get("severity", "WARNING")),
                scope=scope,
                family=family,
                check=str(item.get("check_fn", "") or item["code"]),
            )
        )
    return out


def load_blog_rules(blog_cfg: dict) -> list[RuleSpec]:
    """blogs.d/*.yaml 블로그 항목 dict 에서 선택적 "quality_rules:" 키 추출.

    형태: [{code, severity, scope:"blog", ...}]. 키 부재 → [].
    """
    items = blog_cfg.get("quality_rules", []) or []
    out: list[RuleSpec] = []
    for item in items:
        if not isinstance(item, dict) or not item.get("code"):
            continue
        out.append(
            RuleSpec(
                code=str(item["code"]),
                severity=str(item.get("severity", "WARNING")),
                scope=str(item.get("scope", "blog")),
                family=str(item["family"]) if item.get("family") else None,
                check=str(item.get("check", "") or item.get("check_fn", "") or item["code"]),
            )
        )
    return out


def resolve_rules(
    rules,
    brand,
    blog_id=None,
    blog_overrides=None,
) -> list[RuleSpec]:
    """3계층 해석 — blog > family > global 우선순위 (순수 함수).

    - blog: blog_overrides[blog_id] 의 blog 규칙
    - family: rule.scope == "family" && rule.family == brand
    - global: rule.scope == "global"
    같은 code 가 여러 계층에 있으면 더 구체적 계층이 대체.
    blog_overrides: dict[str, list[RuleSpec]] — blog_id → blog 규칙 목록.
    """
    blog_overrides = blog_overrides or {}
    resolved: dict[str, RuleSpec] = {}
    # global 계층
    for r in rules:
        if r.scope == "global":
            resolved[r.code] = r
    # family 계층 — brand 일치 시 global 대체
    if brand:
        for r in rules:
            if r.scope == "family" and r.family == brand:
                resolved[r.code] = r
    # blog 계층 — blog_overrides 가 family/global 대체
    if blog_id and blog_id in blog_overrides:
        for r in blog_overrides[blog_id]:
            if isinstance(r, RuleSpec):
                resolved[r.code] = r
    return list(resolved.values())


def resolve_rules_for_blog(
    rules,
    conn,
    blog_id,
    blog_overrides=None,
) -> list[RuleSpec]:
    """편의 함수 — ops_dashboard.get_blog_brand 로 brand 조회 후 resolve_rules 위임.

    ops_dashboard.db import 는 함수 내부에서만 수행 (import 시점 부작용 없음).
    brand 가 None 이면 family 규칙 제외 (global + blog 만) — resolve_rules(brand=None) 이
    자연히 family 규칙(rule.family == brand 일치 불가)을 배제.
    """
    from ops_dashboard.db import get_blog_brand  # function-internal import

    brand = get_blog_brand(conn, blog_id)
    return resolve_rules(rules, brand, blog_id=blog_id, blog_overrides=blog_overrides)

"""ops_dashboard.checks.c08_staging — c08 2단계 판정 레이어 (스키마-as-code).

설계 참조: docs/superpowers/specs/2026-08-22-schema-as-code-design.md §3b
  - Stage 1 (로컬 전용): 로컬 frontmatter vs SchemaSpec → LOCAL_VIOLATION 즉시 확정.
  - Stage 2 (라이브 비교): Stage 1 통과 시에만 라이브 og:title/og:image 비교 →
    LIVE_DRIFT / FALSE_POSITIVE(dismiss).

기존 content_integrity.py _compare_live_vs_local은 **무수정**. 이 모듈이 위에
새 판정 레이어로 얹힌다.

사용:
  - CI 드라이런 = stage1()만 (로컬 파일 기반, 라이브 크롤 없음).
  - 대시보드 정기 검사 = stage1() → 통과 시 stage2().
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

from ops_dashboard.schema_loader import load_schema, SchemaSpec

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Stage 1 — 로컬 frontmatter vs SchemaSpec
# ---------------------------------------------------------------------------


def stage1(frontmatter: dict, spec: SchemaSpec | None = None,
           blog_id: str | None = None) -> dict:
    """Stage 1: 로컬 frontmatter를 SchemaSpec과 대조 → 위반 rule_id 목록.

    입력:
      frontmatter: 포스트 frontmatter dict (파싱된 YAML)
      spec: SchemaSpec (None이면 blog_id로 load_schema)
      blog_id: spec 생략 시 로드용

    출력:
      {"status": "PASS"} 또는 {"status": "LOCAL_VIOLATION", "violations": [rule_id...]}
    """
    if spec is None:
        spec = load_schema(blog_id) if blog_id else None
    if spec is None:
        # 스키마 없으면 검사 불가 — 통과로 간주 (기존 체커 동작 유지)
        return {"status": "PASS", "violations": []}

    violations: list[str] = []

    # 1) required_frontmatter 빈 값/누락 (empty_value_policy 기본 disallow)
    for field in spec.required_frontmatter:
        val = str(frontmatter.get(field, "") or "").strip()
        if not val:
            policy = spec.empty_value_policy.get(field, "disallow")
            if policy == "disallow":
                violations.append(f"FM-EMPTY:{field}")

    # 2) title_format_rule — forbid_ellipsis / max_len / allow_suffix
    title = str(frontmatter.get("title", "") or "")
    tfr = spec.title_format_rule or {}
    if title:
        forbid = tfr.get("forbid_ellipsis", True)
        allow_suffix = tfr.get("allow_suffix") or []
        if forbid:
            stripped = title
            for suf in allow_suffix:
                stripped = stripped.rstrip(suf)
            if "…" in stripped or "..." in stripped:
                violations.append("FM-TITLE_FORMAT:ellipsis")
        max_len = tfr.get("max_len")
        if max_len and len(title) > max_len:
            violations.append(f"FM-TITLE_FORMAT:max_len({len(title)}>{max_len})")

    # 3) og_rule.og_image_required — featureimage 필수
    og_rule = spec.og_rule or {}
    if og_rule.get("og_image_required"):
        src_key = og_rule.get("og_image_source", "featureimage")
        if not str(frontmatter.get(src_key, "") or "").strip():
            violations.append(f"FM-OG-REQUIRED:{src_key}")

    if violations:
        return {"status": "LOCAL_VIOLATION", "violations": violations}
    return {"status": "PASS", "violations": []}


# ---------------------------------------------------------------------------
# Stage 2 — 라이브 og:title/og:image vs SchemaSpec.live_og_format_rule
# ---------------------------------------------------------------------------

# 라이브 og 메타 추출용 (content_integrity.py와 동일 패턴)
_OG_TITLE_RE = re.compile(
    r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']*)["\']',
    re.I,
)
_OG_IMAGE_RE = re.compile(
    r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']*)["\']',
    re.I,
)


def _extract_live_og(live_html: str) -> dict:
    """라이브 HTML에서 og:title / og:image 추출."""
    title_m = _OG_TITLE_RE.search(live_html or "")
    image_m = _OG_IMAGE_RE.search(live_html or "")
    return {
        "og_title": title_m.group(1).strip() if title_m else "",
        "og_image": image_m.group(1).strip() if image_m else "",
    }


def _matches_format(local_title: str, live_og_title: str, rule: str) -> bool:
    """live_og_format_rule 기준 로컬 title vs 라이브 og:title 정상 여부.

    - exact_match: 완전 일치
    - contains: live가 local을 포함 (local ⊂ live)
    - prefix_match: live가 local로 시작
    - case_insensitive_match: 대소문자 무시 일치
    """
    if not live_og_title:
        return False
    lt, lt_s = local_title.strip().lower(), local_title.strip()
    if rule == "contains":
        return lt in live_og_title.lower()
    if rule == "prefix_match":
        return live_og_title.lower().startswith(lt)
    if rule == "case_insensitive_match":
        return lt == live_og_title.lower()
    # exact_match (기본)
    return lt_s == live_og_title.strip()


def stage2(frontmatter: dict, live_html: str,
           spec: SchemaSpec | None = None,
           blog_id: str | None = None) -> dict:
    """Stage 2: 라이브 og 메타 vs SchemaSpec → LIVE_DRIFT / FALSE_POSITIVE.

    Stage 1 통과 후에만 호출 (호출부가 보장). 라이브 크롤은 호출부 책임 —
    이 함수는 이미 받은 live_html만 판정한다.

    출력:
      {"status": "FALSE_POSITIVE", "reason": "..."}  (정상 — 기존 C08 신호 dismiss)
      {"status": "LIVE_DRIFT", "drifts": [서브코드...]}  (실제 라이브 결함)
    """
    if spec is None:
        spec = load_schema(blog_id) if blog_id else None
    if spec is None:
        return {"status": "FALSE_POSITIVE", "reason": "스키마 없음 — 판정 불가, dismiss"}

    live = _extract_live_og(live_html)
    local_title = str(frontmatter.get("title", "") or "").strip()
    og_rule = spec.og_rule or {}
    drifts: list[str] = []

    # og:image — 로컬 featureimage vs 라이브 og:image
    if og_rule.get("og_image_required"):
        src_key = og_rule.get("og_image_source", "featureimage")
        local_og = str(frontmatter.get(src_key, "") or "").strip()
        if local_og and not live["og_image"]:
            drifts.append("C08_OG_MISSING")
        elif local_og and live["og_image"] and local_og.rstrip("/") != live["og_image"].rstrip("/"):
            drifts.append("C08_OG_MISMATCH")

    # og:title — live_og_format_rule
    if local_title and live["og_title"]:
        if not _matches_format(local_title, live["og_title"], spec.live_og_format_rule):
            drifts.append("C08_TITLE_MISMATCH")

    if drifts:
        return {"status": "LIVE_DRIFT", "drifts": drifts}
    return {"status": "FALSE_POSITIVE", "reason": "라이브 og 메타가 스키마 규칙 충족"}


# ---------------------------------------------------------------------------
# 통합 판정 (대시보드 정기 검사용: Stage 1 → Stage 2)
# ---------------------------------------------------------------------------


def check_c08_staged(frontmatter: dict, live_html: str,
                     blog_id: str | None = None,
                     spec: SchemaSpec | None = None) -> dict:
    """c08 2단계 통합 판정.

    Stage 1 LOCAL_VIOLATION → 즉시 확정 (라이브 크롤 생략).
    Stage 1 PASS → Stage 2로 라이브 og 비교.

    출력: {"status": "LOCAL_VIOLATION"|"LIVE_DRIFT"|"FALSE_POSITIVE", ...}
    """
    s1 = stage1(frontmatter, spec=spec, blog_id=blog_id)
    if s1["status"] == "LOCAL_VIOLATION":
        return s1
    s2 = stage2(frontmatter, live_html, spec=spec, blog_id=blog_id)
    return s2

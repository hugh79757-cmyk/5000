"""ops_dashboard.registry.errors — 발행 오류 P01~P24 (+unknown_failure) 선언 (Phase 69, W1).

`shared/problem_registry.py`의 `PROBLEM_REGISTRY`(ProblemSpec)를 **동일한 중립
스키마(UnifiedEntry)** 로 미러링한 순수 선언이다. 기존 PROBLEM_REGISTRY는 이 웨이브에서
수정하지 않는다 — 소비 전환은 후속 웨이브(W5/W6)에서 이룬다.

매핑 규칙 (ProblemSpec -> UnifiedEntry):
    problem_id -> id
    name_ko    -> target (대상/설명)
    severity   -> severity (그대로)
    threshold  -> threshold (그대로)
    detect_fn  -> check_fn (detect_fn 없으면 hook 값으로 대체)
    action     -> action (그대로)
    bucket     -> 기본값 "" (error는 준수율 산정 대상 아님)

PROBLEM_REGISTRY에서 직접 파생하므로 카운트 불일치(기존 오류 수 != 레지스트리 오류 수)가
구조적으로 발생하지 않는다. 단, PROBLEM_REGISTRY 자체는 절대 수정하지 않는다.
"""
from __future__ import annotations

from shared.problem_registry import PROBLEM_REGISTRY, ProblemSpec
from ops_dashboard.registry.schema import UnifiedEntry, validate_entry


def _to_entry(spec: ProblemSpec) -> UnifiedEntry:
    return UnifiedEntry(
        id=spec.problem_id,
        kind="error",
        target=spec.name_ko,
        severity=spec.severity,
        threshold=spec.threshold,
        check_fn=spec.detect_fn or spec.hook,
        action=spec.action or spec.name_ko,
        bucket="",
    )


# PROBLEM_REGISTRY의 모든 spec을 중립 스키마로 미러링 (기존 dict는 변경하지 않음).
ERRORS: list[UnifiedEntry] = [_to_entry(spec) for spec in PROBLEM_REGISTRY.values()]

# W1 게이트: 모든 선언이 스키마 허용 값을 지키는지 즉시 검증.
for _entry in ERRORS:
    validate_entry(_entry)

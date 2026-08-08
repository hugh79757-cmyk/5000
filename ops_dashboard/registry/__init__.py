"""ops_dashboard.registry — 통합 규칙·오류 레지스트리 (Phase 69, W1).

규칙(RULES)과 오류(ERRORS)를 하나의 중립 스키마(UnifiedEntry)로 통합 조회하는 API.

이 패키지는 **순수 정의**만 담는다 — 실행 경로(check 함수 디스패치, DB 기록, 엔드포인트)
에는 연결하지 않는다. 후속 웨이브(W3/W5/W6/W7)와 신규 규칙/오류 콘텐츠 채우기가 이 API를
공통 계약으로 사용한다.

제공 API:
    all_entries() -> list[UnifiedEntry]   # RULES + ERRORS 병합
    get_entry(id) -> UnifiedEntry | None  # 전역 고유 id로 조회
    by_kind(kind) -> list[UnifiedEntry]   # kind(rule|error)별 필터
"""
from __future__ import annotations

from ops_dashboard.registry.schema import UnifiedEntry, KIND, SEVERITY, THRESHOLD, BUCKET, validate_entry
from ops_dashboard.registry.rules import RULES
from ops_dashboard.registry.errors import ERRORS

__all__ = [
    "UnifiedEntry",
    "KIND",
    "SEVERITY",
    "THRESHOLD",
    "BUCKET",
    "validate_entry",
    "RULES",
    "ERRORS",
    "all_entries",
    "get_entry",
    "by_kind",
]

# 병합 시 id 중복이 없어야 한다 (전역 고유). 구조적으로 RULES/R01..R12와
# ERRORS/P01..P24(+unknown_failure)는 접두사가 달라 중복되지 않는다.
_INDEX: dict[str, UnifiedEntry] = {e.id: e for e in RULES + ERRORS}
if len(_INDEX) != len(RULES) + len(ERRORS):
    dupes = [e.id for e in RULES + ERRORS if (RULES + ERRORS).count(e) > 1]
    raise ValueError(f"registry entry id 중복: {dupes}")


def all_entries() -> list[UnifiedEntry]:
    """모든 규칙·오류 선언 반환 (RULES + ERRORS 병합)."""
    return RULES + ERRORS


def get_entry(entry_id: str) -> UnifiedEntry | None:
    """전역 고유 id로 단일 선언 조회. 없으면 None."""
    return _INDEX.get(entry_id)


def by_kind(kind: str) -> list[UnifiedEntry]:
    """kind("rule"|"error")로 필터링한 선언 목록 반환."""
    return [e for e in all_entries() if e.kind == kind]

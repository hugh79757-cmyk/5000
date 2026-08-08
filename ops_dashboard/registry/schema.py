"""ops_dashboard.registry.schema — 통합 레지스트리 중립 스키마 (Phase 69, W1).

규칙(R01~R12)과 오류(P01~P24)를 하나의 동일한 선언 스키마(UnifiedEntry)로 표현한다.

이 모듈은 **순수 정의**만 담는다 — 실행 경로(check 함수 디스패치, DB 기록,
엔드포인트)에는 일절 연결하지 않는다. 소비는 후속 웨이브(W3/W5/W6)에서 registry API
(all_entries/get_entry/by_kind)를 통해 이루어진다.

필드 스키마 (중립):
    id          : 전역 고유 (R01 / P01 / THUMBNAIL-01 / R2-01)
    kind        : "rule" | "error"
    target      : 파일 경로 또는 대상 (hugo.toml, extend-head.html, body, publish, ...)
    severity    : CRITICAL | MAJOR | MINOR
    threshold   : always | consecutive:N | quiet
    check_fn    : rule용 검사함수명 / error용 detect_fn
    action      : 조치 안내 텍스트
    bucket      : rule용 준수율 산정 (actionable|deferred|out_of_scope), error는 빈 문자열

strictly additive — 기존 STANDARD_RULES/SEED_STANDARD_RULES/problem_registry/
auto_triage_rules.yaml은 수정하지 않는다. 신규 레지스트리에 미러링만 한다.
"""
from __future__ import annotations

from dataclasses import dataclass

# 허용 값 상수 — 잘못된 값은 validate_entry()에서 ValueError (조용한 실패 금지).
KIND: tuple = ("rule", "error")
SEVERITY: tuple = ("CRITICAL", "MAJOR", "MINOR")
THRESHOLD: tuple = ("always", "consecutive:N", "quiet")
BUCKET: tuple = ("actionable", "deferred", "out_of_scope")


@dataclass(frozen=True)
class UnifiedEntry:
    """규칙/오류 1건의 중립 선언 스키마."""

    id: str            # 전역 고유 (R01 / P01 / THUMBNAIL-01 / R2-01)
    kind: str          # "rule" | "error"
    target: str        # 파일 경로 또는 대상 (hugo.toml, extend-head.html, body, publish, ...)
    severity: str      # CRITICAL | MAJOR | MINOR
    threshold: str     # always | consecutive:N | quiet
    check_fn: str      # rule용 검사함수명 / error용 detect_fn
    action: str        # 조치 안내 텍스트
    bucket: str = ""   # rule용 준수율 산정 (actionable|deferred|out_of_scope)


def _valid_threshold(value: str) -> bool:
    """threshold 허용 값 검증.

    `consecutive:N` 은 리터럴 패턴이므로, 실제 값은 `consecutive:3` 처럼
    양의 정수 N을 붙인 형태로 온다. 패턴과 구체값 모두 허용한다.
    """
    if value in THRESHOLD:
        return True
    if value.startswith("consecutive:"):
        suffix = value[len("consecutive:"):]
        return suffix.isdigit() and int(suffix) > 0
    return False


def validate_entry(entry: "UnifiedEntry") -> None:
    """선언 스키마가 허용 값 집합을 지키는지 검증.

    잘못된 kind/severity/threshold/bucket이면 ValueError를 던진다.
    id는 비어있지 않아야 한다. (조용한 실패 금지 원칙)
    """
    if not entry.id:
        raise ValueError(f"registry entry id는 비어 있을 수 없음: {entry!r}")
    if entry.kind not in KIND:
        raise ValueError(
            f"invalid kind={entry.kind!r} for id={entry.id!r}; "
            f"expected one of {KIND}"
        )
    if entry.severity not in SEVERITY:
        raise ValueError(
            f"invalid severity={entry.severity!r} for id={entry.id!r}; "
            f"expected one of {SEVERITY}"
        )
    if not _valid_threshold(entry.threshold):
        raise ValueError(
            f"invalid threshold={entry.threshold!r} for id={entry.id!r}; "
            f"expected one of {THRESHOLD} (예: consecutive:N 에서 N은 양의 정수)"
        )
    # bucket은 rule에서만 사용 (error는 기본값 빈 문자열 허용).
    if entry.kind == "rule" and entry.bucket not in BUCKET:
        raise ValueError(
            f"invalid bucket={entry.bucket!r} for rule id={entry.id!r}; "
            f"expected one of {BUCKET}"
        )

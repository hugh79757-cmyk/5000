"""공용 ValidationResult 계약 — Phase 62 (M5 Step 1).

16종 검증 반환값(list[str] / (ok, errors) / dict / preflight)을 하나의
ValidationResult 계약으로 묶는 어댑터 계층. report-only 기본값(block=False):
기존 발행 파이프라인 동작은 100% 무변경이며, 차단 게이트 활성화는 Phase 63.

호환성 원칙:
- 래핑 대상(dispatcher preflight_check, validators validate_post 등)은
  read-only 참조 — 이 모듈은 반환 형태만 소비하는 어댑터.
- evidence sanitize는 shared.pipeline_result._sanitize_evidence 재사용(복제 금지).
- DB/네트워크/부작용 없음. JSON 직렬화 가능(dispatcher JSON 계약 불변).
"""

from dataclasses import dataclass, field

from shared.pipeline_result import _sanitize_evidence
from shared.problem_registry import lookup_reason


@dataclass
class ValidationIssue:
    """단일 검증 이슈."""

    severity: str  # "CRITICAL" | "WARNING" | "INFO"
    check: str  # rule/check id (R01, CQ-UNIT, validate_post, ...)
    msg: str


@dataclass
class ValidationResult:
    """공용 검증 결과 계약.

    - passed: 검증 통과 여부
    - issues: 검증 이슈 목록
    - scope: "global" | "family" | "blog"
    - family: brand (cap/cuap/etap/rap/seap/stap/tap/manual) 또는 None
    - block: report-only 기본값(False). Phase 63에서만 True 활성화.
    """

    passed: bool
    issues: list[ValidationIssue] = field(default_factory=list)
    scope: str = "global"  # "global" | "family" | "blog"
    family: str | None = None  # brand — scope="family"일 때만 의미
    blog_id: str | None = None
    block: bool = False  # report-only 기본값 — Phase 63에서만 True 활성화

    def to_legacy(self) -> dict:
        """preflight 구조로 변환 — dispatcher preflight_check dict 선례 미러링.

        {"blocked": self.block,
         "violations": [{"check": ..., "severity": ..., "detail": ...}],
         "reason": "" if passed else "validation_failed"}
        """
        return {
            "blocked": self.block,
            "violations": [
                {"check": i.check, "severity": i.severity, "detail": i.msg}
                for i in self.issues
            ],
            "reason": "" if self.passed else "validation_failed",
        }

    def to_incident(self, reason_key: str, stage: str) -> dict:
        """incident 계약 — reason/stage/detail 3요소 + pcode 채움 경로.

        - reason: reason_key (등록된 reason 어휘 폐쇄 유지)
        - stage: 안정 stage 문자열 (호출 측이 명시)
        - detail: issues[:5] 를 "; " 로 join 후 _sanitize_evidence (≤500자, 비밀 마스킹)
        - pcode: lookup_reason(reason_key) → problem_id. 미등록이면 "" — never raise.
        실제 incident 호출(Telegram 등)은 Phase 63. 이 메서드는 dict 생성 계약만 제공.
        """
        spec = lookup_reason(reason_key)
        pcode = spec.problem_id if spec else ""
        detail = _sanitize_evidence(
            "; ".join(f"[{i.severity}] {i.msg}" for i in self.issues[:5])
        )
        return {"reason": reason_key, "stage": stage, "detail": detail, "pcode": pcode}

    def as_pipeline_extra(self) -> dict:
        """dispatcher 정규화(:1321-1333) extra passthrough 계약.

        {"validation": {"passed", "issues": [{severity,check,msg}...],
                        "scope", "family", "block"}}
        success/reason 최상위 키 불변 — report-only(block=False)는 절대
        차단 상태(blocked/publish_blocked)로 매핑하지 않는다.
        """
        return {
            "validation": {
                "passed": self.passed,
                "issues": [
                    {"severity": i.severity, "check": i.check, "msg": i.msg}
                    for i in self.issues
                ],
                "scope": self.scope,
                "family": self.family,
                "block": self.block,
            }
        }


def from_legacy_issues(
    issues,
    *,
    blog_id=None,
    scope="global",
    family=None,
    check="validate_post",
) -> ValidationResult:
    """기존 검증 반환값 3종을 ValidationResult로 변환 (never-raise).

    허용 형태:
      list[str]:            passed = (len == 0)
                            "[ERROR] ..." → CRITICAL, "[WARNING] ..." → WARNING,
                            접두사 없음 → WARNING
      (ok: bool, errors: list[str]): passed = ok
      dict {"passed": bool, "issues": [{"severity","check","msg"}]}: 그대로 변환
    그 외 형태: passed=False + CRITICAL "unknown_legacy_shape" 폴백 (T06 패턴).
    """
    # dict 형태
    if isinstance(issues, dict):
        raw_issues = issues.get("issues", [])
        converted = []
        for it in raw_issues:
            if not isinstance(it, dict):
                converted.append(ValidationIssue("WARNING", check, str(it)))
                continue
            converted.append(
                ValidationIssue(
                    severity=str(it.get("severity", "WARNING")),
                    check=str(it.get("check", check)),
                    msg=str(it.get("msg", "")),
                )
            )
        return ValidationResult(
            passed=bool(issues.get("passed", False)),
            issues=converted,
            scope=scope,
            family=family,
            blog_id=blog_id,
        )

    # (ok, errors) 튜플 형태
    if (
        isinstance(issues, (tuple, list))
        and len(issues) == 2
        and isinstance(issues[0], bool)
        and isinstance(issues[1], (list, tuple))
    ):
        ok, errors = issues
        return ValidationResult(
            passed=ok,
            issues=[
                ValidationIssue(severity="WARNING", check=check, msg=str(e))
                for e in errors
            ],
            scope=scope,
            family=family,
            blog_id=blog_id,
        )

    # list[str] 형태
    if isinstance(issues, list) and all(
        isinstance(i, str) for i in issues
    ):
        return ValidationResult(
            passed=(len(issues) == 0),
            issues=[_issue_from_str(i, check) for i in issues],
            scope=scope,
            family=family,
            blog_id=blog_id,
        )

    # 알 수 없는 형태 — never-raise 폴백
    return ValidationResult(
        passed=False,
        issues=[ValidationIssue("CRITICAL", check, "unknown_legacy_shape")],
        scope=scope,
        family=family,
        blog_id=blog_id,
    )


def _issue_from_str(item: str, check: str) -> ValidationIssue:
    """list[str] 항목에서 severity 접두사 매핑. 접두사 없음 → WARNING."""
    if item.startswith("[ERROR]"):
        return ValidationIssue("CRITICAL", check, item)
    if item.startswith("[WARNING]"):
        return ValidationIssue("WARNING", check, item)
    return ValidationIssue("WARNING", check, item)


def from_preflight(preflight: dict, *, blog_id=None) -> ValidationResult:
    """dispatcher.preflight_check dict 소비 (read-only 어댑터).

    preflight 구조: {"blocked": bool, "violations": [{slug, rule_id,
    severity, detail}], ...}
    - passed = not blocked
    - block  = bool(preflight.get("blocked")) — 기존 차단 게이트 의미 보존
    """
    violations = preflight.get("violations", [])
    issues = []
    for v in violations if isinstance(violations, list) else []:
        if not isinstance(v, dict):
            continue
        issues.append(
            ValidationIssue(
                severity=str(v.get("severity", "WARNING")),
                check=str(v.get("rule_id", "preflight")),
                msg=f"{v.get('slug', '')}: {v.get('detail', '')}",
            )
        )
    blocked = bool(preflight.get("blocked", False))
    return ValidationResult(
        passed=not blocked,
        issues=issues,
        scope="global",
        blog_id=blog_id,
        block=blocked,
    )

"""Backward-compatible Pipeline Result Contract (PR-CAP-1).

Pure data + adapter. No DB access, no network, no import side effects.
Does NOT write incident tables, generate incident_key, or change any
pipeline behavior. Safe to import anywhere in the 5000 codebase.

Scope (per approval package): introduce a structured result contract while
keeping every existing caller (dispatcher normalization, scheduler JSON
parse) working unchanged. All 6 dashboard defects and PR-CAP-2/3/4/5 work are
explicitly OUT of scope here.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional

_EVIDENCE_MAX = 500
_SECRET_RE = re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*=")
_NEWLINE_RE = re.compile(r"\n")


class PipelineStatus(str, Enum):
    SUCCESS = "SUCCESS"
    WAITING_FOR_CANDIDATES = "WAITING_FOR_CANDIDATES"
    BLOCKED_QUALITY = "BLOCKED_QUALITY"
    FAILED_TRANSIENT = "FAILED_TRANSIENT"
    FAILED_PERMANENT = "FAILED_PERMANENT"


# Reasons that map to candidate exhaustion (WAITING, not a failure)
_WAITING_REASONS = {"no_topics", "no_topic", "quota_met"}
# Reasons that map to a permanent block
_PERMANENT_REASONS = {"duplicate_source_id", "duplicate_slug", "standard_violation"}


@dataclass
class PipelineResult:
    status: PipelineStatus
    pipeline: str = ""
    blog: str = ""
    stage: str = ""
    reason: str = ""
    pcode: str = ""
    retryable: bool = False
    publish_blocked: bool = False
    topic_id: Optional[int] = None
    source_id: Optional[str] = None
    artifact_path: Optional[str] = None
    evidence: str = ""
    # Carry-through for producer-specific keys (url, file_path, article_id,
    # deployed, deploy_error, ...). Preserved in to_legacy_dict() so no
    # downstream consumer loses data.
    extras: Dict[str, Any] = field(default_factory=dict)
    # Original legacy `success` value, kept separate from `status`. A
    # deploy-failure (success=True + deploy_error) is labeled FAILED_TRANSIENT
    # in the new contract while legacy `success` must stay True for scheduler
    # parity. None -> derived from status in to_legacy_dict().
    legacy_success: Optional[bool] = None

    def __post_init__(self) -> None:
        self.evidence = _sanitize_evidence(self.evidence)
        self._validate_combination()

    def _validate_combination(self) -> None:
        if self.status == PipelineStatus.SUCCESS and self.publish_blocked:
            raise ValueError("SUCCESS cannot have publish_blocked=True")
        if self.status == PipelineStatus.WAITING_FOR_CANDIDATES and self.retryable:
            raise ValueError("WAITING_FOR_CANDIDATES cannot be retryable")
        if self.status == PipelineStatus.FAILED_PERMANENT and self.retryable:
            raise ValueError("FAILED_PERMANENT cannot be retryable")
        if self.status == PipelineStatus.BLOCKED_QUALITY and not self.publish_blocked:
            raise ValueError("BLOCKED_QUALITY must have publish_blocked=True")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "pipeline": self.pipeline,
            "blog": self.blog,
            "stage": self.stage,
            "reason": self.reason,
            "pcode": self.pcode,
            "retryable": self.retryable,
            "publish_blocked": self.publish_blocked,
            "topic_id": self.topic_id,
            "source_id": self.source_id,
            "artifact_path": self.artifact_path,
            "evidence": self.evidence,
            "extras": self.extras,
            "legacy_success": self.legacy_success,
        }

    def to_legacy_dict(self, original_extras: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        if original_extras:
            out.update(original_extras)
        out.update(self.extras)
        out["success"] = (
            self.legacy_success
            if self.legacy_success is not None
            else (self.status == PipelineStatus.SUCCESS)
        )
        out["reason"] = self.reason
        out["pipeline_status"] = self.status.value
        return out


def _sanitize_evidence(value: Any) -> str:
    if not isinstance(value, str):
        value = str(value)
    value = _NEWLINE_RE.sub(" ", value)
    if _SECRET_RE.search(value):
        return "[redacted:evidence]"
    if len(value) > _EVIDENCE_MAX:
        value = value[:_EVIDENCE_MAX]
    return value


def _status_for_reason(reason: str) -> PipelineStatus:
    r = (reason or "").strip().lower()
    if r in _WAITING_REASONS:
        return PipelineStatus.WAITING_FOR_CANDIDATES
    if r in _PERMANENT_REASONS:
        return PipelineStatus.FAILED_PERMANENT
    return PipelineStatus.FAILED_TRANSIENT


def _derive_retryable(status: PipelineStatus) -> bool:
    return status == PipelineStatus.FAILED_TRANSIENT


def _safe_fallback(success: bool, reason: str) -> "PipelineResult":
    status = PipelineStatus.SUCCESS if success else PipelineStatus.FAILED_TRANSIENT
    return PipelineResult(
        status=status,
        reason=reason,
        retryable=_derive_retryable(status),
        publish_blocked=False,
        legacy_success=success,
    )


def from_legacy(raw: Any, ctx: Optional[Dict[str, Any]] = None) -> "PipelineResult":
    """Adapt a legacy pipeline return (dict/bool/str/None) to PipelineResult.

    Never raises into the caller. On any unexpected input it returns a safe
    fallback PipelineResult preserving whatever success/reason it could derive.
    """
    ctx = ctx or {}
    pipeline = ctx.get("pipeline", "") or ""
    blog = ctx.get("blog", "") or ""
    stage = ctx.get("stage", "") or ""

    success: Optional[bool] = None
    reason = ""
    extras: Dict[str, Any] = {}
    try:
        if raw is None:
            success = False
            reason = "no_result"
        elif isinstance(raw, bool):
            success = raw
            reason = "" if raw else "pipeline_returned_false"
        elif isinstance(raw, str):
            success = True
            reason = raw
        elif isinstance(raw, dict):
            extras = {k: v for k, v in raw.items() if k not in ("success", "reason")}
            if "success" in raw:
                success = bool(raw["success"])
            if raw.get("reason") is not None:
                reason = str(raw["reason"])
            if success is None:
                success = False
                if not reason:
                    reason = "unknown_return_type"
        else:
            return _safe_fallback(False, "unknown_return_type")
    except Exception:
        return _safe_fallback(False, "unknown_return_type")

    try:
        # Deploy-failure special case: producer returned success=True but a
        # deploy_error is present. Label FAILED_TRANSIENT for future routing
        # while keeping legacy_success=True so scheduler parity is preserved.
        deploy_failed = (
            isinstance(raw, dict)
            and bool(raw.get("success"))
            and bool(raw.get("deploy_error"))
        )
        if success and not deploy_failed:
            status = PipelineStatus.SUCCESS
        elif success and deploy_failed:
            status = PipelineStatus.FAILED_TRANSIENT
        else:
            status = _status_for_reason(reason)
        retryable = _derive_retryable(status)
        publish_blocked = (status == PipelineStatus.BLOCKED_QUALITY)
        return PipelineResult(
            status=status,
            pipeline=pipeline,
            blog=blog,
            stage=stage,
            reason=reason,
            retryable=retryable,
            publish_blocked=publish_blocked,
            legacy_success=success if success is not None else False,
            extras=extras,
        )
    except Exception:
        # Defensive: a forbidden combination or construction error must never
        # propagate into the dispatcher control flow.
        return _safe_fallback(success if success is not None else False, reason or "unknown_error")


def from_exception(exc: BaseException, ctx: Optional[Dict[str, Any]] = None) -> "PipelineResult":
    """Build a FAILED_TRANSIENT result from an uncaught exception.

    Provided for future use; PR-CAP-1 does NOT install a dispatcher exception
    boundary (that would change exit-code parity and belongs to PR-CAP-2+).
    """
    ctx = ctx or {}
    return PipelineResult(
        status=PipelineStatus.FAILED_TRANSIENT,
        pipeline=ctx.get("pipeline", "") or "",
        blog=ctx.get("blog", "") or "",
        stage=ctx.get("stage", "") or "",
        reason="exception:" + type(exc).__name__,
        retryable=True,
        publish_blocked=False,
    )

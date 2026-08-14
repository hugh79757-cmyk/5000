"""pipelines/etap/_contract.py — ETAP 실행 계약 정규화 헬퍼 (Phase 61, D-08).

ETAP topic pipeline들의 `run()` 반환을 표준 `run(cfg) -> dict` 계약으로 정규화한다.
모듈 계약만 통일하며 dispatcher의 기존 `dispatch()` 정규화(dispatcher.py L740 부근)는
대체하지 않는다. 파이프라인 생성 로직은 재작성하지 않고 반환 형태만 표준 dict로 바꾼다.

- Review #2 (flight 정규화): `{"status": ...}` dict(success 키 없음)를
  표준 `success`/`reason` 형태로 매핑한다 (PIPELINE-STANDARD §3.5).
- Review #3 (간접 bool 반환): `return result` 형태로 bool을 돌려주는 경우도
  `_normalize_result`가 처리한다. adapter 배선 시 간접 반환에 대해서도 이 헬퍼를 통과시킨다.
"""
import logging

logger = logging.getLogger(__name__)

# flight_pipeline run(cfg)의 status 값 → (reason, success) 매핑 (PIPELINE-STANDARD §3.5)
_STATUS_TO_STANDARD = {
    "ok": ("ok", True),
    "skip": ("no_topic", False),
    "error": ("generation_failed", False),
    "draft": ("content_quality_gate", False),
    "exhausted": ("daily_quota_reached", False),
    "build_fail": ("deploy_error", False),
}


def _normalize_result(result) -> dict:
    """bool/None/int/str/status-dict → 표준 success/reason dict로 정규화.

    - dict 이고 `success` 키가 있으면 그대로 반환 (이미 표준 계약).
    - dict 이고 `status` 키만 있으면 §3.5 매핑으로 success/reason 변환 (flight).
    - None → {"success": False, "reason": "no_result"}
    - bool → {"success": <bool>}
    - int/float → {"success": <value> > 0}
    - 그 외(str 등) → {"success": bool(result)}
    """
    if isinstance(result, dict):
        if "success" in result:
            return result
        status = result.get("status")
        if status in _STATUS_TO_STANDARD:
            reason, success = _STATUS_TO_STANDARD[status]
            out = dict(result)
            out["success"] = success
            out.setdefault("reason", reason)
            return out
        # 미지정 status → 성공 여부를 알 수 없으므로 보수적으로 실패 처리 + 원문 보존
        out = dict(result)
        out.setdefault("success", False)
        out.setdefault("reason", "unknown_status")
        return out
    if result is None:
        return {"success": False, "reason": "no_result"}
    if isinstance(result, bool):
        return {"success": result, "reason": "pipeline_returned_false" if not result else "pipeline_success"}
    if isinstance(result, (int, float)):
        return {"success": result > 0}
    return {"success": bool(result), "reason": str(result)}


__all__ = ["_normalize_result"]

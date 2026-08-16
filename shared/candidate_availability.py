"""Candidate availability contract — 발행 전 후보 소진 상태 판정 (PR3).

핵심: `pending=0 + source healthy`는 ERROR가 아니라 WAITING이다.
scheduler가 dispatcher를 호출하기 전에 이 모듈의 `check_availability()`로
실행 가능 여부를 판정하고, 후보가 없으면 dispatcher 실행 자체를 생략한다.

- car pipeline: car.db `topics` 테이블의 site_id(+post_type)별 pending count로 판정.
- 미지원 pipeline: state=unknown 반환 → 기존 실행 경로 유지 (후보 없음으로 단정 금지).
- checker 실패: 예외를 던지지 않고 checker_error state 반환 → 해당 blog 1회 skip
  (전체 scheduler 중단도, 무조건 실행하는 fail-open도 금지).
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from shared.db import get_db_path

SUPPORTED_PIPELINES: tuple[str, ...] = ("car",)

# car pipeline: config에 site_id가 없으므로 blog_id에서 유도 (기존 pipeline.py:101과 동일 규칙)
DEFAULT_SITE_ID_SUFFIX = "-hugo"

DEFAULT_CHECK_INTERVAL_MINUTES = 60  # 다음 검사 예정 시각 계산용


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _next_check_iso(minutes: int = DEFAULT_CHECK_INTERVAL_MINUTES) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()


def _site_id(blog_cfg: dict) -> str:
    """blog config에서 site_id 결정 — 명시된 값 우선, 없으면 blog_id에서 유도."""
    sid = (blog_cfg.get("site_id") or "").strip()
    if sid:
        return sid
    blog_id = (blog_cfg.get("id") or "").strip()
    if blog_id.endswith(DEFAULT_SITE_ID_SUFFIX):
        return blog_id[: -len(DEFAULT_SITE_ID_SUFFIX)]
    return blog_id


def _post_types(blog_cfg: dict) -> list[str]:
    """post_type 정규화 — string이면 [1개], list면 그대로, 없으면 []."""
    pt = blog_cfg.get("post_type")
    if isinstance(pt, list):
        return [str(x) for x in pt if str(x).strip()]
    if pt:
        return [str(pt)]
    return []


def _car_db_path(car_db_path: str | Path | None = None) -> Path:
    if car_db_path is not None:
        return Path(car_db_path)
    return Path(get_db_path("car"))


def _count_pending(conn: sqlite3.Connection, site_id: str, post_types: list[str]) -> int:
    """site_id(+post_type별) pending 토픽 수. post_types가 비면 site_id 전체 pending."""
    if post_types:
        placeholders = ",".join("?" for _ in post_types)
        row = conn.execute(
            f"SELECT COUNT(*) FROM topics WHERE site_id = ? "
            f"AND status = 'pending' AND post_type IN ({placeholders})",
            (site_id, *post_types),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT COUNT(*) FROM topics WHERE site_id = ? AND status = 'pending'",
            (site_id,),
        ).fetchone()
    return int(row[0]) if row else 0


def check_car_availability(blog_cfg: dict, car_db_path: str | Path | None = None) -> dict:
    """car pipeline 후보 가용성 판정 (읽기 전용, DB 쓰기 없음)."""
    blog_id = str(blog_cfg.get("id") or "")
    site_id = _site_id(blog_cfg)
    post_types = _post_types(blog_cfg)
    candidate_type = ",".join(post_types) if post_types else "*"
    try:
        conn = sqlite3.connect(f"file:{_car_db_path(car_db_path)}?mode=ro", uri=True, timeout=5)
        try:
            pending = _count_pending(conn, site_id, post_types)
        finally:
            conn.close()
    except Exception as e:
        # checker 자체 실패 — fail-open 금지. scheduler가 해당 blog 1회 skip하도록 신호.
        return {
            "state": "checker_error",
            "available_count": -1,
            "reason": f"car.db 조회 실패: {e}",
            "resource_id": "car.db",
            "candidate_type": candidate_type,
            "checked_at": _now_iso(),
            "next_check_at": _next_check_iso(),
            "source_health_state": "unknown",
            "linked_incident_key": "",
        }
    if pending > 0:
        return {
            "state": "healthy",
            "available_count": pending,
            "reason": "",
            "resource_id": "car.db",
            "candidate_type": candidate_type,
            "checked_at": _now_iso(),
            "next_check_at": _next_check_iso(),
            "source_health_state": "ok",
            "linked_incident_key": "",
        }
    return {
        "state": "waiting_for_candidates",
        "available_count": 0,
        "reason": "no_topics",
        "resource_id": "car.db",
        "candidate_type": candidate_type,
        "checked_at": _now_iso(),
        "next_check_at": _next_check_iso(),
        "source_health_state": "ok",
        "linked_incident_key": "",
    }


def check_availability(
    blog_cfg: dict,
    car_db_path: str | Path | None = None,
    source_health_state: str = "",
    linked_incident_key: str = "",
) -> dict:
    """실행 전 availability gate 인터페이스.

    반환: {
        state, available_count, reason, resource_id, candidate_type,
        checked_at, next_check_at, source_health_state, linked_incident_key
    }
    state: healthy / waiting_for_candidates / blocked_by_source /
           recovering / unknown / checker_error
    """
    blog_id = str(blog_cfg.get("id") or "")
    pipeline = str(blog_cfg.get("pipeline") or "")
    if pipeline not in SUPPORTED_PIPELINES:
        # 미지원 pipeline: 기존 실행 유지 (후보 없음으로 단정 금지)
        return {
            "state": "unknown",
            "available_count": -1,
            "reason": "unsupported_pipeline",
            "resource_id": "",
            "candidate_type": "",
            "checked_at": _now_iso(),
            "next_check_at": _next_check_iso(),
            "source_health_state": source_health_state or "",
            "linked_incident_key": linked_incident_key or "",
        }

    if pipeline == "car":
        info = check_car_availability(blog_cfg, car_db_path=car_db_path)
    else:  # SUPPORTED_PIPELINES 확장 대비
        info = {
            "state": "unknown",
            "available_count": -1,
            "reason": "unsupported_pipeline",
            "resource_id": "",
            "candidate_type": "",
            "checked_at": _now_iso(),
            "next_check_at": _next_check_iso(),
            "source_health_state": "",
            "linked_incident_key": "",
        }

    # root incident(P33 등) 연동: blocked_by_source 우선 반영
    if info["state"] == "waiting_for_candidates" and linked_incident_key:
        info["state"] = "blocked_by_source"
        info["reason"] = "source_refresh_stalled"
        info["linked_incident_key"] = linked_incident_key
    if source_health_state and info["state"] != "checker_error":
        info["source_health_state"] = source_health_state
    if linked_incident_key and info["state"] != "blocked_by_source":
        info["linked_incident_key"] = linked_incident_key
    return info


def is_blocked(info: dict) -> bool:
    """gate 판정 — True면 dispatcher 실행 생략."""
    return info.get("state") in (
        "waiting_for_candidates", "blocked_by_source", "checker_error",
    )
"""ops_dashboard.checks.disk_space — 데이터 볼륨 여유 공간 감시 (P34 사고 예방)

2026-09-08 사고: 데이터 볼륨 100% 만료로 Errno 28 파생 오류 다수
(ipo-hugo Hugo build 실패, sector-hugo failure_count.json 쓰기 실패,
travel-hugo DB I/O error → no_result, stock-hugo disk I/O).
디스크는 모든 파이프라인의 선행 조건이므로 fleet 대표 1건으로 보고.
"""
from __future__ import annotations

import shutil

from ops_dashboard.checks import register_check

# 체커는 (conn, blog_id) 시그니처 → 파일시스템 상태는 blog 무관.
# 전 블로그에 같은 결과가 94번 기록되는 것을 피하기 위해 대표 1개만 실행.
FLEET_SENTINEL = "travel-hugo"
WARN_GB = 10.0  # 이 미만 시 fail — Errno 28 직전 방어선


@register_check("disk_space")
def check_disk_space(conn, blog_id: str) -> dict:
    if blog_id != FLEET_SENTINEL:
        return {"status": "pass", "detail": "skip (fleet sentinel에서만 검사)"}
    try:
        usage = shutil.disk_usage(__file__)
        free_gb = usage.free / (1024**3)
        if free_gb < WARN_GB:
            return {
                "status": "fail",
                "detail": f"디스크 여유 {free_gb:.1f}GB (< {WARN_GB:.0f}GB) — Errno 28 직전. 백업(.bak) 정리 필요.",
            }
        return {"status": "pass", "detail": f"디스크 여유 {free_gb:.1f}GB"}
    except Exception as e:
        return {"status": "unknown", "detail": f"disk check error: {e}"}

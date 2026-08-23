"""ops_dashboard.views.schema_view — 분기별 표준화 스키마 뷰 컨텍스트 빌더.

라우트(app.py)는 여기서 반환한 dict를 템플릿에 넘기기만 한다.
"""
from ops_dashboard.schema_registry import (
    classify_standardization,
    get_branch_summary,
    get_schema,
)


def render_schema_summary() -> dict:
    """전체 요약 + 분기별 목록 + 블로그 상태 테이블 컨텍스트."""
    cls = classify_standardization()
    s = cls["summary"]
    by_branch: dict[str, list] = {}
    for r in cls["blogs"]:
        by_branch.setdefault(r["branch"], []).append(r)

    branch_rows = []
    for b in get_branch_summary():
        rows = by_branch.get(b["branch"], [])
        branch_rows.append({
            "branch": b["branch"],
            "total": b["total"],
            "ok": sum(1 for r in rows if r["state"] == "ok"),
            "attention": sum(1 for r in rows if r["state"] == "attention"),
            "inactive": sum(1 for r in rows if r["state"] == "inactive"),
            "with_ga4": b["with_ga4"],
            "build_pass": b["build_pass"],
            "last_synced_at": b["last_synced_at"],
        })

    return {
        "summary": s,
        "branches": branch_rows,
        "blogs": cls["blogs"],
    }


def render_schema_detail(blog_id: str) -> dict | None:
    """개별 블로그 스키마 상세 (registry 행 + 분류 사유)."""
    row = get_schema(None, blog_id)
    if not row:
        return None
    cls = classify_standardization()
    mine = next((b for b in cls["blogs"] if b["blog_id"] == blog_id), None)
    return {"row": row, "state": (mine or {}).get("state", "unknown"),
            "reasons": (mine or {}).get("reasons", [])}

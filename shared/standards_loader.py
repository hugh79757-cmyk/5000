"""Phase 71 (SC-3): 통일 표준 로더.

config/quality_checklist.yaml 의 ``global_standard`` + ``brand_standards`` 와
blogs.d/*.yaml 의 brand 메타를 합쳐, blog_id → 적용 표준 집합 + 각 표준↔rule
1:1 + ``agent_action`` 맵을 반환한다.

소비처:
  - ops_dashboard/app.py ``standards()`` 뷰 (표준 노출)
  - Wave 5 자동수정 디스패처 (agent_action → fixer 키)

설계 원칙:
  - additive / non-destructive — 기존 검사 로직 미변경.
  - 라이브 서버/DB 의존 없음 (순수 YAML 파싱).
  - brand 는 blogs.d/<brand>.yaml 파일명에서 유추 (dispatcher._detect_brand 와 동일).
  - OQ#1 (세부 서브세그먼트 기준) 는 시니어 결정 대기 → brand 레벨만 매핑.
"""

from __future__ import annotations

import yaml
from pathlib import Path

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
QC_PATH = CONFIG_DIR / "quality_checklist.yaml"
BLOGS_D = CONFIG_DIR / "blogs.d"


def _load_qc() -> dict:
    if not QC_PATH.exists():
        return {}
    try:
        with open(QC_PATH, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def _detect_brand(blog_id: str) -> str | None:
    """blogs.d/<brand>.yaml 파일명에서 brand 유추 (dispatcher._detect_brand 동일)."""
    if not BLOGS_D.exists():
        return None
    for p in sorted(BLOGS_D.glob("*.yaml")):
        if p.name.endswith(".bak") or p.name.endswith(".bak2"):
            continue
        try:
            data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        for entry in data.get("blogs", []) or []:
            if isinstance(entry, dict) and entry.get("id") == blog_id:
                return p.stem
    return None


def get_applicable_standards(blog_id: str) -> dict:
    """blog_id 에 적용되는 통일 표준 집합 반환.

    반환 형태::

        {
          "blog_id": str,
          "brand": str,            # 매칭된 brand (없으면 "default")
          "rules": [               # global_standard + brand_standards 병합
            {
              "id": str,
              "target": str,
              "severity": str,
              "description": str,
              "agent_action": str | None,   # 항상 키 존재 (Wave5 fixer 참조)
            }, ...
          ],
          "global_count": int,
          "brand_count": int,
        }
    """
    qc = _load_qc()
    global_std = qc.get("global_standard", []) or []
    brand = _detect_brand(blog_id) or "default"
    brand_std = (qc.get("brand_standards", {}) or {}).get(brand, []) or []

    rules: list[dict] = []
    for item in list(global_std) + list(brand_std):
        if not isinstance(item, dict):
            continue
        rules.append(
            {
                "id": item.get("id"),
                "target": item.get("target", ""),
                "severity": item.get("severity", "MAJOR"),
                "description": item.get("description", ""),
                # 항상 키 존재하도록 보장 (값은 None 가능)
                "agent_action": item.get("agent_action", None),
            }
        )

    return {
        "blog_id": blog_id,
        "brand": brand,
        "rules": rules,
        "global_count": len(global_std),
        "brand_count": len(brand_std),
    }


def get_brand_standards_summary() -> dict:
    """브랜드별 표준 항목 수 집계 (standards() 뷰용)."""
    qc = _load_qc()
    brand_std = qc.get("brand_standards", {}) or {}
    return {brand: len(items or []) for brand, items in brand_std.items()}


def get_global_standard() -> list:
    """전체공통 표준 항목 리스트 (standards() 뷰용)."""
    qc = _load_qc()
    return qc.get("global_standard", []) or []

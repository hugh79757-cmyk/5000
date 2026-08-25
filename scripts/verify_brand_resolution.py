"""Phase 71 Wave 2 — R3 브랜드 해석 검증 스크립트 (run-only, side-effect 없음).

config/blogs.d/*.yaml 에 선언된 모든 블로그의 브랜드 해석 결과를 출력하고,
CAP 블로그가 brand 'cap' 으로 해석되는지 선택적으로 검증한다.

사용법:
    python scripts/verify_brand_resolution.py            # 출력만
    python scripts/verify_brand_resolution.py --assert-cap  # CAP 검증 + 실패 시 exit 1
"""

from __future__ import annotations

import argparse
import sys
import yaml
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.standards_loader import (  # noqa: E402
    BLOGS_D,
    get_applicable_standards,
)


def _is_backup(name: str) -> bool:
    return name.endswith(".bak") or name.endswith(".bak2")


def _collect_blog_ids() -> list[str]:
    """config/blogs.d/*.yaml (*.bak 제외) 에서 블로그 id 전체 수집."""
    ids: list[str] = []
    if not BLOGS_D.exists():
        return ids
    for p in sorted(BLOGS_D.glob("*.yaml")):
        if _is_backup(p.name):
            continue
        try:
            data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        for entry in data.get("blogs", []) or []:
            if isinstance(entry, dict) and entry.get("id"):
                ids.append(entry["id"])
    return ids


def _cap_blog_ids() -> set[str]:
    """cap.yaml 에 선언된 블로그 id 집합."""
    cap_path = BLOGS_D / "cap.yaml"
    if not cap_path.exists():
        return set()
    try:
        data = yaml.safe_load(cap_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return set()
    return {
        e["id"] for e in (data.get("blogs", []) or []) if isinstance(e, dict) and e.get("id")
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify brand resolution for all blogs.")
    parser.add_argument(
        "--assert-cap",
        action="store_true",
        help="Assert CAP blogs resolve to brand 'cap'; exit non-zero on failure.",
    )
    args = parser.parse_args()

    blog_ids = _collect_blog_ids()
    cap_ids = _cap_blog_ids()

    print(f"=== Brand resolution verification ===")
    print(f"Total blog ids found (blogs.d, non-bak): {len(blog_ids)}")
    print(f"CAP blog ids (cap.yaml): {len(cap_ids)}")
    print()

    results = []
    cap_failures = []
    defaults = []
    for bid in blog_ids:
        r = get_applicable_standards(bid)
        brand = r["brand"]
        rule_count = len(r["rules"])
        results.append((bid, brand, rule_count))
        if brand == "default":
            defaults.append(bid)
        if bid in cap_ids and brand != "cap":
            cap_failures.append((bid, brand))

    # per-blog table
    print(f"{'blog_id':<45} {'brand':<22} {'rules':<6}")
    print("-" * 75)
    for bid, brand, rule_count in results:
        print(f"{bid:<45} {brand:<22} {rule_count:<6}")

    print()
    print(f"=== blogs resolved to brand 'default' ({len(defaults)}) ===")
    if defaults:
        for d in defaults:
            print(f"  - {d}")
    else:
        print("  (none)")

    if args.assert_cap:
        print()
        print(f"=== CAP assertion ===")
        if cap_failures:
            print(f"FAIL: {len(cap_failures)} CAP blog(s) did not resolve to 'cap':")
            for bid, brand in cap_failures:
                print(f"  - {bid} -> {brand}")
            return 1
        print(f"PASS: all {len(cap_ids)} CAP blogs resolve to brand 'cap'.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""ops_dashboard.investigate_publish — 발행/배포 중단 원인 규명

publish_ledger를 pre-refactor-baseline 커밋 시각과 대조하여,
각 블로그의 발행 중단 원인을 (a)원래문제 (b)시도중단 (c)배포유실 (d)리팩토링회귀로 판별한다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from ops_dashboard.db import (
    get_publish_log_conn,
    get_publish_ledger_blog_ids,
    get_publish_ledger_total,
    get_publish_ledger_last_success,
    get_publish_ledger_counts_since,
    get_publish_ledger_fail_count,
    get_publish_ledger_fail_reasons,
    get_conn,
    get_all_blogs,
)

# pre-refactor-baseline 커밋 시각 (2026-08-06 10:33:52 +0700)
REFACTOR_CUTOVER = "2026-08-06T10:33:52"
REFACTOR_DATE = "2026-08-01"  # 8/1 이후 데이터 분석 기준

PROJECT_ROOT = Path(__file__).parent.parent
OPS_DB_PATH = Path(__file__).parent / "ops.db"


def _classify_blog(conn, blog_id: str) -> dict:
    """단일 블로그의 발행 중단 원인을 판별."""
    # 전체 발행 이력
    total = get_publish_ledger_total(conn, blog_id)

    # 마지막 성공 발행
    last_pub = get_publish_ledger_last_success(conn, blog_id)

    # 8/1 이후 데이터
    counts = get_publish_ledger_counts_since(conn, blog_id, REFACTOR_DATE)
    pub_after = counts["pub"]
    fail_after = counts["fail"]

    # 리팩토링 이후 실패 (cutover 이후)
    fail_after_refactor = get_publish_ledger_fail_count(conn, blog_id, REFACTOR_CUTOVER)

    # 리팩토링 이전 실패 (cutover 이전, 8/1 이후)
    fail_before_refactor = get_publish_ledger_fail_count(
        conn, blog_id, REFACTOR_DATE, REFACTOR_CUTOVER
    )

    # 실패 사유 분포 (8/1 이후)
    fail_reasons = get_publish_ledger_fail_reasons(conn, blog_id, REFACTOR_DATE)

    # 판정 로직
    if last_pub is None:
        # 성공 발행 기록 자체가 없음
        if fail_after > 0:
            # 실패만 있고 성공 없음 → 발행 시도 중단 (아니면 첫 시도부터 실패)
            cause = "b"
            reason = "성공 발행 0건, 실패만 존재 (파이프라인 자체 미가동 또는 첫 시도부터 실패)"
        else:
            cause = "b"
            reason = "publish_ledger 데이터 없음 (파이프라인 미연동)"
    elif last_pub < REFACTOR_DATE:
        # 마지막 성공이 8/1 이전
        if fail_after > 0:
            cause = "a"
            reason = f"마지막 성공 {last_pub[:10]}, 이후 시도 {fail_after}건 실패 (차단 반복)"
        else:
            cause = "b"
            reason = f"마지막 성공 {last_pub[:10]}, 8/1 이후 시도 0건 (발행 시도 중단)"
    elif last_pub >= REFACTOR_DATE and last_pub < REFACTOR_CUTOVER:
        # 마지막 성공이 8/1~리팩토링 사이
        if fail_after_refactor > 0 and pub_after == 0:
            cause = "d"
            reason = f"마지막 성공 {last_pub[:10]} (리팩토링 전), 리팩토링 후 시도 {fail_after_refactor}건 실패 (리팩토링 회귀)"
        elif fail_after_refactor > 0:
            cause = "a"
            reason = f"마지막 성공 {last_pub[:10]}, 리팩토링 후에도 성공 {pub_after}건 있으나 실패 {fail_after_refactor}건 (차단 반복)"
        elif pub_after > 0:
            cause = "ok"
            reason = f"리팩토링 후 성공 {pub_after}건 발행 중 (정상)"
        else:
            cause = "b"
            reason = f"마지막 성공 {last_pub[:10]}, 리팩토링 후 시도 0건 (발행 시도 중단)"
    elif last_pub >= REFACTOR_CUTOVER:
        # 마지막 성공이 리팩토링 이후
        if fail_after_refactor > 0:
            cause = "a"
            reason = f"리팩토링 후 마지막 성공 {last_pub[:10]}, 실패 {fail_after_refactor}건 (차단 반복)"
        else:
            cause = "ok"
            reason = f"리팩토링 후 마지막 성공 {last_pub[:10]}, 실패 0건 (정상)"
    else:
        cause = "?"
        reason = f"last_pub={last_pub}, 판정 불가"

    return {
        "blog_id": blog_id,
        "total_records": total,
        "last_publish": last_pub,
        "pub_after_8_1": pub_after,
        "fail_after_8_1": fail_after,
        "fail_after_refactor": fail_after_refactor,
        "fail_before_refactor": fail_before_refactor,
        "cause": cause,
        "reason": reason,
        "top_fail_reasons": fail_reasons[:3],
    }


def investigate_all() -> list[dict]:
    """전 블로그 조사."""
    conn = get_publish_log_conn()
    ops_conn = get_conn()

    # publish_ledger에 있는 모든 블로그
    blog_ids = get_publish_ledger_blog_ids(conn)

    # blog_lifecycle에 있는 블로그도 포함 (ledger에 없을 수 있음)
    lifecycle_blogs = [b["blog_id"] for b in get_all_blogs(ops_conn)]

    all_blogs = sorted(set(blog_ids + lifecycle_blogs))

    results = []
    for bid in all_blogs:
        result = _classify_blog(conn, bid)
        results.append(result)

    conn.close()
    ops_conn.close()
    return results


def print_report(results: list[dict]) -> None:
    """판정표 출력."""
    CAUSE_LABELS = {
        "ok": "정상",
        "a": "(a) 차단 반복",
        "b": "(b) 발행 시도 중단",
        "c": "(c) 배포 유실",
        "d": "(d) 리팩토링 회귀",
        "?": "미판별",
    }

    print("=" * 100)
    print("Part 1: 발행/배포 중단 원인 판정표")
    print(f"리팩토링 컷오버: {REFACTOR_CUTOVER}")
    print("=" * 100)

    print(f"\n{'blog_id':<25} {'원인':<5} {'last_publish':<12} {'pub_8/1':>7} {'fail_8/1':>8} {'fail_ref':>8} {'상세'}")
    print("-" * 120)

    # 원인별 집계
    cause_counts = {}
    for r in results:
        cause = r["cause"]
        cause_counts[cause] = cause_counts.get(cause, 0) + 1

    for r in sorted(results, key=lambda x: (x["cause"], x["blog_id"])):
        cause_label = CAUSE_LABELS.get(r["cause"], r["cause"])
        last_pub = r["last_publish"][:10] if r["last_publish"] else "없음"
        print(
            f'{r["blog_id"]:<25} {r["cause"]:<5} {last_pub:<12} '
            f'{r["pub_after_8_1"]:>7} {r["fail_after_8_1"]:>8} '
            f'{r["fail_after_refactor"]:>8}  {r["reason"][:50]}'
        )

    print("\n" + "=" * 100)
    print("원인별 집계:")
    for cause, label in sorted(CAUSE_LABELS.items()):
        count = cause_counts.get(cause, 0)
        if count > 0:
            print(f"  {label}: {count}개 블로그")
    print(f"  전체: {len(results)}개 블로그")

    # 주요 문제 블로그 상세
    problem_blogs = [r for r in results if r["cause"] in ("a", "b", "d")]
    if problem_blogs:
        print(f"\n{'=' * 100}")
        print(f"문제 블로그 상세 ({len(problem_blogs)}개):")
        print("-" * 100)
        for r in problem_blogs:
            print(f"\n  [{r['cause']}] {r['blog_id']}:")
            print(f"    원인: {r['reason']}")
            if r["top_fail_reasons"]:
                print(f"    주요 실패: {', '.join(f'{s}({c}건)' for s, c in r['top_fail_reasons'])}")


def main() -> None:
    results = investigate_all()
    print_report(results)

    # JSON 저장
    output_path = Path(__file__).parent / "investigate_publish_result.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n결과 저장: {output_path}")


if __name__ == "__main__":
    main()

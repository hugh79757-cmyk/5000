"""CUAP 비교표 품질 체크 — 컬럼 수 + 빈값 비율 측정

15 CUAP blogs (config/blogs.d/cuap.yaml) content/posts/*.md 스캔.
측정: column_count, empty_cell_ratio, has_dash_cells
판정: column_count <=5 PASS, >5 WARNING | empty_ratio >0.3 WARNING
"""
import os
import glob
import re
from pathlib import Path

CUAP_BLOGS = [
    "appliance-hugo", "baby-hugo", "beauty-hugo", "bike-hugo", "camping-hugo",
    "car-hugo", "fitness-hugo", "golf-hugo", "health-hugo", "homeappliance-hugo",
    "interior-hugo", "kitchen-hugo", "laptop-hugo", "massage-hugo", "pet-hugo",
]
CONTENT_BASE = Path("/Users/twinssn/Projects/cuap")
WARN_COLUMNS = 5
WARN_EMPTY_RATIO = 0.30


def parse_table_from_md(filepath):
    """마크다운 파일에서 첫 번째 표의 컬럼 수와 빈값 비율 반환. 표 없으면 None."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception:
        return None
    table_rows = [l for l in lines if l.strip().startswith("|")]
    if len(table_rows) < 3:
        return None
    # header 파싱 — split "|", 양끝 빈값 제거
    def split_row(row):
        parts = row.strip().strip("|").split("|")
        return [c.strip() for c in parts]
    header = split_row(table_rows[0])
    # separator 행은 --- 포함, skip
    sep = table_rows[1]
    if not re.search(r"[-:]{2,}", sep):
        # separator 아니면 데이터 행으로 취급 — header+separator 2줄 필요하므로 표 아님
        return None
    col_count = len(header)
    if col_count == 0:
        return None
    data_rows = table_rows[2:]
    total_cells = 0
    empty_cells = 0
    dash_cells = 0
    for row in data_rows:
        cells = split_row(row)
        # col_count에 맞춰 패딩/트림 — 빈 셀 정확 계산
        if len(cells) < col_count:
            cells += [""] * (col_count - len(cells))
        cells = cells[:col_count]
        for cell in cells:
            total_cells += 1
            if cell in ("-", "—", "–", ""):
                empty_cells += 1
                if cell in ("-", "—", "–"):
                    dash_cells += 1
            elif cell.strip() == "":
                empty_cells += 1
    empty_ratio = empty_cells / max(total_cells, 1)
    return {
        "col_count": col_count,
        "empty_ratio": round(empty_ratio, 3),
        "rows": len(data_rows),
        "dash_cells": dash_cells,
        "total_cells": total_cells,
    }


def run_check(sample_per_blog=5):
    """CUAP 블로그별 최근 N개 md 스캔 → check_results_custom 호환 dict 목록 반환 + CLI용 상세."""
    results = []
    for blog in CUAP_BLOGS:
        blog_posts = CONTENT_BASE / blog / "content" / "posts"
        blog_content = CONTENT_BASE / blog / "content"
        search_base = blog_posts if blog_posts.is_dir() else blog_content
        if not search_base.is_dir():
            results.append({
                "check_name": "TABLE_QUALITY",
                "blog_id": blog,
                "result": "unknown",
                "detail": "path not found",
            })
            continue
        md_files = sorted(
            glob.glob(str(search_base / "**" / "*.md"), recursive=True),
            key=lambda p: os.path.getmtime(p),
            reverse=True,
        )[:sample_per_blog]
        if not md_files:
            results.append({
                "check_name": "TABLE_QUALITY",
                "blog_id": blog,
                "result": "unknown",
                "detail": "no md files",
            })
            continue
        for md in md_files:
            info = parse_table_from_md(md)
            if not info:
                continue
            status = "pass"
            reasons = []
            if info["col_count"] > WARN_COLUMNS:
                status = "warning"
                reasons.append(f"cols={info['col_count']}>{WARN_COLUMNS}")
            if info["empty_ratio"] > WARN_EMPTY_RATIO:
                status = "warning"
                reasons.append(f"empty={info['empty_ratio']:.0%} >30%")
            detail = f"cols={info['col_count']} rows={info['rows']} empty={info['empty_ratio']:.0%} dash={info['dash_cells']} file={os.path.basename(md)}"
            if reasons:
                detail += " WARN:" + ",".join(reasons)
            # 상세 필드도 함께 반환 (대시보드 API에서 활용)
            results.append({
                "check_name": "TABLE_QUALITY",
                "blog_id": blog,
                "result": status,
                "detail": detail,
                "file": os.path.basename(md),
                "col_count": info["col_count"],
                "empty_ratio": info["empty_ratio"],
                "rows": info["rows"],
                "dash_cells": info["dash_cells"],
                "_status": status,
            })
        # 표가 하나도 없던 블로그는 unknown 대신 pass로 처리하지 않고 스킵 기록 없음
        # (기존 동작 유지 — 표 없는 글은 품질 이슈 아님)
    return results


def run_check_cli():
    """CLI 출력용 — 기존 run_check 래핑."""
    results = run_check()
    # unknown/path-not-found 제외한 파일 단위 결과
    file_results = [r for r in results if "file" in r]
    warn = [r for r in file_results if r["result"] == "warning"]
    passed = [r for r in file_results if r["result"] == "pass"]
    skip = [r for r in results if r["result"] == "unknown"]
    print(f"{'Blog':<20} {'File':<45} {'Cols':<5} {'Empty%':<8} {'Status'}")
    print("-" * 105)
    for r in file_results:
        print(f"{r['blog_id']:<20} {r['file']:<45} {r['col_count']:<5} {r['empty_ratio']*100:<8.1f} {r['result'].upper()}")
        if r["result"] == "warning":
            print(f"  -> {r['detail']}")
    for r in skip:
        print(f"{r['blog_id']:<20} {'—':<45} {'—':<5} {'—':<8} UNKNOWN: {r['detail']}")
    print(f"\nTotal file checks: {len(file_results)} | WARNING: {len(warn)} | PASS: {len(passed)} | SKIP blogs: {len(skip)}")
    return results


if __name__ == "__main__":
    run_check_cli()

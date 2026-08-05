#!/usr/bin/env python3
"""scan_keyword_relevance.py — curation low_relevance 게이트 재현 스캐너 + 위험 키워드 A/B0/B1/C 분류

kw_scan_pipeline.json 의 위험 셋 601행(고유쌍 589 + 중복 12행)을 재현하는 읽기 전용 스캐너.

재현 로직 (pipeline.py:976-1047 게이트 시맨틱 그대로):
  1. KEYWORD_MAP 전 블로그 키워드를 블로그별 **고유 1회** 평가 (중복 토큰은 1회 평가)
  2. products (data/curation.db) 전수 조회 — 스캔 JSON 증거: '걸레' count=23 (limit 10이 아님)
  3. score_products() -> avg / get_adaptive_threshold()(=base, 전 블로그 동일 확인) -> 개별 drop(미달 제거, >=3 남으면 재평균) -> passes_gate(avg >= threshold)
  4. 게이트 실패 = RISK -> [keyword, avg, below_frac, count] (kw_scan_pipeline.json 튜플 형태와 동일)

분류 (고유쌍 기준):
  A_FOREIGN : 한자/가나/키릴 포함 (re.search) -> 자동 제거
  on-ratio  : top-8 상품 (id DESC) 중 allowed substring 포함 비율
  B0_OFFTOPIC : on_ratio == 0.0 AND 키워드에 allowed 미포함 -> 자동 제거
  B1_REVIEW   : 0 < on_ratio < 0.5 OR (on_ratio == 0.0 AND 키워드에 allowed 포함) -> 샘플 검토 대상
  C_ONTOPIC_WATCH : on_ratio >= 0.5 -> 유지

충실도 게이트 (변경 전 HARD): 고유 위험 (blog, keyword) 쌍 == kw_scan_pipeline.json 고유 위험 쌍 589건.
주의: Task 3 재스캔(제거 후)에서는 고유 쌍이 261 이하로 줄어 충실도 비교는 정보성 출력만 (--fidelity-hard 가 아니면 exit 0).

Production 코드(pipeline.py / relevance_scorer.py / keywords.py / curation.db) 무수정 — SELECT 전용 읽기 전용.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

DB_PATH = REPO_ROOT / "data/curation.db"
TASK_DIR = REPO_ROOT / ".planning/quick/260805-n1j-keyword-map-low-relevance-601"
REF_JSON = TASK_DIR / "kw_scan_pipeline.json"
OUT_JSON = TASK_DIR / "kw_risk_classified.json"
KEYWORDS_PY = REPO_ROOT / "pipelines/curation/keywords.py"

from shared.relevance_scorer import (  # noqa: E402
    score_product,
    score_products,
    get_adaptive_threshold,
    passes_gate,
)
from pipelines.curation.keywords import KEYWORD_MAP  # noqa: E402
from pipelines.curation.pipeline import CATEGORY_FILTERS  # noqa: E402

# 한자 / 가나(히라가나·가타카나) / 키릴 — 외국어 혼합 키워드
A_FOREIGN_RE = re.compile(r"[\u4e00-\u9fff\u3040-\u30ff\u0400-\u04ff]")


def fetch_products(conn: sqlite3.Connection, keyword: str) -> list[dict]:
    """products 테이블 전수 조회 (id DESC) — 스캔 JSON count와 일치하려면 limit 없음."""
    rows = conn.execute(
        "SELECT product_name, category_name FROM products WHERE keyword=? ORDER BY id DESC",
        (keyword,),
    ).fetchall()
    return [{"product_name": r[0], "category_name": r[1]} for r in rows]


def evaluate_keyword(conn: sqlite3.Connection, blog_id: str, keyword: str) -> dict:
    """pipeline.py:976-1047 게이트 시맨틱 재현.

    Returns: dict(avg, threshold, count, below_frac, scores, products)
    - threshold: get_adaptive_threshold (전 블로그 base 그대로 확인됨)
    - 개별 drop: score < threshold 제거, >=3 남으면 재평균 (avg/min 갱신)
    - below_frac: 최종 점수 셋에서 threshold 미달 비율 (kw_scan_pipeline.json의 threshold 컬럼)
    """
    products = fetch_products(conn, keyword)
    scores = score_products(products, blog_id)
    threshold = get_adaptive_threshold(str(DB_PATH), blog_id, scores["threshold"])
    final_scores = scores["scores"]
    if final_scores:
        dropped = [s for s in final_scores if s < threshold]
        passed = [s for s in final_scores if s >= threshold]
        if dropped and len(passed) >= 3:
            final_scores = passed
            scores["avg"] = sum(final_scores) / len(final_scores)
            scores["min"] = min(final_scores)
    below_frac = (
        sum(1 for s in final_scores if s < threshold) / len(final_scores)
        if final_scores
        else 0.0
    )
    return {
        "avg": scores["avg"],
        "threshold": threshold,
        "count": len(products),
        "below_frac": below_frac,
        "scores": final_scores,
        "products": products,
    }


def on_ratio(blog_id: str, products: list[dict]) -> float:
    """top-8 상품 (id DESC 첫 8개) 중 allowed substring 매치 비율."""
    allowed = CATEGORY_FILTERS[blog_id]["allowed"]
    top8 = products[:8]
    if not top8:
        return 0.0
    hits = 0
    for p in top8:
        text = (p["product_name"] + " " + p["category_name"]).lower()
        if any(aw.lower() in text for aw in allowed):
            hits += 1
    return hits / len(top8)


def keyword_has_allowed(blog_id: str, keyword: str) -> bool:
    """키워드 문자열 자체에 allowed substring 포함 여부."""
    allowed = CATEGORY_FILTERS[blog_id]["allowed"]
    k = keyword.lower()
    return any(aw.lower() in k for aw in allowed)


def classify(bucket_a: bool, on_ratio_val: float, has_allowed: bool) -> str:
    if bucket_a:
        return "A"
    if on_ratio_val == 0.0 and not has_allowed:
        return "B0"
    if 0 < on_ratio_val < 0.5 or (on_ratio_val == 0.0 and has_allowed):
        return "B1"
    if on_ratio_val >= 0.5:
        return "C"
    return "?"  # 도달 불가 — 방어용


def scan_keyword_relevance(blog_id: str | None = None) -> dict:
    """모든 블로그(또는 blog_id 1개)의 고유 키워드 게이트 재현 스캔.

    Returns: dict(per_blog, results, duplicates, risk_pairs, totals)
    - per_blog: {blog: {kw: {avg, threshold, count, below_frac, on_ratio, bucket, sample}}}
    """
    conn = sqlite3.connect(str(DB_PATH))
    blogs = [blog_id] if blog_id else list(KEYWORD_MAP)
    results: dict[str, dict] = {}
    risk_pairs: set[tuple[str, str]] = set()
    occurrences: dict[str, dict] = {}  # blog -> {kw: occurrence_count}

    for blog in blogs:
        kws = KEYWORD_MAP[blog]
        occ = Counter(kws)
        occurrences[blog] = dict(occ)
        blog_res: dict[str, dict] = {}
        for kw in occ:  # 고유 키워드 1회 평가
            ev = evaluate_keyword(conn, blog, kw)
            passed, _reason = passes_gate(
                {"avg": ev["avg"], "threshold": ev["threshold"]}
            )
            bucket = None
            on_ratio_val = None
            if not passed:
                on_ratio_val = on_ratio(blog, ev["products"])
                bucket = classify(
                    bool(A_FOREIGN_RE.search(kw)),
                    on_ratio_val,
                    keyword_has_allowed(blog, kw),
                )
                risk_pairs.add((blog, kw))
            blog_res[kw] = {
                "avg": round(ev["avg"], 2),
                "threshold": round(ev["below_frac"], 2),
                "count": ev["count"],
                "on_ratio": round(on_ratio_val, 2) if on_ratio_val is not None else None,
                "bucket": bucket,
                "sample": [p["product_name"] for p in ev["products"][:8]],
            }
        results[blog] = blog_res
    conn.close()

    totals = Counter(r["bucket"] for res in results.values() for r in res.values() if r["bucket"])
    # 중복 12행: 위험 키워드 중 블록 내 2회 이상 정의된 (blog, keyword, occurrence_count)
    duplicates = sorted(
        [blog, kw, occurrences[blog][kw]]
        for blog in blogs
        for kw in results[blog]
        if results[blog][kw]["bucket"] is not None and occurrences[blog][kw] >= 2
    )
    return {
        "per_blog": results,
        "occurrences": occurrences,
        "duplicates": duplicates,
        "risk_pairs": risk_pairs,
        "totals": {
            "A": totals.get("A", 0),
            "B0": totals.get("B0", 0),
            "B1": totals.get("B1", 0),
            "C": totals.get("C", 0),
            "risk_unique": len(risk_pairs),
        },
    }


def load_reference_risk_set() -> dict:
    """kw_scan_pipeline.json 고유 위험 쌍 + 중복 행 목록."""
    with open(REF_JSON, encoding="utf-8") as f:
        ref = json.load(f)
    pairs: set[tuple[str, str]] = set()
    raw: list[tuple[str, str]] = []
    for blog, v in ref.items():
        for row in v.get("risk", []):
            raw.append((blog, row[0]))
            pairs.add((blog, row[0]))
    dup_rows = sorted(
        [[b, kw, cnt] for (b, kw), cnt in Counter(raw).items() if cnt >= 2]
    )
    return {"pairs": pairs, "raw_count": len(raw), "dup_rows": dup_rows}


def build_classified_json(scan: dict) -> dict:
    """kw_risk_classified.json 구조: {blog: {A/B0/B1/C: [[...]], ...}} + totals + duplicates."""
    out: dict = {}
    for blog, res in scan["per_blog"].items():
        buckets: dict[str, list] = {"A": [], "B0": [], "B1": [], "C": []}
        for kw, r in res.items():
            bucket = r["bucket"]
            if bucket is None:
                continue
            if bucket == "B1":
                buckets["B1"].append([kw, r["avg"], r["on_ratio"], r["sample"]])
            else:
                buckets[bucket].append([kw, r["avg"], r["threshold"], r["count"]])
        out[blog] = {k: sorted(v) for k, v in buckets.items()}
    out["totals"] = scan["totals"]
    out["duplicates"] = scan["duplicates"]
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blog", default=None, help="특정 blog_id만 스캔")
    parser.add_argument("--out", default=str(OUT_JSON), help="kw_risk_classified.json 경로")
    parser.add_argument(
        "--fidelity-hard",
        action="store_true",
        help="충실도 게이트 실패 시 exit 1 (변경 전 검증용)",
    )
    args = parser.parse_args(argv)

    scan = scan_keyword_relevance(args.blog)
    res = scan["per_blog"]
    totals = scan["totals"]

    # ── 콘솔 요약 ──
    print(f"TOTAL KEYWORDS: {sum(len(v) for v in KEYWORD_MAP.values())}")
    for blog in res:
        n_risk = sum(1 for r in res[blog].values() if r["bucket"])
        n_risk_raw = sum(
            scan["occurrences"][blog][kw]
            for kw, r in res[blog].items()
            if r["bucket"] is not None
        )
        bc = Counter(r["bucket"] for r in res[blog].values() if r["bucket"])
        print(
            f"{blog}: total={len(KEYWORD_MAP[blog])} unique={len(res[blog])} "
            f"risk={n_risk} risk_raw={n_risk_raw} "
            f"A={bc.get('A',0)} B0={bc.get('B0',0)} B1={bc.get('B1',0)} C={bc.get('C',0)}"
        )
    print(
        f"RISK UNIQUE: {totals['risk_unique']} "
        f"(A={totals['A']} B0={totals['B0']} B1={totals['B1']} C={totals['C']})"
    )

    # ── 충실도 게이트 (변경 전 HARD) ──
    if REF_JSON.exists():
        ref = load_reference_risk_set()
        same = scan["risk_pairs"] == ref["pairs"] and scan["duplicates"] == ref["dup_rows"]
        if same:
            print(
                "FIDELITY OK: 589 unique pairs match "
                "(601 rows, 12 duplicates documented)"
            )
            for blog, kw, cnt in scan["duplicates"]:
                print(f"  dup: {blog} {kw!r} x{cnt}")
        else:
            missing = ref["pairs"] - scan["risk_pairs"]
            extra = scan["risk_pairs"] - ref["pairs"]
            print(
                f"FIDELITY CHANGED: scan={len(scan['risk_pairs'])} "
                f"reference={len(ref['pairs'])} missing={len(missing)} extra={len(extra)}"
            )
            for b, kw in sorted(missing)[:20]:
                print(f"  missing vs ref: {b} {kw!r}")
            for b, kw in sorted(extra)[:20]:
                print(f"  extra vs ref: {b} {kw!r}")
            # row-level diff (디버깅 보조)
            for b, kw in sorted(scan["risk_pairs"] & ref["pairs"])[:10]:
                r = res[b][kw]
                print(
                    f"  rowdiff {b} {kw!r}: avg={r['avg']} thr={r['threshold']} cnt={r['count']}"
                )
            if args.fidelity_hard:
                print("FIDELITY GATE FAILED")
                return 1
    else:
        print(f"REFERENCE NOT FOUND: {REF_JSON}")

    # ── SKIP_ARTIFACT 후보 (소스 토큰 부재) ──
    src = KEYWORDS_PY.read_text(encoding="utf-8")
    artifacts = sorted(
        kw
        for b, kw in sorted(scan["risk_pairs"])
        if f'"{kw}"' not in src and f"'{kw}'" not in src
    )
    print(f"SKIP_ARTIFACT candidates: {artifacts}")

    # ── JSON 출력 ──
    out = build_classified_json(scan)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"WROTE: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Before/After 품질 측정 스크립트 — Q1/Q2/Q3 위반 건수 카운트

사용법:
    python3 measure_quality.py before   # 프롬프트 수정 전
    python3 measure_quality.py after    # 프롬프트 수정 후

결과는 .planning/phase-55-curation-quality-diagnostics/samples/{label}/ 에 저장.
"""
import json
import os
import re
import sqlite3
import sys
from datetime import datetime

# 5000 프로젝트 루트
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from pipelines.curation.writer import generate_curation_article

DATA_DIR = os.path.join(PROJECT_ROOT, "data")
SAMPLES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "samples")

# ── 벤치마크 키워드 6개 ──
BENCHMARKS = [
    {"blog_id": "health-hugo",  "keyword": "비염 영양제 추천",    "category": "health"},
    {"blog_id": "beauty-hugo",  "keyword": "비타민C 세럼 추천",   "category": "beauty"},
    {"blog_id": "fitness-hugo", "keyword": "케틀벨",           "category": "fitness"},
    {"blog_id": "laptop-hugo",  "keyword": "맥북에어",          "category": "laptop"},
    {"blog_id": "interior-hugo","keyword": "현관 수납장 추천",     "category": "interior"},
    {"blog_id": "kitchen-hugo", "keyword": "밥솥",            "category": "kitchen"},
]

# ── Q1/Q2/Q3 위반 패턴 ──

# Q1: 경험/체험 허위 주장
Q1_PATTERNS = [
    r"실제\s*사용",
    r"직접\s*사용",
    r"실사용",
    r"저도\s",
    r"저는\s",
    r"경험했",
    r"體驗했",
    r"써보니",
    r"사용해보니",
    r"사용해본",
    r"써본",
    r"체험했",
    r"느꼈습",
    r"느끼는",
    r"만족스러웠",
]

# Q2: 소스 불명 수치 (퍼지 표현)
Q2_PATTERNS = [
    r"일반적으로\s*\d",
    r"일반적으론\s*\d",
    r"잘 알려져\s*있",
    r"보통\s*\d",
    r"대체로\s*\d",
    r"흔히\s*\d",
    r"많이\s*쓰이는\s*\d",
]

# Q3: 건강 효능 단정 표현
Q3_PATTERNS = [
    r"효과가?\s*있",
    r"효과적",
    r"도움이?\s*되",
    r"도움을?\s*주",
    r"개선",
    r"향상",
    r"치료",
    r"예방",
    r"완화",
    r"환해",
    r"탄력",
    r"활력",
    r"피부를?\s*改善",
    r"몸에\s*좋",
    r"건강에\s*좋",
    r"면역",
    r"혈액\s*순환",
    r"기억력",
    r"집중력",
]


def fetch_products(keyword, limit=5):
    """DB에서 상품 데이터를 가져온다."""
    db_path = os.path.join(DATA_DIR, "curation.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT * FROM products WHERE keyword=? ORDER BY rank ASC LIMIT ?""",
        (keyword, limit),
    ).fetchall()
    conn.close()
    if not rows:
        return []
    return [dict(r) for r in rows]


def check_violations(body, title=""):
    """Q1/Q2/Q3 위반 건수를 카운트한다."""
    text = title + "\n" + body
    violations = {"Q1": [], "Q2": [], "Q3": []}

    for pat in Q1_PATTERNS:
        matches = re.findall(pat, text)
        if matches:
            violations["Q1"].extend(matches)

    for pat in Q2_PATTERNS:
        matches = re.findall(pat, text)
        if matches:
            violations["Q2"].extend(matches)

    for pat in Q3_PATTERNS:
        matches = re.findall(pat, text)
        if matches:
            violations["Q3"].extend(matches)

    return violations


def run_benchmark(label):
    """벤치마크 6개 키워드로 글을 생성하고 위반 건수를 측정한다."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = os.path.join(SAMPLES_DIR, label)
    os.makedirs(out_dir, exist_ok=True)

    results = []
    total_violations = {"Q1": 0, "Q2": 0, "Q3": 0}

    for i, bm in enumerate(BENCHMARKS, 1):
        blog_id = bm["blog_id"]
        keyword = bm["keyword"]
        category = bm["category"]

        print(f"\n[{i}/6] {blog_id} — {keyword}")

        products = fetch_products(keyword, limit=5)
        if len(products) < 3:
            print(f"  ⚠️ 상품 부족 ({len(products)}개) — 스킵")
            results.append({
                "blog_id": blog_id, "keyword": keyword, "category": category,
                "status": "skipped", "reason": f"products={len(products)}",
            })
            continue

        article = generate_curation_article(keyword, products, blog_id=blog_id)
        if not article or not article.get("body_md"):
            print(f"  ⚠️ 생성 실패 — 스킵")
            results.append({
                "blog_id": blog_id, "keyword": keyword, "category": category,
                "status": "failed", "reason": "generation_failed",
            })
            continue

        body = article["body_md"]
        title = article.get("title", "")
        violations = check_violations(body, title)

        q1_count = len(violations["Q1"])
        q2_count = len(violations["Q2"])
        q3_count = len(violations["Q3"])
        total_violations["Q1"] += q1_count
        total_violations["Q2"] += q2_count
        total_violations["Q3"] += q3_count

        status = "✅ OK" if (q1_count + q2_count + q3_count) == 0 else "❌ VIOLATION"
        print(f"  Q1={q1_count} Q2={q2_count} Q3={q3_count} — {status}")
        if violations["Q1"]:
            print(f"    Q1 examples: {violations['Q1'][:3]}")
        if violations["Q2"]:
            print(f"    Q2 examples: {violations['Q2'][:3]}")
        if violations["Q3"]:
            print(f"    Q3 examples: {violations['Q3'][:3]}")

        # 샘플 저장
        sample = {
            "blog_id": blog_id,
            "keyword": keyword,
            "category": category,
            "title": title,
            "body_md": body,
            "body_length": len(body),
            "violations": {k: v for k, v in violations.items()},
            "generated_at": ts,
            "temperature": 0.85,
            "model": "gpt-4o-mini (via ai_writer)",
            "products_count": len(products),
        }
        fname = f"{blog_id}__{keyword.replace(' ', '_')}__{label}.json"
        fpath = os.path.join(out_dir, fname)
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(sample, f, ensure_ascii=False, indent=2)
        print(f"  → 저장: {fpath}")

        results.append({
            "blog_id": blog_id, "keyword": keyword, "category": category,
            "status": "ok", "title": title, "body_length": len(body),
            "Q1": q1_count, "Q2": q2_count, "Q3": q3_count,
            "violations": violations,
        })

    # 요약 리포트
    summary = {
        "label": label,
        "timestamp": ts,
        "benchmarks": results,
        "total_violations": total_violations,
        "condition": {
            "temperature": 0.85,
            "max_tokens": 6000,
            "model": "gpt-4o-mini",
        },
    }
    summary_path = os.path.join(out_dir, f"summary__{label}__{ts}.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"벤치마크 결과 ({label})")
    print(f"{'='*60}")
    print(f"Q1 (경험 주장):     {total_violations['Q1']}건")
    print(f"Q2 (소스 불명 수치):  {total_violations['Q2']}건")
    print(f"Q3 (효능 단정):     {total_violations['Q3']}건")
    print(f"전체 위반:          {sum(total_violations.values())}건")
    print(f"요약: {summary_path}")

    return summary


if __name__ == "__main__":
    label = sys.argv[1] if len(sys.argv) > 1 else "before"
    if label not in ("before", "after"):
        print(f"사용법: python3 {sys.argv[0]} [before|after]")
        sys.exit(1)
    run_benchmark(label)

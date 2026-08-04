#!/usr/bin/env python3
"""기존 발행 글 품질 측정 — Before 베이스라인

실제 발행된 글을 분석하여 Q1/Q2/Q3 위반 건수를 측정.
AI 생성 시간/비용 없이 측정 가능.
"""
import json
import os
import re
import sqlite3
import sys
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
SAMPLES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "samples")

# ── 벤치마크 블로그 6개 ──
BENCHMARK_BLOGS = [
    "health-hugo",
    "beauty-hugo",
    "fitness-hugo",
    "laptop-hugo",
    "interior-hugo",
    "kitchen-hugo",
]

# ── Q1/Q2/Q3 위반 패턴 ──
Q1_PATTERNS = [
    r"실제\s*사용", r"직접\s*사용", r"실사용", r"저도\s", r"저는\s",
    r"경험했", r"써보니", r"사용해보니", r"사용해본", r"써본",
    r"체험했", r"느꼈습", r"만족스러웠",
]
Q2_PATTERNS = [
    r"일반적으로\s*\d", r"일반적으론\s*\d", r"잘 알려져\s*있",
    r"보통\s*\d", r"대체로\s*\d", r"흔히\s*\d",
]
Q3_PATTERNS = [
    r"효과가?\s*있", r"효과적", r"도움이?\s*되", r"도움을?\s*주",
    r"개선", r"향상", r"치료", r"예방", r"완화",
    r"환해", r"탄력", r"활력", r"피부를?\s*改善",
    r"몸에\s*좋", r"건강에\s*좋", r"면역", r"혈액\s*순환",
    r"기억력", r"집중력",
]


def find_latest_post(blog_id):
    """해당 블로그의 최신 발행 글 index.md를 찾는다."""
    hugo_dir = os.path.join("/Users/twinssn/Projects/CUAP", blog_id, "content", "posts")
    if not os.path.isdir(hugo_dir):
        return None

    posts = []
    for slug in os.listdir(hugo_dir):
        idx = os.path.join(hugo_dir, slug, "index.md")
        if os.path.isfile(idx):
            # frontmatter에서 draft 확인
            with open(idx, "r", encoding="utf-8") as f:
                head = f.read(500)
            if "draft: true" in head:
                continue
            mtime = os.path.getmtime(idx)
            posts.append((mtime, idx, slug))

    if not posts:
        return None
    posts.sort(reverse=True)
    return posts[0][1], posts[0][2]


def extract_frontmatter_and_body(filepath):
    """index.md에서 frontmatter와 body를 분리."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    fm = {}
    body = content
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            # simple YAML parse
            for line in parts[1].split("\n"):
                if ":" in line:
                    k, v = line.split(":", 1)
                    fm[k.strip()] = v.strip().strip("'\"")
            body = parts[2].strip()

    return fm, body


def check_violations(text):
    """Q1/Q2/Q3 위반 건수를 카운트."""
    violations = {"Q1": [], "Q2": [], "Q3": []}
    for pat in Q1_PATTERNS:
        violations["Q1"].extend(re.findall(pat, text))
    for pat in Q2_PATTERNS:
        violations["Q2"].extend(re.findall(pat, text))
    for pat in Q3_PATTERNS:
        violations["Q3"].extend(re.findall(pat, text))
    return violations


def run_measurement():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = os.path.join(SAMPLES_DIR, "before_existing")
    os.makedirs(out_dir, exist_ok=True)

    results = []
    total = {"Q1": 0, "Q2": 0, "Q3": 0}

    for blog_id in BENCHMARK_BLOGS:
        found = find_latest_post(blog_id)
        if not found:
            print(f"⚠️ {blog_id}: 발행된 글 없음")
            results.append({"blog_id": blog_id, "status": "no_posts"})
            continue

        fpath, slug = found
        fm, body = extract_frontmatter_and_body(fpath)
        text = fm.get("title", "") + "\n" + body
        violations = check_violations(text)

        q1 = len(violations["Q1"])
        q2 = len(violations["Q2"])
        q3 = len(violations["Q3"])
        total["Q1"] += q1
        total["Q2"] += q2
        total["Q3"] += q3

        status = "✅" if (q1 + q2 + q3) == 0 else "❌"
        print(f"{status} {blog_id} ({slug[:40]}…) — Q1={q1} Q2={q2} Q3={q3}")
        if violations["Q1"]:
            print(f"   Q1: {violations['Q1'][:3]}")
        if violations["Q2"]:
            print(f"   Q2: {violations['Q2'][:3]}")
        if violations["Q3"]:
            print(f"   Q3: {violations['Q3'][:3]}")

        sample = {
            "blog_id": blog_id, "slug": slug, "title": fm.get("title", ""),
            "body_length": len(body),
            "violations": {k: v for k, v in violations.items()},
            "file": fpath,
        }
        fname = f"{blog_id}__before_existing.json"
        with open(os.path.join(out_dir, fname), "w", encoding="utf-8") as f:
            json.dump(sample, f, ensure_ascii=False, indent=2)

        results.append({
            "blog_id": blog_id, "slug": slug, "title": fm.get("title", ""),
            "Q1": q1, "Q2": q2, "Q3": q3,
        })

    print(f"\n{'='*60}")
    print(f"Before 베이스라인 (기존 발행 글 기준)")
    print(f"{'='*60}")
    print(f"Q1 (경험 주장):     {total['Q1']}건")
    print(f"Q2 (소스 불명 수치):  {total['Q2']}건")
    print(f"Q3 (효능 단정):     {total['Q3']}건")
    print(f"전체: {sum(total.values())}건")

    summary = {"label": "before_existing", "timestamp": ts, "results": results, "total": total}
    with open(os.path.join(out_dir, f"summary__{ts}.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    run_measurement()

#!/usr/bin/env python3
"""apply_keyword_removals.py — ast 기반 토큰 단위 삭제 엔진 (블록 스코프)

KEYWORD_MAP (pipelines/curation/keywords.py) 에서 지정 (blog, keyword) 쌍의 토큰만 제거한다.
한 줄에 키워드 2~10개가 들어간 다중 키워드 라인도 토큰 단위로만 삭제 — 라인 전체 삭제 금지.

입력:
  --class-file  kw_risk_classified.json  → A + B0 버킷 자동 제거
  --review-file kw_b1_review.json        → decision == "remove" 항목 제거
  두 파일 동시 지정 가능 (타깃 합집합).

삭제 메커니즘:
  1. ast.parse → KEYWORD_MAP 할당 Dict → 블로그별 List 노드 → 요소(Constant)의
     (value, lineno, col_offset, end_col_offset) 열거. col_offset 은 UTF-8 **바이트** 오프셋.
  2. 블록 스코프: 블로그 List 노드 내에서만 일치 — 들여쓰기(0/4/8-space) 무관.
  3. 타깃 (blog, kw) 의 모든 발생 요소를 제거 (예: fitness '논슬립' 598/616행 2회 모두).
     - end_lineno > lineno (결합 아티팩트, 예: '노트북가을' 455-456행) → SKIP_ARTIFACT: 파일 무변경 + 로그.
     - 소스에 토큰 부재 (f'"{kw}"' 없음) → SKIP_ARTIFACT 로그 (스캐너 사전 경고 2건과 일치해야 함).
     - 블로그 블록 내 일치 요소 없음 → 충실도 위반: exit 1.
  4. 라인별로 바이트 스팬 `"<kw>"` + 뒤따르는 쉼표 + 공백 1칸 제거. 라인이 whitespace-only 가 되면 라인 삭제.
     주석은 독립 라인 (검증됨) — 수정 대상 아님. 그 외 모든 라인/순서/포맷 보존.

검증 (SET_DIFF — done 기준):
  편집 후 fresh subprocess 로 keywords.py 를 재-import 하여 블로그별 발생 수 pre/post 비교:
  (a) 제거 타깃 키워드 0건  (b) 총 발생 수 == pre − Σ(타깃 pre 발생)  (c) 비타깃 키워드 동일 (0 collateral)
  → "SET_DIFF OK: {n} pairs removed, 0 collateral, 0 remaining" (실패 시 exit 1)

안전 밸브: 블로그별 잔여 키워드 발생 수가 8 미만이 될 블로그는 해당 블로그 제거 전부 되돌림.

Production 코드(pipeline.py / relevance_scorer.py / keyword_health.py / curation.db / 테스트) 무수정.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

KEYWORDS_PY = REPO_ROOT / "pipelines/curation/keywords.py"
MIN_BLOG_KEYWORDS = 8  # 안전 밸브 하한

COUNT_CODE = (
    "import sys, json; sys.path.insert(0, {root!r}); "
    "from pipelines.curation.keywords import KEYWORD_MAP; "
    "from collections import Counter; "
    "print(json.dumps({{b: dict(Counter(kws)) for b, kws in KEYWORD_MAP.items()}}, ensure_ascii=False))"
).format(root=str(REPO_ROOT))


def fresh_occurrence_counts() -> dict[str, dict[str, int]]:
    """fresh subprocess 로 keywords.py 를 import 하여 블로그별 키워드 발생 수 반환."""
    res = subprocess.run(
        [sys.executable, "-c", COUNT_CODE],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=120,
    )
    if res.returncode != 0:
        raise RuntimeError(f"fresh import failed:\n{res.stderr}")
    return json.loads(res.stdout.strip().splitlines()[-1])


def load_targets(class_file: str | None, review_file: str | None) -> set[tuple[str, str]]:
    targets: set[tuple[str, str]] = set()
    if class_file:
        with open(class_file, encoding="utf-8") as f:
            data = json.load(f)
        for blog, buckets in data.items():
            if blog in ("totals", "duplicates"):
                continue
            for bucket in ("A", "B0"):
                for row in buckets.get(bucket, []):
                    targets.add((blog, row[0]))
    if review_file:
        with open(review_file, encoding="utf-8") as f:
            reviews = json.load(f)
        for entry in reviews:
            if entry.get("decision") == "remove":
                targets.add((entry["blog_id"], entry["keyword"]))
    return targets


def parse_keyword_map(source: str) -> dict[str, ast.List]:
    """KEYWORD_MAP 할당의 블로그 → List 노드 매핑."""
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "KEYWORD_MAP" for t in node.targets
        ):
            value = node.value
            break
    else:
        raise RuntimeError("KEYWORD_MAP assignment not found")
    if not isinstance(value, ast.Dict):
        raise RuntimeError("KEYWORD_MAP is not a Dict")
    blog_lists: dict[str, ast.List] = {}
    for key, val in zip(value.keys, value.values):
        if isinstance(key, ast.Constant) and isinstance(val, ast.List):
            blog_lists[key.value] = val
    return blog_lists


def plan_edits(
    source: str,
    blog_lists: dict[str, ast.List],
    targets: set[tuple[str, str]],
) -> tuple[dict[int, list[tuple[int, int]]], list[tuple[str, str]], list[tuple[str, str]], list[tuple[str, str]]]:
    """라인별 제거 바이트 스팬 계획.

    Returns: (line_edits, removed_pairs, artifact_pairs, missing_pairs)
    - line_edits: {lineno: [(start_byte, end_byte), ...]} — end 는 token+쉼표+공백1 확장
    """
    line_edits: dict[int, list[tuple[int, int]]] = {}
    removed: list[tuple[str, str]] = []
    artifacts: list[tuple[str, str]] = []
    missing: list[tuple[str, str]] = []
    source_lines = source.split("\n")

    for blog, kw in sorted(targets):
        lst = blog_lists.get(blog)
        if lst is None:
            missing.append((blog, kw))
            continue
        matches = [
            el
            for el in lst.elts
            if isinstance(el, ast.Constant) and isinstance(el.value, str) and el.value == kw
        ]
        if not matches:
            # 소스에 토큰 자체가 없으면 결합 아티팩트 (스캐너 SKIP_ARTIFACT 사전 경고와 일치)
            if f'"{kw}"' not in source and f"'{kw}'" not in source:
                artifacts.append((blog, kw))
            else:
                missing.append((blog, kw))
            continue
        # 결합 아티팩트: 요소가 다중 라인 스팬 (예: '노트북가을' 455-456)
        if any(el.lineno != el.end_lineno for el in matches):
            artifacts.append((blog, kw))
            continue
        for el in matches:
            line = source_lines[el.lineno - 1]
            line_bytes = line.encode("utf-8")
            start = el.col_offset
            end = el.end_col_offset
            # 뒤따르는 쉼표 + 공백 1칸 확장
            if line_bytes[end : end + 1] == b",":
                end += 1
                if line_bytes[end : end + 1] == b" ":
                    end += 1
            line_edits.setdefault(el.lineno, []).append((start, end))
        removed.append((blog, kw))

    return line_edits, removed, artifacts, missing


def apply_line_edits(source: str, line_edits: dict[int, list[tuple[int, int]]]) -> str:
    """바이트 스팬 제거 후 재조립. whitespace-only 라인은 삭제. 수정 라인은 rstrip."""
    lines = source.split("\n")
    for lineno, spans in line_edits.items():
        line = lines[lineno - 1]
        b = line.encode("utf-8")
        unique = sorted(set(spans), key=lambda s: (s[0], s[1]))
        chunks = []
        prev = len(b)
        for start, end in sorted(unique, reverse=True):
            chunks.append(b[end:prev])
            prev = start
        chunks.append(b[:prev])
        new_b = b"".join(reversed(chunks))
        new_line = new_b.decode("utf-8").rstrip()
        lines[lineno - 1] = "" if new_line.strip() == "" else new_line
    text = "\n".join(lines)
    if source.endswith("\n"):
        text += "\n"
    return text


def safety_valve(
    pre: dict[str, dict[str, int]],
    targets: set[tuple[str, str]],
) -> tuple[set[tuple[str, str]], list[str]]:
    """잔여 키워드 < 8 이 될 블로그의 타깃을 제외. (blog, reverted_pairs) 로그 반환."""
    kept: set[tuple[str, str]] = set()
    logs: list[str] = []
    for blog, occ in pre.items():
        blog_targets = {(b, kw) for (b, kw) in targets if b == blog}
        removed_occ = sum(occ.get(kw, 0) for (b, kw) in blog_targets)
        remaining = sum(occ.values()) - removed_occ
        if remaining < MIN_BLOG_KEYWORDS:
            logs.append(
                f"SAFETY VALVE: reverted removals for {blog} "
                f"(remaining would be {remaining} < {MIN_BLOG_KEYWORDS})"
            )
        else:
            kept |= blog_targets
    return kept, logs


def verify_set_diff(
    pre: dict[str, dict[str, int]],
    post: dict[str, dict[str, int]],
    removed_pairs: list[tuple[str, str]],
) -> list[str]:
    removed_set = set(removed_pairs)
    problems: list[str] = []
    for blog, kw in removed_pairs:
        if post.get(blog, {}).get(kw, 0) != 0:
            problems.append(f"[a] {blog} {kw!r}: still present x{post[blog].get(kw)}")
    pre_total = sum(v for b in pre for v in pre[b].values())
    post_total = sum(v for b in post for v in post[b].values())
    removed_occ = sum(pre.get(b, {}).get(kw, 0) for b, kw in removed_pairs)
    if post_total != pre_total - removed_occ:
        problems.append(
            f"[b] total mismatch: pre={pre_total} post={post_total} "
            f"expected={pre_total - removed_occ} (removed_occ={removed_occ})"
        )
    for blog, occ in pre.items():
        for kw, cnt in occ.items():
            if (blog, kw) in removed_set:
                continue
            post_cnt = post.get(blog, {}).get(kw, 0)
            if post_cnt != cnt:
                problems.append(
                    f"[c] collateral: {blog} {kw!r} {cnt} -> {post_cnt}"
                )
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--class-file", default=None, help="kw_risk_classified.json — A+B0 자동 제거")
    parser.add_argument("--review-file", default=None, help="kw_b1_review.json — decision=='remove' 제거")
    parser.add_argument("--dry-run", action="store_true", help="파일 쓰지 않고 계획만 출력")
    args = parser.parse_args(argv)

    if not args.class_file and not args.review_file:
        parser.error("--class-file 또는 --review-file 필수")

    print("PRE-STATE: fresh import occurrence counts...")
    pre = fresh_occurrence_counts()

    targets = load_targets(args.class_file, args.review_file)
    targets, valve_logs = safety_valve(pre, targets)
    for log in valve_logs:
        print(log)

    source = KEYWORDS_PY.read_text(encoding="utf-8")
    blog_lists = parse_keyword_map(source)
    line_edits, removed, artifacts, missing = plan_edits(source, blog_lists, targets)

    for blog, kw in artifacts:
        print(f"SKIP_ARTIFACT: {blog} {kw!r} — 소스 토큰 없음/결합 아티팩트, 파일 무변경")
    if missing:
        print("FIDELITY BREACH: 일치 요소 없음 — 중단")
        for blog, kw in missing:
            print(f"  missing: {blog} {kw!r}")
        return 1

    edited_lines = len(line_edits)
    print(f"PLAN: {len(removed)} pairs removed, {edited_lines} lines touched, {len(artifacts)} artifacts skipped")

    if args.dry_run:
        new_text = apply_line_edits(source, line_edits)
        ast.parse(new_text)  # 문법 검증
        print("DRY RUN OK — no file written")
        return 0

    new_text = apply_line_edits(source, line_edits)
    ast.parse(new_text)  # 편집 후 문법 검증 (쓰기 전)
    KEYWORDS_PY.write_text(new_text, encoding="utf-8")

    # ── SET_DIFF 검증 ──
    post = fresh_occurrence_counts()
    problems = verify_set_diff(pre, post, removed)
    if problems:
        print("SET_DIFF FAILED:")
        for p in problems:
            print(f"  {p}")
        return 1
    removed_occ = sum(pre.get(b, {}).get(kw, 0) for b, kw in removed)
    print(f"SET_DIFF OK: {len(removed)} pairs removed, 0 collateral, 0 remaining "
          f"(tokens removed: {removed_occ})")

    # ── 잔여 블로그별 키워드 수 ──
    for blog in sorted(pre):
        print(f"  {blog}: remaining={sum(post[blog].values())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

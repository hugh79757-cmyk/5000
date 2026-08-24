#!/usr/bin/env python3
"""
rule_reverse_validate.py — 일반화된 역검증 게이트 (Phase 64-06)

c01_c08_reverse_validation.py 패턴을 일반화:
  argparse --rule-id --positive-dir --negative-dir
  gate: 전건탐지 100% + 오탐 0건 → exit 0 else 1 + report table

Usage:
  python scripts/rule_reverse_validate.py --rule-id C01 \
    --positive-dir scripts/c01_c08_validation_data/c01_demo_positive \
    --negative-dir scripts/c01_c08_validation_data/c01_demo_negative

  python scripts/rule_reverse_validate.py --rule-id C04 \
    --positive-dir /path/to/positive_md_files \
    --negative-dir /path/to/negative_md_files

  python scripts/rule_reverse_validate.py --help

Positive = 위반 샘플 (rule이 fail 해야 함), Negative = 정상 샘플 (pass 해야 함).
Gate: positive 전건 fail + negative 오탐 0건 모두 충족 시 exit 0, 아니면 exit 1.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# ── 로컬 체크 함수 (stdlib, 신규 dependency 없음) ────────────────
# ops_dashboard/checks/content_integrity 와 shared/leak_tracker 로직과 동일 판정.
# 외부 모듈 import 실패 시에도 동작하도록 로컬 구현을 1차로 사용.

CURVED_SINGLE = {'\u2018', '\u2019'}
CURVED_DOUBLE = {'\u201c', '\u201d'}

FM_KEY_PATTERN = re.compile(
    r'^\s*(title|og_image|featureimage|date|slug|categories|tags|'
    r'description|draft|image|pubDate|author|cover):'
)

KO_PATTERNS = [
    re.compile(r'먼저\s*생각', re.I),
    re.compile(r'생각해보자|생각해\s*보자', re.I),
    re.compile(r'다음\s*단계', re.I),
    re.compile(r'단계별로', re.I),
    re.compile(r'우선\s*', re.I),
    re.compile(r'우리가\s*해야\s*할', re.I),
    re.compile(r'필요한\s*것', re.I),
    re.compile(r'생각\s*해보자', re.I),
    re.compile(r'(?:^|\n)\s*주의:', re.M),
]

EN_PATTERNS = [
    re.compile(r'\bNeed\s+think\b', re.I),
    re.compile(r'\bWe\s+need\s+to\s+write\b', re.I),
    re.compile(r"Let\.?s\s+think\s+step\s+by\s+step", re.I),
    re.compile(r'think\s+step\s+by\s+step', re.I),
    re.compile(r"let\.?s\s+break\s+this\s+down", re.I),
    re.compile(r"here\.?s?\s+the\s+plan", re.I),
    re.compile(r'in\s+order\s+to\s+achieve', re.I),
    re.compile(r'The\s+user\s+(?:has\s+provided|wants\s+me|said|is\s+asking)', re.I),
    re.compile(r'Let\s+me\s+(?:re-?[Rr]ead|write|check|look|verify|start|create)', re.I),
    re.compile(r'I\s+should\s+(?:write|check|note|add)', re.I),
    re.compile(r'Actually,?\s+', re.I),
    re.compile(r'First,?\s+', re.I),
    re.compile(r'Wait,?\s+', re.I),
    re.compile(r'we\s+need\s+to', re.I),
]

C09_STR_LIST_PATTERN = re.compile(r'^\[\s*[\'"].*[\'"]\s*\]$')


def _check_c01(content: str) -> tuple[bool, str]:
    fm = _extract_frontmatter(content)[0]
    found = []
    if any(c in fm for c in CURVED_SINGLE):
        found.append("곡선홑따옴표")
    if any(c in fm for c in CURVED_DOUBLE):
        found.append("곡선쌍따옴표")
    if found:
        return False, f"C01 위반: {', '.join(found)}"
    return True, "C01 통과"


def _check_c02(content: str) -> tuple[bool, str]:
    lines = content.split('\n')
    first = second = None
    for i, line in enumerate(lines):
        if line.strip() == '---':
            if first is None:
                first = i
            elif second is None:
                second = i
                break
    if first is None:
        return False, "C02 위반: 첫 --- 없음"
    if second is None:
        return False, "C02 위반: 첫 --- 이후 두 번째 --- 없음"
    return True, "C02 통과"


def _check_c03(content: str) -> tuple[bool, str]:
    _, body = _extract_frontmatter(content)[0:2]
    # fallback: if no frontmatter, body is full content
    if not body:
        # body extraction already handles no-frontmatter case
        pass
    leaked = []
    for line in body.split('\n'):
        if FM_KEY_PATTERN.match(line):
            leaked.append(line.strip()[:80])
    if leaked:
        return False, f"C03 위반: {leaked[0]}"
    return True, "C03 통과"


def _check_c04(content: str, locale: str = "ko") -> tuple[bool, str]:
    _, body = _extract_frontmatter(content)[0:2]
    # for C04, if frontmatter stripped, body is content after fm; if no fm, body is full content
    # so check both body and full content for patterns (generation text could be in body)
    target = body if body else content
    patterns = EN_PATTERNS if locale == "en" else KO_PATTERNS
    found = []
    for pat in patterns:
        m = pat.search(target)
        if m:
            found.append(m.group()[:50])
    if found:
        return False, f"C04 위반({locale}): {found[0]}"
    return True, f"C04 통과({locale})"


def _check_c04_any(content: str) -> tuple[bool, str]:
    # try ko first, then en — if either fails, it's contamination
    ok_ko, msg_ko = _check_c04(content, "ko")
    ok_en, msg_en = _check_c04(content, "en")
    if not ok_ko or not ok_en:
        return False, f"C04 위반(ko:{msg_ko}/en:{msg_en})"
    return True, "C04 통과"


def _check_c05(content: str) -> tuple[bool, str]:
    fm_dict = _extract_frontmatter(content)[2]
    val = fm_dict.get("draft", None) if isinstance(fm_dict, dict) else None
    if val is True:
        return False, "C05 위반: draft:true"
    if isinstance(val, str) and val.strip().lower() == "true":
        return False, "C05 위반: draft:true(문자열)"
    return True, "C05 통과"


def _check_c09(content: str) -> tuple[bool, str]:
    fm_dict = _extract_frontmatter(content)[2]
    if not isinstance(fm_dict, dict):
        return True, "C09 통과"
    issues = []
    for field in ("categories", "tags"):
        val = fm_dict.get(field)
        if val is None:
            continue
        if isinstance(val, list):
            continue
        if isinstance(val, str) and C09_STR_LIST_PATTERN.match(val.strip()):
            issues.append(f"{field}='{val}'")
    if issues:
        return False, f"C09 위반: {', '.join(issues)}"
    return True, "C09 통과"


def _extract_frontmatter(content: str) -> tuple[str, str, dict]:
    """Returns (frontmatter_str, body, frontmatter_dict)."""
    if not content.startswith('---'):
        return '', content, {}
    lines = content.split('\n')
    fm_end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == '---':
            fm_end = i
            break
    if fm_end is None:
        return content, '', {}
    fm_str = '\n'.join(lines[1:fm_end])
    body = '\n'.join(lines[fm_end + 1:]).lstrip('\n')
    fm_dict: dict = {}
    try:
        import yaml  # type: ignore
        fm_dict = yaml.safe_load(fm_str) or {}
        if not isinstance(fm_dict, dict):
            fm_dict = {}
    except Exception:
        fm_dict = {}
    return fm_str, body, fm_dict


# rule_id → checker dispatch
_CHECKERS = {
    "C01": _check_c01,
    "C02": _check_c02,
    "C03": _check_c03,
    "C04": _check_c04_any,
    "C05": _check_c05,
    "C09": _check_c09,
}

# C04 locale-aware: if --locale en passed via content detection, use directly
# For generic flow, C04 checks both locales.


def _collect_files(input_path: Path) -> list[Path]:
    """Collect files from a directory or single file or json manifest."""
    if not input_path.exists():
        return []
    if input_path.is_file():
        # if json manifest (list of {source_file: ...}), expand its entries
        if input_path.suffix == ".json":
            try:
                data = json.loads(input_path.read_text(encoding="utf-8", errors="replace"))
                if isinstance(data, list):
                    files = []
                    for item in data:
                        if isinstance(item, dict):
                            sf = item.get("source_file") or item.get("path") or item.get("file")
                            if sf and Path(sf).exists():
                                files.append(Path(sf))
                            elif sf:
                                # fallback: treat slug-like entry without file
                                pass
                        elif isinstance(item, str) and Path(item).exists():
                            files.append(Path(item))
                    if files:
                        return files
                    # if manifest contained no resolvable files, fall through to treat json itself as 0 entries
                    return []
            except Exception:
                pass
            # single file
            return [input_path]
        return [input_path]
    # directory
    files: list[Path] = []
    for p in sorted(input_path.rglob("*")):
        if p.is_file() and p.suffix in (".md", ".txt", ".json", ".yaml", ".yml"):
            # skip validation_result.json etc if it's report not sample
            if p.name in ("validation_result.json",):
                continue
            files.append(p)
        elif p.is_file() and p.suffix == "":
            files.append(p)
    # also include any files without extension but likely content
    if not files:
        for p in sorted(input_path.iterdir()):
            if p.is_file():
                files.append(p)
    return files


def _run_check(rule_id: str, content: str) -> tuple[bool, str]:
    rid = rule_id.upper().strip()
    # try local checker first
    fn = _CHECKERS.get(rid)
    if fn:
        return fn(content)
    # try importing from ops_dashboard or shared for unlisted C rules
    try:
        from ops_dashboard.checks.content_integrity import _check_c01 as _ci_c01  # type: ignore
        # fallback: attempt to reuse content_integrity dispatcher per rule
        import importlib
        mod = importlib.import_module("ops_dashboard.checks.content_integrity")
        # try _check_{rule_lower}
        fname = f"_check_{rid.lower()}"
        if hasattr(mod, fname):
            f = getattr(mod, fname)
            # adapt signature: content_integrity checks take various args; try generic
            try:
                result = f(content)
                if isinstance(result, tuple) and len(result) == 2:
                    return result  # type: ignore
            except Exception:
                pass
        if rid == "C07":
            # C07 needs dead_slugs set — cannot validate without context, treat as skip
            return True, f"{rid} skip (context-dependent, validation deferred)"
        if rid == "C08":
            return True, f"{rid} skip (live compare required, placeholder)"
    except Exception:
        pass
    # S/L/P/V candidates not yet implemented — warning, treat as pass for validation harness
    if rid and rid[0] in ("S", "L", "P", "V"):
        return True, f"{rid} not yet implemented (WARNING observe — validation deferred, treated as pass)"
    return True, f"{rid} unknown rule — treated as pass (no checker)"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rule reverse-validate: gate 전건탐지 100% + 오탐 0건 (Phase 64-06)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--rule-id", required=True, help="rule identifier, e.g. C01, C04, S01, V01")
    parser.add_argument("--positive-dir", required=True, help="directory (or json manifest) containing violated samples (should fail rule)")
    parser.add_argument("--negative-dir", required=True, help="directory (or json manifest) containing normal samples (should pass rule)")
    parser.add_argument("--locale", default="auto", help="locale for C04: ko|en|auto (auto tries both)")
    args = parser.parse_args()

    rule_id = args.rule_id
    pos_path = Path(args.positive_dir)
    neg_path = Path(args.negative_dir)

    pos_files = _collect_files(pos_path)
    neg_files = _collect_files(neg_path)

    # graceful handling if manifest json pointed but no files resolved — try reading positive-dir as dir containing json entries fallback
    # If zero files collected and path is directory with json manifests, attempt to read json lists inside
    if not pos_files and pos_path.is_dir():
        for jf in pos_path.glob("*.json"):
            if jf.name == "validation_result.json":
                continue
            extra = _collect_files(jf)
            pos_files.extend(extra)
    if not neg_files and neg_path.is_dir():
        for jf in neg_path.glob("*.json"):
            if jf.name == "validation_result.json":
                continue
            extra = _collect_files(jf)
            neg_files.extend(extra)

    if not pos_path.exists():
        print(f"[error] positive-dir not found: {pos_path}", file=sys.stderr)
        return 1
    if not neg_path.exists():
        print(f"[error] negative-dir not found: {neg_path}", file=sys.stderr)
        return 1
    if not pos_files:
        print(f"[error] positive-dir empty or no readable files: {pos_path} (need ≥1 violated sample)", file=sys.stderr)
        return 1
    if not neg_files:
        print(f"[error] negative-dir empty or no readable files: {neg_path} (need ≥1 normal sample)", file=sys.stderr)
        return 1

    # ── evaluate positive (should fail → detected) ──
    pos_total = len(pos_files)
    pos_detected = 0
    pos_details: list[dict] = []
    for f in pos_files:
        try:
            content = f.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            pos_details.append({"file": str(f), "result": "error", "msg": str(e)})
            continue
        ok, msg = _run_check(rule_id, content)
        # ok=True means rule passed (no violation), so for positive we expect ok=False (violation found)
        detected = not ok
        if detected:
            pos_detected += 1
        pos_details.append({"file": str(f), "expected": "fail", "actual": ("fail" if not ok else "pass"), "detected": detected, "msg": msg})

    # ── evaluate negative (should pass → no false positive) ──
    neg_total = len(neg_files)
    neg_false = 0
    neg_details: list[dict] = []
    for f in neg_files:
        try:
            content = f.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            neg_details.append({"file": str(f), "result": "error", "msg": str(e)})
            continue
        ok, msg = _run_check(rule_id, content)
        false_pos = not ok  # if rule failed on negative, it's false positive
        if false_pos:
            neg_false += 1
        neg_details.append({"file": str(f), "expected": "pass", "actual": ("fail" if not ok else "pass"), "false_positive": false_pos, "msg": msg})

    # ── report table ──
    print("=" * 72)
    print(f"  rule_reverse_validate — rule {rule_id}")
    print(f"  positive-dir: {pos_path} ({pos_total} files)")
    print(f"  negative-dir: {neg_path} ({neg_total} files)")
    print("=" * 72)
    print()
    # markdown-ish table
    print("| rule | positive | detected | rate | negative | false_positive | gate |")
    print("|------|----------|----------|------|----------|----------------|------|")
    pos_rate = f"{pos_detected}/{pos_total} ({pos_detected/pos_total*100:.0f}%)" if pos_total else "N/A"
    neg_fp = f"{neg_false}/{neg_total}"
    pos_ok = pos_detected == pos_total and pos_total > 0
    neg_ok = neg_false == 0
    gate = "PASS" if (pos_ok and neg_ok) else "FAIL"
    print(f"| {rule_id} | {pos_total} | {pos_detected} | {pos_rate} | {neg_total} | {neg_fp} | {gate} |")
    print()
    print(f"  전건탐지 : {'통과' if pos_ok else '미달'} ({pos_detected}/{pos_total} {'✅' if pos_ok else '❌'})")
    print(f"  오탐     : {'0건 ✅' if neg_ok else f'{neg_false}건 ❌'} ({neg_false}/{neg_total})")
    print(f"  게이트   : {gate} (전건탐지 100% + 오탐 0건 모두 충족 시 PASS)")
    print()

    # detail for failures (limit 5)
    if not pos_ok:
        missed = [d for d in pos_details if not d.get("detected")]
        if missed:
            print(f"  ⚠️  positive 미탐지 (예상 fail, 실제 pass): {len(missed)}건")
            for d in missed[:5]:
                print(f"     - {Path(d['file']).name}: {d.get('msg','')}")
    if not neg_ok:
        fps = [d for d in neg_details if d.get("false_positive")]
        if fps:
            print(f"  ⚠️  negative 오탐 (예상 pass, 실제 fail): {len(fps)}건")
            for d in fps[:5]:
                print(f"     - {Path(d['file']).name}: {d.get('msg','')}")
    print()

    # final verdict
    if pos_ok and neg_ok:
        print(f"  ✅ 결과: 전건탐지 100% + 오탐 0건 → 승격 가능 (gate PASS)")
        return 0
    else:
        print(f"  ❌ 결과: 조건 미달 — 승격 보류, 조건 수정 후 재검증 필요")
        if not pos_ok:
            print(f"     - positive 전건탐지 미달: {pos_detected}/{pos_total}")
        if not neg_ok:
            print(f"     - negative 오탐 있음: {neg_false}/{neg_total}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

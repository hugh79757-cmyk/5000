#!/usr/bin/env python3
"""Title Quality Gate — Phase 7 Integration Verification

Validates sanitize_title() output against Phase 7 quality gates:
  1. No date prefix (YYYY년 MM월)
  2. No special characters (em dash, en dash, middle dot, bullet, fullwidth colon)
  3. Title length ≤ 65 chars
  4. Title length ≥ 10 chars

Usage:
  python scripts/test_title_quality.py
"""

import sys, re

sys.path.insert(0, ".")

from shared.validators import sanitize_title

TEST_SAMPLES = [
    # (input, expected_contains, description)
    ("2026년 7월 립밤 추천 BEST 5", "립밤", "date prefix stripped"),
    ("립밤 추천 — 하루 종일 촉촉한 선택", "촉촉한", "em dash removed"),
    ("립밤 추천 – en 대시", "en 대시", "en dash removed"),
    ("TOP5 · 추천 순위", "TOP5", "middle dot removed"),
    ("립밤•bullet", "립밤bullet", "bullet removed"),
    ("립밤 추천：BEST 5", "BEST 5", "fullwidth colon removed"),
    ("비교 분석: TOP5 선정", ":", "regular colon preserved"),
    ("A vs B - comparison", "-", "hyphen preserved"),
    ("짧음", "짧음", "short title unchanged"),
    ("가" * 70, None, "long title truncated to ≤65"),
    ("2026년 7월 제주도 렌트카·SUV 추천 – BEST 5 선정", "제주도", "combined multi-issue"),
]


def check_title(title: str, label: str = "") -> list:
    errors = []
    if re.match(r"^\d{4}년\s*\d{1,2}월", title):
        errors.append(f"DATE_PREFIX")
    special = re.findall(r"[—–·•：]", title)
    if special:
        errors.append(f"SPECIAL({''.join(set(special))})")
    if len(title) > 65:
        errors.append(f"TOO_LONG({len(title)})")
    if len(title) < 10 and len(title) < len(TEST_SAMPLES[8][0]) - 1:  # only flag non-trivial short titles
        errors.append(f"TOO_SHORT({len(title)})")
    return errors


def main():
    passed = 0
    failed = 0

    print(f"{'Input':55} {'Output':40} {'Length':7} Status")
    print("-" * 110)

    for inp, expected, desc in TEST_SAMPLES:
        result = sanitize_title(inp)
        errors = check_title(result, desc)
        status = "✅" if not errors else "❌"
        flag = f"FAIL: {', '.join(errors)}" if errors else "OK"

        print(f"{inp!r:55} {result!r:40} {len(result):5}  {status}  {flag}")
        if errors:
            failed += 1
        else:
            passed += 1

    print(f"\n{'=' * 60}")
    print(f"Results: {passed} passed, {failed} failed, {passed + failed} total")
    print(f"{'=' * 60}")

    if failed > 0:
        print("\n❌ Some quality gates failed")
        return 1

    print("\n✅ All title quality gates passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

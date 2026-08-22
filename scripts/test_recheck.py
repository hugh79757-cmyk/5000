"""scripts/test_recheck.py — BLK-4 TARGETED_RECHECK 동작 검증.

실행: python3 scripts/test_recheck.py
- travel4-hugo FM-MISSINGKEYS 위반 케이스 → passed=False
- RecheckResult 필드 전수 존재
- 통과 케이스 → passed=True
블로그 소스 미수정 — 임시파일 사용.
"""
from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, "/Users/twinssn/Projects/5000")

from ops_dashboard.recheck import RecheckResult, targeted_recheck

EXPECTED_FIELDS = [
    "blog_id", "post_path", "check_name", "previous_status",
    "current_status", "passed", "timestamp", "detail",
]


def _write_tmp(text: str) -> str:
    fd = tempfile.NamedTemporaryFile(
        "w", suffix=".md", delete=False, encoding="utf-8"
    )
    fd.write(text)
    fd.close()
    return fd.name


def main() -> None:
    # 위반 케이스 (FM-MISSINGKEYS: description/date/slug/tags 누락)
    bad = "---\ntitle: \"테스트\"\n---\nbody\n"
    p_bad = _write_tmp(bad)
    r = targeted_recheck("travel4-hugo", p_bad, "FM-MISSINGKEYS")
    assert isinstance(r, RecheckResult), "RecheckResult 타입 아님"
    assert r.passed is False, f"위반 케이스 passed=True (status={r.current_status})"
    d = r.to_dict()
    missing = [k for k in EXPECTED_FIELDS if k not in d]
    assert not missing, f"필드 누락: {missing}"
    print(f"  [위반] status={r.current_status} prev={r.previous_status} detail={r.detail!r}")

    # 통과 케이스 (필수키 전부 존재)
    good = (
        "---\ntitle: \"t\"\ndescription: \"d\"\n"
        "date: \"2026-01-01\"\nslug: \"s\"\ntags: [\"x\"]\n---\nbody\n"
    )
    p_good = _write_tmp(good)
    r2 = targeted_recheck("travel4-hugo", p_good, "FM-MISSINGKEYS")
    assert r2.passed is True, f"통과 케이스 passed=False (status={r2.current_status})"
    print(f"  [통과] status={r2.current_status}")

    # 미지원 rule_id 거부 확인
    try:
        targeted_recheck("travel4-hugo", p_good, "NOT-A-RULE")
        raise AssertionError("미지원 rule_id에서 ValueError 미발생")
    except ValueError:
        print("  [거부] 미지원 check_name → ValueError OK")

    os.unlink(p_bad)
    os.unlink(p_good)
    print("test_recheck PASS")


if __name__ == "__main__":
    main()

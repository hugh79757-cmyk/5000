"""scripts/test_rollback.py — BLK-5 ROLLBACK_CHAIN 동작 검증.

실행: python3 scripts/test_rollback.py
- create_rollback_point → 백업 생성
- 내용 변경 후 execute_rollback → matches_original=True
- 백업 훼손 시나리오 → success=False (해시 불일치)
블로그 소스 미수정 — 임시파일 사용. git commit 미수행.
"""
from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, "/Users/twinssn/Projects/5000")

from ops_dashboard.rollback import (
    RollbackPoint,
    RollbackResult,
    create_rollback_point,
    execute_rollback,
)


def _write(p: str, text: str) -> None:
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)


def main() -> None:
    p = tempfile.mktemp(suffix=".md")
    _write(p, "# orig\n")

    rp = create_rollback_point("test-blog", p)
    assert isinstance(rp, RollbackPoint), "RollbackPoint 타입 아님"
    print(f"  [생성] backup={rp.backup_path}")

    # fixer 적용(내용 변경) 시뮬레이션
    _write(p, "# changed by fixer\n")
    res = execute_rollback(rp)
    assert isinstance(res, RollbackResult), "RollbackResult 타입 아님"
    assert res.matches_original is True, f"복원 실패: {res}"
    assert res.success is True
    print(f"  [복원] matches_original={res.matches_original} restored={res.restored_hash[:8]}")

    # 해시 불일치 시나리오: backup 자체 훼손
    _write(p, "# changed again\n")
    _write(rp.backup_path, "# corrupted backup\n")
    res2 = execute_rollback(rp)
    assert res2.success is False, "해시 불일치인데 success=True"
    assert res2.matches_original is False
    print(f"  [불일치] success={res2.success} matches_original={res2.matches_original}")

    # 누락 백업 → 예외 raise (silent fail 금지)
    import pathlib
    missing = pathlib.Path(rp.backup_path)
    missing.unlink()
    try:
        execute_rollback(rp)
        raise AssertionError("누락 백업에서 예외 미발생")
    except FileNotFoundError:
        print("  [예외] 누락 백업 → FileNotFoundError OK")

    os.unlink(p)
    print("test_rollback PASS")


if __name__ == "__main__":
    main()

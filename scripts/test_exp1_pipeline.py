"""scripts/test_exp1_pipeline.py — Phase 2+3 통합 검증 (plain assert).

시나리오:
  A. 정상: rollback_point → dry_apply(safe) → 적용 → record(APPLIED) → recheck(pass) → record(RECHECK_PASS)
  B. 차단: dry_apply(unsafe) → 적용 중단 (PATCH_PROPOSED 유지)
  C. 롤백: 잘못 적용 → recheck(fail) → execute_rollback → record(ROLLED_BACK)
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import ops_dashboard.fix_history as fh
import ops_dashboard.recheck as rc
import ops_dashboard.rollback as rb
import ops_dashboard.verify_before_apply as va


def _post_path() -> str:
    d = Path(tempfile.mkdtemp(prefix="exp1_"))
    p = d / "post.md"
    # FM-MISSINGKEYS 상태 (description/date/slug/tags 누락) — 실제 크기 근사 본문
    body = "\n".join(f"본문 단락 {i}. 여행 코스 설명." for i in range(60))
    p.write_text(
        f"---\ntitle: \"테스트\"\n---\n\n{body}\n", encoding="utf-8"
    )
    return str(p)


def _fix_missingkeys(content: str) -> str:
    end = content.find("\n---", 3)
    block = content[3:end]
    body = content[end + 4:]
    adds = [
        'description: "요약"',
        'date: "2026-08-22"',
        'slug: "test"',
        'tags: ["x"]',
    ]
    new_block = block.rstrip("\n") + "\n" + "\n".join(adds) + "\n"
    return "---\n" + new_block + "---" + body


def _noop(content: str) -> str:
    return content  # FM 미수정 (의도적 잘못 적용)


def test_scenario_a_normal():
    fh.ROOT = Path(tempfile.mkdtemp(prefix="histA_"))
    p = _post_path()
    rp = rb.create_rollback_point("b1", p)
    vr = va.dry_apply("b1", p, "FM-MISSINGKEYS", _fix_missingkeys)
    assert vr.safe_to_apply is True
    Path(p).write_text(_fix_missingkeys(Path(p).read_text(encoding="utf-8")))
    fh.record_fix("b1", p, "FM-MISSINGKEYS", "APPLIED")
    rr = rc.targeted_recheck("b1", p, "FM-MISSINGKEYS")
    assert rr.passed is True, rr.detail
    fh.record_fix("b1", p, "FM-MISSINGKEYS", "RECHECK_PASS")
    assert fh.get_latest("b1", p, "FM-MISSINGKEYS").action == "RECHECK_PASS"


def test_scenario_b_blocked():
    fh.ROOT = Path(tempfile.mkdtemp(prefix="histB_"))
    p = _post_path()
    vr = va.dry_apply("b1", p, "FM-MISSINGKEYS", lambda c: "")
    assert vr.safe_to_apply is False
    fh.record_fix("b1", p, "FM-MISSINGKEYS", "PATCH_PROPOSED")  # 적용 안 함
    assert fh.get_latest("b1", p, "FM-MISSINGKEYS").action == "PATCH_PROPOSED"


def test_scenario_c_rollback():
    fh.ROOT = Path(tempfile.mkdtemp(prefix="histC_"))
    p = _post_path()
    rp = rb.create_rollback_point("b1", p)
    Path(p).write_text(_noop(Path(p).read_text(encoding="utf-8")))  # 미수정 적용
    fh.record_fix("b1", p, "FM-MISSINGKEYS", "APPLIED")
    rr = rc.targeted_recheck("b1", p, "FM-MISSINGKEYS")
    assert rr.passed is False
    res = rb.execute_rollback(rp)
    assert res.matches_original is True
    fh.record_fix("b1", p, "FM-MISSINGKEYS", "ROLLED_BACK")
    assert fh.get_latest("b1", p, "FM-MISSINGKEYS").action == "ROLLED_BACK"


if __name__ == "__main__":
    test_scenario_a_normal()
    test_scenario_b_blocked()
    test_scenario_c_rollback()
    print("test_exp1_pipeline: PASS")

"""Phase 71 (SC-4) pending_fixes 영속 큐 + 실제 fixer 배선 통합 검증.

작업 0/1(신호 정합성) 후, 작업 2 배선의 핵심을 실제 코드 경로로 검증한다:

  - 감지 루프가 쓴 fail 규칙 행(check_results rule_id=...) → _fetch_failed_rule_ids
    → _run_autofix_after_checks 가 _auto_fix_on_fail 로 전달 (배선).
  - 파괴등급(R08 등 사람 승인 필요) fix 는 기본 approve_non_safe=False 일 때
    **실행하지 않고** pending_fixes 에 proposed 로 영속 적재 (승인 대기 큐).
  - 승인 경로(execute_pending_fix)는 **실제 fixer**(DUMMY 대신 shared/autofix
    FIXERS 레지스트리 경유)를 실행하고 resolved/failed 로 전이한다.

실제 fixer 실행으로 검증하되, 외부 부수효과(백업 git tag, GA4 조회)는 mock 으로
격리한다. 재배포(파괴적)는 redeploy=False 로 끈다.
"""

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import shared.autofix as autofix_mod
import dispatcher
from ops_dashboard.db import (
    init_db,
    get_pending_fix,
    list_pending_fixes,
    record_check_rule,
    set_pending_fix_status,
)


def _make_site_with_lead() -> str:
    """single.html 에 리터럴 .Lead 토큰이 있는 임시 Hugo 사이트 반환.

    R08 표준 체크(standard.py)는 literal '.Lead'/'.Description' 서브스트링을 위반으로
    감지하고, 실제 fixer(fix_r08_lead)는 그 줄을 제거한다. class="Lead" 형태는 R08
    위반이 아니므로 이 fixture 는 .Lead 리터럴을 사용한다.
    """
    site = tempfile.mkdtemp(prefix="pendingfix-test-")
    layout = Path(site) / "layouts" / "_default"
    layout.mkdir(parents=True, exist_ok=True)
    (layout / "single.html").write_text(
        '<article class="content prose">\n'
        '  <p class="post-description">{{ .Lead }}</p>\n'
        "  {{ .Content }}\n"
        "</article>\n",
        encoding="utf-8",
    )
    return site


class PendingFixesWiringTest(unittest.TestCase):
    def setUp(self):
        self.site = _make_site_with_lead()
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        init_db(self.conn)
        self.patches = [
            patch.object(autofix_mod, "backup_blog", lambda sp, b: True),
            patch.object(autofix_mod, "get_ga4_id", lambda b, d: None),
            patch.object(
                dispatcher, "get_blog_config",
                lambda b: {"site_path": self.site, "domain": "cap.example.kr"},
            ),
        ]
        for p in self.patches:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in self.patches])

    def test_fetch_failed_rule_ids_reads_detection_rows(self):
        record_check_rule(self.conn, "cap-hugo", "R08", "fail", "MAJOR", "fix_r08", "ev")
        record_check_rule(self.conn, "cap-hugo", "R06", "fail", "CRITICAL", "fix_r06", "ev")
        got = dispatcher._fetch_failed_rule_ids(self.conn, "cap-hugo")
        self.assertCountEqual(got, ["R08", "R06"])

    def test_run_autofix_after_checks_feeds_detection_to_pending(self):
        """배선: 감지 루프가 쓴 fail 행 → _auto_fix_on_fail → pending_fixes proposed."""
        record_check_rule(self.conn, "cap-hugo", "R08", "fail", "MAJOR", "fix_r08", "ev")
        summary = dispatcher._run_autofix_after_checks(
            self.conn, "cap-hugo", str(Path(self.site) / "ops.db")
        )
        self.assertIsNotNone(summary)
        # 파괴등급(R08)은 승인 전 실행하지 않고 pending 큐에 적재
        self.assertIn("R08->fix_r08", summary["requires_approval"])
        self.assertEqual(summary["applied"], [])
        rows = list_pending_fixes(self.conn, blog_id="cap-hugo")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["rule_id"], "R08")
        self.assertEqual(rows[0]["status"], "proposed")

    def test_destructive_r08_real_fixer_runs_only_with_approval(self):
        """실제 fixer 경유 검증: approve_non_safe=True 시 실 fixer 가 site 파일을 고친다."""
        self.assertIn('.Lead', (Path(self.site) / "layouts/_default/single.html").read_text())
        res = dispatcher._auto_fix_on_fail(
            "cap-hugo", ["R08"], conn=self.conn, approve_non_safe=True, redeploy=False
        )
        self.assertTrue(any(a.startswith("R08:") for a in res["applied"]), res)
        self.assertNotIn('.Lead', (Path(self.site) / "layouts/_default/single.html").read_text())

    def test_destructive_gate_persists_proposed_and_does_not_apply(self):
        """승인 없이(R08, approve_non_safe=False) → 실행 금지 + proposed 영속 적재."""
        res = dispatcher._auto_fix_on_fail(
            "cap-hugo", ["R08"], conn=self.conn, redeploy=False
        )
        self.assertEqual(res["applied"], [])
        self.assertIn("R08->fix_r08", res["requires_approval"])
        row = get_pending_fix(self.conn, 1)
        self.assertIsNotNone(row)
        self.assertEqual(row["rule_id"], "R08")
        self.assertEqual(row["status"], "proposed")
        self.assertIn('.Lead', (Path(self.site) / "layouts/_default/single.html").read_text())

    def test_dedup_no_pileup_on_hourly_rechecks(self):
        """동일 rule 이 재검사로 반복 감지돼도 active 큐에 중복 적재되지 않는다."""
        for _ in range(3):
            dispatcher._auto_fix_on_fail(
                "cap-hugo", ["R08"], conn=self.conn, redeploy=False
            )
        rows = list_pending_fixes(self.conn, blog_id="cap-hugo", status="proposed")
        self.assertEqual(len(rows), 1)

    def test_execute_pending_fix_runs_real_fixer_and_resolves(self):
        """승인 엔드포인트 경로: execute_pending_fix 가 실제 fixer 로 resolved 전이."""
        dispatcher._auto_fix_on_fail("cap-hugo", ["R08"], conn=self.conn, redeploy=False)
        fix_id = get_pending_fix(self.conn, 1)["id"]
        result = dispatcher.execute_pending_fix(self.conn, fix_id, redeploy=False)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["status"], "resolved")
        self.assertNotIn('.Lead', (Path(self.site) / "layouts/_default/single.html").read_text())
        row = get_pending_fix(self.conn, fix_id)
        self.assertEqual(row["status"], "resolved")
        self.assertIsNotNone(row["resolved_at"])

    def test_execute_pending_fix_guards_duplicate_and_bad_status(self):
        """이미 resolved/failed 인 행은 재실행 불가, 없는 행은 404성 처리."""
        dispatcher._auto_fix_on_fail("cap-hugo", ["R08"], conn=self.conn, redeploy=False)
        fix_id = get_pending_fix(self.conn, 1)["id"]
        dispatcher.execute_pending_fix(self.conn, fix_id, redeploy=False)
        dup = dispatcher.execute_pending_fix(self.conn, fix_id, redeploy=False)
        self.assertFalse(dup["ok"])
        missing = dispatcher.execute_pending_fix(self.conn, 99999, redeploy=False)
        self.assertFalse(missing["ok"])


if __name__ == "__main__":
    unittest.main()

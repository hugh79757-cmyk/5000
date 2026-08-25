"""Phase 71 (SC-4) 자동수정 디스패처 게이트 검증.

실제 fixer / 라이브 블로그 / 재배포를 건드리지 않고, OQ#2 승인게이트 로직만
격리 검증:
  - actionable bucket 규칙만 대상
  - SAFE_ACTIONS(fix_thumbnail_r2) 는 기본 무인 실행
  - 비안전 항목(파괴등급)은 항상 requires_approval (approve_non_safe 와 무관 — 옵션 a)
  - redeploy(파괴적) 는 env AUTOFIX_REDEPLOY_APPROVED=1 + approve_non_safe 게이트 필요
"""

import tempfile
import unittest
from unittest.mock import patch

import shared.autofix as autofix_mod
import dispatcher


DUMMY_FIXERS = {
    "fix_r04": lambda site, blog, ga4=None: (True, "dummy r04"),
    "fix_r06": lambda site, blog, ga4=None: (True, "dummy r06"),
    "fix_r08": lambda site, blog, ga4=None: (True, "dummy r08"),
    "fix_r12": lambda site, blog, ga4=None: (True, "dummy r12"),
    "fix_thumbnail_r2": lambda site, blog, ga4=None: (True, "dummy thumb"),
    "fix_r2_images": lambda site, blog, ga4=None: (True, "dummy r2"),
}


class AutoFixHookTest(unittest.TestCase):
    def setUp(self):
        self.site = tempfile.mkdtemp(prefix="autofix-test-")
        self.patches = [
            patch.object(autofix_mod, "FIXERS", DUMMY_FIXERS),
            patch.object(autofix_mod, "get_ga4_id", lambda b, d: None),
            patch.object(autofix_mod, "backup_blog", lambda sp, b: True),
            patch.object(
                dispatcher, "get_blog_config",
                lambda b: {"site_path": self.site, "domain": "x.kr"},
            ),
        ]
        for p in self.patches:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in self.patches])

    def test_safe_action_runs_unattended_no_redeploy(self):
        with patch.object(dispatcher, "_build_and_deploy_central") as dep, \
             patch.object(dispatcher, "_trigger_post_publish_checks") as rc:
            res = dispatcher._auto_fix_on_fail(
                "cap-hugo", ["THUMBNAIL-01"], redeploy=False
            )
        self.assertIn("THUMBNAIL-01:dummy thumb", res["applied"])
        self.assertEqual(res["requires_approval"], [])
        self.assertFalse(res["redeployed"])
        dep.assert_not_called()
        rc.assert_not_called()

    def test_non_safe_requires_approval_by_default(self):
        res = dispatcher._auto_fix_on_fail("cap-hugo", ["R08"])
        self.assertIn("R08->fix_r08", res["requires_approval"])
        self.assertEqual(res["applied"], [])

    def test_non_safe_always_manual_even_with_approval(self):
        # 옵션 a: 비안전 항목은 approve_non_safe=True 여도 무인 실행/재배포 금지
        with patch.object(dispatcher, "_build_and_deploy_central") as dep, \
             patch.object(dispatcher, "_trigger_post_publish_checks") as rc, \
             patch.object(dispatcher, "_record_destructive_redeploy") as rec:
            res = dispatcher._auto_fix_on_fail(
                "cap-hugo", ["R08"], approve_non_safe=True, redeploy=True
            )
        self.assertIn("R08->fix_r08", res["requires_approval"])
        self.assertEqual(res["applied"], [])
        self.assertFalse(res["redeployed"])
        self.assertFalse(res["recheck_triggered"])
        dep.assert_not_called()
        rc.assert_not_called()
        rec.assert_not_called()

    def test_safe_action_redeploys_when_gate_approved(self):
        # 옵션 a: 안전항목은 env 게이트+AUTOFIX_REDEPLOY_APPROVED 통과 시 무인 재배포
        import os
        with patch.dict(os.environ, {"AUTOFIX_REDEPLOY_APPROVED": "1"}), \
             patch.object(dispatcher, "_build_and_deploy_central") as dep, \
             patch.object(dispatcher, "_trigger_post_publish_checks") as rc, \
             patch.object(dispatcher, "_record_destructive_redeploy") as rec:
            res = dispatcher._auto_fix_on_fail(
                "cap-hugo", ["THUMBNAIL-01"], approve_non_safe=True, redeploy=True
            )
        self.assertIn("THUMBNAIL-01:dummy thumb", res["applied"])
        self.assertEqual(res["requires_approval"], [])
        self.assertTrue(res["redeployed"])
        self.assertTrue(res["recheck_triggered"])
        dep.assert_called_once_with("cap-hugo")
        rc.assert_called_once()
        rec.assert_called_once()

    def test_out_of_scope_and_deferred_skipped(self):
        res = dispatcher._auto_fix_on_fail("cap-hugo", ["R04", "R06", "R03"])
        self.assertEqual(res["applied"], [])
        self.assertEqual(res["requires_approval"], [])
        self.assertTrue(any("R04" in s for s in res["skipped"]))
        self.assertTrue(any("R06" in s for s in res["skipped"]))


if __name__ == "__main__":
    unittest.main()

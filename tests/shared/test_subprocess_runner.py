"""Wave-0 tests for shared/subprocess_runner.py (Phase 61, D-03).

These tests verify run_subprocess() runs an external project module in an isolated
subprocess and returns a dict, with timeout/no-output/nonzero handling, signature
bridging (run() vs run(cfg) vs run_publish()), and CLOUDFLARE_API_TOKEN stripping.
"""

import os

import pytest

from shared.subprocess_runner import run_subprocess


def _make_project(tmp_path, module_body, module_name="mymod", package="pipeline"):
    """Create a temp external project: <root>/<package>/<module>.py with module_body."""
    pkg_dir = tmp_path / package
    pkg_dir.mkdir(parents=True, exist_ok=True)
    (pkg_dir / "__init__.py").write_text("", encoding="utf-8")
    (pkg_dir / f"{module_name}.py").write_text(module_body, encoding="utf-8")
    return str(tmp_path), f"{package}.{module_name}"


class TestReturnsDict:
    def test_run_subprocess_returns_dict(self, tmp_path):
        root, spec = _make_project(
            tmp_path,
            'def run(cfg):\n    return {"success": True, "slug": "ok"}\n',
        )
        result = run_subprocess(root, "", spec, run_callable="run", cfg={"daily_quota": 1})
        assert isinstance(result, dict)
        assert result.get("success") is True
        assert result.get("slug") == "ok"

    def test_tap_style_run_publish_no_arg(self, tmp_path):
        root, spec = _make_project(
            tmp_path,
            'def run_publish():\n    return {"success": True, "slug": "tap-style"}\n',
        )
        result = run_subprocess(root, "", spec, run_callable="run_publish", cfg=None)
        assert isinstance(result, dict)
        assert result.get("success") is True
        assert result.get("slug") == "tap-style"

    def test_signature_bridge_run_no_arg(self, tmp_path):
        """A callable with no parameters is invoked as run() (dispatcher bridge)."""
        root, spec = _make_project(
            tmp_path,
            'def run():\n    return {"success": True, "slug": "noarg"}\n',
        )
        result = run_subprocess(root, "", spec, run_callable="run", cfg={"daily_quota": 1})
        assert result.get("slug") == "noarg"


class TestTimeout:
    def test_run_subprocess_timeout(self, tmp_path):
        root, spec = _make_project(
            tmp_path,
            "import time\ndef run(cfg):\n    time.sleep(30)\n    return {'success': True}\n",
        )
        result = run_subprocess(root, "", spec, run_callable="run", cfg={}, timeout=1, prefix="subproc")
        assert result == {"success": False, "reason": "subproc_timeout"}


class TestNoOutput:
    def test_run_subprocess_no_output(self, tmp_path):
        """No parseable JSON on stdout (module early-exits with returncode 0) → no_output."""
        root, spec = _make_project(
            tmp_path,
            "import os\ndef run(cfg):\n    os._exit(0)\n",
        )
        result = run_subprocess(root, "", spec, run_callable="run", cfg={}, prefix="subproc")
        assert result == {"success": False, "reason": "subproc_no_output"}


class TestNonZero:
    def test_run_subprocess_nonzero(self, tmp_path):
        root, spec = _make_project(
            tmp_path,
            "import sys\ndef run(cfg):\n    sys.exit(1)\n",
        )
        result = run_subprocess(root, "", spec, run_callable="run", cfg={}, prefix="subproc")
        assert result == {"success": False, "reason": "subproc_subprocess_error"}

    def test_run_subprocess_preserves_stderr_on_crash(self, tmp_path):
        """크래시(stderr)가 버려지지 않고 result['stderr']에 보존 — sector 진단(작업3)."""
        root, spec = _make_project(
            tmp_path,
            "def run(cfg):\n    raise RuntimeError('boom detail')\n",
        )
        result = run_subprocess(root, "", spec, run_callable="run", cfg={}, prefix="stap")
        assert result["reason"] == "stap_subprocess_error"
        assert "boom detail" in result.get("stderr", ""), "stderr가 보존되어야 함"

    def test_run_subprocess_redacts_secrets_in_stderr(self, tmp_path):
        """stderr의 봇 토큰은 마스킹되어 대시보드로 새지 않는다."""
        root, spec = _make_project(
            tmp_path,
            "def run(cfg):\n    raise RuntimeError('api_key=sk-secret123 crash')\n",
        )
        result = run_subprocess(root, "", spec, run_callable="run", cfg={}, prefix="stap")
        stderr = result.get("stderr", "")
        assert "sk-secret123" not in stderr
        assert "api_key=[REDACTED]" in stderr


class TestTokenSafety:
    def test_runner_strips_cloudflare_api_token(self, tmp_path, monkeypatch):
        root, spec = _make_project(
            tmp_path,
            'import os\ndef run(cfg):\n    return {"success": True, "token": os.environ.get("CLOUDFLARE_API_TOKEN")}\n',
        )
        monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "should_be_stripped")
        result = run_subprocess(root, "", spec, run_callable="run", cfg={}, prefix="subproc")
        assert result.get("token") is None, "runner must pop CLOUDFLARE_API_TOKEN from env"


class TestMissingProject:
    def test_run_subprocess_missing_project_root(self, tmp_path):
        result = run_subprocess(
            os.path.join(str(tmp_path), "nope"),
            "",
            "mymod.pipeline",
            run_callable="run",
            cfg={},
            prefix="subproc",
        )
        assert result == {"success": False, "reason": "subproc_not_found"}

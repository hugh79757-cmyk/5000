"""Plan 61-08 — STAP/TAP external subprocess routing integration test.

Verifies dispatcher._run_stap / _run_tap_subprocess route through
shared.subprocess_runner.run_subprocess (mock, no live external services),
and that behavior (reason prefixes, TAP tuple→dict, CLOUDFLARE_API_TOKEN
strip) is preserved.
"""

import dispatcher
import shared.paths
import shared.subprocess_runner
from dispatcher import _run_stap, _run_tap_subprocess


class TestStapRouting:
    def test_stap_delegates_to_run_subprocess(self, tmp_path, monkeypatch):
        monkeypatch.setattr(shared.paths, "STAP_ROOT", str(tmp_path))
        captured = {}

        def fake_run_subprocess(**kwargs):
            captured.update(kwargs)
            return {"success": True, "slug": "ok"}

        monkeypatch.setattr(shared.subprocess_runner, "run_subprocess", fake_run_subprocess)
        result = _run_stap("stock", {"daily_quota": 1})

        assert result == {"success": True, "slug": "ok"}
        assert captured["module_spec"] == "pipelines.stock.pipeline"
        assert captured["run_callable"] == "run"
        assert captured["prefix"] == "stap"
        assert captured["cfg"] == {"daily_quota": 1}

    def test_stap_not_found_reason(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            shared.paths, "STAP_ROOT", str(tmp_path / "does-not-exist")
        )
        result = _run_stap("stock", {})
        assert result == {"success": False, "reason": "stap_not_found"}


class TestTapRouting:
    def test_tap_delegates_to_run_subprocess(self, tmp_path, monkeypatch):
        monkeypatch.setattr(dispatcher, "TAP_ROOT", str(tmp_path))
        captured = {}

        def fake_run_subprocess(**kwargs):
            captured.update(kwargs)
            return {"success": True, "slug": "tap"}

        monkeypatch.setattr(shared.subprocess_runner, "run_subprocess", fake_run_subprocess)
        result = _run_tap_subprocess({"pipeline": "tap"})

        assert result == {"success": True, "slug": "tap"}
        assert captured["module_spec"] == "app"
        assert captured["run_callable"] == "run_publish"
        assert captured["prefix"] == "tap"
        assert captured["cfg"] is None

    def test_tap_tuple_result_converted_to_dict(self, tmp_path, monkeypatch):
        monkeypatch.setattr(dispatcher, "TAP_ROOT", str(tmp_path))

        def fake_run_subprocess(**kwargs):
            return (True, {"success": True, "slug": "tap"}, None)

        monkeypatch.setattr(shared.subprocess_runner, "run_subprocess", fake_run_subprocess)
        result = _run_tap_subprocess({"pipeline": "tap"})
        assert isinstance(result, dict)
        assert result.get("success") is True

    def test_tap_not_found_reason(self, tmp_path, monkeypatch):
        monkeypatch.setattr(dispatcher, "TAP_ROOT", str(tmp_path / "does-not-exist"))
        result = _run_tap_subprocess({})
        assert result == {"success": False, "reason": "tap_not_found"}


class TestRunnerContract:
    def test_run_subprocess_strips_cf_token(self, tmp_path, monkeypatch):
        """run_subprocess pops CLOUDFLARE_API_TOKEN from env before subprocess."""
        root = tmp_path / "proj"
        (root / "pipeline").mkdir(parents=True)
        (root / "pipeline" / "__init__.py").write_text("", encoding="utf-8")
        (root / "pipeline" / "mymod.py").write_text(
            'import os\ndef run(cfg):\n    return {"success": True, "token": os.environ.get("CLOUDFLARE_API_TOKEN")}\n',
            encoding="utf-8",
        )
        monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "should_be_stripped")
        result = shared.subprocess_runner.run_subprocess(
            project_root=str(root),
            venv_python="",
            module_spec="pipeline.mymod",
            run_callable="run",
            cfg={},
            prefix="subproc",
        )
        assert result.get("success") is True
        assert result.get("token") is None, "runner must pop CLOUDFLARE_API_TOKEN"

"""Wave-0 tests for scripts/scaffold_branch.py (Phase 61, D-05).

Behavior tests (Wave-0, written BEFORE implementation):
- scaffold_branch() creates the standard 6-module skeleton (pipeline/fetcher/topic_manager/writer/enrich/validator)
- creates a config/blogs.d/{branch}.yaml template with standard required fields + managed_by: pipeline
- wires DB path via shared/db.py get_db_path (no inline hardcoded path)
- validates branch name against ^[a-z][a-z0-9_]*$ (path/module injection safety, T-61-09-01)
- refuses to overwrite an existing branch dir (T-61-09-02)
- supports --dry-run (no files written)
- a scaffolded pipeline module imports and run(cfg) returns a dict (standard contract)

The generated skeleton is import-verifiable but NOT end-to-end publish-tested
(fetch/write/validate are placeholders; no live network/DB service invoked).
"""

import importlib
import importlib.util
import os
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent.parent / "scripts"
SCAFFOLD = SCRIPTS / "scaffold_branch.py"

STANDARD_MODULES = ("pipeline", "fetcher", "topic_manager", "writer", "enrich", "validator")


def _load_scaffold():
    spec = importlib.util.spec_from_file_location("scaffold_branch", SCAFFOLD)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def scaffold():
    return _load_scaffold()


class TestScaffoldCreatesSkeleton:
    def test_scaffold_creates_skeleton(self, scaffold, tmp_path):
        p = scaffold.scaffold_branch("testbranch", base_dir=tmp_path, config_dir=tmp_path)
        assert p == tmp_path / "pipelines" / "testbranch"
        files = {f.name for f in p.iterdir() if f.is_file()}
        for mod in STANDARD_MODULES:
            assert f"{mod}.py" in files, f"missing module: {mod}.py"
        assert "__init__.py" in files

    def test_scaffold_creates_config_template(self, scaffold, tmp_path):
        scaffold.scaffold_branch("testbranch", base_dir=tmp_path, config_dir=tmp_path)
        cfg = tmp_path / "blogs.d" / "testbranch.yaml"
        assert cfg.exists()
        text = cfg.read_text(encoding="utf-8")
        for field in (
            "id: testbranch-hugo",
            "pipeline: testbranch",
            "platform: hugo",
            "name:",
            "domain:",
            "daily_quota:",
            "schedule:",
            "status: inactive",
            "managed_by: pipeline",
        ):
            assert field in text, f"config missing field: {field}"

    def test_scaffold_wires_db_path(self, scaffold, tmp_path):
        scaffold.scaffold_branch("testbranch", base_dir=tmp_path, config_dir=tmp_path)
        src = (tmp_path / "pipelines" / "testbranch" / "pipeline.py").read_text(encoding="utf-8")
        assert "from shared.db import get_db_path" in src
        assert "get_db_path(" in src
        assert "testbranch" in src


class TestScaffoldValidatesBranchName:
    @pytest.mark.parametrize(
        "bad",
        ["../evil", "a b", "with.dot", "Uppercase", "has/hyphen", "1startsDigit", ""],
    )
    def test_rejects_invalid_names(self, scaffold, tmp_path, bad):
        with pytest.raises(ValueError):
            scaffold.scaffold_branch(bad, base_dir=tmp_path, config_dir=tmp_path)

    @pytest.mark.parametrize("good", ["car", "rap2", "my_branch", "x"])
    def test_accepts_valid_names(self, scaffold, tmp_path, good):
        scaffold.scaffold_branch(good, base_dir=tmp_path, config_dir=tmp_path)
        assert (tmp_path / "pipelines" / good / "pipeline.py").exists()


class TestScaffoldOverwriteAndDryRun:
    def test_refuses_overwrite_existing_dir(self, scaffold, tmp_path):
        d = tmp_path / "pipelines" / "dup"
        d.mkdir(parents=True)
        with pytest.raises(FileExistsError):
            scaffold.scaffold_branch("dup", base_dir=tmp_path, config_dir=tmp_path)

    def test_dry_run_writes_nothing(self, scaffold, tmp_path):
        scaffold.scaffold_branch("dryrunb", base_dir=tmp_path, config_dir=tmp_path, dry_run=True)
        assert not (tmp_path / "pipelines" / "dryrunb").exists()
        assert not (tmp_path / "blogs.d" / "dryrunb.yaml").exists()


class TestScaffoldedPipelineImport:
    def test_scaffolded_pipeline_imports_and_run_returns_dict(self, scaffold, tmp_path):
        branch = "demobranch"
        scaffold.scaffold_branch(branch, base_dir=tmp_path, config_dir=tmp_path)
        # temp pipelines/ 를 regular package 로 만들기 위해 상위 __init__.py 필요
        # (없으면 namespace package 라 repo 루트의 pipelines/ 에 밀린다).
        (tmp_path / "pipelines" / "__init__.py").write_text("", encoding="utf-8")

        # repo 루트의 'pipelines' 패키지가 이미 sys.modules 에 캐시되어 있을 수 있으므로
        # 임시로 제거하고 sys.path 앞에 tmp_path 를 넣어 생성된 패키지가 해석되게 한다.
        # 테스트 종료 후 원래 'pipelines' 를 복원한다 (다른 테스트 영향 방지).
        old_pipelines = sys.modules.pop("pipelines", None)
        old_sub = {
            k: v
            for k, v in sys.modules.items()
            if k == f"pipelines.{branch}" or k.startswith(f"pipelines.{branch}.")
        }
        for k in old_sub:
            sys.modules.pop(k, None)
        sys.path.insert(0, str(tmp_path))
        try:
            mod = importlib.import_module(f"pipelines.{branch}.pipeline")
            assert callable(getattr(mod, "run", None))
            result = mod.run({"id": f"{branch}-hugo", "pipeline": branch})
            assert isinstance(result, dict)
            assert "success" in result
            assert "reason" in result
            assert result["success"] is False
            assert result["reason"] == "no_topic"
            # get_db_path 배선 — 신규 미등록 분기라 safe fallback(None)을 반환해야 한다.
            assert mod._resolve_db_path() is None
            from shared.db import get_db_path

            assert callable(get_db_path)
        finally:
            if str(tmp_path) in sys.path:
                sys.path.remove(str(tmp_path))
            for k in old_sub:
                sys.modules[k] = old_sub[k]
            if old_pipelines is not None:
                sys.modules["pipelines"] = old_pipelines
            else:
                sys.modules.pop("pipelines", None)

    def test_scaffold_generates_run_contract(self, scaffold, tmp_path):
        scaffold.scaffold_branch("contractb", base_dir=tmp_path, config_dir=tmp_path)
        src = (tmp_path / "pipelines" / "contractb" / "pipeline.py").read_text(encoding="utf-8")
        assert "def run(cfg):" in src

"""Wave-3 tests — pipeline standard skeleton presence (Phase 61, D-01).

Stage C pilot: senior(SEAP) and rap(RAP) must each expose the standard 6-module
skeleton (pipeline / fetcher / topic_manager / writer / enrich / validator).
These tests verify module-file EXISTENCE via pkgutil, not run() invocation
(run() may require live network/DB services).

Per review: senior/rap topic_manager/enrich wrappers are pass-through placeholders;
pipeline/fetcher/writer are pre-existing; validator wraps shared.validators.
"""

import inspect
import pkgutil

import pipelines.etap as etap_pkg
import pipelines.rap as rap_pkg
import pipelines.senior as senior_pkg

STANDARD_MODULES = ("pipeline", "fetcher", "topic_manager", "writer", "enrich", "validator")


def _module_names(pkg) -> set:
    return {m.name for m in pkgutil.iter_modules(pkg.__path__)}


class TestSeniorSkeleton:
    def test_senior_exposes_six_standard_modules(self):
        names = _module_names(senior_pkg)
        for mod in STANDARD_MODULES:
            assert mod in names, f"senior missing standard module: {mod}"


class TestRapSkeleton:
    def test_rap_exposes_six_standard_modules(self):
        names = _module_names(rap_pkg)
        for mod in STANDARD_MODULES:
            assert mod in names, f"rap missing standard module: {mod}"


class TestSkeletonRunContract:
    def test_senior_run_is_callable(self):
        from pipelines.senior import pipeline
        assert callable(pipeline.run)

    def test_rap_run_is_callable(self):
        from pipelines.rap import pipeline
        assert callable(pipeline.run)


class TestEtapSkeleton:
    """ETAP (Stage D4, highest risk) standard skeleton + signature-bridge presence.

    Verifies module-file EXISTENCE via pkgutil and that the dispatcher
    inspect.signature bridge still resolves on a real topic pipeline — without
    invoking run() (run() may require live network/DB services).
    """

    def test_etap_exposes_six_standard_modules(self):
        names = _module_names(etap_pkg)
        for mod in STANDARD_MODULES:
            assert mod in names, f"etap missing standard module: {mod}"

    def test_etap_contract_helper_present(self):
        from pipelines.etap import _contract
        assert callable(_contract._normalize_result)
        assert _contract._normalize_result(True) == {"success": True}

    def test_etap_flight_run_bridge_preserved(self):
        # dispatcher._resolve_pipeline uses inspect.signature; flight is the
        # run(cfg) exception in _ETAP_BLOG_EXCEPTIONS. Assert cfg param present
        # and that its status-dict normalizes to success/reason (§3.5).
        from pipelines.etap import _contract
        import pipelines.etap.flight_pipeline as flight
        sig = inspect.signature(flight.run)
        assert "cfg" in sig.parameters
        norm = _contract._normalize_result({"status": "ok"})
        assert norm["success"] is True
        assert norm["reason"] == "ok"

    def test_etap_topic_pipelines_expose_run_adapter(self):
        import glob
        import importlib
        for f in glob.glob("pipelines/etap/*_pipeline.py"):
            if f.endswith("writer.py") or f.endswith("etap/pipeline.py"):
                continue
            modname = "pipelines.etap." + f.split("/")[-1][:-3]
            mod = importlib.import_module(modname)
            assert callable(mod.run), f"{modname}.run not callable"
            assert callable(getattr(mod, "_run_impl", None)), f"{modname} missing _run_impl"
            assert "_normalize_result" in open(f).read(), f"{modname} missing normalization"

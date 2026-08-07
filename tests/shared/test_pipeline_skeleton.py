"""Wave-3 tests — pipeline standard skeleton presence (Phase 61, D-01).

Stage C pilot: senior(SEAP) and rap(RAP) must each expose the standard 6-module
skeleton (pipeline / fetcher / topic_manager / writer / enrich / validator).
These tests verify module-file EXISTENCE via pkgutil, not run() invocation
(run() may require live network/DB services).

Per review: senior/rap topic_manager/enrich wrappers are pass-through placeholders;
pipeline/fetcher/writer are pre-existing; validator wraps shared.validators.
"""

import pkgutil

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

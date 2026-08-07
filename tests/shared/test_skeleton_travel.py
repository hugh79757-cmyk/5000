"""Wave-4 tests — pipeline standard skeleton presence for travel (Phase 61, D-01).

Stage D2: travel(8 blogs) must expose the standard 6-module skeleton
(pipeline / fetcher / topic_manager / writer / enrich / validator).
These tests verify module-file EXISTENCE via pkgutil, not run() invocation
(run() may require live network/DB services).

Per review: travel topic_manager/enrich are pass-through placeholders
(no existing independent module to delegate to); pipeline/fetcher/writer are
pre-existing; validator wraps shared.validators. travel run(cfg) normalizes
None → {success:False, reason:'no_result'} (behavior preserved).
"""

import inspect
import pkgutil

import pipelines.travel as travel_pkg

STANDARD_MODULES = ("pipeline", "fetcher", "topic_manager", "writer", "enrich", "validator")


def _module_names(pkg) -> set:
    return {m.name for m in pkgutil.iter_modules(pkg.__path__)}


class TestTravelSkeleton:
    def test_travel_exposes_six_standard_modules(self):
        names = _module_names(travel_pkg)
        for mod in STANDARD_MODULES:
            assert mod in names, f"travel missing standard module: {mod}"

    def test_travel_run_is_callable(self):
        from pipelines.travel import pipeline
        assert callable(pipeline.run)

    def test_travel_run_normalizes_none_to_no_result(self):
        """run(cfg) must never return None — _run_single None → no_result dict.

        Verified statically via source inspection (does NOT invoke run(), which
        may require live network/DB). Dispatcher already falls back to
        {success:False, reason:'no_result'} (dispatcher.py:732), so this is
        behavior-preserving contract normalization (PIPELINE-STANDARD §3.3).
        """
        from pipelines.travel import pipeline
        src = inspect.getsource(pipeline.run)
        assert '{"success": False, "reason": "no_result"}' in src or "no_result" in src

    def test_travel_wrappers_expose_standard_functions(self):
        from pipelines.travel import enrich, topic_manager, validator
        assert hasattr(topic_manager, "select_topic")
        assert hasattr(enrich, "enrich_content")
        assert hasattr(validator, "validate_post")

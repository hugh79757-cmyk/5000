"""Wave-4 tests — curation standard skeleton presence (Phase 61, D-01).

Stage D3: curation(CUAP, 15 blogs) must expose the standard 6-module skeleton
(pipeline / fetcher / topic_manager / writer / enrich / validator).
These tests verify module-file EXISTENCE via pkgutil, not run() invocation
(run() may require live network/DB services).

Per review: curation fetcher/topic_manager/validator are pass-through placeholders;
pipeline/writer are pre-existing; `enricher.py` is pre-existing and preserved —
the standard `enrich` module wires to it (additive).
"""

import pkgutil

import pipelines.curation as curation_pkg

STANDARD_MODULES = ("pipeline", "fetcher", "topic_manager", "writer", "enrich", "validator")


def _module_names(pkg) -> set:
    return {m.name for m in pkgutil.iter_modules(pkg.__path__)}


class TestCurationSkeleton:
    def test_curation_exposes_six_standard_modules(self):
        names = _module_names(curation_pkg)
        for mod in STANDARD_MODULES:
            assert mod in names, f"curation missing standard module: {mod}"

    def test_curation_preserves_existing_enricher(self):
        names = _module_names(curation_pkg)
        assert "enricher" in names, "curation enricher.py must be preserved"

    def test_curation_run_is_callable(self):
        from pipelines.curation import pipeline
        assert callable(pipeline.run)

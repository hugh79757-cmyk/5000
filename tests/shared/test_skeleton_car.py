"""Wave-4 tests — car(CAP) pipeline standard skeleton presence (Phase 61, D-01).

Stage D1: car must expose the standard 6-module skeleton
(pipeline / fetcher / topic_manager / writer / enrich / validator).
These tests verify module-file EXISTENCE via pkgutil, not run() invocation
(run() may require live network/DB services).

Per review: car fetcher/writer delegate to existing data_builder + shared.ai_writer;
enrich is a pass-through placeholder; validator wraps shared.validators.
"""

import pkgutil

import pipelines.car as car_pkg

STANDARD_MODULES = ("pipeline", "fetcher", "topic_manager", "writer", "enrich", "validator")


def _module_names(pkg) -> set:
    return {m.name for m in pkgutil.iter_modules(pkg.__path__)}


class TestCarSkeleton:
    def test_car_exposes_six_standard_modules(self):
        names = _module_names(car_pkg)
        for mod in STANDARD_MODULES:
            assert mod in names, f"car missing standard module: {mod}"


class TestCarSkeletonRunContract:
    def test_car_run_is_callable(self):
        from pipelines.car import pipeline
        assert callable(pipeline.run)


class TestCarSkeletonWrapperPresence:
    def test_fetcher_has_fetch_data(self):
        from pipelines.car import fetcher
        assert callable(fetcher.fetch_data)

    def test_writer_has_write_article(self):
        from pipelines.car import writer
        assert callable(writer.write_article)

    def test_enrich_has_enrich_content(self):
        from pipelines.car import enrich
        assert callable(enrich.enrich_content)

    def test_validator_has_validate_post(self):
        from pipelines.car import validator
        assert callable(validator.validate_post)


class TestCarSkeletonWiring:
    def test_car_db_path_centralized_via_shared_db(self):
        from shared.db import get_db_path
        expected = get_db_path("car")
        from pipelines.car import pipeline
        assert str(pipeline.CAR_DB_PATH) == expected

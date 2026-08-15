"""Regression: P계열 발행 실패 이벤트 복구 시 자동 close (작업2, phase-71e-pcode-2).

발행 성공 경로에서 P01/P02/P20 등 publish-failure 이벤트가 stale open으로 누적되지
않도록 dispatcher._close_publish_failure_events가 해당 blog의 문제들에 대해
close_publish_error_event를 호출하는지 검증한다. (라이브 ops.db는 건드리지 않는다)
"""

from unittest.mock import MagicMock, patch

import dispatcher


class FakeConn:
    """매직모의 DB 커넥션 — commit/execute가 실연산 없이 동작해 close 루프 검증만 한다."""

    def __init__(self):
        self.closed = False

    def commit(self):
        pass

    def execute(self, *a, **kw):
        return MagicMock()

    def close(self):
        self.closed = True


class TestPublishFailureAutoClose:
    def test_closes_all_publish_failure_ids(self):
        attempted = []
        fake = FakeConn()

        def _fake_close(conn, *, blog_id, problem_id, before=None):
            attempted.append(problem_id)
            return 1

        with patch.object(dispatcher.sqlite3, "connect", return_value=fake), \
             patch("shared.publish_error_events.close_publish_error_event",
                   side_effect=_fake_close):
            dispatcher._close_publish_failure_events("sector-hugo")

        assert set(attempted) == set(dispatcher._PUBLISH_FAILURE_PROBLEM_IDS)
        assert fake.closed is True  # 커넥션 정리 확인

    def test_exception_is_suppressed_but_reported(self, caplog):
        """예외는 삼키지 않고 경고로 기록해 발행 성공 경로가 중단되지 않게 한다."""
        fake = FakeConn()

        def _boom(conn, *, blog_id, problem_id, before=None):
            raise RuntimeError("db down")

        with patch.object(dispatcher.sqlite3, "connect", return_value=fake), \
             patch("shared.publish_error_events.close_publish_error_event",
                   side_effect=_boom), \
             caplog.at_level("WARNING", logger="dispatcher"):
            dispatcher._close_publish_failure_events("sector-hugo")
        assert any("close 실패" in r.message for r in caplog.records)
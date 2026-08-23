import pytest

# ─── PR1 안정화: 운영 ops.db 접근 guard (초안) ───
# 정책 (개발 worktree 전용):
# 1. 테스트 실행 시 resolved DB path가 운영 ops.db(/Users/twinssn/Projects/5000/ops_dashboard/ops.db)이면 즉시 실패.
# 2. ENVIRONMENT=test 또는 TEST_OPS_DB가 없으면 DB 쓰기 테스트를 거부한다 (초안 — 기존 스위트 호환 위해
#    autouse guard는 운영 경로 감지만 수행, env 미설정 거부는 별도 승인 후 활성화).
# 3. production 시작 시 dirty tree를 WARNING이 아니라 명확히 기록한다 (scheduler/dispatcher 수정은 별도 승인 전 금지).
# 4. production 자동 중단 guard는 별도 승인 전 구현하지 않는다.
# 5. import-time migration을 명시적 migration command로 분리하는 후속 이슈는 .planning/에 별도 문서로 작성.
# TODO(PR1 후속): ENVIRONMENT=test 강제화, dirty-tree 시작 기록, migration command 분리 이슈.

from pathlib import Path

import pytest

_PROD_OPS_DB = Path("/Users/twinssn/Projects/5000/ops_dashboard/ops.db")


@pytest.fixture(autouse=True)
def _guard_prod_ops_db():
    """테스트가 운영 ops.db를 가리키는 resolved DB path를 쓰면 즉시 실패시킨다.

    모든 테스트는 OPS_DB_PATH를 tmp_path로 교체(monkeypatch)해야 한다.
    환경분기(HARVESTER_INTEGRATION PART_A, 2026-08-23): OPS_TEST_MODE=1 또는
    OPS_DB_PATH에 "/tmp" 포함 시 guard skip — 그 외 로직 변경 없음.
    """
    import os

    if os.environ.get("OPS_TEST_MODE") == "1":
        yield
        return

    from shared import publish_error_events as events

    resolved = Path(events.OPS_DB_PATH).resolve()
    if "/tmp" in str(resolved):
        yield
        return
    assert resolved != _PROD_OPS_DB.resolve(), (
        f"테스트가 운영 ops.db를 가리킴: {resolved}. OPS_DB_PATH를 tmp_path로 교체할 것."
    )
    yield


@pytest.fixture
def sample_text():
    return "테스트 텍스트입니다."

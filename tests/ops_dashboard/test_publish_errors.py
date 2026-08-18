import base64
import os
import sqlite3

import pytest


def _auth_header():
    token = base64.b64encode(
        f"{os.environ.get('OPS_USER', 'ops')}:{os.environ.get('OPS_PASSWORD', '')}".encode()
    ).decode("ascii")
    return {"Authorization": "Basic " + token}


@pytest.fixture
def isolated_ops_db(tmp_path, monkeypatch):
    """app DB와 events DB를 같은 tmp 파일로 격리 (운영 ops.db 미접촉)."""
    from ops_dashboard import db as ops_db
    from shared import publish_error_events as events

    db_path = tmp_path / "ops.db"
    monkeypatch.setattr(ops_db, "DB_PATH", db_path)
    monkeypatch.setattr(events, "OPS_DB_PATH", db_path)
    return db_path


def _seed_events(count: int, base_blog: str = "blog") -> None:
    from shared import publish_error_events as events

    for i in range(count):
        events.record_publish_error(
            blog_id=f"{base_blog}-{i}-hugo",
            stage="no_topics" if i % 10 == 0 else "publish",
            detail=f"seed {i}",
            reason="no_topics" if i % 10 == 0 else "other",
            problem_id="P01" if i % 10 == 0 else "P02",
            retryable=False if i % 10 == 0 else True,
            pipeline="car" if i % 10 == 0 else "rap",
        )


def test_publish_errors_page_and_api(isolated_ops_db):
    from ops_dashboard.app import create_app

    app = create_app()
    client = app.test_client()
    page = client.get("/publish-errors", headers=_auth_header())
    assert page.status_code == 200
    assert b"Operational Errors" in page.data

    response = client.get("/api/publish-errors?limit=5", headers=_auth_header())
    assert response.status_code == 200
    payload = response.get_json()
    assert {"summary", "events", "total"} <= set(payload)
    assert {"total", "open", "by_problem"} <= set(payload["summary"])


def test_publish_errors_pagination(isolated_ops_db):
    _seed_events(120)
    from ops_dashboard.app import create_app

    client = create_app().test_client()

    page1 = client.get("/publish-errors?page=1", headers=_auth_header())
    assert page1.status_code == 200
    assert "총 120건 · 페이지 1/3".encode("utf-8") in page1.data

    p1 = client.get("/api/publish-errors?limit=50&offset=0", headers=_auth_header()).get_json()
    assert len(p1["events"]) == 50 and p1["total"] == 120
    p3 = client.get("/api/publish-errors?limit=50&offset=100", headers=_auth_header()).get_json()
    assert len(p3["events"]) == 20

    # 페이지 초과 요청은 마지막 페이지로 clamp
    clamped = client.get("/publish-errors?page=99", headers=_auth_header())
    assert "페이지 3/3".encode("utf-8") in clamped.data


def test_publish_errors_api_filter_total_matches_events(isolated_ops_db):
    """필터 적용 시 API total == 필터링된 events 수 (회귀: total이 비필터였던 결함)."""
    from shared import publish_error_events as events

    for i in range(5):
        events.record_publish_error(
            blog_id="blog-a-hugo", stage="publish", detail=f"a open {i}",
            reason=f"reason-a-{i}", problem_id="P02", state="open",
        )
    for i in range(3):
        events.record_publish_error(
            blog_id="blog-b-hugo", stage="publish", detail=f"b open {i}",
            reason=f"reason-b-{i}", problem_id="P02", state="open",
        )
    for i in range(2):
        events.record_publish_error(
            blog_id="blog-a-hugo", stage="deploy", detail=f"a closed {i}",
            reason="deploy", problem_id="P04", state="closed",
        )

    from ops_dashboard.app import create_app

    client = create_app().test_client()

    all_resp = client.get("/api/publish-errors?limit=50", headers=_auth_header()).get_json()
    assert all_resp["total"] == 10 and len(all_resp["events"]) == 10

    blog_a = client.get(
        "/api/publish-errors?blog_id=blog-a-hugo&limit=50", headers=_auth_header()
    ).get_json()
    assert blog_a["total"] == 7 and len(blog_a["events"]) == 7

    open_resp = client.get("/api/publish-errors?state=open&limit=50", headers=_auth_header()).get_json()
    assert open_resp["total"] == 8 and len(open_resp["events"]) == 8

    combo = client.get(
        "/api/publish-errors?blog_id=blog-a-hugo&state=open&limit=50",
        headers=_auth_header(),
    ).get_json()
    assert combo["total"] == 5 and len(combo["events"]) == 5


def test_publish_errors_classification(isolated_ops_db):
    from shared import publish_error_events as events

    # WAITING 사례: no_topics + P01 + retryable=0
    events.record_publish_error(
        blog_id="waiting-hugo", stage="no_topics", detail="no candidates",
        reason="no_topics", problem_id="P01", retryable=False, pipeline="car",
    )
    # LEGACY 사례: incident_key 없음 + pipeline 빈 값 → LEGACY_UNMERGED + UNKNOWN
    events.record_publish_error(
        blog_id="legacy-hugo", stage="publish", detail="old row",
        reason="duplicate", problem_id="P16", retryable=False, pipeline="",
    )
    conn = sqlite3.connect(str(isolated_ops_db))
    conn.execute(
        "UPDATE publish_error_events SET incident_key=NULL WHERE blog_id='legacy-hugo'"
    )
    conn.commit()
    conn.close()

    from ops_dashboard.app import create_app

    client = create_app().test_client()

    page = client.get("/publish-errors", headers=_auth_header())
    assert page.status_code == 200
    assert b"WAITING_FOR_CANDIDATES" in page.data
    assert b"LEGACY_UNMERGED" in page.data
    assert b"UNKNOWN" in page.data
    assert b"waiting-hugo" in page.data

    payload = client.get("/api/publish-errors?limit=50", headers=_auth_header()).get_json()
    by_blog = {e["blog_id"]: e for e in payload["events"]}
    assert by_blog["waiting-hugo"]["execution_status"] == "WAITING_FOR_CANDIDATES"
    assert by_blog["waiting-hugo"]["incident_label"] == "INCIDENT"
    assert by_blog["waiting-hugo"]["pipeline_label"] == "car"
    assert by_blog["legacy-hugo"]["execution_status"] == "OPEN"
    assert by_blog["legacy-hugo"]["incident_label"] == "LEGACY_UNMERGED"
    assert by_blog["legacy-hugo"]["pipeline_label"] == "UNKNOWN"
import base64
import os


def _auth_header():
    token = base64.b64encode(
        f"{os.environ.get('OPS_USER', 'ops')}:{os.environ.get('OPS_PASSWORD', '')}".encode()
    ).decode("ascii")
    return {"Authorization": "Basic " + token}


def test_publish_errors_page_and_api():
    from ops_dashboard.app import create_app

    app = create_app()
    client = app.test_client()
    page = client.get("/publish-errors", headers=_auth_header())
    assert page.status_code == 200
    assert b"Operational Errors" in page.data

    response = client.get("/api/publish-errors?limit=5", headers=_auth_header())
    assert response.status_code == 200
    payload = response.get_json()
    assert set(payload) == {"summary", "events"}
    assert {"total", "open", "by_problem"} <= set(payload["summary"])

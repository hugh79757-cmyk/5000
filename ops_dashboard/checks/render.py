"""ops_dashboard.checks.render — 렌더링 헬스체크

도메인 HTTP HEAD 요청으로 라이브 사이트 가용성을 검사한다.
"""
from __future__ import annotations

import logging
import urllib.request
import urllib.error

from ops_dashboard.checks import register_check

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 10  # seconds


@register_check("render_health")
def check_render_health(conn, blog_id: str) -> dict:
    """도메인 HTTP HEAD 요청으로 라이브 사이트 가용성 검사."""
    blog = conn.execute(
        "SELECT * FROM blog_lifecycle WHERE blog_id = ?", (blog_id,)
    ).fetchone()
    if not blog:
        return {"status": "unknown", "detail": f"Blog {blog_id} not found in lifecycle"}

    config_status = blog["config_status"]
    domain = blog["domain"]

    # 비활성 블로그 또는 도메인 없음
    if config_status in ("inactive", "disabled"):
        return {
            "status": "pass",
            "detail": f"Blog is {config_status} — render check not applicable",
            "evidence_url": "",
        }
    if not domain:
        return {
            "status": "pass",
            "detail": "No domain configured — render check not applicable",
            "evidence_url": "",
        }

    url = f"https://{domain}"
    try:
        req = urllib.request.Request(url, method="HEAD")
        req.add_header("User-Agent", "OpsDashboard/1.0")
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            status_code = resp.status
            if 200 <= status_code < 400:
                return {
                    "status": "pass",
                    "detail": f"HTTP {status_code} — site reachable",
                    "evidence_url": url,
                }
            return {
                "status": "fail",
                "detail": f"HTTP {status_code} — unexpected status",
                "evidence_url": url,
            }
    except urllib.error.HTTPError as e:
        return {
            "status": "fail",
            "detail": f"HTTP {e.code} — {e.reason}",
            "evidence_url": url,
        }
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        return {
            "status": "fail",
            "detail": f"Connection failed: {e}",
            "evidence_url": url,
        }

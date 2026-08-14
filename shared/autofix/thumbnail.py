"""THUMBNAIL-01: featureimage 를 R2 webp 로 (배치 썸네일 재생성).

scripts/batch_thumbnails.py 를 subprocess 로 호출하는 래퍼.
썸네일 재생성은 AGENTS.md 등급 규칙상 안전(grade A) 항목으로 분류.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from shared.autofix.core import WORKSPACE, logger


def fix_thumbnail_r2(site: Path, blog_id: str) -> tuple[bool, str]:
    """blog_id 사이트의 썸네일을 R2 webp 로 재생성.

    returns: (ok, message)
      - blog_id 가 배치 스크립트 site 이름과 일치한다고 가정.
    """
    script = WORKSPACE / "scripts" / "batch_thumbnails.py"
    if not script.exists():
        return False, "batch_thumbnails.py 없음 — skip"

    try:
        r = subprocess.run(
            ["python3", str(script), "--site", blog_id, "--missing-only"],
            capture_output=True, text=True, timeout=600, cwd=str(WORKSPACE)
        )
        if r.returncode == 0:
            return True, f"THUMBNAIL-01: {blog_id} 썸네일 재생성 완료 (R2 webp)"
        return False, f"THUMBNAIL-01 배치 실패: {r.stderr[:200]}"
    except subprocess.TimeoutExpired:
        return False, "THUMBNAIL-01 배치 타임아웃"
    except Exception as e:
        return False, f"THUMBNAIL-01 오류: {e}"

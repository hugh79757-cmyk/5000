"""Phase 71 (SC-4) 자동수정 코어 헬퍼.

blog_std_autofix.py 가 사용하던 공통 헬퍼(WORKSPACE, 백업, Hugo 빌드,
GA4 조회, 재검사 트리거, site 로드)를 캐노니컬하게 보관.
shared/autofix/* fixer 모듈과 blog_std_autofix.py 가 공유한다.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from shared.paths import FIVEK_ROOT  # 5000 루트 (fallback)

logger = logging.getLogger("shared.autofix")

WORKSPACE = Path("/Users/twinssn/Projects/5000")
BACKUP_TAG_PREFIX = "pre-autostd-2026-08-10"


def _blog_sites_from_config() -> list[tuple[str, str, str]]:
    """config/blogs.d/*.yaml에서 (blog_id, site_path, domain) 수집."""
    import yaml

    sites: list[tuple[str, str, str]] = []
    bd = WORKSPACE / "config" / "blogs.d"
    if not bd.is_dir():
        return sites
    for yml in sorted(bd.glob("*.yaml")):
        if yml.name.endswith(".bak") or yml.name.endswith(".bak2"):
            continue
        try:
            data = yaml.safe_load(yml.read_text(encoding="utf-8"))
        except Exception:
            continue
        blogs = data.get("blogs", [])
        if not isinstance(blogs, list):
            continue
        for b in blogs:
            bid = b.get("id", "")
            sp = b.get("site_path", "")
            dom = b.get("domain", "")
            if sp and Path(sp).is_dir():
                sites.append((bid, sp, dom))
    return sites


def backup_blog(site_path: str, blog_id: str) -> bool:
    """git tag 백업 (repo 내에서 실행). 실패 시 파일 백업."""
    site = Path(site_path)
    if not site.is_dir():
        return False
    try:
        r = subprocess.run(
            ["git", "tag", f"{BACKUP_TAG_PREFIX}-{blog_id}", "--points-at", "HEAD"],
            cwd=str(site), capture_output=True, text=True, timeout=10
        )
        if r.returncode == 0:
            logger.info(f"  backup: git tag {BACKUP_TAG_PREFIX}-{blog_id}")
            return True
    except Exception:
        pass
    layouts = site / "layouts"
    if layouts.is_dir():
        BAK = site / f".bak_layouts_{datetime.now().strftime('%Y%m%d')}"
        try:
            if not BAK.exists():
                shutil.copytree(layouts, BAK / "layouts", dirs_exist_ok=True)
            logger.info(f"  backup: {BAK}")
            return True
        except Exception as e:
            logger.warning(f"  backup 실패: {e}")
    return False


def get_ga4_id(blog_id: str, domain: str) -> str | None:
    """config/blogs.d/*.yaml에서 ga4_property 조회."""
    import yaml

    bd = WORKSPACE / "config" / "blogs.d"
    if not bd.is_dir():
        return None
    for yml in sorted(bd.glob("*.yaml")):
        if yml.name.endswith(".bak") or yml.name.endswith(".bak2"):
            continue
        try:
            data = yaml.safe_load(yml.read_text(encoding="utf-8"))
        except Exception:
            continue
        for b in data.get("blogs", []):
            if b.get("id") == blog_id:
                ga4 = b.get("ga4_property", "")
                if ga4 and str(ga4).strip():
                    return str(ga4).strip()
    return None


def build_hugo(site_path: str) -> tuple[bool, str]:
    """Hugo 빌드 (에러 0 확인)."""
    env = os.environ.copy()
    env["HUGO_THEMESDIR"] = "/Users/twinssn/Projects/shared-themes"
    try:
        r = subprocess.run(
            ["hugo", "--gc", "--minify", "--source", site_path],
            capture_output=True, text=True, timeout=120, env=env
        )
        if r.returncode == 0:
            return True, "Hugo 빌드 성공 (0에러)"
        return False, f"Hugo 빌드 실패: {r.stderr[:200]}"
    except subprocess.TimeoutExpired:
        return False, "Hugo 빌드 타임아웃"
    except Exception as e:
        return False, f"Hugo 빌드 오류: {e}"


def trigger_recheck(blog_id: str) -> bool:
    """POST /api/run-checks?blog_id={blog_id} 호출."""
    try:
        r = subprocess.run(
            ["curl", "-s", "-X", "POST", "-u",
             f"{os.environ.get('OPS_USER', 'ops')}:{os.environ.get('OPS_PASSWORD', '')}",
             f"http://localhost:5060/api/run-checks?blog_id={blog_id}"],
            capture_output=True, text=True, timeout=30
        )
        return r.returncode == 0
    except Exception:
        return False

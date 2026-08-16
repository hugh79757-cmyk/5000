"""shared.autofix — Phase 71 (SC-4) 자동수정 캐노니컬 패키지.

blog_std_autofix.py 와 Wave 5 디스패처(dispatcher._auto_fix_on_fail) 가
공유하는 fixer 모음. 각 fixer 는 agent_action 키(quality_checklist.yaml
global_standard/brand_standards 의 agent_action)로 레지스트리에 등록.

FIXERS[action_key] = callable(site: Path, blog_id: str, ga4_id: str|None)
                      -> tuple[bool, str]
"""

from __future__ import annotations

from pathlib import Path

from shared.autofix.core import (
    BACKUP_TAG_PREFIX,
    WORKSPACE,
    backup_blog,
    build_hugo,
    get_ga4_id,
    trigger_recheck,
)
from shared.autofix.r04 import fix_r04_ga4
from shared.autofix.r06 import fix_r06_fluid
from shared.autofix.r08 import fix_r08_lead
from shared.autofix.r12 import fix_r12_overrides
from shared.autofix.thumbnail import fix_thumbnail_r2
from shared.autofix.r2 import fix_r2_images
from shared.autofix.fix_draft_true import fix_draft_true
from shared.autofix.fix_featureimage_url_sanitize import fix_featureimage_url_sanitize
from shared.autofix.fix_frontmatter_missing_keys import fix_frontmatter_missing_keys

__all__ = [
    "WORKSPACE",
    "BACKUP_TAG_PREFIX",
    "backup_blog",
    "build_hugo",
    "get_ga4_id",
    "trigger_recheck",
    "fix_r04_ga4",
    "fix_r06_fluid",
    "fix_r08_lead",
    "fix_r12_overrides",
    "fix_thumbnail_r2",
    "fix_r2_images",
    "fix_draft_true",
    "fix_featureimage_url_sanitize",
    "fix_frontmatter_missing_keys",
    "FIXERS",
    "get_fixer",
]


# agent_action 키 → 통일 시그니처 래퍼
def _wrap_r04(site, blog_id, ga4_id=None):
    return fix_r04_ga4(site, ga4_id)


def _wrap_r06(site, blog_id, ga4_id=None):
    return fix_r06_fluid(site)


def _wrap_r08(site, blog_id, ga4_id=None):
    return fix_r08_lead(site)


def _wrap_r12(site, blog_id, ga4_id=None):
    return fix_r12_overrides(site)


def _wrap_thumb(site, blog_id, ga4_id=None):
    return fix_thumbnail_r2(site, blog_id)


def _wrap_r2(site, blog_id, ga4_id=None):
    return fix_r2_images(site, blog_id)


def _wrap_fm_draft(site, blog_id, ga4_id=None):
    return fix_draft_true(site, blog_id)


def _wrap_fm_feat(site, blog_id, ga4_id=None):
    return fix_featureimage_url_sanitize(site, blog_id)


def _wrap_fm_keys(site, blog_id, ga4_id=None):
    return fix_frontmatter_missing_keys(site, blog_id)


FIXERS = {
    "fix_r04": _wrap_r04,
    "fix_r06": _wrap_r06,
    "fix_r08": _wrap_r08,
    "fix_r12": _wrap_r12,
    "fix_thumbnail_r2": _wrap_thumb,
    "fix_r2_images": _wrap_r2,
    "fix_draft_true": _wrap_fm_draft,
    "fix_featureimage_url_sanitize": _wrap_fm_feat,
    "fix_frontmatter_missing_keys": _wrap_fm_keys,
}


def get_fixer(action_key: str):
    """agent_action 키로 fixer 콜러블 반환 (없으면 None)."""
    return FIXERS.get(action_key)

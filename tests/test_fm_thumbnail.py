"""Phase 73 (SC-3) FM-THUMBNAIL 단위 검증.

stock-hugo Blowfish variant(`thumbnail:`) 키가:
  1) 프론트매터 체크에서 FM-THUMBNAIL 로 탐지되는지
  2) fix_featureimage_url_sanitize 로 정화되는지 (featureimage 와 동일 경로)
  3) 정화 후 재검사가 통과(pass)되는지

라이브 블로그/배포/DB 를 건드리지 않는 격리 테스트.
"""

import re
import tempfile
from pathlib import Path

import frontmatter

import ops_dashboard.checks.frontmatter as fm_check
from shared.autofix import fix_featureimage_url_sanitize


# 토큰 반복(LLM 아티팩트) URL — check 와 동일 기준으로 위반 판정
BAD_THUMB = "https://x.com/gLozv0gLozv0gLozv0gLozv0gLozv0"
# 정화 후 기대값: 토큰 반복 1회만 남음
CLEAN_THUMB = "https://x.com/gLozv0"

POST_BODY = (
    "---\n"
    'title: "T"\n'
    'description: "D"\n'
    'date: "2026-08-16"\n'
    'slug: "s"\n'
    'tags: "a"\n'
    'thumbnail: "{thumb}"\n'
    "---\n"
    "body\n"
)


def _make_site() -> Path:
    site = Path(tempfile.mkdtemp(prefix="fm-thumb-test-"))
    posts = site / "content" / "posts" / "slug"
    posts.mkdir(parents=True)
    (posts / "index.md").write_text(
        POST_BODY.format(thumb=BAD_THUMB), encoding="utf-8"
    )
    return site


def test_fm_thumbnail_detected(monkeypatch):
    site = _make_site()
    monkeypatch.setattr(fm_check, "_find_site_path", lambda conn, blog_id: site)
    monkeypatch.setattr("ops_dashboard.db.record_check_rule", lambda *a, **k: None)
    monkeypatch.setattr("ops_dashboard.registry.get_entry", lambda rid: None)

    res = fm_check.check_frontmatter(None, "stock-hugo")
    assert res["status"] == "fail"
    assert "FM-THUMBNAIL" in res["detail"]


def test_fm_thumbnail_sanitized_and_recheck_passes(monkeypatch):
    site = _make_site()
    ok, msg = fix_featureimage_url_sanitize(site, "stock-hugo")
    assert ok is True, msg

    # 썸네일이 실제로 정화되었는지 파일에서 확인
    post = frontmatter.load(site / "content" / "posts" / "slug" / "index.md")
    assert post.metadata.get("thumbnail") == CLEAN_THUMB

    # 재검사 → 통과
    monkeypatch.setattr(fm_check, "_find_site_path", lambda conn, blog_id: site)
    monkeypatch.setattr("ops_dashboard.db.record_check_rule", lambda *a, **k: None)
    monkeypatch.setattr("ops_dashboard.registry.get_entry", lambda rid: None)
    res = fm_check.check_frontmatter(None, "stock-hugo")
    assert res["status"] == "pass"


def test_fm_thumbnail_clean_url_not_flagged():
    bad, why = fm_check._fm_url_bad(CLEAN_THUMB, "thumbnail")
    assert bad is False, why


def test_fm_thumbnail_token_repeat_flagged():
    bad, why = fm_check._fm_url_bad(BAD_THUMB, "thumbnail")
    assert bad is True
    assert "thumbnail" in why

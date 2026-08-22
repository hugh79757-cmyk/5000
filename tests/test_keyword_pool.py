"""keyword_pool 통합 테스트 (HARVESTER_FULL_INTEGRATION). Mock-only, tmp DB만 사용.

커버: 테이블 자동생성, INSERT OR IGNORE 중복방지, get_from_pool 조회+used 마킹,
pool 비었을 때 KEYWORD_MAP fallback, api_call_log 기록.
"""

import sqlite3
from unittest.mock import patch

import pytest

from pipelines.curation import keywords as kw_mod
from pipelines.curation import run_harvest
from pipelines.curation.keyword_harvester import KeywordHarvester


@pytest.fixture(autouse=True)
def _isolated_dbs(tmp_path, monkeypatch):
    """운영 DB 완전 격리 — pool db + ops.db 모두 tmp로."""
    from shared import publish_error_events as events
    monkeypatch.setattr(events, "OPS_DB_PATH", tmp_path / "ops.db")
    pool_db = str(tmp_path / "curation.db")
    monkeypatch.setattr(kw_mod, "_POOL_DB_PATH", pool_db)
    monkeypatch.setattr(run_harvest, "_pool_db", lambda: pool_db)
    return pool_db


def _rows(db, sql):
    conn = sqlite3.connect(db)
    out = conn.execute(sql).fetchall()
    conn.close()
    return out


# ── 1. keyword_pool 테이블 생성 검증 ──

def test_save_to_pool_creates_table_and_rows(_isolated_dbs):
    saved = run_harvest._save_to_pool(["무선청소기 추천", "공기청정기 필터"])
    assert saved == 2
    rows = _rows(_isolated_dbs, "SELECT blog_id, keyword, source, used FROM keyword_pool ORDER BY id")
    assert rows[0] == ("", "무선청소기 추천", "harvest", 0)
    assert rows[1][1] == "공기청정기 필터"


# ── 2. INSERT OR IGNORE 중복 방지 ──

def test_save_to_pool_ignores_duplicates(_isolated_dbs):
    assert run_harvest._save_to_pool(["중복키워드"]) == 1
    assert run_harvest._save_to_pool(["중복키워드", "새키워드"]) == 1
    total = _rows(_isolated_dbs, "SELECT COUNT(*) FROM keyword_pool")[0][0]
    assert total == 2


# ── 3. get_from_pool 조회 + used 마킹 ──

def test_get_from_pool_marks_used(_isolated_dbs):
    run_harvest._save_to_pool(["첫키워드", "둘째키워드"])
    kw = kw_mod._get_from_pool("massage-hugo")  # blog 전용 없음 → 범용('') 반환
    assert kw == "첫키워드"
    used = [r[0] for r in _rows(_isolated_dbs, "SELECT used FROM keyword_pool")]
    assert used == [1, 0]
    # 다음 호출은 두 번째(미사용) 키워드
    assert kw_mod._get_from_pool("any-hugo") == "둘째키워드"
    # 전부 소진 → None
    assert kw_mod._get_from_pool("any-hugo") is None


def test_get_from_pool_prefers_blog_specific(_isolated_dbs):
    run_harvest._save_to_pool(["범용키워드"])
    conn = sqlite3.connect(_isolated_dbs)
    conn.execute(
        "INSERT INTO keyword_pool (blog_id, keyword, source, harvested_at) VALUES ('golf-hugo', '골프특수', 'manual', datetime('now'))"
    )
    conn.commit()
    conn.close()
    assert kw_mod._get_from_pool("golf-hugo") == "골프특수"
    assert kw_mod._get_from_pool("other-hugo") == "범용키워드"


# ── 4. pool 비었을 때 KEYWORD_MAP fallback ──

def test_get_keywords_falls_back_to_keyword_map(_isolated_dbs):
    # pool 테이블 미생성 상태 — get_keywords가 정상 목록 반환해야 함
    kws = kw_mod.get_keywords("nonexistent-blog-xyz")
    assert kws == []
    known = next(b for b in kw_mod.KEYWORD_MAP if kw_mod.KEYWORD_MAP[b])
    assert kw_mod.get_keywords(known) == kw_mod.KEYWORD_MAP[known]
    assert kw_mod._get_from_pool("whatever") is None


def test_get_keywords_prefers_pool_over_map(_isolated_dbs):
    run_harvest._save_to_pool(["풀우선키워드"])
    assert kw_mod.get_keywords("fitness-hugo") == ["풀우선키워드"]


# ── 5. api_call_log 기록 (mock fetch) ──

def test_harvester_logs_api_calls_to_shared_counter(_isolated_dbs):
    calls = []

    def fake_fetch(source):
        calls.append(source)
        return {"status_code": 200, "rcode": "0", "keywords": ["kw-from-" + source]}

    h = KeywordHarvester(fetch_fn=fake_fetch, existing_keywords=set(),
                         db_path=_isolated_dbs)
    got = h.harvest(max_new=3)
    assert len(calls) >= 1 and got
    logged = _rows(_isolated_dbs, "SELECT COUNT(*) FROM api_call_log")[0][0]
    assert logged == len(calls), "fetch 1회당 api_call_log 정확히 1행"


def test_harvester_without_db_path_does_not_log(tmp_path):
    def fake_fetch(source):
        return {"status_code": 200, "rcode": "0", "keywords": []}

    h = KeywordHarvester(fetch_fn=fake_fetch, existing_keywords=set(), db_path=None)
    assert h.harvest() == []
    # db_path=None → 어떤 파일도 생성되지 않음 (조용한 스킵)
    assert not list(tmp_path.iterdir())


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))

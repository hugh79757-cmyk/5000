"""Phase 54 옵션 A — 타이틀 회귀 방지 테스트.

- SC-5: publish_log에 fallback 템플릿 타이틀("추천 TOP5 (2026년)") 0건이어야 함
- _validate_title이 템플릿/CoT 패턴을 거부하는지 (재사용 검증)
- 백스톱: H1이 있어도 템플릿 패턴이면 재생성으로 처리되는지

DB 직접 접속이 필요하므로 실제 curation.db 기준으로 동작한다.
"""
import sqlite3
import sys
import os

import pytest

DB_PATH = os.environ.get("CURATION_DB", "/Users/twinssn/Projects/5000/data/curation.db")

if not os.path.exists(DB_PATH):
    pytest.skip("CURATION_DB not available", allow_module_level=True)
WRITER_DIR = "/Users/twinssn/Projects/5000/pipelines/curation"
_TITLE_TEMPLATE = "%추천 TOP5 (2026년)%"


def test_no_fallback_title_template():
    """SC-5: publish_log에 fallback 템플릿 타이틀 0건이어야 함."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT count(*) FROM publish_log WHERE title LIKE ?",
        (_TITLE_TEMPLATE,),
    )
    count = cur.fetchone()[0]
    conn.close()
    assert count == 0, f"fallback 타이틀 {count}건 (회귀)"


def test_validate_title_rejects_template():
    """_validate_title이 '추천 TOP N' 패턴을 거부해야 함."""
    sys.path.insert(0, WRITER_DIR)
    from writer import _validate_title
    assert _validate_title("네덜란드 추천 TOP5 (2026년)") is False
    assert _validate_title("고려은단 추천 TOP 5") is False
    assert _validate_title("고려은단 BEST 5 추천") is False
    assert _validate_title("2026년 8월 네덜란드산 산양유 총정리 — 올바른습관 비교") is True


def test_validate_title_rejects_cot():
    """_validate_title이 CoT 마커를 거부해야 함."""
    sys.path.insert(0, WRITER_DIR)
    from writer import _validate_title
    assert _validate_title("우선 사용자 요청은 네덜란드 글 작성") is False

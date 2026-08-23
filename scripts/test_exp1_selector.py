"""test_exp1_selector — stale/거짓양성/게이트/파서버그 필터 검증."""
import sys, tempfile, textwrap, sqlite3
from pathlib import Path

sys.path.insert(0, "/Users/twinssn/Projects/5000")

from unittest.mock import patch
import ops_dashboard.exp1_selector as sel
from ops_dashboard.exp1_selector import select_exp1_candidates


def _make_site() -> Path:
    root = Path(tempfile.mkdtemp())
    site = root / "testsel-hugo"
    posts = site / "content" / "posts"
    for d in ("draftpost", "blocktags", "cleanpost"):
        (posts / d).mkdir(parents=True, exist_ok=True)
    (posts / "draftpost" / "index.md").write_text(
        textwrap.dedent("---\n"
                        "title: D\n"
                        "draft: true\n"
                        "tags: [x]\n"
                        "---\n\nbody\n"), encoding="utf-8")
    (posts / "blocktags" / "index.md").write_text(
        textwrap.dedent("---\n"
                        "title: T\n"
                        "tags:\n"
                        "  - uncategorized\n"
                        "---\n\nbody\n"), encoding="utf-8")
    (posts / "cleanpost" / "index.md").write_text(
        textwrap.dedent("---\n"
                        "title: C\n"
                        "tags: [x]\n"
                        "---\n\nbody\n"), encoding="utf-8")
    return site


def _make_db() -> sqlite3.Connection:
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE check_results (blog_id TEXT, check_name TEXT, status TEXT, severity TEXT)")
    rows = [
        ("testsel-hugo", "FM-DRAFT", "fail", "MINOR"),
        ("testsel-hugo", "FM-MISSINGKEYS", "fail", "MINOR"),
        ("adventure-hugo", "FM-MISSINGKEYS", "fail", "MINOR"),  # parser bug → 제외
        ("hotels-hugo", "FM-DRAFT", "fail", "MINOR"),           # gate_filtered → 제외
    ]
    db.executemany("INSERT INTO check_results VALUES (?,?,?,?)", rows)
    db.commit()
    return db


def test_all_filters():
    site = _make_site()
    db = _make_db()
    with patch.object(sel, "_find_site_path", return_value=site), \
         patch.object(sel, "get_conn", return_value=db):
        cands = select_exp1_candidates(5, checkers=["FM-DRAFT", "FM-MISSINGKEYS"])
    # testsel-hugo FM-DRAFT(draftpost 실제) 1건만
    assert len(cands) == 1, f"expected 1, got {len(cands)}: {cands}"
    c = cands[0]
    assert c.blog_id == "testsel-hugo"
    assert c.check_name == "FM-DRAFT"
    assert c.pre_recheck_status == "FAIL"
    assert c.eligible is True
    print("[PASS] stale(blocktags FP + cleanpost stale) filtered; adventure/hotels excluded; real FM-DRAFT kept")


if __name__ == "__main__":
    test_all_filters()
    print("test_exp1_selector: ALL PASS")

"""Phase 0 Task 1 진단 스크립트 READ-ONLY 보장 테스트.

스크립트가 DB/API/launchd를 변경하지 않음을 검증한다.
실제 실행 후에도 analytics.db mtime이 변하지 않아야 한다.
"""
import subprocess
import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path("/Users/twinssn/Projects/5000")
SCRIPT = ROOT / "scripts" / "diagnose_analytics.py"
DB = ROOT / "data" / "analytics.db"

# WRITE 의도 패턴 (진단 스크립트에 절대 없어야 함)
WRITE_PATTERNS = [
    r"\bINSERT\b", r"\bUPDATE\b", r"\bDELETE\b", r"\bDROP\b",
    r"\bALTER\b", r"\bCREATE\s+TABLE\b", r"\bREPLACE\s+INTO\b",
    r"\bkill\b", r"\blaunchctl\s+(unload|load|remove|stop)\b",
    r"rm\s+-f.*\.lock", r"unlink\(", r"run_local_server",
]


def test_script_has_no_write_intent():
    text = SCRIPT.read_text()
    for pat in WRITE_PATTERNS:
        assert not __import__("re").search(pat, text, __import__("re").IGNORECASE), \
            f"금지 패턴 발견: {pat}"


def test_script_runs_and_produces_json():
    before = DB.stat().st_mtime
    res = subprocess.run(
        ["/opt/homebrew/bin/python3", str(SCRIPT)],
        capture_output=True, text=True, cwd=str(ROOT), timeout=60,
    )
    assert res.returncode == 0, f"진단 실패: {res.stderr[:300]}"
    out_path = res.stdout.strip().splitlines()[0]
    report = __import__("json").loads(Path(out_path).read_text())
    assert "hang_pids" in report
    assert "db" in report
    assert "oauth_meta" in report
    # DB 미변경 검증
    after = DB.stat().st_mtime
    assert before == after, "진단이 analytics.db를 변경함 (mtime 불일치)"


def test_oauth_meta_has_no_token_values():
    """OAuth 메타데이터에 실제 access_token/refresh_token 값이 포함되지 않아야 함.

    주의: 키 이름('refresh_token', 'has_refresh_token')은 허용 — 값만 금지.
    """
    res = subprocess.run(
        ["/opt/homebrew/bin/python3", str(SCRIPT)],
        capture_output=True, text=True, cwd=str(ROOT), timeout=60,
    )
    out_path = res.stdout.strip().splitlines()[0]
    report = __import__("json").loads(Path(out_path).read_text())
    blob = __import__("json").dumps(report["oauth_meta"])
    # 실제 자격 증명 값(40자 이상 base64/hex 문자열)이 노출되지 않아야 함
    import re
    # access_token/refresh_token의 값 위치에 긴 문자열이 있는지 검사
    assert not re.search(r'"(access_token|refresh_token)"\s*:\s*"[A-Za-z0-9\-_]{20,}"', blob), \
        "OAuth 토큰 값이 노출됨"


def test_db_uses_readonly_uri():
    """DB 연결이 read-only 모드여야 함."""
    text = SCRIPT.read_text()
    assert "mode=ro" in text, "DB read-only URI 미사용"
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    row = conn.execute("SELECT COUNT(*) FROM adsense_daily").fetchone()
    assert row[0] > 0
    conn.close()

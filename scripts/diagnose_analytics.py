#!/usr/bin/env python3
"""Analytics 파이프라인 근본원인 진단 (READ-ONLY).

Phase 0 Task 1. DB(SELECT)/파일 metadata/프로세스 조회만 수행하며,
DB·API·launchd·파일을 절대 변경하지 않는다.
출력: logs/diagnose_analytics_YYYYMMDD_HHMMSS.json
"""
import json
import re
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path("/Users/twinssn/Projects/5000")
LOG_DIR = ROOT / "logs"
CREDS = Path.home() / "Projects" / "blogdex" / "credentials"


def _run(cmd: str) -> str:
    """프로세스 조회 전용 (읽기만)."""
    try:
        return subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=30
        ).stdout
    except Exception as e:
        return f"ERROR: {e}"


def collect() -> dict:
    out = {
        "collected_at": datetime.now().isoformat(timespec="seconds"),
        "hang_pids": [],
        "launchd": {},
        "python_env": {},
        "db": {},
        "oauth_meta": {},
        "network": {},
    }

    # 1) 프로세스 (hang/stale/미실행 구분용)
    ps = _run("ps -eo pid,ppid,lstart,etime,time,%cpu,stat,command")
    for line in ps.splitlines():
        if re.search(r"collect_analytics|analytics_watchdog|analytics_collector", line) \
                and "grep" not in line:
            parts = line.split(None, 6)
            if len(parts) >= 7:
                out["hang_pids"].append({
                    "pid": parts[0], "ppid": parts[1], "start": parts[2],
                    "etime": parts[3], "cpu_time": parts[4], "cpu_pct": parts[5],
                    "stat": parts[6][:1], "cmd": parts[6][:120],
                })

    # 2) launchd 상태
    out["launchd"]["state"] = _run(
        "launchctl list | grep com.5000.analytics || true"
    ).strip()
    out["launchd"]["watchdog"] = _run(
        "launchctl list | grep com.5000.analytics.watchdog || true"
    ).strip()

    # 3) Python 환경
    out["python_env"]["version"] = _run("/opt/homebrew/bin/python3 --version").strip()
    out["python_env"]["packages"] = _run(
        '/opt/homebrew/bin/python3 -c "'
        "import importlib.metadata as md;"
        "print(','.join(f'{p}={md.version(p)}' for p in "
        "['google-auth','google-api-python-client','google-analytics-data',"
        "'google-analytics-admin','requests','pyyaml']))"
        '"'
    ).strip()

    # 4) DB (SELECT만)
    db_path = ROOT / "data" / "analytics.db"
    st = db_path.stat()
    out["db"]["file_mtime"] = datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds")
    out["db"]["size_bytes"] = st.st_size
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    for tbl in ["adsense_daily", "gsc_keywords", "gsc_pages", "gsc_daily_summary", "ga4_daily", "ga4_pages"]:
        try:
            row = conn.execute(f"SELECT COUNT(*), MIN(date), MAX(date) FROM {tbl}").fetchone()
            out["db"][tbl] = {"rows": row[0], "min_date": row[1], "max_date": row[2]}
        except Exception as e:
            out["db"][tbl] = f"ERROR: {e}"
    # 계정별 (adsense)
    try:
        out["db"]["adsense_by_account"] = [
            list(r) for r in conn.execute(
                "SELECT account, COUNT(*), MIN(date), MAX(date) FROM adsense_daily GROUP BY account"
            ).fetchall()
        ]
    except Exception as e:
        out["db"]["adsense_by_account"] = f"ERROR: {e}"
    conn.close()

    # 5) OAuth 메타데이터 (값 미출력: token/refresh_token 본문 제외)
    for f in sorted(CREDS.glob("adsense_token_*.json")) + sorted(CREDS.glob("token_*_*.json")):
        if f.suffix == ".lock" or ".dead" in f.name:
            continue
        mode = oct(f.stat().st_mode & 0o777)
        meta = {"size": f.stat().st_size, "mode": mode}
        try:
            data = json.loads(f.read_text())
            meta["scopes"] = len(data.get("scopes", []))
            meta["has_refresh_token"] = bool(data.get("refresh_token"))
            meta["expiry"] = data.get("expiry")
            # 토큰 값/refresh_token 값은 절대 출력하지 않음
        except Exception as e:
            meta["read_error"] = type(e).__name__
        out["oauth_meta"][f.name] = meta

    # 6) 네트워크 (DNS 해석 + TLS 도달성, 인증 요청 없음)
    for host in ["oauth2.googleapis.com", "adsense.googleapis.com", "searchconsole.googleapis.com"]:
        ip = _run(f"dig +short {host} 2>/dev/null | head -1").strip()
        out["network"][host] = {"dns": ip or "FAIL"}
    return out


def main() -> None:
    data = collect()
    LOG_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = LOG_DIR / f"diagnose_analytics_{stamp}.json"
    dest.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    print(dest)
    print(json.dumps({
        "hang_count": len(data["hang_pids"]),
        "launchd": data["launchd"],
        "db_latest": {k: v["max_date"] if isinstance(v, dict) else v
                      for k, v in data["db"].items() if isinstance(v, dict)},
        "oauth_expiry": {k: v.get("expiry") for k, v in data["oauth_meta"].items()},
        "network_dns": {k: v["dns"] for k, v in data["network"].items()},
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
"""TOPIC_POOL_HEALTH check — 분기별 토픽 잔량 감시
ETAP: per-table *_topics exhausted=0, CAP: topics status!='exhausted', RAP: keywords status='active'
STAP/CUAP는 별도 로직 필요 — 현재는 ETAP/CAP/RAP만 정확 판정, 나머지는 스킵
"""
import sqlite3
import os
from pathlib import Path

FIVEK_ROOT = Path("/Users/twinssn/Projects/5000")

POOLS = [
    {"branch": "ETAP", "db": FIVEK_ROOT / "data/travel-en.db", "type": "etap"},
    {"branch": "CAP", "db": FIVEK_ROOT / "data/car.db", "type": "cap"},
    {"branch": "RAP", "db": FIVEK_ROOT / "data/rap.db", "type": "rap"},
]

WARN_THRESHOLD = 10
CRIT_THRESHOLD = 0

def _check_etap(db_path):
    results = []
    if not db_path.exists():
        return results
    conn = sqlite3.connect(str(db_path))
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%_topics'")
    tables = [r[0] for r in cur.fetchall()]
    for tbl in tables:
        try:
            row = conn.execute(f"SELECT SUM(CASE WHEN exhausted=0 THEN 1 ELSE 0 END), COUNT(*) FROM {tbl}").fetchone()
            avail = row[0] or 0
            total = row[1] or 0
            blog_id = tbl.replace("_topics", "-hugo")
            # special: flight_topics -> flights-hugo etc mapping fallback: use table name
            if avail <= CRIT_THRESHOLD:
                status = "critical"
            elif avail <= WARN_THRESHOLD:
                status = "warning"
            else:
                status = "pass"
            results.append({"check_name": "TOPIC_POOL_HEALTH", "blog_id": f"ETAP/{blog_id}", "result": status, "detail": f"available={avail}/{total} table={tbl}"})
        except Exception as e:
            results.append({"check_name": "TOPIC_POOL_HEALTH", "blog_id": f"ETAP/{tbl}", "result": "unknown", "detail": str(e)})
    conn.close()
    return results

def _check_cap(db_path):
    results = []
    if not db_path.exists():
        return results
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute("SELECT site_id, SUM(CASE WHEN status!='exhausted' THEN 1 ELSE 0 END) as avail, COUNT(*) as total FROM topics GROUP BY site_id").fetchall()
        for site_id, avail, total in rows:
            avail = avail or 0
            if avail <= CRIT_THRESHOLD:
                status = "critical"
            elif avail <= WARN_THRESHOLD:
                status = "warning"
            else:
                status = "pass"
            results.append({"check_name": "TOPIC_POOL_HEALTH", "blog_id": f"CAP/{site_id}", "result": status, "detail": f"available={avail}/{total}"})
    except Exception as e:
        results.append({"check_name": "TOPIC_POOL_HEALTH", "blog_id": "CAP/topics", "result": "unknown", "detail": str(e)})
    conn.close()
    return results

def _check_rap(db_path):
    results = []
    if not db_path.exists():
        return results
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute("SELECT blog_target, SUM(CASE WHEN status='active' THEN 1 ELSE 0 END) as avail, COUNT(*) as total FROM keywords GROUP BY blog_target").fetchall()
        for target, avail, total in rows:
            if not target:
                continue  # orphan 2 rows, 무시
            avail = avail or 0
            if avail <= CRIT_THRESHOLD:
                status = "critical"
            elif avail <= WARN_THRESHOLD:
                status = "warning"
            else:
                status = "pass"
            results.append({"check_name": "TOPIC_POOL_HEALTH", "blog_id": f"RAP/{target}", "result": status, "detail": f"available={avail}/{total}"})
    except Exception as e:
        results.append({"check_name": "TOPIC_POOL_HEALTH", "blog_id": "RAP/keywords", "result": "unknown", "detail": str(e)})
    conn.close()
    return results

def run_check():
    results = []
    for pool in POOLS:
        if pool["type"] == "etap":
            results.extend(_check_etap(pool["db"]))
        elif pool["type"] == "cap":
            results.extend(_check_cap(pool["db"]))
        elif pool["type"] == "rap":
            results.extend(_check_rap(pool["db"]))
    return results

if __name__ == "__main__":
    for r in run_check():
        print(f"{r['result'].upper():8s} {r['blog_id']:30s} {r['detail']}")
# TODO: runner.py에 from checks.topic_pool_health import run_check 추가

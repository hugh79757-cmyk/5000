"""5000 dispatcher — 중앙 라우터
blog_id를 받아 해당 pipeline의 run(cfg)를 호출하고,
결과를 publish_ledger에 기록한다.
"""
import sys
import os
import logging
import importlib
import sqlite3
import yaml
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, "/Users/twinssn/Projects/TAP")

from dotenv import load_dotenv
load_dotenv("/Users/twinssn/Projects/TAP/.env")
load_dotenv("/Users/twinssn/Projects/5000/.env")

from shared.telegram_notifier import send_error as _tg_error

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

PROJECT_DIR = Path(__file__).parent
CONFIG_DIR = PROJECT_DIR / "config"
LEDGER_DB = PROJECT_DIR / "data" / "content.db"

# --- STAP 파이프라인 매핑 (확장 시 여기만 추가) ---
STAP_PIPELINE_MAP = {
    "stock-hugo": "stock",
    "dividend-hugo": "dividend",
    "etf-hugo": "etf",
    "sector-hugo": "sector",
    "ipo-hugo": "ipo",
    "finance-hugo": "finance",
}


def load_blogs():
    with open(CONFIG_DIR / "blogs.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)["blogs"]


def get_blog_config(blog_id):
    for b in load_blogs():
        if b["id"] == blog_id:
            return b
    return None


# ─── 중앙 발행 기록 ───

def _record_ledger(blog_id):
    """publish_ledger에 발행 사실 기록 — 각 파이프라인 DB에서 최신 건 조회"""
    try:
        title, url = "", ""

        # STAP 블로그는 STAP DB에서 조회
        if blog_id in STAP_PIPELINE_MAP:
            stap_db = "/Users/twinssn/Projects/STAP/data/stap_content.db"
            conn_src = sqlite3.connect(stap_db)
            row = conn_src.execute(
                "SELECT title, published_url FROM articles WHERE blog_id=? ORDER BY rowid DESC LIMIT 1",
                (blog_id,)
            ).fetchone()
            if row:
                title, url = row[0], row[1]
            conn_src.close()
        else:
            # 5000 content.db에서 조회
            conn_src = sqlite3.connect(str(LEDGER_DB))
            row = conn_src.execute(
                "SELECT title, published_url FROM articles WHERE blog_id=? ORDER BY rowid DESC LIMIT 1",
                (blog_id,)
            ).fetchone()
            if row:
                title, url = row[0], row[1]
            conn_src.close()

        conn = sqlite3.connect(str(LEDGER_DB))
        conn.execute(
            "INSERT INTO publish_ledger (blog_id, title, published_url, status, created_at) VALUES (?,?,?,?,?)",
            (blog_id, title, url or "", "published", datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"ledger 기록 실패: {e}")


# ─── STAP 모듈 격리 ───

def _run_stap(stap_name, cfg):
    """STAP 파이프라인을 모듈 격리하여 실행"""
    stap_root = os.getenv("STAP_ROOT", "/Users/twinssn/Projects/STAP")

    # 1. STAP 경로를 최상위에 삽입
    if stap_root in sys.path:
        sys.path.remove(stap_root)
    sys.path.insert(0, stap_root)

    # 2. 기존 shared/pipelines 모듈 캐시 제거
    for mod_name in list(sys.modules.keys()):
        if mod_name.startswith("shared.") or mod_name.startswith("pipelines."):
            del sys.modules[mod_name]
    for pkg in ("shared", "pipelines"):
        if pkg in sys.modules:
            del sys.modules[pkg]

    # 3. 실행
    mod = importlib.import_module(f"pipelines.{stap_name}.pipeline")
    importlib.reload(mod)
    result = mod.run(cfg)

    # 4. 복원: STAP 경로 제거 + 모듈 캐시 정리
    if stap_root in sys.path:
        sys.path.remove(stap_root)
    for mod_name in list(sys.modules.keys()):
        if mod_name.startswith("shared.") or mod_name.startswith("pipelines."):
            del sys.modules[mod_name]
    for pkg in ("shared", "pipelines"):
        if pkg in sys.modules:
            del sys.modules[pkg]

    return result


# ─── 파이프라인 실행 ───

def _run_pipeline(cfg):
    """pipeline 종류에 따라 해당 모듈의 run(cfg)를 호출"""
    pipeline = cfg.get("pipeline", "")
    blog_id = cfg["id"]

    if pipeline == "car":
        from pipelines.car.pipeline import run
        return run(cfg)

    elif pipeline == "travel":
        from pipelines.travel.pipeline import run
        return run(cfg)

    elif pipeline == "senior":
        from pipelines.senior.pipeline import run
        return run(cfg)

    elif pipeline == "gap":
        from pipelines.gap.pipeline import run
        return run(cfg)

    elif pipeline == "stock":
        stap_name = STAP_PIPELINE_MAP.get(blog_id)
        if stap_name:
            return _run_stap(stap_name, cfg)
        else:
            logger.error(f"STAP 매핑 없음: {blog_id}")
            return {"success": False, "reason": "unknown_stap_blog"}

    else:
        logger.error(f"Unknown pipeline: {pipeline}")
        _tg_error(blog_id, "pipeline", f"Unknown pipeline: {pipeline}")
        return {"success": False, "reason": "unknown_pipeline"}


# ─── 메인 디스패치 ───

def dispatch(blog_id):
    """blog_id → config 조회 → pipeline 실행 → ledger 기록"""
    cfg = get_blog_config(blog_id)
    if not cfg:
        logger.error(f"Unknown blog_id: {blog_id}")
        _tg_error(blog_id, "config", "blogs.yaml에 없는 blog_id")
        return None
    if cfg.get("status") != "active":
        logger.info(f"{blog_id} is not active")
        return None

    result = _run_pipeline(cfg)

    # 결과 정규화: 모든 pipeline이 dict를 반환하도록
    if result is None:
        result = {"success": False, "reason": "no_result"}
    elif isinstance(result, str):
        # senior 등 문자열 반환 pipeline 호환
        if result in ("quota_met", "fetch_error", "no_data", "write_error",
                       "no_content", "publish_error", "config_error"):
            result = {"success": False, "reason": result}
        else:
            result = {"success": True, "reason": result}
    elif isinstance(result, bool):
        result = {"success": result}

    # 성공 시 중앙 ledger에 기록
    if result.get("success"):
        _record_ledger(blog_id)

    return result


def main():
    if len(sys.argv) < 2:
        print("usage: dispatcher.py <blog_id|report|init-db>")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "init-db":
        from shared.content_store import init_db
        init_db()
        # publish_ledger도 초기화
        conn = sqlite3.connect(str(LEDGER_DB))
        conn.execute("""CREATE TABLE IF NOT EXISTS publish_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            blog_id TEXT NOT NULL, title TEXT NOT NULL,
            published_url TEXT, status TEXT DEFAULT 'published',
            created_at TEXT NOT NULL)""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ledger_blog_date ON publish_ledger(blog_id, created_at)")
        conn.commit()
        conn.close()
        print("DB initialized")
        return

    if cmd == "report":
        try:
            from shared.monitor import send_daily_report
            send_daily_report()
        except Exception as e:
            print(f"Report failed: {e}")
        return

    dispatch(cmd)


if __name__ == "__main__":
    main()

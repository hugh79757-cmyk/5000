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
from shared.validators import sanitize_title

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
    return _load_all_blogs().get("blogs", [])



def _load_all_blogs():
    """blogs.yaml + blogs.d/*.yaml 통합 로드"""
    main_path = CONFIG_DIR / "blogs.yaml"
    with open(main_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    if "blogs" not in config:
        config["blogs"] = []
    blogs_d = CONFIG_DIR / "blogs.d"
    if blogs_d.is_dir():
        for fpath in sorted(blogs_d.glob("*.yaml")):
            with open(fpath, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            config["blogs"].extend(data.get("blogs", []))
    return config

def get_blog_config(blog_id):
    for b in load_blogs():
        if b["id"] == blog_id:
            return b
    return None


# ─── 중앙 발행 기록 ───


def _is_duplicate(blog_id: str) -> bool:
    """오늘 동일 blog_id가 이미 daily_quota만큼 ledger에 있으면 True
    (car pipeline은 articles 테이블을 사용하지 않으므로 ledger 건수 기준으로 판단)
    """
    try:
        import sqlite3
        from datetime import datetime
        config = load_config()
        blog_cfg = next(
            (b for b in config.get("blogs", []) if isinstance(b, dict) and b.get("id") == blog_id),
            None
        )
        daily_quota = blog_cfg.get("daily_quota", 50) if blog_cfg else 50
        today = datetime.now().strftime("%Y-%m-%d")
        conn = sqlite3.connect(str(LEDGER_DB))
        count = conn.execute(
            "SELECT COUNT(*) FROM publish_ledger WHERE blog_id=? AND DATE(created_at)=?",
            (blog_id, today)
        ).fetchone()[0]
        conn.close()
        return count >= daily_quota
    except Exception:
        return False

# CAP 블로그 매핑 (car.db 사용)
CAP_BLOGS = {
    "rank-hugo", "pick-hugo", "compare-hugo", "deal-hugo",
    "guide-hugo", "hotissue-hugo", "ev-hugo", "tco-hugo",
}
CAP_DB = PROJECT_DIR / "data" / "car.db"


def _record_ledger(blog_id):
    """publish_ledger에 발행 사실 기록 — 각 파이프라인 DB에서 최신 건 조회"""
    try:
        title, url, source_id = "", "", ""

        # STAP 블로그는 STAP DB에서 조회
        if blog_id in STAP_PIPELINE_MAP:
            stap_db = "/Users/twinssn/Projects/STAP/data/stap_content.db"
            conn_src = sqlite3.connect(stap_db)
            row = conn_src.execute(
                "SELECT title, published_url, source_id FROM articles WHERE blog_id=? AND status='published' ORDER BY rowid DESC LIMIT 1",
                (blog_id,)
            ).fetchone()
            if row:
                title, url, source_id = row[0], row[1], row[2] or ""
            conn_src.close()
        elif blog_id in CAP_BLOGS:
            # CAP 블로그는 car.db publish_log에서 조회
            site_key = blog_id.replace("-hugo", "")
            conn_src = sqlite3.connect(str(CAP_DB))
            row = conn_src.execute(
                "SELECT title, slug FROM publish_log WHERE site=? ORDER BY id DESC LIMIT 1",
                (site_key,)
            ).fetchone()
            if row:
                title = row[0] or ""
                url = row[1] or ""
                source_id = site_key
            conn_src.close()
        else:
            # 5000 content.db에서 조회
            conn_src = sqlite3.connect(str(LEDGER_DB))
            row = conn_src.execute(
                "SELECT title, published_url, source_id FROM articles WHERE blog_id=? AND status='published' ORDER BY rowid DESC LIMIT 1",
                (blog_id,)
            ).fetchone()
            if row:
                title, url, source_id = row[0], row[1], row[2] or ""
            conn_src.close()

        conn = sqlite3.connect(str(LEDGER_DB))
        conn.execute(
            "INSERT INTO publish_ledger (blog_id, title, published_url, status, created_at, source_id) VALUES (?,?,?,?,?,?)",
            (blog_id, title, url or "", "published", datetime.now().isoformat(), source_id)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"ledger 기록 실패: {e}")


# ─── STAP 모듈 격리 ───

def _run_stap(stap_name, cfg):
    """STAP 파이프라인을 subprocess로 완전 격리 실행"""
    import json as _json, tempfile as _tmp, subprocess as _sp
    stap_root = os.getenv("STAP_ROOT", "/Users/twinssn/Projects/STAP")
    stap_python = os.path.join(stap_root, ".venv", "bin", "python3")
    if not os.path.exists(stap_python):
        stap_python = sys.executable

    cfg_json = _json.dumps(cfg, ensure_ascii=False)
    project_env = str(PROJECT_DIR / ".env")

    runner = "\n".join([
        "import sys, json, os",
        "sys.path.insert(0, " + repr(stap_root) + ")",
        "os.chdir(" + repr(stap_root) + ")",
        "from dotenv import load_dotenv",
        "load_dotenv(os.path.join(" + repr(stap_root) + ", \".env\"), override=True)",
        "load_dotenv(" + repr(project_env) + ", override=True)",
        "cfg = json.loads(" + repr(cfg_json) + ")",
        "from pipelines." + stap_name + ".pipeline import run",
        "result = run(cfg)",
        "print(json.dumps(result or {\"success\": False, \"reason\": \"no_result\"}, ensure_ascii=False))",
    ])

    try:
        with _tmp.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(runner)
            runner_path = f.name

        proc = _sp.run(
            [stap_python, runner_path],
            capture_output=True, text=True, timeout=600, cwd=stap_root
        )
        os.unlink(runner_path)

        if proc.returncode != 0:
            logger.error(f"STAP subprocess failed: {proc.stderr[-300:]}")
            return {"success": False, "reason": "stap_subprocess_error"}

        for line in reversed(proc.stdout.strip().split("\n")):
            if line.strip().startswith("{"):
                return _json.loads(line.strip())

        logger.warning(f"STAP no JSON output: {proc.stdout[-200:]}")
        return {"success": False, "reason": "stap_no_output"}

    except _sp.TimeoutExpired:
        logger.error(f"STAP {stap_name} timeout (600s)")
        try:
            os.unlink(runner_path)
        except Exception:
            pass
        return {"success": False, "reason": "stap_timeout"}
    except Exception as e:
        logger.error(f"STAP {stap_name} error: {e}")
        return {"success": False, "reason": "stap_error"}


# ─── 파이프라인 실행 ───

def _run_pipeline(cfg):
    """pipeline 종류에 따라 해당 모듈의 run(cfg)를 호출"""
    pipeline = cfg.get("pipeline", "")
    blog_id = cfg["id"]

    if pipeline == "etap":
        if blog_id == "flights-hugo":
            from pipelines.etap.flight_pipeline import run
        elif blog_id == "cruise-hugo":
            from pipelines.etap.cruise_pipeline import run
        elif blog_id == "luxury-hugo":
            from pipelines.etap.luxury_pipeline import run
        elif blog_id == "citytours-hugo":
            from pipelines.etap.citytours_pipeline import run
        elif blog_id == "watertours-hugo":
            from pipelines.etap.watertours_pipeline import run
        elif blog_id == "hiking-hugo":
            from pipelines.etap.hiking_pipeline import run
        elif blog_id == "escape-hugo":
            from pipelines.etap.escape_pipeline import run
        elif blog_id == "extreme-hugo":
            from pipelines.etap.extreme_pipeline import run
        elif blog_id == "nightlife-hugo":
            from pipelines.etap.nightlife_pipeline import run
        elif blog_id == "ghost-hugo":
            from pipelines.etap.ghost_pipeline import run
        elif blog_id == "layover-hugo":
            from pipelines.etap.layover_pipeline import run
        elif blog_id == "nomad-hugo":
            from pipelines.etap.nomad_pipeline import run
        else:
            from pipelines.etap.pipeline import run
        # run(cfg) 또는 run() 호환
        import inspect
        if 'cfg' in inspect.signature(run).parameters or len(inspect.signature(run).parameters) > 0:
            return run(cfg)
        else:
            return run()
    elif pipeline == "curation":
        from pipelines.curation.pipeline import run
        return run(cfg)
    elif pipeline == "car":
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

    elif pipeline == "rap":
        from pipelines.rap.pipeline import run
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
    # 발행 전 중복 체크
    if _is_duplicate(blog_id):
        logger.info(f"[DEDUP] {blog_id} 동일 제목 중복 — 발행 건너뜀 (quota 소모 안 함)")
        return {"success": False, "reason": "duplicate_title"}

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

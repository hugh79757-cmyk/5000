"""5000 dispatcher — 중앙 라우터
blog_id를 받아 해당 pipeline의 run(cfg)를 호출하고,
결과를 publish_ledger에 기록한다.
"""
import importlib
import json
import logging
import os
import sqlite3
import subprocess
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import yaml

from shared.paths import FIVEK_ROOT, TAP_ROOT, STAP_ROOT

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TAP_ROOT)

from dotenv import load_dotenv

load_dotenv(os.path.expanduser("~/.env.common"))
load_dotenv(os.path.join(TAP_ROOT, ".env"))
load_dotenv(os.path.join(FIVEK_ROOT, ".env"))

import contextlib

from shared.telegram_notifier import send_error as _tg_error
from shared.problem_registry import lookup_reason
from shared.problem_monitor import get_monitor

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)



PROJECT_DIR = Path(FIVEK_ROOT)
CONFIG_DIR = PROJECT_DIR / "config"

# ── Config validation ──────────────────────────────────────────
_REQUIRED_ENV_VARS = [
    "FIVEK_ROOT", "TAP_ROOT", "STAP_ROOT", "HUGO_PATH",
]
_OPTIONAL_ENV_VARS = [
    "OPENAI_API_KEY", "TOURAPI_KEY", "BLOGGER_API_KEY",
    "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
]


def validate_config() -> list[str]:
    """Startup-time config integrity check. Returns list of warnings/errors."""
    issues = []
    for var in _REQUIRED_ENV_VARS:
        val = os.getenv(var)
        if not val:
            issues.append(f"MISSING ENV: {var}")
        elif not os.path.isdir(val):
            issues.append(f"ENV PATH NOT FOUND: {var}={val}")
    for var in _OPTIONAL_ENV_VARS:
        if not os.getenv(var):
            logger.warning(f"Optional env var not set: {var}")
    db_dir = PROJECT_DIR / "data"
    for db_name in ["content.db", "stap_content.db"]:
        db_path = db_dir / db_name
        if not db_path.exists():
            issues.append(f"DB NOT FOUND: {db_path}")
    if issues:
        for issue in issues:
            logger.error(f"[CONFIG] {issue}")
    else:
        logger.info("[CONFIG] All checks passed")
    return issues
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

# --- no_result backoff (30분 쿨다운) ---
_COOLDOWN_FILE = os.path.join(FIVEK_ROOT, "data", "cooldown.json")
_COOLDOWN_MINUTES = 30

# --- no_result 실패 횟수 추적 (에스컬레이션용) ---
_FAILURE_COUNT_FILE = os.path.join(FIVEK_ROOT, "data", "failure_count.json")
_ESCALATION_THRESHOLD = 3  # 3회 연속 실패 시 에스컬레이션 알림


def _get_cooldowns() -> dict:
    try:
        with open(_COOLDOWN_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _set_cooldown(blog_id: str) -> None:
    cooldowns = _get_cooldowns()
    cooldowns[blog_id] = datetime.now().isoformat()
    os.makedirs(os.path.dirname(_COOLDOWN_FILE), exist_ok=True)
    with open(_COOLDOWN_FILE, "w") as f:
        json.dump(cooldowns, f)


def _is_on_cooldown(blog_id: str) -> bool:
    cooldowns = _get_cooldowns()
    last = cooldowns.get(blog_id)
    if not last:
        return False
    elapsed = datetime.now() - datetime.fromisoformat(last)
    return elapsed < timedelta(minutes=_COOLDOWN_MINUTES)


def _set_daily_cooldown(blog_id: str) -> None:
    """하루 종일 cooldown — 다음 날 00:00까지 발행 중단"""
    cooldowns = _get_cooldowns()
    now = datetime.now()
    tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    cooldowns[f"daily_{blog_id}"] = tomorrow.isoformat()
    os.makedirs(os.path.dirname(_COOLDOWN_FILE), exist_ok=True)
    with open(_COOLDOWN_FILE, "w") as f:
        json.dump(cooldowns, f)


def _is_on_daily_cooldown(blog_id: str) -> bool:
    cooldowns = _get_cooldowns()
    expiry = cooldowns.get(f"daily_{blog_id}")
    if not expiry:
        return False
    try:
        return datetime.now() < datetime.fromisoformat(expiry)
    except (ValueError, TypeError):
        return False


def _get_failure_counts() -> dict:
    try:
        with open(_FAILURE_COUNT_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _increment_failure_count(blog_id: str, problem_id: str | None = None) -> int:
    """연속 실패 카운터 증분. problem_id가 주어지면 {blog_id}와
    {blog_id}:{problem_id} 확장 키 둘 다 1씩 증분 (Phase 58, W-1 카운터 공용화)."""
    counts = _get_failure_counts()
    counts[blog_id] = counts.get(blog_id, 0) + 1
    if problem_id:
        _ext_key = f"{blog_id}:{problem_id}"
        counts[_ext_key] = counts.get(_ext_key, 0) + 1
    os.makedirs(os.path.dirname(_FAILURE_COUNT_FILE), exist_ok=True)
    with open(_FAILURE_COUNT_FILE, "w") as f:
        json.dump(counts, f)
    return counts[blog_id]


def _increment_extended_failure_count(blog_id: str, problem_id: str) -> int:
    """{blog_id}:{problem_id} 확장 키만 증분 — 기존 {blog_id}는 증분하지 않음.

    no_result 계열은 기존 실패 분기가 _increment_failure_count(blog_id)로
    {blog_id}를 이미 증분하므로, 이중 증분을 피하면서 문제별 연속 카운터를
    함께 유지하기 위한 전용 경로 (Phase 58, W-1)."""
    counts = _get_failure_counts()
    _ext_key = f"{blog_id}:{problem_id}"
    counts[_ext_key] = counts.get(_ext_key, 0) + 1
    os.makedirs(os.path.dirname(_FAILURE_COUNT_FILE), exist_ok=True)
    with open(_FAILURE_COUNT_FILE, "w") as f:
        json.dump(counts, f)
    return counts[_ext_key]


def _reset_failure_count(blog_id: str) -> None:
    counts = _get_failure_counts()
    if blog_id in counts:
        del counts[blog_id]
    with open(_FAILURE_COUNT_FILE, "w") as f:
        json.dump(counts, f)


def _reset_extended_failure_keys(blog_id: str) -> None:
    """발행 성공 시 {blog_id}:{problem_id} 확장 키 일괄 삭제 (연속 카운터 누적 방지).

    기존 _reset_failure_count(blog_id)가 다루는 {blog_id} 키는 건드리지 않는다."""
    counts = _get_failure_counts()
    _prefix = f"{blog_id}:"
    _ext_keys = [k for k in counts if k.startswith(_prefix)]
    if _ext_keys:
        for _k in _ext_keys:
            del counts[_k]
        with open(_FAILURE_COUNT_FILE, "w") as f:
            json.dump(counts, f)


def load_blogs():
    return _load_all_blogs().get("blogs", [])



def _load_all_blogs():
    """blogs.yaml + blogs.d/*.yaml 통합 로드"""
    main_path = CONFIG_DIR / "blogs.yaml"
    with open(main_path, encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    if "blogs" not in config:
        config["blogs"] = []
    blogs_d = CONFIG_DIR / "blogs.d"
    if blogs_d.is_dir():
        for fpath in sorted(blogs_d.glob("*.yaml")):
            with open(fpath, encoding="utf-8") as f:
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


def _record_ledger(blog_id) -> None:
    """publish_ledger에 발행 사실 기록 — 각 파이프라인 DB에서 최신 건 조회"""
    try:
        title, url, source_id = "", "", ""

        # STAP 블로그는 STAP DB에서 조회
        if blog_id in STAP_PIPELINE_MAP:
            stap_db = os.path.join(STAP_ROOT, "data", "stap_content.db")
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
        elif blog_id in ("rap-hugo", "rap2-hugo", "rap3-hugo", "rap4-hugo", "rap5-hugo"):
            # RAP 블로그는 stap_content.db(ARTICLES_DB)에서 조회
            conn_src = sqlite3.connect(os.path.join(FIVEK_ROOT, "data", "stap_content.db"))
            row = conn_src.execute(
                "SELECT title, published_url, source_id FROM articles WHERE blog_id=? AND status='published' ORDER BY rowid DESC LIMIT 1",
                (blog_id,)
            ).fetchone()
            if row:
                title, url, source_id = row[0], row[1], row[2] or ""
            conn_src.close()
        elif blog_id in ("travel-hugo", "travel1-hugo", "travel2-hugo", "travel3-hugo", "travel4-hugo"):
            # travel 블로그는 stap_content.db articles에서 조회
            conn_src = sqlite3.connect(os.path.join(FIVEK_ROOT, "data", "stap_content.db"))
            row = conn_src.execute(
                "SELECT title, published_url, source_id FROM articles WHERE blog_id=? AND status='published' ORDER BY rowid DESC LIMIT 1",
                (blog_id,)
            ).fetchone()
            if row:
                title, url, source_id = row[0], row[1], row[2] or ""
            conn_src.close()
        else:
            # ETAP 블로그는 Hugo content/posts 최신 파일에서 title 직접 조회
            import glob as _glob
            import os as _os
            etap_site = next(
                (b.get("site_path","") for b in _load_all_blogs().get("blogs", [])
                 if b.get("id") == blog_id and b.get("pipeline") == "etap"),
                None
            )
            if etap_site:
                files = sorted(
                    _glob.glob(f"{etap_site}/content/posts/*/index.md"),
                    key=_os.path.getmtime, reverse=True
                )
                if files:
                    import re as _re
                    _content = open(files[0], encoding="utf-8").read()
                    _m = _re.search(r"""^\s*title:\s*["\']?(.+?)["\']?\s*$""", _content, _re.MULTILINE)
                    title = _m.group(1).strip() if _m else ""
                    slug = files[0].split("/")[-2]
                    domain = blog_id.replace("-hugo", "")
                    url = f"https://{domain}.techpawz.com/{slug}/"
                    source_id = slug
            else:
                # 5000 content.db에서 조회 (non-ETAP)
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
        logger.exception(f"ledger 기록 실패: {e}")


# ─── STAP 모듈 격리 ───

def _run_stap(stap_name, cfg):
    """STAP 파이프라인을 subprocess로 완전 격리 실행"""
    from shared.paths import STAP_ROOT as _STAP_ROOT
    stap_root = _STAP_ROOT
    if not os.path.isdir(stap_root):
        logger.error(f"[STAP] STAP 프로젝트를 찾을 수 없음: {stap_root}. STAP_ROOT 환경변수를 확인하세요.")
        return {"success": False, "reason": "stap_not_found"}
    import json as _json
    import subprocess as _sp
    import tempfile as _tmp
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
        "load_dotenv(os.path.join(" + repr(stap_root) + ', ".env"), override=True)',
        "load_dotenv(" + repr(project_env) + ", override=True)",
        "cfg = json.loads(" + repr(cfg_json) + ")",
        "from pipelines." + stap_name + ".pipeline import run",
        "result = run(cfg)",
        'print(json.dumps(result or {"success": False, "reason": "no_result"}, ensure_ascii=False))',
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
        logger.exception(f"STAP {stap_name} timeout (600s)")
        with contextlib.suppress(Exception):
            os.unlink(runner_path)
        return {"success": False, "reason": "stap_timeout"}
    except Exception as e:
        logger.exception(f"STAP {stap_name} error: {e}")
        return {"success": False, "reason": "stap_error"}


# ─── 파이프라인 레지스트리 ───

_ETAP_BLOG_EXCEPTIONS = {
    "flights-hugo": "pipelines.etap.flight_pipeline",
}

def _resolve_pipeline(blog_id: str, pipeline: str, cfg: dict):
    """Pipeline 모듈을 동적으로 찾아 실행"""
    if pipeline == "etap":
        if blog_id in _ETAP_BLOG_EXCEPTIONS:
            module_path = _ETAP_BLOG_EXCEPTIONS[blog_id]
        else:
            stem = blog_id.replace("-hugo", "")
            module_path = f"pipelines.etap.{stem}_pipeline"
        try:
            mod = importlib.import_module(module_path)
        except ModuleNotFoundError as _e:
            logger.warning(f"[registry] {blog_id}: {module_path} not found ({_e}), falling back to etap default")
            mod = importlib.import_module("pipelines.etap.pipeline")
        run = mod.run
        import inspect
        if "cfg" in inspect.signature(run).parameters or len(inspect.signature(run).parameters) > 0:
            return run(cfg)
        return run()

    if pipeline == "stock":
        stap_name = STAP_PIPELINE_MAP.get(blog_id)
        if stap_name:
            stap_result = _run_stap(stap_name, cfg)
            if stap_result and stap_result.get("success"):
                try:
                    from shared.quality_recorder import record_quality
                    slug = stap_result.get("slug", "")
                    title = stap_result.get("title", "")
                    metrics = {
                        "content_length": len(stap_result.get("body_md", "") or ""),
                        "paragraph_count": (stap_result.get("body_md", "") or "").count("\n\n") + 1,
                        "has_cta": bool(stap_result.get("cta_html")),
                        "has_og_image": bool(stap_result.get("thumbnail_url")),
                        "min_length_pass": len(stap_result.get("body_md", "") or "") >= 500,
                        "empty_template_count": 0,
                    }
                    record_quality(blog_id, slug, title, datetime.now().isoformat(), metrics)
                except Exception as _qe:
                    logger.warning(f"[stock] 품질 메트릭 기록 실패 (비치명적): {_qe}")
            return stap_result
        logger.error(f"STAP 매핑 없음: {blog_id}")
        return {"success": False, "reason": "unknown_stap_blog"}

    if pipeline == "tap":
        return _run_tap_subprocess(cfg)

    module_path = f"pipelines.{pipeline}.pipeline"
    try:
        mod = importlib.import_module(module_path)
    except ModuleNotFoundError:
        logger.error(f"Unknown pipeline: {pipeline}")
        _tg_error(blog_id, "pipeline", f"Unknown pipeline: {pipeline}")
        return {"success": False, "reason": "unknown_pipeline"}
    return mod.run(cfg)


def _run_tap_subprocess(cfg):
    """TAP 파이프라인을 subprocess로 완전 격리 실행"""
    if not os.path.isdir(TAP_ROOT):
        logger.error(f"[TAP] TAP 프로젝트를 찾을 수 없음: {TAP_ROOT}. TAP_ROOT 환경변수를 확인하세요.")
        return {"success": False, "reason": "tap_not_found"}
    import json
    import tempfile
    tap_root = TAP_ROOT
    tap_python = os.path.join(tap_root, "venv", "bin", "python3")
    if not os.path.exists(tap_python):
        tap_python = sys.executable
    runner_code = (
        "import sys, os; sys.path.insert(0, " + repr(tap_root) + "); "
        "os.chdir(" + repr(tap_root) + "); "
        "from dotenv import load_dotenv; "
        "load_dotenv(os.path.join(" + repr(tap_root) + ", '.env'), override=True); "
        "from app import run_publish; "
        "result = run_publish(); "
        "import json; print(json.dumps(result if isinstance(result, dict) else {'success': bool(result)}))"
    )
    runner_path = os.path.join(tempfile.gettempdir(), f"tap_runner_{uuid.uuid4().hex}.py")
    with open(runner_path, "w") as _f:
        _f.write(runner_code)
    try:
        proc = subprocess.run(
            [tap_python, runner_path],
            capture_output=True, text=True, timeout=600, cwd=tap_root
        )
        if proc.returncode != 0:
            logger.error(f"TAP subprocess failed: {proc.stderr[-300:]}")
            return {"success": False, "reason": "tap_subprocess_error"}
        out = proc.stdout.strip().split("\n")[-1]
        if out:
            try:
                return json.loads(out)
            except Exception:
                pass
        return {"success": True}
    except subprocess.TimeoutExpired:
        logger.exception("TAP timeout (600s)")
        return {"success": False, "reason": "tap_timeout"}
    except Exception as e:
        logger.exception(f"TAP error: {e}")
        return {"success": False, "reason": "tap_error"}


# ─── 파이프라인 실행 ───

def _run_pipeline(cfg):
    """Pipeline 종류에 따라 해당 모듈의 run(cfg)를 호출"""
    pipeline = cfg.get("pipeline", "")
    blog_id = cfg["id"]
    return _resolve_pipeline(blog_id, pipeline, cfg)



# ─── ETAP 중앙 빌드/배포 ───────────────────────────────────
from shared.paths import ETAP_ROOT as _ETAP_ROOT, HUGO_PATH as _HUGO_PATH, WRANGLER_PATH as _WRANGLER_PATH
ETAP_BASE = Path(_ETAP_ROOT)
HUGO      = _HUGO_PATH
WRANGLER  = _WRANGLER_PATH

ETAP_PIPELINE_BLOGS = {
    "adventure-hugo", "airlines-hugo", "airports-hugo", "bus-hugo",
    "citytours-hugo", "cruise-hugo", "culture-hugo", "daytrips-hugo",
    "deals-hugo", "dining-hugo", "escape-hugo", "esim-hugo",
    "eurail-hugo", "extreme-hugo", "ferry-hugo", "flights-hugo",
    "foodtour-hugo", "ghost-hugo", "hiking-hugo", "layover-hugo",
    "luxury-hugo", "michelin-hugo", "multiday-hugo", "nature-hugo",
    "nightlife-hugo", "nomad-hugo", "phototour-hugo", "tours-hugo",
    "trains-hugo", "transfers-hugo", "visa-hugo", "visafree-hugo",
    "walking-hugo", "watersports-hugo", "watertours-hugo",
}

# Workers 배포 대상 블로그 (Pages 대신 Workers 사용)
WORKERS_BLOGS = {
    "health-hugo",
    "pet-hugo",
    "kitchen-hugo",
    "beauty-hugo",
    "camping-hugo",
    "baby-hugo",
    "massage-hugo",
    "car-hugo",
    "homeappliance-hugo",
    "golf-hugo",
    "bike-hugo",
}

DEPLOY_LOCK = "/tmp/wrangler_deploy.lock"
DEPLOY_LOCK_TIMEOUT = 600

def _build_and_deploy_central(blog_id: str) -> bool:
    """중앙 빌드+배포 — ETAP/Workers 블로그 공용"""
    import fcntl as _fcntl
    _all = _load_all_blogs().get("blogs", [])
    _cfg = next((b for b in _all if b.get("id") == blog_id), {})
    _sp = _cfg.get("site_path", "") or str(ETAP_BASE / blog_id)
    site_path = Path(_sp)
    if not site_path.exists():
        logger.warning(f"[deploy] site_path 없음: {site_path}")
        return False
    try:
        r1 = subprocess.run(
            [HUGO, "--gc", "--minify"],
            cwd=str(site_path),
            capture_output=True, text=True
        )
        if r1.returncode != 0:
            logger.error(f"[deploy] Hugo 빌드 실패 {blog_id}\nSTDERR: {r1.stderr[-400:]}")
            return False

        # 파일 락 획득 (wrangler deploy 순차 직렬화)
        lock_file = open(DEPLOY_LOCK, "w")
        try:
            lock_acquired = False
            import time as _time
            deadline = _time.time() + DEPLOY_LOCK_TIMEOUT
            while _time.time() < deadline:
                try:
                    _fcntl.flock(lock_file, _fcntl.LOCK_EX | _fcntl.LOCK_NB)
                    lock_acquired = True
                    logger.info(f"[deploy] {blog_id} 락 획득 (wrangler deploy 직렬화)")
                    break
                except BlockingIOError:
                    _time.sleep(2)

            if not lock_acquired:
                logger.error(f"[deploy] {blog_id} 락 대기 시간 초과 ({DEPLOY_LOCK_TIMEOUT}초)")
                return False

            # wrangler auth profile 우선 — CLOUDFLARE_API_TOKEN env var 해제
            # (agent 세션에서 설정된 token이 profile보다 우선 적용됨)
            deploy_env = {k: v for k, v in os.environ.items() if k != "CLOUDFLARE_API_TOKEN"}
            deploy_env["PATH"] = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

            if blog_id in WORKERS_BLOGS:
                r2 = subprocess.run(
                    [WRANGLER, "deploy",
                     "--config", str(site_path / "wrangler.toml")],
                    cwd=str(site_path),
                    capture_output=True, text=True,
                    timeout=300,
                    env=deploy_env
                )
            else:
                r2 = subprocess.run(
                    [WRANGLER, "pages", "deploy", "public",
                     "--project-name", blog_id,
                     "--commit-dirty=true",
                     "--commit-message=publish"],
                    cwd=str(site_path),
                    capture_output=True, text=True,
                    timeout=300,
                    env=deploy_env
                )
        finally:
            try:
                _fcntl.flock(lock_file, _fcntl.LOCK_UN)
                lock_file.close()
                logger.info(f"[deploy] {blog_id} 락 해제")
            except Exception:
                pass

        if r2.returncode != 0:
            logger.error(f"[deploy] Wrangler 배포 실패 {blog_id}\nSTDERR: {r2.stderr[-400:]}")
            return False

        logger.info(f"[deploy] OK: {blog_id}")
        return True
    except Exception as e:
        logger.exception(f"[deploy] 예외 {blog_id}: {e}")
        return False

# ─── 발행 실패 기록 (publish_ledger) ───

def _record_failure(blog_id: str, stage: str, error_msg: str) -> None:
    """publish_ledger에 실패 레코드 INSERT (예외 무시)"""
    try:
        conn = sqlite3.connect(str(LEDGER_DB))
        conn.execute(
            """INSERT INTO publish_ledger
               (blog_id, title, status, stage, error_msg, created_at)
               VALUES (?, ?, 'failed', ?, ?, ?)""",
            (blog_id, stage, stage, error_msg, datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


# ─── 메인 디스패치 ───

def dispatch(blog_id):
    """blog_id → config 조회 → pipeline 실행 → ledger 기록"""
    cfg = get_blog_config(blog_id)
    if not cfg:
        logger.error(f"Unknown blog_id: {blog_id}")
        _record_failure(blog_id, "config_error", "blogs.yaml에 없는 blog_id")
        _tg_error(blog_id, "config", "blogs.yaml에 없는 blog_id")
        return None
    if cfg.get("status") != "active":
        logger.info(f"{blog_id} is not active")
        _record_failure(blog_id, "inactive", f"blog status = {cfg.get('status')}")
        return None
    # 발행 전 중복 체크
    if _is_duplicate(blog_id):
        logger.info(f"[DEDUP] {blog_id} 동일 제목 중복 — 발행 건너뜀 (quota 소모 안 함)")
        _record_failure(blog_id, "duplicate_title", "daily_quota 도달")
        return {"success": False, "reason": "duplicate_title"}

    # no_result backoff 체크
    if _is_on_cooldown(blog_id):
        logger.info(f"[SKIP] {blog_id} cooldown ({_COOLDOWN_MINUTES}분) — 발행 건너뜀")
        _record_failure(blog_id, "no_result", f"cooldown {_COOLDOWN_MINUTES}분")
        return {"success": False, "reason": "no_result"}
    # 일일 cooldown 체크 (IPO no_content 등)
    if _is_on_daily_cooldown(blog_id):
        logger.info(f"[SKIP] {blog_id} daily cooldown — 내일까지 발행 중단")
        _record_failure(blog_id, "no_result", "daily cooldown (다음 날 재시작)")
        return {"success": False, "reason": "no_result"}

    result = _run_pipeline(cfg)

    # 결과 정규화: 모든 pipeline이 dict를 반환하도록
    if result is None:
        _set_cooldown(blog_id)
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
    # 성공/실패 기록
    if result.get("success"):
        _record_ledger(blog_id)
        _reset_failure_count(blog_id)
        _reset_extended_failure_keys(blog_id)
        if blog_id in ETAP_PIPELINE_BLOGS or blog_id in WORKERS_BLOGS:
            deploy_ok = _build_and_deploy_central(blog_id)
            if not deploy_ok:
                # Phase 58 Task 5: ETAP/Workers 배포 실패 캡처 — P04 (hook=post_deploy).
                # _build_and_deploy_central은 bool만 반환하므로 Hugo/P05 vs Wrangler/P04
                # 구분 정보는 없어 기본 P04 deploy_error로 보고 (구분 배선은 후속 작업).
                logger.warning(
                    "[problem_monitor] 배포 실패 캡처: blog=%s reason=deploy_error "
                    "problem_id=P04 phase=post_deploy",
                    blog_id)
                get_monitor().report(
                    blog_id, {"reason": "deploy_error"}, phase="post_deploy", extra={})
        # STAP/Hugo 배포 실패 — success=True지만 배포는 실패한 경우
        deploy_err = result.get("deploy_error")
        if deploy_err:
            _record_failure(blog_id, "deploy", deploy_err[:300])
            _tg_error(blog_id, "deploy",
                f"[{blog_id}] Hugo빌드/Wrangler배포 실패\n"
                f"원인: {deploy_err[:200]}\n"
                f"조치: STAP/logs/deploy.log 확인 후 Hugo 테마/themesDir 점검")
    else:
        reason = result.get("reason", "unknown")
        if reason not in ("quota_met", "already_running", "duplicate_title"):
            _record_failure(blog_id, reason, f"pipeline 실패: {reason}")
            # no_result/데이터부족 등은 텔레그램 전송 (침묵 방지)
            if reason in ("no_result", "no_data", "fetch_error", "no_content"):
                # IPO 데이터가 없으면 하루 cooldown + 1회 알림 (재시도 없음)
                if blog_id == "ipo-hugo" and reason == "no_content":
                    _tg_error(blog_id, reason,
                        f"[{blog_id}] IPO/증권신고서 데이터 없음 — 오늘 발행 중단\n"
                        f"다음 데이터 갱신을 기다립니다 (내일 00:00 재시작)")
                    _set_daily_cooldown(blog_id)
                else:
                    count = _increment_failure_count(blog_id)
                    _tg_error(blog_id, reason, f"pipeline {reason}: 발행 가능 데이터 없음 (연속 {count}회)")
                    if count >= _ESCALATION_THRESHOLD:
                        _set_daily_cooldown(blog_id)
                        _tg_error(blog_id, "escalation",
                            f"[{blog_id}] {count}회 연속 {reason} — 오늘 발행 중단, 내일 00:00 재시작")
            elif reason in ("duplicate_slug", "duplicate_source_id"):
                existing = result.get("existing_url", "")
                dup_type = reason.replace("duplicate_", "")
                _tg_error(blog_id, reason,
                    f"[{blog_id}] 중복 발행 방지 — {dup_type} 중복\n"
                    f"기존글: {existing or 'slug 확인 필요'}\n"
                    f"데이터 갱신을 위해 STAP collect_all() 자동 실행합니다.")
                # STAP collect_all 자동 실행 (데이터 갱신)
                try:
                    _STAP_DIR = "/Users/twinssn/Projects/STAP"
                    _stap_py = os.path.join(_STAP_DIR, "pipelines", "data_collector.py")
                    if os.path.isfile(_stap_py):
                        subprocess.Popen(
                            [os.path.join(_STAP_DIR, ".venv", "bin", "python3"), _stap_py],
                            cwd=_STAP_DIR,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                        logger.info(f"[{blog_id}] STAP collect_all() 백그라운드 실행 시작")
                except Exception as _e:
                    logger.warning(f"[{blog_id}] STAP collect_all 실행 실패: {_e}")
            # ── Phase 58 Task 5 (additive): reason → 문제 매핑 + 모니터 훅 ──
            # 기존 _tg_error 발송은 유지, monitor.report는 병렬 (쿨다운이 중복 흡수).
            _spec = lookup_reason(reason)
            if _spec is None:
                logger.warning(
                    "unknown failure reason: %s (blog=%s) — monitor 발송 생략",
                    reason, blog_id)
            else:
                if reason in ("no_result", "no_data", "fetch_error", "no_content"):
                    # 기존 no_result 분기가 _increment_failure_count(blog_id)로
                    # {blog_id}를 이미 증분 — 이중 증분을 피하고 확장 키만 동기화 (W-1).
                    _increment_extended_failure_count(blog_id, _spec.problem_id)
                    _consec = _get_failure_counts().get(blog_id, 0)
                else:
                    _consec = _increment_failure_count(blog_id, _spec.problem_id)
                logger.warning(
                    "[problem_monitor] result_parse 매핑: blog=%s reason=%s "
                    "problem_id=%s consecutive=%s",
                    blog_id, reason, _spec.problem_id, _consec)
                get_monitor().report(
                    blog_id,
                    {"reason": reason},
                    phase=_spec.hook,
                    extra={"consecutive_failures": _consec})
    return result


def _send_quality_report() -> None:
    """발행 품질 주간 리포트 출력"""
    import sqlite3
    from datetime import datetime, timedelta

    cutoff = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    conn = sqlite3.connect(str(LEDGER_DB))
    
    # 최근 7일간 발행 통계
    rows = conn.execute(
        "SELECT blog_id, status, created_at FROM publish_ledger WHERE DATE(created_at) >= ?",
        (cutoff,)
    ).fetchall()
    
    if not rows:
        print("최근 7일간 발행 기록 없음")
        conn.close()
        return

    total = len(rows)
    success = sum(1 for r in rows if r[1] == "published")
    failed = total - success
    
    # 블로그별 통계
    blog_stats = {}
    for blog_id, status, created_at in rows:
        if blog_id not in blog_stats:
            blog_stats[blog_id] = {"total": 0, "success": 0, "no_result": 0}
        blog_stats[blog_id]["total"] += 1
        if status == "published":
            blog_stats[blog_id]["success"] += 1
        elif status == "failed":
            blog_stats[blog_id]["no_result"] += 1

    print("=== 발행 품질 리포트 (최근 7일) ===")
    print(f"총 발행: {total} | 성공: {success} | 실패: {failed}")
    print()
    print("블로그별 통계:")
    for blog_id, stats in sorted(blog_stats.items()):
        rate = (stats["success"] / stats["total"] * 100) if stats["total"] > 0 else 0
        print(f"  {blog_id}: {stats['total']}건 (성공률 {rate:.1f}%, no_result {stats['no_result']}회)")
    
    # no_result 상위 5개
    no_result_sorted = sorted(
        [(b, s["no_result"]) for b, s in blog_stats.items() if s["no_result"] > 0],
        key=lambda x: x[1], reverse=True
    )[:5]
    
    if no_result_sorted:
        print()
        print("no_result 빈도 TOP 5:")
        for blog_id, count in no_result_sorted:
            print(f"  {blog_id}: {count}회")

    conn.close()


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: dispatcher.py <blog_id|report|init-db> [--quality]")
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
        if len(sys.argv) > 2 and sys.argv[2] == "--quality":
            _send_quality_report()
        else:
            try:
                from shared.monitor import send_daily_report
                send_daily_report()
            except Exception as e:
                print(f"Report failed: {e}")
        return

    import json
    result = dispatch(cmd)
    if result is not None:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(json.dumps({"success": False, "reason": "dispatch_returned_none"}))


if __name__ == "__main__":
    main()

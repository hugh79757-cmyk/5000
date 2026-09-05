"""5000 dispatcher — 중앙 라우터
blog_id를 받아 해당 pipeline의 run(cfg)를 호출하고,
결과를 publish_ledger에 기록한다.

# feedback hook (stub, Phase 64-04 — no wiring yet):
# from shared.rule_feedback import record_feedback
# record_feedback(type="false_positive", rule_id="C01", blog_id=blog_id,
#                 slug=slug, severity="MAJOR", gate_decision="blocked",
#                 reason="manual review: gate blocked but content ok",
#                 detected_by="human", status="open")
# record_feedback(type="false_negative", rule_id="C09", blog_id=blog_id,
#                 slug=slug, severity="CRITICAL", gate_decision="passed",
#                 reason="live check found issue but gate passed",
#                 detected_by="agent", status="open")

# Charter: run python -m shared.charter_checklist --job deploy before mass-mod
"""
import importlib
import json
import logging
import os
import sqlite3
import subprocess
import sys
import traceback
from datetime import datetime, timedelta
from pathlib import Path

import yaml

from shared.paths import FIVEK_ROOT, TAP_ROOT, STAP_ROOT, SHARED_THEMES
from shared.publish_slot import (
    acquire_publish_slot,
    release_publish_slot,
    get_inherited_slot_info,
    MAX_CONCURRENT_PUBLISH,
)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TAP_ROOT)

from dotenv import load_dotenv

load_dotenv(os.path.expanduser("~/.env.common"))
load_dotenv(os.path.join(TAP_ROOT, ".env"))
load_dotenv(os.path.join(FIVEK_ROOT, ".env"))


from shared.telegram_notifier import send_error as _tg_error
from shared.problem_registry import lookup_reason
from shared.problem_monitor import get_monitor
from shared.daily_summary import record_event as _record_summary_event, init_daily_summary_tables
from shared.notification_debounce import should_push as _debounce_push, init_debounce_tables
# quality live gate import (optional, safe import)
try:
    from ops_dashboard.checks.content_quality_live import run_live_check
    _QUALITY_LIVE_AVAILABLE = True
except Exception:
    _QUALITY_LIVE_AVAILABLE = False

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

# Phase 73 SC-1: STAP 파이프라인 이름 집합 (중앙 배포 경로 포함용, 1회 정의).
STAP_PIPELINE_BLOGS = set(STAP_PIPELINE_MAP.values())

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
                # CUAP(curation pipeline) 블로그는 content.db articles에 과거 레코드가
                # 남아 있어 잘못된 title이 조회될 수 있음 (2026-08-07 사고:
                # publish_ledger 57823/57824/57826/57827/57828이 3~4월 옛 articles title로
                # 기록됨) — curation 블로그는 아래 CUAP 분기에서 curation.db publish_log
                # 최신 건을 직접 조회하도록 건너뜀.
                blog_cfg = next(
                    (b for b in _load_all_blogs().get("blogs", [])
                     if b.get("id") == blog_id),
                    None
                )
                if not (blog_cfg and blog_cfg.get("pipeline") == "curation"):
                    conn_src = sqlite3.connect(str(LEDGER_DB))
                    row = conn_src.execute(
                        "SELECT title, published_url, source_id FROM articles WHERE blog_id=? AND status='published' ORDER BY rowid DESC LIMIT 1",
                        (blog_id,)
                    ).fetchone()
                    if row:
                        title, url, source_id = row[0], row[1], row[2] or ""
                    conn_src.close()

        if not title and not url:
            # CUAP 블로그는 curation.db publish_log에 기록됨 (STRUCT-07:
            # content.db articles에는 CUAP 레코드가 없어 title이 항상 빈 값이었음.
            # 단, 과거 레코드가 남아있는 curation 블로그는 위 분기에서 articles
            # 조회를 건너뛰므로 여기까지 도달함)
            try:
                conn_cu = sqlite3.connect(os.path.join(FIVEK_ROOT, "data", "curation.db"))
                row_cu = conn_cu.execute(
                    "SELECT title, slug FROM publish_log WHERE blog_id=? ORDER BY id DESC LIMIT 1",
                    (blog_id,)
                ).fetchone()
                if row_cu:
                    title = row_cu[0] or ""
                    url = row_cu[1] or ""
                    source_id = blog_id
                conn_cu.close()
            except Exception as e:
                logger.warning(f"[lead_migration] curation DB close 실패: {e}")
                pass

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

# 발행 실패 계열 P-이벤트 — 발행 성공 시 자동 close 대상 (stale open 누적 방지).
_PUBLISH_FAILURE_PROBLEM_IDS = ("P01", "P02", "P20", "P26", "P27", "P28", "P30")


def _close_publish_failure_events(blog_id: str) -> None:
    """해당 blog의 open 발행 실패 이벤트(P01/P02/P20 등)를 closed로 전환.

    발행 성공 직후 dispatcher 호출부가 호출한다. 예외는 삼키지 않고 경고로 기록
    (현재 발행 성공 경로에 영향 없어야 하므로 격리).
    """
    from shared.publish_error_events import close_publish_error_event
    try:
        _conn = sqlite3.connect(str(PROJECT_DIR / "ops_dashboard" / "ops.db"))
        try:
            for _pid in _PUBLISH_FAILURE_PROBLEM_IDS:
                _closed = close_publish_error_event(_conn, blog_id=blog_id, problem_id=_pid)
                if _closed:
                    logger.info(f"[pcode] 발행 실패 이벤트 close: {blog_id}/{_pid} ({_closed}건)")
        finally:
            _conn.close()
    except Exception as _e:
        logger.warning(f"[pcode] 발행 실패 이벤트 close 실패: {blog_id}: {_e}")


def _deploy_log_hint(blog_id: str) -> str:
    """배포 실패 푸시에 알맞은 deploy.log 경로 힌트.

    STAP 계열(주식/배당/ETF/섹터/IPO/금융)은 STAP/logs/deploy.log, 그 외 내부
    블로그(CAP/SEAP 등)는 5000 중앙 logs/deploy.log를 가리킨다. 하드코딩된
    'STAP/logs/deploy.log'는 SEAP senior-hugo를 STAP으로 오귀속시키는 부수버그 해소.
    """
    if blog_id in STAP_PIPELINE_MAP:
        return "STAP/logs/deploy.log"
    return "logs/deploy.log (5000 중앙)"


def _is_site_live(blog_id: str, timeout: int = 5) -> bool:
    """배포 알람 오탐 방지용 사이트 생존 확인.

    사이트가 정상 서빙(HTTP 200) 중이면 배포 실패는 transient일 가능성이 높아
    즉각 CRITICAL 페이징을 건너뛴다. 조회 자체가 실패하면 False를 반환해
    기존 페이징 경로로 폴백(fail-safe).
    """
    try:
        cfg = get_blog_config(blog_id)
    except Exception:
        return False
    domain = (cfg or {}).get("domain", "")
    if not domain:
        return False
    url = domain if domain.startswith("http") else f"https://{domain}"
    try:
        import urllib.request
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 400
    except Exception:
        return False


def _run_stap(stap_name, cfg):
    """STAP 파이프라인을 subprocess로 완전 격리 실행 (shared runner 위임)"""
    from shared.paths import STAP_ROOT as _STAP_ROOT
    from shared.subprocess_runner import run_subprocess
    stap_root = _STAP_ROOT
    if not os.path.isdir(stap_root):
        logger.error(f"[STAP] STAP 프로젝트를 찾을 수 없음: {stap_root}. STAP_ROOT 환경변수를 확인하세요.")
        return {"success": False, "reason": "stap_not_found"}
    stap_python = os.path.join(stap_root, ".venv", "bin", "python3")
    return run_subprocess(
        project_root=stap_root,
        venv_python=stap_python,
        module_spec=f"pipelines.{stap_name}.pipeline",
        run_callable="run",
        cfg=cfg,
        timeout=600,
        prefix="stap",
        blog_id=cfg["id"],
    )


# ─── 파이프라인 레지스트리 ───

_ETAP_BLOG_EXCEPTIONS = {
    "flights-hugo": "pipelines.etap.flight_pipeline",
    # tour-hugo: tour_pipeline.py 준비됨(중복 이슈로 승인 대기) — 승인 전까지 기존 fallback 유지.
    # 승인 시 이 한 줄 삭제하면 dispatcher 관례(tour-hugo→tour_pipeline)가 자동 활성화됨.
    "tour-hugo": "pipelines.etap.pipeline",
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
    """TAP 파이프라인을 subprocess로 완전 격리 실행 (shared runner 위임)"""
    from shared.subprocess_runner import run_subprocess
    if not os.path.isdir(TAP_ROOT):
        logger.error(f"[TAP] TAP 프로젝트를 찾을 수 없음: {TAP_ROOT}. TAP_ROOT 환경변수를 확인하세요.")
        return {"success": False, "reason": "tap_not_found"}
    tap_python = os.path.join(TAP_ROOT, "venv", "bin", "python3")
    result = run_subprocess(
        project_root=TAP_ROOT,
        venv_python=tap_python,
        module_spec="app",
        run_callable="run_publish",
        cfg=None,
        timeout=600,
        prefix="tap",
        blog_id=cfg["id"],
    )
    # TAP run_publish()는 (bool, result, error) 튜플을 반환할 수 있음 — dict 정규화.
    # 원래 subprocess runner가 했던 것과 동일하게 비-dict는 {'success': bool(...)}로 변환.
    if not isinstance(result, dict):
        return {"success": bool(result)}
    return result


# ─── 파이프라인 실행 ───

def _run_pipeline(cfg):
    """Pipeline 종류에 따라 해당 모듈의 run(cfg)를 호출"""
    pipeline = cfg.get("pipeline", "")
    blog_id = cfg["id"]
    return _resolve_pipeline(blog_id, pipeline, cfg)


def _resolved_pipeline_for(blog_id: str, cfg: dict) -> str:
    """실제 실행된 pipeline 값 (cfg의 빈 fallback 대신 사용).

    - STAP 블로그는 cfg.pipeline("stock")이 아니라 실제 실행 모듈 파이프라인
      이름(STAP_PIPELINE_MAP 값, 예: sector-hugo → "sector")을 반환.
    - 그 외 블로그는 cfg의 pipeline (CAP car 블로그는 "car").
    - 어느 쪽에도 없으면 "" (해당 블로그에 해석 가능한 pipeline 부재).
    """
    return STAP_PIPELINE_MAP.get(blog_id) or cfg.get("pipeline") or ""



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
    "walking-hugo", "watersports-hugo", "watertours-hugo", "tour-hugo",
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
    "fitness-hugo",
    "best-electronics-hugo",
    "best-sports-hugo",
    "best-books-hugo",
    "best-toys-hugo",
    "best-stationery-hugo",
    "best-pet-supplies-hugo",
    "best-unisex-clothing-hugo",
}

DEPLOY_LOCK = "/tmp/wrangler_deploy.lock"
DEPLOY_LOCK_TIMEOUT = 180  # 스케줄러 600s 킬 이전 포기 → P04로 빠지고 재시도.
# updated 2026-08-29: Hugo build timeout 180s 추가.
# 추정 예산: Hugo(180s) + lock wait(≤180s) + wrangler(≤120s) = 480s < 600s,
# content gen + preflight 에 120s 여백 확보.


def _compute_baseline_keys(posts_dir: "Path") -> set:
    """해당 블로그 전체 포스트에서 ≥80% 출현하는 프런트매터 키 집합.

    패리티 게이트 기준: 신규 포스트가 이 집합의 키를 누락하면 차단.
    """
    from collections import Counter
    import yaml as _y
    cnt = Counter()
    total = 0
    for md in posts_dir.rglob("*.md"):
        try:
            txt = md.read_text(encoding="utf-8", errors="replace")
            i = txt.find("---")
            j = txt.find("---", i + 3)
            if i < 0 or j < 0:
                continue
            fm = _y.safe_load(txt[i + 3:j]) or {}
            if isinstance(fm, dict):
                total += 1
                for k in fm.keys():
                    cnt[k] += 1
        except Exception:
            pass
    if total == 0:
        return set()
    return {k for k, c in cnt.items() if c / total >= 0.8}


def _stored_points_to_gate_data(raw_json):
    """Phase 72 W4 T4.2: topics.unique_data_points 저장 JSON → S03 gate 입력 변환.

    저장 스키마는 data_adapters 포인트({label,value,unit,source_table}) 배열의 JSON.
    각 포인트를 {label: value} dict로 변환해 unique_data_points_gate가 price/date/
    entity 키로 인식할 수 있게 한다. 파싱 실패·빈 값은 {} 반환(폴백 경로 보존).
    """
    try:
        pts = json.loads(raw_json) if raw_json else []
    except (TypeError, ValueError):
        return {}
    items = []
    for p in pts if isinstance(pts, list) else []:
        if isinstance(p, dict) and p.get("label") and p.get("value") not in (None, ""):
            items.append({str(p["label"]): p["value"]})
    return {"stored_unique_data_points": items} if items else {}


def preflight_check(blog_id: str) -> dict:
    """배포 전 콘텐츠 무결성 프리플라이트 체크.

    C01(MAJOR warn-only)/C02(CRITICAL)/C04(CRITICAL)/C09(CRITICAL) 검사.
    S01~S05(CRITICAL) Phase 70 Wave 1 품질 게이트 검사.
    C06/C08 placeholder (미구현, 주석 유지). blocked는 CRITICAL 위반만.

    Phase 72 W4: S03/S04 위반 시 blocked=True (기존 warn-only에서 전환).
    kill-switch: 환경변수 QUALITY_ENFORCE_S03_S04=0 → warn-only 복귀.

    Returns:
        {"blocked": bool, "violations": list[dict], "reason": str}
        - blocked=True: CRITICAL 위반 시 배포 중단
        - violations: [{rule_id, slug, severity, detail}, ...]
    """
    import json
    import re
    from datetime import datetime
    from pathlib import Path

    from shared.paths import FIVEK_ROOT

    violations = []
    blocked = False

    # Phase 72 W4 T4.2: S03/S04 blocking kill-switch.
    # "0"이면 기존 warn-only 동작(위반 기록만, blocked 미설정) — 재배포 없이 즉시 복귀.
    _enforce_s03_s04 = os.getenv("QUALITY_ENFORCE_S03_S04", "1") == "1"
    # 구조 고정 블로그(adventure/kitchen)는 S04 미치환 마커 hard-block 제외(warn-only).
    # 해당 블로그는 템플릿 구조가 고정이라 정상 발행분도 S04 위반으로 오탐 → 별도 튜닝 과제(B).
    _s04_warn_only_blogs = ("adventure-hugo", "kitchen-hugo")

    # 대상 블로그 site_path 확인
    _all_blogs = _load_all_blogs().get("blogs", [])
    _cfg = next((b for b in _all_blogs if b.get("id") == blog_id), {})
    site_path = Path(_cfg.get("site_path", "")) if _cfg.get("site_path") else None
    if not site_path or not site_path.exists():
        return {"blocked": False, "violations": [],
                "reason": f"site_path 없음: {blog_id}"}

    # 최근 발행된 포스트 목록 확인 (content/posts/)
    posts_dir = site_path / "content" / "posts"
    if not posts_dir.exists():
        return {"blocked": False, "violations": [],
                "reason": f"posts_dir 없음: {posts_dir}"}

    # X5(2026-08-21): 패리티 기준 키 집합 (블로그 전체 포스트 ≥80% 출현)
    _baseline_keys = _compute_baseline_keys(posts_dir)

    # 최근 7일 내 생성된 포스트 추출 (파일 mtime 기준)
    cutoff = datetime.now().timestamp() - 7 * 86400
    recent_posts = []
    for md_file in posts_dir.rglob("*.md"):
        if md_file.stat().st_mtime >= cutoff:
            recent_posts.append(md_file)

    if not recent_posts:
        return {"blocked": False, "violations": [],
                "reason": "최근 7일 내 발행 포스트 없음 (skip)"}

    # 각 포스트 검사
    # ponytail: corpus를 포스트 루프 밖에서 1회만 구축(기존: 포스트마다 전체 재스캔 →
    # 301포스트×300파일 I/O로 900s scheduler kill, tour-hugo P25). 상한 캡=200 샘플.
    _S_CORPUS_CAP = 200
    corpus_by_file = {}
    for other_md in posts_dir.rglob("*.md"):
        try:
            other_content = other_md.read_text(encoding="utf-8", errors="replace")
            other_body_start = other_content.find("---\n", 4)
            if other_body_start > 0:
                other_body = other_content[other_body_start + 4:]
                if len(other_body) > 200:
                    corpus_by_file[other_md] = other_body
        except Exception:
            pass

    _total_corpus = len(corpus_by_file)
    if _total_corpus > _S_CORPUS_CAP:
        logger.info("[preflight] corpus %d건 → cap %d건 샘플링 (blog=%s)" % (_total_corpus, _S_CORPUS_CAP, blog_id))

    for md_file in recent_posts:
        content = md_file.read_text(encoding="utf-8", errors="replace")
        slug = md_file.parent.name
        # 자기 자신 제외한 corpus — 루프 밖 1회 구축 재사용.
        # ponytail: 상한 200 초과 시 stride 샘플링(전 기간 골고루) — 301코퍼스
        # 전량 TF-IDF는 포스트당 ~0.8s×301로 900s kill 유발(tour-hugo P25).
        corpus = [b for f, b in corpus_by_file.items() if f != md_file]
        if len(corpus) > _S_CORPUS_CAP:
            _step = len(corpus) // _S_CORPUS_CAP or 1
            corpus = corpus[::_step][:_S_CORPUS_CAP]

        # --- C01: 곡선따옴표 (MAJOR, warn-only) ---
        # reuse ops_dashboard/checks/content_integrity.py _check_c01 char set
        # \u2018\u2019\u201c\u201d inclusion — severity lookup SEED_STANDARD_RULES
        _C01_CURVED_SINGLE = ["\u2018", "\u2019"]
        _C01_CURVED_DOUBLE = ["\u201c", "\u201d"]
        _c01_found = []
        if any(c in content for c in _C01_CURVED_SINGLE):
            _c01_found.append("곡선따옴표(' ')")
        if any(c in content for c in _C01_CURVED_DOUBLE):
            _c01_found.append('곡선따옴표(" ")')
        if _c01_found:
            # severity-aware: lookup SEED_STANDARD_RULES — C01 is MAJOR, blocked only if CRITICAL
            _c01_severity = "MAJOR"
            try:
                from ops_dashboard.db import SEED_STANDARD_RULES as _SEED
                for _r in _SEED:
                    if _r.get("rule_id") == "C01":
                        _c01_severity = _r.get("severity", "MAJOR")
                        break
            except Exception:
                pass
            violations.append({
                "rule_id": "C01", "slug": slug, "severity": _c01_severity,
                "detail": f"C01 위반: {', '.join(_c01_found)}",
                "file": str(md_file)})
            if _c01_severity == "CRITICAL":
                blocked = True

        # --- C02: 프론트매터 미종료 (CRITICAL) ---
        lines = content.split('\n')
        first_dash = None
        second_dash = None
        for i, line in enumerate(lines):
            if line.strip() == '---':
                if first_dash is None:
                    first_dash = i
                elif second_dash is None and i > first_dash:
                    second_dash = i
                    break
        if first_dash is not None and second_dash is None:
            violations.append({
                "rule_id": "C02", "slug": slug, "severity": "CRITICAL",
                "detail": "프론트매터 미종료: 첫 --- 이후 두 번째 --- 없음",
                "file": str(md_file)})
            blocked = True

        # --- C04: 프롬프트/사고문 누수 (CRITICAL) ---
        # 국문 + 영문 패턴 모두 확인
        # 주의: 일반 한국어 표현과 LLM 프롬프트 누수 패턴을 구분하기 위해
        # 구체적인 문맥 패턴만 사용 (예: "생각해보자" alone is OK, but "먼저 생각해보자"
        # as a standalone sentence suggesting LLM reasoning is suspicious)
        ko_patterns = [
            r"생각해보자\b",         # "생각해보자" (문장 끝)
            r"생각해\s*보자\b",      # "생각해 보자" (문장 끝)
            r"다음\s*단계로\s*넘어", # "다음 단계로 넘어가자"
            r"단계별로\s*진행해",    # "단계별로 진행해보자"
            r"우선\s*,?\s*(우리가|제가|내가|우리)\s*해야",  # "우선, 우리가 해야..."
            r"우리가\s*해야\s*할\s*것은",  # "우리가 해야 할 것은"
            r"생각\s*과정을\s*통해", # "생각 과정을 통해"
            r"결론부터\s*말하면",    # "결론부터 말하면"
            r"먼저\s*생각해보자",    # "먼저 생각해보자" (let's think)
            r"단계별로\s*생각",      # "단계별로 생각해보자"
        ]
        en_patterns = [
            r"\bNeed\s+to\s+think\b",
            r"\bWe\s+need\s+to\s+write\b",
            r"Let['']s\s+think\s+step\s+by\s+step",
            r"think\s+step\s+by\s+step",
            r"let['']s\s+break\s+this\s+down",
            r"here['']s\s+the\s+plan",
            r"in\s+order\s+to\s+achieve",
            r"as\s+an\s+AI\s+language\s+model",
        ]
        body_start = content.find("---\n", 4)  # 첫 frontmatter 닫기 이후
        body = content[body_start:] if body_start > 0 else content
        for pat in ko_patterns + en_patterns:
            if re.search(pat, body, re.IGNORECASE):
                violations.append({
                    "rule_id": "C04", "slug": slug, "severity": "CRITICAL",
                    "detail": f"프롬프트 누수 패턴 감지: {pat[:30]}",
                    "file": str(md_file)})
                blocked = True
                break  # 한 포스트당 1건만 기록

        # --- C06: mtime > deploy_time (MAJOR) ---
        # placeholder: deploy timestamp 소스 미확보 — heuristic 유지, LATER 후보
        # 기존 _check_c06 days_since<1 heuristic 유지, preflight에서는 미구현

        # --- C08: 라이브-파일 불일치 (CRITICAL) ---
        # 현재 구현에서는 제목/og_image 비교 로직 생략 (별도 구현 필요)
        # placeholder: 향후 라이브 비교 API 연동 시 활성화

        # --- C09: categories/tags 문자열화 (CRITICAL) ---
        # YAML 배열이 "['추천']" 같은 문자열 리터럴로 저장되면 Hugo range 실패
        # severity=CRITICAL → 1건이라도 있으면 배포 차단
        try:
            import yaml as _yaml9
            _fm_body = '\n'.join(lines[1:second_dash]) if second_dash else ''
            _fm_dict = _yaml9.safe_load(_fm_body) or {}
            if isinstance(_fm_dict, dict):
                for _c09_field in ('categories', 'tags'):
                    _c09_val = _fm_dict.get(_c09_field)
                    if _c09_val is not None and isinstance(_c09_val, str):
                        # "['...']" 또는 '["..."]' 패턴이면 문자열화
                        _c09_match = re.match(r'^\[\s*[\'"].*[\'"]\s*\]$', _c09_val.strip())
                        if _c09_match:
                            violations.append({
                                "rule_id": "C09", "slug": slug, "severity": "CRITICAL",
                                "detail": f"categories/tags 문자열화: {_c09_field}='{_c09_val}'",
                                "file": str(md_file)})
                            blocked = True
                            break  # 한 포스트당 1건만 기록
        except Exception:
            pass  # YAML 파싱 실패 시 C09 검사는 skip (C02에서 이미 걸렸을 가능성)

        # --- PHASE 70 WAVE 1: S-CATEGORY RULES ---
        # S01: Uniqueness Ratio ≥ 0.85
        # S02: Structural Similarity ≤ 0.70
        # S03: Unique Data Points ≥ 3
        # S04: Editorial Synthesis (no template markers)
        # S05: Freshness Gate (data age < 30 days)
        # corpus: 루프 밖 1회 구축(위) — 포스트마다 재스캔하지 않음

        # Frontmatter 파싱 (S04, S05용)
        fm_dict = {}
        try:
            import yaml as _yaml_s
            fm_body = '\n'.join(lines[1:second_dash]) if second_dash else ''
            fm_dict = _yaml_s.safe_load(fm_body) or {}
        except Exception:
            pass
        
        # S01: Uniqueness Ratio
        # ponytail: 킬스위치 QUALITY_ENFORCE_S01_S02=1일 때만 계산(기본 OFF).
        # WARN-ONLY라 blocked에 영향 없으면서 301포스트×TF-IDF(1.2s/포스트)
        # 로 900s scheduler kill 유발(tour-hugo P25). 발행 시점 quality_guard가
        # 동일 게이트를 이미 수행 — preflight 중복. corpus 재구축은 위에서
        # 1회로 축소했으므로 재활성화 시에도 포스트당 1.2s 유지됨.
        if corpus and os.getenv("QUALITY_ENFORCE_S01_S02", "0") == "1":
            try:
                from pipelines.etap.quality_guard import uniqueness_ratio_gate
                passed, ratio, details = uniqueness_ratio_gate(body, corpus, threshold=0.85)
                if not passed:
                    violations.append({
                        "rule_id": "S01", "slug": slug, "severity": "CRITICAL",
                        "detail": f"S01 위반: uniqueness={ratio:.4f} (threshold=0.85), max_sim={details.get('max_similarity', 0):.4f}",
                        "file": str(md_file)})
                    # WARN-ONLY: sklearn 부재 시 평소 스킵(dormant) 상태라 prod에서
                    # 차단한 적 없음. 활성화 시 짧은 synthesis 단락 vs 코퍼스 비교로
                    # 오탐 과다 → hard-block 미설정(S02/S06과 동일 품질신호 계열).
            except ImportError:
                pass  # quality_guard 미사용 블로그는 skip
            except Exception as e:
                logger.warning(f"[preflight] S01 check error for {slug}: {e}")

        # S02: Structural Similarity (S01과 동일 킬스위치 — 계산 비용 대비 sim=0.0000만 관측)
        if corpus and os.getenv("QUALITY_ENFORCE_S01_S02", "0") == "1":
            try:
                from pipelines.etap.quality_guard import structural_similarity_gate
                passed, sim, details = structural_similarity_gate(body, corpus, threshold=0.70)
                if not passed:
                    violations.append({
                        "rule_id": "S02", "slug": slug, "severity": "CRITICAL",
                        "detail": f"S02 위반: structural_sim={sim:.4f} (threshold=0.70)",
                        "file": str(md_file)})
                    # WARN-ONLY (Phase 71 editorial synthesis 완료 전): blocked 미설정
            except ImportError:
                pass
            except Exception as e:
                logger.warning(f"[preflight] S02 check error for {slug}: {e}")
        
        # S03: Unique Data Points (source_data 재구성 필요 - ETAP 블로그만)
        if blog_id in ETAP_PIPELINE_BLOGS:
            try:
                from pipelines.etap.quality_guard import unique_data_points_gate
                # slug로 source_data 재구성 시도
                source_data = {}
                import sqlite3
                db_path = Path(__file__).parent / "data" / "travel-en.db"
                if db_path.exists():
                    conn = sqlite3.connect(str(db_path))
                    conn.row_factory = sqlite3.Row
                    row = conn.execute(
                        "SELECT topic_id FROM publish_log WHERE blog_id = ? AND slug = ? ORDER BY log_id DESC LIMIT 1",
                        (blog_id, slug)
                    ).fetchone()
                    if row and row["topic_id"]:
                        topic_id = row["topic_id"]
                        source_data["topic_id"] = topic_id
                        # 관련 테이블에서 데이터 조회
                        for table in ["flight_prices", "popular_directions", "flight_calendar"]:
                            try:
                                rows = conn.execute(f"SELECT * FROM {table} WHERE origin = ? OR destination = ? LIMIT 20",
                                                    (slug, slug)).fetchall()
                                if rows:
                                    source_data[table] = [dict(r) for r in rows]
                            except Exception:
                                pass
                        # Phase 72 W4 T4.1 연동: 역추적된 topic_id의 <topic_table>.unique_data_points
                        # 저장값을 gate 입력에 병합 (저장 위치=topics 테이블, 읽는 위치 일치).
                        # 기존 테이블 재구성 로직은 폴백으로 보존.
                        try:
                            _stem = blog_id[:-5] if blog_id.endswith("-hugo") else blog_id
                            _ttable = ("flight" if _stem == "flights" else _stem) + "_topics"
                            _pkrows = conn.execute(f"PRAGMA table_info({_ttable})").fetchall()
                            _pk = next((r["name"] for r in _pkrows if r["pk"] == 1), "id")
                            _trow = conn.execute(
                                f"SELECT unique_data_points FROM {_ttable} WHERE {_pk} = ?", (topic_id,)
                            ).fetchone()
                            for _k, _v in _stored_points_to_gate_data(
                                    _trow["unique_data_points"] if _trow else None).items():
                                source_data[_k] = _v
                        except Exception:
                            pass  # 테이블/컬럼 부재 시 기존 재구성값만 사용
                    conn.close()

                # gate는 검증 가능한 소스 값이 있을 때만 실행 — bare topic_id만 있으면
                # count=0이 보장되어 전량 오탐(발행 대량 차단, T-72-03)이 되므로 skip.
                if any(k != "topic_id" for k in source_data):
                    passed, count, details = unique_data_points_gate(body, source_data, threshold=3)
                    if not passed:
                        # Phase 72-fix: S03 = 데이터 충분성 품질신호 → WARN-ONLY(MAJOR).
                        # warn-only 시절 합법 발행분을 enforce 전환 시 소급 차단하면
                        # 단 1포스트 실패로 블로그 전체 배포 정지 → hard-block 부적절.
                        # 실제 깨진 synthesis(미치환 마커)는 S04가 hard-block 담당.
                        violations.append({
                            "rule_id": "S03", "slug": slug,
                            "severity": "MAJOR",
                            "detail": f"S03 위반: data_points={count} (threshold=3) — warn-only",
                            "file": str(md_file)})
            except ImportError:
                pass
            except Exception as e:
                logger.warning(f"[preflight] S03 check error for {slug}: {e}")
        
        # S04: Editorial Synthesis (template markers)
        # (?![<{%]) — Hugo 쇼트코드({{< lead >}}, {{% foo %}})는 정상 문법이므로 제외.
        template_markers = re.findall(r"\{\{(?![<{%])[^}]+\}\}", body)
        if template_markers:
            unique_markers = set(template_markers)
            violations.append({
                "rule_id": "S04", "slug": slug, "severity": "CRITICAL",
                "detail": f"S04 위반: 미치환 템플릿 마커 {len(unique_markers)}개 — {list(unique_markers)[:5]}",
                "file": str(md_file)})
            # Phase 72 W4: blocking 전환 (kill-switch QUALITY_ENFORCE_S03_S04=0 → warn-only 복귀)
            if _enforce_s03_s04 and blog_id not in _s04_warn_only_blogs:
                blocked = True

        # S06: Editorial Synthesis cosine (WARN-ONLY, Phase 72 W3 T3.2)
        # 본문 말미 synthesis 단락의 동일 블로그 최근 발행 대비 TF-IDF cosine < 0.70 검사.
        # corpus는 S02에서 만든 것 재사용(블로그에 다른 포스트가 있을 때만 검사).
        if corpus:
            try:
                from pipelines.etap.editorial_synthesis import extract_trailing_synthesis
                from pipelines.etap.uniqueness_check import editorial_cosine_check
                _syn = extract_trailing_synthesis(body)
                if _syn:
                    _s06_ok, _s06_cos = editorial_cosine_check(_syn, blog_id, threshold=0.70)
                    if not _s06_ok:
                        violations.append({
                            "rule_id": "S06", "slug": slug, "severity": "MAJOR",
                            "detail": f"S06 경고: synthesis cosine={_s06_cos:.4f} (threshold=0.70)",
                            "file": str(md_file)})
                        # WARN-ONLY: blocked 미설정 (Wave 4 이후 재검토)
            except ImportError:
                pass
            except Exception as e:
                logger.warning(f"[preflight] S06 check error for {slug}: {e}")

        # S05: Freshness Gate
        freshness_keys = ["data_date", "price_date", "source_date", "last_updated", "data_freshness_days"]
        for key in freshness_keys:
            if key in fm_dict and fm_dict[key]:
                val = str(fm_dict[key]).strip()
                try:
                    from datetime import datetime as _dt
                    for fmt in ("%Y-%m-%d", "%Y%m%d", "%Y-%m-%d %H:%M:%S"):
                        try:
                            data_date = _dt.strptime(val[:10], "%Y-%m-%d")
                            age_days = (_dt.now() - data_date).days
                            if age_days > 30:
                                violations.append({
                                    "rule_id": "S05", "slug": slug, "severity": "CRITICAL",
                                    "detail": f"S05 위반: 데이터 경과 {age_days}일 (threshold=30일), {key}={val}",
                                    "file": str(md_file)})
                                blocked = True
                            break
                        except ValueError:
                            continue
                    # 정수 일수로 파싱 시도
                    try:
                        age_days = int(val)
                        if age_days > 30:
                            violations.append({
                                "rule_id": "S05", "slug": slug, "severity": "CRITICAL",
                                "detail": f"S05 위반: 데이터 경과 {age_days}일 (threshold=30일), {key}={val}",
                                "file": str(md_file)})
                            blocked = True
                    except ValueError:
                        pass
                except Exception:
                    pass
                break  # 첫 번째 freshness 키만 검사

        # --- PHASE 70 WAVE 3: freshness gate (lastmod) ---
        # lastmod 프론트매터가 30일 초과 시 MAJOR 경고 (warn-only, blocked=False)
        _lm = fm_dict.get("lastmod") or fm_dict.get("date")
        if _lm:
            try:
                from datetime import datetime as _dt
                _lm_str = str(_lm)
                _lm_dt = _dt.fromisoformat(_lm_str.replace("Z", "+00:00"))
                _stale_days = (_dt.now().astimezone() - _lm_dt).days
                if _stale_days > 30:
                    violations.append({
                        "rule_id": "FRESH", "slug": slug, "severity": "MAJOR",
                        "detail": f"FRESH 경고: lastmod {_stale_days}일 경과 (threshold=30일)",
                        "file": str(md_file)})
                    # warn only — blocked remains False
            except Exception:
                pass

        # --- C2(2026-08-21): 이미지 배포 차단 게이트는 deploy._pre_deploy_image_gate
        #     (shared/publishers/deploy.py:41) 로 단일 초크포인트 통합.
        #     deploy_site()가 dispatcher·etap pipeline 양 경로 공용이라 중복 제거. ---

    # 결과 기록 (logs/c01_c04_preflight.json)
    logs_dir = Path(__file__).parent / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    preflight_log = logs_dir / "c01_c04_preflight.json"
    _results = {
        "blog_id": blog_id,
        "checked_at": datetime.now().isoformat(),
        "blocked": blocked,
        "violations": violations,
        "reason": "차단: critical 위반 있음" if blocked else "통과",
    }
    try:
        existing = json.loads(preflight_log.read_text()) if preflight_log.exists() else {}
    except (json.JSONDecodeError, OSError):
        existing = {}
    existing[blog_id] = _results
    preflight_log.write_text(json.dumps(existing, ensure_ascii=False, indent=2))

    return _results


def _build_and_deploy_central(blog_id: str) -> bool:
    """중앙 빌드+배포 — ETAP/Workers 블로그 공용"""
    # ── C01~C04·C08 프리플라이트 게이트 ──
    _pf_result = preflight_check(blog_id)
    if _pf_result.get("blocked"):
        logger.error(
            f"[deploy] 프리플라이트 차단: {blog_id} "
            f"— critical 위반 {len(_pf_result['violations'])}건: "
            f"{[v['rule_id']+':'+v['slug'] for v in _pf_result['violations']]}"
        )
        # Telegram 알림 (기존 _tg_error 활용)
        _violation_summary = "; ".join(
            f"{v['rule_id']}({v['slug']})" for v in _pf_result["violations"]
        )
        try:
            from shared.telegram_notifier import send_error as _tg_error
            _tg_error(f"[deploy blocked] {blog_id}: {_violation_summary}")
        except Exception as e:
            logger.warning(f"[deploy blocked] 텔레그램 전송 실패: {e}")
            pass
        # W5 프리플라이트 차단을 대시보드에 가시화(P12 품질 게이트 차단 코드로 기록)
        try:
            from shared.publish_error_events import record_publish_error as _rec_pe
            _rec_pe(
                blog_id, "preflight", _violation_summary,
                problem_id="P12", reason="preflight_blocked",
                pipeline=blog_id, retryable=False,
            )
        except Exception as e:
            logger.warning(f"[deploy blocked] 이벤트 기록 실패: {e}")
        return False

    import fcntl as _fcntl
    _all = _load_all_blogs().get("blogs", [])
    _cfg = next((b for b in _all if b.get("id") == blog_id), {})
    _sp = _cfg.get("site_path", "") or str(ETAP_BASE / blog_id)
    site_path = Path(_sp)
    if not site_path.exists():
        logger.warning(f"[deploy] site_path 없음: {site_path}")
        return False
    try:
        # Phase 71d: wrangler env(CLOUDFLARE_API_TOKEN 제거 + ACCOUNT_ID 복원)를
        # shared.publishers.deploy.build_wrangler_env()로 위임 (단일 토큰 정책).
        from shared.publishers.deploy import build_wrangler_env
        deploy_env = build_wrangler_env()
        deploy_env["PATH"] = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
        deploy_env["HUGO_THEMESDIR"] = SHARED_THEMES
        r1 = subprocess.run(
            [HUGO, "--gc", "--minify"],
            cwd=str(site_path),
            capture_output=True, text=True,
            env=deploy_env,
            timeout=180,
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

            # Phase 73 SC-8: deploy_type 설정 키 우선, 없으면 WORKERS_BLOGS 휴리스틱 폴백.
            _deploy_type = _cfg.get("deploy_type")
            _use_workers = (
                _deploy_type == "workers"
                or (_deploy_type is None and blog_id in WORKERS_BLOGS)
            )
            if _use_workers:
                r2 = subprocess.run(
                    [WRANGLER, "deploy",
                     "--config", str(site_path / "wrangler.toml")],
                    cwd=str(site_path),
                    capture_output=True, text=True,
                    timeout=300,  # ponytail: 120→300 large ETAP Pages/Workers need >120s (tour-hugo P25)
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
                    timeout=300,  # ponytail: 120→300 ETAP large sites
                    env=deploy_env
                )
        finally:
            try:
                _fcntl.flock(lock_file, _fcntl.LOCK_UN)
                lock_file.close()
                logger.info(f"[deploy] {blog_id} 락 해제")
            except Exception as e:
                logger.warning(f"[deploy] {blog_id} 락 해제 실패: {e}")
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
    except Exception as e:
        logger.warning(f"[deploy] deploy 실패 이벤트 기록 오류: {e}")
        pass


# ─── 발행 성공 후 자동 재검사 훅 (Phase 71, SC-1) ───

def _trigger_post_publish_checks(
    blog_id: str,
    ops_db_path: str | None = None,
    _run_autofix: bool = True,
) -> None:
    """발행 성공 직후 해당 blog 체크를 자동 트리거 (수동 호출 불필요).

    dispatcher↔ops_dashboard 결합도 리스크 완화를 위해 lazy import + 예외 격리.
    체크 실패가 발행 성공을 훼손하면 안 되므로, 모든 예외는 로깅만 하고
    발행 경로에는 영향 0 (삼킴 금지 → 명시적 경고 로깅).
    ops_db_path 를 주입하면 실제 ops.db 가 아닌 테스트용 DB 를 쓸 수 있음.

    Phase 71 (SC-4) 배선: 재검사 완료 후 해당 blog 의 fail 규칙을
    _auto_fix_on_fail 로 전달 (안전 fixer 무인 실행, 파괴등급은 pending_fixes 적재).
    _run_autofix=False 면 자동수정 루프를 건너뛴다 — _auto_fix_on_fail 내부 재검사
    호출이 재귀 무한루프로 빠지지 않도록 내부 호출이 False 를 넘긴다.
    """
    try:
        from ops_dashboard.checks import run_all_checks
        from ops_dashboard.db import get_conn

        path = ops_db_path or str(PROJECT_DIR / "ops_dashboard" / "ops.db")
        # get_conn 은 row_factory=sqlite3.Row 를 설정 — run_all_checks/get_all_blogs
        # 가 dict(row) 를 가정하므로 반드시 get_conn 을 써야 함 (raw sqlite3.connect X).
        conn = get_conn(path)
        try:
            run_all_checks(conn, blog_ids=[blog_id])
            if _run_autofix:
                _run_autofix_after_checks(conn, blog_id, path)
        finally:
            conn.close()
        logger.info("[post-publish-check] %s 자동 재검사 완료", blog_id)
    except Exception as e:  # 발행 성공 경로 보호 — 체크 실패가 발행을 죽이면 안 됨
        logger.warning(
            "[post-publish-check] %s 자동 재검사 실패(발행경로 무영향): %s",
            blog_id, e,
        )


def _fetch_failed_rule_ids(conn, blog_id: str) -> list[str]:
    """run_all_checks 직후 해당 blog 의 실패 규칙 id 목록 조회.

    개별 규칙 행은 check_results 에 check_name=rule_id 로 기록되므로,
    status='fail' 이고 rule_id 가 채워진 행의 rule_id 를 distinct 로 수집한다.
    aggregate(standard_compliance) 행은 rule_id 가 NULL 이라 제외된다.
    """
    rows = conn.execute(
        """
        SELECT DISTINCT rule_id FROM check_results
        WHERE blog_id = ? AND status = 'fail'
          AND rule_id IS NOT NULL AND rule_id != ''
        """,
        (blog_id,),
    ).fetchall()
    return [r["rule_id"] for r in rows]


def _run_autofix_after_checks(conn, blog_id: str, ops_db_path: str) -> dict | None:
    """재검사 결과를 폐루프 디스패처(_auto_fix_on_fail)로 전달 (SC-4 배선).

    감지 루프(check_standard_compliance / run_all_checks)가 쓴 fail rule 행을
    _auto_fix_on_fail 로 넘긴다. 실패 규칙이 없으면 None. 모든 예외는 격리되어
    호출자(발행/재검사 경로)를 죽이지 않는다.
    """
    try:
        failed = _fetch_failed_rule_ids(conn, blog_id)
        if not failed:
            return None
        summary = _auto_fix_on_fail(blog_id, failed, conn=conn, ops_db_path=ops_db_path)
        if summary.get("requires_approval"):
            logger.info(
                "[auto-fix] %s 파괴등급 %d건 pending_fixes 적재(승인 대기)",
                blog_id, len(summary["requires_approval"]),
            )
        if summary.get("applied"):
            logger.info(
                "[auto-fix] %s 자동수정 적용 %d건: %s",
                blog_id, len(summary["applied"]), summary["applied"],
            )
        return summary
    except Exception as e:
        logger.warning("[auto-fix] %s 폐루프 배선 실패(무영향): %s", blog_id, e)
        return None


# ─── 자동 수정 폐루프 (Phase 71, SC-4) ───

# rule_id → agent_action 키 (config/quality_checklist.yaml global_standard 와 1:1)
_AUTOFIX_RULE_TO_ACTION = {
    "R04": "fix_r04",
    "R06": "fix_r06",
    "R08": "fix_r08",
    "R12": "fix_r12",
    "THUMBNAIL-01": "fix_thumbnail_r2",
    "R2-01": "fix_r2_images",
    "FM-DRAFT": "fix_draft_true",
    "FM-FEATUREIMAGE": "fix_featureimage_url_sanitize",
    "FM-THUMBNAIL": "fix_featureimage_url_sanitize",
    "FM-MISSINGKEYS": "fix_frontmatter_missing_keys",
}

# OQ#2 (시니어 결정 대기) 승인게이트: 무인 자동 실행 허용 항목(grade A).
# 썸네일 재생성은 안전으로 분류. 나머지(fix_r04/r06/r08/r12/r2_images)는
# approve_non_safe=True 가 필요 — 그렇지 않으면 'requires_approval' 으로 분류되어
# 자동 실행되지 않음 (사람 승인 경로).
_AUTOFIX_SAFE_ACTIONS = {
    "fix_thumbnail_r2",
    "fix_draft_true",
    "fix_featureimage_url_sanitize",
    "FM-THUMBNAIL",
    "fix_frontmatter_missing_keys",
}


def _auto_fix_on_fail(
    blog_id: str,
    failed_rule_ids: list[str],
    ops_db_path: str | None = None,
    conn=None,
    approve_non_safe: bool = False,
    redeploy: bool = False,
) -> dict:
    """감지된 fail 규칙에 대해 자동수정 시도 (SC-4 폐루프 디스패처).

    게이트 (AGENTS.md 파괴적 작업 + OQ#2 승인게이트):
      - actionable bucket 규칙만 대상 (deferred R06 / out_of_scope R03,R04 제외)
      - 구현된 fixer 가 있는 규칙만 대상
      - SAFE_ACTIONS 만 무인 실행+재배포. 그 외(파괴등급)는 항상 사람 승인 경로(requires_approval), approve_non_safe 와 무관 (OQ#2 옵션 a)
      - redeploy(실발행 재배포 = 파괴적)는 기본 False — 명시적 승인 필요

    Phase 71 (SC-4) 영속화: conn 을 넘기면 파괴등급(사람 승인 필요) fix 를
    pending_fixes 에 proposed 로 적재하고, 안전 fixer 로 무인 적용된 규칙은
    resolved/failed 로 적재해 감사 흔적을 남긴다. conn 이 없으면(레거시 호출/테스트)
    pending_fixes 는 건드리지 않는다 (in-memory summary 만 반환).

    반환: {"blog_id", "applied":[...], "requires_approval":[...],
            "skipped":[...], "redeployed": bool, "recheck_triggered": bool}
    """
    summary = {
        "blog_id": blog_id,
        "applied": [],
        "requires_approval": [],
        "skipped": [],
        "redeployed": False,
        "recheck_triggered": False,
    }
    if not failed_rule_ids:
        return summary

    # WAVE3-3.1 게이트: redeploy(파괴적 재배포)는 기본 False 유지.
    # 명시적 redeploy=True + env AUTOFIX_REDEPLOY_APPROVED=1 + approve_non_safe=True
    # 세 조건 동시 충족 시에만 활성화. 그 외 모든 경로는 False 로 고정(자동 활성화 없음).
    effective_redeploy = (
        redeploy
        and os.environ.get("AUTOFIX_REDEPLOY_APPROVED") == "1"
        and approve_non_safe
    )

    cfg = get_blog_config(blog_id)
    site_path = cfg.get("site_path", "") if cfg else ""
    if not site_path or not Path(site_path).is_dir():
        summary["skipped"].append("site_path 없음")
        return summary

    try:
        from ops_dashboard.db import (
            enqueue_pending_fix,
            get_conn,
            set_pending_fix_status,
        )
        from ops_dashboard.registry.rules import RULES
        from shared.autofix import FIXERS, backup_blog, get_ga4_id

        bucket_by_id = {e.id: e.bucket for e in RULES}
        # pending 적재용 conn: 명시 conn 우선, 없으면 ops_db_path/default 로 연다.
        pend_conn = conn or get_conn(ops_db_path)
        need_close = conn is None
        try:
            return _dispatch_auto_fix(
                summary, blog_id, failed_rule_ids, site_path,
                bucket_by_id, pend_conn, ops_db_path,
                approve_non_safe, effective_redeploy,
            )
        finally:
            if need_close:
                pend_conn.close()
    except Exception as e:
        logger.warning("[auto-fix] %s 디스패치 실패: %s", blog_id, e)
    return summary


def _dispatch_auto_fix(
    summary, blog_id, failed_rule_ids, site_path,
    bucket_by_id, pend_conn, ops_db_path,
    approve_non_safe, redeploy,
) -> dict:
    """_auto_fix_on_fail 의 본체 — pending 영속화 + fixer 디스패치 분리."""
    from ops_dashboard.db import (
        enqueue_pending_fix,
        set_pending_fix_status,
    )
    from ops_dashboard.registry import get_entry
    from shared.autofix import FIXERS, backup_blog, get_ga4_id

    cfg = get_blog_config(blog_id)
    ga4_id = get_ga4_id(blog_id, cfg.get("domain", ""))

    # 파괴적 작업 4단계 (1) 백업
    try:
        backup_blog(site_path, blog_id)
    except Exception as e:
        logger.warning("[auto-fix] %s 백업 실패: %s", blog_id, e)

    site = Path(site_path)
    applied_any = False
    for rule_id in failed_rule_ids:
        bucket = bucket_by_id.get(rule_id)
        if bucket != "actionable":
            summary["skipped"].append(f"{rule_id}(bucket={bucket})")
            continue
        action_key = _AUTOFIX_RULE_TO_ACTION.get(rule_id)
        fixer = FIXERS.get(action_key) if action_key else None
        if not fixer:
            summary["skipped"].append(f"{rule_id}(fixer 없음)")
            continue
        entry = get_entry(rule_id)
        severity = entry.severity if entry else ""
        # 사람 승인 필요(파괴등급) — 안전항목(SAFE_ACTIONS)만 무인 실행.
        # 그 외는 항상 pending_fixes 에 proposed 로 적재(사람 승인 경로),
        # approve_non_safe 와 무관 (OQ#2 옵션 a: 비안전은 무인 재배포 대상 아님)
        if action_key not in _AUTOFIX_SAFE_ACTIONS:
            summary["requires_approval"].append(f"{rule_id}->{action_key}")
            try:
                enqueue_pending_fix(
                    pend_conn, blog_id, rule_id, action_key,
                    severity=severity,
                    evidence=f"감지: {rule_id}(bucket={bucket}) fail — 승인 필요",
                    diff_ref=action_key,
                )
            except Exception as e:
                logger.warning("[auto-fix] %s %s pending 적재 실패: %s", blog_id, rule_id, e)
            continue
        try:
            # R1 상태 어휘: fixer 실행 직전 proposed→fixing 전이 기록 (폐루프 감사)
            try:
                set_pending_fix_status(
                    pend_conn, _latest_pending_id(pend_conn, blog_id, rule_id), "fixing",
                )
            except Exception as e:
                logger.warning("[auto-fix] %s %s fixing 기록 실패: %s", blog_id, rule_id, e)
            ok, msg = fixer(site, blog_id, ga4_id)
            if ok:
                summary["applied"].append(f"{rule_id}:{msg}")
                applied_any = True
                try:
                    set_pending_fix_status(
                        pend_conn, _latest_pending_id(pend_conn, blog_id, rule_id),
                        "resolved", resolved_at=_now_iso(),
                        diff_ref=f"{action_key}: {msg}",
                    )
                except Exception as e:
                    logger.warning("[auto-fix] %s %s resolved 기록 실패: %s", blog_id, rule_id, e)
            else:
                summary["skipped"].append(f"{rule_id}:{msg}")
                try:
                    set_pending_fix_status(
                        pend_conn, _latest_pending_id(pend_conn, blog_id, rule_id),
                        "failed", resolved_at=_now_iso(),
                        diff_ref=f"{action_key}: {msg}",
                    )
                except Exception as e:
                    logger.warning("[auto-fix] %s %s failed 기록 실패: %s", blog_id, rule_id, e)
        except Exception as e:
            logger.warning("[auto-fix] %s %s fixer 실패: %s", blog_id, rule_id, e)
            summary["skipped"].append(f"{rule_id}(예외:{e})")

    # 파괴적 작업 4단계 (3) 재배포 — 안전항목만, env 승인 게이트 필요 (OQ#2 옵션 a)
    if applied_any and redeploy:
        # (1) 사전카운트: 재배포 대상 적용 건수 기록
        _applied_count = len(summary["applied"])
        logger.info("[auto-fix] %s 재배포 사전카운트: 적용 %d건", blog_id, _applied_count)
        from datetime import datetime
        import subprocess
        _ts = datetime.now().strftime("%Y-%m-%d")
        # (2) 백업 보강: site_path git 태그 (롤백 지점)
        try:
            subprocess.run(
                ["git", "tag", f"pre-autofix-{blog_id}-{_ts.replace('-', '')}"],
                cwd=str(site_path), check=False, capture_output=True,
            )
        except Exception:
            pass
        try:
            _build_and_deploy_central(blog_id)
            summary["redeployed"] = True
        except Exception as e:
            logger.warning("[auto-fix] %s 재배포 실패: %s", blog_id, e)
        # (4) 사후대조 — 재검사는 _run_autofix=False 로 재귀 차단
        try:
            _trigger_post_publish_checks(blog_id, ops_db_path, _run_autofix=False)
            summary["recheck_triggered"] = True
        except Exception as e:
            logger.warning("[auto-fix] %s 재검사 트리거 실패: %s", blog_id, e)
        # 파괴적 작업 기록 (민감정보 미포함: blog/건수/시각만)
        try:
            _record_destructive_redeploy(blog_id, _applied_count, _ts)
        except Exception as e:
            logger.warning("[auto-fix] %s 파괴적 기록 실패: %s", blog_id, e)
    return summary


def _record_destructive_redeploy(blog_id: str, applied_count: int, ts: str) -> None:
    """파괴적 재배포 4단계 로그 + worklog 기록 (민감정보 미포함: blog/건수/시각만).

    redeploy 게이트(AUTOFIX_REDEPLOY_APPROVED=1 + approve_non_safe) 통과 후에만 호출.
    """
    try:
        _log_dir = Path("logs")
        _log_dir.mkdir(exist_ok=True)
        _line = f"{ts} autofix-redeploy blog={blog_id} applied={applied_count}\n"
        with open(_log_dir / f"destructive_{ts}.log", "a", encoding="utf-8") as _lf:
            _lf.write(_line)
    except Exception as e:
        logger.warning("[auto-fix] %s 파괴적 로그 기록 실패: %s", blog_id, e)
    try:
        _wl_dir = Path(".planning/worklog")
        _wl_dir.mkdir(parents=True, exist_ok=True)
        _wp = _wl_dir / f"WL-{ts}-autofix-redeploy.md"
        if not _wp.exists():
            _wp.write_text(
                f"# WL-{ts} autofix-redeploy — {blog_id}\n\n"
                f"- 시각: {ts}\n"
                f"- blog: {blog_id}\n"
                f"- 적용 건수: {applied_count}\n"
                f"- 게이트: AUTOFIX_REDEPLOY_APPROVED=1 + approve_non_safe (안전항목만)\n"
                f"- 롤백: git tag pre-autofix-{blog_id}-{ts.replace('-', '')}\n"
            )
    except Exception as e:
        logger.warning("[auto-fix] %s worklog 생성 실패: %s", blog_id, e)


def _latest_pending_id(conn, blog_id: str, rule_id: str) -> int:
    """가장 최근 pending_fixes 행 id (safe auto-fix 결과 기록용). 없으면 -1."""
    row = conn.execute(
        "SELECT id FROM pending_fixes WHERE blog_id = ? AND rule_id = ? "
        "ORDER BY id DESC LIMIT 1",
        (blog_id, rule_id),
    ).fetchone()
    return int(row["id"]) if row is not None else -1


def _now_iso() -> str:
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def execute_pending_fix(
    conn,
    fix_id: int,
    *,
    redeploy: bool = True,
    ops_db_path: str | None = None,
) -> dict:
    """승인 엔드포인트에서 호출되는 pending_fixes 실행자 (SC-4 승인 폐루프).

    proposed(또는 approved) 행을 load → executing 전이 → 백업 → 실제 fixer
    (shared/autofix.FIXERS) 실행 → (redeploy 시) 재배포 + 사후대조 재검사 →
    resolved/failed 전이. 실제 fixer 를 FIXERS 레지스트리 경유로 실행하므로
    테스트는 실제 fixer 경로를 검증한다.

    redeploy(실발행 재배포 = 파괴적)는 실행자 기본 True — 승인 엔드포인트가 사람 승인
    통과 후 호출하므로 승인 게이트를 대신한다. 테스트는 redeploy=False 로 재배포를 끈다.

    반환: {"fix_id", "blog_id", "rule_id", "action", "ok", "msg", "status",
            "redeployed", "recheck_triggered"}
    """
    from ops_dashboard.db import (
        get_pending_fix,
        get_conn,
        set_pending_fix_status,
    )
    from shared.autofix import FIXERS, backup_blog, get_ga4_id

    row = get_pending_fix(conn, fix_id)
    if not row:
        return {"fix_id": fix_id, "ok": False, "msg": "pending_fixes 행 없음", "status": ""}
    if row["status"] not in ("proposed", "approved"):
        return {
            "fix_id": fix_id, "blog_id": row["blog_id"], "rule_id": row["rule_id"],
            "action": row["action"], "ok": False,
            "msg": f"상태 {row['status']!r} 에서 실행 불가 (proposed/approved 만 허용)",
            "status": row["status"],
        }

    blog_id = row["blog_id"]
    rule_id = row["rule_id"]
    action_key = row["action"]
    cfg = get_blog_config(blog_id)
    site_path = cfg.get("site_path", "") if cfg else ""
    if not site_path or not Path(site_path).is_dir():
        set_pending_fix_status(conn, fix_id, "failed", resolved_at=_now_iso(),
                               diff_ref="site_path 없음/미존재")
        return {
            "fix_id": fix_id, "blog_id": blog_id, "rule_id": rule_id,
            "action": action_key, "ok": False, "msg": "site_path 없음",
            "status": "failed",
        }

    set_pending_fix_status(conn, fix_id, "executing")
    ga4_id = get_ga4_id(blog_id, cfg.get("domain", ""))
    fixer = FIXERS.get(action_key)
    redeemed = False
    rechecked = False
    if fixer is None:
        result = (False, f"fixer 없음({action_key})")
    else:
        try:
            backup_blog(site_path, blog_id)
            result = fixer(Path(site_path), blog_id, ga4_id)
        except Exception as e:
            result = (False, f"fixer 예외: {e}")

    ok, msg = result
    if ok and redeploy:
        try:
            _build_and_deploy_central(blog_id)
            redeemed = True
        except Exception as e:
            logger.warning("[pending-fix] %s 재배포 실패: %s", blog_id, e)
        try:
            _trigger_post_publish_checks(blog_id, ops_db_path, _run_autofix=False)
            rechecked = True
        except Exception as e:
            logger.warning("[pending-fix] %s 재검사 트리거 실패: %s", blog_id, e)
            pass

    final_status = "resolved" if ok else "failed"
    set_pending_fix_status(conn, fix_id, final_status, resolved_at=_now_iso(),
                           diff_ref=f"{action_key}: {msg}")
    return {
        "fix_id": fix_id, "blog_id": blog_id, "rule_id": rule_id,
        "action": action_key, "ok": ok, "msg": msg, "status": final_status,
        "redeployed": redeemed, "recheck_triggered": rechecked,
    }


# ─── 메인 디스패치 ───


def _terminate_pipeline_children(blog_id: str) -> None:
    """300s 타임아웃 시 워커 스레드가 남긴 hugo/wrangler 자식 프로세스를 종료.

    스레드는 kill 불가하므로, 현재 dispatcher 프로세스의 자식 트리를 순회하며
    SIGTERM → SIGKILL 로 정리. 이들이 잡고 있던 /tmp/wrangler_deploy.lock 이
    해제되어 후속 배포가 블록되지 않는다. (psutil 미설치 환경 → pgrep fallback)
    """
    import os
    import signal
    import subprocess

    pid = os.getpid()
    to_kill: list[int] = []
    seen: set[int] = set()
    frontier = [pid]
    while frontier:
        p = frontier.pop()
        if p in seen:
            continue
        seen.add(p)
        try:
            out = subprocess.run(
                ["pgrep", "-P", str(p)], capture_output=True, text=True, timeout=5
            )
            for line in out.stdout.split():
                try:
                    c = int(line)
                    if c != pid:
                        to_kill.append(c)
                    frontier.append(c)
                except ValueError:
                    pass
        except Exception:
            pass
    for c in to_kill:
        try:
            os.kill(c, signal.SIGTERM)
        except ProcessLookupError:
            pass
    # grace 2s 후 강제 SIGKILL
    if to_kill:
        import time
        time.sleep(2)
        for c in to_kill:
            try:
                os.kill(c, signal.SIGKILL)
            except ProcessLookupError:
                pass
        logger.warning(
            f"[dispatch] terminated {len(to_kill)} child process(es) on timeout for {blog_id}"
        )


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
    # 발행 전 중복 체크 (QUOTA_OVERRIDE: 임시 우회)
    if _is_duplicate(blog_id):  # QUOTA_OVERRIDE
        logger.info(f"[DEDUP] {blog_id} 동일 제목 중복 — 발행 건너뜀 (quota 소모 안 함)")
        _record_failure(blog_id, "duplicate_title", "daily_quota 도달")
        return {"success": False, "reason": "duplicate_title"}

    # no_result backoff 체크 (cooldown은 정상 백오프 — 실패 아님)
    if _is_on_cooldown(blog_id):
        logger.info(f"[SKIP] {blog_id} cooldown ({_COOLDOWN_MINUTES}분) — 발행 건너뜀")
        return {"success": True, "reason": "cooldown",
                "detail": f"cooldown {_COOLDOWN_MINUTES}분 (정상 백오프, 실패 카운트 제외)"}
    # 일일 cooldown 체크 (IPO no_content 등 — 실패 아님)
    if _is_on_daily_cooldown(blog_id):
        logger.info(f"[SKIP] {blog_id} daily cooldown — 내일까지 발행 중단")
        return {"success": True, "reason": "cooldown",
                "detail": "daily cooldown (다음 날 재시작, 실패 카운트 제외)"}

    # ── 전역 publish 동시성 제한: 슬롯 확보 ──────────────────────
    inherited = get_inherited_slot_info()
    if inherited:
        # 부모가 슬롯 확보 (scheduler → env var PUBLISH_SLOT_ID 상속)
        slot_id = inherited["slot_id"]
        self_acquired = False
        logger.debug(f"[CONCURRENCY] 부모 슬롯 상속: slot={slot_id} blog={blog_id}")
    else:
        # 직접 호출(외부/수동/cron) — 자체 acquire
        slot_id = acquire_publish_slot(blog_id)
        if slot_id is None:
            logger.warning(
                f"[CONCURRENCY] publish 슬롯 풀 소진 "
                f"(MAX_CONCURRENT={MAX_CONCURRENT_PUBLISH}) — {blog_id} 스킵"
            )
            return {"success": False, "reason": "concurrency_limit"}
        self_acquired = True

    try:
        import threading
        from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
        from concurrent.futures.thread import _worker

        class _DaemonThreadPoolExecutor(ThreadPoolExecutor):
            """Worker threads are daemons so a 150s pipeline timeout actually ends
            the process. A non-daemon worker would keep the interpreter alive until
            the scheduler's 600s kill (observed: rap4-hugo 09:23 run survived 600s)."""
            def _adjust_thread_count(self):
                if self._idle_semaphore.acquire(timeout=0):
                    return
                import weakref
                from concurrent.futures.thread import _threads_queues

                def weakref_cb(_, q=self._work_queue):
                    q.put(None)

                num_threads = len(self._threads)
                if num_threads < self._max_workers:
                    thread_name = '%s_%d' % (
                        self._thread_name_prefix or self,
                        num_threads)
                    t = threading.Thread(
                        name=thread_name, target=_worker,
                        args=(weakref.ref(self, weakref_cb),
                              self._create_worker_context(),
                              self._work_queue),
                        daemon=True)
                    t.start()
                    self._threads.add(t)
                    _threads_queues[t] = self._work_queue

        # NOTE: do NOT use `with` — its implicit shutdown(wait=True) would join the
        # still-running worker thread and block until the pipeline finishes (600s),
        # defeating the 300s timeout. Abandon the thread on timeout instead.
        _exec = _DaemonThreadPoolExecutor(max_workers=1, thread_name_prefix="pipeline")
        _fut = _exec.submit(_run_pipeline, cfg)
        try:
            result = _fut.result(timeout=300)
        except FuturesTimeoutError:
            logger.warning(f"[dispatch] pipeline timeout 300s for {blog_id}")
            # ponytail: terminate spawned children (hugo/wrangler) so they release
            # /tmp/wrangler_deploy.lock instead of holding it for the full run.
            _terminate_pipeline_children(blog_id)
            result = {"success": False, "reason": "pipeline_timeout_300s"}
        finally:
            _exec.shutdown(wait=False)  # abandon worker thread, let process exit
    except Exception as e:
        logger.warning(f"[dispatch] pipeline exception for {blog_id}: {type(e).__name__}: {str(e)[:200]}")
        result = {
            "success": False,
            "reason": f"exception:{type(e).__name__}:{str(e)[:200]}",
            "traceback": traceback.format_exc()[-500:],
        }

    # 결과 정규화: 모든 pipeline이 dict를 반환하도록
    if result is None:
        logger.warning(
            f"[dispatch] {blog_id} pipeline returned None → no_result "
            f"(서브사인: subprocess는 logs/<prefix>_<blog>.pipeline.log, "
            f"in-process는 파이프라인 내부 로그 확인)"
        )
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
        result = {"success": result, "reason": "pipeline_returned_false" if not result else "pipeline_success"}

    # ── PR-CAP-1: backward-compatible Pipeline Result Contract enrichment ──
    # Adds `pipeline_status` to the result dict only. `success`/`reason` and all
    # downstream control flow (failure_count, cooldown, DB writes, deploy) are
    # UNCHANGED. Wrapped so a contract import failure is a safe no-op.
    try:
        from shared.pipeline_result import from_legacy as _from_legacy_result
        _contract_ctx = {"pipeline": cfg.get("pipeline", ""), "blog": blog_id, "stage": ""}
        _contract = _from_legacy_result(result, _contract_ctx)
        result["pipeline_status"] = _contract.status.value
    except Exception:
        pass

    # 성공/실패 기록
    if result.get("success"):
        _record_ledger(blog_id)
        # live quality gate (auto blogs only)
        if _QUALITY_LIVE_AVAILABLE:
            try:
                from pathlib import Path
                # locate latest post markdown path (simplified heuristic)
                site_root = Path(cfg.get("site_path", "")).resolve() if cfg.get("site_path") else None
                if site_root and (site_root / "content").exists():
                    # find most recent index.md
                    md_files = sorted(site_root.rglob("content/posts/*/index.md"), key=lambda p: p.stat().st_mtime, reverse=True)
                    if md_files:
                        qres = run_live_check(blog_id, md_files[0])
                        if qres.get("issues"):
                            logger.warning(f"[QUALITY LIVE] {blog_id} issues detected: {qres['issues']}")
            except Exception as e:
                logger.debug(f"[QUALITY LIVE] check skipped for {blog_id}: {e}")
        _reset_failure_count(blog_id)
        _reset_extended_failure_keys(blog_id)
        # P계열 발행 실패 이벤트 자동 close — 해당 blog가 정상 발행 성공하면
        # stale open 누적을 끊는다 (ERROR_PLAYBOOKS.md L161 "재시도 성공 시 close").
        _close_publish_failure_events(blog_id)
        if blog_id in ETAP_PIPELINE_BLOGS or blog_id in WORKERS_BLOGS or blog_id in STAP_PIPELINE_BLOGS:
            deploy_ok = _build_and_deploy_central(blog_id)
            if not deploy_ok:
                # Phase 58 Task 5: ETAP/Workers 배포 실패 캡처 — P04 (hook=post_deploy).
                # _build_and_deploy_central은 bool만 반환하므로 Hugo/P05 vs Wrangler/P04
                # 구분 정보는 없어 기본 P04 deploy_error로 보고 (구분 배선은 후속 작업).
                # 오탐 방지: 사이트가 여전히 200으로 서빙 중이면 transient 배포 실패로
                # 간주하고 CRITICAL 페이징을 건너뛴다(이벤트는 감사 추적용으로 기록).
                _site_live = _is_site_live(blog_id)
                logger.warning(
                    "[problem_monitor] 배포 실패 캡처: blog=%s reason=deploy_error "
                    "problem_id=P04 phase=post_deploy live=%s",
                    blog_id, _site_live)
                if not _site_live:
                    get_monitor().report(
                        blog_id, {"reason": "deploy_error"}, phase="post_deploy", extra={})
                else:
                    # 라이브면 즉시 close (flicker 방지 — 1886 부근 STAP 경로와 동일 정책)
                    try:
                        from shared.publish_error_events import close_publish_error_event
                        _ops_c = sqlite3.connect(str(PROJECT_DIR / "ops_dashboard" / "ops.db"))
                        try:
                            close_publish_error_event(_ops_c, blog_id=blog_id, problem_id="P04")
                        finally:
                            _ops_c.close()
                    except Exception:
                        pass
        # STAP/Hugo 배포 실패 — success=True지만 배포는 실패한 경우
        deploy_err = result.get("deploy_error")
        if deploy_err:
            _record_failure(blog_id, "deploy", deploy_err[:300])
            # 오탐 방지: 사이트가 여전히 정상 서빙(200) 중이면 transient 배포 실패로
            # 간주하고 즉각 CRITICAL 페이징을 건너뛴다(이벤트는 기록해 감사 추적 유지).
            _site_live = _is_site_live(blog_id)
            # 실시간 푸시: 디바운스 적용 (하루 1회)
            try:
                _ops_conn = sqlite3.connect(str(PROJECT_DIR / "ops_dashboard" / "ops.db"))
                init_debounce_tables(_ops_conn)
                _record_summary_event(_ops_conn, datetime.now().strftime("%Y-%m-%d"),
                    "deploy_error", blog_id)
                if not _site_live and _debounce_push(_ops_conn, blog_id, "deploy_error"):
                    _tg_error(blog_id, "deploy",
                        f"[{blog_id}] Hugo빌드/Wrangler배포 실패\n"
                        f"원인: {deploy_err[:200]}\n"
                        f"조치: {_deploy_log_hint(blog_id)} 확인 후 Hugo 테마/themesDir 점검")
                _ops_conn.close()
            except Exception:
                # 디바운스/사이트체크 실패 시 기존대로 발송
                if not _site_live:
                    _tg_error(blog_id, "deploy",
                        f"[{blog_id}] Hugo빌드/Wrangler배포 실패\n"
                        f"원인: {deploy_err[:200]}\n"
                        f"조치: {_deploy_log_hint(blog_id)} 확인 후 Hugo 테마/themesDir 점검")
        else:
            # 성공 + 배포 오류 없음 → stale P04 이벤트 close
            # (성공했으나 이전에 생성된 P04 open 이벤트가 남아있을 수 있음)
            try:
                from shared.publish_error_events import close_publish_error_event
                ops_conn = sqlite3.connect(str(PROJECT_DIR / "ops_dashboard" / "ops.db"))
                try:
                    closed = close_publish_error_event(
                        ops_conn, blog_id=blog_id, problem_id="P04")
                    if closed:
                        logger.info(f"[deploy] P04 이벤트 close: {blog_id} ({closed}건)")
                finally:
                    ops_conn.close()
            except Exception as _e:
                logger.warning(f"[deploy] P04 close 실패: {blog_id}: {_e}")
        # Phase 71 (SC-1): 발행 성공 직후 해당 blog 자동 재검사 트리거.
        # 예외 격리되어 있으므로 발행 성공 경로에 영향 없음.
        _trigger_post_publish_checks(blog_id)
    else:
        reason = result.get("reason", "unknown")
        # Phase 73 SC-1: STAP 배포 실패 → P04 deploy_error 로우팅.
        # STAP pipeline이 success=False + deploy_error 를 반환하면 배포 실패로
        # 분류해 중앙 P04 경로로 유도 (기존 opaque reason 대체).
        _deploy_err = result.get("deploy_error")
        if _deploy_err:
            logger.warning(
                "[problem_monitor] STAP 배포 실패 캡처: blog=%s reason=deploy_error "
                "problem_id=P04 phase=post_deploy",
                blog_id)
            get_monitor().report(
                blog_id, {"reason": "deploy_error"}, phase="post_deploy", extra={})
            _record_failure(blog_id, "deploy", _deploy_err[:300])
        if reason not in ("quota_met", "already_running", "duplicate_title", "cooldown"):
            _record_failure(blog_id, reason, f"pipeline 실패: {reason}")
            # no_result/no_content — 실제 파이프라인 실패 → 실시간 푸시 + 요약 기록
            if reason in ("no_result", "no_data", "fetch_error", "no_content"):
                # IPO 데이터가 없으면 하루 cooldown
                if blog_id == "ipo-hugo" and reason == "no_content":
                    _set_daily_cooldown(blog_id)
                else:
                    count = _increment_failure_count(blog_id)
                    if count >= _ESCALATION_THRESHOLD:
                        _set_daily_cooldown(blog_id)
                # 실시간 푸시: 디바운스 적용 (하루 1회)
                _problem_id = lookup_reason(reason).problem_id if lookup_reason(reason) else reason
                try:
                    _ops_conn = sqlite3.connect(str(PROJECT_DIR / "ops_dashboard" / "ops.db"))
                    init_debounce_tables(_ops_conn)
                    init_daily_summary_tables(_ops_conn)
                    if _debounce_push(_ops_conn, blog_id, _problem_id):
                        _tg_error(blog_id, reason,
                            f"[{blog_id}] pipeline {reason}: 발행 가능 데이터 없음\n"
                            f"연속 실패: {_increment_failure_count(blog_id)}회\n"
                            f"조치: 데이터 수집 소스/API 상태 확인")
                    _record_summary_event(_ops_conn, datetime.now().strftime("%Y-%m-%d"),
                        _problem_id, blog_id)
                    _ops_conn.close()
                except Exception:
                    # 디바운스 실패 시 기존대로 발송
                    _tg_error(blog_id, reason,
                        f"[{blog_id}] pipeline {reason}: 발행 가능 데이터 없음")
            elif reason in ("duplicate_slug", "duplicate_source_id"):
                existing = result.get("existing_url", "")
                dup_type = reason.replace("duplicate_", "")
                # 일일 요약에 기록 (텔레그램 소음 제거)
                try:
                    _ops_conn = sqlite3.connect(str(PROJECT_DIR / "ops_dashboard" / "ops.db"))
                    init_daily_summary_tables(_ops_conn)
                    _record_summary_event(_ops_conn, datetime.now().strftime("%Y-%m-%d"),
                        "P16", blog_id)
                    _ops_conn.close()
                except Exception as e:
                    logger.warning("[summary] P16 일일 요약 기록 실패: %s", e)
                    pass
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
                elif reason in ("no_topics", "no_topic"):
                    # PR3: no_topics는 정상 후보 소진(WAITING) — failure_count 증분 금지
                    _consec = 0
                else:
                    _consec = _increment_failure_count(blog_id, _spec.problem_id)
                logger.warning(
                    "[problem_monitor] result_parse 매핑: blog=%s reason=%s "
                    "problem_id=%s consecutive=%s",
                    blog_id, reason, _spec.problem_id, _consec)
                # PR2: candidate_exhausted(no_topics) symptom을 알림 발송과 무관하게
                # 항상 ops.db SSOT에 기록 (root 판정/retry 제한의 근거).
                # monitor.report는 consecutive:3 미만이면 기록하지 않으므로 별도 경로.
                if reason in ("no_topics", "no_topic"):
                    try:
                        from shared import publish_error_events as _events
                        # state stays 'open' — incident lifecycle이므로 유지
                        # (incident_key partial-index merge 보존, 스키마 변경 없음).
                        # reason='no_topics' 유지. WAITING 경계: M4 Dashboard가
                        # (reason='no_topics' + problem_id='P01' + retryable=0)을
                        # execution status=WAITING_FOR_CANDIDATES로 표시한다.
                        # Dashboard 구현은 본 브랜치 범위 밖.
                        _events.record_publish_error(
                            blog_id, reason,
                            str(result.get("stderr") or result.get("detail") or reason),
                            reason=reason, problem_id="P01", relation_type="symptom",
                            retryable=False, pipeline=_resolved_pipeline_for(blog_id, cfg),
                        )
                    except Exception:
                        # SSOT 기록 실패가 발행 흐름을 막지 않음 (조용히 통과)
                        pass
                get_monitor().report(
                    blog_id,
                    {"reason": reason, "stage": reason,
                     "detail": str(result.get("stderr") or result.get("detail") or reason)},
                    phase=_spec.hook,
                    extra={"consecutive_failures": _consec})

    # 슬롯 반납 (self_acquired인 경우만 — 상속 슬롯은 부모가 책임)
    if self_acquired:
        release_publish_slot(slot_id, blog_id)
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

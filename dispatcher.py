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
from datetime import datetime, timedelta
from pathlib import Path

import yaml

from shared.paths import FIVEK_ROOT, TAP_ROOT, STAP_ROOT
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
            except Exception:
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
    )


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


def preflight_check(blog_id: str) -> dict:
    """배포 전 콘텐츠 무결성 프리플라이트 체크.

    C01~C04·C08 중 critical이 1건이라도 있으면 배포 중단.

    Returns:
        {"blocked": bool, "violations": list[dict], "reason": str}
        - blocked=True: 배포 중단 필요
        - violations: [{rule_id, slug, severity, detail}, ...]
    """
    import json
    import re
    from datetime import datetime
    from pathlib import Path

    from shared.paths import FIVEK_ROOT

    violations = []
    blocked = False

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
    for md_file in recent_posts:
        content = md_file.read_text(encoding="utf-8", errors="replace")
        slug = md_file.parent.name

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
        except Exception:
            pass
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
        deploy_env = {k: v for k, v in os.environ.items() if k != "CLOUDFLARE_API_TOKEN"}
        deploy_env["PATH"] = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
        deploy_env["HUGO_THEMESDIR"] = "/Users/twinssn/Projects/shared-themes"
        r1 = subprocess.run(
            [HUGO, "--gc", "--minify"],
            cwd=str(site_path),
            capture_output=True, text=True,
            env=deploy_env
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
    # 발행 전 중복 체크 (QUOTA_OVERRIDE: 임시 우회)
    if _is_duplicate(blog_id):  # QUOTA_OVERRIDE
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
        result = _run_pipeline(cfg)
    except Exception as e:
        logger.warning(f"[dispatch] pipeline exception for {blog_id}: {type(e).__name__}: {str(e)[:150]}")
        result = {"success": False, "reason": f"exception:{type(e).__name__}"}

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
        result = {"success": result, "reason": "pipeline_returned_false" if not result else "pipeline_success"}
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
            # 실시간 푸시: 디바운스 적용 (하루 1회)
            try:
                _ops_conn = sqlite3.connect(str(PROJECT_DIR / "ops_dashboard" / "ops.db"))
                init_debounce_tables(_ops_conn)
                if _debounce_push(_ops_conn, blog_id, "deploy_error"):
                    _tg_error(blog_id, "deploy",
                        f"[{blog_id}] Hugo빌드/Wrangler배포 실패\n"
                        f"원인: {deploy_err[:200]}\n"
                        f"조치: STAP/logs/deploy.log 확인 후 Hugo 테마/themesDir 점검")
                _record_summary_event(_ops_conn, datetime.now().strftime("%Y-%m-%d"),
                    "deploy_error", blog_id)
                _ops_conn.close()
            except Exception:
                # 디바운스 실패 시 기존대로 발송
                _tg_error(blog_id, "deploy",
                    f"[{blog_id}] Hugo빌드/Wrangler배포 실패\n"
                    f"원인: {deploy_err[:200]}\n"
                    f"조치: STAP/logs/deploy.log 확인 후 Hugo 테마/themesDir 점검")
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
    else:
        reason = result.get("reason", "unknown")
        if reason not in ("quota_met", "already_running", "duplicate_title"):
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
                except Exception:
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

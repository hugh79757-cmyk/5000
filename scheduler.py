"""5000 Scheduler — launchd에서 호출
blogs.yaml의 스케줄에 따라 dispatcher를 실행하고,
놓친 스케줄을 publish_ledger 기반으로 보충한다.
"""
import logging
import os
import sqlite3
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import schedule
import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from shared.paths import FIVEK_ROOT, STAP_ROOT, DATA_DIR
from shared.publish_slot import (
    acquire_publish_slot,
    release_publish_slot,
    cleanup_stale_slots,
    MAX_CONCURRENT_PUBLISH,
)

from dotenv import load_dotenv

load_dotenv(os.path.expanduser("~/.env.common"))
load_dotenv(os.path.join(FIVEK_ROOT, ".env"))

# ── 패키지 의존성 체크 (표면 + 심층) ──
REQUIRED_PACKAGES = {
    "boto3": "boto3",
    "bs4": "beautifulsoup4",
    "openai": "openai",
    "dotenv": "python-dotenv",
    "yaml": "pyyaml",
    "requests": "requests",
    "schedule": "schedule",
}

def _check_imports() -> None:
    """표면 import 체크 — 모듈 로드 가능 여부"""
    missing = []
    for module, pip_name in REQUIRED_PACKAGES.items():
        try:
            __import__(module)
        except ImportError:
            missing.append(pip_name)
    if missing:
        print(f"[FATAL] 누락 패키지: {', '.join(missing)}")
        print(f"  실행: pip install {' '.join(missing)}")
        sys.exit(1)

def _check_boto3_deep() -> bool | None:
    """boto3 심층 체크 — 실제 Client 생성 + R2 헬스체크
    서브패키지 누락(boto3.resources) 등 표면 import로 못 잡는 문제 감지
    """
    try:
        import boto3 as _b3
        # 실제 session 생성으로 서브패키지完整性까지 검증
        _session = _b3.session.Session()
        _client = _session.client("s3",
            endpoint_url=os.getenv("R2_ENDPOINT", "https://non-existent"),
            aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID", ""),
            aws_secret_access_key=os.getenv("R2_ACCESS_SECRET_KEY", ""),
            region_name="auto",
        )
        # Client 생성만으로 충분 (실제 API 호출하지 않음)
        del _client, _session
        return True
    except ModuleNotFoundError as _e:
        _mod_name = str(_e).split("'")[1] if "'" in str(_e) else str(_e)
        print(f"[DEEP_CHECK] boto3 서브패키지 누락: {_mod_name}")
        return False
    except Exception as _e:
        # 설정 오류는 무시 (Client 생성까지만 검증)
        if "endpoint_url" in str(_e) or "access" in str(_e).lower():
            return True  # 설정 부재는 환경 문제, 패키지 문제 아님
        print(f"[DEEP_CHECK] boto3 비정상: {_e}")
        return False

def _auto_repair_boto3() -> bool | None:
    """boto3 재설치 + 텔레그램 알림"""
    print("[AUTO_REPAIR] boto3 재설치 시작...")
    try:
        import subprocess as _sp
        _pip = os.path.join(os.path.dirname(sys.executable), "pip")
        _r = _sp.run([_pip, "install", "--force-reinstall", "--no-deps", "boto3"],
                     capture_output=True, text=True, timeout=120)
        if _r.returncode == 0:
            # 버전 추출
            _ver = ""
            for _line in _r.stdout.split("\n"):
                if "Successfully installed" in _line:
                    _ver = _line.strip()
            print(f"[AUTO_REPAIR] boto3 재설치 완료: {_ver}")
            # 텔레그램 알림
            try:
                from shared.telegram_notifier import send_error
                send_error("boto3-auto-repair",
                           f"boto3 서브패키지 누락 → 자동 재설치 완료 ({_ver})")
            except Exception:
                pass
            return True
        print(f"[AUTO_REPAIR] boto3 재설치 실패: {_r.stderr[-200:]}")
        return False
    except Exception as _e:
        print(f"[AUTO_REPAIR] 예외: {_e}")
        return False

def _check_python_syntax() -> None:
    """프로젝트 내 모든 .py 파일 구문 검증 (IndentationError 사전 방지)"""
    import ast
    project_root = os.path.dirname(os.path.abspath(__file__))
    errors = []
    for root, _dirs, files in os.walk(project_root):
        _dirs[:] = [d for d in _dirs if d.startswith(".") or d in {"__pycache__", ".venv"}]
        for f in files:
            if not f.endswith(".py"):
                continue
            fpath = os.path.join(root, f)
            try:
                with open(fpath, encoding="utf-8") as fh:
                    ast.parse(fh.read())
            except SyntaxError as e:
                errors.append(f"{fpath}:{e.lineno} — {e.msg}")
    if errors:
        print(f"[FATAL] 구문 오류 발견 ({len(errors)}건):", file=sys.stderr)
        for err in errors:
            print(f"  ❌ {err}", file=sys.stderr)
        sys.exit(1)

def _check_dependencies() -> None:
    """통합 의존성 체크 — 표면 → 심층 → 자동복구"""
    _check_python_syntax()
    _check_imports()
    if not _check_boto3_deep():
        print("[WARN] boto3 심층 체크 실패 — 자동 복구 시도")
        if _auto_repair_boto3():
            # 재설치 후 재검증
            if _check_boto3_deep():
                print("[OK] boto3 복구 완료")
            else:
                print("[FATAL] boto3 복구 후에도 심층 체크 실패")
                sys.exit(1)
        else:
            print("[FATAL] boto3 복구 실패 — 수동 조치 필요")
            sys.exit(1)

def _check_thumbnail_health() -> None:
    """썸네일 생성 + R2 업로드 헬스체크 (스케줄러 시작 시 1회)"""
    logger.info("[HealthCheck] 썸네일 생성 테스트 시작...")
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "pipelines"))
        from senior.thumbnail import generate_senior_thumbnail
        url = generate_senior_thumbnail(
            title="헬스체크 테스트",
            category="생활지원",
            department="테스트",
            slug=f"healthcheck-{int(time.time())}",
        )
        if url and url.startswith("http"):
            logger.info(f"[HealthCheck] senior 썸네일 ✅ → {url[:60]}...")
        else:
            logger.warning("[HealthCheck] senior 썸네일 생성 실패 (R2 문제일 수 있음)")
    except Exception as e:
        logger.warning(f"[HealthCheck] senior 썸네일 예외: {e}")

    try:
        _stap_modules = set(sys.modules.keys())
        _stap_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "STAP")
        _old_path = sys.path.copy()
        sys.path.insert(0, _stap_path)
        from pipelines.thumbnail_factory import make_and_upload
        url2 = make_and_upload("stock", "헬스체크 테스트", "공시분석")
        if url2 and url2.startswith("http"):
            logger.info(f"[HealthCheck] stock 썸네일 ✅ → {url2[:60]}...")
        else:
            logger.warning("[HealthCheck] stock 썸네일 생성 실패")
    except Exception as e:
        logger.warning(f"[HealthCheck] stock 썸네일 예외: {e}")
    finally:
        sys.path = _old_path
        # STAP import 시 캐시된 모듈 제거 (auto_collector에서 5000/pipelines 사용하도록)
        for _m in set(sys.modules.keys()) - _stap_modules:
            del sys.modules[_m]

_check_dependencies()

import contextlib

from shared.telegram_notifier import send_error as _tg_error

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# FileHandler: scheduler.log 직접 기록 (stderr와 병행 — 이중화)
# 2026-08-26: 라이브 프로세스에서 FileHandler fd 누락로 scheduler.log 10:22 이후 silent.
# 재시작 필요. 여기서는 (1) 전용 logger에 직접 attach, (2) root에도 attach, (3) propagate 강제로
# 어느 경로든 scheduler.log 기록 보장. FileHandler 생성 실패 시 stderr로만 동작(크래시 방지).
from shared.paths import LOGS_DIR
_log_file = os.path.join(LOGS_DIR, "scheduler.log")
try:
    _fh = logging.FileHandler(_log_file, encoding="utf-8", delay=False)
    _fh.setLevel(logging.INFO)
    _fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logging.getLogger().addHandler(_fh)
    logger.addHandler(_fh)          # 전용 logger에도 직접 부착
    logger.propagate = True
except OSError as _e:
    logger.error(f"scheduler.log FileHandler 생성 실패 — stderr만 기록: {_e}")

PROJECT_DIR = FIVEK_ROOT
CONFIG_DIR = os.path.join(PROJECT_DIR, "config")
PYTHON = os.path.join(PROJECT_DIR, ".venv", "bin", "python3")
LEDGER_DB = os.path.join(PROJECT_DIR, "data", "content.db")


# ─── Heartbeat ───
HB_FILE = os.path.join(PROJECT_DIR, "logs", "heartbeat")

def _update_heartbeat() -> None:
    try:
        with open(HB_FILE, "w") as f:
            f.write(str(int(time.time())))
    except Exception:
        pass

MAX_CATCHUP_PER_BLOG = 3
# PR2: 동일 unresolved candidate_exhausted(no_topics) symptom에 대한
# scheduler catchup 재시도 허용 상한 (ops.db SSOT retry_count 기준)
MAX_CATCHUP_RETRY = 3
PUBLISH_DELAY = 60  # 블로그 간 딜레이(초)


# ─── Config ───

def load_config():
    """blogs.yaml(공통) + blogs.d/*.yaml(파이프라인별) 통합 로드"""
    main_path = os.path.join(CONFIG_DIR, "blogs.yaml")
    with open(main_path, encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    if "blogs" not in config:
        config["blogs"] = []
    blogs_d = os.path.join(CONFIG_DIR, "blogs.d")
    if os.path.isdir(blogs_d):
        for fname in sorted(os.listdir(blogs_d)):
            if not fname.endswith(".yaml"):
                continue
            fpath = os.path.join(blogs_d, fname)
            with open(fpath, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            config["blogs"].extend(data.get("blogs", []))
    return config


# ─── 발행 실행 ───

def _resource_id(blog_cfg) -> str:
    """availability key용 resource_id — car면 car.db (후보 소스)."""
    pipeline = blog_cfg.get("pipeline", "")
    return f"{pipeline}.db" if pipeline else ""


def _candidate_type(blog_cfg) -> str:
    """availability key용 candidate_type — post_type list는 콤마 조인."""
    pt = blog_cfg.get("post_type")
    if isinstance(pt, list):
        return ",".join(str(x) for x in pt if str(x).strip())
    return str(pt) if pt else ""


def _open_root_key(_events, blog_cfg) -> str:
    """해당 resource의 open root incident key — P33 stalled 등."""
    try:
        resource_id = _resource_id(blog_cfg)
        if not resource_id:
            return ""
        root = _events.get_open_root_incident(resource_id)
        return (root or {}).get("incident_key", "") or ""
    except Exception:
        return ""


def _availability_gate(blog_cfg) -> bool:
    """PR3: candidate availability gate — 후보가 없으면 dispatcher 실행 금지.

    - car: pending=0 → waiting_for_candidates 상태 기록 후 실행 생략.
    - checker 오류: 전체 중단도 fail-open도 금지 → 해당 blog 1회 안전 skip.
    - 미지원 pipeline: state=unknown 기록, 기존 실행 유지 (후보 없음으로 단정 금지).
    - P33 root open → blocked_by_source 전환.
    반환: True=실행 허용 / False=dispatcher 실행 생략 (run_publish는 None 반환).
    """
    blog_id = blog_cfg.get("id", "?")
    pipeline = blog_cfg.get("pipeline", "")
    try:
        from shared import candidate_availability, publish_error_events as _events
        root_key = _open_root_key(_events, blog_cfg)
        info = candidate_availability.check_availability(
            blog_cfg, linked_incident_key=root_key,
        )
    except Exception as e:
        logger.warning(f"AVAILABILITY: {blog_id} checker 오류 — 정규 schedule 1회 skip: {e}")
        try:
            from shared import publish_error_events as _events
            _events.upsert_availability(
                blog_id, pipeline=pipeline, resource_id=_resource_id(blog_cfg),
                candidate_type=_candidate_type(blog_cfg), state="checker_error",
                available_count=-1, reason=f"checker_error: {e}",
            )
        except Exception:
            pass
        return False

    try:
        from shared import publish_error_events as _events
        _events.upsert_availability(
            blog_id, pipeline=pipeline, resource_id=_resource_id(blog_cfg),
            candidate_type=_candidate_type(blog_cfg), state=info.get("state", "unknown"),
            available_count=info.get("available_count", 0), reason=info.get("reason", ""),
            source_health_state=info.get("source_health_state", ""),
            linked_incident_key=info.get("linked_incident_key", ""),
            next_check_at=info.get("next_check_at", ""),
        )
    except Exception:
        pass

    if info.get("state") == "unknown":
        return True  # 미지원 pipeline — 기존 실행 유지
    if candidate_availability.is_blocked(info):
        logger.info(
            f"AVAILABILITY: {blog_id} state={info.get('state')} "
            f"available={info.get('available_count')} — dispatcher 실행 생략"
        )
        return False
    return True


def _upsert_availability_healthy(blog_cfg) -> None:
    """발행 성공 → state=healthy 기록 (PHASE 4: RECOVERING → HEALTHY)."""
    try:
        from shared import publish_error_events as _events
        _events.upsert_availability(
            blog_cfg.get("id", "?"), pipeline=blog_cfg.get("pipeline", ""),
            resource_id=_resource_id(blog_cfg), candidate_type=_candidate_type(blog_cfg),
            state="healthy", available_count=1, reason="published",
        )
    except Exception:
        pass


def run_publish(blog_id) -> bool | None:
    """dispatcher를 subprocess로 실행 (quota 게이트 포함)

    반환: True=성공 / False=실패 / None=실행 생략 (availability gate 차단)
    """
    global _last_publish_reason
    _last_publish_reason = None  # 매 호출마다 초기화 — 이전 호출 잔여 방지
    blog_cfg = None
    # 중앙 quota 체크: ledger 기준으로 초과 시 skip
    try:
        config = load_config()
        blog_cfg = next((b for b in config.get("blogs", []) if isinstance(b, dict) and b.get("id") == blog_id), None)
        if blog_cfg:
            daily_quota = blog_cfg.get("daily_quota", 50)
            today_str = datetime.now().strftime("%Y-%m-%d")
            actual = _get_ledger_count(blog_id, today_str)
            if actual >= daily_quota:
                logger.info(f"QUOTA SKIP: {blog_id} actual={actual} >= quota={daily_quota}")
                return True  # 성공으로 처리 (재시도 방지)
    except Exception as e:
        logger.warning(f"Quota check failed for {blog_id}: {e}")

    # PR3: candidate availability gate — 후보 없으면 dispatcher 실행 금지
    if blog_cfg is not None and not _availability_gate(blog_cfg):
        return None

    logger.info("Publishing: " + blog_id)
    import json as _json

    # ── 전역 publish 동시성 제한: 슬롯 확보 ──────────────────────
    slot_id = acquire_publish_slot(blog_id)
    if slot_id is None:
        logger.warning(
            f"[CONCURRENCY] publish 슬롯 풀 소진 "
            f"(MAX_CONCURRENT={MAX_CONCURRENT_PUBLISH}) — {blog_id} 스킵 (실패로 미집계)"
        )
        # 슬롯 소진은 일시적 fleet 부하일 뿐 콘텐츠 실패 아님. None 반환→호출자에서
        # consecutive_failures 미증가(실패 집계 제외). bool|None 계약 준수.
        return None

    _last_publish_reason = None  # dispatcher JSON에서 파싱된 reason
    try:
        # env var로 슬롯 ID 상속 (자식 dispatcher가 이중 acquire 방지)
        run_env = os.environ.copy()
        run_env["PUBLISH_SLOT_ID"] = str(slot_id)
        run_env["PUBLISH_SLOT_BLOG_ID"] = blog_id

        # 블로그별 타임아웃: ETAP 등 대형 사이트는 LLM 폴백 체인 경쟁으로 느림
        _pipeline_timeout = int(blog_cfg.get("pipeline_timeout", 600)) if blog_cfg else 600

        result = subprocess.run(
            [PYTHON, "dispatcher.py", blog_id],
            cwd=PROJECT_DIR,
            capture_output=True, text=True, timeout=_pipeline_timeout,
            env=run_env,
        )
        parsed_success = None
        if result.stdout:
            for line in result.stdout.strip().split("\n")[-3:]:
                logger.info("  [OUT] " + line)
            # 마지막 줄이 JSON 결과라고 가정하고 파싱
            last_line = result.stdout.strip().split("\n")[-1].strip()
            try:
                parsed = _json.loads(last_line)
                parsed_success = bool(parsed.get("success"))
                if parsed_success:
                    logger.info(f"[PUBLISH] {blog_id} 발행 성공")
                else:
                    reason = parsed.get("reason", "unknown")
                    _last_publish_reason = reason
                    logger.error(f"[PUBLISH] {blog_id} 발행 실패 — stage={reason}")
            except (_json.JSONDecodeError, Exception):
                pass
        if result.returncode != 0:
            error_text = (result.stderr or result.stdout or "dispatcher returned non-zero")
            logger.error("  ERR: " + error_text[-200:])
            _tg_error(blog_id, "scheduler", error_text[-300:])
            return False
        if parsed_success is not True:
            if result.stderr:
                logger.error("  ERR: " + result.stderr.strip().splitlines()[-1][-500:])
            logger.error(f"[PUBLISH] {blog_id} dispatcher reported failure or missing JSON")
            return False
        if blog_cfg is not None:
            _upsert_availability_healthy(blog_cfg)
        return True
    except subprocess.TimeoutExpired:
        logger.exception(blog_id + f" timeout ({_pipeline_timeout}s)")
        _tg_error(blog_id, "scheduler", f"timeout {_pipeline_timeout}s")
        return False
    except Exception as e:
        logger.exception(blog_id + " failed: " + str(e))
        _tg_error(blog_id, "scheduler", str(e)[:300])
        return False
    finally:
        # 슬롯 반납 (crash-safe: 프로세스가 살아있으면 여기서 반납,
        # 사망 시 pid 체크로 다른 acquire에서 자동 회수)
        release_publish_slot(slot_id, blog_id)


# ─── 발행 큐 ───

_publish_queue = []
_queue_lock = threading.Lock()


def queue_publish(blog_id) -> None:
    """동시간대 블로그를 큐에 넣고 순차 실행 (중복 방지)"""
    # ── inactive 실시간 체크: YAML이 바뀌어도 즉시 반영 ──
    try:
        _cfg = load_config()
        _blog_cfg = next(
            (b for b in _cfg.get("blogs", [])
             if isinstance(b, dict) and b.get("id") == blog_id),
            None
        )
        if _blog_cfg and _blog_cfg.get("status") != "active":
            logger.info(f"Queue skip (inactive): {blog_id}")
            return
    except Exception as _e:
        logger.warning(f"queue_publish config check failed: {_e}")

    with _queue_lock:
        if blog_id in _publish_queue:
            logger.info(f"Queue skip (duplicate): {blog_id}")
            return
        _publish_queue.append(blog_id)
        if len(_publish_queue) == 1:
            threading.Thread(target=_drain_queue, daemon=True).start()


def _drain_queue() -> None:
    """큐에 쌓인 블로그를 순차적으로 실행"""
    while True:
        with _queue_lock:
            if not _publish_queue:
                return
            blog_id = _publish_queue.pop(0)
        logger.info(f"Queue executing: {blog_id} (remaining: {len(_publish_queue)})")
        try:
            _success = run_publish(blog_id)
            if _success is not None:
                _track_publish_result(blog_id, bool(_success), _last_publish_reason)
        except Exception as e:
            logger.exception(f"Queue publish failed: {blog_id} - {e}")
            _track_publish_result(blog_id, False)
        with _queue_lock:
            if not _publish_queue:
                return
        time.sleep(PUBLISH_DELAY)


# ─── Catchup (중앙 ledger 기반) ───

_catchup_lock = threading.Lock()  # catchup 중복 실행 방지


def _get_ledger_count(blog_id, date_str):
    """publish_ledger에서 오늘 발행 건수 조회 — published만 카운트"""
    try:
        conn = sqlite3.connect(LEDGER_DB)
        row = conn.execute(
            "SELECT COUNT(*) FROM publish_ledger WHERE blog_id=? AND date(created_at)=? AND status='published'",
            (blog_id, date_str)
        ).fetchone()
        conn.close()
        return row[0] if row else 0
    except Exception:
        return 0


def catchup_missed() -> None:
    """놓친 스케줄 보충 발행 — 5분마다 체크 (중복 실행 방지)"""
    if not _catchup_lock.acquire(blocking=False):
        logger.debug("Catchup already running, skipping")
        return
    try:
        _catchup_missed_inner()
    finally:
        _catchup_lock.release()


def _catchup_missed_inner() -> None:
    """Catchup 실제 로직"""
    from shared import publish_error_events as _events

    config = load_config()
    blogs = config.get("blogs", [])
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")

    # 스케줄러 시작 직후 보호: 첫 스케줄 시각 이전이면 catchup 안 함
    first_schedule_hour = 7
    if now.hour < first_schedule_hour:
        return

    for blog in blogs:
        if not isinstance(blog, dict) or blog.get("status") != "active":
            continue
        blog_id = blog["id"]

        # 일일 catchup 상한 (ops.db 영속화 — 재시작 후에도 유지)
        attempts = _events.get_catchup_attempts(blog_id, today_str)
        if attempts >= MAX_CATCHUP_PER_BLOG:
            continue

        # PR2: unresolved candidate_exhausted(no_topics) symptom retry 제한 (ops.db SSOT)
        try:
            _retry_state = _events.get_catchup_retry_state(blog_id)
        except Exception as e:
            # fail-open/fail-closed 금지: 해당 blog catchup만 안전하게 skip
            logger.warning(f"CATCHUP: {blog_id} retry 상태 조회 실패 — 해당 blog만 skip: {e}")
            continue
        if _retry_state:
            if _retry_state.get("retry_blocked"):
                logger.info(
                    f"CATCHUP: {blog_id} retry block 유지 — catchup 제외 "
                    f"(retry_count={_retry_state.get('retry_count', 0)})"
                )
                continue
            if _retry_state.get("retry_count", 0) >= MAX_CATCHUP_RETRY:
                try:
                    _events.record_retry_amplification(
                        blog_id, root_incident_key=_retry_state.get("root_incident_key") or ""
                    )
                except Exception as e:
                    logger.warning(f"CATCHUP: {blog_id} amplifier 기록 실패: {e}")
                logger.warning(
                    f"CATCHUP: {blog_id} retry_count={_retry_state.get('retry_count')} "
                    f">= {MAX_CATCHUP_RETRY} — catchup 제외 (retry_amplification open)"
                )
                continue

        # daily_quota 체크 — quota 도달 시 skip
        daily_quota = blog.get("daily_quota", 50)
        actual = _get_ledger_count(blog_id, today_str)
        if actual >= daily_quota:
            continue

        # 오늘 발행해야 할 횟수: 현재 시각 이전 스케줄 수
        times = blog.get("schedule", {}).get("times", [])
        expected = 0
        for t in times:
            parts = str(t).split(":")
            if len(parts) != 2:
                logger.warning(f"CATCHUP: 잘못된 스케줄 시각 무시 — {blog_id} time={t!r}")
                continue
            try:
                h, m = map(int, parts)
            except ValueError:
                logger.warning(f"CATCHUP: 잘못된 스케줄 시각 무시 — {blog_id} time={t!r}")
                continue
            if h < now.hour or (h == now.hour and m <= now.minute):
                expected += 1

        if expected == 0:
            continue

        missed = expected - actual
        if missed <= 0:
            continue

        # 중복 방지: 현재 큐에 같은 blog_id가 있으면 skip
        with _queue_lock:
            if blog_id in _publish_queue:
                continue

        _events.set_catchup_attempts(blog_id, today_str, attempts + 1)
        logger.info(
            f"CATCHUP: {blog_id} expected={expected} actual={actual} "
            f"missed={missed} quota={daily_quota} attempt={attempts + 1}/{MAX_CATCHUP_PER_BLOG}"
        )
        try:
            before = _events.get_open_incident(blog_id, "P01", reason="no_topics")
            before_occurrences = before.get("occurrence_count", 0) if before else 0
            success = run_publish(blog_id)
            if success is None:
                # availability gate 차단 (후보 없음) — 실패로 집계하지 않는다
                logger.info(f"CATCHUP: {blog_id} 후보 없음 — 보충 생략")
                continue
            _track_publish_result(blog_id, bool(success), _last_publish_reason)
            if not success:
                logger.warning(f"CATCHUP: {blog_id} 보충 실패 ({attempts + 1}/{MAX_CATCHUP_PER_BLOG})")
                after = _events.get_open_incident(blog_id, "P01", reason="no_topics")
                if after and after.get("occurrence_count", 0) > before_occurrences:
                    # 실제 pipeline 실행에서 no_topics 재발 — catchup 재시도로만 누적
                    _events.increment_incident_retry(blog_id, "P01")
                    logger.warning(
                        f"CATCHUP: {blog_id} no_topics 재발 — retry_count 증가 "
                        f"(occurrence_count={after.get('occurrence_count')})"
                    )
            else:
                # 발행 성공 → P01 symptom close + P34 close + retry block 해제 + retry reset
                try:
                    _events.release_blog_retry_state(blog_id)
                    logger.info(f"CATCHUP: {blog_id} 발행 성공 — no_topics symptom close + P34 close + retry reset")
                except Exception as e:
                    logger.warning(f"CATCHUP: {blog_id} retry state 해제 실패: {e}")
        except Exception as e:
            logger.exception(f"CATCHUP: {blog_id} 예외: {e}")
        time.sleep(5)


# ─── 배치 작업 ───

def batch_deploy() -> None:
    logger.info("Batch deploy started")
    try:
        result = subprocess.run(
            ["bash", os.path.join(PROJECT_DIR, "scripts", "batch_push.sh")],
            capture_output=True, text=True, timeout=1800
        )
        parsed_success = None
        if result.stdout:
            for line in result.stdout.strip().split("\n")[-5:]:
                logger.info("  " + line)
    except Exception as e:
        logger.exception("Batch deploy failed: " + str(e))


def _run_quality_scan() -> None:
    """발행 후 품질 스캔 + 텔레그램 리포트 (매일 23:00)"""
    try:
        from pipelines.etap.quality_scanner import run_scan
        result = run_scan()
        logger.info(f"[QualityScan] 완료: {result}")
    except Exception as e:
        logger.exception(f"[QualityScan] 실패: {e}")
        _tg_error("QualityScan 오류", str(e))


def _run_p32_scan() -> None:
    """P32: 배포된 글의 빈 내용 사후 검증 (주기적 스캔, 6시간 간격).

    모든 active 블로그 대상 detect_empty_content_deployed 실행.
    실HTTP 수행하므로 순차 실행 + 블로그 간 2초 지연(대상 사이트 부하 방지).
    dry_run에서도 스캔 자체는 실행(알림은 억제됨).
    """
    try:
        import time as _time
        from shared.publisher import load_blogs
        from shared.problem_monitor import get_monitor

        blogs = load_blogs()
        active_blogs = [b for b in blogs if b.get("status") == "active"]
        logger.info(f"[P32] 스캔 시작: active 블로그 {len(active_blogs)}개")

        monitor = get_monitor()
        scanned = 0
        alerted = 0
        for blog in active_blogs:
            blog_id = blog.get("id", "")
            domain = blog.get("domain", "")
            site_path = blog.get("site_path", "")
            if not domain or not site_path:
                continue
            try:
                sent = monitor.report_deployed_content(blog_id)
                scanned += 1
                if sent:
                    alerted += 1
                    logger.info(f"[P32] {blog_id}: 알림 발송 — {sent}")
                else:
                    logger.debug(f"[P32] {blog_id}: PASS")
            except Exception as e:
                logger.warning(f"[P32] {blog_id} 스캔 예외: {e}")
            # 2초 지연 — 대상 사이트 동시 HTTP 부하 방지
            _time.sleep(2)

        logger.info(f"[P32] 스캔 완료: {scanned}개 스캔, {alerted}개 알림")
    except Exception as e:
        logger.exception(f"[P32] 스캔 실패: {e}")
        try:
            from shared.telegram_notifier import send_error
            send_error("P32 스캔 오류", error_msg=str(e))
        except Exception:
            pass


def _snapshot_check_fails(conn) -> set:
    """현재 check_results 에서 fail 상태인 (blog_id, check_name) 집합 스냅샷.

    record_check 는 UPSERT(최신 상태만 보관, 이력 없음)라, 실행 전 스냅샷과
    실행 후 집합을 대조해야 '신규 FAIL' 만 골라낼 수 있다.
    """
    rows = conn.execute(
        "SELECT blog_id, check_name FROM check_results WHERE status='fail'"
    ).fetchall()
    return {(r["blog_id"], r["check_name"]) for r in rows}


def _alert_new_check_fails(conn, before_fails: set) -> None:
    """직전 스냅샷 대비 신규 FAIL 만 텔레그램으로 요약 발송 (fail-soft).

    - 신규 FAIL 없으면 아무것도 안 함 (지속 FAIL 재알림 없음).
    - 같은 날 이미 fleet 알림을 보냈으면 디바운스로 억제 (이어지는 FAIL 노이즈 방지).
    - 알림 실패는 로그만 남기고 run-checks 흐름을 막지 않음.
    """
    try:
        from shared.notification_debounce import init_debounce_tables, should_push
        from shared.telegram_notifier import send_dashboard_alert

        new_fails = sorted(_snapshot_check_fails(conn) - before_fails)
        if not new_fails:
            return
        init_debounce_tables(conn)
        if not should_push(conn, "fleet", "new_check_fail"):
            logger.info("[RecheckAll] 신규 FAIL %d건 디바운스 억제", len(new_fails))
            return
        detail = "\n".join(f"• {bid} / {check}" for bid, check in new_fails)
        send_dashboard_alert("fleet", f"new_check_fail ({len(new_fails)}건)", "fail", detail)
    except Exception:
        logger.exception("[RecheckAll] 신규 FAIL 알림 실패 (무시 — run-checks 지속)")


def _run_recheck_all() -> None:
    """Phase 71 (SC-1): 주기적 전체 재검사 (2차 안전망).

    발행 성공 시점의 훅(_trigger_post_publish_checks) 외에, 주기적으로
    전체 블로그를 재검사해 check_results 를 갱신한다. 비용 부담을 고려해
    매시간 1회로 등록(저빈도). run_all_checks 단일 진입점 사용(중복 없음).
    """
    try:
        from ops_dashboard.checks import run_all_checks
        from ops_dashboard.db import get_conn
        from pathlib import Path

        ops_db = Path(PROJECT_DIR) / "ops_dashboard" / "ops.db"
        # get_conn 은 row_factory=sqlite3.Row 설정 — run_all_checks/get_all_blogs 가
        # dict(row) 를 가정하므로 raw sqlite3.connect 가 아닌 get_conn 사용.
        conn = get_conn(str(ops_db))
        try:
            # 실행 전 fail 쌍 스냅샷 — record_check(UPSERT)는 이력이 없어
            # 직전 상태를 in-memory diff 로만 알 수 있음. 신규 FAIL 알림 기준.
            before_fails = _snapshot_check_fails(conn)
            summary = run_all_checks(conn)
            logger.info(
                "[RecheckAll] 완료: total=%d pass=%d fail=%d unknown=%d",
                summary.get("total", 0),
                summary.get("pass", 0),
                summary.get("fail", 0),
                summary.get("unknown", 0),
            )
            # 신규 FAIL → 텔레그램 [OPS ALERT] 1회 (디바운스/fail-soft)
            _alert_new_check_fails(conn, before_fails)
            # Phase 71 (SC-4): fail 규칙이 있는 블로그의 감지 결과를 폐루프 디스패처로
            # 전달 (안전 fixer 무인 실행, 파괴등급은 pending_fixes 적재). 발행 훅 외
            # '재검사 경로'의 2차 안전망. 실패 시 무영향 로깅만 (run_all_checks 결과 보존).
            failed_blog_ids = [
                r["blog_id"]
                for r in conn.execute(
                    "SELECT DISTINCT blog_id FROM check_results WHERE status='fail'"
                ).fetchall()
            ]
            if failed_blog_ids:
                try:
                    from dispatcher import _run_autofix_after_checks
                except Exception as _impe:
                    _run_autofix_after_checks = None
                    logger.warning("[RecheckAll] dispatcher import 실패(재검사 배선 건너뜀): %s", _impe)
                if _run_autofix_after_checks:
                    for bid in failed_blog_ids:
                        _run_autofix_after_checks(conn, bid, str(ops_db))
        finally:
            conn.close()
    except Exception as e:
        logger.exception("[RecheckAll] 실패: %s", e)
        try:
            from shared.telegram_notifier import send_error

            send_error("RecheckAll 오류", error_msg=str(e))
        except Exception:
            pass


def daily_report() -> None:
    logger.info("Daily report")
    try:
        result = subprocess.run(
            [PYTHON, "dispatcher.py", "report"],
            cwd=PROJECT_DIR,
            capture_output=True, text=True, timeout=120
        )
        parsed_success = None
        if result.stdout:
            logger.info("  " + result.stdout.strip()[-200:])
    except Exception as e:
        logger.exception("Report failed: " + str(e))


def _run_gap_keyword_sync() -> None:
    """news-keyword-pro golden CSV -> gap.db 동기화"""
    try:
        result = subprocess.run(
            ["python3", os.path.join(PROJECT_DIR, "scripts", "sync_golden_to_gap.py")],
            capture_output=True, text=True, timeout=120, cwd=PROJECT_DIR
        )
        logger.info(f"GAP keyword sync: {result.stdout.strip().split(chr(10))[-1]}")
        if result.returncode != 0:
            logger.warning(f"GAP keyword sync stderr: {result.stderr[:200]}")
    except Exception as e:
        logger.exception(f"GAP keyword sync failed: {e}")


def _run_car_refresh() -> None:
    """CAR daily_refresh subprocess 실행 + resource health를 ops.db SSOT에 기록.

    - Popen poll loop로 실행 중에도 heartbeat를 갱신해 watchdog kickstart 루프 방지.
    - timeout 시 process group 전체(killpg)를 정리한다 — 예외를 빈 성공으로 처리하지 않는다.
    """
    import re
    import signal
    import tempfile
    from shared import publish_error_events as _events

    resource_id = _events.DEFAULT_STALLED_RESOURCE_ID
    job_name = "pipelines/car/daily_refresh.py"
    started = time.time()
    refresh_timeout = int(os.environ.get("CAR_REFRESH_TIMEOUT_SEC", "3600"))
    deadline = started + refresh_timeout

    try:
        _events.record_resource_start(resource_id, job_name=job_name)
    except Exception as e:
        logger.warning(f"CAR daily_refresh resource start 기록 실패: {e}")

    # 파일 리다이렉트 (PIPE 대신) → pipe deadlock 방지. start_new_session → killpg로 후손 정리 가능.
    stdout_tmp = tempfile.TemporaryFile(mode="w+", encoding="utf-8")
    stderr_tmp = tempfile.TemporaryFile(mode="w+", encoding="utf-8")
    timed_out = False
    try:
        proc = subprocess.Popen(
            [sys.executable, "-m", "pipelines.car.daily_refresh"],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            stdout=stdout_tmp, stderr=stderr_tmp, text=True,
            start_new_session=True,
        )
        while proc.poll() is None:
            try:
                _update_heartbeat()
                _events.record_resource_heartbeat(resource_id)
            except Exception:
                pass  # heartbeat 실패가 refresh 결과를 왜곡하지 않는다
            if time.time() > deadline:
                timed_out = True
                break
            time.sleep(30)

        if timed_out:
            # process group 전체 정리 (자식/손자 포함) — 10초 대기 후 강제 kill
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except Exception:
                proc.terminate()
            try:
                proc.wait(timeout=10)
            except Exception:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except Exception:
                    proc.kill()
                proc.wait()

        stdout_tmp.seek(0)
        stdout = stdout_tmp.read()
        stderr_tmp.seek(0)
        stderr = stderr_tmp.read()

        duration = time.time() - started
        if timed_out:
            _events.record_resource_timeout(resource_id, duration_seconds=duration)
            logger.error(f"CAR daily_refresh timed out ({refresh_timeout}s) — process group killed")
        elif proc.returncode == 0:
            m = re.search(r"신규토픽 (\d+)개", stdout or "")
            rows_inserted = int(m.group(1)) if m else 0
            _events.record_resource_success(
                resource_id, rows_inserted=rows_inserted, duration_seconds=duration
            )
            logger.info(f"CAR daily_refresh completed (exit=0, rows_inserted={rows_inserted})")
            # 신규 candidate 유입 → pending>0인 blog들의 retry block 해제
            if rows_inserted > 0:
                _release_pending_blog_retry_states(_events)
            # refresh 결과를 availability 상태에 반영 (pending>0 → recovering, pending=0 → waiting 유지)
            _evaluate_car_availability_after_refresh(_events)
        else:
            detail = (stderr or stdout or "").strip()[:500]
            _events.record_resource_failure(
                resource_id, error_reason=detail or f"exit={proc.returncode}",
                duration_seconds=duration,
            )
            logger.error(f"CAR daily_refresh failed (exit={proc.returncode}): {detail}")
    except Exception as e:
        duration = time.time() - started
        try:
            _events.record_resource_failure(
                resource_id, error_reason=str(e)[:500], duration_seconds=duration
            )
        except Exception:
            pass
        logger.exception(f"CAR daily_refresh error: {e}")
    finally:
        stdout_tmp.close()
        stderr_tmp.close()

    # SLA(36h) 위반 시 공용 resource root incident 열기 (멱등)
    try:
        _events.evaluate_and_open_root_stalled()
    except Exception as e:
        logger.warning(f"CAR root stalled 평가 실패: {e}")


def _release_pending_blog_retry_states(_events) -> None:
    """car.db에 pending>0인 blog들의 retry 상태만 해제 (pending=0인 blog 유지).

    root(P33)는 건드리지 않는다 — root close는 refresh 성공 증거로만 가능.
    """
    car_db = os.path.join(PROJECT_DIR, "data", "car.db")
    try:
        conn = sqlite3.connect(f"file:{car_db}?mode=ro", uri=True, timeout=5)
        try:
            rows = conn.execute(
                "SELECT DISTINCT site_id FROM topics WHERE status = 'pending'"
            ).fetchall()
        finally:
            conn.close()
    except Exception as e:
        logger.warning(f"CAR pending blog 조회 실패: {e}")
        return
    for row in rows:
        blog_id = row[0]
        if not blog_id:
            continue
        try:
            _events.release_blog_retry_state(blog_id)
            logger.info(f"CAR refresh 유입 복구 — {blog_id} retry block 해제 (pending>0)")
        except Exception as e:
            logger.warning(f"CAR refresh {blog_id} retry state 해제 실패: {e}")


def _evaluate_car_availability_after_refresh(_events) -> None:
    """refresh 성공 후 car blog availability 재평가 (PHASE 4 상태 전이).

    - pending>0: waiting/blocked였던 blog는 recovering로 전이 (다음 발행 성공 시 healthy).
    - pending=0: waiting_for_candidates 유지 (rows_inserted=0이어도 source는 정상).
    - P33 root open이면 blocked_by_source 반영.
    """
    try:
        config = load_config()
        blogs = config.get("blogs", [])
    except Exception as e:
        logger.warning(f"AVAILABILITY: refresh 후 blog 목록 조회 실패: {e}")
        return
    try:
        from shared import candidate_availability
    except Exception as e:
        logger.warning(f"AVAILABILITY: candidate_availability import 실패: {e}")
        return
    for blog in blogs:
        if not isinstance(blog, dict) or blog.get("pipeline") != "car":
            continue
        blog_id = blog.get("id", "")
        if not blog_id:
            continue
        try:
            root_key = _open_root_key(_events, blog)
            info = candidate_availability.check_availability(blog, linked_incident_key=root_key)
            prev = _events.get_availability(
                blog_id, pipeline="car",
                resource_id=_resource_id(blog), candidate_type=_candidate_type(blog),
            )
            prev_state = (prev or {}).get("state")
            if info.get("state") == "healthy":  # pending>0
                # refresh 후 후보 복구 — waiting/blocked/recovering였으면 recovering 유지,
                # 이미 healthy였으면 healthy 유지
                new_state = (
                    "recovering"
                    if prev_state in ("waiting_for_candidates", "blocked_by_source", "recovering")
                    else "healthy"
                )
            else:
                new_state = info.get("state", "waiting_for_candidates")  # pending=0 → waiting 유지
            _events.upsert_availability(
                blog_id, pipeline="car", resource_id=_resource_id(blog),
                candidate_type=_candidate_type(blog), state=new_state,
                available_count=info.get("available_count", 0),
                reason=info.get("reason", ""),
                source_health_state=info.get("source_health_state", ""),
                linked_incident_key=info.get("linked_incident_key", ""),
                next_check_at=info.get("next_check_at", ""),
            )
            if new_state == "recovering":
                logger.info(f"AVAILABILITY: {blog_id} refresh 후 후보 복구 — RECOVERING")
        except Exception as e:
            logger.warning(f"AVAILABILITY: {blog_id} refresh 후 평가 실패: {e}")


def _run_stap_collector() -> None:
    """STAP data collector를 subprocess로 완전 격리 실행 (import shadow 방지)"""
    import subprocess as _sp
    import tempfile as _tmp
    stap_root = STAP_ROOT
    stap_python = os.path.join(stap_root, ".venv", "bin", "python3")
    if not os.path.exists(stap_python):
        stap_python = sys.executable
        logger.warning("[STAP collector] .venv/python3 없음 → sys.executable 사용")

    runner = "\n".join([
        "import sys, os",
        "sys.path.insert(0, " + repr(stap_root) + ")",
        "os.chdir(" + repr(stap_root) + ")",
        "from dotenv import load_dotenv",
        "load_dotenv(os.path.join(" + repr(stap_root) + ', ".env"), override=True)',
        "from pipelines.data_collector import collect_all",
        "result = collect_all()",
        "print('OK' if result else 'FAIL')",
    ])

    try:
        with _tmp.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(runner)
            runner_path = f.name

        proc = _sp.run(
            [stap_python, runner_path],
            capture_output=True, text=True, timeout=300,
            cwd=stap_root,
        )
        stdout = (proc.stdout or "").strip()
        stderr = (proc.stderr or "").strip()
        if proc.returncode == 0:
            logger.info(f"[STAP collector] 완료: {stdout}")
        else:
            logger.error(f"[STAP collector] 실패 (exit={proc.returncode}): {stderr or stdout}")
    except _sp.TimeoutExpired:
        logger.exception("[STAP collector] 300초 타임아웃")
    except Exception as e:
        logger.exception(f"[STAP collector] 오류: {e}")
    finally:
        with contextlib.suppress(Exception):
            os.unlink(runner_path)



def _run_etap_collectors() -> None:
    """ETAP 데이터 컬렉터들을 subprocess로 완전 격리 실행 (import shadow 방지)

    수집 대상:
    - viator.py: Viator deals feed (매일)
    - aviasales.py: 항공권 가격/캘린더/노선 (매일)
    - topic_expander.py: 토픽 부족분 자동 보충 (매일)
    - nomad_data.py: 코워킹/카페/기후 (주 1회)
    - omio.py: Omio 교통편 CSV (주 1회, CSV 업데이트 의존)
    - airalo.py: Airalo eSIM XML (주 1회, XML 업데이트 의존)
    """
    import subprocess as _sp
    import tempfile as _tmp
    etap_root = os.path.join(PROJECT_DIR, "pipelines", "etap")
    if not os.path.isdir(etap_root):
        logger.warning("[ETAP collector] etap 디렉토리 없음")
        return

    # 컬렉터별 실행 스크립트 생성
    collectors = [
        ("viator", "from collectors.viator import run_full_collection; print('viator:', run_full_collection())"),
        ("aviasales", "from collectors.aviasales import run_full_collection; print('aviasales:', run_full_collection())"),
        ("topic_expander", "from collectors.topic_expander import expand_topics; r = expand_topics(); print('topic_expander:', r['added'])"),
        ("nomad_data", "from collectors.nomad_data import main; main()"),
        ("omio", "from collectors.omio import run_full_collection; print('omio:', run_full_collection())"),
        ("airalo", "from collectors.airalo import run_full_collection; print('airalo:', run_full_collection())"),
    ]

    ok_count = 0
    fail_count = 0

    for name, code in collectors:
        runner = "\n".join([
            "import sys, os, logging",
            f"logging.basicConfig(level=logging.INFO, format='%(asctime)s [ETAP-{name}] %(message)s')",
            "logger = logging.getLogger('etap')",
            f"sys.path.insert(0, {repr(etap_root)})",
            f"os.chdir({repr(etap_root)})",
            "from dotenv import load_dotenv",
            "load_dotenv(os.path.join(" + repr(etap_root) + ', ".env"), override=True)',
            code,
        ])

        try:
            with _tmp.NamedTemporaryFile(mode="w", suffix=f"_{name}.py", delete=False, encoding="utf-8") as f:
                f.write(runner)
                runner_path = f.name

            proc = _sp.run(
                [sys.executable, runner_path],
                capture_output=True, text=True, timeout=600,
                cwd=etap_root,
            )
            stdout = (proc.stdout or "").strip()
            stderr = (proc.stderr or "").strip()
            if proc.returncode == 0:
                logger.info(f"[ETAP {name}] 완료: {stdout[-200:]}")
                ok_count += 1
            else:
                logger.error(f"[ETAP {name}] 실패 (exit={proc.returncode}): {stderr[-200:]}")
                fail_count += 1
        except _sp.TimeoutExpired:
            logger.exception(f"[ETAP {name}] 600초 타임아웃")
            fail_count += 1
        except Exception as e:
            logger.exception(f"[ETAP {name}] 오류: {e}")
            fail_count += 1
        finally:
            with contextlib.suppress(Exception):
                os.unlink(runner_path)

    logger.info(f"[ETAP collector] 완료: {ok_count} 성공, {fail_count} 실패")


def _run_senior_sync() -> None:
    """senior.db 서비스 데이터 일일 동기화 (pending 보충)"""
    try:
        import sys
        sys.path.insert(0, FIVEK_ROOT)
        from pipelines.senior.fetcher import get_pending_count, sync_services
        pending = get_pending_count()
        logger.info(f"[SeniorSync] 현재 pending: {pending}건")
        # ✅ pending 500건 이상이면 sync 불필요 (2026-06-12 추가)
        if pending >= 500:
            logger.info(f"[SeniorSync] pending {pending}건 충분 — sync 스킵")
            return
        synced = sync_services()
        logger.info(f"[SeniorSync] 완료: {synced}건 신규 저장, pending: {get_pending_count()}건")
    except Exception as e:
        logger.exception(f"[SeniorSync] 실패: {e}")

def _run_festival_refresh() -> None:
    try:
        subprocess.run([sys.executable, "scripts/refresh_festival.py"],
                       cwd=os.path.dirname(os.path.abspath(__file__)), timeout=600)
        logger.info("Festival refresh completed")
    except Exception as e:
        logger.exception(f"Festival refresh failed: {e}")


def _run_course_refresh() -> None:
    try:
        subprocess.run([sys.executable, "scripts/refresh_course.py"],
                       cwd=os.path.dirname(os.path.abspath(__file__)), timeout=120)
        logger.info("Course refresh completed")
    except Exception as e:
        logger.exception(f"Course refresh failed: {e}")


def _run_tap_fetcher(source: str = "all") -> None:
    """TAP content_pool 갱신 — core.fetcher를 subprocess로 실행.

    5000 venv python에 sqlalchemy이 필요하며, 없을 경우 실패 로그만 남기고 종료.
    (refresh_festival.py / refresh_course.py와 별도 스케줄로 운영.)
    """
    tap_root = os.getenv("TAP_ROOT", "/Users/twinssn/Projects/TAP")
    if not os.path.isdir(tap_root):
        logger.warning(f"[TAP fetcher] TAP_ROOT 없음: {tap_root}")
        return
    if not os.path.isdir(os.path.join(tap_root, "core")):
        logger.warning(f"[TAP fetcher] core/ 디렉토리 없음: {tap_root}/core")
        return
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "core.fetcher", source],
            cwd=tap_root,
            capture_output=True, text=True, timeout=600,
            env={**os.environ, "TAP_ROOT": tap_root, "BASE_PATH": tap_root},
        )
        if proc.stdout:
            for line in proc.stdout.strip().split("\n")[-5:]:
                logger.info(f"[TAP fetcher] {line}")
        if proc.returncode != 0:
            logger.error(f"[TAP fetcher] 실패 (exit={proc.returncode}): {proc.stderr[-300:]}")
        else:
            logger.info(f"[TAP fetcher] {source} 완료")
    except subprocess.TimeoutExpired:
        logger.exception(f"[TAP fetcher] {source} 600초 타임아웃")
    except Exception as e:
        logger.exception(f"[TAP fetcher] {source} 오류: {e}")


def _send_morning_report() -> None:
    subprocess.run([sys.executable, "-m", "shared.daily_report"],
                   cwd=os.path.dirname(os.path.abspath(__file__)))



def _run_indexnow() -> None:
    try:
        subprocess.run([sys.executable, "scripts/indexnow.py"],
                       cwd=os.path.dirname(os.path.abspath(__file__)), timeout=600)
        logger.info("IndexNow 제출 완료")
    except Exception as e:
        logger.exception(f"IndexNow 실패: {e}")

def _run_schema_sync() -> None:
    try:
        from ops_dashboard.schema_registry import sync_all_schemas
        result = sync_all_schemas()
        logger.info(f"Schema registry sync 완료: {result['inserted']}/{result['total']}")
    except Exception as e:
        logger.exception(f"Schema registry sync 실패: {e}")

# ─── 스케줄 등록 ───

def register_schedules():
    config = load_config()
    blogs = config.get("blogs", [])
    job_count = 0

    for blog in blogs:
        if blog.get("status") != "active":
            continue
        blog_id = blog["id"]
        times = blog.get("schedule", {}).get("times", [])
        for t in times:
            parts = str(t).split(":")
            if len(parts) != 2:
                logger.warning(f"SCHEDULE: 잘못된 스케줄 시각 무시 — {blog_id} time={t!r}")
                continue
            try:
                h, m = map(int, parts)
            except ValueError:
                logger.warning(f"SCHEDULE: 잘못된 스케줄 시각 무시 — {blog_id} time={t!r}")
                continue
            schedule.every().day.at(t).do(queue_publish, blog_id)
            job_count += 1

    batch_time = config.get("batch_deploy", {}).get("schedule", "22:45")
    schedule.every().day.at(batch_time).do(batch_deploy)

#     schedule.every().day.at("05:00").do(_run_gap_keyword_sync)
#     logger.info("GAP keyword sync scheduled at 05:00")
    job_count += 1

    schedule.every().day.at("06:00").do(_run_festival_refresh)
    schedule.every().day.at("05:30").do(_run_senior_sync)

    logger.info("Festival refresh scheduled at 06:00")
    schedule.every().day.at("06:05").do(_run_course_refresh)
    logger.info("Course refresh scheduled at 06:05")
    # ETAP 데이터 컬렉터: 매일 05:00 (발행 전 데이터 수집)
    schedule.every().day.at("05:00").do(_run_etap_collectors)
    logger.info("ETAP data collectors scheduled at 05:00 (viator + aviasales + topic_expander + nomad + omio + airalo)")

    schedule.every().day.at("06:10").do(_run_stap_collector)
    logger.info("STAP data collector scheduled at 06:10")

    # TAP content_pool 갱신 (core.fetcher) — refresh_festival.py / refresh_course.py 직후
    schedule.every().day.at("06:07").do(_run_tap_fetcher, "festival")
    logger.info("TAP festival fetcher scheduled at 06:07 (daily)")
    schedule.every().monday.at("06:15").do(_run_tap_fetcher, "camping")
    logger.info("TAP camping fetcher scheduled Monday at 06:15")

    schedule.every().day.at("06:30").do(_run_car_refresh)

    schedule.every().day.at("06:45").do(_run_indexnow)
    logger.info("IndexNow scheduled at 06:45")

    schedule.every().day.at("09:00").do(_run_schema_sync)
    logger.info("Schema registry sync scheduled at 09:00")

    logger.info("CAR daily_refresh scheduled at 06:30")
    job_count += 1

    # CUAP auto_collector: 매 시간 :50에 실행
    def _run_cuap_collector() -> None:
        try:
            from pipelines.curation.auto_collector import run as cuap_collect
            cuap_collect()
        except Exception as e:
            logger.exception(f"CUAP auto_collector error: {e}")

    schedule.every().hour.at(":50").do(_run_cuap_collector)
    logger.info("CUAP auto_collector scheduled every hour at :50")

    # CUAP keyword_expander: 매일 02:00에 실행 (동적 키워드 확장)
    def _run_keyword_expander() -> None:
        """keyword_expander subprocess 격리 + deadline (CAR daily_refresh 동일 패턴).

        - in-process 호출 시 네트워크/DNS 블록이 스케줄러 루프 전체를 정지시킴
          (2026-08-23 02:00→06:59 침묵사 원인) → subprocess + start_new_session 격리.
        - Popen poll 중 heartbeat 갱신 → watchdog kickstart 루프 방지.
        - deadline 초과 시 process group 전체(killpg) 정리.
        """
        import signal
        import tempfile

        timeout_sec = int(os.environ.get("EXPANDER_TIMEOUT_SEC", "1800"))
        started = time.time()
        deadline = started + timeout_sec
        stdout_tmp = tempfile.TemporaryFile(mode="w+", encoding="utf-8")
        stderr_tmp = tempfile.TemporaryFile(mode="w+", encoding="utf-8")
        timed_out = False
        try:
            proc = subprocess.Popen(
                [sys.executable, "-m", "pipelines.curation.keyword_expander", "all"],
                cwd=os.path.dirname(os.path.abspath(__file__)),
                stdout=stdout_tmp, stderr=stderr_tmp, text=True,
                start_new_session=True,
            )
            while proc.poll() is None:
                try:
                    _update_heartbeat()
                except Exception:
                    pass  # heartbeat 실패가 expander 결과를 왜곡하지 않는다
                if time.time() > deadline:
                    timed_out = True
                    break
                time.sleep(30)

            if timed_out:
                logger.error(f"keyword_expander DEADLINE exceeded ({timeout_sec}s), killing process group")
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                    proc.wait(timeout=10)
                except Exception:
                    try:
                        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                    except Exception:
                        pass
            rc = proc.returncode
            stdout_tmp.seek(0)
            stderr_tmp.seek(0)
            tail = (stderr_tmp.read() or stdout_tmp.read())[-2000:]
            if timed_out or rc != 0:
                logger.warning(f"keyword_expander rc={rc} timed_out={timed_out}\n{tail}")
            else:
                logger.info(f"keyword_expander completed in {time.time()-started:.0f}s")
        except Exception as e:
            logger.exception(f"CUAP keyword_expander error: {e}")
        finally:
            stdout_tmp.close()
            stderr_tmp.close()

    schedule.every().day.at("02:00").do(_run_keyword_expander)
    logger.info("CUAP keyword_expander scheduled daily at 02:00")

    # CUAP per-blog expander (spec 14 blogs, --count 20) — 02:00과 동일 분에 추가 스케줄
    def _run_cuap_expander() -> None:
        try:
            for blog in ['golf-hugo','fitness-hugo','kitchen-hugo','car-hugo','health-hugo',
                         'beauty-hugo','camping-hugo','interior-hugo','pet-hugo',
                         'baby-hugo','appliance-hugo','garden-hugo','hotissue-hugo','deal-hugo']:
                try:
                    subprocess.run([sys.executable, 'pipelines/curation/keyword_expander.py', blog, '--count', '20'], timeout=600)
                    logger.info(f"[CUAP expander] {blog} --count 20 done")
                except Exception as e:
                    logger.warning(f"[CUAP expander] {blog} error: {e}")
        except Exception as e:
            logger.exception(f"CUAP cuap_expander error: {e}")

    schedule.every().day.at("02:00").do(_run_cuap_expander)
    logger.info("CUAP cuap_expander scheduled daily at 02:00 (14 blogs x20)")

    # CUAP keyword_harvester: 매일 03:00 (윈도우 게이트는 run_harvest 내부 이중 확인)
    def _run_cuap_harvest() -> None:
        try:
            from pipelines.curation.run_harvest import main as harvest_main
            harvest_main()
        except Exception as e:
            logger.exception(f"CUAP keyword_harvester error: {e}")

    schedule.every().day.at("03:00").do(_run_cuap_harvest)
    logger.info("CUAP keyword_harvester scheduled daily at 03:00")

    schedule.every().day.at("23:00").do(_run_quality_scan)
    schedule.every().day.at("23:50").do(daily_report)
    # P32: 배포된 글의 빈 내용 사후 검증 — 6시간 간격 (00:00, 06:00, 12:00, 18:00)
    for _h in ("00:00", "06:00", "12:00", "18:00"):
        schedule.every().day.at(_h).do(_run_p32_scan)
    logger.info(f"P32 scan scheduled every 6h (00:00, 06:00, 12:00, 18:00)")
    job_count += 1

    # Phase 71 (SC-1): 전체 재검사 — 매시간 1회 (발행훅 외 2차 안전망)
    schedule.every().hour.do(_run_recheck_all)
    logger.info("RecheckAll scheduled every hour (ops_dashboard run_all_checks)")
    job_count += 1

    # CUAP weekly off-topic 리포트: 매주 월요일 10:00
    DB_NAME = "curation.db"

    def _run_weekly_offtopic_report() -> None:
        try:
            from shared.relevance_scorer import run_all_weekly_reports
            from shared.telegram_notifier import send
            report = run_all_weekly_reports(os.path.join(DATA_DIR, DB_NAME))
            if report:
                send(report)
        except Exception as e:
            logger.exception(f"Weekly off-topic report error: {e}")

    schedule.every().monday.at("10:00").do(_run_weekly_offtopic_report)
    logger.info("CUAP weekly off-topic report scheduled Monday at 10:00")
    job_count += 1

    # ETAP topic_expander: daily 01:00 auto-refill (deals/airlines/airports/nature/watersports)
    def _run_etap_expander() -> None:
        try:
            for blog in ['deals','airlines','airports','nature','watersports']:
                try:
                    subprocess.run([sys.executable, 'pipelines/etap/topic_expander.py', blog, '--count', '50', '--execute'], timeout=300)
                    logger.info(f"[ETAP expander] {blog} --count 50 --execute done")
                except Exception as e:
                    logger.warning(f"[ETAP expander] {blog} error: {e}")
        except Exception as e:
            logger.exception(f"ETAP expander error: {e}")

    schedule.every().day.at("01:00").do(_run_etap_expander)
    logger.info("ETAP topic_expander scheduled daily at 01:00 (5 blogs x 50)")
    job_count += 1

    return job_count


# ─── 메인 ───

def _wait_for_network(timeout=300) -> bool:
    """네트워크 연결 대기 — DNS 해석 가능할 때까지 최대 timeout초"""
    import socket
    start = time.time()
    while time.time() - start < timeout:
        try:
            socket.getaddrinfo("api.openai.com", 443)
            logger.info("Network ready")
            return True
        except socket.gaierror:
            logger.warning("Network not ready, waiting 30s...")
            time.sleep(30)
    logger.error("Network timeout after %ds", timeout)
    return False


# ── Consecutive Failure Detection ──────────────────────────────
_CONSECUTIVE_FAILURES: dict[str, int] = {}
_FAILURE_THRESHOLD = 5  # 2026-08-25: 상향 3→5 (일시적 장애 1~4회로 블로그 중단 방지)
# 파이프라인에서 조용히 스킵하는 reason — 스케줄러 consecutive_failures 집계에서 제외
_SILENT_SKIP_REASONS = frozenset({"interval_skip", "quota_met", "similar_title", "already_running"})


def _track_publish_result(blog_id: str, success: bool, reason: str | None = None) -> None:
    """Track consecutive publish failures per blog_id.
    Resets on success. Sends Telegram alert on threshold breach.

    reason이 _SILENT_SKIP_REASONS에 해당하면 실패로 집계하지 않는다 —
    파이프라인 의도적 스킵이지 콘텐츠 생성 실패가 아니다.
    """
    if success:
        _CONSECUTIVE_FAILURES.pop(blog_id, None)
        # timeout(P25) 후 재시도 성공 시 stale P25 이벤트 close
        try:
            from shared.publish_error_events import close_publish_error_event
            conn = sqlite3.connect(str(Path(__file__).resolve().parent / "ops_dashboard" / "ops.db"))
            try:
                closed = close_publish_error_event(
                    conn, blog_id=blog_id, problem_id="P25")
                if closed:
                    logger.info(f"[scheduler] P25 이벤트 close: {blog_id} ({closed}건)")
            finally:
                conn.close()
        except Exception as _e:
            logger.warning(f"[scheduler] P25 close 실패: {blog_id}: {_e}")
        return

    # 파이프라인 의도적 스킵 — 실패로 집계하지 않는다
    if reason and reason in _SILENT_SKIP_REASONS:
        logger.info(f"[SKIP] {blog_id} reason={reason} — consecutive_failures 미집계")
        return

    count = _CONSECUTIVE_FAILURES.get(blog_id, 0) + 1
    _CONSECUTIVE_FAILURES[blog_id] = count
    logger.warning(f"[FAILURE] {blog_id}: consecutive failures={count}/{_FAILURE_THRESHOLD}")

    if count >= _FAILURE_THRESHOLD:
        try:
            from shared.telegram_notifier import send_error as _tg
            _tg(blog_id, f"연속 {count}회 실패 (scheduler — {count} consecutive failures)")
        except Exception as _e:
            logger.warning(f"Telegram alert failed: {_e}")
        # alert_thresholds 배선 — reason별 임계값/쿨다운 알림
        try:
            from shared.alert_thresholds import ThresholdChecker
            checker = ThresholdChecker()
            checker.maybe_alert(blog_id, "consecutive_failures", {"consecutive_failures": count})
        except Exception as _ae:
            logger.debug(f"alert_thresholds 호출 실패 (non-fatal): {_ae}")
        _CONSECUTIVE_FAILURES[blog_id] = 0  # 알림 발송 후 카운터 리셋


def main() -> None:
    logger.info("=== 5000 Scheduler Starting ===")
    _wait_for_network()
    # stale publish slot 정리 (crash 후 남은 슬롯, TTL 만료 슬롯)
    cleaned = cleanup_stale_slots()
    if cleaned:
        logger.info(f"[CONCURRENCY] startup stale slot 정리: {cleaned}개 제거")
    job_count = register_schedules()
    logger.info(f"Registered {job_count} jobs")
    logger.info(f"Next run: {schedule.next_run()}")

    _check_thumbnail_health()  # 썸네일 헬스체크

    _update_heartbeat()  # 시작 즉시 heartbeat
    last_catchup = 0
    while True:
        _update_heartbeat()
        schedule.run_pending()
        now_ts = time.time()
        if now_ts - last_catchup >= 300:  # 5분마다
            try:
                catchup_missed()
            except Exception as e:
                logger.exception(f"Catchup error: {e}")
            last_catchup = now_ts
        time.sleep(30)


if __name__ == "__main__":
    main()

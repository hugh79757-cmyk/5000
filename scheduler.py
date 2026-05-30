"""5000 Scheduler — launchd에서 호출
blogs.yaml의 스케줄에 따라 dispatcher를 실행하고,
놓친 스케줄을 publish_ledger 기반으로 보충한다.
"""
import os
import sys
import yaml
import time
import logging
import schedule
import subprocess
import threading
import sqlite3
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv("/Users/twinssn/Projects/5000/.env")

# ── 패키지 의존성 체크 ──
REQUIRED_PACKAGES = {
    "boto3": "boto3",
    "bs4": "beautifulsoup4",
    "openai": "openai",
    "dotenv": "python-dotenv",
    "yaml": "pyyaml",
    "requests": "requests",
    "schedule": "schedule",
}

def _check_dependencies():
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

_check_dependencies()

from shared.telegram_notifier import send_error as _tg_error

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# FileHandler: scheduler.log 직접 기록
_log_file = "/Users/twinssn/Projects/5000/logs/scheduler.log"
_fh = logging.FileHandler(_log_file, encoding="utf-8")
_fh.setLevel(logging.INFO)
_fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logging.getLogger().addHandler(_fh)

PROJECT_DIR = "/Users/twinssn/Projects/5000"
CONFIG_DIR = os.path.join(PROJECT_DIR, "config")
PYTHON = os.path.join(PROJECT_DIR, ".venv", "bin", "python3")
LEDGER_DB = os.path.join(PROJECT_DIR, "data", "content.db")


# ─── Heartbeat ───
HB_FILE = os.path.join(PROJECT_DIR, "logs", "heartbeat")

def _update_heartbeat():
    try:
        with open(HB_FILE, "w") as f:
            f.write(str(int(time.time())))
    except Exception:
        pass

MAX_CATCHUP_PER_BLOG = 3
PUBLISH_DELAY = 180  # 블로그 간 딜레이(초)


# ─── Config ───

def load_config():
    """blogs.yaml(공통) + blogs.d/*.yaml(파이프라인별) 통합 로드"""
    main_path = os.path.join(CONFIG_DIR, "blogs.yaml")
    with open(main_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    if "blogs" not in config:
        config["blogs"] = []
    blogs_d = os.path.join(CONFIG_DIR, "blogs.d")
    if os.path.isdir(blogs_d):
        for fname in sorted(os.listdir(blogs_d)):
            if not fname.endswith(".yaml"):
                continue
            fpath = os.path.join(blogs_d, fname)
            with open(fpath, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            config["blogs"].extend(data.get("blogs", []))
    return config


# ─── 발행 실행 ───

def run_publish(blog_id):
    """dispatcher를 subprocess로 실행 (quota 게이트 포함)"""
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

    logger.info("Publishing: " + blog_id)
    import json as _json
    try:
        result = subprocess.run(
            [PYTHON, "dispatcher.py", blog_id],
            cwd=PROJECT_DIR,
            capture_output=True, text=True, timeout=600
        )
        if result.stdout:
            for line in result.stdout.strip().split("\n")[-3:]:
                logger.info("  [OUT] " + line)
            # 마지막 줄이 JSON 결과라고 가정하고 파싱
            last_line = result.stdout.strip().split("\n")[-1].strip()
            try:
                parsed = _json.loads(last_line)
                if parsed.get("success"):
                    logger.info(f"[PUBLISH] {blog_id} 발행 성공")
                else:
                    reason = parsed.get("reason", "unknown")
                    logger.error(f"[PUBLISH] {blog_id} 발행 실패 — stage={reason}")
            except (_json.JSONDecodeError, Exception):
                pass
        if result.returncode != 0 and result.stderr:
            logger.error("  ERR: " + result.stderr[-200:])
            _tg_error(blog_id, "scheduler", result.stderr[-300:])
            return False
        return True
    except subprocess.TimeoutExpired:
        logger.error(blog_id + " timeout (600s)")
        _tg_error(blog_id, "scheduler", "timeout 600s")
        return False
    except Exception as e:
        logger.error(blog_id + " failed: " + str(e))
        _tg_error(blog_id, "scheduler", str(e)[:300])
        return False


# ─── 발행 큐 ───

_publish_queue = []
_queue_lock = threading.Lock()


def queue_publish(blog_id):
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


def _drain_queue():
    """큐에 쌓인 블로그를 순차적으로 실행"""
    while True:
        with _queue_lock:
            if not _publish_queue:
                return
            blog_id = _publish_queue.pop(0)
        logger.info(f"Queue executing: {blog_id} (remaining: {len(_publish_queue)})")
        try:
            run_publish(blog_id)
        except Exception as e:
            logger.error(f"Queue publish failed: {blog_id} - {e}")
        with _queue_lock:
            if not _publish_queue:
                return
        time.sleep(PUBLISH_DELAY)


# ─── Catchup (중앙 ledger 기반) ───

_catchup_attempts = {}
_catchup_date = None
_catchup_lock = threading.Lock()  # catchup 중복 실행 방지


def _get_ledger_count(blog_id, date_str):
    """publish_ledger에서 오늘 발행 건수 조회 — 모든 블로그 동일 방식"""
    try:
        conn = sqlite3.connect(LEDGER_DB)
        row = conn.execute(
            "SELECT COUNT(*) FROM publish_ledger WHERE blog_id=? AND date(created_at)=?",
            (blog_id, date_str)
        ).fetchone()
        conn.close()
        return row[0] if row else 0
    except Exception:
        return 0


def catchup_missed():
    """놓친 스케줄 보충 발행 — 5분마다 체크 (중복 실행 방지)"""
    if not _catchup_lock.acquire(blocking=False):
        logger.debug("Catchup already running, skipping")
        return
    global _catchup_attempts, _catchup_date
    try:
        _catchup_missed_inner()
    finally:
        _catchup_lock.release()


def _catchup_missed_inner():
    """catchup 실제 로직"""
    global _catchup_attempts, _catchup_date

    config = load_config()
    blogs = config.get("blogs", [])
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")

    # 날짜 바뀌면 카운터 초기화
    if _catchup_date != today_str:
        _catchup_attempts = {}
        _catchup_date = today_str

    # 스케줄러 시작 직후 보호: 첫 스케줄 시각 이전이면 catchup 안 함
    first_schedule_hour = 7
    if now.hour < first_schedule_hour:
        return

    for blog in blogs:
        if not isinstance(blog, dict) or blog.get("status") != "active":
            continue
        blog_id = blog["id"]

        # 일일 catchup 상한
        attempts = _catchup_attempts.get(blog_id, 0)
        if attempts >= MAX_CATCHUP_PER_BLOG:
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
            h, m = map(int, str(t).split(":"))
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

        _catchup_attempts[blog_id] = attempts + 1
        logger.info(
            f"CATCHUP: {blog_id} expected={expected} actual={actual} "
            f"missed={missed} quota={daily_quota} attempt={attempts + 1}/{MAX_CATCHUP_PER_BLOG}"
        )
        try:
            success = run_publish(blog_id)
            if not success:
                logger.warning(f"CATCHUP: {blog_id} 보충 실패 ({attempts + 1}/{MAX_CATCHUP_PER_BLOG})")
        except Exception as e:
            logger.error(f"CATCHUP: {blog_id} 예외: {e}")
        time.sleep(5)


# ─── 배치 작업 ───

def batch_deploy():
    logger.info("Batch deploy started")
    try:
        result = subprocess.run(
            ["bash", os.path.join(PROJECT_DIR, "scripts", "batch_push.sh")],
            capture_output=True, text=True, timeout=1800
        )
        if result.stdout:
            for line in result.stdout.strip().split("\n")[-5:]:
                logger.info("  " + line)
    except Exception as e:
        logger.error("Batch deploy failed: " + str(e))


def _run_quality_scan():
    """발행 후 품질 스캔 + 텔레그램 리포트 (매일 23:00)"""
    try:
        from pipelines.etap.quality_scanner import run_scan
        result = run_scan()
        logger.info(f"[QualityScan] 완료: {result}")
    except Exception as e:
        logger.error(f"[QualityScan] 실패: {e}")
        _tg_error("QualityScan 오류", str(e))


def daily_report():
    logger.info("Daily report")
    try:
        result = subprocess.run(
            [PYTHON, "dispatcher.py", "report"],
            cwd=PROJECT_DIR,
            capture_output=True, text=True, timeout=120
        )
        if result.stdout:
            logger.info("  " + result.stdout.strip()[-200:])
    except Exception as e:
        logger.error("Report failed: " + str(e))


def _run_gap_keyword_sync():
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
        logger.error(f"GAP keyword sync failed: {e}")


def _run_car_refresh():
    subprocess.run([sys.executable, "pipelines/car/daily_refresh.py"],
                   cwd=os.path.dirname(os.path.abspath(__file__)))
    logger.info("CAR daily_refresh completed")


def _run_stap_collector():
    try:
        import sys
        if '/Users/twinssn/Projects/STAP' not in sys.path:
            sys.path.insert(0, '/Users/twinssn/Projects/STAP')
        from pipelines.data_collector import collect_all
        result = collect_all()
        logger.info(f"[STAP collector] 완료: {result}")
    except Exception as e:
        logger.error(f"[STAP collector] 오류: {e}")



def _run_senior_sync():
    """senior.db 서비스 데이터 일일 동기화 (pending 보충)"""
    try:
        import sys
        sys.path.insert(0, "/Users/twinssn/Projects/5000")
        from pipelines.senior.fetcher import sync_services, get_pending_count
        pending = get_pending_count()
        logger.info(f"[SeniorSync] 현재 pending: {pending}건")
        synced = sync_services()
        logger.info(f"[SeniorSync] 완료: {synced}건 신규 저장, pending: {get_pending_count()}건")
    except Exception as e:
        logger.error(f"[SeniorSync] 실패: {e}")

def _run_festival_refresh():
    try:
        subprocess.run([sys.executable, "scripts/refresh_festival.py"],
                       cwd=os.path.dirname(os.path.abspath(__file__)), timeout=600)
        logger.info("Festival refresh completed")
    except Exception as e:
        logger.error(f"Festival refresh failed: {e}")


def _send_morning_report():
    subprocess.run([sys.executable, "-m", "shared.daily_report"],
                   cwd=os.path.dirname(os.path.abspath(__file__)))



def _run_indexnow():
    try:
        subprocess.run([sys.executable, "scripts/indexnow.py"],
                       cwd=os.path.dirname(os.path.abspath(__file__)), timeout=600)
        logger.info("IndexNow 제출 완료")
    except Exception as e:
        logger.error(f"IndexNow 실패: {e}")

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
            schedule.every().day.at(t).do(queue_publish, blog_id)
            job_count += 1

    batch_time = config.get("batch_deploy", {}).get("schedule", "22:45")
    schedule.every().day.at(batch_time).do(batch_deploy)

    schedule.every().day.at("05:00").do(_run_gap_keyword_sync)
    logger.info("GAP keyword sync scheduled at 05:00")
    job_count += 1

    schedule.every().day.at("06:00").do(_run_festival_refresh)
    schedule.every().day.at("05:30").do(_run_senior_sync)
    logger.info("Senior DB sync scheduled at 05:30")
    logger.info("Festival refresh scheduled at 06:00")
    schedule.every().day.at("06:10").do(_run_stap_collector)
    logger.info("STAP data collector scheduled at 06:10")

    schedule.every().day.at("06:30").do(_run_car_refresh)

    schedule.every().day.at("06:45").do(_run_indexnow)
    logger.info("IndexNow scheduled at 06:45")

    logger.info("CAR daily_refresh scheduled at 06:30")
    job_count += 1

    # CUAP auto_collector: 매 시간 :50에 실행
    def _run_cuap_collector():
        try:
            from pipelines.curation.auto_collector import run as cuap_collect
            cuap_collect()
        except Exception as e:
            logger.error(f"CUAP auto_collector error: {e}")

    schedule.every().hour.at(":50").do(_run_cuap_collector)
    logger.info("CUAP auto_collector scheduled every hour at :50")

    schedule.every().day.at("23:00").do(_run_quality_scan)
    schedule.every().day.at("23:50").do(daily_report)
    job_count += 1

    return job_count


# ─── 메인 ───

def _wait_for_network(timeout=300):
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


def main():
    logger.info("=== 5000 Scheduler Starting ===")
    _wait_for_network()
    job_count = register_schedules()
    logger.info(f"Registered {job_count} jobs")
    logger.info(f"Next run: {schedule.next_run()}")

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
                logger.error(f"Catchup error: {e}")
            last_catchup = now_ts
        time.sleep(30)


if __name__ == "__main__":
    main()

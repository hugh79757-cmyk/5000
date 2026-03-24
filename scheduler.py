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

from shared.telegram_notifier import send_error as _tg_error

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

PROJECT_DIR = "/Users/twinssn/Projects/5000"
CONFIG_DIR = os.path.join(PROJECT_DIR, "config")
PYTHON = os.path.join(PROJECT_DIR, ".venv", "bin", "python3")
LEDGER_DB = os.path.join(PROJECT_DIR, "data", "content.db")

MAX_CATCHUP_PER_BLOG = 3
PUBLISH_DELAY = 180  # 블로그 간 딜레이(초)


# ─── Config ───

def load_config():
    with open(os.path.join(CONFIG_DIR, "blogs.yaml"), "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ─── 발행 실행 ───

def run_publish(blog_id):
    """dispatcher를 subprocess로 실행"""
    logger.info("Publishing: " + blog_id)
    try:
        result = subprocess.run(
            [PYTHON, "dispatcher.py", blog_id],
            cwd=PROJECT_DIR,
            capture_output=True, text=True, timeout=600
        )
        if result.stdout:
            for line in result.stdout.strip().split("\n")[-3:]:
                logger.info("  " + line)
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
    """동시간대 블로그를 큐에 넣고 순차 실행"""
    with _queue_lock:
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
    """놓친 스케줄 보충 발행 — 5분마다 체크, 블로그당 일일 3회 상한"""
    global _catchup_attempts, _catchup_date

    config = load_config()
    blogs = config.get("blogs", [])
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")

    # 날짜 바뀌면 카운터 초기화
    if _catchup_date != today_str:
        _catchup_attempts = {}
        _catchup_date = today_str

    for blog in blogs:
        if blog.get("status") != "active":
            continue
        blog_id = blog["id"]

        # 일일 상한 체크
        attempts = _catchup_attempts.get(blog_id, 0)
        if attempts >= MAX_CATCHUP_PER_BLOG:
            continue

        # 오늘 발행해야 할 횟수: 현재 시각 이전 스케줄 수
        times = blog.get("schedule", {}).get("times", [])
        expected = 0
        for t in times:
            h, m = map(int, t.split(":"))
            if h < now.hour or (h == now.hour and m <= now.minute):
                expected += 1

        if expected == 0:
            continue

        # 오늘 실제 발행 수 — publish_ledger 한 곳만 조회
        actual = _get_ledger_count(blog_id, today_str)

        missed = expected - actual
        if missed > 0:
            _catchup_attempts[blog_id] = attempts + 1
            logger.info(f"CATCHUP: {blog_id} expected={expected} actual={actual} missed={missed} attempt={attempts + 1}/{MAX_CATCHUP_PER_BLOG}")
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


def _send_morning_report():
    subprocess.run([sys.executable, "-m", "shared.daily_report"],
                   cwd=os.path.dirname(os.path.abspath(__file__)))


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

    schedule.every().day.at("06:30").do(_run_car_refresh)
    logger.info("CAR daily_refresh scheduled at 06:30")
    job_count += 1

    schedule.every().day.at("23:50").do(daily_report)
    job_count += 1

    return job_count


# ─── 메인 ───

def main():
    logger.info("=== 5000 Scheduler Starting ===")
    job_count = register_schedules()
    logger.info(f"Registered {job_count} jobs")
    logger.info(f"Next run: {schedule.next_run()}")

    last_catchup = 0
    while True:
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

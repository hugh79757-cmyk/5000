import os
import sys
import yaml
import time
import logging
import schedule
from shared.telegram_notifier import send_error as _tg_error
import subprocess
from datetime import datetime
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv("/Users/twinssn/Projects/5000/.env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

CONFIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")
PROJECT_DIR = "/Users/twinssn/Projects/5000"
PYTHON = os.path.join(PROJECT_DIR, ".venv", "bin", "python3")


def load_config():
    with open(os.path.join(CONFIG_DIR, "blogs.yaml"), "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_publish(blog_id):
    logger.info("Publishing: " + blog_id)
    try:
        result = subprocess.run(
            [PYTHON, "dispatcher.py", blog_id],
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
            timeout=600
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


import threading
from collections import defaultdict

_publish_queue = []
_queue_lock = threading.Lock()
PUBLISH_DELAY = 180  # 블로그 간 딜레이(초)

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


# 일일 catchup 시도 카운터: {blog_id: count}
_catchup_attempts = {}
_catchup_date = None

MAX_CATCHUP_PER_BLOG = 3  # 블로그당 하루 최대 보충 시도 횟수


def catchup_missed():
    """놓친 스케줄 보충 발행 — 5분마다 체크, 블로그당 일일 3회 상한"""
    global _catchup_attempts, _catchup_date

    config = load_config()
    blogs = config.get("blogs", [])
    now = datetime.now()
    current_hour = now.hour
    today_str = now.strftime("%Y-%m-%d")

    # 날짜 바뀌면 카운터 초기화
    if _catchup_date != today_str:
        _catchup_attempts = {}
        _catchup_date = today_str

    for blog in blogs:
        if blog.get("status") != "active":
            continue
        blog_id = blog["id"]
        pipeline = blog.get("pipeline", "")

        # 일일 상한 체크
        attempts = _catchup_attempts.get(blog_id, 0)
        if attempts >= MAX_CATCHUP_PER_BLOG:
            continue

        # 오늘 발행해야 할 횟수: 현재 시각 이전 스케줄 수
        times = blog.get("schedule", {}).get("times", [])
        expected = 0
        for t in times:
            h, m = map(int, t.split(":"))
            if h < current_hour or (h == current_hour and m <= now.minute):
                expected += 1

        if expected == 0:
            continue

        # 오늘 실제 발행 수
        if pipeline == "car":
            db_path = os.path.join(PROJECT_DIR, "data", "car.db")
            try:
                conn = sqlite3.connect(db_path)
                car_site = blog_id.replace("-hugo", "")
                row = conn.execute(
                    "SELECT COUNT(*) FROM publish_log WHERE site=? AND date(published_at)=date('now')",
                    (car_site,)
                ).fetchone()
                actual = row[0] if row else 0
                conn.close()
            except Exception:
                actual = 0
        else:
            try:
                sys.path.insert(0, PROJECT_DIR)
                from shared.content_store import get_today_count
                actual = get_today_count(blog_id)
            except Exception:
                actual = 0

        missed = expected - actual
        if missed > 0:
            _catchup_attempts[blog_id] = attempts + 1
            logger.info("CATCHUP: " + blog_id + " expected=" + str(expected) + " actual=" + str(actual) + " missed=" + str(missed) + " attempt=" + str(attempts + 1) + "/" + str(MAX_CATCHUP_PER_BLOG))
            try:
                success = run_publish(blog_id)
                if not success:
                    logger.warning("CATCHUP: " + blog_id + " 보충 실패 (" + str(attempts + 1) + "/" + str(MAX_CATCHUP_PER_BLOG) + ")")
            except Exception as e:
                logger.error("CATCHUP: " + blog_id + " 예외: " + str(e))
            time.sleep(5)


def batch_deploy():
    logger.info("Batch deploy started")
    try:
        result = subprocess.run(
            ["bash", os.path.join(PROJECT_DIR, "scripts", "batch_push.sh")],
            capture_output=True,
            text=True,
            timeout=1800
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
            capture_output=True,
            text=True,
            timeout=120
        )
        if result.stdout:
            logger.info("  " + result.stdout.strip()[-200:])
    except Exception as e:
        logger.error("Report failed: " + str(e))


def _run_gap_keyword_sync():
    """news-keyword-pro golden CSV → gap.db 동기화"""
    try:
        import subprocess
        result = subprocess.run(
            ["python3", "/Users/twinssn/Projects/5000/scripts/sync_golden_to_gap.py"],
            capture_output=True, text=True, timeout=120,
            cwd="/Users/twinssn/Projects/5000"
        )
        logger.info(f"GAP keyword sync: {result.stdout.strip().split(chr(10))[-1]}")
        if result.returncode != 0:
            logger.warning(f"GAP keyword sync stderr: {result.stderr[:200]}")
    except Exception as e:
        logger.error(f"GAP keyword sync failed: {e}")


def _run_car_refresh():
    import subprocess
    subprocess.run([sys.executable, "pipelines/car/daily_refresh.py"], cwd=os.path.dirname(os.path.abspath(__file__)))
    logger.info("CAR daily_refresh completed")


def _send_morning_report():
    import subprocess
    subprocess.run([sys.executable, "-m", "shared.daily_report"], cwd=os.path.dirname(os.path.abspath(__file__)))


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


def main():
    logger.info("=== 5000 Scheduler Starting ===")
    job_count = register_schedules()
    logger.info("Registered " + str(job_count) + " jobs")
    logger.info("Next run: " + str(schedule.next_run()))

    last_catchup = 0
    while True:
        schedule.run_pending()
        now_ts = time.time()
        if now_ts - last_catchup >= 300:  # 5분마다
            try:
                catchup_missed()
            except Exception as e:
                logger.error("Catchup error: " + str(e))
            last_catchup = now_ts
        time.sleep(30)


if __name__ == "__main__":
    main()

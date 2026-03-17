import os
import sys
import yaml
import time
import logging
import schedule
import subprocess
from datetime import datetime

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
    except subprocess.TimeoutExpired:
        logger.error(blog_id + " timeout (600s)")
    except Exception as e:
        logger.error(blog_id + " failed: " + str(e))


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
            schedule.every().day.at(t).do(run_publish, blog_id)
            job_count += 1

    batch_time = config.get("batch_deploy", {}).get("schedule", "22:45")
    schedule.every().day.at(batch_time).do(batch_deploy)
    job_count += 1

    schedule.every().day.at("23:50").do(daily_report)
    job_count += 1

    return job_count


def main():
    logger.info("=== 5000 Scheduler Starting ===")
    job_count = register_schedules()
    logger.info("Registered " + str(job_count) + " jobs")
    logger.info("Next run: " + str(schedule.next_run()))

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()

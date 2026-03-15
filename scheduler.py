import schedule
import time
import subprocess
import logging
import os
import sys
from datetime import datetime

sys.path.insert(0, "/Users/twinssn/Projects/5000")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

PROJECT_DIR = "/Users/twinssn/Projects/5000"
PYTHON = "/Users/twinssn/Projects/5000/.venv/bin/python3"


def run_publish(blog_id):
    logger.info(f"=== {blog_id} 발행 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
    try:
        result = subprocess.run(
            [PYTHON, "dispatcher.py", blog_id],
            capture_output=True, text=True,
            cwd=PROJECT_DIR,
            timeout=300
        )
        if result.stdout:
            logger.info(result.stdout[-500:])
        if result.returncode != 0 and result.stderr:
            logger.error(result.stderr[-300:])
    except subprocess.TimeoutExpired:
        logger.error(f"{blog_id} 타임아웃 (300s)")
    except Exception as e:
        logger.error(f"{blog_id} 발행 실패: {e}")


def git_push(site_name):
    site_dir = f"/Users/twinssn/Projects/{site_name}"
    if not os.path.isdir(site_dir):
        logger.warning(f"{site_dir} 없음, push 스킵")
        return
    logger.info(f"=== {site_name} git push ===")
    try:
        subprocess.run(["git", "add", "-A"], cwd=site_dir, capture_output=True, timeout=30)
        result = subprocess.run(
            ["git", "commit", "-m", f"auto: {datetime.now().strftime('%Y-%m-%d %H:%M')}"],
            cwd=site_dir, capture_output=True, text=True, timeout=30
        )
        if "nothing to commit" not in result.stdout:
            subprocess.run(["git", "push", "origin", "main"], cwd=site_dir, capture_output=True, timeout=60)
            logger.info(f"{site_name} pushed")
        else:
            logger.info(f"{site_name} no changes")
    except Exception as e:
        logger.error(f"{site_name} push 실패: {e}")


def git_push_all():
    for site in ["travel-hugo", "travel1-hugo", "travel2-hugo", "travel3-hugo", "travel4-hugo", "hotissue-hugo"]:
        git_push(site)


def daily_report():
    logger.info("=== 일일 리포트 생성 ===")
    try:
        from shared.content_store import init_db
        from shared.monitor import send_daily_report
        init_db()
        send_daily_report()
    except Exception as e:
        logger.error(f"리포트 실패: {e}")


# travel-hugo: 07:00 10:00 13:00 17:00 21:00
schedule.every().day.at("07:00").do(run_publish, "travel-hugo")
schedule.every().day.at("10:00").do(run_publish, "travel-hugo")
schedule.every().day.at("13:00").do(run_publish, "travel-hugo")
schedule.every().day.at("17:00").do(run_publish, "travel-hugo")
schedule.every().day.at("21:00").do(run_publish, "travel-hugo")

# travel1-hugo: 07:30 10:30 14:00 18:00 21:30
schedule.every().day.at("07:30").do(run_publish, "travel1-hugo")
schedule.every().day.at("10:30").do(run_publish, "travel1-hugo")
schedule.every().day.at("14:00").do(run_publish, "travel1-hugo")
schedule.every().day.at("18:00").do(run_publish, "travel1-hugo")
schedule.every().day.at("21:30").do(run_publish, "travel1-hugo")

# travel2-hugo: 08:00 11:00 14:30 18:30 22:00
schedule.every().day.at("08:00").do(run_publish, "travel2-hugo")
schedule.every().day.at("11:00").do(run_publish, "travel2-hugo")
schedule.every().day.at("14:30").do(run_publish, "travel2-hugo")
schedule.every().day.at("18:30").do(run_publish, "travel2-hugo")
schedule.every().day.at("22:00").do(run_publish, "travel2-hugo")

# travel3-hugo: 08:30 11:30 15:00 19:00 22:15
schedule.every().day.at("08:30").do(run_publish, "travel3-hugo")
schedule.every().day.at("11:30").do(run_publish, "travel3-hugo")
schedule.every().day.at("15:00").do(run_publish, "travel3-hugo")
schedule.every().day.at("19:00").do(run_publish, "travel3-hugo")
schedule.every().day.at("22:15").do(run_publish, "travel3-hugo")

# travel4-hugo: 09:00 12:00 15:30 19:30 22:30
schedule.every().day.at("09:00").do(run_publish, "travel4-hugo")
schedule.every().day.at("12:00").do(run_publish, "travel4-hugo")
schedule.every().day.at("15:30").do(run_publish, "travel4-hugo")
schedule.every().day.at("19:30").do(run_publish, "travel4-hugo")
schedule.every().day.at("22:30").do(run_publish, "travel4-hugo")

# git push: 발행 웨이브 종료 후 일괄 push (5회/일)
schedule.every().day.at("09:10").do(git_push_all)
schedule.every().day.at("12:40").do(git_push_all)
schedule.every().day.at("16:00").do(git_push_all)
schedule.every().day.at("20:00").do(git_push_all)
schedule.every().day.at("22:45").do(git_push_all)


schedule.every().day.at("07:00").do(run_publish, "hotissue-hugo")
schedule.every().day.at("10:00").do(run_publish, "hotissue-hugo")
schedule.every().day.at("13:00").do(run_publish, "hotissue-hugo")
schedule.every().day.at("17:00").do(run_publish, "hotissue-hugo")
schedule.every().day.at("21:00").do(run_publish, "hotissue-hugo")

schedule.every().day.at("23:50").do(daily_report)


logger.info("5000 scheduler started")
logger.info(f"registered {len(schedule.get_jobs())} jobs")
for job in schedule.get_jobs():
    logger.info(f"  {job}")

while True:
    schedule.run_pending()
    time.sleep(30)

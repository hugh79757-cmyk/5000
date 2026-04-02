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

# ── 중복 실행 방지 (PID lock) ──
import atexit
import signal

_PIDFILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".scheduler.pid")

def _acquire_pidlock():
    if os.path.exists(_PIDFILE):
        try:
            old_pid = int(open(_PIDFILE).read().strip())
            os.kill(old_pid, 0)  # 프로세스 존재 확인
            print(f"[FATAL] scheduler already running (PID {old_pid}). Exiting.")
            sys.exit(1)
        except (ProcessLookupError, ValueError):
            pass  # 이전 프로세스 이미 죽음 — lock file 무효
        except PermissionError:
            print(f"[FATAL] scheduler already running (PID {old_pid}, permission denied). Exiting.")
            sys.exit(1)
    with open(_PIDFILE, 'w') as f:
        f.write(str(os.getpid()))

def _release_pidlock():
    try:
        if os.path.exists(_PIDFILE) and int(open(_PIDFILE).read().strip()) == os.getpid():
            os.remove(_PIDFILE)
    except Exception:
        pass

def _signal_handler(signum, frame):
    _release_pidlock()
    sys.exit(0)

_acquire_pidlock()
atexit.register(_release_pidlock)
signal.signal(signal.SIGTERM, _signal_handler)
signal.signal(signal.SIGINT, _signal_handler)


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
    """동시간대 블로그를 큐에 넣고 순차 실행 (중복 방지)"""
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
    """놓친 스케줄 보충 발행 — 5분마다 체크"""
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



# ─── Blogdex-Lite Analytics ───

def _run_analytics_sync():
    """매일 05:30 — GSC/GA4 데이터 수집 + 효율 스코어 산출"""
    logger.info("[analytics] 수집 시작")
    try:
        from analytics.gsc_collector import collect_all as gsc_collect, collect_keywords
        from analytics.ga4_collector import collect_all as ga4_collect
        from analytics.efficiency_scorer import update_scores

        gsc_collect(days_back=7, verbose=False)
        collect_keywords(days_back=7, verbose=False)
        ga4_collect(days_back=7, verbose=False)
        update_scores(verbose=False)
        logger.info("[analytics] 수집 + 스코어 완료")
    except Exception as e:
        logger.error(f"[analytics] 수집 실패: {e}")
        _tg_error("analytics", "scheduler", str(e)[:300])


def _run_analytics_report():
    """매일 23:40 — 성과 리포트 텔레그램 전송"""
    logger.info("[analytics] 리포트 전송")
    try:
        from analytics.analytics_report import send_report
        send_report(test=False)
        logger.info("[analytics] 리포트 전송 완료")
    except Exception as e:
        logger.error(f"[analytics] 리포트 실패: {e}")


def _run_daily_indexing():
    """매일 23:00 — 오늘 발행된 URL 색인 제출 (Google + IndexNow)"""
    logger.info("[indexing] 색인 제출 시작")
    try:
        from analytics.indexing import daily_index_submit
        result = daily_index_submit(verbose=False)
        logger.info(f"[indexing] 완료: {result['total_urls']}개 URL")
    except Exception as e:
        logger.error(f"[indexing] 실패: {e}")


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


# ─── 스케줄 등록 ───




def _run_viator_collection():
    try:
        from pipelines.etap.collectors.viator import run_full_collection
        count = run_full_collection()
        logger.info(f'[ETAP] Viator 수집 완료: {count}건')
    except Exception as e:
        logger.error(f'[ETAP] Viator 수집 실패: {e}')
        try:
            _tg_error(f'[ETAP] Viator collection failed: {e}')
        except:
            pass

def _run_airalo_collection():
    try:
        from pipelines.etap.collectors.airalo import run_full_collection
        count = run_full_collection()
        logger.info(f'[ETAP] Airalo 수집 완료: {count}건')
    except Exception as e:
        logger.error(f'[ETAP] Airalo 수집 실패: {e}')
        try:
            _tg_error(f'[ETAP] Airalo collection failed: {e}')
        except:
            pass

def _run_omio_collection():
    try:
        from pipelines.etap.collectors.omio import run_full_collection
        count = run_full_collection()
        logger.info(f'[ETAP] Omio 수집 완료: {count}건')
    except Exception as e:
        logger.error(f'[ETAP] Omio 수집 실패: {e}')
        try:
            _tg_error(f'[ETAP] Omio collection failed: {e}')
        except:
            pass


def _run_flight_publish():
    from pipelines.etap.safeguard import safe_run
    cfg = {
        "id": "flights-hugo",
        "domain": "flights.techpawz.com",
        "site_path": "/Users/twinssn/Projects/ETAP/flights-hugo",
        "cf_project": "flights-hugo"
    }
    def _do():
        from pipelines.etap.flight_pipeline import run
        return run(cfg)
    result = safe_run(
        blog_id="flights-hugo",
        topic_table="flight_topics",
        data_table="flight_prices",
        run_fn=_do,
        tg_func=_tg_error,
        min_data=10
    )
    logger.info(f'[ETAP] Flight: {result}')

def _run_aviasales_collection():
    """항공권 가격 데이터 일일 수집"""
    try:
        from pipelines.etap.collectors.aviasales import run_full_collection
        count = run_full_collection()
        logger.info(f'[ETAP] Aviasales 수집 완료: {count}건')
    except Exception as e:
        logger.error(f'[ETAP] Aviasales 수집 실패: {e}')
        try:
            _tg_error(f'[ETAP] Aviasales collection failed: {e}')
        except:
            pass

def _run_etap_batch():
    """ETAP 배치 — 3건 생성 + 1회 빌드/배포."""
    try:
        from pipelines.etap.pipeline import run_batch
        cfg = {
            "id": "tour-hugo",
            "domain": "tour.techpawz.com",
            "site_path": "/Users/twinssn/Projects/ETAP/tour-hugo",
            "cf_project": "tour-hugo",
        }
        results = run_batch(cfg, count=3)
        logger.info(f"[ETAP] 배치 완료: {len(results)}건")
    except Exception as e:
        logger.error(f"[ETAP] 배치 실패: {e}")
        try:
            _tg_error(f"[ETAP] 배치 실패: {e}")
        except Exception:
            pass

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
    logger.info("Festival refresh scheduled at 06:00")

    schedule.every().day.at("06:30").do(_run_car_refresh)
    logger.info("CAR daily_refresh scheduled at 06:30")
    job_count += 1

    schedule.every().day.at("05:30").do(_run_analytics_sync)
    schedule.every().day.at("23:00").do(_run_daily_indexing)
    schedule.every().day.at("23:40").do(_run_analytics_report)
    schedule.every().day.at("23:50").do(daily_report)
    job_count += 1

    # ── ETAP 배치 (하루 15건 = 5회 × 3건) ──
    schedule.every().day.at("06:00").do(_run_aviasales_collection)
    logger.info("ETAP Aviasales collection scheduled at 06:00")
    schedule.every().day.at("08:00").do(_run_flight_publish)
    schedule.every().day.at("11:00").do(_run_flight_publish)
    schedule.every().day.at("14:00").do(_run_flight_publish)
    schedule.every().day.at("17:00").do(_run_flight_publish)
    schedule.every().day.at("21:00").do(_run_flight_publish)
    logger.info("ETAP Flight publish scheduled 5x daily (08,11,14,17,21)")
    schedule.every().day.at("06:30").do(_run_viator_collection)
    logger.info("ETAP Viator collection scheduled at 06:30")
    schedule.every().day.at("06:30").do(_run_airalo_collection)
    logger.info("ETAP Airalo collection scheduled at 06:30")
    schedule.every().day.at("06:30").do(_run_omio_collection)
    logger.info("ETAP Omio collection scheduled at 06:30")
    etap_times = ["07:30", "10:30", "13:30", "16:30", "20:30"]
    for t in etap_times:
        schedule.every().day.at(t).do(_run_etap_batch)
        job_count += 1
    logger.info(f"ETAP batch scheduled: {etap_times}")

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
            # heartbeat 기록
            try:
                with open("/Users/twinssn/Projects/5000/logs/heartbeat", "w") as _hb:
                    _hb.write(str(int(now_ts)))
            except Exception:
                pass
        time.sleep(30)


if __name__ == "__main__":
    main()

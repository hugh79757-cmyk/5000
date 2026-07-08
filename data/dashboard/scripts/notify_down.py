"""
사이트 다운 알림 — 텔레그램 전송

대시보드 API를 주기적으로 호출하여 오프라인 사이트 발견 시 텔레그램 알림.

사용법:
    python notify_down.py                          # 모든 사이트 체크
    python notify_down.py --threshold 3            # 3회 연속 실패 시만 알림
    python notify_down.py --cooldown 60            # 60분 내 중복 알림 억제

cron: 매 10분 실행
"""

import argparse
import json
import logging
import os
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

_DASHBOARD_ROOT = Path(__file__).resolve().parent.parent
_DATA_DIR = _DASHBOARD_ROOT / "data"
_STATE_DB = _DATA_DIR / "notify_state.db"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# 텔레그램 (shared/env_loader를 통해 ~/.env.common에서 로드)
sys.path.insert(0, str(_DASHBOARD_ROOT.parent.parent))
from shared.env_loader import load_env
load_env()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
DASHBOARD_URL = os.getenv("DASHBOARD_URL", "http://127.0.0.1:5050")


def _init_state():
    """알림 상태 DB 초기화 (사이트별 연속 실패 횟수 + 마지막 알림 시간)"""
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_STATE_DB))
    conn.execute(
        """CREATE TABLE IF NOT EXISTS notify_state (
            blog_id TEXT PRIMARY KEY,
            consecutive_failures INTEGER DEFAULT 0,
            last_notified_at TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )"""
    )
    conn.commit()
    return conn


def send_telegram(message: str):
    """텔레그램 메시지 전송"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("텔레그램 설정 없음, 알림 스킵")
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        resp = requests.post(
            url,
            json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"},
            timeout=10,
        )
        if resp.status_code == 200:
            logger.info("텔레그램 알림 전송 성공")
            return True
        else:
            logger.warning(f"텔레그램 전송 실패: {resp.status_code}")
            return False
    except Exception as e:
        logger.error(f"텔레그램 전송 오류: {e}")
        return False


def check_sites(threshold: int = 1, cooldown_minutes: int = 60):
    """
    대시보드 /api/health 호출 → 오프라인 사이트 감지 → 텔레그램 알림.
    threshold회 연속 실패 시에만 알림 전송.
    cooldown_minutes 내 동일 사이트 중복 알림 억제.
    """
    conn = _init_state()
    now = datetime.now()

    # health API 호출
    try:
        resp = requests.get(f"{DASHBOARD_URL}/api/health", timeout=30)
        if resp.status_code != 200:
            logger.error(f"대시보드 API 오류: {resp.status_code}")
            return {"status": "error", "message": f"API responded {resp.status_code}"}
        sites = resp.json()
    except requests.exceptions.ConnectionError:
        msg = f"⚠️ 대시보드 연결 실패: {DASHBOARD_URL}"
        logger.error(msg)
        send_telegram(msg)
        return {"status": "error", "message": msg}
    except Exception as e:
        logger.error(f"헬스 체크 실패: {e}")
        return {"status": "error", "message": str(e)}

    total = len(sites) if isinstance(sites, list) else 0
    offline = [s for s in (sites if isinstance(sites, list) else []) if s.get("status", 0) != 200]
    online = total - len(offline)

    logger.info(f"헬스 체크: {online}/{total} 온라인, {len(offline)} 오프라인")

    # 상태 업데이트 + 알림 전송
    alerts_sent = 0
    for site in offline:
        blog_id = site.get("blog_id", "unknown")
        status = site.get("status", 0)
        url = site.get("url", "")
        error = site.get("error", "")

        # 연속 실패 카운트
        row = conn.execute(
            "SELECT consecutive_failures, last_notified_at FROM notify_state WHERE blog_id=?",
            (blog_id,),
        ).fetchone()

        if row:
            failures = row[0] + 1
            last_notified = row[1]
        else:
            failures = 1
            last_notified = None

        conn.execute(
            "INSERT OR REPLACE INTO notify_state (blog_id, consecutive_failures, last_notified_at) VALUES (?,?,?)",
            (blog_id, failures, last_notified),
        )

        # 알림 조건: threshold 이상 연속 실패 AND cooldown 경과
        should_notify = failures >= threshold
        if last_notified:
            last_dt = datetime.fromisoformat(last_notified)
            elapsed = (now - last_dt).total_seconds() / 60
            if elapsed < cooldown_minutes:
                should_notify = False

        if should_notify:
            msg = (
                f"🔴 <b>사이트 다운</b>\n"
                f"블로그: {blog_id}\n"
                f"URL: {url}\n"
                f"상태: {status}\n"
                f"오류: {error or 'N/A'}\n"
                f"연속 실패: {failures}회\n"
                f"시간: {now.strftime('%Y-%m-%d %H:%M')}"
            )
            if send_telegram(msg):
                alerts_sent += 1
                conn.execute(
                    "UPDATE notify_state SET last_notified_at=? WHERE blog_id=?",
                    (now.isoformat(), blog_id),
                )

    # 온라인 회복된 사이트는 카운트 리셋
    online_ids = [s.get("blog_id") for s in (sites if isinstance(sites, list) else []) if s.get("status") == 200]
    for blog_id in online_ids:
        conn.execute(
            "UPDATE notify_state SET consecutive_failures=0 WHERE blog_id=? AND consecutive_failures>0",
            (blog_id,),
        )

    conn.commit()
    conn.close()

    summary = {
        "status": "ok",
        "total": total,
        "online": online,
        "offline": len(offline),
        "alerts_sent": alerts_sent,
    }
    logger.info(f"알림 체크 완료: {summary}")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="사이트 다운 알림")
    parser.add_argument("--threshold", type=int, default=1, help="연속 실패 알림 기준 (기본: 1)")
    parser.add_argument("--cooldown", type=int, default=60, help="중복 알림 억제 분 (기본: 60)")
    args = parser.parse_args()

    result = check_sites(threshold=args.threshold, cooldown_minutes=args.cooldown)
    print(json.dumps(result, ensure_ascii=False, indent=2))

#!/usr/bin/env python3
"""heartbeat reader watchdog: logs/heartbeat 가 5분 이상 stale 이면 스케줄러 강제 재기동.

KeepAlive 는 프로세스 사망만 잡는다. 루프 블록/좀비 상태에서는 프로세스가 살아 있어
heartbeat 만 멈추므로 KeepAlive 가 못 잡는다. 이 워치독이 그 틈을 메운다.
"""
import os
import subprocess
import time

HB_FILE = "/Users/twinssn/Projects/5000/logs/heartbeat"
LOG = "/tmp/5000-watchdog.log"
LABEL = f"gui/{os.getuid()}/com.5000.scheduler"
STALE_SEC = 300
POLL_SEC = 60


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n"
    try:
        with open(LOG, "a") as f:
            f.write(line)
    except Exception:
        pass


def age() -> float:
    try:
        return time.time() - os.stat(HB_FILE).st_mtime
    except FileNotFoundError:
        return float("inf")


def kickstart() -> None:
    r = subprocess.run(
        ["launchctl", "kickstart", "-k", LABEL],
        capture_output=True, text=True,
    )
    log(f"kickstart {LABEL} rc={r.returncode} out={r.stdout.strip()} err={r.stderr.strip()}")


def main() -> None:
    log("watchdog started")
    while True:
        a = age()
        if a > STALE_SEC:
            log(f"heartbeat stale age={a:.0f}s > {STALE_SEC}s -> kickstart")
            kickstart()
            time.sleep(120)  # 재기동 후 heartbeat 갱신 대기 (연속 kickstart 방지)
        time.sleep(POLL_SEC)


if __name__ == "__main__":
    main()

"""
log_config.py — Structured logging configuration and stage decorator

Usage:
    from shared.log_config import log_stage, logger

    @log_stage("fetch_food")
    def fetch_food(...):
        ...
"""

import functools
import logging
import time

_FORMAT = "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d — %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

logging.basicConfig(
    level=logging.INFO,
    format=_FORMAT,
    datefmt=_DATE_FORMAT,
    force=True,
)

logger = logging.getLogger(__name__)


def log_stage(stage_name: str):
    """Decorator: logs pipeline stage START/END with duration.

    Example log output:
        2026-07-01 12:34:56 [INFO] fetcher:42 — STAGE:fetch_food START
        2026-07-01 12:34:58 [INFO] fetcher:42 — STAGE:fetch_food END (2.34s)
    On exception:
        2026-07-01 12:34:58 [ERROR] fetcher:42 — STAGE:fetch_food FAIL (2.34s): error message
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            _logger = logging.getLogger(func.__module__)
            _logger.info(f"STAGE:{stage_name} START")
            start = time.time()
            try:
                result = func(*args, **kwargs)
                elapsed = time.time() - start
                _logger.info(f"STAGE:{stage_name} END ({elapsed:.2f}s)")
                return result
            except Exception as e:
                elapsed = time.time() - start
                _logger.error(f"STAGE:{stage_name} FAIL ({elapsed:.2f}s): {e}")
                raise
        return wrapper
    return decorator

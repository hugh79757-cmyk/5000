"""Coupang keyword harvester — rate-limit safe auto-replenishment of KEYWORD_MAP sources.

Hard caps (spec m0455):
    HOURLY_SEARCH_LIMIT = 8   (Coupang search API: 10/hour official)
    MINUTE_TOTAL_LIMIT  = 80  (all APIs combined: 100/min official)
    403 anywhere -> SafetyGuard HARD_STOP: all calls stop, 12h cooldown,
    stdout "[CRITICAL] COUPANG_RATE_EXCEEDED".

Fetch function is injected (fetch_fn) so tests mock everything; production
wires it to collector._search_api-style calls. No existing files modified.
"""

import logging
import time
from pipelines.curation.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

HOURLY_SEARCH_LIMIT = 8
MINUTE_TOTAL_LIMIT = 80
COOLDOWN_HOURS = 12

HARVEST_SOURCES = ["bestcategories", "goldbox"]


class SafetyGuard:
    """Single-403 tripwire. Once tripped, blocks ALL harvesting for cooldown."""

    def __init__(self, cooldown_hours: int = COOLDOWN_HOURS):
        self.cooldown_seconds = cooldown_hours * 3600
        self._tripped_until = 0.0

    @property
    def is_stopped(self) -> bool:
        return time.time() < self._tripped_until

    def on_response(self, status_code: int, body_rcode: str = "") -> None:
        """Inspect an API response; HARD_STOP on any 403 (HTTP or rCode)."""
        if status_code == 403 or str(body_rcode) == "403":
            print("[CRITICAL] COUPANG_RATE_EXCEEDED")
            logger.critical(
                f"[CRITICAL] COUPANG_RATE_EXCEEDED — harvesting stopped "
                f"for {COOLDOWN_HOURS}h"
            )
            self._tripped_until = time.time() + self.cooldown_seconds


class KeywordHarvester:
    """Cycles HARVEST_SOURCES via injected fetch_fn, dedupes against known keywords."""

    def __init__(self, fetch_fn=None, existing_keywords=None, db_path=None):
        # fetch_fn(source_name) -> {"status_code": int, "rCode": str, "keywords": [...]}
        # Injected to keep tests mock-only and avoid real Coupang calls here.
        if fetch_fn is None:
            from pipelines.curation.collector import _search_api as _default
            fetch_fn = lambda source: {"status_code": 200, "rCode": "0",
                                       "keywords": [r["keyword"] for r in _default(source)]}
        self._fetch_fn = fetch_fn
        # db_path 설정 시 모든 fetch를 curation.db api_call_log에 기록해
        # auto_collector(매시 :50)와 동일 카운터 공유 (분40/시300 합산 한도).
        self._db_path = str(db_path) if db_path else None
        self.existing_keywords = set(existing_keywords or ())
        self._hourly = RateLimiter(limit=HOURLY_SEARCH_LIMIT, window_seconds=3600)
        self._minute = RateLimiter(limit=MINUTE_TOTAL_LIMIT, window_seconds=60)
        self.guard = SafetyGuard()
        self._source_idx = 0

    def _log_call(self) -> None:
        """collector._log_api_call과 동일 패턴 — api_call_log INSERT + 2h prune."""
        if not self._db_path:
            return
        try:
            import sqlite3
            conn = sqlite3.connect(self._db_path)
            conn.execute("CREATE TABLE IF NOT EXISTS api_call_log (id INTEGER PRIMARY KEY AUTOINCREMENT, called_at TEXT DEFAULT (datetime('now')))")
            conn.execute("INSERT INTO api_call_log (called_at) VALUES (datetime('now'))")
            conn.execute("DELETE FROM api_call_log WHERE called_at < datetime('now', '-2 hours')")
            conn.commit()
            conn.close()
        except Exception:
            pass

    def _call_api(self, source: str) -> dict:
        resp = self._fetch_fn(source)
        self._log_call()  # 단일 기록 지점 — fetch_fn 래퍼와 이중 카운트 방지
        return resp

    def harvest(self, max_new: int = 20) -> list[str]:
        """Harvest up to max_new new keywords. Returns [] when stopped/limited."""
        if self.guard.is_stopped:
            logger.warning("SafetyGuard HARD_STOP active — skip harvest")
            return []

        collected: list[str] = []
        while len(collected) < max_new:
            if not self._hourly.allowed() or not self._minute.allowed():
                logger.info("rate cap reached — stopping this cycle")
                break
            source = HARVEST_SOURCES[self._source_idx % len(HARVEST_SOURCES)]
            self._source_idx += 1

            resp = self._call_api(source)
            self._hourly.record()
            self._minute.record()
            self.guard.on_response(resp.get("status_code", 0), resp.get("rcode", ""))
            if self.guard.is_stopped:
                return collected

            for kw in resp.get("keywords", []) or []:
                kw = (kw or "").strip()
                if not kw or kw in self.existing_keywords or kw in collected:
                    continue  # dedup filter
                collected.append(kw)
                if len(collected) >= max_new:
                    break
        return collected

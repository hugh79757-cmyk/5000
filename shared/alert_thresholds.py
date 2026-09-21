"""Threshold-based alert system for consecutive failure detection.

Checks failure thresholds (consecutive failures, keyword streaks, daily rate)
and sends Telegram alerts via shared.telegram_notifier with cooldown management.
"""

import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_ALERT_CONFIG = {
    "consecutive_failures": 3,     # Alert after N consecutive failures for same blog
    "daily_failure_rate": 0.5,     # Alert if >50% of daily publications fail
    "keyword_fail_streak": 5,      # Alert if same keyword fails 5+ times consecutively
    "cooldown_minutes": 60,        # Don't re-alert for same blog within N minutes
    "enabled": True,               # Master enable/disable
    "dry_run": False,              # Log only, don't send Telegram
}

# Per-blog overrides for blog-specific thresholds
# Smaller blogs or less critical blogs get different sensitivity
BLOG_OVERRIDES: dict[str, dict] = {
    "pet-hugo": {"consecutive_failures": 2},       # 소규모 블로그 더 민감
    "fitness-hugo": {"consecutive_failures": 5},
    "health-hugo": {"consecutive_failures": 5},
}


class ThresholdChecker:
    """Checks failure thresholds and manages alert cooldowns.

    Uses in-memory cooldown tracking (no DB persistence needed for single-run
    cooldown management). Thresholds are configurable per-blog via BLOG_OVERRIDES.

    Usage:
        checker = ThresholdChecker()
        if checker.check_consecutive_failures('pet-hugo', 3):
            checker.maybe_alert('pet-hugo', 'irrelevant_products')
    """

    def __init__(self, blog_config: Optional[dict] = None):
        """Initialize with optional per-blog overrides.

        Args:
            blog_config: Optional dict mapping blog_id -> config overrides.
                         These take precedence over BLOG_OVERRIDES and defaults.
        """
        self._blog_config = blog_config or {}
        self._last_alerted: dict[str, float] = {}

    def get_config(self, blog_id: str) -> dict:
        """Get merged configuration for a blog.

        Precedence (highest to lowest):
        1. Instance-level blog_config passed via __init__
        2. Static BLOG_OVERRIDES dict
        3. DEFAULT_ALERT_CONFIG defaults
        """
        config = dict(DEFAULT_ALERT_CONFIG)
        if blog_id in BLOG_OVERRIDES:
            config.update(BLOG_OVERRIDES[blog_id])
        if blog_id in self._blog_config:
            config.update(self._blog_config[blog_id])
        return config

    def check_consecutive_failures(self, blog_id: str, consecutive_count: int) -> bool:
        """Returns True if consecutive_count >= the configured threshold."""
        config = self.get_config(blog_id)
        threshold = config.get("consecutive_failures", 3)
        return consecutive_count >= threshold

    def check_keyword_streak(self, blog_id: str, keyword: str, streak_count: int) -> bool:
        """Returns True if streak_count >= the keyword_fail_streak threshold."""
        config = self.get_config(blog_id)
        threshold = config.get("keyword_fail_streak", 5)
        return streak_count >= threshold

    def _in_cooldown(self, blog_id: str, problem_id: str = "", cooldown_minutes: int = 0) -> bool:
        """Returns True if (blog_id, problem_id) is still within its cooldown period.

        R-5: per-problem cooldown. Key is (blog_id, problem_id).
        cooldown_minutes overrides blog-level config when > 0.
        """
        key = (blog_id, problem_id) if problem_id else (blog_id, "")
        if key not in self._last_alerted:
            return False
        if cooldown_minutes > 0:
            cooldown_seconds = cooldown_minutes * 60
        else:
            config = self.get_config(blog_id)
            cooldown_seconds = config.get("cooldown_minutes", 60) * 60
        elapsed = time.time() - self._last_alerted[key]
        return elapsed < cooldown_seconds

    def _mark_alerted(self, blog_id: str, problem_id: str = "") -> None:
        """Records current timestamp for cooldown tracking. R-5: per-problem key."""
        key = (blog_id, problem_id) if problem_id else (blog_id, "")
        self._last_alerted[key] = time.time()

    def maybe_alert(
        self,
        blog_id: str,
        reason: str,
        context: Optional[dict] = None,
    ) -> Optional[str]:
        """Check thresholds and cooldown, then send Telegram alert if warranted.

        Args:
            blog_id: Blog identifier (e.g., 'pet-hugo').
            reason: Failure reason string (e.g., 'irrelevant_products').
            context: Optional dict with additional context for the alert message.
                     Must include 'consecutive_failures' int for threshold check.

        Returns:
            Alert message string if alert was sent (or would have been sent
            in dry_run mode), or None if suppressed (disabled, cooldown active,
            or consecutive count below threshold).
        """
        config = self.get_config(blog_id)

        if not config.get("enabled", True):
            logger.debug(f"[alert_threshold] 알림 비활성화: {blog_id}/{reason}")
            return None

        # 연속 횟수 확인 (새로 추가)
        consecutive = context.get("consecutive_failures", 0) if context else 0
        threshold = config.get("consecutive_failures", 3)
        if consecutive < threshold:
            logger.debug(
                f"[alert_threshold] 연속 {consecutive}회 < 임계값 {threshold}: "
                f"{blog_id}/{reason}"
            )
            return None

        if self._in_cooldown(blog_id):
            remaining = (
                config["cooldown_minutes"]
                - (time.time() - self._last_alerted[blog_id]) / 60
            )
            logger.info(
                f"[alert_threshold] 쿨다운 중: {blog_id}/{reason} "
                f"(남은: {remaining:.0f}분)"
            )
            return None

        # Build alert message
        message = f"[임계값 초과] {blog_id}: {reason} (연속 {consecutive}회)"
        if context:
            ctx_str = ", ".join(f"{k}={v}" for k, v in context.items())
            message += f" ({ctx_str})"

        self._mark_alerted(blog_id)

        if config.get("dry_run", False):
            logger.info(f"[alert_threshold DRY-RUN] {message}")
        else:
            from shared.telegram_notifier import send_error as _tg_error

            logger.info(f"[alert_threshold] 알림 전송: {message}")
            _tg_error(blog_id, reason, message)

        return message

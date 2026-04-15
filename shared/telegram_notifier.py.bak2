"""텔레그램 알림 허브 — 3등급 분리
CRITICAL : 🚨 즉시 확인 필요 (스케줄러 중단, 발행 실패, API 키 오류 등)
WARNING  : ⚠️  품질 이슈 (quality_guard draft 처리, 데이터 이상 등)
INFO     : 📊 일반 정보 (일일 리포트, 발행 완료 요약 등)

외부에서는 send_critical / send_warning / send_info / send_error 만 사용.
send() 는 내부 공통 전송 함수.
"""
import os
import logging
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")
_API_URL  = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

# 등급별 쿨다운 (초) — 동일 메시지 반복 전송 방지
_COOLDOWN: dict[str, float] = {}
_COOLDOWN_SEC = {"CRITICAL": 0, "WARNING": 300, "INFO": 0}  # WARNING은 5분 내 중복 차단


def _esc(text: str) -> str:
    """Telegram HTML 특수문자 이스케이프"""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def send(message: str, parse_mode: str = "HTML") -> bool:
    """공통 전송. 실패해도 False만 반환 — 발행 프로세스 중단 안 함."""
    if not BOT_TOKEN or not CHAT_ID:
        logger.debug("TELEGRAM 미설정 — 알림 생략")
        return False
    try:
        resp = requests.post(
            _API_URL,
            json={"chat_id": CHAT_ID, "text": message[:4000], "parse_mode": parse_mode},
            timeout=10,
        )
        if resp.status_code == 200:
            return True
        logger.warning(f"Telegram send failed: {resp.status_code} {resp.text[:100]}")
        return False
    except requests.RequestException as e:
        logger.error(f"[TELEGRAM] Request failed: {e}")
        return False


def _dedup_key(level: str, title: str) -> str:
    return f"{level}:{title[:80]}"


def _is_cooldown(level: str, title: str) -> bool:
    import time
    key = _dedup_key(level, title)
    cooldown = _COOLDOWN_SEC.get(level, 0)
    if cooldown == 0:
        return False
    last = _COOLDOWN.get(key, 0)
    if time.time() - last < cooldown:
        return True
    _COOLDOWN[key] = time.time()
    return False


def send_critical(title: str, detail: str = "", exc=None) -> bool:
    """🚨 CRITICAL — 즉시 확인 필요. 스케줄러/발행 실패, API 오류 등."""
    if _is_cooldown("CRITICAL", title):
        return False
    from datetime import datetime
    now = datetime.now().strftime("%m-%d %H:%M")
    msg = f"🚨 <b>[CRITICAL] {_esc(title)}</b>\n<i>{now}</i>"
    if detail:
        msg += f"\n{_esc(str(detail)[:500])}"
    if exc is not None:
        import traceback
        tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))[-600:]
        msg += f"\n<pre>{_esc(tb)}</pre>"
    return send(msg)


def send_warning(title: str, detail: str = "") -> bool:
    """⚠️ WARNING — 품질 이슈, 데이터 이상. 5분 내 동일 제목 중복 차단."""
    if _is_cooldown("WARNING", title):
        logger.debug(f"[TELEGRAM] WARNING 쿨다운 중: {title}")
        return False
    from datetime import datetime
    now = datetime.now().strftime("%m-%d %H:%M")
    msg = f"⚠️ <b>[WARNING] {_esc(title)}</b>\n<i>{now}</i>"
    if detail:
        msg += f"\n{_esc(str(detail)[:600])}"
    return send(msg)


def send_info(title: str, detail: str = "") -> bool:
    """📊 INFO — 일일 리포트, 발행 완료 요약 등."""
    from datetime import datetime
    now = datetime.now().strftime("%m-%d %H:%M")
    msg = f"📊 <b>[INFO] {_esc(title)}</b>\n<i>{now}</i>"
    if detail:
        msg += f"\n{detail}"  # 리포트는 이미 HTML 포맷이므로 esc 안 함
    return send(msg)


# ── 하위 호환 함수들 (기존 코드 수정 최소화) ──────────────────────────

def send_error(blog_id: str, stage: str, error_msg: str, exc=None) -> bool:
    """CRITICAL 래퍼 — dispatcher/scheduler에서 사용하던 기존 시그니처 유지."""
    _SILENT = ["quota_met", "quota_exceeded", "daily_quota"]
    if any(r in str(error_msg).lower() for r in _SILENT):
        logger.info(f"[Silent] {blog_id}/{stage}: {error_msg}")
        return False

    # blogs.yaml에서 도메인/파이프라인 보강
    domain = pipeline = ""
    try:
        import yaml
        from pathlib import Path
        cfg = yaml.safe_load(
            (Path(__file__).parent.parent / "config" / "blogs.yaml").read_text(encoding="utf-8")
        )
        for b in cfg.get("blogs", []):
            if b.get("id") == blog_id:
                domain   = b.get("domain", "")
                pipeline = b.get("pipeline", "")
                break
    except Exception:
        pass

    lines = [f"블로그: {blog_id}"]
    if domain:   lines.append(f"도메인: {domain}")
    if pipeline: lines.append(f"파이프라인: {pipeline}")
    lines.append(f"단계: {stage}")
    lines.append(f"오류: {str(error_msg)[:300]}")
    detail = "\n".join(lines)
    return send_critical(f"발행 오류 — {blog_id}/{stage}", detail, exc=exc)


def send_daily_report(report_text: str) -> bool:
    """INFO 래퍼 — daily_report.py에서 사용하던 기존 시그니처 유지."""
    return send(report_text)


def alert(title: str, detail: str = "") -> bool:
    """WARNING 래퍼 — shared/notify.py의 alert() 대체."""
    return send_warning(title, detail)

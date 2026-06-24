import os
import requests
import logging
from dotenv import load_dotenv

# 중앙 env 파일 로드
load_dotenv("/Users/twinssn/.env.common")
# 프로젝트 .env 파일도 로드 ( 덮어쓰기 가능)
load_dotenv()

logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
API_URL = "https://api.telegram.org/bot" + BOT_TOKEN + "/sendMessage"


def send(message, parse_mode="HTML"):
    if not BOT_TOKEN or not CHAT_ID:
        logger.warning("Telegram credentials missing")
        return False
    try:
        resp = requests.post(API_URL, json={
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": parse_mode,
        }, timeout=10)
        if resp.status_code == 200:
            return True
        logger.warning("Telegram send failed: " + str(resp.status_code))
        return False
    except requests.RequestException as e:
        logger.error(f"[TELEGRAM_ERROR] Request failed: {e}")
        return False


def send_error(blog_id, stage, error_msg):
    # 정상 동작인 quota 초과는 알림 불필요 (로그에만 기록)
    _SILENT_REASONS = ["quota_met", "quota_exceeded", "daily_quota_exceeded", "daily_quota"]
    _err_lower = str(error_msg).lower()
    if any(reason in _err_lower for reason in _SILENT_REASONS):
        logger.info(f"[Silent] {blog_id}/{stage}: {error_msg}")
        return False

    # blogs.d/*.yaml 전체에서 도메인, 레포 정보 가져오기
    domain = ""
    repo = ""
    try:
        import yaml
        from pathlib import Path
        config_dir = Path(__file__).parent.parent / "config"
        all_blogs = []
        blogs_d = config_dir / "blogs.d"
        if blogs_d.is_dir():
            for fpath in sorted(blogs_d.glob("*.yaml")):
                with open(fpath, "r", encoding="utf-8") as yf:
                    data = yaml.safe_load(yf) or {}
                all_blogs.extend(data.get("blogs", []))
        for blog in all_blogs:
            if blog and blog.get("id") == blog_id:
                domain = blog.get("domain", "")
                repo = blog.get("repo", "")
                break
    except (IOError, yaml.YAMLError) as e:
        logger.error(f"[CONFIG_ERROR] Failed to load blogs.d: {e}")

    text = "🚨 <b>발행 오류</b>\n"
    text += "<b>블로그:</b> " + blog_id + "\n"
    if domain:
        text += "<b>도메인:</b> " + domain + "\n"
    if repo:
        text += "<b>레포:</b> " + repo + "\n"
    text += "<b>단계:</b> " + stage + "\n"
    text += "<b>오류:</b> " + str(error_msg)[:500]
    return send(text)


def send_daily_report(report_text):
    return send(report_text)

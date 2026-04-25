#!/usr/bin/env python3
"""
db_backup.py — 5000 프로젝트 DB 백업
- 대상: 5000/data/ + STAP/data/ + TAP/
- 백업: Cloudflare R2 (hotissue-images / db-backups/)
- 보존: 7일
- 실행: 매일 05:00 (launchd)
- 수정: 2026-04-25 (DB 정리 반영)
"""
import os, gzip, shutil, logging, subprocess
from datetime import datetime, timedelta
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

DATE       = datetime.now().strftime("%Y%m%d")
BACKUP_DIR = Path.home() / "Projects/5000/data/backups"
R2_BUCKET  = "hotissue-images"
R2_PREFIX  = "db-backups"
RETAIN_DAYS = 7

TARGETS = [
    # ── 5000 내부 ──────────────────────────────
    Path.home() / "Projects/5000/data/content.db",
    Path.home() / "Projects/5000/data/5000_content.db",
    Path.home() / "Projects/5000/data/analytics.db",
    Path.home() / "Projects/5000/data/stock.db",
    Path.home() / "Projects/5000/data/car.db",
    Path.home() / "Projects/5000/data/travel-en.db",
    Path.home() / "Projects/5000/data/rap.db",
    Path.home() / "Projects/5000/data/curation.db",
    Path.home() / "Projects/5000/data/festival.db",
    Path.home() / "Projects/5000/data/scanner.db",
    # ── STAP ───────────────────────────────────
    Path.home() / "Projects/STAP/data/stap.db",
    Path.home() / "Projects/STAP/data/stap_content.db",
    Path.home() / "Projects/STAP/data/stap_entities.db",
    Path.home() / "Projects/STAP/data/stock.db",
    # ── TAP ────────────────────────────────────
    Path.home() / "Projects/TAP/tap.db",
]

def backup_db(src: Path) -> Path | None:
    if not src.exists():
        logger.warning(f"SKIP (없음): {src.name}")
        return None
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    dst = BACKUP_DIR / f"{src.stem}_{DATE}.db.gz"
    try:
        with open(src, "rb") as f_in, gzip.open(dst, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
        logger.info(f"압축 완료: {dst.name} ({dst.stat().st_size // 1024}KB)")
        return dst
    except Exception as e:
        logger.error(f"압축 실패 {src.name}: {e}")
        return None

def upload_r2(local: Path) -> bool:
    r2_path = f"r2://{R2_BUCKET}/{R2_PREFIX}/{local.name}"
    try:
        result = subprocess.run(
            ["rclone", "copyto", str(local), r2_path],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0:
            logger.info(f"R2 업로드 완료: {local.name}")
            return True
        else:
            logger.error(f"R2 업로드 실패: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"R2 업로드 오류: {e}")
        return False

def cleanup_old():
    cutoff = datetime.now() - timedelta(days=RETAIN_DAYS)
    removed = 0
    for f in BACKUP_DIR.glob("*.db.gz"):
        parts = f.stem.replace(".db", "").split("_")
        try:
            date_str = parts[-1]
            file_date = datetime.strptime(date_str, "%Y%m%d")
            if file_date < cutoff:
                f.unlink()
                removed += 1
                logger.info(f"삭제 (7일 초과): {f.name}")
        except Exception:
            continue
    logger.info(f"정리 완료: {removed}개 삭제")

def main():
    logger.info(f"=== DB 백업 시작: {DATE} ===")
    success, fail, skip = 0, 0, 0
    for src in TARGETS:
        dst = backup_db(src)
        if dst is None:
            skip += 1
            continue
        if upload_r2(dst):
            success += 1
        else:
            fail += 1
    cleanup_old()
    logger.info(f"=== 완료: 성공={success} 실패={fail} 스킵={skip} ===")

if __name__ == "__main__":
    main()

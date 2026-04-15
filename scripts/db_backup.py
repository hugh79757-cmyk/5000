#!/usr/bin/env python3
"""5000 DB 백업 — 로컬 + R2 업로드
launchd: com.5000.db-backup.plist (매일 05:00)
"""
import os
import sys
import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("db_backup")

BACKUP_DIR = Path(__file__).parent.parent / "data" / "backups"
BACKUP_DIR.mkdir(exist_ok=True)

DBS = [
    Path.home() / "Projects/5000/data/content.db",
    Path.home() / "Projects/5000/data/car.db",
    Path.home() / "Projects/5000/data/travel-en.db",
    Path.home() / "Projects/5000/data/rap.db",
    Path.home() / "Projects/5000/data/analytics.db",
    Path.home() / "Projects/5000/data/stock.db",
    Path.home() / "Projects/5000/data/curation.db",
    Path.home() / "Projects/STAP/data/stap.db",
    Path.home() / "Projects/STAP/data/stap_content.db",
]

DATE = datetime.now().strftime("%Y%m%d")


def local_backup(db_path):
    name = db_path.stem
    backup_file = BACKUP_DIR / f"{name}_{DATE}.db"
    try:
        conn = sqlite3.connect(str(db_path))
        bak = sqlite3.connect(str(backup_file))
        conn.backup(bak)
        bak.close()
        conn.close()
        logger.info(f"[LOCAL OK] {name} -> {backup_file.name}")
        return backup_file
    except Exception as e:
        logger.error(f"[LOCAL FAIL] {name}: {e}")
        return None


def r2_upload(backup_file):
    import boto3
    endpoint = os.getenv("R2_ENDPOINT", "")
    access_key = os.getenv("R2_ACCESS_KEY_ID", "")
    secret_key = os.getenv("R2_SECRET_ACCESS_KEY", "")
    bucket = os.getenv("R2_BUCKET_NAME", "")

    if not all([endpoint, access_key, secret_key, bucket]):
        logger.warning("[R2 SKIP] R2 환경변수 미설정")
        return False

    try:
        s3 = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )
        key = f"db-backups/{backup_file.name}"
        s3.upload_file(str(backup_file), bucket, key)
        logger.info(f"[R2 OK] {backup_file.name} -> s3://{bucket}/{key}")
        return True
    except Exception as e:
        logger.error(f"[R2 FAIL] {backup_file.name}: {e}")
        return False


def r2_cleanup():
    import boto3
    endpoint = os.getenv("R2_ENDPOINT", "")
    access_key = os.getenv("R2_ACCESS_KEY_ID", "")
    secret_key = os.getenv("R2_SECRET_ACCESS_KEY", "")
    bucket = os.getenv("R2_BUCKET_NAME", "")

    if not all([endpoint, access_key, secret_key, bucket]):
        return

    cutoff = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")
    try:
        s3 = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )
        resp = s3.list_objects_v2(Bucket=bucket, Prefix="db-backups/")
        for obj in resp.get("Contents", []):
            fname = obj["Key"].split("/")[-1]
            # 파일명에서 날짜 추출: name_YYYYMMDD.db
            parts = fname.replace(".db", "").split("_")
            if parts and parts[-1].isdigit() and len(parts[-1]) == 8:
                if parts[-1] < cutoff:
                    s3.delete_object(Bucket=bucket, Key=obj["Key"])
                    logger.info(f"[R2 DEL] {obj['Key']}")
    except Exception as e:
        logger.error(f"[R2 CLEANUP FAIL] {e}")


def local_cleanup():
    cutoff = datetime.now() - timedelta(days=7)
    for f in BACKUP_DIR.glob("*.db"):
        if datetime.fromtimestamp(f.stat().st_mtime) < cutoff:
            f.unlink()
            logger.info(f"[LOCAL DEL] {f.name}")


def main():
    logger.info("=== DB Backup Start ===")
    ok, fail = 0, 0

    for db_path in DBS:
        if not db_path.exists():
            logger.warning(f"[SKIP] {db_path} 없음")
            continue
        backup_file = local_backup(db_path)
        if backup_file:
            ok += 1
            r2_upload(backup_file)
        else:
            fail += 1

    local_cleanup()
    r2_cleanup()
    logger.info(f"=== DB Backup Done: OK={ok}, FAIL={fail} ===")


if __name__ == "__main__":
    main()

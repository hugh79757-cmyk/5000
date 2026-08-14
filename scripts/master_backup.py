#!/usr/bin/env python3
"""
master_backup.py — 통합 백업 스크립트 v2.1.0
- [1] 5000 DB 백업     → db-backups/5000/
- [2] SAP DB 백업      → db-backups/sap/
- [3] Hugo MD 백업     → db-backups/{pipeline}/
- 보존: 7일
- 실행: 매일 05:00 (launchd)
- 텔레그램: 전체 완료 후 1회 요약 발송
- v2.0.0: arcname에 slug 경로 포함 (복구 가능하도록 수정)
- v2.1.0: 하드코딩 제거, yaml 자동 로드, site_path 대소문자 자동 보정
"""
import os, sys, gzip, shutil, tarfile, logging, subprocess
from datetime import datetime, timedelta
from pathlib import Path

import yaml

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

DATE        = datetime.now().strftime("%Y%m%d")
PROJ_ROOT   = Path.home() / "Projects"
BACKUP_DIR  = PROJ_ROOT / "5000/data/backups"
R2_BUCKET   = "hotissue-images"
RETAIN_DAYS = 7
R2_ENV_FILE = Path.home() / ".env.common"

BLOGS_D  = PROJ_ROOT / "5000/config/blogs.d"
SAP_YAML = PROJ_ROOT / "SAP/config/blogs.yaml"

# ── DB 백업 대상 ────────────────────────────────────────
DB_TARGETS = {
    "5000": [
        PROJ_ROOT / "5000/data/content.db",
        PROJ_ROOT / "5000/data/5000_content.db",
        PROJ_ROOT / "5000/data/analytics.db",
        PROJ_ROOT / "5000/data/stock.db",
        PROJ_ROOT / "5000/data/car.db",
        PROJ_ROOT / "5000/data/travel-en.db",
        PROJ_ROOT / "5000/data/rap.db",
        PROJ_ROOT / "5000/data/curation.db",
        PROJ_ROOT / "5000/data/festival.db",
        PROJ_ROOT / "5000/data/scanner.db",
        PROJ_ROOT / "STAP/data/stap.db",
        PROJ_ROOT / "STAP/data/stap_content.db",
        PROJ_ROOT / "STAP/data/stap_entities.db",
        PROJ_ROOT / "STAP/data/stock.db",
        PROJ_ROOT / "TAP/tap.db",
    ],
    "sap": [
        PROJ_ROOT / "SAP/data/daum_match.db",
        PROJ_ROOT / "SAP/data/indexnow.db",
        PROJ_ROOT / "SAP/data/kbo.db",
        PROJ_ROOT / "SAP/data/kleague.db",
        PROJ_ROOT / "SAP/data/match.db",
        PROJ_ROOT / "SAP/data/proto.db",
        PROJ_ROOT / "SAP/data/publish_log.db",
    ],
}


# ── 공통 유틸 ───────────────────────────────────────────
def resolve_path(p: Path) -> Path:
    """실제 존재하는 경로 반환. 대소문자 불일치 시 자동 보정."""
    if p.exists():
        return p
    # PROJ_ROOT 기준으로 각 파트를 대소문자 무시하고 탐색
    resolved = PROJ_ROOT
    parts = p.relative_to(PROJ_ROOT).parts
    for part in parts:
        candidates = [c for c in resolved.iterdir() if c.name.lower() == part.lower()]
        if not candidates:
            return p  # 보정 불가 → 원본 반환
        resolved = candidates[0]
    return resolved


def upload_r2(r2_path: str, local: Path) -> bool:
    cmd = [
        "/opt/homebrew/bin/rclone", "copyto",
        str(local), r2_path,
        "--config", str(Path.home() / ".config/rclone/rclone.conf"),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(f"R2 업로드 실패 {local.name}: {result.stderr.strip()}")
        return False
    logger.info(f"R2 업로드 완료: {r2_path}")
    return True


# ── [1][2] DB 백업 ──────────────────────────────────────

def _load_env_file(path: Path) -> None:
    """Load only missing R2 environment keys without logging secret values."""
    if not path.exists():
        return
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if key.startswith("export "):
                key = key[7:].strip()
            if not key or not key.startswith("R2_"):
                continue
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                value = value[1:-1]
            os.environ.setdefault(key, value)
    except Exception as e:
        logger.error(f"R2 ;  : {e}")


def get_r2_config() -> dict | None:
    """Return R2 config without exposing secret values in logs."""
    _load_env_file(R2_ENV_FILE)
    if not os.environ.get("R2_ENDPOINT") and os.environ.get("R2_ACCOUNT_ID"):
        os.environ["R2_ENDPOINT"] = (
            f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com"
        )
    required = ("R2_ENDPOINT", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY")
    missing = [key for key in required if not os.environ.get(key)]
    if missing:
        logger.error(f": {', '.join(missing)}")
        return None
    return {
        "endpoint": os.environ["R2_ENDPOINT"],
        "access_key": os.environ["R2_ACCESS_KEY_ID"],
        "secret_key": os.environ["R2_SECRET_ACCESS_KEY"],
        "bucket": os.environ.get("R2_BUCKET_NAME", R2_BUCKET),
    }
def run_db_backup() -> dict:
    stats = {}
    for group, targets in DB_TARGETS.items():
        out_dir = BACKUP_DIR / "db" / group
        out_dir.mkdir(parents=True, exist_ok=True)
        success, fail, skip = 0, 0, 0
        for src in targets:
            src = resolve_path(src)
            if not src.exists():
                logger.warning(f"SKIP (없음): {src.name}")
                skip += 1
                continue
            dst = out_dir / f"{src.stem}_{DATE}.db.gz"
            try:
                with open(src, "rb") as f_in, gzip.open(dst, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
                logger.info(f"DB 압축: {dst.name} ({dst.stat().st_size // 1024}KB)")
            except Exception as e:
                logger.error(f"DB 압축 실패 {src.name}: {e}")
                fail += 1
                continue
            if upload_r2(f"r2://{R2_BUCKET}/db-backups/{group}/{dst.name}", dst):
                success += 1
            else:
                fail += 1
        stats[group] = {"success": success, "fail": fail, "skip": skip}
        logger.info(f"[DB/{group}] 완료: 성공={success} 실패={fail} 스킵={skip}")
    return stats


# ── [3] Hugo MD 백업 ────────────────────────────────────
def load_md_targets() -> list[dict]:
    targets = []

    # blogs.d/*.yaml 전체 로드
    for yaml_file in sorted(BLOGS_D.glob("*.yaml")):
        if yaml_file.suffix == ".bak":
            continue
        try:
            data = yaml.safe_load(yaml_file.read_text())
            pipeline = yaml_file.stem
            for blog in data.get("blogs", []):
                if blog.get("platform") == "hugo" and blog.get("site_path"):
                    site_path = resolve_path(Path(blog["site_path"]))
                    targets.append({
                        "pipeline": pipeline,
                        "id": blog.get("id", "unknown"),
                        "site_path": site_path,
                    })
        except Exception as e:
            logger.error(f"yaml 파싱 실패 {yaml_file.name}: {e}")

    # SAP yaml
    try:
        data = yaml.safe_load(SAP_YAML.read_text())
        for blog in data.get("blogs", []):
            if blog.get("platform") == "hugo" and blog.get("site_path"):
                site_path = resolve_path(Path(blog["site_path"]))
                targets.append({
                    "pipeline": "sap-content",
                    "id": blog.get("id", "unknown"),
                    "site_path": site_path,
                })
    except Exception as e:
        logger.error(f"SAP yaml 파싱 실패: {e}")

    logger.info(f"총 {len(targets)}개 Hugo 사이트 로드")
    return targets


def backup_site(pipeline: str, site_id: str, site_path: Path) -> tuple[Path | None, int]:
    content_dir = site_path / "content"
    posts_dir = content_dir / "posts"

    # posts/ 없으면 content/ 하위 전체 섹션 백업 (멀티섹션 블로그 대응)
    md_files = []
    if posts_dir.exists():
        for md in posts_dir.glob("*.md"):
            md_files.append((md, md.name))
        for md in posts_dir.glob("*/index.md"):
            md_files.append((md, f"{md.parent.name}/{md.name}"))
    elif content_dir.exists():
        for section in content_dir.iterdir():
            if section.is_dir() and not section.name.startswith("_"):
                for md in section.rglob("*.md"):
                    md_files.append((md, md.relative_to(content_dir)))
        if md_files:
            logger.info(f"멀티섹션 백업: {site_id} ({len(md_files)}개)")
        else:
            logger.warning(f"SKIP (MD 없음): {site_id}")
            return None, 0
    else:
        logger.warning(f"SKIP (content 없음): {site_id} ({site_path})")
        return None, 0

    if not md_files:
        logger.warning(f"SKIP (MD 없음): {site_id}")
        return None, 0

    out_dir = BACKUP_DIR / "content" / pipeline
    out_dir.mkdir(parents=True, exist_ok=True)
    dst = out_dir / f"{pipeline}-{site_id}-{DATE}.tar.gz"

    try:
        with tarfile.open(dst, "w:gz") as tar:
            for md_path, arcname in md_files:
                tar.add(md_path, arcname=arcname)

        # ── 백업 검증 ──
        with tarfile.open(dst, "r:gz") as verify_tar:
            backed_up = len(verify_tar.getmembers())

        if backed_up != len(md_files):
            logger.error(f"검증 실패 {site_id}: 원본={len(md_files)} 백업={backed_up}")
            return None, 0

        logger.info(f"MD 압축+검증 완료: {dst.name} ({backed_up}개, {dst.stat().st_size // 1024}KB)")
        return dst, len(md_files)

    except Exception as e:
        logger.error(f"MD 압축 실패 {site_id}: {e}")
        return None, 0


def run_content_backup() -> dict:
    targets = load_md_targets()
    pipeline_stats = {}
    total_success, total_fail, total_skip = 0, 0, 0

    for t in targets:
        pipeline = t["pipeline"]
        dst, count = backup_site(pipeline, t["id"], t["site_path"])
        if dst is None:
            total_skip += 1
            continue
        if upload_r2(f"r2://{R2_BUCKET}/db-backups/{pipeline}/{dst.name}", dst):
            total_success += 1
            if pipeline not in pipeline_stats:
                pipeline_stats[pipeline] = {"sites": 0, "files": 0}
            pipeline_stats[pipeline]["sites"] += 1
            pipeline_stats[pipeline]["files"] += count
        else:
            total_fail += 1

    logger.info(f"[MD] 완료: 성공={total_success} 실패={total_fail} 스킵={total_skip}")
    return {"pipeline_stats": pipeline_stats, "success": total_success, "fail": total_fail, "skip": total_skip}


# ── 정리 ────────────────────────────────────────────────
def cleanup_old():
    cutoff = datetime.now() - timedelta(days=RETAIN_DAYS)
    removed = 0
    for f in BACKUP_DIR.rglob("*"):
        if not f.is_file():
            continue
        if f.suffix not in (".gz",):
            continue
        stem = f.stem.replace(".db", "").replace(".tar", "")
        for part in reversed(stem.split("-") + stem.split("_")):
            try:
                if datetime.strptime(part, "%Y%m%d") < cutoff:
                    f.unlink()
                    removed += 1
                    logger.info(f"삭제 (7일 초과): {f.name}")
                break
            except ValueError:
                continue
    logger.info(f"정리 완료: {removed}개 삭제")




def cleanup_r2_old(*, dry_run: bool = True) -> dict:
    """Report or delete expired backup objects; dry-run is the default."""
    config = get_r2_config()
    if not config:
        return {"status": "skipped_missing_credentials", "scanned": 0, "candidates": 0, "bytes": 0}
    try:
        import boto3
        from botocore.config import Config
        cutoff = datetime.now() - timedelta(days=RETAIN_DAYS)
        s3 = boto3.client(
            "s3",
            endpoint_url=config["endpoint"],
            aws_access_key_id=config["access_key"],
            aws_secret_access_key=config["secret_key"],
            config=Config(signature_version="s3v4"),
        )
        prefix = "db-backups/"
        scanned = candidates = removed = bytes_total = 0
        for page in s3.get_paginator("list_objects_v2").paginate(Bucket=config["bucket"], Prefix=prefix):
            for obj in page.get("Contents", []):
                scanned += 1
                key = obj["Key"]
                name = key.rsplit("/", 1)[-1]
                stem = name.replace(".db.gz", "").replace(".tar.gz", "")
                date_dt = None
                for part in reversed(stem.replace("-", "_").split("_")):
                    try:
                        date_dt = datetime.strptime(part, "%Y%m%d")
                        break
                    except ValueError:
                        continue
                if not date_dt or date_dt >= cutoff:
                    continue

                candidates += 1
                size = int(obj.get("Size", 0) or 0)
                bytes_total += size
                if dry_run:
                    logger.info(f"[R2 dry-run]  :::::::::::::::::::::::::::::::::: {key} ({size} bytes)")
                else:
                    s3.delete_object(Bucket=config["bucket"], Key=key)
                    removed += 1
                    logger.info(f"[r2 ] {key} ({size} bytes)")
        status = "dry_run" if dry_run else "success"
        logger.info(f"[R2  {status}] scanned={scanned} candidates={candidates} removed={removed} bytes={bytes_total}")
        return {"status": status, "scanned": scanned, "candidates": candidates, "removed": removed, "bytes": bytes_total}
    except Exception as e:
        logger.exception(f"R2  : {e}")
        return {"status": "failed", "scanned": 0, "candidates": 0, "bytes": 0, "error": str(e)}
# ── 텔레그램 ─────────────────────────────────────────────
def send_summary(db_stats: dict, md_stats: dict):
    try:
        sys.path.insert(0, str(PROJ_ROOT / "5000"))
        from shared.notify import send_telegram

        total_fail = sum(v["fail"] for v in db_stats.values()) + md_stats["fail"]
        icon = "✅" if total_fail == 0 else "⚠️"
        lines = [f"{icon} <b>[통합 백업 v2.1]</b> {DATE}", ""]

        lines.append("<b>📦 DB 백업</b>")
        for group, s in db_stats.items():
            lines.append(f"  • {group}: 성공 {s['success']} / 실패 {s['fail']} / 스킵 {s['skip']}")

        lines.append("")
        lines.append("<b>📝 MD 백업</b>")
        for pl, s in sorted(md_stats["pipeline_stats"].items()):
            lines.append(f"  • {pl}: {s['sites']}개 사이트 / {s['files']}개 파일")
        lines.append(f"  성공 {md_stats['success']} / 실패 {md_stats['fail']} / 스킵 {md_stats['skip']}")

        send_telegram("\n".join(lines))
    except Exception as e:
        logger.warning(f"텔레그램 알림 실패: {e}")


# ── 메인 ─────────────────────────────────────────────────
def main():
    logger.info(f"=== 통합 백업 시작 v2.1.0: {DATE} ===")
    db_stats = run_db_backup()
    md_stats = run_content_backup()
    cleanup_old()
    cleanup_r2_old(dry_run=False)
    send_summary(db_stats, md_stats)
    logger.info(f"=== 통합 백업 완료 ===")


if __name__ == "__main__":
    if "--r2-cleanup-apply" in sys.argv:
        print(cleanup_r2_old(dry_run=False))
    elif "--r2-cleanup-dry-run" in sys.argv:
        print(cleanup_r2_old(dry_run=True))
    else:
        main()

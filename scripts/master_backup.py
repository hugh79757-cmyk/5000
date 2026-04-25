#!/usr/bin/env python3
"""
master_backup.py — 통합 백업 스크립트
- [1] 5000 DB 백업     → db-backups/5000/
- [2] SAP DB 백업      → db-backups/sap/
- [3] Hugo MD 백업     → db-backups/{pipeline}/
- 보존: 7일
- 실행: 매일 05:00 (launchd)
- 텔레그램: 전체 완료 후 1회 요약 발송
"""
import sys, gzip, shutil, tarfile, logging, subprocess
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
def upload_r2(r2_path: str, local: Path) -> bool:
    try:
        result = subprocess.run(
            ["rclone", "copyto", str(local), r2_path],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0:
            logger.info(f"R2 업로드 완료: {local.name}")
            return True
        else:
            logger.error(f"R2 업로드 실패 {local.name}: {result.stderr.strip()}")
            return False
    except Exception as e:
        logger.error(f"R2 업로드 오류 {local.name}: {e}")
        return False


# ── [1][2] DB 백업 ──────────────────────────────────────
def run_db_backup() -> dict:
    stats = {}
    for group, targets in DB_TARGETS.items():
        out_dir = BACKUP_DIR / "db" / group
        out_dir.mkdir(parents=True, exist_ok=True)
        success, fail, skip = 0, 0, 0
        for src in targets:
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
    for yaml_file in sorted(BLOGS_D.glob("*.yaml")):
        if yaml_file.suffix == ".bak":
            continue
        try:
            data = yaml.safe_load(yaml_file.read_text())
            pipeline = yaml_file.stem
            for blog in data.get("blogs", []):
                if blog.get("platform") == "hugo" and blog.get("site_path"):
                    targets.append({
                        "pipeline": pipeline,
                        "id": blog.get("id", "unknown"),
                        "site_path": Path(blog["site_path"]),
                    })
        except Exception as e:
            logger.error(f"yaml 파싱 실패 {yaml_file.name}: {e}")
    try:
        data = yaml.safe_load(SAP_YAML.read_text())
        for blog in data.get("blogs", []):
            if blog.get("platform") == "hugo" and blog.get("site_path"):
                targets.append({
                    "pipeline": "sap-content",
                    "id": blog.get("id", "unknown"),
                    "site_path": Path(blog["site_path"]),
                })
    except Exception as e:
        logger.error(f"SAP yaml 파싱 실패: {e}")
    return targets


def backup_site(pipeline: str, site_id: str, site_path: Path) -> tuple[Path | None, int]:
    posts_dir = site_path / "content" / "posts"
    if not posts_dir.exists():
        logger.warning(f"SKIP (없음): {site_id}")
        return None, 0
    md_files = list(posts_dir.glob("*.md")) + list(posts_dir.glob("*/index.md"))
    if not md_files:
        logger.warning(f"SKIP (MD 없음): {site_id}")
        return None, 0
    out_dir = BACKUP_DIR / "content" / pipeline
    out_dir.mkdir(parents=True, exist_ok=True)
    dst = out_dir / f"{pipeline}-{site_id}-{DATE}.tar.gz"
    try:
        with tarfile.open(dst, "w:gz") as tar:
            for md in md_files:
                tar.add(md, arcname=md.name)
        logger.info(f"MD 압축: {dst.name} ({len(md_files)}개, {dst.stat().st_size // 1024}KB)")
        return dst, len(md_files)
    except Exception as e:
        logger.error(f"MD 압축 실패 {site_id}: {e}")
        return None, 0


def run_content_backup() -> dict:
    targets = load_md_targets()
    logger.info(f"MD 백업 대상: {len(targets)}개 사이트")
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
        if f.suffix not in (".gz",) and not f.name.endswith(".tar.gz"):
            continue
        parts = f.stem.replace(".db", "").split("_") + f.stem.split("-")
        for part in reversed(parts):
            try:
                if datetime.strptime(part, "%Y%m%d") < cutoff:
                    f.unlink()
                    removed += 1
                    logger.info(f"삭제 (7일 초과): {f.name}")
                break
            except ValueError:
                continue
    logger.info(f"정리 완료: {removed}개 삭제")


# ── 텔레그램 ─────────────────────────────────────────────
def send_summary(db_stats: dict, md_stats: dict):
    try:
        sys.path.insert(0, str(PROJ_ROOT / "5000"))
        from shared.notify import send_telegram

        total_fail = sum(v["fail"] for v in db_stats.values()) + md_stats["fail"]
        icon = "✅" if total_fail == 0 else "⚠️"
        lines = [f"{icon} <b>[통합 백업]</b> {DATE}", ""]

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
    logger.info(f"=== 통합 백업 시작: {DATE} ===")
    db_stats = run_db_backup()
    md_stats = run_content_backup()
    cleanup_old()
    send_summary(db_stats, md_stats)
    logger.info(f"=== 통합 백업 완료 ===")


if __name__ == "__main__":
    main()

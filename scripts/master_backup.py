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
    posts_dir = site_path / "content" / "posts"
    if not posts_dir.exists():
        logger.warning(f"SKIP (posts 없음): {site_id} ({site_path})")
        return None, 0

    # flat: posts/*.md → arcname 그대로
    # page bundle: posts/{slug}/index.md → arcname = {slug}/index.md
    md_files = []
    for md in posts_dir.glob("*.md"):
        md_files.append((md, md.name))
    for md in posts_dir.glob("*/index.md"):
        md_files.append((md, f"{md.parent.name}/{md.name}"))

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
    send_summary(db_stats, md_stats)
    logger.info(f"=== 통합 백업 완료 ===")


if __name__ == "__main__":
    main()

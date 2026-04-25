#!/usr/bin/env python3
"""
content_backup.py — 전체 Hugo MD 파일 백업
- 대상: 5000/config/blogs.d/*.yaml 의 platform:hugo 사이트 전체
- 백업: Cloudflare R2 (hotissue-images / db-backups/{pipeline}/)
- 파일명: {pipeline}-{site_id}-{YYYYMMDD}.tar.gz
- 보존: 7일
- 실행: 매일 05:20 (launchd)
- 텔레그램: 파이프라인별 요약 알림
"""
import os, sys, tarfile, logging, subprocess
from datetime import datetime, timedelta
from pathlib import Path

import yaml

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

DATE        = datetime.now().strftime("%Y%m%d")
PROJ_ROOT   = Path.home() / "Projects"
BLOGS_D     = PROJ_ROOT / "5000/config/blogs.d"
BACKUP_DIR  = PROJ_ROOT / "5000/data/backups/content"
R2_BUCKET   = "hotissue-images"
RETAIN_DAYS = 7

# SAP는 별도 yaml 경로
SAP_YAML    = PROJ_ROOT / "SAP/config/blogs.yaml"


def load_targets() -> list[dict]:
    """모든 yaml에서 platform:hugo 사이트만 추출"""
    targets = []

    # 5000/config/blogs.d/*.yaml
    for yaml_file in sorted(BLOGS_D.glob("*.yaml")):
        if yaml_file.name.endswith(".bak"):
            continue
        try:
            data = yaml.safe_load(yaml_file.read_text())
            pipeline = yaml_file.stem  # cap, etap, tap ...
            for blog in data.get("blogs", []):
                if blog.get("platform") == "hugo" and blog.get("site_path"):
                    targets.append({
                        "pipeline": pipeline,
                        "id": blog.get("id", "unknown"),
                        "site_path": Path(blog["site_path"]),
                    })
        except Exception as e:
            logger.error(f"yaml 파싱 실패 {yaml_file.name}: {e}")

    # SAP/config/blogs.yaml
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

    # flat: posts/*.md / page bundle: posts/{slug}/index.md 둘 다 지원
    md_files = list(posts_dir.glob("*.md")) + list(posts_dir.glob("*/index.md"))
    if not md_files:
        logger.warning(f"SKIP (MD 없음): {site_id}")
        return None, 0

    out_dir = BACKUP_DIR / pipeline
    out_dir.mkdir(parents=True, exist_ok=True)
    dst = out_dir / f"{pipeline}-{site_id}-{DATE}.tar.gz"

    try:
        with tarfile.open(dst, "w:gz") as tar:
            for md in md_files:
                tar.add(md, arcname=md.name)
        size_kb = dst.stat().st_size // 1024
        logger.info(f"압축: {dst.name} ({len(md_files)}개, {size_kb}KB)")
        return dst, len(md_files)
    except Exception as e:
        logger.error(f"압축 실패 {site_id}: {e}")
        return None, 0


def upload_r2(pipeline: str, local: Path) -> bool:
    r2_path = f"r2://{R2_BUCKET}/db-backups/{pipeline}/{local.name}"
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


def cleanup_old():
    removed = 0
    cutoff = datetime.now() - timedelta(days=RETAIN_DAYS)
    for f in BACKUP_DIR.rglob("*.tar.gz"):
        parts = f.stem.split("-")
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
    logger.info(f"=== 콘텐츠 백업 시작: {DATE} ===")

    targets = load_targets()
    logger.info(f"백업 대상: {len(targets)}개 사이트")

    pipeline_stats = {}
    total_success, total_fail, total_skip = 0, 0, 0

    for t in targets:
        pipeline = t["pipeline"]
        dst, count = backup_site(pipeline, t["id"], t["site_path"])
        if dst is None:
            total_skip += 1
            continue
        if upload_r2(pipeline, dst):
            total_success += 1
            if pipeline not in pipeline_stats:
                pipeline_stats[pipeline] = {"sites": 0, "files": 0}
            pipeline_stats[pipeline]["sites"] += 1
            pipeline_stats[pipeline]["files"] += count
        else:
            total_fail += 1

    cleanup_old()
    logger.info(f"=== 완료: 성공={total_success} 실패={total_fail} 스킵={total_skip} ===")

    # 텔레그램 알림
    try:
        sys.path.insert(0, str(PROJ_ROOT / "5000"))
        from shared.notify import send_telegram
        icon = "✅" if total_fail == 0 else "⚠️"
        lines = [f"{icon} <b>[콘텐츠 백업]</b> {DATE}"]
        for pl, stat in sorted(pipeline_stats.items()):
            lines.append(f"  • {pl}: {stat['sites']}개 사이트 / {stat['files']}개 MD")
        lines.append(f"\n  성공: {total_success} / 실패: {total_fail} / 스킵: {total_skip}")
        send_telegram("\n".join(lines))
    except Exception as e:
        logger.warning(f"텔레그램 알림 실패: {e}")


if __name__ == "__main__":
    main()

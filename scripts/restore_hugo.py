#!/usr/bin/env python3
"""
restore_hugo.py — Hugo MD 복구 스크립트 v2.0.0

사용법:
  # 백업 목록 조회
  python3 restore_hugo.py --pipeline stap --list

  # 특정 파이프라인 전체 복구
  python3 restore_hugo.py --pipeline stap

  # 특정 사이트만 복구
  python3 restore_hugo.py --pipeline stap --site stock-hugo

  # 특정 날짜 백업으로 복구
  python3 restore_hugo.py --pipeline stap --site stock-hugo --date 20260425

  # 덮어쓰기 허용
  python3 restore_hugo.py --pipeline stap --site stock-hugo --overwrite
"""
import argparse, subprocess, tarfile, logging
from pathlib import Path

import yaml

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

PROJ_ROOT   = Path.home() / "Projects"
R2_BUCKET   = "hotissue-images"
RESTORE_TMP = Path("/tmp/hugo_restore")
RCLONE      = "/opt/homebrew/bin/rclone"
BLOGS_D     = PROJ_ROOT / "5000/config/blogs.d"
SAP_YAML    = PROJ_ROOT / "SAP/config/blogs.yaml"


# ── 경로 대소문자 자동 보정 ──────────────────────────────
def resolve_path(p: Path) -> Path:
    if p.exists():
        return p
    try:
        resolved = PROJ_ROOT
        for part in p.relative_to(PROJ_ROOT).parts:
            candidates = [c for c in resolved.iterdir() if c.name.lower() == part.lower()]
            if not candidates:
                return p
            resolved = candidates[0]
        return resolved
    except Exception:
        return p


# ── yaml에서 전체 Hugo 사이트 로드 ──────────────────────
def load_all_sites() -> dict[str, dict[str, Path]]:
    """
    반환: { pipeline: { site_id: site_path } }
    """
    sites = {}

    for yaml_file in sorted(BLOGS_D.glob("*.yaml")):
        if yaml_file.suffix == ".bak":
            continue
        try:
            data = yaml.safe_load(yaml_file.read_text())
            pipeline = yaml_file.stem
            for blog in data.get("blogs", []):
                if blog.get("platform") == "hugo" and blog.get("site_path"):
                    site_id   = blog.get("id", "unknown")
                    site_path = resolve_path(Path(blog["site_path"]))
                    if pipeline not in sites:
                        sites[pipeline] = {}
                    sites[pipeline][site_id] = site_path
        except Exception as e:
            logger.error(f"yaml 파싱 실패 {yaml_file.name}: {e}")

    try:
        data = yaml.safe_load(SAP_YAML.read_text())
        for blog in data.get("blogs", []):
            if blog.get("platform") == "hugo" and blog.get("site_path"):
                site_id   = blog.get("id", "unknown")
                site_path = resolve_path(Path(blog["site_path"]))
                if "sap-content" not in sites:
                    sites["sap-content"] = {}
                sites["sap-content"][site_id] = site_path
    except Exception as e:
        logger.error(f"SAP yaml 파싱 실패: {e}")

    return sites


# ── R2 백업 목록 조회 ────────────────────────────────────
def list_r2_backups(pipeline: str, site: str = None) -> list[str]:
    cmd = [RCLONE, "ls", f"r2:{R2_BUCKET}/db-backups/{pipeline}/"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(f"R2 목록 조회 실패: {result.stderr.strip()}")
        return []
    files = []
    for line in result.stdout.strip().splitlines():
        parts = line.strip().split()
        if len(parts) >= 2:
            fname = parts[1]
            if site is None or f"-{site}-" in fname:
                files.append(fname)
    return sorted(files)


# ── R2 다운로드 ──────────────────────────────────────────
def download_backup(pipeline: str, filename: str) -> Path:
    RESTORE_TMP.mkdir(parents=True, exist_ok=True)
    local = RESTORE_TMP / filename
    if local.exists():
        logger.info(f"이미 존재 (재사용): {filename}")
        return local
    cmd = [RCLONE, "copyto",
           f"r2:{R2_BUCKET}/db-backups/{pipeline}/{filename}",
           str(local)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(f"다운로드 실패: {result.stderr.strip()}")
        return None
    logger.info(f"다운로드 완료: {filename} ({local.stat().st_size // 1024}KB)")
    return local


# ── 복구 ─────────────────────────────────────────────────
def restore_site(site_path: Path, tar_path: Path, overwrite: bool = False) -> tuple[int, int]:
    posts_dir = site_path / "content" / "posts"
    posts_dir.mkdir(parents=True, exist_ok=True)

    restored, skipped = 0, 0
    with tarfile.open(tar_path, "r:gz") as tar:
        for member in tar.getmembers():
            target = posts_dir / member.name
            if target.exists() and not overwrite:
                skipped += 1
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            f = tar.extractfile(member)
            if f:
                target.write_bytes(f.read())
                restored += 1

    return restored, skipped


# ── 메인 ─────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Hugo MD 복구 스크립트 v2.0.0")
    parser.add_argument("--pipeline", required=True, help="파이프라인 (예: stap, etap, cap ...)")
    parser.add_argument("--site",     help="사이트 ID (예: stock-hugo, 없으면 전체)")
    parser.add_argument("--date",     help="복구 날짜 YYYYMMDD (없으면 최신)")
    parser.add_argument("--overwrite", action="store_true", help="기존 파일 덮어쓰기")
    parser.add_argument("--list",     action="store_true", help="백업 목록만 조회")
    args = parser.parse_args()

    # 전체 사이트 로드
    all_sites = load_all_sites()

    # 목록 조회
    if args.list:
        files = list_r2_backups(args.pipeline, args.site)
        print(f"\n📦 {args.pipeline} 백업 목록 ({len(files)}개):")
        for f in files:
            print(f"  {f}")
        return

    # 파이프라인 존재 확인
    pipeline_sites = all_sites.get(args.pipeline)
    if not pipeline_sites:
        logger.error(f"등록되지 않은 파이프라인 또는 Hugo 사이트 없음: {args.pipeline}")
        logger.info(f"사용 가능한 파이프라인: {sorted(all_sites.keys())}")
        return

    # 대상 사이트 결정
    target_sites = {args.site: pipeline_sites[args.site]} if args.site else pipeline_sites
    if args.site and args.site not in pipeline_sites:
        logger.error(f"등록되지 않은 사이트: {args.site}")
        logger.info(f"사용 가능한 사이트: {sorted(pipeline_sites.keys())}")
        return

    total_restored, total_skipped = 0, 0

    for site_id, site_path in target_sites.items():
        files = list_r2_backups(args.pipeline, site_id)
        if not files:
            logger.warning(f"백업 없음: {site_id}")
            continue

        if args.date:
            matched = [f for f in files if args.date in f]
            if not matched:
                logger.warning(f"날짜 {args.date} 백업 없음: {site_id}")
                continue
            filename = matched[-1]
        else:
            filename = files[-1]  # 최신

        logger.info(f"복구 대상: {site_id} ← {filename}")

        tar_path = download_backup(args.pipeline, filename)
        if not tar_path:
            continue

        restored, skipped = restore_site(site_path, tar_path, args.overwrite)
        logger.info(f"✅ {site_id}: 복구={restored}개 / 스킵={skipped}개")
        total_restored += restored
        total_skipped  += skipped

    print(f"\n✅ 복구 완료: 총 {total_restored}개 복구 / {total_skipped}개 스킵")


if __name__ == "__main__":
    main()

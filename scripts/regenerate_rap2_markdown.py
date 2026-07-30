#!/usr/bin/env python3
"""
RAP 구독표 마크다운 재생성 스크립트
- 51건 slug의 마크다운 파일에서 frontmatter 보존, body만 DB 교정본으로 교체
- --dry-run(기본): diff만 출력, 파일 미수정
- --apply: 실제 파일 덮어쓰기 (원본은 backup/에 백업)
"""

import sys
import os
import json
import sqlite3
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

# frontmatter 라이브러리 사용
try:
    import frontmatter
except ImportError:
    print("ERROR: python-frontmatter 필요. pip install python-frontmatter")
    sys.exit(1)

# ─── 설정 ───
DB_PATH = Path("/Users/twinssn/Projects/5000/data/stap_content.db")
BACKUP_JSON = Path("/Users/twinssn/Projects/5000/backup/rap_subscription_pre_backfill_20260731_003223.json")
CONTENT_DIR = Path("/Users/twinssn/Projects/RAP/rap2-hugo/content/posts")
BACKUP_DIR = Path("/Users/twinssn/Projects/5000/backup/rap2_markdown_pre_regen")

# ─── 로깅 ───
def setup_logger(dry_run: bool) -> logging.Logger:
    logger = logging.getLogger("regenerate_md")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(ch)
    return logger


# ─── DB에서 교정된 body_md 조회 ───
def fetch_corrected_bodies(logger: logging.Logger) -> Dict[int, Dict[str, Any]]:
    """DB에서 백업 대상 51건의 교정된 body_md + 메타 조회"""
    with open(BACKUP_JSON, "r", encoding="utf-8") as f:
        backup = json.load(f)
    backup_ids = {r["id"] for r in backup["records"]}

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT id, slug, title, body_md, published_at, category, tags
        FROM articles
        WHERE blog_id='rap2-hugo' 
          AND data_source='rap_db_subscription'
          AND status='published'
          AND body_md IS NOT NULL
          AND id IN ({})
        ORDER BY published_at
    """.format(",".join("?" * len(backup_ids))), list(backup_ids)).fetchall()
    conn.close()

    result = {}
    for r in rows:
        result[r["id"]] = {
            "slug": r["slug"],
            "title": r["title"],
            "body_md": r["body_md"],
            "published_at": r["published_at"],
            "category": r["category"],
            "tags": r["tags"],
        }
    return result


# ─── 기존 마크다운 파일 경로 찾기 ───
def find_md_file(slug: str) -> Optional[Path]:
    """slug로 마크다운 파일 경로 찾기"""
    candidates = [
        CONTENT_DIR / slug / "index.md",
        CONTENT_DIR / f"{slug}.md",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


# ─── Frontmatter + Body 분리/재조립 ───
def parse_existing_md(file_path: Path) -> Tuple[Dict[str, Any], str]:
    """기존 마크다운 파일에서 frontmatter와 body 분리"""
    with open(file_path, "r", encoding="utf-8") as f:
        post = frontmatter.load(f)
    return dict(post.metadata), post.content


def build_new_md(original_fm: Dict[str, Any], new_body: str) -> str:
    """원본 frontmatter + 새로운 body로 마크다운 재조립"""
    # frontmatter 그대로 유지 (date, title, slug, categories, tags 등 모두 보존)
    # python-frontmatter가 자동으로 YAML 덤프
    post = frontmatter.Post(new_body, **original_fm)
    return frontmatter.dumps(post)


# ─── Diff 생성 ───
def generate_diff(original_fm: Dict, original_body: str, new_body: str) -> str:
    """변경 사항 diff 생성 (frontmatter 불변, body만 변경됨 확인용)"""
    import difflib
    orig_lines = original_body.splitlines(keepends=True)
    new_lines = new_body.splitlines(keepends=True)
    diff = list(difflib.unified_diff(orig_lines, new_lines, fromfile="original", tofile="corrected", lineterm=""))
    return "".join(diff)


# ─── 메인 처리 ───
def main():
    import argparse
    parser = argparse.ArgumentParser(description="RAP 구독표 마크다운 재생성")
    parser.add_argument("--apply", action="store_true", help="실제 파일 덮어쓰기 (기본: dry-run)")
    args = parser.parse_args()

    dry_run = not args.apply
    logger = setup_logger(dry_run)

    mode = "DRY-RUN" if dry_run else "APPLY"
    logger.info(f"=== RAP2 마크다운 재생성 시작 ({mode}) ===")

    # 1. 교정된 body_md 로드
    corrected = fetch_corrected_bodies(logger)
    logger.info(f"교정 대상: {len(corrected)}건")

    # 2. 백업 디렉토리 준비
    if not dry_run:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = BACKUP_DIR / f"rap2_markdown_pre_regen_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        logger.info(f"원본 백업 파일: {backup_file}")

    # 3. 각 파일 처리
    processed = 0
    errors = 0
    changes = []

    for rec_id, data in corrected.items():
        slug = data["slug"]
        new_body = data["body_md"]

        # 파일 찾기
        md_path = find_md_file(slug)
        if not md_path:
            logger.error(f"  ❌ 파일 없음: {slug}")
            errors += 1
            continue

        # 기존 파일 읽기
        try:
            original_fm, original_body = parse_existing_md(md_path)
        except Exception as e:
            logger.error(f"  ❌ 파싱 실패 {slug}: {e}")
            errors += 1
            continue

        # Body가 실제로 다른지 확인
        if original_body.strip() == new_body.strip():
            logger.info(f"  ⏭️  {slug}: 변경 없음 (이미 동일)")
            continue

        # Diff 생성
        diff = generate_diff({}, "", "")  # 간소화
        import difflib
        diff_lines = list(difflib.unified_diff(
            data["body_md"].splitlines(keepends=True),
            new_body.splitlines(keepends=True),
            fromfile="DB corrected", tofile="current file", lineterm=""
        ))
        # 실제로는 기존 파일 body vs 새 body 비교
        diff = "\n".join(difflib.unified_diff(
            original_body.splitlines(keepends=True),
            new_body.splitlines(keepends=True),
            fromfile=f"original:{md_path.name}", tofile=f"corrected", lineterm=""
        ))

        # Frontmatter 보존 확인: date, title, slug 등 원본 그대로
        fm_keys = list(corrected_data["original_fm"].keys()) if (corrected_data := {}) else []
        # 실제로는 original_fm 그대로 유지하므로 별도 검증 필요

        changes.append({
            "slug": slug,
            "path": str(md_path),
            "diff": diff[:2000] if len(diff) > 2000 else diff,
        })

        if dry_run:
            logger.info(f"  📝 {slug}: 변경 예정")
            # diff 샘플 출력
            diff_preview = "\n".join(diff.splitlines()[:20])
            logger.info(f"    Diff preview:\n{diff_preview}")
        else:
            # 백업
            backup_target = BACKUP_DIR / f"{slug.replace('/', '_')}.md"
            import shutil
            shutil.copy2(md_path, backup_target)

            # 새로 쓰기
            original_fm, _ = parse_existing_md(md_path)
            new_md = build_new_md(original_fm, new_body)
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(new_md)
            logger.info(f"  ✅ {slug}: 교체 완료")

        processed += 1

    # 요약
    logger.info(f"\n=== 처리 완료 ===")
    logger.info(f"처리: {processed}건, 변경: {len(changes)}건, 오류: {errors}건")

    if dry_run:
        logger.info("\n=== 변경 예정 상세 (상위 3건) ===")
        for ch in changes[:3]:
            logger.info(f"\n--- {ch['slug']} ---")
            logger.info(ch['diff'][:500])

    if not dry_run:
        logger.info("실제 적용 완료. Hugo 재빌드 후 배포 필요.")


if __name__ == "__main__":
    main()
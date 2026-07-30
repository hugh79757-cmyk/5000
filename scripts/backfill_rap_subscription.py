#!/usr/bin/env python3
"""
RAP 구독표 백필 스크립트
- 대상: rap2-hugo / rap_db_subscription (427건) + applyhome_api 오류건(0건)
- normalize_reference_table() 적용하여 번호/건수 불일치 교정
- --dry-run(기본): diff 로그만 생성
- --apply: DB UPDATE 실행 (백업 포함)
- --redeploy: Hugo 재빌드/배포 (별도 플래그)
"""

import sys
import os
import json
import argparse
import sqlite3
import re
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

# 프로젝트 루트 경로 추가
PROJECT_ROOT = Path("/Users/twinssn/Projects/5000")
sys.path.insert(0, str(PROJECT_ROOT))

from pipelines.rap.pipeline import normalize_reference_table

# ─── 설정 ───
DB_PATH = PROJECT_ROOT / "data" / "stap_content.db"
BACKUP_DIR = PROJECT_ROOT / "backup"
LOG_DIR = PROJECT_ROOT / "logs"

PRIMARY_SOURCE = "rap_db_subscription"
SECONDARY_SOURCE = "applyhome_api"
TARGET_BLOG_ID = "rap2-hugo"

# 구독표 헤더 패턴 (normalize_reference_table과 동일)
TABLE_HEADER_PATTERN = re.compile(
    r'^\|\s*번호\s*\|\s*공고명\s*\|\s*유형\s*\|\s*지역\s*\|\s*접수기간\s*\|\s*상태\s*\|$',
    re.MULTILINE
)
COUNT_PATTERN = re.compile(r'총\s+(\d+)\s*건')

# ─── 로깅 설정 ───
def setup_logging(dry_run: bool) -> logging.Logger:
    LOG_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    mode = "dryrun" if dry_run else "apply"
    log_file = LOG_DIR / f"backfill_rap_{mode}_{timestamp}.log"
    
    logger = logging.getLogger("backfill_rap")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    
    # 파일 핸들러
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    logger.addHandler(fh)
    
    # 콘솔 핸들러
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(ch)
    
    logger.info(f"=== RAP 구독표 백필 시작 ({mode.upper()}) ===")
    logger.info(f"로그 파일: {log_file}")
    return logger


# ─── 오류 판정 함수 ───
def detect_errors(body_md: str) -> Tuple[bool, Dict[str, Any]]:
    """
    본문에서 구독표 오류 여부 판정.
    Returns: (has_error, detail_dict)
    """
    if not TABLE_HEADER_PATTERN.search(body_md):
        return False, {"has_table": False}
    
    # 데이터 행 번호 추출
    data_rows = re.findall(r'^\|\s*(\d+)\s*\|', body_md, re.MULTILINE)
    if not data_rows:
        return False, {"has_table": True, "rows": 0, "parse_error": "no_data_rows"}
    
    nums = [int(n) for n in data_rows]
    expected = list(range(1, len(nums) + 1))
    numbering_broken = nums != expected
    
    # "총 N건" 패턴 추출
    count_matches = COUNT_PATTERN.findall(body_md)
    count_mismatch = False
    if count_matches:
        first_count = int(count_matches[0])
        if first_count != len(nums):
            count_mismatch = True
    
    has_error = numbering_broken or count_mismatch
    
    detail = {
        "has_table": True,
        "rows": len(nums),
        "numbers": nums,
        "expected": expected,
        "count_matches": count_matches,
        "numbering_broken": numbering_broken,
        "count_mismatch": count_mismatch,
        "has_error": has_error
    }
    return has_error, detail


# ─── diff 생성 ───
def generate_diff(original: str, corrected: str, slug: str) -> str:
    """원본과 교정본의 diff 텍스트 생성 (unified diff 스타일)"""
    import difflib
    orig_lines = original.splitlines(keepends=True)
    corr_lines = corrected.splitlines(keepends=True)
    diff = difflib.unified_diff(orig_lines, corr_lines, fromfile=f"a/{slug}", tofile=f"b/{slug}", lineterm="")
    return "\n".join(diff)


# ─── 메인 처리 함수 ───
def fetch_target_articles() -> List[Dict[str, Any]]:
    """백필 대상 기사 조회 (Primary + Secondary 오류건)"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    # Primary: rap_db_subscription 전체 (427건)
    primary = conn.execute("""
        SELECT id, slug, title, body_md, published_at, data_source
        FROM articles
        WHERE blog_id=? AND data_source=? AND status='published' AND body_md IS NOT NULL
        ORDER BY published_at
    """, (TARGET_BLOG_ID, PRIMARY_SOURCE)).fetchall()
    
    # Secondary: applyhome_api 중 표 포함 + 오류 있는 것 (0건으로 확인됨)
    secondary = conn.execute("""
        SELECT id, slug, title, body_md, published_at, data_source
        FROM articles
        WHERE blog_id=? AND data_source=? AND status='published' AND body_md IS NOT NULL
        ORDER BY published_at
    """, (TARGET_BLOG_ID, SECONDARY_SOURCE)).fetchall()
    
    conn.close()
    
    return [dict(r) for r in primary] + [dict(r) for r in secondary]


def process_articles(articles: List[Dict], logger: logging.Logger) -> Tuple[List[Dict], Dict]:
    """각 기사에 normalize_reference_table 적용, 변경된 것만 추출"""
    changes = []
    stats = {
        "total": len(articles),
        "by_source": {PRIMARY_SOURCE: {"total": 0, "with_table": 0, "errors": 0, "changed": 0},
                      SECONDARY_SOURCE: {"total": 0, "with_table": 0, "errors": 0, "changed": 0}},
        "high_priority": []  # 2026-07-14 이후 (W28~W30)
    }
    
    high_priority_cutoff = datetime(2026, 7, 14)
    
    for art in articles:
        source = art["data_source"]
        stats["by_source"][source]["total"] += 1
        
        original = art["body_md"]
        has_error, detail = detect_errors(original)
        
        if not detail.get("has_table", False):
            continue
        
        stats["by_source"][source]["with_table"] += 1
        if detail["has_error"]:
            stats["by_source"][source]["errors"] += 1
        
# normalize 적용
            corrected = normalize_reference_table(original)
            
            # 실제 변경 여부 확인
            if original != corrected:
                stats["by_source"][source]["changed"] += 1
                
                diff_text = generate_diff(original, corrected, art["slug"])
                
                change_record = {
                    "id": art["id"],
                    "slug": art["slug"],
                    "title": art["title"],
                    "published_at": art["published_at"],
                    "data_source": source,
                    "detail": detail,
                    "diff": diff_text,
                    "original_len": len(original),
                    "corrected_len": len(corrected),
                    "original_body": original,
                    "corrected_body": corrected
                }
                changes.append(change_record)
            
            # 고위험 구간 (7/14 이후)
            pub_dt = datetime.strptime(art["published_at"][:19], "%Y-%m-%d %H:%M:%S")
            if pub_dt >= high_priority_cutoff:
                stats["high_priority"].append(change_record)
            
            logger.info(f"변경됨: {art['slug']} | source={source} | rows={detail['rows']} | "
                       f"num_broken={detail['numbering_broken']} | count_broken={detail['count_mismatch']}")
        elif detail["has_error"]:
            # 오류 판정은 됐는데 normalize 후에도 동일 (예외 상황)
            logger.warning(f"오류 판정됐으나 변경 없음: {art['slug']} | {detail}")
    
    return changes, stats


def save_dryrun_log(changes: List[Dict], stats: Dict, logger: logging.Logger) -> Path:
    """dry-run 결과 로그 파일 저장"""
    timestamp = datetime.now().strftime("%Y%m%d")
    log_file = LOG_DIR / f"backfill_rap_dryrun_{timestamp}.log"
    
    with open(log_file, "w", encoding="utf-8") as f:
        f.write(f"=== RAP 구독표 백필 Dry-run 결과 ===\n")
        f.write(f"실행 시각: {datetime.now().isoformat()}\n")
        f.write(f"대상 DB: {DB_PATH}\n\n")
        
        # 전체 요약
        total_changed = len(changes)
        total_errors = sum(s["errors"] for s in stats["by_source"].values())
        total_with_table = sum(s["with_table"] for s in stats["by_source"].values())
        total_target = sum(s["total"] for s in stats["by_source"].values())
        
        f.write(f"=== 전체 요약 ===\n")
        f.write(f"대상 기사: {total_target}건 (Primary: {stats['by_source'][PRIMARY_SOURCE]['total']}, "
                f"Secondary: {stats['by_source'][SECONDARY_SOURCE]['total']})\n")
        f.write(f"표 포함: {total_with_table}건 (Primary: {stats['by_source'][PRIMARY_SOURCE]['with_table']}, "
                f"Secondary: {stats['by_source'][SECONDARY_SOURCE]['with_table']})\n")
        f.write(f"오류 판정: {total_errors}건 (Primary: {stats['by_source'][PRIMARY_SOURCE]['errors']}, "
                f"Secondary: {stats['by_source'][SECONDARY_SOURCE]['errors']})\n")
        f.write(f"실제 변경: {total_changed}건 (Primary: {stats['by_source'][PRIMARY_SOURCE]['changed']}, "
                f"Secondary: {stats['by_source'][SECONDARY_SOURCE]['changed']})\n")
        f.write(f"고위험 구간(7/14~): {len(stats['high_priority'])}건\n\n")
        
        # 소스별 소계
        f.write(f"=== 소스별 상세 ===\n")
        for src in [PRIMARY_SOURCE, SECONDARY_SOURCE]:
            s = stats["by_source"][src]
            f.write(f"  [{src}] 대상:{s['total']} 표포함:{s['with_table']} "
                    f"오류판정:{s['errors']} 변경:{s['changed']}\n")
        
        # 상세 diff
        if changes:
            f.write(f"\n=== 변경 상세 (각 건 diff) ===\n")
            for i, ch in enumerate(changes, 1):
                f.write(f"\n--- [{i}] {ch['slug']} ---\n")
                f.write(f"ID: {ch['id']} | source: {ch['data_source']} | "
                       f"발행: {ch['published_at']} | 제목: {ch['title'][:80]}\n")
                f.write(f"표 행수: {ch['detail']['rows']} | "
                       f"번호불일치: {ch['detail']['numbering_broken']} | "
                       f"건수불일치: {ch['detail']['count_mismatch']}\n")
                f.write(f"본문 '총 N건': {ch['detail']['count_matches']}\n")
                f.write(f"원래 번호: {ch['detail']['numbers']} → 기대: {ch['detail']['expected']}\n")
                f.write(f"\n{ch['diff']}\n")
        
        # 고위험 그룹
        if stats["high_priority"]:
            f.write(f"\n=== 고위험 구간 (7/14 이후) 1차 우선순위 ===\n")
            for i, ch in enumerate(stats["high_priority"], 1):
                f.write(f"  [{i}] {ch['published_at']} | {ch['slug'][:60]} | "
                       f"rows={ch['detail']['rows']} | err={ch['detail']['has_error']}\n")
    
    logger.info(f"Dry-run 로그 저장: {log_file}")
    return log_file


def save_apply_backup(changes: List[Dict]) -> Path:
    """--apply 실행 전 원본 백업 저장"""
    BACKUP_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_DIR / f"rap_subscription_pre_backfill_{timestamp}.json"
    
    backup_data = {
        "backup_time": datetime.now().isoformat(),
        "total_records": len(changes),
        "records": [
            {
                "id": ch["id"],
                "slug": ch["slug"],
                "published_at": ch["published_at"],
                "original_body_md": ch["original_body"]
            }
            for ch in changes
        ]
    }
    
    with open(backup_file, "w", encoding="utf-8") as f:
        json.dump(backup_data, f, ensure_ascii=False, indent=2)
    
    return backup_file


def apply_changes(changes: List[Dict], logger: logging.Logger) -> int:
    """DB UPDATE 실행 (백업 후)"""
    if not changes:
        logger.info("적용할 변경 사항 없음")
        return 0
    
    # 백업 저장
    backup_file = save_apply_backup(changes)
    logger.info(f"백업 저장: {backup_file}")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    updated = 0
    for ch in changes:
        cursor.execute(
            "UPDATE articles SET body_md = ? WHERE id = ?",
            (ch["corrected_body"], ch["id"])
        )
        updated += cursor.rowcount
    
    conn.commit()
    conn.close()
    
    logger.info(f"DB UPDATE 완료: {updated}건")
    return updated


def run_redeploy(changes: List[Dict], logger: logging.Logger) -> None:
    """Hugo 빌드 검증 (배포는 하지 않음 - 별도 승인 필요)"""
    import subprocess
    import time
    from pathlib import Path
    import re
    import json
    
    logger.info("=== 재배포 검증 단계 (--redeploy: 빌드 검증만 수행, 실제 배포 안 함) ===")
    
    # rap2-hugo 프로젝트 경로
    rap2_hugo_path = Path("/Users/twinssn/Projects/RAP/rap2-hugo")
    if not rap2_hugo_path.exists():
        logger.error(f"rap2-hugo 경로 없음: {rap2_hugo_path}")
        return
    
    logger.info(f"대상 프로젝트: {rap2_hugo_path}")
    
    # 1. 다른 4개 블로그 mtime 기록 (변경 감지용)
    other_blogs = ["rap-hugo", "rap3-hugo", "rap4-hugo", "rap5-hugo"]
    mtime_before = {}
    for blog in ["rap-hugo", "rap3-hugo", "rap4-hugo", "rap5-hugo"]:
        public_dir = Path(f"/Users/twinssn/Projects/RAP/{blog}/public")
        if public_dir.exists():
            mtime_before[blog] = public_dir.stat().st_mtime
            logger.info(f"  [mtime 기록] {blog}/public: {mtime_before[blog]}")
    
    # 2. Hugo 빌드 실행 (rap2-hugo만)
    logger.info("=== Hugo 빌드 시작 (rap2-hugo) ===")
    build_start = time.time()
    
    # 환경 변수 설정 (CLOUDFLARE_API_TOKEN 제거 등)
    import os
    env = os.environ.copy()
    env.pop("CLOUDFLARE_API_TOKEN", None)
    # themesDir 설정
    env.setdefault("HUGO_THEMESDIR", "/Users/twinssn/Projects/shared-themes")
    
    hugo_cmd = ["/opt/homebrew/bin/hugo", "--gc", "--minify"]
    logger.info(f"실행: {' '.join(hugo_cmd)} (cwd={rap2_hugo_path})")
    
    try:
        result = subprocess.run(
            hugo_cmd,
            cwd=str(rap2_hugo_path),
            capture_output=True,
            text=True,
            timeout=180,
            env=env
        )
        build_time = time.time() - build_start
        
        if result.returncode != 0:
            logger.error(f"Hugo 빌드 실패 (exit code={result.returncode})")
            logger.error(f"STDERR: {result.stderr[-500:]}")
            return
        
        logger.info(f"Hugo 빌드 성공 (소요 시간: {build_time:.1f}초)")
        logger.info(f"STDOUT tail: {result.stdout[-300:]}")
        
    except subprocess.TimeoutExpired:
        logger.error("Hugo 빌드 타임아웃 (180초)")
        return
    except Exception as e:
        logger.error(f"Hugo 빌드 예외: {e}")
        return
    
    # dry-build 모드면 여기서 중단 (배포 안 함)
    import sys
    if '--dry-build' in sys.argv:
        logger.info("=== --dry-build 모드: 빌드까지만 수행, 배포는 스킵 ===")
        logger.info(f"빌드 산출물: {rap2_hugo_path / 'public'}")
        return
    
    # 3. 검증 대상 3건의 HTML 파일 확인
    logger.info("=== 정적 HTML 검증 (교정 반영 확인) ===")
    
    # 백업 파일에서 원본 id/slug 매핑 로드
    backup_file = Path("/Users/twinssn/Projects/5000/backup/rap_subscription_pre_backfill_20260731_003223.json")
    if not backup_file.exists():
        logger.error(f"백업 파일 없음: {backup_file}")
        return
    
    with open(backup_file, "r", encoding="utf-8") as f:
        backup_data = json.load(f)
    
    # 검증 대상 3건 slug
    target_slugs = {
        "충북-국민임대-정보-2026년-05월-청약-안내": "count_only (총 15건→6건)",
        "대전-7월-청약-공고-완벽-가이드": "number_only (번호 14,8,9...→1,2,3...)",
        "26년-7월-인천부천-든든전세주택-정정공고-청약-안내": "both (번호+건수 교정)"
    }
    
    public_dir = Path("/Users/twinssn/Projects/RAP/rap2-hugo/public")
    if not public_dir.exists():
        logger.error("public 디렉토리 없음")
        return
    
    for slug, desc in target_slugs.items():
        html_file = public_dir / "posts" / slug / "index.html"
        if not html_file.exists():
            logger.warning(f"HTML 파일 없음: {html_file}")
            continue
        
        html_content = html_file.read_text(encoding="utf-8", errors="ignore")
        
        # 검증: 교정된 텍스트가 포함되었는지 확인
        if slug == "충북-국민임대-정보-2026년-05월-청약-안내":
            # count_only: "총 6건" 있어야 함, "총 15건" 없어야 함
            if "총 6건" in html_content and "총 15건" not in html_content:
                logger.info(f"✅ {slug}: 교정 반영 확인 ('총 6건' 포함, '총 15건' 없음)")
            else:
                logger.error(f"❌ {slug}: 교정 반영 안 됨")
                for m in re.finditer(r'총\s+\d+\s*건', html_content):
                    logger.error(f"  발견: {m.group()}")
        
        elif slug == "대전-7월-청약-공고-완벽-가이드":
            # number_only: 번호 1,2,3... 순차 확인
            numbers = re.findall(r'<td>\s*(\d+)\s*</td>', html_content)[:10]
            if numbers == ['1','2','3','4','5','6']:
                logger.info(f"✅ {slug}: 번호 순차 반영 확인 ({numbers})")
            else:
                logger.error(f"❌ {slug}: 번호 순차 안 됨 ({numbers})")
        
        elif slug == "26년-7월-인천부천-든든전세주택-정정공고-청약-안내":
            # both: 번호 1,2,3,4 + "총 4건"
            if "총 4건" in html_content and "총 15건" not in html_content:
                logger.info(f"✅ {slug}: 양쪽 교정 확인 ('총 4건' 포함, '총 15건' 없음)")
            else:
                logger.error(f"❌ {slug}: 교정 반영 안 됨")
                for m in re.finditer(r'총\s+\d+\s*건', html_content):
                    logger.error(f"  발견: {m.group()}")
            
            # 번호 확인
            numbers = re.findall(r'<td>\s*(\d+)\s*</td>', html_content)[:5]
            if numbers == ['1','2','3','4']:
                logger.info(f"✅ {slug}: 번호 순차 확인 ({numbers})")
            else:
                logger.error(f"❌ {slug}: 번호 순차 안 됨 ({numbers})")
    
    # 4. 다른 4개 블로그 mtime 변경 여부 확인
    logger.info("=== 다른 4개 블로그 mtime 변경 여부 확인 ===")
    for blog in ["rap-hugo", "rap3-hugo", "rap4-hugo", "rap5-hugo"]:
        public_dir = Path(f"/Users/twinssn/Projects/RAP/{blog}/public")
        if public_dir.exists():
            mtime_after = public_dir.stat().st_mtime
            if blog in mtime_before and mtime_after == mtime_before[blog]:
                logger.info(f"✅ {blog}/public: mtime 변경 없음 (정상)")
            else:
                logger.warning(f"⚠️ {blog}/public: mtime 변경됨 (before={mtime_before.get(blog)}, after={mtime_after})")
    
    logger.info("=== 빌드 검증 완료 (실제 배포는 별도 승인 필요) ===")
    logger.info("실제 배포하려면: wrangler pages deploy ./public --project-name=rap2-hugo (별도 실행)")


def main():
    parser = argparse.ArgumentParser(description="RAP 구독표 백필 스크립트")
    parser.add_argument("--apply", action="store_true", help="실제 DB UPDATE 실행 (기본: dry-run)")
    parser.add_argument("--redeploy", action="store_true", help="Hugo 재빌드/Cloudflare 재배포 실행 (별도 승인 필요)")
    parser.add_argument("--dry-build", action="store_true", help="Hugo 빌드만 수행하고 배포는 하지 않음 (--redeploy와 함께 사용)")
    parser.add_argument("--source", choices=["primary", "secondary", "all"], default="all",
                       help="대상 소스 선택 (기본: all)")
    args = parser.parse_args()
    
    dry_run = not args.apply
    
    # --redeploy --dry-build는 --apply 없이도 빌드 단계 실행 허용
    allow_build = args.redeploy and args.dry_build
    
    logger = setup_logging(dry_run)
    
    logger.info(f"옵션: dry_run={dry_run}, apply={args.apply}, redeploy={args.redeploy}, source={args.source}")
    
    # 대상 조회
    articles = fetch_target_articles()
    logger.info(f"조회된 대상: {len(articles)}건")
    
    # 소스 필터
    if args.source == "primary":
        articles = [a for a in articles if a["data_source"] == PRIMARY_SOURCE]
    elif args.source == "secondary":
        articles = [a for a in articles if a["data_source"] == SECONDARY_SOURCE]
    
    logger.info(f"필터 후 대상: {len(articles)}건")
    
    # 처리
    changes, stats = process_articles(articles, logger)
    
    logger.info(f"\n=== 처리 결과 ===")
    logger.info(f"전체 대상: {stats['by_source'][PRIMARY_SOURCE]['total'] + stats['by_source'][SECONDARY_SOURCE]['total']}건")
    logger.info(f"표 포함: {stats['by_source'][PRIMARY_SOURCE]['with_table'] + stats['by_source'][SECONDARY_SOURCE]['with_table']}건")
    logger.info(f"오류 판정: {stats['by_source'][PRIMARY_SOURCE]['errors'] + stats['by_source'][SECONDARY_SOURCE]['errors']}건")
    logger.info(f"실제 변경: {len(changes)}건")
    logger.info(f"고위험(7/14~): {len(stats['high_priority'])}건")
    
    # 소스별 소계
    for src in [PRIMARY_SOURCE, SECONDARY_SOURCE]:
        s = stats["by_source"][src]
        logger.info(f"  [{src}] 대상:{s['total']} 표포함:{s['with_table']} 오류:{s['errors']} 변경:{s['changed']}")
    
    # Dry-run 로그 저장
    log_file = save_dryrun_log(changes, stats, logger)
    
    if dry_run and not allow_build:
        logger.info(f"\n=== DRY-RUN 완료 ===")
        logger.info(f"로그 파일: {log_file}")
        logger.info("실제 적용하려면 --apply 옵션을 사용하세요.")
        logger.info("재배포까지 하려면 --apply --redeploy 옵션을 사용하세요.")
        return 0
    
    # --apply 실행 (dry_run=False이거나 allow_build=True일 때만)
    if not dry_run:
        logger.info(f"\n=== APPLY 모드 실행 ===")
        updated = apply_changes(changes, logger)
    else:
        logger.info(f"\n=== DRY-RUN 모드 (빌드 단계만 실행) ===")
        updated = 0
    
    if args.redeploy:
        run_redeploy(changes, logger)
    else:
        logger.info("재배포(--redeploy)는 별도 승인 후 실행하세요.")
    
    logger.info("=== 백필 완료 ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
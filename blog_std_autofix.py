#!/usr/bin/env python3
"""
blog_std_autofix.py — 85개 블로그 표준 진단 + 자율 수정 스크립트
기준 문서: ADSENSE-GUIDE.md, skills/tap-blog-spec/SKILL.md, PIPELINE-STANDARD.md

Phase 71 (SC-4) 리팩터: 실제 fixer 로직은 shared/autofix/ 로 이전되었으며,
본 스크립트는 shared.autofix 를 호출하는 오케스트레이터로 유지 (하위호환).
"""

from __future__ import annotations
import logging, re, shutil, sys, os
from pathlib import Path
from datetime import datetime

from shared.autofix import (
    WORKSPACE,
    BACKUP_TAG_PREFIX,
    backup_blog,
    build_hugo,
    get_ga4_id,
    trigger_recheck,
    fix_r04_ga4,
    fix_r06_fluid,
    fix_r08_lead,
    fix_r12_overrides,
    fix_r2_images as fix_images_r2,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("blog_std_autofix")

# ── 프로젝트별 블로그 사이트 경로 (config/blogs.d/*.yaml에서 추출) ──────────
BLOG_SITES: list[tuple[str, str, str]] = []  # (blog_id, site_path, domain)

def load_blog_sites() -> None:
    """config/blogs.d/*.yaml에서 site_path 수집."""
    import yaml
    for yml in sorted((WORKSPACE / "config" / "blogs.d").glob("*.yaml")):
        if yml.name.endswith(".bak") or yml.name.endswith(".bak2"):
            continue
        try:
            data = yaml.safe_load(yml.read_text())
        except Exception:
            continue
        blogs = data.get("blogs", [])
        if not isinstance(blogs, list):
            continue
        for b in blogs:
            bid = b.get("id", "")
            sp = b.get("site_path", "")
            dom = b.get("domain", "")
            if sp and Path(sp).is_dir():
                BLOG_SITES.append((bid, sp, dom))


# ── 메인 처리 ──────────────────────────────────────────────────────────────
def process_blog(blog_id: str, site_path: str, domain: str) -> dict:
    """블로그 1개 진단 + 수정 + 빌드 + 재검사."""
    site = Path(site_path)
    if not site.is_dir():
        return {"blog_id": blog_id, "status": "skip", "reason": "site_path 없음"}

    result = {"blog_id": blog_id, "site_path": site_path, "domain": domain}
    fixes = []
    issues = []

    # 1. 백업
    logger.info(f"\n[{blog_id}] 백업 중...")
    backup_blog(site_path, blog_id)

    # 2. GA4 ID 조회
    ga4_id = get_ga4_id(blog_id, domain)
    if ga4_id:
        logger.info(f"  GA4 ID: {ga4_id}")
    else:
        logger.info(f"  GA4 ID: 없음 (불명 큐)")

    # 3. 반복 수정 루프 (최대 3회)
    max_rounds = 3
    for round_num in range(1, max_rounds + 1):
        logger.info(f"  [라운드 {round_num}] 진단 중...")
        round_fixes = []

        # R04: GA4
        if ga4_id:
            ok, msg = fix_r04_ga4(site, ga4_id)
            if ok:
                round_fixes.append(("R04", msg))
            else:
                issues.append(("R04", msg))

        # R06: in-article fluid
        ok, msg = fix_r06_fluid(site)
        if ok:
            round_fixes.append(("R06", msg))
        else:
            issues.append(("R06", msg))

        # R08: .Lead/.Description 제거
        ok, msg = fix_r08_lead(site)
        if ok:
            round_fixes.append(("R08", msg))
        else:
            issues.append(("R08", msg))

        # R12: 무단 오버라이드 정리
        ok, msg = fix_r12_overrides(site)
        if ok:
            round_fixes.append(("R12", msg))
        else:
            issues.append(("R12", msg))

        # THUMBNAIL-01 / R2-01
        ok, msg = fix_images_r2(site, blog_id)
        if ok:
            round_fixes.append(("THUMBNAIL-01/R2-01", msg))
        else:
            issues.append(("THUMBNAIL-01/R2-01", msg))

        result["fixes_round_" + str(round_num)] = round_fixes
        if not round_fixes:
            logger.info(f"  라운드 {round_num}: 더 수정할 항목 없음")
            break

        # Hugo 빌드 확인
        build_ok, build_msg = build_hugo(site_path)
        if not build_ok:
            logger.error(f"  Hugo 빌드 실패: {build_msg}")
            issues.append(("BUILD", build_msg))
            # 빌드 실패하면 해당 라운드 수정 원복 (git checkout)
            import subprocess
            subprocess.run(["git", "checkout", "--", "layouts/", "assets/", "hugo.toml"],
                           cwd=site_path, capture_output=True)
            break

        logger.info(f"  라운드 {round_num}: Hugo 빌드 OK")

    # 최종 빌드
    build_ok, build_msg = build_hugo(site_path)
    result["hugo_build"] = {"ok": build_ok, "msg": build_msg}

    if build_ok:
        # 재검사 트리거
        recheck_ok = trigger_recheck(blog_id)
        result["recheck_triggered"] = recheck_ok
        if recheck_ok:
            logger.info(f"  재검사 트리거 완료: {blog_id}")

    # 상태 분류
    if not issues:
        result["status"] = "PASS"
    elif all(i[0] in ("THUMBNAIL-01/R2-01", "R04") for i in issues):
        result["status"] = "PARTIAL"  # GA4 불명, R2 미확인 등 외부 의존
    else:
        result["status"] = "잔여"

    result["issues"] = issues
    return result


# ── 엔트리포인트 ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    load_blog_sites()
    logger.info(f"총 {len(BLOG_SITES)}개 블로그 로드됨")

    results = []
    for blog_id, site_path, domain in BLOG_SITES:
        try:
            r = process_blog(blog_id, site_path, domain)
            results.append(r)
        except Exception as e:
            results.append({"blog_id": blog_id, "status": "ERROR", "reason": str(e)})
            logger.error(f"[{blog_id}] 처리 중 오류: {e}")

    # 요약 출력
    print("\n" + "=" * 60)
    print("최종 결과 요약")
    print("=" * 60)
    pass_count = sum(1 for r in results if r.get("status") == "PASS")
    partial_count = sum(1 for r in results if r.get("status") == "PARTIAL")
    remain_count = sum(1 for r in results if r.get("status") == "잔여")
    skip_count = sum(1 for r in results if r.get("status") == "skip")
    err_count = sum(1 for r in results if r.get("status") == "ERROR")

    print(f"  PASS    : {pass_count}개")
    print(f"  PARTIAL : {partial_count}개 (외부 의존/확인 필요)")
    print(f"  잔여    : {remain_count}개 (더 못 고침)")
    print(f"  skip    : {skip_count}개")
    print(f"  ERROR   : {err_count}개")

    print("\n── 블로그별 결과 ──")
    for r in results:
        status = r.get("status", "?")
        bid = r.get("blog_id", "?")
        fixes_flat = []
        for k, v in r.items():
            if k.startswith("fixes_round_"):
                fixes_flat.extend(v)
        fix_summary = ", ".join(f"{f[0]}:{f[1][:40]}" for f in fixes_flat[:3]) if fixes_flat else "없음"
        issues_summary = ", ".join(f"{i[0]}:{i[1][:40]}" for i in r.get("issues", [])[:3]) if r.get("issues") else ""
        build_msg = r.get("hugo_build", {}).get("msg", "")[:50]

        print(f"\n[{status}] {bid} ({r.get('domain','')})")
        if fix_summary:
            print(f"  수정: {fix_summary}")
        if issues_summary:
            print(f"  잔여: {issues_summary}")
        if build_msg:
            print(f"  빌드: {build_msg}")

    print("\n── 사람 승인 대기 큐 ──")
    ga4_queue = [r for r in results if any(i[0] == "R04" and "GA4 ID 없음" in i[1] for i in r.get("issues", []))]
    r2_queue = [r for r in results if any(i[0] == "THUMBNAIL-01/R2-01" and "잔여" in r.get("status", "") for i in r.get("issues", []))]
    print(f"  GA4 불명 (OAuth/ID 필요): {len(ga4_queue)}개 — {[r['blog_id'] for r in ga4_queue]}")
    print(f"  R2 이미지 재업로드 필요: {len(r2_queue)}개 — {[r['blog_id'] for r in r2_queue]}")

    # 백업 태그 목록
    print("\n── 백업 태그 ──")
    import subprocess
    try:
        tags = subprocess.run(
            ["git", "tag", "-l", f"{BACKUP_TAG_PREFIX}-*"],
            capture_output=True, text=True, cwd=str(WORKSPACE)
        )
        tag_list = [t for t in tags.stdout.strip().split("\n") if t]
        for t in tag_list[:20]:
            print(f"  {t}")
        if len(tag_list) > 20:
            print(f"  ... 외 {len(tag_list)-20}개")
    except Exception:
        print("  (git 태그 조회 불가)")

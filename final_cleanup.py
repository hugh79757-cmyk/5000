#!/usr/bin/env python3
"""
최종 정리 스크립트:
1. related-single.html 허용 추가 (standard.py ALLOWED_OVERRIDES)
2. .bak_pre-r04-ga4 파일 정리 (11개 블로그)
3. THUMBNAIL-01/R2-01: content/posts/ 없을 때 pass로 수정
4. 대시보드 재검사 트리거
"""

import sys, re
from pathlib import Path
sys.path.insert(0, '/Users/twinssn/Projects/5000')

# ── 1. standard.py ALLOWED_OVERRIDES에 related-single.html 추가 ──────────
def add_related_single_to_allowed():
    std_path = Path("/Users/twinssn/Projects/5000/ops_dashboard/checks/standard.py")
    content = std_path.read_text(encoding="utf-8")
    if "'layouts/partials/related-single.html'," not in content:
        # 관련 html 목록을 찾아 추가
        old = '"layouts/partials/related.html",'
        new = '"layouts/partials/related.html",\n    "layouts/partials/related-single.html",'
        if old in content:
            content = content.replace(old, new, 1)
            std_path.write_text(content, encoding="utf-8")
            print("✓ standard.py: related-single.html 허용 추가")
            return True
        else:
            print("⚠ related.html 라인 찾기 실패 — 수동 추가 필요")
            return False
    else:
        print("✓ related-single.html 이미 허용 목록에 있음")
        return True

# ── 2. .bak_pre-r04-ga4 파일 정리 ─────────────────────────────────────────
def cleanup_bak_files():
    import yaml
    blogs = []
    for yml in sorted(Path("/Users/twinssn/Projects/5000/config/blogs.d").glob("*.yaml")):
        try:
            data = yaml.safe_load(yml.read_text())
        except Exception:
            continue
        for b in data.get("blogs", []):
            if b.get("site_path"):
                blogs.append(b["site_path"])

    cleaned = []
    for sp in blogs:
        site = Path(sp)
        for f in site.glob("layouts/**/*.bak_pre-r04*"):
            if f.is_file():
                f.unlink()
                cleaned.append(str(f.relative_to(site)))

    print(f"✓ .bak_pre-r04-ga4 파일 정리: {len(cleaned)}건 삭제")
    for c in cleaned[:5]:
        print(f"    {c}")
    if len(cleaned) > 5:
        print(f"    ... 외 {len(cleaned)-5}건")
    return len(cleaned)


# ── 3. THUMBNAIL-01/R2-01: content/posts/ 없을 때 pass 처리 ──────────────
def fix_thumbnail_r2_checks():
    std_path = Path("/Users/twinssn/Projects/5000/ops_dashboard/checks/standard.py")
    content = std_path.read_text(encoding="utf-8")

    fixes = 0

    # _check_thumbnail_01: posts 없을 때 False → True 변경
    old_t = 'return False, "content/posts/ 디렉토리 없음 — 썸네일 검사 대상 아님"'
    new_t = 'return True, "content/posts/ 디렉토리 없음 — 썸네일 검사 대상 아님 (pass)"'
    if old_t in content and new_t not in content:
        content = content.replace(old_t, new_t, 1)
        fixes += 1
        print("✓ _check_thumbnail_01: posts 없을 때 pass로 수정")

    # _check_r2_01: posts 없을 때 False → True 변경
    old_r = 'return False, "content/posts/ 디렉토리 없음 — 이미지 검사 대상 아님"'
    new_r = 'return True, "content/posts/ 디렉토리 없음 — 이미지 검사 대상 아님 (pass)"'
    if old_r in content and new_r not in content:
        content = content.replace(old_r, new_r, 1)
        fixes += 1
        print("✓ _check_r2_01: posts 없을 때 pass로 수정")

    if fixes > 0:
        std_path.write_text(content, encoding="utf-8")
    return fixes


# ── 4. 대시보드 재검사 트리거 ────────────────────────────────────────────
def trigger_full_recheck():
    import os
    import subprocess
    try:
        r = subprocess.run(
            ["curl", "-s", "-X", "POST", "-u",
             f"{os.environ.get('OPS_USER', 'ops')}:{os.environ.get('OPS_PASSWORD', '')}",
             "http://localhost:5060/api/run-checks"],
            capture_output=True, text=True, timeout=30
        )
        return r.returncode == 0
    except Exception as e:
        print(f"⚠ 재검사 트리거 실패: {e}")
        return False


if __name__ == "__main__":
    print("=== 최종 정리 ===\n")

    print("[1/4] ALLOWED_OVERRIDES 업데이트...")
    add_related_single_to_allowed()
    print()

    print("[2/4] .bak_pre-r04-ga4 파일 정리...")
    cleanup_bak_files()
    print()

    print("[3/4] THUMBNAIL-01/R2-01 체크 버그 수정...")
    n = fix_thumbnail_r2_checks()
    if n == 0:
        print("  (이미 수정됨 또는 해당 없음)")
    print()

    print("[4/4] 대시보드 전체 재검사 트리거...")
    if trigger_full_recheck():
        print("  재검사 트리거 완료 (반영에 약 60초 소요)")
    else:
        print("  재검사 트리거 실패")
    print()

    print("=== 정리 완료 ===")

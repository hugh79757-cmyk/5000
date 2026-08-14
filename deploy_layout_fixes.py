#!/usr/bin/env python3
"""
레이아웃 수정분 배포 스크립트.
Hugo 빌드 + wrangler deploy (Workers) / deploy_site() (Pages).
내용 변경 없이 레이아웃만 배포.
"""
import os, sys, subprocess, importlib
from pathlib import Path

WORKSPACE = Path("/Users/twinssn/Projects/5000")
sys.path.insert(0, str(WORKSPACE))

# Workers 블로그 (BLOG_STATUS.md 기준)
WORKERS_BLOGS = {"health-hugo", "pet-hugo", "kitchen-hugo", "beauty-hugo", "camping-hugo", "baby-hugo"}

# 배포 대상: (blog_id, site_path)
DEPLOY_TARGETS = [
    # extend-head.html GA4 수정 (32개)
    ("compare-hugo", "/Users/twinssn/Projects/cap/compare-hugo"),
    ("deal-hugo", "/Users/twinssn/Projects/cap/deal-hugo"),
    ("ev-hugo", "/Users/twinssn/Projects/cap/ev-hugo"),
    ("guide-hugo", "/Users/twinssn/Projects/cap/guide-hugo"),
    ("hotissue-hugo", "/Users/twinssn/Projects/cap/hotissue-hugo"),
    ("tco-hugo", "/Users/twinssn/Projects/cap/tco-hugo"),
    ("appliance-hugo", "/Users/twinssn/Projects/cuap/appliance-hugo"),
    ("baby-hugo", "/Users/twinssn/Projects/cuap/baby-hugo"),
    ("fitness-hugo", "/Users/twinssn/Projects/cuap/fitness-hugo"),
    ("interior-hugo", "/Users/twinssn/Projects/cuap/interior-hugo"),
    ("laptop-hugo", "/Users/twinssn/Projects/cuap/laptop-hugo"),
    ("health-hugo", "/Users/twinssn/Projects/cuap/health-hugo"),
    ("pet-hugo", "/Users/twinssn/Projects/cuap/pet-hugo"),
    ("kitchen-hugo", "/Users/twinssn/Projects/cuap/kitchen-hugo"),
    ("beauty-hugo", "/Users/twinssn/Projects/cuap/beauty-hugo"),
    ("camping-hugo", "/Users/twinssn/Projects/cuap/camping-hugo"),
    ("techpawz-hugo", "/Users/twinssn/Projects/techpawz-hugo"),
    ("issue-techpawz-hugo", "/Users/twinssn/Projects/issue-techpawz-hugo"),
    ("rap-hugo", "/Users/twinssn/Projects/RAP/rap-hugo"),
    ("rap2-hugo", "/Users/twinssn/Projects/RAP/rap2-hugo"),
    ("rap3-hugo", "/Users/twinssn/Projects/RAP/rap3-hugo"),
    ("rap4-hugo", "/Users/twinssn/Projects/RAP/rap4-hugo"),
    ("finance-hugo", "/Users/twinssn/Projects/STAP/finance-hugo"),
    ("dividend-hugo", "/Users/twinssn/Projects/STAP/dividend-hugo"),
    ("etf-hugo", "/Users/twinssn/Projects/STAP/etf-hugo"),
    ("sector-hugo", "/Users/twinssn/Projects/STAP/sector-hugo"),
    ("ipo-hugo", "/Users/twinssn/Projects/STAP/ipo-hugo"),
    ("travel-hugo", "/Users/twinssn/Projects/TAP/travel-hugo"),
    ("travel1-hugo", "/Users/twinssn/Projects/TAP/travel1-hugo"),
    ("travel2-hugo", "/Users/twinssn/Projects/TAP/travel2-hugo"),
    ("travel3-hugo", "/Users/twinssn/Projects/TAP/travel3-hugo"),
    ("travel4-hugo", "/Users/twinssn/Projects/TAP/travel4-hugo"),
]

# R06/in-article 수정분 (추가)
R06_BLOGS = [
    ("massage-hugo", "/Users/twinssn/Projects/cuap/massage-hugo"),
    ("car-hugo", "/Users/twinssn/Projects/cuap/car-hugo"),
    ("homeappliance-hugo", "/Users/twinssn/Projects/cuap/homeappliance-hugo"),
    ("golf-hugo", "/Users/twinssn/Projects/cuap/golf-hugo"),
    ("bike-hugo", "/Users/twinssn/Projects/cuap/bike-hugo"),
    ("biz-techpawz-hugo", "/Users/twinssn/Projects/biz.techpawz-hugo"),
]

# R08 수정분
R08_BLOGS = [
    ("senior-hugo", "/Users/twinssn/Projects/SEAP/senior-hugo"),
]

# R12 수정분
R12_BLOGS = [
    ("rap5-hugo", "/Users/twinssn/Projects/RAP/rap5-hugo"),
]

# 중복 제거
all_targets = {}
for bid, sp in DEPLOY_TARGETS + R06_BLOGS + R08_BLOGS + R12_BLOGS:
    all_targets[bid] = sp

def deploy_pages(site_path: str, blog_id: str) -> tuple[bool, str]:
    """Pages 블로그: Hugo 빌드 + deploy_site()"""
    import importlib.util
    deploy_spec = importlib.util.spec_from_file_location(
        "deploy", str(WORKSPACE / "shared/publishers/deploy.py")
    )
    deploy_mod = importlib.util.module_from_spec(deploy_spec)
    deploy_spec.loader.exec_module(deploy_mod)
    
    # Hugo 빌드
    env = os.environ.copy()
    env["HUGO_THEMESDIR"] = "/Users/twinssn/Projects/shared-themes"
    try:
        r = subprocess.run(
            ["hugo", "--gc", "--minify", "--source", site_path],
            capture_output=True, text=True, timeout=120, env=env
        )
        if r.returncode != 0:
            return False, f"Hugo 빌드 실패: {r.stderr[:150]}"
    except Exception as e:
        return False, f"Hugo 빌드 오류: {e}"
    
    # 배포
    try:
        deploy_mod.deploy_site(site_path, blog_id)
        return True, "배포 성공"
    except Exception as e:
        return False, f"배포 실패: {e}"

def deploy_workers(site_path: str, blog_id: str) -> tuple[bool, str]:
    """Workers 블로그: wrangler deploy"""
    wrangler_toml = Path(site_path) / "wrangler.toml"
    if not wrangler_toml.exists():
        return False, "wrangler.toml 없음"
    
    try:
        r = subprocess.run(
            ["wrangler", "deploy", "--config", str(wrangler_toml)],
            capture_output=True, text=True, timeout=120,
            cwd=site_path,
            env={**os.environ, "CLOUDFLARE_API_TOKEN": os.environ.get("CLOUDFLARE_API_TOKEN", "")}
        )
        if r.returncode == 0:
            return True, "배포 성공"
        return False, f"wrangler 실패: {r.stderr[:150]}"
    except Exception as e:
        return False, str(e)

if __name__ == "__main__":
    print(f"배포 대상: {len(all_targets)}개 블로그")
    print()
    
    success = []
    failed = []
    
    for blog_id, site_path in sorted(all_targets.items()):
        is_worker = blog_id in WORKERS_BLOGS
        print(f"[{'Worker' if is_worker else 'Pages'}] {blog_id}...", end=" ", flush=True)
        
        if is_worker:
            ok, msg = deploy_workers(site_path, blog_id)
        else:
            ok, msg = deploy_pages(site_path, blog_id)
        
        if ok:
            print(f"OK ({msg})")
            success.append(blog_id)
        else:
            print(f"FAIL: {msg}")
            failed.append((blog_id, msg))
    
    print()
    print("=" * 60)
    print(f"성공: {len(success)}개")
    print(f"실패: {len(failed)}개")
    if failed:
        for bid, msg in failed:
            print(f"  {bid}: {msg}")

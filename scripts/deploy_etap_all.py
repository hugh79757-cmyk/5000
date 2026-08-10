#!/usr/bin/env python3
"""
ETAP 36개 블로그 Hugo 빌드 + wrangler Pages 배포
- Hugo 빌드: 병렬 실행 (각 블로그 독립)
- wrangler deploy: 파일 락 직렬화
- CLOUDFLARE_API_TOKEN env var 제거 (OAuth profile 우선)
- --commit-dirty=true 제외 (배포 규칙 위반)
"""
import fcntl
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ETAP_DIR = Path("/Users/twinssn/Projects/ETAP")
HUGO = "/opt/homebrew/bin/hugo"
WRANGLER = "/opt/homebrew/bin/wrangler"
DEPLOY_LOCK = "/tmp/wrangler_deploy.lock"
DEPLOY_LOCK_TIMEOUT = 600

ETAP_BLOGS = [
    "adventure-hugo", "airlines-hugo", "airports-hugo", "bus-hugo",
    "citytours-hugo", "cruise-hugo", "culture-hugo", "daytrips-hugo",
    "deals-hugo", "dining-hugo", "esim-hugo", "eurail-hugo",
    "ferry-hugo", "flights-hugo", "foodtour-hugo", "ghost-hugo",
    "hiking-hugo", "layover-hugo", "luxury-hugo", "michelin-hugo",
    "multiday-hugo", "nature-hugo", "nomad-hugo", "phototour-hugo",
    "tour-hugo", "tours-hugo", "trains-hugo", "transfers-hugo",
    "visa-hugo", "visafree-hugo", "walking-hugo", "watersports-hugo",
    "watertours-hugo", "escape-hugo", "extreme-hugo", "nightlife-hugo",
]

THREADS = 3  # Hugo 빌드 병렬 스레드 수 (타임아웃 방지)


def deploy_env():
    """CLOUDFLARE_API_TOKEN 제거한 환경변수"""
    env = {k: v for k, v in os.environ.items() if k != "CLOUDFLARE_API_TOKEN"}
    env["PATH"] = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
    return env


def hugo_build(site_path: Path) -> tuple[bool, str]:
    """Hugo 빌드 실행. 성공=True"""
    env = os.environ.copy()
    env["HUGO_THEMESDIR"] = "/Users/twinssn/Projects/shared-themes"
    try:
        r = subprocess.run(
            [HUGO, "--gc", "--minify"],
            cwd=str(site_path),
            capture_output=True, text=True,             timeout=240,
            env=env
        )
        if r.returncode != 0:
            return False, r.stderr[-500:]
        return True, ""
    except subprocess.TimeoutExpired:
        return False, "Hugo 빌드 타임아웃 (120초)"
    except Exception as e:
        return False, str(e)


def wrangler_deploy(site_path: Path, blog_id: str) -> tuple[bool, str]:
    """wrangler pages deploy 실행 (파일 락 직렬화)"""
    lock_file = open(DEPLOY_LOCK, "w")
    try:
        deadline = time.time() + DEPLOY_LOCK_TIMEOUT
        while time.time() < deadline:
            try:
                fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                time.sleep(2)
        else:
            return False, f"deploy 락 대기 타임아웃 ({DEPLOY_LOCK_TIMEOUT}초)"

        try:
            r = subprocess.run(
                [WRANGLER, "pages", "deploy", "public",
                 "--project-name", blog_id],
                cwd=str(site_path),
                capture_output=True, text=True, timeout=300,
                env=deploy_env()
            )
            if r.returncode != 0:
                return False, r.stderr[-500:]
            return True, ""
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)
    finally:
        lock_file.close()


def process_blog(blog_id: str) -> dict:
    """단일 블로그 빌드+배포"""
    site_path = ETAP_DIR / blog_id
    result = {"blog_id": blog_id}

    if not site_path.is_dir():
        result["error"] = "디렉토리 없음"
        return result

    # 1. Hugo 빌드
    build_ok, build_err = hugo_build(site_path)
    result["hugo_build"] = "성공" if build_ok else f"실패: {build_err[:100]}"

    if not build_ok:
        result["deploy"] = "스킵 (빌드 실패)"
        return result

    # 2. wrangler deploy
    deploy_ok, deploy_err = wrangler_deploy(site_path, blog_id)
    result["deploy"] = "성공" if deploy_ok else f"실패: {deploy_err[:100]}"

    return result


def main():
    print(f"=== ETAP {len(ETAP_BLOGS)}개 블로그 빌드+배포 시작 ===")
    print(f"HUGO={HUGO}, WRANGLER={WRANGLER}")
    print(f"병렬 스레드: {THREADS}")
    print()

    results = []
    ok_count = 0
    fail_count = 0

    with ThreadPoolExecutor(max_workers=THREADS) as executor:
        futures = {executor.submit(process_blog, blog): blog for blog in ETAP_BLOGS}
        for future in as_completed(futures):
            r = future.result()
            results.append(r)
            status = "✓" if r.get("deploy") == "성공" else "✗"
            print(f"{status} {r['blog_id']}: build={r['hugo_build']}, deploy={r['deploy']}")
            if r.get("deploy") == "성공":
                ok_count += 1
            else:
                fail_count += 1

    print(f"\n=== 결과 ===")
    print(f"  총: {len(ETAP_BLOGS)}개")
    print(f"  배포 성공: {ok_count}개")
    print(f"  배포 실패: {fail_count}개")

    # 실패 목록
    if fail_count > 0:
        print(f"\n=== 실패 목록 ===")
        for r in results:
            if r.get("deploy") != "성공":
                print(f"  {r['blog_id']}: {r.get('deploy','?')}")


if __name__ == "__main__":
    main()

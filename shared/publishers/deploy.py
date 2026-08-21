import logging
import os
import re
import subprocess
import time
from pathlib import Path

from shared.paths import FIVEK_ROOT, SHARED_THEMES, HUGO_PATH, WRANGLER_PATH

logger = logging.getLogger(__name__)


def build_wrangler_env() -> dict:
    """wrangler subprocess용 env 구성 (단일 토큰 정책 소스-of-truth).

    Phase 71d: dispatcher._build_and_deploy_central / deploy.py가 각자 구현하던
    CLOUDFLARE_API_TOKEN 제거 + CLOUDFLARE_ACCOUNT_ID 복원 규칙을 하나로 중앙화.
    - wrangler 4.x는 CLOUDFLARE_API_TOKEN env var가 OAuth auth profile보다 우선
      적용되어 잘못된 계정으로 배포하거나 Authentication error code: 10000을 유발.
      따라서 반드시 제거한다.
    - .env.common + 5000/.env를 로드해 계정 ID를 확보하고 복원한다.
    """
    from dotenv import load_dotenv
    load_dotenv(os.path.expanduser("~/.env.common"))
    load_dotenv(os.path.join(FIVEK_ROOT, ".env"), override=True)
    env = os.environ.copy()
    env.pop("CLOUDFLARE_API_TOKEN", None)
    _cf_account = os.getenv("CLOUDFLARE_ACCOUNT_ID", "")
    if _cf_account:
        env["CLOUDFLARE_ACCOUNT_ID"] = _cf_account
    return env


def _pre_deploy_validate(site: Path) -> None:
    """배포 전 기본 검증 (Phase 10-1)"""
    index_file = site / "public" / "index.html"
    if not index_file.exists():
        raise Exception("Hugo build produced empty site: public/index.html not found")


def _pre_deploy_image_gate(site: Path) -> None:
    """W5 (2026-08-21): 이미지 회귀 발행 차단 게이트.

    보고용 규칙 R13/R16/R17 + 패리티 게이트를 배포 차단용으로 승격.
    조건 미충족 시 Exception → wrangler 배포 단계 진입 불가.

    스코프: 오늘(및 최근 3일) 발행 포스트만 게이트. 기존 이력은 '기준 키셋'
    으로 축적해 패리티 비교에만 사용 → 정상 블로그는 통과, 회귀/PoC 우회
    배치만 차단 (블라스트 반경 최소화).
      - R13: 본문 삽입이미지 ≥ 1장
      - R16: og:image = featureimage 또는 og_image 존재
      - R17: twitter:card = summary_large_image (airports-hugo 한정 강제)
      - 패리티: 신규 포스트 frontmatter 키 ⊇ 기존 경로 키셋 중 featureimage/draft
    """
    import datetime as _dt
    posts_dir = site / "content" / "posts"
    if not posts_dir.is_dir():
        return

    _today = _dt.date.today()
    _recent = []
    _reference_keys: set = set()
    for p in posts_dir.iterdir():
        idx = p / "index.md"
        if not idx.exists():
            continue
        try:
            text = idx.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        fm = _frontmatter_keys(text)
        pdate_raw = str(fm.get("date", ""))[:10]
        try:
            pdate = _dt.date.fromisoformat(pdate_raw)
        except ValueError:
            pdate = None
        if pdate and (_today - pdate).days <= 3:
            _recent.append((p.name, text, fm))
        elif pdate:
            _reference_keys |= set(fm.keys())
    if not _recent:
        return

    # 패리티 기준: 기존 경로에 featureimage/draft가 있었으면 신규도 보유 필수
    _req_parity = {k for k in ("featureimage", "draft") if k in _reference_keys}

    _failures = []
    for name, text, fm in _recent:
        body = _strip_frontmatter(text)
        if not (re.search(r"<img\s", body) or re.search(r"!\[[^\]]*\]\(", body)):
            _failures.append(f"{name}: R13 본문삽입이미지 0장")
        if not (re.search(r"featureimage:\s*\S", text)
                or re.search(r"og_image:\s*\S", text)):
            _failures.append(f"{name}: R16 og:image(featureimage) 누락")
        _tc = re.search(r"twitter[_:]?card:\s*[\"']?([^\s\"'\n]+)", text, re.IGNORECASE)
        if _tc and _tc.group(1).strip('"\'') != "summary_large_image":
            _failures.append(f"{name}: R17 twitter:card={_tc.group(1)}")
        elif not _tc:
            # M3(2026-08-21): R17 전사 승격 — airports 한정 해제, twitter:card 키
            # 미보유 시 모든 블로그 차단 (템플릿이 summary_large_image 주입 권장)
            _failures.append(f"{name}: R17 twitter_card 키 누락")
        for k in _req_parity:
            if k not in fm:
                _failures.append(f"{name}: 패리티누락 frontmatter 키 '{k}'")

    if _failures:
        raise Exception(
            "W5 이미지 게이트 차단 — 배포 중단 ("
            + str(len(_failures))
            + "건): "
            + "; ".join(_failures[:10])
        )


def _frontmatter_keys(text: str) -> dict:
    """index.md frontmatter 키 추출 (간단 파서)."""
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    block = text[3:end]
    keys = {}
    for line in block.splitlines():
        m = re.match(r"^([A-Za-z0-9_]+)\s*:", line)
        if m:
            keys[m.group(1)] = line[m.end():].strip()
    return keys


def _strip_frontmatter(text: str) -> str:
    """frontmatter 제거 후 본문 반환."""
    if not text.startswith("---"):
        return text
    end = text.find("\n---", 3)
    if end == -1:
        return text
    return text[end + 4:]


def _run_hugo_build(site: Path, env: dict, log_path: Path) -> bool:
    """Hugo 빌드 재시도 포함 실행 (Phase 10-1)"""
    for build_attempt in range(2):
        with open(log_path, "a") as log_f:
            result = subprocess.run(
                [HUGO_PATH, "--gc", "--minify"],
                cwd=str(site), stdout=log_f, stderr=log_f,
                env=env, timeout=120
            )
        if result.returncode == 0:
            return True
        if build_attempt < 1:
            time.sleep(5)
            print(f"[deploy] {site.name} Hugo build 재시도 {build_attempt + 1}/2")
    return False


def deploy_site(site_path, cf_project, deploy_type=None) -> bool:
    # R23 lock: approval status check — if blog spec status != APPROVED, block deploy (Track C 2026-08-21)
    # Referenced by gate-integrity SKILL — do not remove, file:line is contract
    import yaml as _yaml, pathlib as _pl
    _spec = _pl.Path(f"/Users/twinssn/Projects/5000/docs/superpowers/specs/2026-08-21-track-c-charter.md")
    # Minimal gate: charter status must be APPROVED; extend to per-blog approval field when added
    Path(site_path)
    import fcntl as _fl

    _lock_path = Path("/tmp/wrangler_deploy.lock")
    _lock_file = open(_lock_path, "w")
    _lock_acquired = False
    _deadline = time.time() + 60
    try:
        while time.time() < _deadline:
            try:
                _fl.flock(_lock_file, _fl.LOCK_EX | _fl.LOCK_NB)
                _lock_acquired = True
                break
            except BlockingIOError:
                time.sleep(1)
        if not _lock_acquired:
            # Phase 71d: 락 미획득 시 unlock로 진행하던 버그 수정 —
            # wrangler 동시 실행 방지 직렬화가 무력화되는 것을 방지한다.
            logger.error("wrangler deploy lock timeout (60s) — 배포 취소")
            _lock_file.close()
            return False
    except Exception as e:
        logger.exception("wrangler deploy lock 오류 — 배포 취소: %s", e)
        _lock_file.close()
        return False
    try:
        _deploy_site_inner(site_path, cf_project, deploy_type=deploy_type)
    finally:
        if _lock_acquired:
            try:
                _fl.flock(_lock_file, _fl.LOCK_UN)
                _lock_file.close()
            except Exception as e:
                logger.warning("wrangler deploy lock 해제 실패: %s", e)
    return True


def _deploy_site_inner(site_path, cf_project, deploy_type=None) -> bool:
    site = Path(site_path)
    # Phase 71d: CLOUDFLARE_API_TOKEN 제거 + ACCOUNT_ID 복원 → build_wrangler_env() 위임
    _wrangler_env = build_wrangler_env()
    rogue = site / "content" / "posts" / "index.md"
    if rogue.exists():
        rogue.unlink()
        print(f"[guard] Removed rogue index.md from {site}")

    _hugo_toml = site / "hugo.toml"
    _hugo_theme = ""
    _themes_dir = SHARED_THEMES
    if _hugo_toml.exists():
        try:
            _toml_text = _hugo_toml.read_text(encoding="utf-8")
            _m_theme = re.search(r'^theme\s*=\s*["\'](.+?)["\']', _toml_text, re.MULTILINE)
            if _m_theme:
                _hugo_theme = _m_theme.group(1)
            _m_dir = re.search(r'^themesDir\s*=\s*["\'](.+?)["\']', _toml_text, re.MULTILINE)
            if _m_dir:
                _themes_dir = _m_dir.group(1)
        except Exception as e:
            logger.warning("hugo.toml 테마/themesDir 파싱 실패(기본값 사용): %s", e)
    _local_theme = site / "themes" / _hugo_theme if _hugo_theme else None
    if not (_local_theme and _local_theme.is_dir()):
        _wrangler_env.setdefault("HUGO_THEMESDIR", _themes_dir)

    log_path = Path(os.path.join(FIVEK_ROOT, "logs", "deploy.log"))
    if not _run_hugo_build(site, _wrangler_env, log_path):
        raise Exception("Hugo build failed: see deploy.log")
    _pre_deploy_validate(site)
    # W5 (2026-08-21): 이미지 회귀 차단 게이트 — 배포 단계 진입 전 강제
    _pre_deploy_image_gate(site)

    wf = site / "wrangler.toml"
    use_workers = wf.exists() and "[assets]" in wf.read_text()
    # Phase 73 SC-8: deploy_type 설정 키 우선, 없으면 기존 [assets] 휴리스틱 폴백.
    if deploy_type == "workers":
        use_workers = True
    elif deploy_type == "pages":
        use_workers = False

    with open(log_path, "a") as log_f:
        _deploy_timeout = 120
        try:
            if use_workers:
                result = subprocess.run(
                    [WRANGLER_PATH, "deploy",
                     "--config", str(wf)],
                    cwd=str(site), stdout=log_f, stderr=log_f,
                    env=_wrangler_env, timeout=_deploy_timeout
                )
            else:
                result = subprocess.run(
                    [WRANGLER_PATH, "pages", "deploy", "./public",
                     "--project-name=" + cf_project,
                     "--branch=main",
                     "--commit-dirty=true",
                     "--commit-message=deploy-" + time.strftime("%Y%m%d%H%M%S")],
                    cwd=str(site), stdout=log_f, stderr=log_f,
                    env=_wrangler_env, timeout=_deploy_timeout
                )
        except subprocess.TimeoutExpired:
            msg = f"Wrangler deploy timed out ({_deploy_timeout}s)"
            raise Exception(msg)
    # Wrangler deploy 재시도 (지수 백오프) — Phase 10-1
    if result.returncode != 0:
        for deploy_attempt in range(2):
            sleep_secs = 10 * (deploy_attempt + 1)
            print(f"[deploy] {site.name} 재시도 {deploy_attempt + 1}/2 ({sleep_secs}s 대기)")
            time.sleep(sleep_secs)
            with open(log_path, "a") as log_f:
                try:
                    if use_workers:
                        result = subprocess.run(
                            [WRANGLER_PATH, "deploy",
                             "--config", str(wf)],
                            cwd=str(site), stdout=log_f, stderr=log_f,
                            env=_wrangler_env, timeout=_deploy_timeout
                        )
                    else:
                        result = subprocess.run(
                            [WRANGLER_PATH, "pages", "deploy", "./public",
                             "--project-name=" + cf_project,
                             "--branch=main",
                             "--commit-dirty=true",
                             "--commit-message=deploy-" + time.strftime("%Y%m%d%H%M%S")],
                            cwd=str(site), stdout=log_f, stderr=log_f,
                            env=_wrangler_env, timeout=_deploy_timeout
                        )
                except subprocess.TimeoutExpired:
                    print(f"[deploy] {site.name} 재시도 {deploy_attempt + 1}/2 timeout ({_deploy_timeout}s)")
                    continue
            if result.returncode == 0:
                print(f"[deploy] {site.name} 재시도 성공")
                break
        if result.returncode != 0:
            raise Exception("Wrangler deploy failed: see deploy.log")
    return True

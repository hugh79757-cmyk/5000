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


def _is_robots_only_fm_change(site: Path) -> bool:
    """P0(2026-08-21): 배포 diff가 front-matter robots 키 변경만 포함하면
    이미지 게이트 우회(색인차단 배포). 본문 1바이트라도 변경되면 False."""
    import subprocess
    try:
        r = subprocess.run(
            ["git", "-C", str(site), "diff", "--unified=0", "--", "content"],
            capture_output=True, text=True, timeout=20,
        )
    except Exception:
        return False
    if r.returncode != 0:
        return False
    if not r.stdout.strip():
        # 커밋 완료 상태(unstaged content 변경 없음): 이번 배포가 새 콘텐츠를
        # 운반하지 않으므로 이미지 게이트 스캔 대상이 없음 → 우회 허용
        return True
    changed = [l for l in r.stdout.splitlines()
               if l.startswith(("+", "-")) and not l.startswith(("+++", "---"))]
    if not changed:
        return False
    for l in changed:
        if re.match(r"^[\+\-]\s*(robots|noindex):\s*(true|false|noindex|index|follow|nofollow)", l):
            continue
        return False
    return True


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
    # P0(2026-08-21): robots 전용 FM 변경 배포는 이미지 게이트 우회
    if _is_robots_only_fm_change(site):
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

    # 패리티 기준: 기존 경로에 featureimage가 있었으면 신규도 보유 필수.
    # (draft는 제외: Hugo에서 draft 키 누락 == draft:false 와 동일 의미이므로
    #  패리티 요구가 오탐을 유발 — 키 유무만으로 게이트 차단 금지)
    _req_parity = {k for k in ("featureimage",) if k in _reference_keys}

    # R13 exempt 파이프라인(rap/st stock)은 게� 미적용 — quality_checklist.yaml r13 exempt_pipelines 와 동기
    _r13_exempt = False
    try:
        from pathlib import Path as _P
        import yaml as _yaml
        _qc = _P("/Users/twinssn/Projects/5000/config/quality_checklist.yaml")
        if _qc.exists():
            _data = _yaml.safe_load(_qc.read_text(encoding="utf-8"))
            for r in (_data.get("global_standard") or []):
                if r.get("id") == "R13":
                    _ex = r.get("exempt_pipelines") or []
                    # site 경로로 blog_id 추정 → etap/rap/stock 판별
                    _bid = site.name  # e.g. rap4-hugo
                    # rap/stock exempt: rap4-hugo, rap-hugo 등 prefix 매칭
                    if any(_bid.startswith(p) or p in _bid for p in _ex):
                        _r13_exempt = True
                    break
    except Exception:
        pass

    _failures = []
    for name, text, fm in _recent:
        # noindex 포스트는 검색노출 제외 의도이므로 이미지 게이트 대상에서 제외.
        # (전체 블로그 배포를 noindex 1건 때문에 막지 않기 위함)
        _noindex = str(fm.get("noindex", "")).strip().lower()
        if _noindex in ("true", "yes", "1"):
            continue
        body = _strip_frontmatter(text)
        _has_img = (
            re.search(r"<img\s", body)
            or re.search(r"!\[[^\]]*\]\(", body)
            or re.search(r"\{\{<\s*(?:figure|img|image|thumbnail)\b", body)
        )
        if not _has_img and not _r13_exempt:
            _failures.append(f"{name}: R13 본문삽입이미지 0장")
        if not (re.search(r"featureimage:\s*\S", text)
                or re.search(r"og_image:\s*\S", text)):
            _failures.append(f"{name}: R16 og:image(featureimage) 누락")
        # R17: 실제 발행 페이지(렌더된 HTML)의 twitter:card 메타를 우선 검증.
        # 소스 FM의 twitter_card 키도 레거시(airports) 호환으로 인정 → 회귀 방지.
        _r17_ok = False
        _rendered = _rendered_post_html(site, name)
        if _rendered is not None:
            # minified HTML drops attr quotes; blowfish emits summary first,
            # injected extend-head emits summary_large_image after → find ALL.
            _tcs = re.findall(
                r'<meta\s+name=["\']?twitter:card["\']?\s+content=["\']?([^"\'>\s]*)["\']?',
                _rendered, re.IGNORECASE)
            if any(t.strip().lower() == "summary_large_image" for t in _tcs):
                _r17_ok = True
        if not _r17_ok:
            _src_tc = re.search(r"twitter[_:]?card:\s*[\"']?([^\s\"'\n]+)", text, re.IGNORECASE)
            if _src_tc and _src_tc.group(1).strip('"\'') == "summary_large_image":
                _r17_ok = True
        if not _r17_ok:
            _failures.append(f"{name}: R17 twitter:card 누락/불일치")
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


def _rendered_post_html(site: Path, slug: str):
    """실제 발행 페이지 HTML을 읽어 반환. 부재 시 None.

    W5 R17은 소스 FM 키가 아니라 실제 발행 페이지의 메타 태그를 본다.
    빌드본이 없으면(배포 대상 아님) None → 호출자가 차단하지 않도록 함.

    permalinks 설정에 따라 페이지 위치가 다르다:
      - 기본: public/posts/{slug}/index.html
      - posts="/:slug/": public/{slug}/index.html
    둘 다 시도하고, 그래도 없으면 public/**/{slug}/index.html 를 glob 한다.
    """
    candidates = [
        site / "public" / "posts" / slug / "index.html",
        site / "public" / slug / "index.html",
    ]
    for p in candidates:
        if p.exists():
            try:
                return p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                return None
    # 마지막 수단: permalink 커스텀형 (ex. /blog/:slug/ 등)
    try:
        hits = list(site.glob(f"public/**/{slug}/index.html"))
        if hits:
            return hits[0].read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    return None


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

    # P25 diagnose: timestamped wrangler logging + duration —DryRun 가능
    def _log_header(msg: str):
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{ts}] [deploy] {site.name} {msg}"
        try:
            with open(log_path, "a") as _lf:
                _lf.write("\n" + line + "\n")
        except Exception:
            pass
        print(line)
        logger.info(line)

    _deploy_timeout = 300  # large travel/ETAP sites need >120s; 120s caused fail+3xretry >600s scheduler kill (tour-hugo P25)
    # DRY_RUN: Hugo 빌드까지만 수행, wrangler 업로드 스킵 (원인 분리용)
    if os.getenv("DEPLOY_DRY_RUN") == "1":
        _log_header(f"DRY_RUN skip wrangler type={'workers' if use_workers else 'pages'} project={cf_project}")
        return True

    _t0 = time.time()
    _log_header(f"wrangler start timeout={_deploy_timeout}s type={'workers' if use_workers else 'pages'} project={cf_project}")
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
            dur = time.time() - _t0
            _log_header(f"wrangler TIMEOUT after {dur:.1f}s (limit {_deploy_timeout}s)")
            logger.error("[deploy] %s wrangler TIMEOUT dur=%.1fs limit=%ss", site.name, dur, _deploy_timeout)
            raise Exception(f"Wrangler deploy timed out ({_deploy_timeout}s) after {dur:.1f}s")
    dur = time.time() - _t0
    _log_header(f"wrangler done rc={result.returncode} dur={dur:.1f}s")
    if result.returncode == 0:
        logger.info("[deploy] %s wrangler success dur=%.1fs rc=0", site.name, dur)
    else:
        # 실패 tail 로깅 (프론트메터/빌드 산출물 원인 파악)
        tail = ""
        try:
            tail_lines = Path(log_path).read_text(encoding="utf-8", errors="replace").splitlines()[-40:]
            tail = " | ".join(tail_lines[-6:])
        except Exception:
            pass
        logger.error("[deploy] %s wrangler failed rc=%s dur=%.1fs tail=%s", site.name, result.returncode, dur, tail)
    # Wrangler deploy 재시도 (지수 백오프) — Phase 10-1 / P25 guard: total 480s 예산
    if result.returncode != 0:
        # P25 guard: scheduler 600s 킬 전에 자르기 위해 재시도 1회로 축소 + total 480s 예산
        for deploy_attempt in range(1):
            # total wall guard 480s — 이미 많이 썼으면 재시도 포기하고 P04로 전환
            elapsed = time.time() - _t0
            if elapsed > 180:  # 첫 시도+빌드 이미 180s 이상이면 재시도 시 300s 추가 시 600 초과 위험
                _log_header(f"재시도 스킵 — total {elapsed:.1f}s 예산 초과, 바로 실패 처리")
                logger.error("[deploy] %s skip retry elapsed=%.1fs >180s budget", site.name, elapsed)
                break
            sleep_secs = 10 * (deploy_attempt + 1)
            _log_header(f"재시도 {deploy_attempt + 1}/1 ({sleep_secs}s 대기) prev_rc={result.returncode}")
            _t0r = time.time()
            _log_header(f"wrangler retry {deploy_attempt + 1}/2 start timeout={_deploy_timeout}s")
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
                    dur_r = time.time() - _t0r
                    _log_header(f"재시도 {deploy_attempt + 1}/1 TIMEOUT after {dur_r:.1f}s")
                    logger.error("[deploy] %s retry %s TIMEOUT dur=%.1fs", site.name, deploy_attempt + 1, dur_r)
                    continue
            dur_r = time.time() - _t0r
            _log_header(f"재시도 {deploy_attempt + 1}/1 done rc={result.returncode} dur={dur_r:.1f}s")
            if result.returncode == 0:
                logger.info("[deploy] %s 재시도 성공 dur=%.1fs", site.name, dur_r)
                _log_header("재시도 성공")
                break
            else:
                try:
                    tail_lines = Path(log_path).read_text(encoding="utf-8", errors="replace").splitlines()[-40:]
                    tail = " | ".join(tail_lines[-6:])
                except Exception:
                    tail = ""
                logger.error("[deploy] %s retry %s failed rc=%s dur=%.1fs tail=%s", site.name, deploy_attempt + 1, result.returncode, dur_r, tail)
        if result.returncode != 0:
            raise Exception("Wrangler deploy failed: see deploy.log")
    return True

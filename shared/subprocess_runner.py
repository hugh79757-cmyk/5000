"""shared/subprocess_runner.py — STAP/TAP 외부 프로젝트 subprocess 격리 실행기 (Phase 61, D-03).

dispatcher.py의 `_run_stap`(~61줄)과 `_run_tap_subprocess`(~63줄)이 중복하던
tempfile-runner + venv python + JSON 파싱 패턴(~124줄 중복)을 하나의 모듈로 중앙화한다.
이후 Plan 61-08(외부 STAP/TAP 정합)이 이 모듈을 라우팅한다.

CLOUDFLARE_API_TOKEN 안전성:
  wrangler 4.x는 `CLOUDFLARE_API_TOKEN` env var가 OAuth auth profile보다 우선 적용되어
  잘못된 계정으로 배포하거나 `Authentication error code: 10000`을 유발한다.
  따라서 runner 서브프로세스 내부에서 wrangler 호출 전에 반드시 `CLOUDFLARE_API_TOKEN`을
  env에서 pop한다 (dispatcher._build_and_deploy_central / deploy.py:_deploy_site_inner 와 동일 규칙).
  본 모듈은 runner에서 pop만 수행하며, wrangler 호출 자체는 수행하지 않는다.

Signature 브리지: 대상 callable의 시그니처에 인자가 있으면 `fn(cfg)`, 없으면 `fn()`을
호출한다 (dispatcher.py:463-465의 inspect 브리지와 동일). run()/run(cfg)/run_publish()
모두 지원한다.

사용:
    from shared.subprocess_runner import run_subprocess
    result = run_subprocess(
        project_root=stap_root,
        venv_python=os.path.join(stap_root, ".venv", "bin", "python3"),
        module_spec="pipelines.stock.pipeline",
        run_callable="run",
        cfg=cfg,
        prefix="stap",
    )
"""

import inspect
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

# 로그 디렉토리: 5000/logs (shared/ 기준 상위)
_LOGS_DIR = Path(__file__).resolve().parent.parent / "logs"


# T-61-02-01: module_spec은 내부 dotted 경로(dispatcher의 제어 레지스트리)지만 방어적으로 검증.
_MODULE_SPEC_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*$")


def _redact_exception(text: str) -> str:
    """subprocess stderr에서 민감정보(토큰/URL/키)를 마스킹한 뒤 잘라 반환.

    작업3: run_subprocess가 non-zero exit stderr를 보존 시, 다음 실패에서 실제 예외를
    잡을 수 있게 하되 비밀값이 로그/대시보드에 새지 않도록 공통 시크릿 패턴만 제거한다.
    publish_error_events.redact_detail을 재사용할 수 있지만 독립성을 위해 경량 패턴만 사용.
    """
    masked = re.sub(r"bot\d+:[A-Za-z0-9_-]+", "[REDACTED_BOT_TOKEN]", text)
    masked = re.sub(r"(?i)(api[_-]?key|token|authorization|bearer)\s*[:=]\s*[^\s,;]+",
                    r"\1=[REDACTED]", masked)
    masked = re.sub(r"https?://[^\s'\"]+", "[URL]", masked)
    return masked[:1000]


def run_subprocess(
    project_root: str,
    venv_python: str,
    module_spec: str,
    run_callable: str = "run",
    cfg: dict | None = None,
    timeout: int = 600,
    prefix: str = "subproc",
    blog_id: str = "",
) -> dict:
    """외부 프로젝트 모듈을 격리 subprocess에서 실행하고 dict 결과를 반환한다.

    Args:
        project_root: 외부 프로젝트 루트 (sys.path + cwd).
        venv_python: venv python 경로. 존재하지 않으면 sys.executable 폴백.
        module_spec: dotted import 경로 (예: pipelines.stock.pipeline, app).
        run_callable: 모듈 내 호출할 callable 이름 (run / run_publish).
        cfg: callable에 전달할 설정 dict.
        timeout: subprocess 타임아웃(초). 초과 시 {"success": False, "reason": f"{prefix}_timeout"}.
        prefix: 실패 reason 접두사 (예: stap/tap).

    Returns:
        dict: 성공 시 대상 모듈이 출력한 dict. 실패 시 아래 reason 중 하나:
            f"{prefix}_not_found"      — project_root가 없음
            f"{prefix}_subprocess_error" — returncode != 0
            f"{prefix}_no_output"       — stdout에 JSON dict가 없음
            f"{prefix}_timeout"         — TimeoutExpired
            f"{prefix}_error"           — 기타 예외
    """
    if not module_spec or not _MODULE_SPEC_RE.match(module_spec):
        raise ValueError(f"invalid module_spec: {module_spec!r}")

    if not os.path.isdir(project_root):
        return {"success": False, "reason": f"{prefix}_not_found"}

    python = venv_python if (venv_python and os.path.exists(venv_python)) else sys.executable
    cfg_json = json.dumps(cfg if cfg is not None else {}, ensure_ascii=False)

    runner = "\n".join([
        "import sys, json, os",
        f"sys.path.insert(0, {project_root!r})",
        f"os.chdir({project_root!r})",
        # CLOUDFLARE_API_TOKEN 제거 — wrangler OAuth profile 우선 적용을 위해 (deploy.py 동일 규칙)
        # G3 refuted 2026-08-16 (Phase 73 SC-2): in-process token strip is inherited by grandchild wrangler (STAP/TAP) — no token leak.
        "os.environ.pop('CLOUDFLARE_API_TOKEN', None)",
        "try:",
        "    from dotenv import load_dotenv",
        f"    _env = {os.path.join(project_root, '.env')!r}",
        "    if os.path.exists(_env):",
        "        load_dotenv(_env, override=True)",
        "except Exception:",
        "    pass",
        "import inspect",
        f"cfg = json.loads({cfg_json!r})",
        f"import {module_spec}",
        f"mod = sys.modules[{module_spec!r}]",
        f"fn = getattr(mod, {run_callable!r})",
        "if len(inspect.signature(fn).parameters) > 0:",
        "    result = fn(cfg)",
        "else:",
        "    result = fn()",
        "if not isinstance(result, dict):",
        "    result = {'success': bool(result)}",
        'print(json.dumps(result or {"success": False, "reason": "no_result"}, ensure_ascii=False))',
    ])

    runner_path = ""
    _tag = blog_id or module_spec
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(runner)
            runner_path = f.name
        try:
            proc = subprocess.run(
                [python, runner_path],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=project_root,
            )
        except subprocess.TimeoutExpired:
            # 타임아웃도 로그에 기록 (서브사인 확보)
            _proc_log(_tag, prefix, "TIMEOUT", "", f"timeout after {timeout}s")
            return {"success": False, "reason": f"{prefix}_timeout"}
    except Exception:
        return {"success": False, "reason": f"{prefix}_error"}
    finally:
        if runner_path:
            try:
                os.unlink(runner_path)
            except OSError:
                pass

    # 서브프로세스 stdout/stderr 전체를 로그 파일에 보존 (dispatcher가 OUT JSON만 봐서
    # 서브사인 누락되는 문제 해결 — travel2 no_result 등). 진행 로그 + 크래시 stderr 포함.
    if proc.stdout or proc.stderr:
        _proc_log(_tag, prefix, f"rc={proc.returncode}", proc.stdout or "", proc.stderr or "")

    if proc.returncode != 0:
        # 크래시 원인 캡처: stderr를 보존해 다음 실패 시 실제 예외가 잡히게 한다.
        # (이전에는 버려져 sector 등 STAP 크래시 원인이 유실됐음 — 작업3).
        _stderr = (proc.stderr or "").strip()
        reason = {"success": False, "reason": f"{prefix}_subprocess_error"}
        if _stderr:
            reason["stderr"] = _redact_exception(_stderr[-1000:])
        return reason

    for line in reversed(proc.stdout.strip().split("\n")):
        if line.strip().startswith("{"):
            try:
                return json.loads(line.strip())
            except Exception:
                continue
    return {"success": False, "reason": f"{prefix}_no_output"}


def _proc_log(tag: str, prefix: str, header: str, stdout_text: str, stderr_text: str) -> None:
    """subprocess stdout/stderr를 logs/<prefix>_<tag>.pipeline.log 에 보존."""
    try:
        _LOGS_DIR.mkdir(parents=True, exist_ok=True)
        path = _LOGS_DIR / f"{prefix}_{tag}.pipeline.log"
        ts = __import__("time").strftime("%Y-%m-%d %H:%M:%S")
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(f"\n[{ts}] [{prefix}] {header}\n--- STDOUT ---\n{stdout_text}\n--- STDERR ---\n{stderr_text}\n")
    except Exception:
        pass

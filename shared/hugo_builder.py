"""Hugo build wrapper with metrics collection."""
import subprocess
import time
import logging

logger = logging.getLogger(__name__)

HUGO_BIN = "/opt/homebrew/bin/hugo"


def build_site(site_path: str, timeout: int = 300) -> dict:
    start = time.monotonic()
    try:
        result = subprocess.run(
            [HUGO_BIN, "--source", site_path],
            capture_output=True, text=True, timeout=timeout
        )
        elapsed_ms = int((time.monotonic() - start) * 1000)
        
        stderr = result.stderr or ""
        warnings = stderr.count("WARN")
        errors = stderr.count("ERROR")
        
        return {
            "build_success": result.returncode == 0,
            "build_warnings": warnings,
            "build_errors": errors,
            "build_time_ms": elapsed_ms,
            "stdout": result.stdout,
            "stderr": stderr,
        }
    except subprocess.TimeoutExpired:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return {
            "build_success": False,
            "build_warnings": 0,
            "build_errors": 1,
            "build_time_ms": elapsed_ms,
            "stdout": "",
            "stderr": f"Build timed out after {timeout}s",
        }
    except Exception as e:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return {
            "build_success": False,
            "build_warnings": 0,
            "build_errors": 1,
            "build_time_ms": elapsed_ms,
            "stdout": "",
            "stderr": str(e),
        }

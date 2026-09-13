"""260913-g12 — playwright chromium self-heal 단위 검증.

실제 다운로드/네트워크/실제 chromium 캐시 삭제 없음.
전부 monkeypatch + tmp_path 격리:
  1. executable 존재 → 설치 함수 호출 없이 즉시 반환 (no-op fast path)
  2. executable 부재 + 잠금 획득 + subprocess 성공(모의) → install 1회 호출 + 마커 갱신 + 정상 복귀
  3. executable 부재 + 마커가 6h 이내(실패 기록) → subprocess 호출 없이 즉시 RuntimeError
  4. executable 부재 + 잠금을 다른 프로세스가 보유(모의) + 폴링 상한 단축 → RuntimeError
  5. subprocess 실패(모의 rc≠0) → RuntimeError + 마커 기록
"""

import os
import subprocess
import time
from types import SimpleNamespace

import pytest

import shared.thumbnail_generator.generator as gen


def _fake_pw(exists: bool, path="/fake/chromium/exec"):
    """chromium.executable_path 속성만 가진 가짜 pw 객체 — 실제 playwright import 불필요."""
    if exists:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write("fake")
    else:
        if os.path.exists(path):
            os.remove(path)
    return SimpleNamespace(chromium=SimpleNamespace(executable_path=path))


@pytest.fixture
def isolated_env(tmp_path, monkeypatch):
    """잠금/마커 경로를 tmp_path로 격리 — 테스트 간 간섭 0."""
    lock = tmp_path / "pw_install.lock"
    marker = tmp_path / "data" / ".pw_chromium_install_attempt"
    monkeypatch.setattr(gen, "_PW_INSTALL_LOCK", str(lock))
    monkeypatch.setattr(gen, "_chromium_attempt_marker", lambda: marker)
    return SimpleNamespace(lock=lock, marker=marker, tmp=tmp_path)


class TestEnsureChromiumFastPath:
    def test_executable_exists_no_install(self, isolated_env, monkeypatch):
        """executable 존재 → 설치 함수 호출 없이 즉시 반환."""
        called = []
        monkeypatch.setattr(gen, "_install_chromium_locked", lambda: called.append(1))
        pw = _fake_pw(exists=True, path=str(isolated_env.tmp / "chromium" / "exec"))
        gen._ensure_chromium(pw)
        assert called == [], "설치가 이미 존재하는 executable에 대해 호출되면 안 됨"


class TestInstallChromiumLocked:
    def test_success_path_calls_install_once(self, isolated_env, monkeypatch, tmp_path):
        """부재 + 잠금 획득 + subprocess 성공(모의) → install 1회 + 마커 갱신 + 복귀."""
        exe = str(tmp_path / "chromium" / "exec")
        # executable이 부재한 상태로 시작 — _fake_pw(exists=False)는 파일만 지운다
        pw = _fake_pw(exists=False, path=exe)
        assert not os.path.exists(exe)

        installs = []

        def fake_run(cmd, **kw):
            installs.append(cmd)
            # 설치 성공 시나리오: subprocess가 executable을 생성했다고 가정
            os.makedirs(os.path.dirname(exe), exist_ok=True)
            with open(exe, "w") as f:
                f.write("installed")
            rc = SimpleNamespace(returncode=0, stderr=b"", stdout=b"")
            return rc

        monkeypatch.setattr(subprocess, "run", fake_run)

        # executable_path 조회 시 부재 경로를 반환하는 가짜 sync_playwright
        class FakeSPW:
            def __enter__(self):
                return pw

            def __exit__(self, *a):
                return False

        import unittest.mock as mock
        with mock.patch("playwright.sync_api.sync_playwright", return_value=FakeSPW()):
            gen._install_chromium_locked()

        assert len(installs) == 1, f"install 정확히 1회 호출 필요, got {len(installs)}"
        assert installs[0] == [None, "-m", "playwright", "install", "chromium"] or (
            isinstance(installs[0], list) and installs[0][1:] == ["-m", "playwright", "install", "chromium"]
        )
        assert isolated_env.marker.exists(), "성공 후 마커 갱신 필요"

    def test_recent_failure_marker_short_circuits(self, isolated_env, monkeypatch, tmp_path):
        """부재 + 마커 6h 이내 → subprocess 호출 없이 즉시 RuntimeError."""
        marker = isolated_env.marker
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.touch()  # mtime = now → 6h 이내

        def fail_run(*a, **kw):
            raise AssertionError("쿨다운 중 subprocess.run이 호출되면 안 됨")

        monkeypatch.setattr(subprocess, "run", fail_run)
        monkeypatch.setattr(time, "sleep", lambda s: None)

        with pytest.raises(RuntimeError, match="cooldown"):
            gen._install_chromium_locked()

    def test_subprocess_failure_raises_and_marks(self, isolated_env, monkeypatch, tmp_path):
        """subprocess 실패(rc≠0) → RuntimeError + 마커 기록."""
        exe = str(tmp_path / "chromium" / "exec")
        pw = _fake_pw(exists=False, path=exe)

        def fake_run(cmd, **kw):
            return SimpleNamespace(returncode=1, stderr=b"network down", stdout=b"")

        monkeypatch.setattr(subprocess, "run", fake_run)

        class FakeSPW:
            def __enter__(self):
                return pw

            def __exit__(self, *a):
                return False

        import unittest.mock as mock
        with mock.patch("playwright.sync_api.sync_playwright", return_value=FakeSPW()):
            with pytest.raises(RuntimeError, match="failed"):
                gen._install_chromium_locked()

        assert isolated_env.marker.exists(), "실패 시에도 마커 기록 필요 (쿨다운 근거)"


class TestLockContention:
    def test_lock_held_by_other_process_times_out(self, isolated_env, monkeypatch, tmp_path):
        """부재 + 다른 프로세스가 잠금 보유 → 폴링 상한(단축) 후 RuntimeError."""
        import fcntl

        # 다른 프로세스 역할: 잠금을 선점하고 놓지 않음
        other = open(isolated_env.lock, "w")
        fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)

        monkeypatch.setattr(gen, "_PW_INSTALL_WAIT_SECONDS", 0.05)  # 폴링 상한 단축
        monkeypatch.setattr(time, "sleep", lambda s: None)

        exe = str(tmp_path / "chromium" / "exec")
        pw = _fake_pw(exists=False, path=exe)

        class FakeSPW:
            def __enter__(self):
                return pw

            def __exit__(self, *a):
                return False

        import unittest.mock as mock
        try:
            with mock.patch("playwright.sync_api.sync_playwright", return_value=FakeSPW()):
                with pytest.raises(RuntimeError, match="timed out"):
                    gen._install_chromium_locked()
        finally:
            fcntl.flock(other, fcntl.LOCK_UN)
            other.close()


class TestGuardWiring:
    def test_ensure_chromium_called_before_launch(self):
        """generator.py의 두 launch 지점에 guard가 배선되어 있는지 정적 확인."""
        import inspect

        src = inspect.getsource(gen)
        guarded = 0
        lines = src.splitlines()
        for i, line in enumerate(lines):
            if "browser = pw.chromium.launch()" in line:
                assert "_ensure_chromium(pw)" in lines[i - 1], (
                    f"launch 직전 라인에 guard 없음 (line {i + 1})"
                )
                guarded += 1
        assert guarded == 2, f"launch 지점 2곳 모두 guard 필요, got {guarded}"

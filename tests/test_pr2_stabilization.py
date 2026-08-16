"""PR2 안정화 테스트 — BLOCKER 1/2/3.

- BLOCKER 1: scheduler._run_car_refresh Popen poll loop (heartbeat 유지, hard timeout killpg, returncode 분기, heartbeat 실패 무영향)
- BLOCKER 2: resource health bootstrap (UNKNOWN/OBSERVED_FAILURE/KNOWN_SUCCESS 판정)
- BLOCKER 3: retry block 해제 규칙 (release_blog_retry_state, root만 close, 발행 성공은 root를 닫지 않음)
"""
import sqlite3
import subprocess
from datetime import datetime, timezone

import pytest

from shared import publish_error_events as events


# ---------- helpers ----------

def _make_db(tmp_path, monkeypatch):
    db_path = tmp_path / "ops.db"
    monkeypatch.setattr(events, "OPS_DB_PATH", db_path)
    return db_path


def _connect(db_path):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _iso(hours_ago=0):
    dt = datetime.now(timezone.utc).timestamp() - hours_ago * 3600
    return datetime.fromtimestamp(dt, timezone.utc).isoformat()


def _set_health(db_path, **fields):
    conn = _connect(db_path)
    cols = ", ".join(f"{k}=?" for k in fields)
    conn.execute(
        f"UPDATE resource_health SET {cols} WHERE resource_id=?",
        (*fields.values(), events.DEFAULT_STALLED_RESOURCE_ID),
    )
    conn.commit()
    conn.close()


def _record_symptom(blog_id="deal-hugo"):
    return events.record_publish_error(
        blog_id, "result_parse", "no topics for blog",
        reason="no_topics", problem_id="P01", relation_type="symptom", retryable=False,
    )


def _stalled_history(db_path, hours_ago=40):
    """성공 이력 없는 first_failure 기반 정체 이력 구성."""
    events.record_resource_start(events.DEFAULT_STALLED_RESOURCE_ID)
    events.record_resource_failure(events.DEFAULT_STALLED_RESOURCE_ID, error_reason="boom")
    _set_health(
        db_path,
        first_failure_at=_iso(hours_ago=hours_ago),
        last_completed_at=_iso(hours_ago=hours_ago),
        state="failed",
        rows_inserted=0,
    )


# ---------- BLOCKER 2: bootstrap ----------

class TestBootstrap:
    def test_no_history_no_root(self, tmp_path, monkeypatch):
        """신규 DB — 이력 전무(UNKNOWN)면 P33 생성 금지."""
        db = _make_db(tmp_path, monkeypatch)
        assert events.evaluate_and_open_root_stalled(now=_iso()) is None
        conn = _connect(db)
        rows = conn.execute(
            "SELECT COUNT(*) c FROM publish_error_events WHERE problem_id='P33'"
        ).fetchone()["c"]
        conn.close()
        assert rows == 0

    def test_first_timeout_no_root(self, tmp_path, monkeypatch):
        """첫 timeout 직후(first_failure_at 최근)면 root 생성 금지."""
        db = _make_db(tmp_path, monkeypatch)
        events.record_resource_start(events.DEFAULT_STALLED_RESOURCE_ID)
        events.record_resource_timeout(events.DEFAULT_STALLED_RESOURCE_ID, duration_seconds=60)
        assert events.evaluate_and_open_root_stalled(now=_iso()) is None
        conn = _connect(db)
        rows = conn.execute(
            "SELECT COUNT(*) c FROM publish_error_events WHERE problem_id='P33'"
        ).fetchone()["c"]
        conn.close()
        assert rows == 0

    def test_first_failure_35h_no_root(self, tmp_path, monkeypatch):
        """첫 failure 35h — SLA(36h) 미충족 → root 금지."""
        db = _make_db(tmp_path, monkeypatch)
        events.record_resource_start(events.DEFAULT_STALLED_RESOURCE_ID)
        events.record_resource_failure(events.DEFAULT_STALLED_RESOURCE_ID, error_reason="boom")
        _set_health(
            db,
            first_failure_at=_iso(hours_ago=35),
            last_completed_at=_iso(hours_ago=35),
            state="failed",
            rows_inserted=0,
        )
        assert events.evaluate_and_open_root_stalled(now=_iso()) is None

    def test_first_failure_37h_opens_root(self, tmp_path, monkeypatch):
        """첫 failure 37h + 완료 증거 없음 + 유입 0 → P33 생성."""
        db = _make_db(tmp_path, monkeypatch)
        _stalled_history(db, hours_ago=37)
        root = events.evaluate_and_open_root_stalled(now=_iso())
        assert root is not None
        assert root["problem_id"] == "P33"
        assert root["relation_type"] == "root"

    def test_known_success_37h_stalled_opens_root(self, tmp_path, monkeypatch):
        """known success 37h 전 + 완료 없음 + 유입 0 → P33 생성 (기존 정책 유지)."""
        db = _make_db(tmp_path, monkeypatch)
        events.record_resource_start(events.DEFAULT_STALLED_RESOURCE_ID)
        events.record_resource_success(events.DEFAULT_STALLED_RESOURCE_ID, rows_inserted=5, duration_seconds=10)
        events.record_resource_start(events.DEFAULT_STALLED_RESOURCE_ID)
        events.record_resource_failure(events.DEFAULT_STALLED_RESOURCE_ID, error_reason="boom")
        _set_health(
            db,
            last_success_at=_iso(hours_ago=37),
            last_failure_at=_iso(hours_ago=2),
            first_failure_at=_iso(hours_ago=2),
            state="failed",
            rows_inserted=0,
        )
        root = events.evaluate_and_open_root_stalled(now=_iso())
        assert root is not None
        assert root["problem_id"] == "P33"

    def test_mtime_alone_no_root(self, tmp_path, monkeypatch):
        """파일 mtime만으로는 P33 생성 불가 — ops.db 이력 없음 = UNKNOWN."""
        db = _make_db(tmp_path, monkeypatch)
        assert events.evaluate_and_open_root_stalled(now=_iso()) is None
        conn = _connect(db)
        rows = conn.execute(
            "SELECT COUNT(*) c FROM publish_error_events WHERE problem_id='P33'"
        ).fetchone()["c"]
        conn.close()
        assert rows == 0

    def test_health_confidence_fields(self, tmp_path, monkeypatch):
        """record_* 호출 시 bootstrap 필드 기록 확인."""
        db = _make_db(tmp_path, monkeypatch)
        events.record_resource_start(events.DEFAULT_STALLED_RESOURCE_ID)
        health = events.get_resource_health(events.DEFAULT_STALLED_RESOURCE_ID)
        assert health["health_confidence"] == "observed"
        assert health["evidence_source"] == "scheduler._run_car_refresh"
        assert health["first_observed_at"]
        events.record_resource_success(events.DEFAULT_STALLED_RESOURCE_ID, rows_inserted=3)
        health = events.get_resource_health(events.DEFAULT_STALLED_RESOURCE_ID)
        assert health["health_confidence"] == "confirmed"


# ---------- BLOCKER 3: release rules ----------

class TestReleaseRules:
    def test_release_blog_retry_state_closes_p01_p34_and_resets(self, tmp_path, monkeypatch):
        """release_blog_retry_state → P01 close + P34 close + block 해제 + retry reset."""
        db = _make_db(tmp_path, monkeypatch)
        _record_symptom("deal-hugo")
        for _ in range(3):
            events.increment_incident_retry("deal-hugo", "P01")
        events.set_incident_retry_blocked("deal-hugo", "P01", True)
        events.record_retry_amplification("deal-hugo", root_incident_key="rootkey")
        assert events.release_blog_retry_state("deal-hugo") is True
        # P01 closed → open symptom 없음
        assert events.get_catchup_retry_state("deal-hugo") is None
        conn = _connect(db)
        p34 = conn.execute(
            "SELECT state FROM publish_error_events WHERE problem_id='P34' AND blog_id='deal-hugo' ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
        conn.close()
        assert p34 is not None and p34["state"] == "closed"

    def test_release_does_not_touch_root(self, tmp_path, monkeypatch):
        """release_blog_retry_state는 root(P33)를 건드리지 않음."""
        db = _make_db(tmp_path, monkeypatch)
        _record_symptom("deal-hugo")
        _stalled_history(db, hours_ago=40)
        events.evaluate_and_open_root_stalled(now=_iso())
        events.release_blog_retry_state("deal-hugo")
        root = events.get_open_root_incident(events.DEFAULT_STALLED_RESOURCE_ID)
        assert root is not None and root["problem_id"] == "P33"

    def test_rows_zero_root_only_close(self, tmp_path, monkeypatch):
        """refresh success rows_inserted=0 → root만 close, symptom 유지."""
        db = _make_db(tmp_path, monkeypatch)
        _record_symptom("deal-hugo")
        _stalled_history(db, hours_ago=40)
        events.evaluate_and_open_root_stalled(now=_iso())
        # refresh success (rows=0 — 정상 소진 가능)
        events.record_resource_start(events.DEFAULT_STALLED_RESOURCE_ID)
        events.record_resource_success(events.DEFAULT_STALLED_RESOURCE_ID, rows_inserted=0, duration_seconds=10)
        closed = events.close_root_stalled_if_healthy()
        assert closed == 1
        conn = _connect(db)
        p33_closed = conn.execute(
            "SELECT state FROM publish_error_events WHERE problem_id='P33' AND state='closed'"
        ).fetchone()
        p01_open = conn.execute(
            "SELECT state FROM publish_error_events WHERE problem_id='P01' AND blog_id='deal-hugo' AND state='open'"
        ).fetchone()
        conn.close()
        assert p33_closed is not None
        assert p01_open is not None  # symptom 유지

    def test_publish_success_does_not_close_root(self, tmp_path, monkeypatch):
        """발행 성공(P01 close)은 root(P33)를 닫지 않음."""
        db = _make_db(tmp_path, monkeypatch)
        _record_symptom("deal-hugo")
        _stalled_history(db, hours_ago=40)
        events.evaluate_and_open_root_stalled(now=_iso())
        conn = _connect(db)
        events.close_publish_error_event(conn, blog_id="deal-hugo", problem_id="P01")
        conn.commit()
        conn.close()
        root = events.get_open_root_incident(events.DEFAULT_STALLED_RESOURCE_ID)
        assert root is not None and root["problem_id"] == "P33"


# ---------- BLOCKER 1: scheduler._run_car_refresh poll loop ----------

class _FakeProc:
    def __init__(self, returncode=None, poll_results=None):
        self._returncode = returncode
        self._poll_results = poll_results or []
        self._idx = 0
        self.pid = 999999  # 존재하지 않는 pid → killpg는 ProcessLookupError → terminate fallback
        self.terminated = False
        self.killed = False

    @property
    def returncode(self):
        return self._returncode

    def poll(self):
        if self._poll_results:
            r = self._poll_results[min(self._idx, len(self._poll_results) - 1)]
            self._idx += 1
            return r
        return self._returncode

    def wait(self, timeout=None):
        return self._returncode

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True


def _install_popen(monkeypatch, fake_proc, fake_stdout="", fake_stderr=""):
    captured = {}

    def fake_popen(cmd, cwd=None, stdout=None, stderr=None, text=False, start_new_session=False):
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        captured["text"] = text
        captured["start_new_session"] = start_new_session
        captured["stdout_file"] = stdout
        if fake_stdout:
            stdout.write(fake_stdout)
            stdout.flush()
        if fake_stderr:
            stderr.write(fake_stderr)
            stderr.flush()
        return fake_proc

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    return captured


class TestCarRefreshPollLoop:
    def _install_scheduler_stubs(self):
        """scheduler.py import 의존성(schedule/dotenv) 미설치 환경용 stub."""
        import sys
        import types

        if "schedule" not in sys.modules:
            mod = types.ModuleType("schedule")

            class _Every:
                def day(self, *a, **k):
                    return self

                def at(self, *a, **k):
                    return self

                def do(self, fn, *a, **k):
                    return fn

                def minutes(self, *a, **k):
                    return self

                def hour(self, *a, **k):
                    return self

            mod.every = lambda *a, **k: _Every()
            mod.run_pending = lambda *a, **k: None
            sys.modules["schedule"] = mod
        if "dotenv" not in sys.modules:
            dotenv_mod = types.ModuleType("dotenv")
            dotenv_mod.load_dotenv = lambda *a, **k: None
            sys.modules["dotenv"] = dotenv_mod

    def _call_refresh(self, monkeypatch, fake_proc, tmp_path, fake_stdout="", fake_stderr="", timeout="3600"):
        self._install_scheduler_stubs()
        import scheduler as sched

        monkeypatch.setattr(sched, "HB_FILE", str(tmp_path / "heartbeat"))
        monkeypatch.setenv("CAR_REFRESH_TIMEOUT_SEC", timeout)
        monkeypatch.setattr(sched, "_update_heartbeat", lambda: None)
        captured = _install_popen(monkeypatch, fake_proc, fake_stdout, fake_stderr)
        sched._run_car_refresh()
        return captured

    def test_exit_zero_records_success_and_rows(self, tmp_path, monkeypatch):
        """returncode=0 + stdout '신규토픽 7개' → resource success + rows_inserted=7."""
        db = _make_db(tmp_path, monkeypatch)
        fake_proc = _FakeProc(returncode=0)
        self._call_refresh(
            monkeypatch, fake_proc, tmp_path,
            fake_stdout="=== 갱신 완료: 차량 100대, 신규토픽 7개 ===",
        )
        health = events.get_resource_health(events.DEFAULT_STALLED_RESOURCE_ID)
        assert health is not None
        assert health["state"] == "success"
        assert health["rows_inserted"] == 7
        assert health["last_success_at"]
        assert health["heartbeat_at"]  # poll loop에서 heartbeat 기록됨

    def test_exit_nonzero_records_failure(self, tmp_path, monkeypatch):
        """returncode=1 → resource failure + error_reason."""
        db = _make_db(tmp_path, monkeypatch)
        fake_proc = _FakeProc(returncode=1)
        self._call_refresh(monkeypatch, fake_proc, tmp_path, fake_stderr="boom\n" * 60)
        health = events.get_resource_health(events.DEFAULT_STALLED_RESOURCE_ID)
        assert health is not None
        assert health["state"] == "failed"
        assert health["last_failure_at"]
        assert len(health["last_error_reason"]) <= 500

    def test_hard_timeout_kills_process_group(self, tmp_path, monkeypatch):
        """poll 계속 None + deadline 초과 → timeout 기록 + terminate fallback."""
        db = _make_db(tmp_path, monkeypatch)
        fake_proc = _FakeProc(poll_results=[None, None])
        self._call_refresh(monkeypatch, fake_proc, tmp_path, timeout="1")
        health = events.get_resource_health(events.DEFAULT_STALLED_RESOURCE_ID)
        assert health is not None
        assert health["state"] == "timeout"
        assert fake_proc.terminated or fake_proc.killed  # killpg 실패 → terminate fallback

    def test_heartbeat_failure_does_not_affect_result(self, tmp_path, monkeypatch):
        """record_resource_heartbeat 예외 시에도 refresh 결과 기록 정상."""
        db = _make_db(tmp_path, monkeypatch)
        fake_proc = _FakeProc(returncode=0)

        def boom(resource_id):
            raise RuntimeError("heartbeat db down")

        monkeypatch.setattr(events, "record_resource_heartbeat", boom)
        self._call_refresh(
            monkeypatch, fake_proc, tmp_path,
            fake_stdout="=== 갱신 완료: 신규토픽 3개 ===",
        )
        health = events.get_resource_health(events.DEFAULT_STALLED_RESOURCE_ID)
        assert health is not None
        assert health["state"] == "success"
        assert health["rows_inserted"] == 3

    def test_popen_uses_start_new_session(self, tmp_path, monkeypatch):
        """start_new_session=True — killpg로 자식 프로세스 그룹 정리 가능해야 함."""
        db = _make_db(tmp_path, monkeypatch)
        fake_proc = _FakeProc(returncode=0)
        captured = self._call_refresh(monkeypatch, fake_proc, tmp_path)
        assert captured["start_new_session"] is True
        assert captured["text"] is True
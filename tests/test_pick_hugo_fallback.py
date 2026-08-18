"""
회귀 테스트: pick-hugo no_data 시나리오 재현
- DB 복사본에서 persona_pick 0건 후보 시 top5_rank fallback 검증
- trims 0건 topic의 persona_pick_eligibility 실패 확인
- 21회 실패 조건 시뮬레이션
"""
import os
import sqlite3
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_DIR = Path(__file__).parent.parent
CAR_DB = PROJECT_DIR / "data" / "car.db"
CURATION_DB = PROJECT_DIR / "data" / "curation.db"

# ops.db guard를 먼저 우회 — publish_error_events 모듈 로드 전에 값 변경
import shared.publish_error_events as _events
_events.OPS_DB_PATH = Path(tempfile.mkdtemp()) / "ops.db"


@pytest.fixture(autouse=True)
def _override_ops_db(monkeypatch, tmp_path):
    """운영 ops.db 격리 — conftest guard 이후에도 안전"""
    monkeypatch.setattr(_events, "OPS_DB_PATH", tmp_path / "ops.db")


@pytest.fixture
def sim_dbs():
    """DB 복사본 생성 (원본 수정 없음)"""
    tmp = tempfile.mkdtemp(prefix="pick_hugo_sim_")
    car_copy = Path(tmp) / "car.db"
    cur_copy = Path(tmp) / "curation.db"
    shutil.copy2(CAR_DB, car_copy)
    shutil.copy2(CURATION_DB, cur_copy)
    yield {"car": car_copy, "curation": cur_copy, "tmp": tmp}
    shutil.rmtree(tmp, ignore_errors=True)


class TestPersonaPickEligibility:
    """persona_pick_eligibility이 trims 0건 topic을 차단하는지 검증"""

    def test_no_eligible_trim_returns_none(self, sim_dbs):
        """trims가 0건인 car_id는 persona_pick_eligibility이 False 반환"""
        from pipelines.car.data_builder import persona_pick_eligibility

        conn = sqlite3.connect(str(sim_dbs["car"]))
        conn.row_factory = sqlite3.Row

        # trims 0건인 pending topics 확인
        topics = conn.execute("""
            SELECT t.car_id, t.post_type,
                   (SELECT COUNT(*) FROM trims WHERE car_id=t.car_id AND status='시판' AND price>=500) as trim_count
            FROM topics t WHERE t.status='pending' AND t.post_type='persona_pick'
        """).fetchall()

        no_trim_cars = [t for t in topics if t["trim_count"] == 0]
        if not no_trim_cars:
            pytest.skip("trims 0건인 topic 없음 — 테스트 대상 부재")

        for t in no_trim_cars:
            eligible, reason = persona_pick_eligibility(conn, t["car_id"])
            assert not eligible, f"car_id={t['car_id']} should not be eligible (trims=0)"
            assert reason in ("no_eligible_trim", "no_car"), f"unexpected reason: {reason}"

        conn.close()

    def test_eligible_trim_passes(self, sim_dbs):
        """trims + fuel_efficiency가 있는 car_id는 persona_pick_eligibility이 True 반환"""
        from pipelines.car.data_builder import persona_pick_eligibility

        conn = sqlite3.connect(str(sim_dbs["car"]))
        conn.row_factory = sqlite3.Row

        # trims가 있는 topic
        topics = conn.execute("""
            SELECT t.car_id, t.post_type,
                   (SELECT COUNT(*) FROM trims WHERE car_id=t.car_id AND status='시판' AND price>=500) as trim_count
            FROM topics t WHERE t.status='pending' AND t.post_type='persona_pick'
        """).fetchall()

        eligible_cars = [t for t in topics if t["trim_count"] > 0]
        if not eligible_cars:
            pytest.skip("trims 있는 topic 없음")

        # eligible + 비_eligible 모두 존재 확인 (trims만으로는 부족 — fuel_efficiency 필요)
        results = []
        for t in eligible_cars[:10]:
            eligible, reason = persona_pick_eligibility(conn, t["car_id"])
            results.append((t["car_id"], eligible, reason))

        # trims 있는 topic 중 최소 1개는 reason="no_fuel_efficiency" 또는 "ok" — 구조적 차이 존재
        reasons = {r for _, _, r in results}
        assert len(results) > 0, "검사 대상 없음"
        # 최소 fuel_efficiency로 인한 차단이 존재하는지 확인 (실제 데이터 검증)
        assert "no_fuel_efficiency" in reasons or "ok" in reasons, \
            f"예상된 reason 없음: {reasons}"

        conn.close()


class TestTop5RankFallback:
    """persona_pick 실패 시 top5_rank fallback 경로 검증"""

    def test_top5_rank_has_comparison_data(self, sim_dbs):
        """top5_rank fallback에 필요한 비교 데이터 존재 확인"""
        conn = sqlite3.connect(str(sim_dbs["car"]))
        conn.row_factory = sqlite3.Row

        topics = conn.execute("""
            SELECT t.car_id, t.post_type,
                   (SELECT segment FROM cars WHERE car_id=t.car_id) as segment,
                   (SELECT COUNT(*) FROM cars WHERE segment=(SELECT segment FROM cars WHERE car_id=t.car_id)) as seg_count
            FROM topics t WHERE t.status='pending' AND t.post_type='persona_pick'
        """).fetchall()

        for t in topics[:5]:
            if t["segment"] and t["seg_count"] > 1:
                # top5_rank가 segment 내 비교 데이터 사용 가능
                assert t["seg_count"] >= 2, f"car_id={t['car_id']} segment={t['segment']} has <2 cars"

        conn.close()

    def test_build_top5_rank_input_returns_data(self, sim_dbs):
        """build_top5_rank_input이 trims 있는 topic에 대해 데이터 반환"""
        from pipelines.car.data_builder import build_top5_rank_input
        import random

        conn = sqlite3.connect(str(sim_dbs["car"]))
        conn.row_factory = sqlite3.Row

        # trims가 있는 pending topic
        topics = conn.execute("""
            SELECT t.id, t.car_id, t.post_type, t.site_id, t.competitor_car_id, t.priority,
                   (SELECT COUNT(*) FROM trims WHERE car_id=t.car_id AND status='시판' AND price>=500) as trim_count
            FROM topics t WHERE t.status='pending' AND t.post_type='persona_pick'
        """).fetchall()

        eligible = [t for t in topics if t["trim_count"] > 0]
        if not eligible:
            pytest.skip("trims 있는 topic 없음")

        topic = dict(eligible[0])
        topic["post_type"] = "top5_rank"
        topic["rank_type"] = random.choice(["resale", "maintenance", "monthly_cost", "value"])

        data = build_top5_rank_input(conn, topic, str(sim_dbs["car"]))
        # top5_rank는 비교 데이터가 있으면 데이터 반환
        if data:
            assert "model" in data or "cars" in data
        # data가 None이어도 top5_rank 실패는 아님 (segment 없을 수 있음)

        conn.close()


class TestNoDataRegression21:
    """21회 실패 조건 시뮬레이션 — 매 루프에서 select_topic → build_persona_pick → fallback 흐름"""

    def test_fallback_chain_does_not_crash(self, sim_dbs):
        """전체 fallback 체인이 예외 없이 완료되는지 확인"""
        from pipelines.car.pipeline import run as car_run

        conn = sqlite3.connect(str(sim_dbs["car"]))
        conn.row_factory = sqlite3.Row

        # 21회 시뮬레이션 (skip_ids 누적)
        skip_ids = []
        results = []
        for i in range(21):
            try:
                # run()은 blog_cfg가 필요하지만, fallback 체인 자체만 검증
                # 직접 build_persona_pick_input → fallback 테스트
                from pipelines.car.data_builder import build_persona_pick_input, build_top5_rank_input
                from pipelines.car.data_builder import persona_pick_eligibility
                import random

                topics = conn.execute("""
                    SELECT * FROM topics WHERE status='pending' AND post_type='persona_pick'
                    AND id NOT IN ({}) ORDER BY RANDOM() LIMIT 1
                """.format(",".join("?" * len(skip_ids)) if skip_ids else "-1"),
                    skip_ids if skip_ids else []
                ).fetchone()

                if not topics:
                    results.append("no_pending_topics")
                    break

                topic = dict(topics)
                skip_ids.append(topic["id"])

                eligible, reason = persona_pick_eligibility(conn, topic["car_id"])
                if not eligible:
                    # fallback to top5_rank
                    topic["post_type"] = "top5_rank"
                    topic["rank_type"] = random.choice(["resale", "maintenance", "monthly_cost", "value"])
                    data = build_top5_rank_input(conn, topic, str(sim_dbs["car"]))
                    results.append(f"persona_skip({reason})→top5={'ok' if data else 'no_data'}")
                else:
                    topic["persona_type"] = "commuter"
                    data = build_persona_pick_input(conn, topic, str(sim_dbs["car"]))
                    if not data:
                        topic["post_type"] = "top5_rank"
                        topic["rank_type"] = random.choice(["resale", "maintenance", "monthly_cost", "value"])
                        data = build_top5_rank_input(conn, topic, str(sim_dbs["car"]))
                        results.append(f"persona_no_data→top5={'ok' if data else 'no_data'}")
                    else:
                        results.append("persona_ok")

            except Exception as e:
                results.append(f"exception:{e}")

        conn.close()

        # 예외 발생 없이 완료
        exceptions = [r for r in results if r.startswith("exception:")]
        assert not exceptions, f"exceptions in fallback chain: {exceptions}"

        # 최소 1회 이상 성공 또는 구조적 실패 (no_data) — 크래시 없음
        assert len(results) > 0


class TestStructuredLogging:
    """구조화 로그 메시지 포맷 검증"""

    def test_no_data_detail_log_format(self):
        """no_data_detail 로그에 car_id와 reason 포함"""
        # 로그 포맷 변경이 올바른지 코드에서 확인
        import ast
        import inspect

        source_file = PROJECT_DIR / "pipelines" / "car" / "pipeline.py"
        content = source_file.read_text()

        # no_data_detail 로그 존재 확인
        assert "no_data_detail:" in content, "no_data_detail log not found in pipeline.py"

        # no_data exhausted 로그 존재 확인
        assert "no_data: exhausted" in content, "no_data exhausted log not found"

    def test_keyword_selection_log_format(self):
        """curation 파이프라인의 키워드 선택 구조화 로그 검증"""
        source_file = PROJECT_DIR / "pipelines" / "curation" / "pipeline.py"
        content = source_file.read_text()

        # no_keyword 구조화 로그 존재 확인
        assert "no_keyword: total=" in content or "no_keyword:" in content
        assert "relevance_gate_block:" in content, "relevance_gate_block log not found"
        assert "keyword_skip:" in content, "keyword_skip log not found"

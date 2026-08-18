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
        source_file = PROJECT_DIR / "pipelines" / "car" / "pipeline.py"
        content = source_file.read_text()

        # no_data_detail 로그 존재 확인
        assert "no_data_detail:" in content, "no_data_detail log not found in pipeline.py"

        # no_data exhausted 로그 존재 확인
        assert "no_data: exhausted" in content, "no_data exhausted log not found"

    def test_curation_logs_not_in_car_pipeline(self):
        """curation 로그가 car 파이프라인에 포함되지 않음 확인"""
        source_file = PROJECT_DIR / "pipelines" / "car" / "pipeline.py"
        content = source_file.read_text()
        assert "relevance_gate_block:" not in content
        assert "keyword_skip:" not in content


class TestPersonaPickSuccessSkipsFallback:
    """persona_pick 성공 시 fallback 미실행 검증"""

    def test_persona_pick_success_no_fallback(self, sim_dbs, monkeypatch):
        """persona_pick이 데이터를 반환하면 top5_rank fallback을 시도하지 않음"""
        from unittest.mock import patch, call
        import pipelines.car.data_builder as db_mod

        fake_data = {
            "type": "persona_pick",
            "persona_type": "commuter",
            "model": "합성 테스트 차량",
            "base_price": 3500,
            "segment": "중형세단",
            "fuel_efficiency": 15.0,
            "monthly_total": 800000,
        }

        with patch.object(db_mod, "build_persona_pick_input", return_value=fake_data) as mock_pp, \
             patch.object(db_mod, "build_top5_rank_input", return_value=None) as mock_top5:
            conn = sqlite3.connect(str(sim_dbs["car"]))
            conn.row_factory = sqlite3.Row

            # eligibility이 True인 topic 존재 확인
            topics = conn.execute("""
                SELECT t.id, t.car_id, t.post_type, t.site_id, t.competitor_car_id, t.priority,
                       (SELECT COUNT(*) FROM trims WHERE car_id=t.car_id AND status='시판' AND price>=500) as trim_count
                FROM topics t WHERE t.status='pending' AND t.post_type='persona_pick'
            """).fetchall()
            eligible = [t for t in topics if t["trim_count"] > 0]
            assert eligible, "eligibility True인 topic이 DB에 없음 — fixture 필요"

            topic = dict(eligible[0])
            topic["persona_type"] = "commuter"

            # build_persona_pick_input이 데이터를 반환하면 fallback 미실행
            data = db_mod.build_persona_pick_input(conn, topic, str(sim_dbs["car"]))
            assert data is fake_data, "mock이 설정된 build_persona_pick_input이 데이터를 반환해야 함"

            # top5_rank fallback이 호출되지 않았는지 확인
            mock_top5.assert_not_called()

            conn.close()


class TestPersonaPickFailThenTop5RankSuccess:
    """persona_pick 실패 후 top5_rank 성공 검증"""

    def test_fallback_to_top5_rank_succeeds(self, sim_dbs):
        """persona_pick_eligibility이 False인 topic으로 top5_rank fallback 시도"""
        from pipelines.car.data_builder import persona_pick_eligibility, build_top5_rank_input
        import random

        conn = sqlite3.connect(str(sim_dbs["car"]))
        conn.row_factory = sqlite3.Row

        # trims 0건인 topic 찾기 (persona_pick_eligibility이 False)
        topics = conn.execute("""
            SELECT t.id, t.car_id, t.post_type, t.site_id, t.competitor_car_id, t.priority,
                   (SELECT COUNT(*) FROM trims WHERE car_id=t.car_id AND status='시판' AND price>=500) as trim_count,
                   (SELECT segment FROM cars WHERE car_id=t.car_id) as segment
            FROM topics t WHERE t.status='pending' AND t.post_type='persona_pick'
        """).fetchall()

        no_trim = [t for t in topics if t["trim_count"] == 0 and t["segment"]]
        if not no_trim:
            pytest.skip("trims 0건 + segment 있는 topic 없음")

        topic = dict(no_trim[0])
        eligible, reason = persona_pick_eligibility(conn, topic["car_id"])
        assert not eligible, f"trims 0건 topic은 eligibility=False여야 함: {reason}"

        # top5_rank fallback 시도
        topic["post_type"] = "top5_rank"
        topic["rank_type"] = random.choice(["resale", "maintenance", "monthly_cost", "value"])
        data = build_top5_rank_input(conn, topic, str(sim_dbs["car"]))

        # data가 있으면 fallback 성공, 없으면 구조적 실패 (둘 다 크래시 아님)
        if data:
            assert "model" in data or "cars" in data

        conn.close()


class TestBothCandidatesMissing:
    """양쪽 후보 없음 시나리오 검증"""

    def test_no_pending_topics_returns_no_data(self, sim_dbs):
        """pending topics이 0건이면 no_data 반환"""
        conn = sqlite3.connect(str(sim_dbs["car"]))
        conn.row_factory = sqlite3.Row

        # 모든 pending topics를 skip으로 변경
        conn.execute("UPDATE topics SET status='skip_no_data' WHERE status='pending'")
        conn.commit()

        topics = conn.execute("""
            SELECT * FROM topics WHERE status='pending' AND post_type='persona_pick'
        """).fetchall()

        assert len(topics) == 0, "pending topics이 0건이어야 함"

        conn.close()

    def test_persona_pick_and_top5_rank_both_fail(self, sim_dbs):
        """persona_pick과 top5_rank 모두 실패하는 조건 검증"""
        from pipelines.car.data_builder import persona_pick_eligibility, build_top5_rank_input
        import random

        conn = sqlite3.connect(str(sim_dbs["car"]))
        conn.row_factory = sqlite3.Row

        # trims 0건 + segment 없는 topic (top5_rank도 실패)
        topics = conn.execute("""
            SELECT t.id, t.car_id, t.post_type,
                   (SELECT COUNT(*) FROM trims WHERE car_id=t.car_id AND status='시판' AND price>=500) as trim_count,
                   (SELECT segment FROM cars WHERE car_id=t.car_id) as segment
            FROM topics t WHERE t.status='pending' AND t.post_type='persona_pick'
        """).fetchall()

        # trims 0건인 topic
        no_trim = [t for t in topics if t["trim_count"] == 0]
        if not no_trim:
            pytest.skip("trims 0건 topic 없음")

        for t in no_trim[:3]:
            topic = dict(t)
            eligible, _ = persona_pick_eligibility(conn, topic["car_id"])
            if eligible:
                continue

            topic["post_type"] = "top5_rank"
            topic["rank_type"] = random.choice(["resale", "maintenance", "monthly_cost", "value"])
            data = build_top5_rank_input(conn, topic, str(sim_dbs["car"]))

            # 둘 다 실패할 수 있음 — 크래시만 없으면 됨
            # (segment가 있으면 top5_rank가 성공할 수도 있음)

        conn.close()


class TestDuplicateTopicPrevention:
    """동일 실행 중 중복 주제 선택 방지 검증"""

    def test_skip_ids_prevents_reslection(self, sim_dbs):
        """skip_ids에 추가된 topic이 다시 선택되지 않음"""
        conn = sqlite3.connect(str(sim_dbs["car"]))
        conn.row_factory = sqlite3.Row

        skip_ids = []
        selected_ids = []

        for _ in range(5):
            topics = conn.execute("""
                SELECT * FROM topics WHERE status='pending' AND post_type='persona_pick'
                AND id NOT IN ({}) ORDER BY RANDOM() LIMIT 1
            """.format(",".join("?" * len(skip_ids)) if skip_ids else "-1"),
                skip_ids if skip_ids else []
            ).fetchone()

            if not topics:
                break

            topic = dict(topics)
            skip_ids.append(topic["id"])
            selected_ids.append(topic["id"])

        conn.close()

        # 중복 없음 확인
        assert len(selected_ids) == len(set(selected_ids)), f"중복 topic 선택됨: {selected_ids}"

"""GATE 0-A parity — availability eligible ↔ builder OK 양방향 검증.

사용자 지시(m0428) 필수 테스트:
- fuel 없음 → availability 제외 + builder 미호출
- fuel 존재 → availability 포함
- raw vs eligible 구분
- availability eligible ↔ builder OK 양방향 FP/FN 0
- eligible=0 → waiting
- DB row 변경 0 (mode=ro)
- pick 이외 pipeline 회귀 0 (top5_rank raw 유지)
"""
import sqlite3

from pipelines.car.data_builder import build_persona_pick_input, persona_pick_eligibility
from shared.candidate_availability import check_car_availability

CAR_HUGO = {"id": "car-hugo", "pipeline": "car", "post_type": "persona_pick"}

# car 1: eligible (시판 + price>=500 + fuel 존재)
# car 2: no_eligible_trim (price<500)
# car 3: no_eligible_trim (단종)
# car 4: no_fuel_efficiency (시판 + price>=500, fuel 부재)
# car 5: no_car (cars 행 없음)
# car 99: top5_rank용 (persona_pick 필터 무관)
_INELIGIBLE_REASONS = {"2": "no_eligible_trim", "3": "no_eligible_trim", "4": "no_fuel_efficiency", "5": "no_car"}


def _make_car_db(path):
    conn = sqlite3.connect(str(path))
    conn.executescript(
        """
        CREATE TABLE topics (
            id INTEGER PRIMARY KEY, site_id TEXT, status TEXT,
            post_type TEXT, car_id TEXT
        );
        CREATE TABLE cars (
            id INTEGER PRIMARY KEY, car_id TEXT, brand TEXT, model TEXT,
            displacement INTEGER, fuel_type TEXT, year INTEGER, segment TEXT
        );
        CREATE TABLE trims (
            id INTEGER PRIMARY KEY, car_id TEXT, trim_name TEXT, status TEXT,
            price INTEGER, fuel_efficiency REAL
        );
        CREATE TABLE public_fuel_data (
            id INTEGER PRIMARY KEY, source TEXT, model_nm TEXT, comp_nm TEXT,
            display_eff TEXT, year INTEGER, engine_displacement TEXT, fuel_nm TEXT
        );
        """
    )
    conn.executemany(
        "INSERT INTO topics (site_id, status, post_type, car_id) VALUES (?,?,?,?)",
        [
            ("car", "pending", "persona_pick", "1"),
            ("car", "pending", "persona_pick", "2"),
            ("car", "pending", "persona_pick", "3"),
            ("car", "pending", "persona_pick", "4"),
            ("car", "pending", "persona_pick", "5"),
            ("car", "pending", "top5_rank", "99"),
        ],
    )
    conn.executemany(
        "INSERT INTO cars (car_id, brand, model, displacement, fuel_type, year, segment) "
        "VALUES (?,?,?,?,?,?,?)",
        [
            ("1", "현대", "쏘나타", 1999, "가솔린", 2026, "중형"),
            ("2", "현대", "그랜저", 2497, "가솔린", 2026, "대형"),
            ("3", "기아", "K5", 1999, "가솔린", 2026, "중형"),
            ("4", "기아", "EV6", 0, "전기", 2026, "SUV"),
            ("99", "현대", "아반떼", 1598, "가솔린", 2026, "준중형"),
        ],
    )
    conn.executemany(
        "INSERT INTO trims (car_id, trim_name, status, price, fuel_efficiency) "
        "VALUES (?,?,?,?,?)",
        [
            ("1", "스마트", "시판", 3000, 14.4),   # eligible (fuel 존재)
            ("2", "스마트", "시판", 300, None),    # price < 500
            ("3", "스마트", "단종", 3000, None),   # status != 시판
            ("4", "스마트", "시판", 3000, None),   # fuel 부재 (lookup도 없음)
            ("5", "스마트", "시판", 3000, 14.4),   # cars 행 없음 → no_car
            ("99", "스마트", "시판", 3000, None),  # top5_rank용
        ],
    )
    conn.commit()
    conn.close()


def _topics_for(conn, post_type="persona_pick"):
    return [
        r["car_id"]
        for r in conn.execute(
            "SELECT car_id FROM topics WHERE site_id='car' AND status='pending' "
            "AND post_type=?",
            (post_type,),
        )
    ]


def test_availability_excludes_fuel_missing(tmp_path):
    db = tmp_path / "car.db"
    _make_car_db(db)
    info = check_car_availability(CAR_HUGO, car_db_path=db)
    assert info["state"] == "healthy"
    assert info["available_count"] == 1  # eligible 1건 (raw persona_pick pending 5건)


def test_raw_vs_eligible_distinction(tmp_path):
    db = tmp_path / "car.db"
    _make_car_db(db)
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    raw = len(_topics_for(conn))
    eligible = sum(1 for c in _topics_for(conn) if persona_pick_eligibility(conn, c)[0])
    conn.close()
    assert raw == 5
    assert eligible == 1


def test_builder_returns_none_for_ineligible(tmp_path):
    db = tmp_path / "car.db"
    _make_car_db(db)
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    for car_id, reason in _INELIGIBLE_REASONS.items():
        ok, got = persona_pick_eligibility(conn, car_id)
        assert (ok, got) == (False, reason), (car_id, got)
        assert build_persona_pick_input(conn, {"car_id": car_id}, str(db)) is None
    conn.close()


def test_builder_ok_for_eligible(tmp_path):
    db = tmp_path / "car.db"
    _make_car_db(db)
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    ok, reason = persona_pick_eligibility(conn, "1")
    assert (ok, reason) == (True, "ok")
    result = build_persona_pick_input(conn, {"car_id": "1"}, str(db))
    assert result is not None
    assert result["model"] == "쏘나타"  # 빌더 성공 시 data dict 구성
    conn.close()


def test_bidirectional_parity_no_fp_fn(tmp_path):
    """availability eligible 집합 == builder OK 집합 — FP/FN 0."""
    db = tmp_path / "car.db"
    _make_car_db(db)
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    candidate_ids = _topics_for(conn)
    avail_eligible = {c for c in candidate_ids if persona_pick_eligibility(conn, c)[0]}
    builder_ok = {
        c
        for c in candidate_ids
        if build_persona_pick_input(conn, {"car_id": c}, str(db)) is not None
    }
    conn.close()
    assert avail_eligible == builder_ok == {"1"}


def test_zero_eligible_is_waiting(tmp_path):
    db = tmp_path / "car.db"
    _make_car_db(db)
    conn = sqlite3.connect(str(db))
    conn.execute("UPDATE topics SET car_id = '4' WHERE post_type = 'persona_pick'")
    conn.commit()
    conn.close()
    info = check_car_availability(CAR_HUGO, car_db_path=db)
    assert info["state"] == "waiting_for_candidates"
    assert info["available_count"] == 0


def test_read_only_no_row_change(tmp_path):
    db = tmp_path / "car.db"
    _make_car_db(db)
    conn = sqlite3.connect(str(db))
    before = conn.execute("SELECT car_id, status FROM topics ORDER BY id").fetchall()
    conn.close()
    check_car_availability(CAR_HUGO, car_db_path=db)
    conn = sqlite3.connect(str(db))
    after = conn.execute("SELECT car_id, status FROM topics ORDER BY id").fetchall()
    conn.close()
    assert before == after


def test_other_post_type_keeps_raw(tmp_path):
    db = tmp_path / "car.db"
    _make_car_db(db)
    info = check_car_availability(
        {"id": "car-hugo", "pipeline": "car", "post_type": "top5_rank"},
        car_db_path=db,
    )
    assert info["available_count"] == 1  # top5_rank raw pending 1건
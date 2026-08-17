"""커밋 D + stabilization — car persona_pick effective availability 회귀 테스트.

- persona_pick 단독 blog: SSOT 헬퍼(data_builder.persona_pick_eligibility) 기준
  eligible 후보만 카운트 — cars 행 + 시판+price>=500 trim + 대표 트림 fuel 존재
- persona_pick 외 post_type / post_types 생략: 기존 raw pending 카운트 유지
- check_car_availability는 DB 읽기 전용 (mode=ro) — 테스트도 쓰기 없음
"""
import sqlite3

from shared.candidate_availability import check_car_availability

CAR_HUGO = {"id": "car-hugo", "pipeline": "car", "post_type": "persona_pick"}


def _make_car_db(path):
    conn = sqlite3.connect(str(path))
    conn.executescript(
        """
        CREATE TABLE topics (
            id INTEGER PRIMARY KEY, site_id TEXT, status TEXT,
            post_type TEXT, car_id INTEGER
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
    # persona_pick pending 3건 — eligible은 1건만 (car 1: 시판+price>=500+fuel 존재)
    conn.executemany(
        "INSERT INTO topics (site_id, status, post_type, car_id) VALUES (?,?,?,?)",
        [
            ("car", "pending", "persona_pick", "1"),
            ("car", "pending", "persona_pick", "2"),
            ("car", "pending", "persona_pick", "3"),
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
            ("99", "현대", "아반떼", 1598, "가솔린", 2026, "준중형"),
        ],
    )
    conn.executemany(
        "INSERT INTO trims (car_id, trim_name, status, price, fuel_efficiency) "
        "VALUES (?,?,?,?,?)",
        [
            ("1", "스마트", "시판", 3000, 14.4),   # eligible (fuel 존재)
            ("2", "스마트", "시판", 300, None),    # price < 500 → ineligible
            ("3", "스마트", "단종", 3000, None),   # status != 시판 → ineligible
            ("99", "스마트", "시판", 3000, None),  # top5_rank용 — persona_pick 필터 무관
        ],
    )
    conn.commit()
    conn.close()


def test_persona_pick_effective_count(tmp_path):
    db = tmp_path / "car.db"
    _make_car_db(db)
    info = check_car_availability(CAR_HUGO, car_db_path=db)
    assert info["state"] == "healthy"
    assert info["available_count"] == 1  # eligible 1건 (raw pending은 3건)


def test_persona_pick_zero_eligible_is_waiting(tmp_path):
    db = tmp_path / "car.db"
    _make_car_db(db)
    conn = sqlite3.connect(str(db))
    conn.execute("UPDATE topics SET car_id = '2' WHERE car_id = '1'")  # eligible 제거
    conn.commit()
    conn.close()
    info = check_car_availability(CAR_HUGO, car_db_path=db)
    assert info["state"] == "waiting_for_candidates"
    assert info["available_count"] == 0


def test_other_post_type_keeps_raw_pending(tmp_path):
    db = tmp_path / "car.db"
    _make_car_db(db)
    info = check_car_availability(
        {"id": "car-hugo", "pipeline": "car", "post_type": "top5_rank"},
        car_db_path=db,
    )
    assert info["available_count"] == 1  # raw pending 1건 (필터 없음)


def test_no_post_type_keeps_raw_pending(tmp_path):
    db = tmp_path / "car.db"
    _make_car_db(db)
    info = check_car_availability(
        {"id": "car-hugo", "pipeline": "car"}, car_db_path=db
    )
    assert info["available_count"] == 4  # site_id 전체 raw pending
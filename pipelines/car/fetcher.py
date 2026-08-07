"""CAP(car) 파이프라인 표준 골격 — fetcher (Phase 61, D-01).

표준 6-모듈 골격(pipeline/fetcher/topic_manager/writer/enrich/validator)의 일부.
car 분기는 독립적인 fetcher 모듈이 없었고, 데이터 수집·빌드가
`pipelines/car/data_builder.py` 의 `build_input()` 및 전용 빌더
(`build_top5_rank_input` / `build_persona_pick_input` / `build_price_trend_input`)
로 수행되어 `pipelines/car/pipeline.py::run()` 내부에서 오케스트레이션된다.

이 모듈은 기존 `data_builder.build_input()` 을 **위임**한다 (D-01 additive, 로직 중복 없음).
기존 `pipeline.run(blog_cfg)` 은 여전히 `build_input()` 을 직접 호출하므로 동작은 그대로다.
"""


def fetch_data(cfg, conn=None, topic=None, db_path=None):
    """차량 데이터 빌드 — 기존 `data_builder.build_input()` 을 위임.

    car 분기의 데이터 수집은 pipeline.run() 내부에서 conn + topic 을 확정한 뒤
    `data_builder.build_input(conn, topic, db_path)` 로 수행된다. 이 wrapper는
    동일 경로로 위임하며, 오케스트레이션(토픽 선택·가드)은 pipeline.run() 에 유지된다.

    Args:
        cfg: 블로그 설정 dict (id 사용).
        conn: car.db sqlite3.Connection (row_factory=sqlite3.Row).
        topic: 토픽 dict (car_id, competitor_car_id, post_type 포함).
        db_path: car.db 경로 (없으면 shared.db.get_db_path('car') 사용).
    Returns:
        build_input() 결과 dict, 데이터 없거나 차단 시 None.
    """
    from pipelines.car.data_builder import build_input

    if db_path is None:
        from shared.db import get_db_path
        db_path = get_db_path("car")
    if conn is None or topic is None:
        raise ValueError("car fetcher: conn 과 topic 은 필수입니다.")
    return build_input(conn, topic, db_path)

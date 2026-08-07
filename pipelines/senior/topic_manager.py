"""시니어(SEAP) 파이프라인 표준 골격 — topic_manager (Phase 61, D-01).

표준 6-모듈 골격(pipeline/fetcher/topic_manager/writer/enrich/validator)의 일부.
시니어 분기는 독립적인 topic_manager 모듈이 없었고, 토픽 선택 로직이
`pipelines/senior/pipeline.py::_pick_topic()` 에 인라인되어 있다.

이 모듈은 **pass-through placeholder** — 기존 인라인 선택 함수 `_pick_topic()` 을
위임한다. 실제 선택 로직을 중복하지 않는다 (D-01 additive). 기존 `pipeline.run(cfg)` 은
여전히 `_pick_topic()` 을 직접 호출하므로 동작은 그대로다.
"""


def select_topic(cfg, services=None):
    """토픽(카테고리) 선택 — 기존 `pipeline._pick_topic()` 을 위임.

    Args:
        cfg: 블로그 설정 dict (id 사용).
        services: 서비스 목록 (선택). 기본 None이면 pipeline의 동작대로 빈 목록 사용.
    Returns:
        선택된 토픽(카테고리) 문자열.
    """
    from pipelines.senior.pipeline import _pick_topic

    blog_id = cfg.get("id", "senior-hugo")
    return _pick_topic(blog_id, services or [])

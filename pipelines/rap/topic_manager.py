"""RAP(부동산) 파이프라인 표준 골격 — topic_manager (Phase 61, D-01).

표준 6-모듈 골격(pipeline/fetcher/topic_manager/writer/enrich/validator)의 일부.
RAP 분기는 독립적인 topic_manager 모듈이 없었고, 키워드 선택 로직이
`pipelines/rap/pipeline.py::_pick_keyword()` 와 `_pick_strategy()` 에 인라인되어 있다.

이 모듈은 **pass-through placeholder** — 기존 인라인 선택 함수 `_pick_keyword()` 를
위임한다. 실제 선택 로직을 중복하지 않는다 (D-01 additive). 기존 `pipeline.run(blog_cfg)` 은
여전히 `_pick_keyword()` 를 직접 호출하므로 동작은 그대로다.
"""


def select_topic(cfg):
    """키워드(토픽) 선택 — 기존 `pipeline._pick_keyword()` 를 위임.

    Args:
        cfg: 블로그 설정 dict (id 사용).
    Returns:
        (keyword, category) 튜플. keyword가 없으면 (None, None).
    """
    from pipelines.rap.pipeline import _pick_keyword

    blog_id = (cfg or {}).get("id", "rap-hugo")
    return _pick_keyword(blog_id)

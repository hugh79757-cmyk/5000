"""curation(상품 큐레이션) 파이프라인 표준 골격 — topic_manager (Phase 61, D-01).

표준 6-모듈 골격(pipeline/fetcher/topic_manager/writer/enrich/validator)의 일부.
curation 분기는 독립적인 topic_manager 모듈이 없었고, 키워드 선택 로직이
`pipelines/curation/pipeline.py::_select_keyword()` 에 인라인되어 있다.

이 모듈은 **pass-through placeholder** — 기존 인라인 선택 함수 `_select_keyword()`
를 위임한다. 실제 선택 로직을 중복하지 않는다 (D-01 additive). 기존
`pipeline.run(cfg)` 은 여전히 `_select_keyword()` 를 직접 호출하므로 동작은 그대로다.
"""


def select_topic(cfg):
    """토픽(키워드) 선택 — 기존 `pipeline._select_keyword()` 를 위임.

    Args:
        cfg: 블로그 설정 dict (id 사용).
    Returns:
        선택된 키워드 문자열. 사용 가능한 키워드가 없으면 None.
    """
    from pipelines.curation.pipeline import _select_keyword

    blog_id = (cfg or {}).get("id", "")
    return _select_keyword(blog_id)

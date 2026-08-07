"""여행(TAP) 파이프라인 표준 골격 — topic_manager (Phase 61, D-01).

표준 6-모듈 골격(pipeline/fetcher/topic_manager/writer/enrich/validator)의 일부.
travel 분기는 독립적인 topic_manager 모듈이 없었고, 토픽(소스 유형 + 지역) 선택 로직이
`pipelines/travel/pipeline.py::_fetch_for_blog()` 와 `BLOG_FETCH_MAP` 에 인라인되어 있다.

이 모듈은 **pass-through placeholder** — 기존 인라인 선택 경로 `_fetch_for_blog()` 를
위임한다. 실제 선택/수집 로직을 중복하지 않는다 (D-01 additive). 기존 `pipeline.run(cfg)` 은
여전히 `_fetch_for_blog()` 를 직접 호출하므로 동작은 그대로다.

참고: travel 분기의 토픽 선택은 곧 "어느 fetcher(source_type)로 데이터를 가져올지" 선택이다
(BLOG_FETCH_MAP 가중치 + 시군구 가드). 이 wrapper는 그 경로를 그대로 위임한다.
"""


def select_topic(cfg):
    """토픽(소스 유형 + 데이터) 선택 — 기존 `pipeline._fetch_for_blog()` 를 위임.

    Args:
        cfg: 블로그 설정 dict (id 사용).
    Returns:
        선택된 데이터 dict (items/source_type/sigungu/content_ids 포함) 또는 None.
        None이면 사용 가능한 소스가 없음(단일 소스 실패 등)을 의미.
    """
    from pipelines.travel.pipeline import _fetch_for_blog

    blog_id = cfg.get("id", "travel-hugo")
    return _fetch_for_blog(blog_id)

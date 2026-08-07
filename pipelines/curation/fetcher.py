"""curation(상품 큐레이션) 파이프라인 표준 골격 — fetcher (Phase 61, D-01).

표준 6-모듈 골격(pipeline/fetcher/topic_manager/writer/enrich/validator)의 일부.
curation 분기는 독립적인 fetcher 모듈이 없었고, 상품 데이터 수집이
`pipelines/curation/collector.py` 의 `collect_keyword()` / `get_products()` 로
pipeline.py 내부에서 수행된다.

이 모듈은 **pass-through placeholder** — 기존 collector 수집 경로를 위임한다.
실제 수집 로직을 중복하지 않는다 (D-01 additive). 기존 `pipeline.run(cfg)` 은
여전히 collector 를 직접 호출하므로 동작은 그대로다.
"""


def fetch_data(cfg):
    """상품 데이터 수집 — 기존 collector 수집 경로를 위임.

    Args:
        cfg: 블로그 설정 dict (id, keyword 사용).
    Returns:
        수집된 상품 list (dict). 키워드 부재 시 빈 list.
    """
    from pipelines.curation.collector import collect_keyword, get_products
    from pipelines.curation.pipeline import _select_keyword

    blog_id = (cfg or {}).get("id", "")
    keyword = (cfg or {}).get("keyword", "") or _select_keyword(blog_id)
    if not keyword:
        return []
    collect_keyword(keyword)
    return get_products(keyword, limit=10)

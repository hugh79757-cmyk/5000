"""curation(상품 큐레이션) 파이프라인 표준 골격 — enrich (Phase 61, D-01).

표준 6-모듈 골격(pipeline/fetcher/topic_manager/writer/enrich/validator)의 일부.
curation 분기는 기존 `enricher.py`(상품명 파싱 + 네이버 쇼핑 API brand/maker 보강)가
이미 존재한다. 표준 골격 이름 `enrich` 로 이 기존 `enricher.py` 를 배선(wire)한다.

기존 `enricher.py` 는 **유지**하고 (D-01 additive), 표준 이름으로 재노출만 한다.
실제 엔리치먼트 로직을 중복하지 않는다.
"""


def enrich_content(cfg, products):
    """상품 리스트 엔리치 — 기존 `enricher.enrich_products` 를 위임.

    Args:
        cfg: 블로그 설정 dict (id 사용).
        products: 상품 dict 리스트.
    Returns:
        엔리치된 상품 리스트 (각 상품에 parsed_specs/brand 등 추가).
    """
    from pipelines.curation.enricher import enrich_products

    blog_id = (cfg or {}).get("id", "")
    return enrich_products(products, blog_id)

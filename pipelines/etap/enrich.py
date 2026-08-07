"""pipelines/etap/enrich.py — ETAP 표준 골격 enrich wrapper (Phase 61, D-01).

표준 6-모듈 골격의 enrich 역할. ETAP 파이프라인은 `post_processor`(AdSense/상품 카드/
크로스셀)와 `shared/entity_linker`(내부 링크)로 엔리치먼트를 수행한다. 이 wrapper는
기존 로직으로 위임한다(재작성 없음, D-08).

주요 진입점:
- `enrich_content(cfg, body_md)` -> body_md : 공통 엔리치먼트(AdSense + 내부 링크) 적용.
"""
import logging

from pipelines.etap.post_processor import insert_adsense
from shared.entity_linker import inject_internal_links

logger = logging.getLogger(__name__)


def enrich_content(cfg, body_md, blog_id=None) -> str:
    """body_md에 공통 엔리치먼트(AdSense + 내부 링크)를 적용한다.

    기존 `post_processor.insert_adsense` / `entity_linker.inject_internal_links`로
    위임한다. 고급 엔리치먼트(상품 카드/크로스셀)는 각 토픽 파이프라인이
    필요에 따라 직접 호출하므로 여기서는 최소 공통 적용만 담당한다 (Phase 61 골격).
    """
    if not body_md:
        return body_md
    if not blog_id:
        blog_id = (cfg or {}).get("id", "")
    try:
        body_md = insert_adsense(body_md)
    except Exception as e:  # 엔리치먼트 실패 시 원문 보존 (비치명적)
        logger.warning("[etap.enrich] insert_adsense failed: %s", e)
    try:
        body_md = inject_internal_links(body_md, current_blog=blog_id, max_links=5)
    except Exception as e:
        logger.warning("[etap.enrich] inject_internal_links failed: %s", e)
    return body_md


__all__ = ["enrich_content"]

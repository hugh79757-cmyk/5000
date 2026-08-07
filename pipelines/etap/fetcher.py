"""pipelines/etap/fetcher.py — ETAP 표준 골격 fetcher wrapper (Phase 61, D-01).

표준 6-모듈 골격(pipeline/fetcher/topic_manager/writer/enrich/validator)의
fetcher 역할. ETAP 토픽 파이프라인들은 데이터 수집을 `topic_manager.pick_topic_by_id`
로 수행하고, 이미지는 `image_fetcher`에서 가져온다. 이 wrapper는 기존
`image_fetcher`/`tour_utils`로 위임한다(재작성 없음, D-08).

주요 진입점:
- `fetch_data(cfg, city, country, slug)` -> list : 도시/본문 이미지 목록 반환.
"""
import logging

from pipelines.etap.image_fetcher import fetch_body_images, fetch_city_image
from pipelines.etap.tour_utils import fetch_city_meta

logger = logging.getLogger(__name__)


def fetch_data(cfg, city="", country="", slug="", count=3) -> list:
    """ETAP 데이터(이미지) 수집 — 기존 image_fetcher로 위임.

    cover(대표 이미지) + body(본문 이미지)를 딕셔너리 목록으로 반환한다.
    cfg는 위임 호환성을 위해 받되, ETAP 토픽 데이터는 topic_manager에서
    이미 선택되므로 여기서는 이미지 수집만 담당한다 (Phase 61 골격 위임).
    """
    result = []
    cover = fetch_city_image(city, country, slug) if city else None
    if cover:
        result.append({"type": "cover", **cover})
    body = fetch_body_images(city, country, slug, count=count) if city else []
    for img in body:
        result.append({"type": "body", **img})
    if not result:
        logger.info("[etap.fetcher] fetch_data: no images collected")
    return result


def fetch_city_meta_data(city):
    """도시 메타데이터 조회 — 기존 tour_utils.fetch_city_meta로 위임."""
    return fetch_city_meta(city)


__all__ = ["fetch_data", "fetch_city_meta_data"]

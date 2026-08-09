"""
app_images.core — images:// URL 생성 및 검증 모듈

PPM-5: images:// URL 생성 로직에 정규 표현식 검증 추가.
유효한 images:// 스킴만 생성되도록 하여 의도치 않은 호출을 방지.
"""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# images:// URL 패턴 — ^images://로 시작하는 문자열만 허용
IMAGES_URL_PATTERN = re.compile(r"^images://")

# 유효 스킴 패턴 (images:// 또는 https:// 등)
VALID_SCHEME_PATTERN = re.compile(r"^(images://|https?://)")


def _validate_images_url(url: Optional[str]) -> bool:
    """images:// URL이 유효한지 검증.

    Args:
        url: 검증할 URL 문자열 (None 허용)

    Returns:
        유효하면 True, 유효하지 않거나 None이면 False
    """
    if url is None:
        return False
    return bool(IMAGES_URL_PATTERN.match(url))


def _build_images_asset_path(path: str, use_images_scheme: bool = True) -> Optional[str]:
    """이미지 asset 경로를 생성.

    args:
        path: 이미지 경로 (예: "images/kingsdalecc/thumbnail.webp")
        use_images_scheme: True이면 images:// 스킴 사용, False이면 None 반환

    returns:
        유효한 images:// URL 또는 None (검증 실패 시)
    """
    if not path:
        logger.warning("_build_images_asset_path: empty path provided")
        return None

    if use_images_scheme:
        url = f"images://{path}"
        # 정규식 검증 — 유효하지 않은 images:// URL 생성 거부
        if not _validate_images_url(url):
            logger.error("_build_images_asset_path: generated invalid images:// URL: %s", url)
            return None
        return url

    return None


def normalize_hugo_asset_url(url: Optional[str], base_url: Optional[str] = None) -> Optional[str]:
    """Hugo asset URL 정규화.

    images:// 스킴을 Hugo가 인식할 수 있는 절대 URL로 변환.
    base_url이 없으면 None 반환 ( FrontMatter 삭제 방지용 안전 가드).

    args:
        url: 정규화할 URL (images:// 또는 https:// 등)
        base_url: Hugo 베이스 URL (HUGO_BASEURL 또는 ASSET_DOMAIN)

    returns:
        정규화된 절대 URL 또는 None
    """
    if url is None:
        return None

    # images:// 스킴인 경우
    if IMAGES_URL_PATTERN.match(url):
        if not base_url:
            logger.warning(
                "normalize_hugo_asset_url: images:// URL but no base_url provided — returning None"
            )
            return None
        # images:// 경로를 추출하여 base_url과 결합
        path = url.replace("images://", "", 1)
        return f"{base_url.rstrip('/')}/{path.lstrip('/')}"

    # 이미 절대 URL인 경우 그대로 반환
    if VALID_SCHEME_PATTERN.match(url):
        return url

    logger.warning("normalize_hugo_asset_url: unrecognized URL scheme: %s", url)
    return None

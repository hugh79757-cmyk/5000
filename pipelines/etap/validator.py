"""pipelines/etap/validator.py — ETAP 표준 골격 validator wrapper (Phase 61, D-01).

표준 6-모듈 골격의 validator 역할. 발행 전/후 검증(품질 게이트·이미지 URL·CJK 누수)을
`shared/validators.validate_post` / `shared/post_validator.validate_post_html`로
위임한다(재작성 없음, D-08). ETAP(영문) 파이프라인은 quality_guard
`postprocess_content`를 주 검증 수단으로 사용하므로, 이 wrapper는 표준 골격 배선용
얇은 위임이다.

주요 진입점:
- `validate_post(cfg, article)` -> (ok, errors)
"""
import logging

from shared.post_validator import validate_post_html
from shared.validators import validate_post as _validate_post_shared

logger = logging.getLogger(__name__)


def validate_post(cfg, article) -> tuple:
    """article(title/body_md) 검증. (ok: bool, errors: list) 반환.

    shared/post_validator.validate_post_html로 위임한다. HTML 문맥에서 키워드 커버리지/
    구조를 검증하고, 실패 사유를 errors 목록으로 반환한다. 실패 시에도 파이프라인이
    중단되지 않도록 오류는 로그만 남긴다 (비치명적, graceful degradation).
    """
    errors = []
    if not isinstance(article, dict) or not article.get("title") or not article.get("body_md"):
        errors.append("missing title/body_md")
        return False, errors
    blog_id = (cfg or {}).get("id", "")
    try:
        report = validate_post_html(article["body_md"], blog_id)
        if isinstance(report, dict) and report.get("ok") is False:
            errors.append(report.get("errors", []))
    except Exception as e:
        logger.warning("[etap.validator] validate_post_html failed: %s", e)
    return (len(errors) == 0), errors


__all__ = ["validate_post"]

"""시니어(SEAP) 파이프라인 표준 골격 — validator (Phase 61, D-01).

표준 6-모듈 골격(pipeline/fetcher/topic_manager/writer/enrich/validator)의 일부.
시니어 분기는 독립적인 validator 모듈이 없었고, 검증이 `shared.validators` 의
`validate_post_extended(..., pipeline="senior")` 호출로 pipeline.py 에 인라인되어 있다.

이 모듈은 해당 기존 shared 검증을 **위임**한다 (D-01 additive, 로직 중복 없음).
기존 `pipeline.run()` 의 검증 경로는 그대로 두며, 이 wrapper는 골격 계약
`validate_post(cfg, article) -> (ok: bool, errors: list[str])` 을 제공한다.
"""


def validate_post(cfg, article):
    """발행 전 검증 — `shared.validators.validate_post_extended` 를 위임.

    Args:
        cfg: 블로그 설정 dict (id 사용).
        article: 글 dict (title, body_md, keyword, event_date 등).
    Returns:
        (ok: bool, errors: list[str]) — ok=False 이면 errors에 검증 이슈 목록.
    """
    from shared.validators import validate_post_extended

    blog_id = cfg.get("id", "senior-hugo")
    title = (article or {}).get("title", "")
    body_md = (article or {}).get("body_md", "")
    ctx = {
        "keyword": (article or {}).get("keyword", ""),
        "event_date": (article or {}).get("event_date", (article or {}).get("policy_date", "")),
        "daily_quota": 5,
    }
    issues = validate_post_extended(blog_id, title, body_md, ctx, pipeline="senior")
    return (not issues), list(issues or [])

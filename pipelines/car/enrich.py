"""CAP(car) 파이프라인 표준 골격 — enrich (Phase 61, D-01).

표준 6-모듈 골격(pipeline/fetcher/topic_manager/writer/enrich/validator)의 일부.
car 분기는 독립적인 enrich 모듈이 없었고, 본문 엔리치먼트(광고·내부 링크·크로스셀) 단계가
`pipelines/car/pipeline.py::run()` 의 발행 경로에 존재하지 않는다.

이 모듈은 **pass-through placeholder** — car 분기는 `(cfg, body_md) -> body_md`
시그니처의 독립 엔리치먼트 단계가 없으므로 본문을 그대로 반환한다.
실제 본문 정제는 `pipeline.run()` → `validate_body()` 경로에서 이미 수행되며,
이 wrapper는 골격 완성을 위한 자리표시자이다 (D-01 additive).
"""


def enrich_content(cfg, body_md):
    """본문 엔리치먼트 placeholder — body_md를 그대로 반환.

    car 분기는 독립 enrich 단계가 없어 본문 정제는 topic_manager.validate_body()
    내부에서 수행된다. 여기서 다시 적용하면 중복 삽입이 될 수 있어,
    골격 계약만 충족하며 원문을 유지한다.

    Args:
        cfg: 블로그 설정 dict.
        body_md: 엔리치먼트할 본문 Markdown.
    Returns:
        body_md (변경 없음).
    """
    return body_md

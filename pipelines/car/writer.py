"""CAP(car) 파이프라인 표준 골격 — writer (Phase 61, D-01).

표준 6-모듈 골격(pipeline/fetcher/topic_manager/writer/enrich/validator)의 일부.
car 분기는 독립적인 writer 모듈이 없었고, 글 생성이
`shared.ai_writer.generate_car(prompt_text, data)` 로 수행되고
본문 정제가 `pipelines/car/topic_manager.validate_body(body, data)` 로 수행되어
`pipelines/car/pipeline.py::run()` 내부에 인라인되어 있다.

이 모듈은 위 기존 생성·정제 경로를 **위임**한다 (D-01 additive, 로직 중복 없음).
기존 `pipeline.run(blog_cfg)` 은 여전히 직접 호출하므로 동작은 그대로다.
"""


def write_article(cfg, topic, data=None, prompt_text=None):
    """글 본문 생성 — `shared.ai_writer.generate_car` + `topic_manager.validate_body` 위임.

    car 분기의 글 생성은 pipeline.run() 에서 프롬프트 파일을 읽어
    `generate_car(prompt_text, data)` 로 수행되고 `validate_body()` 로 정제된다.
    이 wrapper는 동일 경로로 위임하며, 프롬프트 로딩·재생성 루프는 pipeline.run() 에 유지된다.

    Args:
        cfg: 블로그 설정 dict (id 사용).
        topic: 토픽 dict.
        data: data_builder 결과 dict.
        prompt_text: 프롬프트 텍스트 (없으면 위임 대상 함수가 인자로 받도록 요구).
    Returns:
        본문 Markdown str, 생성 실패 시 None.
    """
    if prompt_text is None:
        raise ValueError("car writer: prompt_text 은 필수입니다.")
    if data is None:
        raise ValueError("car writer: data 는 필수입니다.")

    from shared.ai_writer import generate_car
    from pipelines.car.topic_manager import validate_body

    body = generate_car(prompt_text, data)
    if not body:
        return None
    return validate_body(body, data)

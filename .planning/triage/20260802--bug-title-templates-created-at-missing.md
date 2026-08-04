# BUG: title_templates recent styles query — `no such column: created_at`

> **등록일**: 2026-08-02
> **발견 맥락**: Phase 55 after 측정 시도 중, `generate_curation_article()` 호출 시마다 반복 발생
> **실행 수정**: 없음 (이번 범위 외)

## 재현 조건

```python
from pipelines.curation.writer import generate_curation_article
generate_curation_article("비타민C 세럼 추천", products, blog_id="beauty-hugo")
```

## 에러 메시지

```
[title_templates] 최근 스타일 조회 실패: no such column: created_at
```

## 발생 위치

`shared/title_templates.py` 또는 `pipelines/curation/writer.py:637-662` — `_tt_picker.get_recent_styles(blog_id)` 호출 시

`writer.py:668-676` 의 recent_titles 쿼리도 `published_at`을 사용하나 이쪽은 정상 동작. 문제는 `_tt_picker.get_recent_styles()` 내부 쿼리에서 `created_at` 컬럼을 참조하나, 해당 테이블에 이 컬럼이 없는 것으로 보임.

## 영향

- 치명적 아님 — except 블록에서 경고 후 계속 진행
- 단, 제목 스타일 다양화가 매번 비활성화되어 동일 패턴 반복 가능성

## 발견 경로

Phase 55 before/after 벤치마크 측정 중 `generate_curation_article()` 호출 로그에서 확인. 이전 Phase 54 테스트에서도 동일 로그 존재했으나 무시됨.

## 복구 계획

`title_templates` 테이블 스키마 확인 → `created_at` 컬럼 추가 또는 쿼리 수정 (별도 작업으로 이연)

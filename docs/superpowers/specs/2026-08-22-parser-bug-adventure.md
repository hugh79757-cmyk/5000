# Track A — Exp1 Parser Bug: FM-MISSINGKEYS 거짓양성 (adventure-hugo 중심)

> 상태: DESIGN ONLY (수정 금지). Exp2 범위에서 처리 권고.

## bug_description
`ops_dashboard/checks/content_integrity._parse_frontmatter` (라인 126-138)는
frontmatter를 단순 regex로 파싱한다 — 각 라인을 첫 `:`에서 분리해 값을 스칼라
문자열로 취한다. block-style YAML 리스트는:

```yaml
tags:
  - uncategorized
  - paragliding
```

첫 라인 `tags:`의 값이 빈 문자열이 되고, 하위 `- item` 라인은 `:`가 없어 무시된다.
결과: `fm.get('tags')` == "" → `check_frontmatter`가 "누락 [tags]"로 오판.

python-frontmatter 라이브러리는 block-style을 정상 파싱하므로, 동일 파일을
`frontmatter.loads()`로 읽으면 tags가 존재한다.

## affected_scope
- adventure-hugo: 133건 (전부 `tags` 누락으로 플래그, 실제로는 block-style로 존재)
- 동일 파서(`_parse_frontmatter`)를 사용하는 전체 블로그의 FM-MISSINGKEYS fail
  (check_results 집계 기준 77개 blog, blog당 1행 = 다수 포스트 집계) — 대다수가
  block-style tags 거짓양성일 가능성 높음.

## root_cause
`content_integrity._parse_frontmatter` (regex per-line) vs `python-frontmatter`
(lib) 불일치. 체커는 전자를, 실제 데이터는 후자 규격(YAML 블록 리스트)을 따름.

## proposed_fix
1. `check_frontmatter`가 frontmatter 파싱에 `python-frontmatter` 라이브러리를
   정규 파서로 채택 (또는 `_parse_frontmatter`가 block-style/list 지원 추가).
2. 단, `_parse_frontmatter`는 10+ 체커(C01~C0x)에서 공용으로 사용 → 교체 시
   연쇄 영향 격리 테스트 필수.

## risk_assessment
- 파서 교체 → 다른 체커 결과 변동 가능 (기존 위양/위음 판정 뒤집힘).
- 따라서 Exp1은 해당 행 자동 제외(선정 로직에서 python-frontmatter 교차검증),
  실제 파서 수정은 Exp2에서 격리 테스트와 함께 진행.

## recommendation
- Exp1: `ops_dashboard/exp1_selector.py`의 `_fm_missingkeys_false_positive()`로
  FM-MISSINGKEYS 거짓양성을 선정 단계에서 차단. adventure-hugo는 PARSER_BUG_BLOGS로
  일괄 제외.
- Exp2: `content_integrity._parse_frontmatter` → python-frontmatter 전환 + 회귀 테스트.

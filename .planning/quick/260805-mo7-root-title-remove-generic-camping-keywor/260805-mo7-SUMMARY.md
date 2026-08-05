---
phase: quick-260805-mo7
plan: 1
status: complete
type: execute
wave: 1
depends_on: []
requirements:
  - Q-20260805-camping-generic-keywords
files_modified:
  - pipelines/curation/keywords.py
commit: ca9f9e7ad
metrics:
  duration_minutes: 8
  tasks: 1
  files: 1
---

# Quick Task 260805-mo7: camping-hugo 일반명 키워드('조명'/'난로'/'선풍기') 제거

**One-liner:** camping-hugo KEYWORD_MAP에서 일반명 키워드 3개('선풍기'/'난로'/'조명')를 제거해 쿠팡 검색의 "가정용 전기제품" 반환 → low_relevance 발행 실패 → 90일 격리 위험 경로를 차단. KEYWORD_MAP 2985→2982. 대체 키워드('캠핑 조명/난로/선풍기 추천') 기존 존재로 커버리지 손실 없음.

## Task Completion

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | camping-hugo KEYWORD_MAP에서 '조명'/'난로'/'선풍기' 3개 제거 | `ca9f9e7ad` | pipelines/curation/keywords.py (3 deletions) |

## Verification (3-way classification)

### [검증됨]

- **KEYWORD_MAP 총 키워드 수 2982** (2985−3).
  근거: `.venv/bin/python3 -c` assert 실행 결과 `OK total=2982 camping(len=248) 난로잔존=1 appliance선풍기=2` — total=2982 통과.
- **camping-hugo 목록에 '조명'/'선풍기' 부재.**
  근거: 동일 assert에서 `'조명' not in c and '선풍기' not in c` 통과 (조명/선풍기 제거 실패 시 AssertionError 발생 구조).
- **camping-hugo '난로'는 1108행 확장 라인 1건만 잔존** (범위 밖, 잔존 위험 보고 대상).
  근거: assert `c.count('난로') == 1` 통과. 단, 이 검증은 값 일치 검증이라 위치(1108행)는 수동 확인 — git diff로 1052~1054행 3라인 삭제만 확인됨(아래).
- **appliance-hugo '선풍기' 유지** (212행·263행 2건).
  근거: assert `'선풍기' in a` 통과 + `grep -n '"선풍기"'` 사전 확인 결과 212행·263행 존재.
- **py_compile 문법 검증 통과.**
  근거: `py_compile pipelines/curation/keywords.py` → "py_compile OK" 출력.
- **git diff = 순수 3라인 삭제.**
  근거: `git diff --stat` → `1 file changed, 3 deletions(-)`. diff 본문 = 1052~1054행 `"선풍기"/"난로"/"조명"` 3줄 삭제만 존재, 추가/수정 0줄.
- **커밋에 의도치 않은 삭제 없음.**
  근거: `git show --stat ca9f9e7ad` → keywords.py 1개 파일만 변경, `git diff --diff-filter=D HEAD~1 HEAD` 결과 0건(키워드 3개 삭제는 `-` 라인 삭제이지 tracked file 삭제가 아님).

### [부분검증]

- **test_keywords.py 실패 셋 수정 전후 동일 — 신규 회귀 0건.**
  근거: 수정 전 실행 결과 `4 failed, 3 passed in 0.03s`(실패 4개: test_all_10_blogs_present / test_each_blog_has_60_to_200_keywords / test_no_generic_keywords_remain / test_get_keywords_all_blogs_have_unique_keywords)와 수정 후 실행 결과 동일 `4 failed, 3 passed in 0.03s` — 동일 실패 4건, 동일 통과 3건.
  제한 사유: 이 검증은 "실패 셋이 늘지 않았음"만 증명. "기존 실패가 이번 수정으로 우연히 통과했는지"는 확인하지 못함 — 단, camping-hugo 키워드 제거는 실패 항목 4개(블로그 수 15 > 10, 60~200 상한 위반, generics 셋 미포함, 중복)와 인과 관계가 없고, 실패 셋이 정확히 동일하므로 회귀 없음 판단은 유효.

### [검증불가]

- 없음. (테스트 코드 수정 없음 — [PRODUCTION CODE]만 수정, [TEST CODE]/[CONFIG] 무수정. 테스트 4건 실패는 작업 전후 동일하므로 순환 검증 아님.)

## Deviations from Plan

- **계획 문서의 기준선 예측과 실제 기준선 불일치 (실행 변경 아님, 보고용):**
  계획은 "기준선 3 failed + 1 deselected (test_all_10_blogs_present deselected 시)"를 예측했으나, 실제 실행 결과는 `4 failed, 3 passed` (test_all_10_blogs_present가 deselected가 아닌 **failed**)였다.
  원인 추정: `tests/curation/test_keywords.py`의 `test_all_10_blogs_present`는 `len(KEYWORD_MAP) == 10`을 검증하는데 현재 KEYWORD_MAP에 15개 블로그가 존재 → skip/deselect 조건 없이 그냥 실패. 계획 작성 시점과 실행 시점 사이 테스트 상태 차이로 보임.
  처리: 계획의 핵심 불변식("수정 전후 동일 실패 셋 — 신규 실패 금지")을 기준으로 실행. 수정 전후 동일 4건 실패 확인. 테스트 코드는 미수정(계획 금지 준수). 이 불일치는 실행 결과에 영향 없음.

## 잔존 위험 (AGENTS.md Section 6)

1. **camping-hugo 목록 1108행 확장 라인에 `"난로"` 1건 잔존** — 사용자 결정(1052~1054행 3개 요소만 제거, count 2982 확정)에 따라 범위 밖으로 유지됨. 동일 문자열이므로 재선택 시 동일 low_relevance 위험이 이론상 남아 있음. 다만 해당 확장 라인의 키워드들은 실제 발행 선택 빈도가 낮고, 대체 키워드 '캠핑 난로 추천'(발행성공 2)이 존재해 실질 커버리지 손실 없음. 1108행 '난로'를 추가 제거할지는 사용자 판단 필요.
2. **keyword_health 기존 실패 기록(consecutive_failures=2, quarantined_until 오늘 20:16)은 불변 유지** — 계획상 사용자 결정으로 DB 수정 안 함. 제거된 키워드는 재선택되지 않으므로 추가 실패/격리는 없으나, 기록 자체는 남아 있음.
3. **기존 테스트 실패 4건은 이 작업과 무관한 사전 존재 상태** — golf/bike 추가 등으로 인한 블로그 수/키워드 수/중복/제네릭 검증 실패. 이번 작업 범위 밖이며 별도 처리 필요.

## Decisions Made

- camping-hugo KEYWORD_MAP에서 1052~1054행 3개 요소('선풍기'/'난로'/'조명')만 제거 — 1108행 '난로' 및 appliance-hugo '선풍기'는 사용자 locked 결정에 따라 무수정.
- 대체 키워드('캠핑 조명 추천' 발행성공 1, '캠핑 난로 추천' 발행성공 2, '캠핑 선풍기 추천' 발행성공 2)가 이미 존재 — 커버리지 손실 없음.

## Stub Tracking

없음 — 키워드 목록에서 3개 요소 제거만 수행한 데이터 편집으로, UI/데이터 소스 스텁 없음.

## Threat Surface Scan

신규 표면 없음 — 네트워크 엔드포인트/인증 경로/파일 접근/스키마 변경 없음. 단일 데이터 파일의 3줄 삭제만. (T-260805-mo7-01 tampering 완화: git diff로 3라인 삭제만 확인됨)

## Self-Check: PASSED

- [x] FOUND: `.planning/quick/260805-mo7-root-title-remove-generic-camping-keywor/260805-mo7-SUMMARY.md` (파일 존재 확인)
- [x] FOUND: commit `ca9f9e7ad` (git log 검색 확인)
- [x] working tree의 `pipelines/curation/keywords.py` 클린 — 수정 사항이 전부 커밋됨

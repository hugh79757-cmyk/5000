# Phase 68 — TAP/Travel "1곳" 하드코딩 제거 실행 계획

> 상태: 계획 수립 (2026-08-09)  
> 근거: `RESEARCH.md` (코드 경로 추적 완료) + `CONTEXT.md` (계약/확정 설계 결정)  
> 작업 규칙: **기존 기능 보존, 증분 수정** — "1곳" 문제만 해소, 다른 프롬프트 내용·구조·규칙은 건드리지 않음

---

## Goal (1문장, 측정 가능)

TAP 여행 파이프라인에서 생성되는 모든 글의 **제목과 SEO description에 "N곳"(특히 items=1일 때 "1곳")이 포함되지 않도록** SEO description 조건부화 + fallback 제목 보강 + 템플릿 필터 보강 + 프롬프트 자연화를 적용한다.

---

## Success Criteria (각각 테스트 가능)

1. **SC-1**: items=1인 글의 description에 "1곳"이 포함되지 않음 — writer.py:1370 수정 후 `len(items)==1`인 mock 데이터로 `_seo_desc` 생성 시 "1곳" 미포함 확인
2. **SC-2**: fallback 제목에 "1곳"이 포함되지 않음 — AI 제목 생성 실패 mock 시 선택된 fallback title에 "1곳" 없음
3. **SC-3**: AI 제목 생성 성공 시에도 "1곳"이 자연스럽게 제거됨 — 기존 보정 로직 개선 확인
4. **SC-4**: 프롬프트 지시문의 "1곳" 표현이 자연스러운 표현으로 교체됨 (tour1_camping, travel_info)
5. **SC-5**: 기존 5개 블로그의 제목·description 생성 로직이 정상 동작 — 기존 테스트 suite가 있으면 pytest 통과, 없으면 mock 기반 수동 검증으로 대체

---

## Task Breakdown

> 구분 표기: **[PRODUCTION CODE]** = 검증 대상 코드 수정, **[CONFIG]** = 설정/프롬프트 수정.

### Task 1 [PRODUCTION CODE] — SEO description 조건부화 (C1 해소, 최우선)

- **파일**: `pipelines/travel/writer.py:1367-1372`
- **설명**:
  - `_seo_desc` 생성 시 `{len(items)}곳`이 조건 없이 포함되는 문제를 수정
  - items 수가 1개일 때는 "N곳"을 생략하고 자연스러운 표현으로 대체
- **변경 내용**:
  ```python
  # 변경 전 (L1370):
  _seo_desc = f"{display_region} {theme} — {_names_str}. {len(items)}곳 정보와 방문 팁 정리."

  # 변경 후:
  _item_count = len(items)
  if _item_count > 1:
      _place_word = f"{_item_count}곳"
  else:
      _place_word = ""
  if _place_word:
      _seo_desc = f"{display_region} {theme} — {_names_str}. {_place_word} 정보와 방문 팁 정리."
  else:
      _seo_desc = f"{display_region} {theme} — {_names_str}. 방문 팁 정리."
  ```
- **Acceptance Check**:
  - `items = [단일 아이템]`(len=1)인 mock 데이터로 테스트 시 `_seo_desc`에 "1곳" 미포함 → 대신 "방문 팁 정리." 포함
  - `items = [아이템1, 아이템2]`(len>=2)인 mock 데이터로 테스트 시 `_seo_desc`에 "{N}곳" 포함 유지 (예: "2곳 정보...")
- **예상 소요**: 약 0.3h

---

### Task 2 [PRODUCTION CODE] — fallback 제목의 "{count}곳" 처리 보강 (C2 해소)

- **파일**: `pipelines/travel/writer.py:1188-1195` (템플릿 선택) + `1353-1356` (fallback 사용부)
- **설명**:
  - 현재 fallback 제목 선택 시 `_body_place_count <= 1`이면 `{count}` 템플릿 제외하는 필터가 있으나, 모든 템플릿에 `{count}` 포함 시 필터 무효
  - **핵심 수정**: `_body_place_count`는 본문 생성 후 계산되나 템플릿 선택은 본문 생성 전이므로 기준이 의도와 다르게 작동할 수 있음 → **`len(items) <= 1`로 기준을 변경** (plan-checker 블록커 #2 해소)
  - fallback 사용 직전에도 "{count}" 없는 템플릿을 우선 선택하도록 보강
- **변경 내용**:
  ```python
  # 변경 전 (L1188-1195):
  templates = TITLE_TEMPLATES.get(blog_id, TITLE_TEMPLATES["travel-hugo"])
  if _body_place_count <= 1:
      _filtered = [t for t in templates if "{count}" not in t]
      if _filtered:
          templates = _filtered
  template = _rand.choice(templates)

  # 변경 후:
  templates = TITLE_TEMPLATES.get(blog_id, TITLE_TEMPLATES["travel-hugo"])
  # _body_place_count 대신 len(items) 사용 — 본문 생성 전 결정 가능한 기준
  if len(items) <= 1:
      _filtered = [t for t in templates if "{count}" not in t and "{count}선" not in t]
      if _filtered:
          templates = _filtered
  template = _rand.choice(templates) if templates else TITLE_TEMPLATES.get(blog_id, [""])[0]
  # 주의: Task 2 실행 시점(앞순번)에는 Task 3 정규식 보정이 미적용 상태.
  # fallback 제목에 "{count}곳"이 포함될 수 있는 경우(len(items)<=1이고 모든 템플릿에 {count} 포함 시),
  # 해당 fallback 제목은 Task 3 정규식 보정(L1326-1328 부근)에 의존해 "1곳"이 제거됨.
  # 즉 fallback에도 Task 3 regex 보정이 적용되도록 L1355(fallback 사용부)에 동일 로직 추가 필요.
  ```
- **주의**: `travel1-hugo`의 `{count}선` 템플릿도 함께 제외.
- **Acceptance Check**:
  - `len(items) <= 1`인 mock 상황에서 선택된 template에 "{count}" 또는 "{count}선" 미포함 확인
  - 모든 템플릿이 `{count}` 포함인 블로그에서도 fallback이 빈 문자열이나 에러 없이 선택됨
- **예상 소요**: 약 0.5h

---

### Task 3 [PRODUCTION CODE] — AI 제목 생성 보강의 견고성 개선 (C3 보조, 선택)

- **파일**: `pipelines/travel/writer.py:1326-1328`
- **설명**:
  - 현재 `"1곳" in generated_title` → `replace(" 1곳", "").replace("1곳 ", "")` 방식은 공백 기준이라 불완전
  - 더 견고한 정규식 기반 대체로 개선
- **변경 내용**:
  ```python
  # 변경 전 (L1326-1328):
  if "1곳" in generated_title:
      generated_title = generated_title.replace(" 1곳", "").replace("1곳 ", "")

  # 변경 후:
  import re as _re
  generated_title = _re.sub(r'\s*1곳\s*', ' ', generated_title).strip()
  # 연속 공백 정리
  generated_title = _re.sub(r'\s{2,}', ' ', generated_title)
  ```
- **Acceptance Check**:
  - "강원 속초시 1곳 추천" → "강원 속초시 추천"
  - "1곳당 비교", "2곳당" 등 복합어는 제거하지 않음 (의도: "1곳" 단독 단어만 제거 — 복합어 제거는 범위 외)
  - 공백이 없는 "X1곳Y" 형태도 `\s*1곳\s*`에 걸리지 않음 → 정규식 범위 한정, SC-3은 "공백 구분된 1곳 제거"로 표현
- **예상 소요**: 약 0.2h

---

### Task 4 [CONFIG] — 프롬프트 "1곳" 표현 정비 (C4 해소, 후순위)

- **파일**: `config/prompts/travel.yaml:87`, `config/prompts.yaml:393`
- **설명**:
  - "가장 추천하는 캠핑장 1곳을 이유와 함께 언급" → "가장 추천하는 캠핑장을 이유와 함께 언급"
  - 본문용 지시문이나 LLM이 제목 생성에도 영향 받을 수 있으므로 자연스러운 표현으로 교체
- **변경 내용**:
  - `config/prompts/travel.yaml` L87: `- 가장 추천하는 캠핑장 1곳을 이유와 함께 언급` → `- 가장 추천하는 캠핑장을 이유와 함께 언급`
  - `config/prompts.yaml` L393: 동일 변경
- **주의**: `travel2_heritage_deep`의 "1건"은 심층 분석 목적과 일치하므로 수정하지 않음
- **Acceptance Check**:
  - grep으로 "1곳"이 프롬프트에서 제거되었는지 확인 (두 파일)
  - `travel2_heritage_deep`의 "1건"은 유지 확인
- **예상 소요**: 약 0.1h

---

## Dependency Graph

```
Task 1 (description 조건부화) ─────────────┐
Task 2 (fallback 템플릿 필터 보강) ────────┤
Task 3 (제목 "1곳" 보정 개선) ────────────┤ (writer.py 순차 편집)
Task 4 (프롬프트 표현 정비) ──────────────┘ (독립 파일)
```

- **병렬 가능**: Task 4는 독립 파일(config)이므로 Task 1~3과 병렬 가능
- **순차 편집**: Task 1~3은 `writer.py` 동일 파일이므로 순차 실행 (diff 충돌 방지)

---

## Verification Loop

```bash
cd /Users/twinssn/Projects/5000

# [1] SC-1: description에 "1곳" 미포함 확인 (코드 변경 검증)
# Task 1 적용 후 L1370 부근에 조건부가 적용되었는지 grep 확인
grep -A3 '_item_count = len(items)' pipelines/travel/writer.py | head -10
# 또는 실제 함수 호출로 검증 (함수명 확인 필요 — writer.py 내 generate_로 시작)
python -c "
import re
# writer.py의 _seo_desc 생성 로직을 직접 테스트
# items 수에 따른 _seo_desc 패턴 확인
"

# [2] SC-2: fallback 템플릿 필터 로직 검증
python -c "
import re
# Task 2 적용 후 len(items)<=1일 때 {count}/{count}선 템플릿이除外되는지 확인
# TITLE_TEMPLATES 구조와 선택 로직을 mock으로 테스트
"

# [3] SC-3: AI 제목 생성 성공 시 '1곳' 제거 확인
python -c "
import re
# Task 3의 regex가 공백을 기준으로 '1곳'을 제거하는지 테스트
test_titles = [
    '강원 속초시 1곳 추천',
    '1곳당 비교',  # 복합어는 제거 안 됨 (의도)
    ' X 1곳 Y ',
]
for t in test_titles:
    result = re.sub(r'\s*1곳\s*', ' ', t).strip()
    result = re.sub(r'\s{2,}', ' ', result)
    print(f'{t!r} → {result!r}')
# '1곳'이 공백으로 구분된 경우만 제거됨을 확인
"

# [4] SC-4: 프롬프트에서 '1곳' 제거 확인
grep -n '1곳' config/prompts/travel.yaml config/prompts.yaml && echo 'FAIL: 프롬프트에 1곳 잔존' || echo 'SC-4 PASS: 프롬프트에서 1곳 제거됨'
grep -n '1건' config/prompts/travel.yaml  # travel2_heritage_deep은 유지 확인 (의도적)

# [5] SC-5: 기존 테스트 suite 녹색 유지 (있으면)
python -m pytest tests/travel -q 2>/dev/null && echo 'SC-5 PASS: 테스트 suite 녹색' || echo 'SC-5 N/A: 테스트 suite 없음 — mock 기반 수동 검증으로 대체'
```

---

## Threat Model / Risks

| 위험 | 영향 | 대응 |
|------|------|------|
| `_body_place_count` 계산 시점 | 본문 생성 전/후 관계 불명확 시 필터 로직 오작동 | 코드 실행 시점 확인 후 조정 |
| `{count}` 치환 로직 위치 | 치환이 어디서 일어나는지 불명확 시 Task 2 효과 제한적 | writer.py 내 title_prompt 구성부 추가 추적 |
| 기존 테스트 없음 | SC-5 검증 불가 | mock 기반 수동 검증으로 대체 |
| travel2-heritage 심층 프롬프트 혼동 | "1건"까지 제거하면 심층 분석 목적 훼손 | travel2_heritage_deep은 수정 대상에서 명시적으로 제외 |

---

## 산출물

- `pipelines/travel/writer.py` 수정 (Task 1, 2, 3)
- `config/prompts/travel.yaml` 수정 (Task 4)
- `config/prompts.yaml` 수정 (Task 4)
- 커밋 메시지: `fix(travel): remove hardcoded "1곳" from titles and descriptions`

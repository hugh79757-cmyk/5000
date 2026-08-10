# Phase 54 — Research: TAP/Travel "1곳" 하드코딩 원인 분석

**Researched:** 2026-08-09
**Domain:** TAP Travel 파이프라인 프롬프트·제목·설명문 생성 로직
**Confidence:** HIGH

---

## 1. 문제 정의

TAP(Travel Auto Publisher) 분기에서 생성되는 모든 글의 제목과 SEO description에 "1곳"이라는 표현이 포함되는 현상이 발생한다. 이는 프롬프트 예시(샘플 글) 추가와 별개로, 코드 자체의 여러 지점에서 `{count}곳` / `1곳`이 하드코딩 또는 준하드코딩되어 있기 때문이다. 목적은 자연스러운 글쓰기이며, 샘플 글은 LLM 규제 최소화 + 역량 발휘가 목적이므로 "1곳"이 제목/본문에 나오는 것은 의도와 맞지 않는다.

---

## 2. 코드 경로 추적

### 2.1 제목 생성 경로

**경로:** `generate_content()` (writer.py L889) → `_select_prompt_id()` (L78) → `build_prompt()` (L990) → AI 제목 생성 (L1304-1356) → fallback 제목 (L1210-1218)

**fallback 제목 결정 (writer.py L1104-1218):**

- `TITLE_TEMPLATES` 딕셔너리 (L1104-1184)에 블로그 ID별로 제목 템플릿 리스트가 정의되어 있음
- 모든 블로그 ID의 템플릿 다수에는 `{count}곳` 플레이스홀더가 포함되어 있음 (예: `"{region} {theme} {count}곳 총정리"`)
- `{count}` 값 결정 (L986): `str(_item_count)`. `_item_count`는 L974-976에서 결정:
  ```python
  _item_count = len(data.get("items", []))
  if data.get("source_type") != "heritage" and data.get("source_type") != "course":
      _item_count = min(_item_count, 3)
  ```
- 즉, 캠핑·축제·맛집은 최대 3, heritage/course는 원본 items 수 전체가 `{count}`가 됨

**1곳일 때 필터 로직 (writer.py L1190-1194):**

```python
# 1곳일 때 "{count}" 포함 템플릿 제외 (제목-본문 불일치 방지)
if _body_place_count <= 1:
    _filtered = [t for t in templates if "{count}" not in t]
    if _filtered:
        templates = _filtered
```

- `_body_place_count`는 L1098-1102에서 결정:
  ```python
  _body_h3 = re.findall(r"^### (.+)", content, re.MULTILINE)
  _body_place_count = len(_body_h3) if _body_h3 else len(items)
  if _body_place_count == 0:
      _body_place_count = min(len(items), 3)
  ```
- H3가 있으면 H3 개수, 없으면 items 수 사용 (단, 3 초과 시 3)
- **문제점:** 이 필터는 `_body_place_count <= 1`일 때만 작동. 즉:
  - `_body_place_count`가 2 이상이면 `{count}곳` 템플릿이 그대로 사용됨
  - `_body_place_count`가 0이면 `min(len(items), 3)`으로 떨어지므로, items가 1개여도 `_body_place_count=1`이 되어 필터 적용됨
  - **그러나** `_body_place_count`가 결정되기 전의 `extra_vars["count"]` (L986)는 별도의 로직으로 결정되므로, fallback 제목 생성 시점(L1210-1218)에는 이미 `{count}` 값이確定되어 있음. 필터는 템플릿 선택에만 영향을 줌

**AI 생성 제목의 "1곳" 보정 (writer.py L1326-1328):**

```python
# "1곳" 어색한 제목 보정
if "1곳" in generated_title:
    generated_title = generated_title.replace(" 1곳", "").replace("1곳 ", "")
```

- AI가 생성한 제목에 "1곳"이 포함되면 제거
- **그러나** 이 보정은 AI 생성 성공 시에만 적용됨. AI 생성 실패 시 사용되는 fallback 제목(L1355-1356)에는 이 보정이 적용되지 않음

### 2.2 설명문(SEO description) 생성 경로

**위치: writer.py L1367-1372**

```python
_seo_desc = f"{display_region} {theme} — {_names_str}. {len(items)}곳 정보와 방문 팁 정리."
if len(_seo_desc) > 160:
    _seo_desc = _seo_desc[:157] + "..."
```

- **항상** `{len(items)}곳` 형식이 포함됨
- items가 1개면 "1곳 정보와 방문 팁 정리"가 됨
- **이 줄에는 어떠한 조건부 필터도 없음** — items 수가 1이든 3이든 무조건 "N곳"이 들어감
- 이 description은 반환값(dict)의 `"description"` 키로 반환됨 (L1398)

### 2.3 프롬프트 내 "1곳" 하드코딩 위치

3곳의 하드코딩 위치가 확인됨:

| # | 파일 | 라인 | 내용 | 성격 |
|---|------|------|------|------|
| 1 | `config/prompts.yaml` | L393 | `- 가장 추천하는 캠핑장 1곳을 이유와 함께 언급` | tour1_camping user 프롬프트 마무리 지시 |
| 2 | `config/prompts/travel.yaml` | L87 | `- 가장 추천하는 캠핑장 1곳을 이유와 함께 언급` | tour1_camping user 프롬프트 마무리 지시 (동일 내용, 별도 파일) |
| 3 | `config/prompts/travel.yaml` | L432 | `아래 문화유산 1건에 대한 심층 정보글을 작성하세요.` | travel2_heritage_deep user 프롬프트 첫 문장 |
| 4 | `config/prompts.yaml` | L1051 | `아래 문화유산 데이터 1건을 기반으로 심층 정보글을 작성하세요.` | travel2_heritage_deep user 프롬프트 첫 문장 (동일 내용, 별도 파일) |

**분석:**

- **#1, #2 (tour1_camping):** "가장 추천하는 캠핑장 1곳"은 여러 캠핑장 중 **하나를 골라 추천하라**는 의미. 본문에서 다루는 전체 장소 수가 1곳이라는 의미가 아님. 하지만 LLM이 이 문구를 오해하여 제목에도 "1곳"을 넣을 가능성이 있음
- **#3, #4 (travel2_heritage_deep):** travel2-hugo heritage 심층 프롬프트. 이 프롬프트는 **애초에 1건의 문화유산만 다루는 것이 의도**임. 따라서 "1건"이라는 표현은 프롬프트의 목적과 일치함. 이 프롬프트가 선택되는 조건은 `item_count == 1`일 때 (writer.py L93-96)

### 2.4 {count} 플레이스홀더 결정 로직

**`extra_vars["count"]` 결정 (writer.py L974-988):**

```python
_item_count = len(data.get("items", []))
if data.get("source_type") != "heritage" and data.get("source_type") != "course":
    _item_count = min(_item_count, 3)
# ...
extra_vars = {
    # ...
    "count": str(_item_count),
    # ...
}
```

- `{count}`는 `build_prompt()`에 `extra_vars`로 전달되어 프롬프트 템플릿 내 `{count}`를 치환함
- **결정 방식:** data의 items 수 (단, heritage/course 제외 최대 3)
- 이 값은 프롬프트 본문 내 `{count}곳` 치환에 사용됨
- **이 값과 `_body_place_count`는 서로 다른 변수** — 전자는 프롬프트 내 플레이스홀더 치환용, 후자는 제목 템플릿 필터링용

---

## 3. 근본 원인

"1곳"이 제목과 설명문에 나타나는 원인은 **단일 지점이 아닌 여러 지점의 복합**이다:

### 3.1 SEO description의 무조건적 "N곳" 표기 (가장 직접적 원인)

`_seo_desc` (writer.py L1370)는 `len(items)`를 항상 "N곳" 형태로 포함시킨다. items가 1개이면 "1곳"이 된다. 이 줄에 조건부 로직이 전혀 없어, 1곳일 때 자연스러운 대안(예: "정보와 방문 팁 정리"만 남기기)으로 전환하는 코드가 없다.

### 3.2 fallback 제목 템플릿의 `{count}곳` 포함

`TITLE_TEMPLATES`의 거의 모든 템플릿에 `{count}곳`이 포함되어 있다. `_body_place_count <= 1`일 때 `{count}` 포함 템플릿을 제외하는 필터(L1191-1194)가 있지만:
- 이 필터는 `_body_place_count`가 1 이하일 때만 작동
- `_body_place_count`가 2 이상이면 `{count}곳` 템플릿이 선택됨
- `travel1-hugo` 템플릿 중 `{count}`가 없는 템플릿이 얼마나 있는지는 템플릿 리스트상 명확하지 않음 (L1117-1138 구간에서 `{count}` 없는 템플릿 존재 여부 확인 필요)

### 3.3 프롬프트의 "1곳" 표현이 LLM에 미치는 영향

- `tour1_camping` / `tour2_food`의 마무리 지시문("가장 추천하는 캠핑장/식당 1곳을 이유와 함께 언급")은 **본문용 지시**이지만, LLM이 이를 제목 생성에도 반영하여 "1곳"을 포함할 수 있음
- `travel2_heritage_deep` 프롬프트 첫 문장("아래 문화유산 1건에 대한 심층 정보글을 작성하세요")은 심층 프롬프트의 의도와 일치하므로 문제가 아님

### 3.4 AI 제목 보정의 불완전한 커버리지

AI 생성 제목의 "1곳" 보정(L1327-1328)은 AI가 제목을 성공적으로 생성했을 때만 작동한다. AI 생성 실패 시 사용되는 fallback 제목에는 이 보정이 적용되지 않는다. 또한 `replace(" 1곳", "").replace("1곳 ", "")`는 "1곳"이 제목 중간에 다른 형태로 있을 때(예: "서울 1곳 추천") 완전히 제거되지 않을 수 있다.

---

## 4. 영향 범위

### 4.1 직접 영향 — "1곳"이 출력되는 지점

| 출력 지점 | 파일·라인 | 조건 | 1곳일 때 결과 |
|-----------|-----------|------|---------------|
| SEO description | writer.py L1370 | 항상 | "{region} {theme} — {names}. 1곳 정보와 방문 팁 정리." |
| fallback 제목 | writer.py L1210-1218 | AI 제목 생성 실패 시 | 선택한 템플릿에 따라 "{region} {theme} 1곳 총정리" 등 |
| AI 생성 제목 | writer.py L1327-1328 | AI 생성 성공 시 | "1곳"이 제거됨 (보정 적용) |

### 4.2 프롬프트 선택 분기 (travel2-hugo heritage)

writer.py L92-97:
```python
if blog_id == "travel2-hugo" and source_type == "heritage" and item_count is not None:
    if item_count == 1:
        return "travel2_heritage_deep"
    return "travel2_heritage_grouped"
```

- `item_count == 1` → `travel2_heritage_deep` 프롬프트 사용. 이 프롬프트는 원래 1건 심층 분석이 목적이므로 "1건" 표현이 적절함
- `item_count >= 2` → `travel2_heritage_grouped` 프롬프트 사용. 이 프롬프트는 `{count}건`/`{count}곳` 사용

### 4.3 fetcher 전략 (heritage)

fetcher.py L1087-1094:
```python
# 심층(1곳) 70% / 맥락묶기(2~3곳) 30%
_roll = random.random()
if _roll < 0.7 and _deep_candidates:
    selected = [random.choice(_deep_candidates)]
    _strategy = "deep"
```

- heritage 파이프라인은 70% 확률로 1곳만 선택 → writer.py에서 `item_count=1` → `travel2_heritage_deep` 프롬프트 선택
- 30% 확률로 2~3곳 선택 → grouped 프롬프트
- **즉, travel2-hugo heritage는 약 70%의 글에서 심층(1곳) 프롬프트가 사용됨.** 이는 의도된 설계

### 4.4 영향받는 블로그

`TITLE_TEMPLATES`에 정의된 모든 여행 블로그:
- `travel-hugo` (캠핑)
- `travel1-hugo` (축제)
- `travel2-hugo` (문화유산)
- `travel3-hugo` (맛집)
- `travel4-hugo` (여행코스)
- `tvshow-blogger`

이 중 `travel2-hugo`의 heritage 심층 프롬프트는 원래 1건 분석이 목적이므로 영향 무의미. 그 외 블로그에서는 items 수가 1개일 때 "1곳"이 제목 또는 description에 나타날 수 있음.

---

## 5. 권장 해결 방향

### 5.1 SEO description (최우선 — 가장 직접적 원인)

**파일:** `pipelines/travel/writer.py`, L1367-1372

현재:
```python
_seo_desc = f"{display_region} {theme} — {_names_str}. {len(items)}곳 정보와 방문 팁 정리."
```

제안:
```python
_item_cnt = len(items)
if _item_cnt <= 1:
    _seo_desc = f"{display_region} {theme} — {_names_str}. 정보와 방문 팁 정리."
else:
    _seo_desc = f"{display_region} {theme} — {_names_str}. {_item_cnt}곳 정보와 방문 팁 정리."
```

또는 더 간단하게 "N곳"을 조건부로 삽입:
```python
_cnt_part = f" {_item_cnt}곳" if _item_cnt > 1 else ""
_seo_desc = f"{display_region} {theme} — {_names_str}.{_cnt_part} 정보와 방문 팁 정리."
```

### 5.2 fallback 제목의 `{count}곳` 처리

**파일:** `pipelines/travel/writer.py`, L1190-1194 (기존 필터) 보강

현재 필터는 `_body_place_count <= 1`일 때 `{count}` 포함 템플릿을 제외한다. 이 로직은 유지하되:

1. `extra_vars["count"]` 결정 시(items 수가 1이면) `_body_place_count`도 함께 1로 설정되도록 정합성 확보
2. `_body_place_count`가 아닌 실제 `len(items)` 기준으로도 1곳 여부를 판단하여 fallback 제목에 반영

혹은 fallback 제목 생성 시점(L1210-1218)에 `_body_place_count <= 1`이면 `{count}`를 "{count}" 그대로 두지 않고 다른 표현으로 치환하는 방안도 가능.

### 5.3 프롬프트의 "1곳" 표현 검토

**파일:** `config/prompts.yaml` L393, `config/prompts/travel.yaml` L87

현재: `- 가장 추천하는 캠핑장 1곳을 이유와 함께 언급`

이 표현은 **마무리에 "하나를 골라 추천하라"**는 의미로 의도된 것이지만, LLM이 오해할 여지가 있다. 더 명확한 표현:

```
- 가장 추천하는 캠핑장 한 곳을 이유와 함께 언급 (전체 소개 장소가 1곳인 경우 이 항목은 생략)
```

또는 단순히:
```
- 가장 추천하는 캠핑장을 이유와 함께 언급 (한 곳만 있다면 그곳을 추천)
```

**단**, 이 변경은 "1곳" 제목 문제의 2차적 원인(LLM이 프롬프트 문구에 영향받음)에 대한 대응이며, 1차적 원인은 5.1(SEO description)과 5.2(fallback 제목)이다.

### 5.4 AI 제목 보강의 커버리지 확대

**파일:** `pipelines/travel/writer.py`, L1326-1328

현재 `replace(" 1곳", "").replace("1곳 ", "")` 방식은 불완전하다. 더 포괄적으로는:

```python
generated_title = re.sub(r"\s*1곳\s*", " ", generated_title).strip()
```

또는 "1곳"이 포함된 제목 전체를 fallback으로 전환하는 현재 로직(L1327-1328 + L1346-1348의 long_words fallback과 유사)을 유지하되, 정규식 기반 제거로 보완.

---

## 부록: 관련 파일 라인 맵

| 파일 | 관련 라인 | 내용 |
|------|-----------|------|
| `pipelines/travel/writer.py` | L78-97 | `_select_prompt_id()` — travel2-hugo heritage 분기 |
| `pipelines/travel/writer.py` | L974-988 | `extra_vars["count"]` 결정 |
| `pipelines/travel/writer.py` | L1098-1102 | `_body_place_count` 산출 |
| `pipelines/travel/writer.py` | L1104-1184 | `TITLE_TEMPLATES` 정의 |
| `pipelines/travel/writer.py` | L1190-1194 | 1곳일 때 `{count}` 템플릿 필터 |
| `pipelines/travel/writer.py` | L1210-1218 | fallback 제목 생성 |
| `pipelines/travel/writer.py` | L1326-1328 | AI 제목의 "1곳" 보정 |
| `pipelines/travel/writer.py` | L1367-1372 | `_seo_desc` 생성 (무조건 "N곳" 포함) |
| `config/prompts.yaml` | L393 | tour1_camping 마무리 "1곳" 지시 |
| `config/prompts.yaml` | L1051 | travel2_heritage_deep 첫 문장 "1건" |
| `config/prompts/travel.yaml` | L87 | tour1_camping 마무리 "1곳" 지시 (동일) |
| `config/prompts/travel.yaml` | L432 | travel2_heritage_deep 첫 문장 "1건" (동일) |
| `pipelines/travel/fetcher.py` | L1087-1094 | heritage 심층(1곳) 70% / 묶기(2~3곳) 30% 전략 |

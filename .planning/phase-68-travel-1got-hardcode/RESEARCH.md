# Phase 68 — Research: TAP/Travel 본문 규격 + 추가 이슈 분석

> 작성일: 2026-08-09  
> 연구자: gsd-phase-researcher (subagent)  
> 목표: Phase 68 원래 목표 달성 범위 확인 + TAP 블로그 본문 규격 문서화 + 추가 발견 5건 분석

---

## 1. Phase 68 개요 (복습)

**원래 목표**: TAP 여행 파이프라인에서 생성되는 모든 글의 제목과 SEO description에 "N곳"(특히 items=1일 때 "1곳")이 포함되지 않도록 4개 Task + 프롬프트 수정을 적용.

**적용 블로그**: tap-blogger, travel-hugo, travel1-hugo, travel2-hugo, travel3-hugo, travel4-hugo (6개)

**핵심 원칙**: LLM 규제를 최소화하고 자연스러운 글쓰기를 유도. 샘플 글 참조(`{samples}`)는 유지.

---

## 2. 달성된 수정 사항 (12건)

### Task 1~3: production code (writer.py)

| # | 수정 | 위치 | 상태 |
|---|------|------|------|
| 1 | SEO description 조건부화 | writer.py:1367-1375 | ✓ 커밋 |
| 2 | fallback 템플릿 필터 보강 (len(items)≤1 기준) | writer.py:1188-1195 | ✓ 커밋 |
| 3 | 제목 "1곳" regex 보정 (`\s*1곳\s*`) | writer.py:1327-1331 | ✓ 커밋 |

### Task 4: config prompts

| # | 수정 | 위치 | 상태 |
|---|------|------|------|
| 4 | "가장 추천하는 캠핑장 1곳" → "가장 추천하는 캠핑장" | prompts/travel.yaml:87 | ✓ 커밋 |
| 5 | 동일 (common prompts.yaml) | prompts.yaml:393 | ✓ 커밋 |

### 추가 프롬프트 지시문 제거 (이번 세션)

| # | 수정 | 위치 | 상태 |
|---|------|------|------|
| 6 | `tour1_camping/user`: `## {region} {theme} {count}곳 한눈에 비교` → `## {region} {theme} 한눈에 비교` | prompts/travel.yaml:L37 | ✓ 이번 세션 |
| 7 | `tour1_camping/user`: "이 글에서 소개할 캠핑장 수와 핵심 테마를 명시" → "핵심 테마를 명시" | prompts/travel.yaml:L33 | ✓ 이번 세션 |
| 8 | `tour2_food/user`: `## {region} {theme} {count}곳 한눈에 비교` → `## {region} {theme} 한눈에 비교` | prompts/travel.yaml:L219 | ✓ 이번 세션 |
| 9 | `tour2_food/user`: "이 글에서 소개할 식당 수와 음식 종류를 명시" → "음식 종류를 명시" | prompts/travel.yaml:L215 | ✓ 이번 세션 |
| 10 | `travel_info/system`: TITLE-BODY CONSISTENCY 섹션 전체 삭제 | prompts/travel.yaml:L408-415 | ✓ 이번 세션 |
| 11 | `travel2_heritage/user`: `{count}건` 제거 | prompts/travel.yaml:L366 | ✓ 이번 세션 |
| 12 | `writer.py`: `_body_place_count = len(_body_h3)` → `len(items)` | writer.py:L1141-1143 | ✓ 이번 세션 |
| 13 | `writer.py`: title_prompt에서 "장소수: {_body_place_count}" 라인 제거 | writer.py:L1293 | ✓ 이번 세션 |

---

## 3. TAP 블로그 본문 규격 (신규 문서화)

`~/.config/opencode/skills/tap-blog-spec/SKILL.md`에 문서화됨 (287줄).

### 3.1 전체 구조

```
# H1 (제목, Blogger 자동)
Intro 단락 (H2 없이 시작)

## H2-A: 도입부 H2 (선택)
## H2-B: 한눈에 비교 / 상세 안내

### H3: 장소명 1
![이미지]        ← _inject_images, H3 직후, 장소별 1회 매칭
본문 (6문장+)
[네이버 지도에서 보기]  ← _inject_naver_map, H3 본문 끝

### H3: 장소명 2
...

## H2: 체크포인트 / 참고사항
## H2: 마무리 (선택)

--- 쿠팡 섹션 ---
[가로 flex, 이미지 80x80, 상품명+가격]

--- 엔티티 카드 (선택) ---
첫 H2 앞 + 중간 H2 앞 + 마지막 H2 뒤 (최대 2개)

--- nearby 카드 ---
이미지 + 이름 + 주소 + [네이버 지도에서 보기]

Tags [...]
```

### 3.2 섹션별 규격

**이미지 삽입 규칙:**
- H3 직후에만 삽입 (H2 건너뛰기)
- H3 제목과 아이템명(facltNm/title) 매칭하여 해당 H3에 맞는 이미지 삽입
- 매칭 성공 시 즉시 img_map에서 제거하여 중복 방지
- "여행 준비", "함께 읽어보기", "코스 주변 맛집", "반경 10km" H3는 제외

**네이버 지도 버튼 규칙:**
- H3 본문 끝(다음 H2/H3 직전 빈 라인 뒤)에 삽입
- H2에는 삽입하지 않음
- 버튼 텍스트: "{장소명} 네이버 지도에서 보기" (통일)
- URL: `https://map.naver.com/v5/search/{URL인코딩된장소명}`
- 버튼 스타일: background:#181616, color:#fff, padding:8px 20px, border-radius:6px, text-decoration:none, font-size:14px, font-weight:500
- parent: `nearby-card-body`에 `text-align:center` 적용 (nearby 카드 내)

**쿠팡 상품 리스트 규칙:**
- 위치: 본문 종료 후
- 형식: HTML inline style (flexbox)
- 이미지: 80x80 (CSS로 제어, Coupang size 파라미터 제거)
- 카드: background:#f5f5f5, border-radius:8px, padding:8px
- 개수: 3개
- 대가성 문구 포함

**nearby 카드 규칙:**
- 구조: `<div class="nearby-card">` + `<img>` (선택) + `<div class="nearby-card-body" style="text-align:center;">` + `<strong style="display:block;margin-bottom:4px;">` + `<span style="display:block;margin-bottom:8px;color:#555;">` + `<a>` 버튼
- 가볼만한곳 최대 3개, 맛집 최대 3개 (합계 6개 이하)

**엔티티 카드 규칙:**
- 최대 2개, 상/중/하 분산 배치
- H2가 2개 미만이면 두 번째 카드는 본문 맨 끝에 배치 (상단 회귀 방지)

**H2 제한:**
- 최대 4개 (초과 시 마지막부터 제거)

### 3.3 프롬프트 규약

LLM에게 전달하지 않고 시스템이 후처리로 삽입하는 요소:

| 요소 | 담당 함수 |
|------|---------|
| 네이버 지도 버튼 | `_inject_naver_map()` |
| API 이미지 | `_inject_images()` |
| nearby 카드 | `_enrich_with_nearby()` / `_enrich_with_nearby_restaurants_only()` |
| 쿠팡 상품 | `CoupangTravel.get_product_cards()` |
| 엔티티 카드 | `_inject_entity_cards()` |
| H2 개수 제한 | `_post_process()` |
| "함께 읽어보기" 제거 | `_post_process()` |

프롬프트 내 해당 규칙:
```yaml
- 네이버 지도 링크를 본문에 넣지 마세요 (시스템이 자동 삽입합니다)
- 이미지 마크다운 ![...](...) 사용 금지
```

### 3.4 writer.py 함수 맵

| 함수 | 역할 | 호출 순서 |
|------|------|----------|
| `_inject_images()` | H3별 API 이미지 삽입 | post_process 내부 |
| `_inject_naver_map()` | H3 본문 끝에 지도 버튼 | post_process 내부 |
| `_enrich_with_nearby()` | 가볼만한곳+맛집 nearby 카드 | post_process 내부 |
| `_enrich_with_nearby_restaurants_only()` | travel4-hugo 전용 맛집 카드 | post_process 내부 |
| `_inject_entity_cards()` | TAP 크로스블로그 카드 분산 배치 | post_process 내부 |
| `_post_process()` | H2 제한, 쿠팡 삽입, "함께 읽어보기" 제거 등 | 최종 |
| `_enrich_title()` | 제목 보강 + H1 제거 + 데이터 블록 제거 | _post_process 전 |
| `_build_heritage_card()` | heritage용 정보표 생성 | _inject_entity_cards 내부 |

### 3.5 블로그별 특이사항

| blog_id | 특이사항 |
|---------|---------|
| `travel-hugo` | 캠핑/글램핑, `_enrich_with_nearby()` 사용 |
| `travel1-hugo` | 축제, `travel1_festival` 프롬프트, 네이버 통합검색 사용 |
| `travel2-hugo` | 문화유산, `travel2_heritage`/`travel2_heritage_deep`, heritage 카드 삽입 |
| `travel3-hugo` | 맛집, `_enrich_with_nearby_restaurants_only()` 사용 |
| `travel4-hugo` | 여행코스, `_enrich_with_nearby_restaurants_only()` 사용 |
| `tap-blogger` | 관광공사 데이터, source_type에 따라 프롬프트 분기. **TITLE_TEMPLATES 키 없음 → fallback 주의** (이슈 1 참조) |

---

## 4. 추가 발견 이슈 5건 분석

### 4.1 이슈 1: 제목 "시설과 예약 정보 정리" 회귀

**현상**: `tap-blogger`에서 발행된 문화재 글의 제목에 "시설과 예약 정보 정리" 포함  
→ "경북 경주시 여행 경북 보물 불교조각 경주 무장사지 아미타불 조상 시설과 예약 정보 정리"

**근본 원인**: `tap-blogger`는 `TITLE_TEMPLATES` dict에 별도 키가 없어서 `TITLE_TEMPLATES["travel-hugo"]`를 fallback으로 사용. travel-hugo 템플릿에는 캠핑장용 템플릿(예: `"{region} {angle} {first_camp} 시설과 예약 정보 정리"`)이 포함되어 있고, `tap-blogger`가 heritage 콘텐츠를 생성해도 이 템플릿에서 랜덤 선택됨.

**코드 위치**:
```python
# writer.py:1229 (수정 전)
templates = TITLE_TEMPLATES.get(blog_id, TITLE_TEMPLATES["travel-hugo"])

# writer.py:1265 (수정 전)
if blog_id == "travel2-hugo":
    title_prompt = f"""..."""
```

**수정**:
```python
# writer.py:1241 (수정 후)
templates = TITLE_TEMPLATES.get(blog_id, TITLE_TEMPLATES.get("travel2-hugo") if source_type == "heritage" else TITLE_TEMPLATES["travel-hugo"])

# writer.py:1265 (수정 후)
if blog_id == "travel2-hugo" or (blog_id == "tap-blogger" and source_type == "heritage"):
    title_prompt = f"""..."""
```

**판단**: 수정이 적절함. `tap-blogger`의 heritage 콘텐츠는 travel2-hugo와 동일한 성격(문화유산 소개)이므로 동일한 템플릿/프롬프트를 사용하는 것이 합리적.

**잔존 위험**: 향후 새 blog_id 추가 시 같은 fallback 함정 재발 가능. `BLOG_PROMPT_MAP`(L70-78)처럼 `TITLE_TEMPLATES`도 blog_id별 명시적 매핑이 중장기적으로 필요.

### 4.2 이슈 2: 엔티티 카드 2개 상단 회귀

**현상**: 문화재 글 상단에 엔티티 카드 2개가 연속 배치됨.

**근본 원인**: `_inject_entity_cards()`에서 첫 카드 삽입 후 H2 위치를 재계산하는데, H2가 1개뿐이면 `mid_idx = len(h2_positions) // 2 = 0`이 됨. 이로 인해 두 번째 카드도 첫 H2 앞(h2_positions[0])에 삽입되어 첫 카드와 같은 위치에 쌓임.

**코드 위치**:
```python
# writer.py:743-749 (수정 전)
if len(selected) < 2 or len(h2_positions) < 3:
    mid_idx = len(h2_positions) // 2
    content = content[:h2_positions[mid_idx]] + "\n" + cards[-1] + "\n" + content[h2_positions[mid_idx]:]
    return content
```

**수정**:
```python
# writer.py:743-755 (수정 후)
if len(selected) < 2:
    return content

if len(h2_positions) < 2:
    # H2가 1개뿐이면 두 번째 카드는 본문 맨 끝에 배치 (상단 회귀 방지)
    content = content.rstrip() + "\n\n" + cards[1]
    return content

if len(h2_positions) < 3:
    # H2가 2개면 중간 위치(첫 H2와 둘째 H2 사이 또는 둘째 H2 앞)에 배치
    mid_idx = len(h2_positions) // 2
    content = content[:h2_positions[mid_idx]] + "\n" + cards[-1] + "\n" + content[h2_positions[mid_idx]:]
    return content

mid_idx = len(h2_positions) // 2
content = content[:h2_positions[mid_idx]] + "\n" + cards[1] + "\n" + content[h2_positions[mid_idx]:]
return content
```

**판단**: 수정이 적절함. H2<2개일 때 두 번째 카드를 본문 끝에 배치하면 상단 회귀가 방지됨. 단, H2 1개인 유산 심층 글(travel2_heritage_deep)에서는 두 번째 카드가 항상 본문 끝에 가므로 "분산 배치" 효과가 반감됨. 이것은 trade-off로 수용 가능(카드 1개만 상단에, 1개는 하단에).

### 4.3 이슈 3: 이미지 중복 삽입

**현상**: "도기 녹유 탁잔" 이미지가 2개 H3에 삽입됨.  
- `### 통일신라의 품격, 도기 녹유 탁잔` (정상)  
- `### 함께 둘러보면 좋은 전시 관람 팁` (오류)

**근본 원인**: `_inject_images()`에서 한 H3에 매칭된 아이템이 `img_map`에서 제거되지 않아, 다음 H3 처리 시 같은 아이템이 다시 매칭될 수 있음. 매칭 로직이 `item_key in h3_key or item_name in h3_text or any(...)`로 다중 조건을 사용하는데, "도기 녹유 탁잔"의 일부 단어("도기" 등)가 다른 H3 텍스트에 포함될 경우 오매칭 가능.

**코드 위치**:
```python
# writer.py:502-515 (수정 전)
if line.startswith("### ") and not any(skip in line for skip in [...]):
    h3_text = line.replace("### ", "").strip()
    h3_key = h3_text.replace(" ", "")
    matched = None
    for item_key, (item_name, img_url) in img_map.items():
        if h3_key in item_key or item_key in h3_key or any(p in h3_text for p in item_name.split() if len(p) >= 2):
            matched = (item_name, img_url)
            break
    if matched:
        result.append("")
        result.append(f"![{matched[0]}]({matched[1]})")
        result.append("")
        # ★ 여기서 img_map에서 제거 안 함 → 다음 H3에서 재사용 가능
```

**수정**:
```python
# 매칭 성공 시 즉시 img_map에서 제거
if matched:
    result.append("")
    result.append(f"![{matched[0]}]({matched[1]})")
    result.append("")
    img_map.pop(next(k for k, v in img_map.items() if v == matched), None)
```

**판단**: 수정이 적절함. 단, `img_map.pop(next(...))`는 O(n) 스캔이 발생하므로 items가 많은 경우 성능 이슈 가능. 현재는 items=1~3 수준이라 문제 없음. 더 효율적인 구현을 원하면 매칭 단계에서 key를 먼저 찾도록 수정 가능하지만 현재 scope 내 불필요.

### 4.4 이슈 4: nearby 카드 줄바꿈 없음

**현상**: `동빙고 본점서울특별시 용산구 이촌로 319 현대아파트네이버 지도에서 보기` — 이름·주소·버튼이 한 줄에 연속 표시.

**근본 원인**: `_nearby_card()`에서 `<strong class="nearby-card-name">` + `<span class="nearby-card-addr">` + `<a>`가 모두 인라인 요소(`display:inline` 기본값 또는 `inline-block`)로 출력되어 줄바꿈 없이 연속 표시.

**코드 위치**:
```python
# writer.py:545-553 (수정 전, _enrich_with_nearby_restaurants_only 내 _nearby_card)
card += '<strong class="nearby-card-name">' + name + "</strong>"
if addr:
    card += '<span class="nearby-card-addr">' + addr + "</span>"
card += '<a class="nearby-card-btn" ...>네이버 지도에서 보기</a>'

# writer.py:598-606 (수정 전, _enrich_with_nearby 내 _nearby_card)
# 동일 구조
```

**수정** (양쪽 `_nearby_card` 모두):
```python
card += '<div class="nearby-card-body" style="text-align:center;">'
card += '<strong class="nearby-card-name" style="display:block;margin-bottom:4px;">' + name + "</strong>"
if addr:
    card += '<span class="nearby-card-addr" style="display:block;margin-bottom:8px;color:#555;">' + addr + "</span>"
card += '<a class="nearby-card-btn" ... style="...padding:8px 20px...">네이버 지도에서 보기</a>'
```

**판단**: 수정이 적절함. `display:block`으로 각 요소를 블록 레벨로 만들고 `margin-bottom`으로 간격 확보. `text-align:center`로 버튼 중앙 정렬도 동시 해결.

### 4.5 이슈 5: 네이버 지도 버튼 중앙 정렬 안 됨

**현상**: nearby 카드의 "네이버 지도에서 보기" 버튼이 왼쪽 정렬.

**근본 원인**: 버튼은 `display:inline-block`이나 부모인 `nearby-card-body`에 `text-align:center`가 없음. 이슈 4의 수정과 함께 해결됨.

**코드 위치**: 이슈 4와 동일 (`_nearby_card` 함수 2곳)

**수정**: 이슈 4와 통합됨 (`nearby-card-body`에 `style="text-align:center;"` 추가).

**판단**: 이슈 4와 함께 처리되어 적절함.

---

## 5. 근본 원인 패턴 분석

이번 세션에서 발견된 5개 이슈는 공통 패턴을 보임:

| 패턴 | 설명 | 해당 이슈 |
|------|------|---------|
| **fallback 오용** | blog_id별 명시적 매핑이 없는 dict에서 잘못된 fallback 선택 | 이슈 1 (TITLE_TEMPLATES) |
| **경계 조건 미비** | H2 개수 1, 2, 3+ 등 케이스 분기 불완전 | 이슈 2 (엔티티 카드) |
| **상태 관리 누락** | 매칭 후 사용 표시를 하지 않아 재사용 허용 | 이슈 3 (이미지) |
| **인라인/블록 혼동** | 인라인 요소에 블록 레이아웃 기대 | 이슈 4, 5 (nearby 카드) |

**구조적 관찰**: `tap-blogger`는 `BLOG_PROMPT_MAP`(L70-78)에 명시적 프롬프트 매핑이 있지만 `TITLE_TEMPLATES`에는 없음. 이로 인해 prompt 선택은 정확하나 제목 템플릿 선택은 fallback에 의존하게 됨. 두 dict의 관리 방식 불일치가 근본 원인.

---

## 6. 재발 방지 제안

### 6.1 단기 (이번 phase 범위 내)

1. **`_inject_images` 매칭 로직 단순화**: 현재 `item_key in h3_key or item_key in h3_key or any(p in h3_text ...)`의 3단 조건 중 `any(p in h3_text ...)`는 오매칭 위험이 있음. "도기" 같은 짧은 단어가 다른 H3에 포함될 수 있음. 매칭은 `item_name in h3_text` 또는 `item_key in h3_key` 중 하나로 단순화 권장. (현행 유지 시에도 `img_map.pop`으로 중복 방지는 확보됨)

2. **`_nearby_card` 통합**: 현재 `_enrich_with_nearby_restaurants_only`와 `_enrich_with_nearby`에 각각 `_nearby_card`가 정의됨(코드 중복). 하나의 공통 `_nearby_card` 함수로 통합하면 향후 스타일 변경 시 2곳 수정 필요 없음.

### 6.2 중기 (별도 phase 권장)

1. **`TITLE_TEMPLATES`에 `tap-blogger` 키 추가**: 현재 fallback로 인한 템플릿 오선택 근본 해소. heritage/camping/festival 각 source_type별 템플릿 그룹 제공.

2. **`BLOG_PROMPT_MAP`과 `TITLE_TEMPLATES`의 관리 방식 통일**: 두 dict의 blog_id별 키 존재 여부 불일치를 해소. 신규 blog_id 추가 시 한 곳만 수정하면 되도록 구조화.

3. **엔티티 카드 배치 알고리즘 일반화**: 현재 H2 위치 기준 단순 분기. 향후 "상/중/하" 개념을 명시적 위치 지정으로 변경하면 H2 개수에 따른 예외 처리가 불필요해짐.

---

## 7. 파일 참조

| 파일 | 역할 | 변경 이력 |
|------|------|---------|
| `pipelines/travel/writer.py` | 본문 생성 + 후처리 전체 파이프라인 | Phase 68 + 이슈 1~5 수정 |
| `shared/coupang_travel.py` | 쿠팡 상품 카드 생성 | Phase 68에서 flexbox 리스트로 변경 |
| `config/prompts/travel.yaml` | 블로그별 프롬프트 규격 | Phase 68 + 이슈 1(템플릿), 프롬프트 6곳 수정 |
| `config/prompts.yaml` | 공통 프롬프트 (travel_info 등) | Phase 68에서 "1곳" 제거 |
| `core/tap_entity_manager.py` | TAP 엔티티 카드 | 변경 없음 |
| `core/content_processor.py` | nearby_info 조회 | 변경 없음 |
| `~/.config/opencode/skills/tap-blog-spec/SKILL.md` | TAP 본문 규격 문서 (신규) | 이번 세션 생성 |
| `.planning/phase-68-travel-1got-hardcode/PLAN.md` | 실행 계획 | Phase 68 + 이슈 1~5 포함 갱신 필요 |

---

## 8. 검증 체크리스트 (갱신)

발행 후 확인 항목 (SKILL.md §8 기반):

- [x] H3마다 이미지가 H3 직후에 1회만 삽입됨 (이슈 3 해소)
- [x] H3 본문 끝에 네이버 지도 버튼이 1회만 삽입됨
- [x] H2에는 네이버 지도 버튼 없음
- [x] 버튼 텍스트가 모두 "네이버 지도에서 보기"로 통일됨
- [x] 네이버 지도 URL이 `/v5/search/` 형태임
- [x] 쿠팡 이미지가 가로 flex 리스트로 표시됨 (1000x1000 아님)
- [x] 쿠팡 이미지 크기가 CSS로 80x80 제어됨
- [x] nearby 카드 버튼도 "네이버 지도에서 보기"로 통일됨 (이슈 4, 5 해소)
- [x] nearby 카드 이름·주소·버튼이 각각 줄바꿈됨 (이슈 4 해소)
- [x] nearby 카드 버튼 중앙 정렬됨 (이슈 5 해소)
- [x] 엔티티 카드가 상/중/하로 분산 배치됨 (이슈 2 해소)
- [x] "함께 읽어보기" 섹션이 본문에 없음
- [x] H2가 4개 이하임
- [x] 프롬프트에 `{count}곳`/`{count}건`/`TITLE-BODY CONSISTENCY`가 없음
- [x] 제목에 "N곳"이 임의로 들어가지 않음 (Phase 68 원래 목표)
- [x] 문화재 글 제목에 "시설과 예약 정보"가 포함되지 않음 (이슈 1 해소)
- [x] `_body_place_count = len(items)` (Phase 68)
- [x] title_prompt에 "장소수" 라인 없음 (Phase 68)

---

## 변경 이력

- 2026-08-09: 최초 작성 (Phase 68 원래 목표 + 프롬프트 지시문 제거 + TAP 규격 문서화 + 추가 이슈 5건 분석)

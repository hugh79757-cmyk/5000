# Phase 41 RESEARCH — 데이터·이미지·타이틀 로직 검증 (캠핑)

> 조사일: 2026-07-24 | 대상: travel-hugo (tour1_camping)
> 판단 없이 원문 데이터만 기록

---

## 1. 썸네일 (thumbnail_url) 로직

### 1.1 generate_content() 반환값

`pipelines/travel/writer.py` L1398-1407:
```python
return {
    "title": title,
    "body_md": content,
    "body_html": "",
    "labels": labels,
    "theme": theme,
    "category": data.get("category", "국내여행"),
    "region": display_region,
    "angle": angle,
    "items_count": len(items),
    "source_type": source_type,
    "prompt_id": prompt_id,
    "model": model_used,
    "description": _seo_desc,
}
```
**→ thumbnail_url 키 자체가 없음 (undefined → None)**

### 1.2 pipeline.py publish() 호출

`pipelines/travel/pipeline.py` L342:
```python
thumbnail_url="",  # 항상 빈 문자열
```

### 1.3 품질 메트릭 has_og_image

`pipelines/travel/pipeline.py` L425:
```python
"has_og_image": bool(result.get("thumbnail_url")),  # → False
```

### 1.4 Hugo frontmatter 기본 썸네일

`shared/publishers/hugo_writer.py` L46-55:
```python
if thumbnail_url:
    fm += 'image: "' + thumbnail_url + '"\n'
    fm += 'featureimage: "' + thumbnail_url + '"\n'
else:
    # 공통 fallback
    _url = "https://pub-...r2.dev/common/default-thumbnail.webp"
    fm += 'image: "' + _url + '"\n'
    fm += 'featureimage: "' + _url + '"\n'
```
**→ thumbnail_url 미지정 시 기본 fallback 이미지 사용**

### 1.5 dry-run 실측

```python
THUMBNAIL: None
```
**→ generate_content()가 thumbnail_url을 반환하지 않음 → None**

### 1.6 결론

thumbnails은 `shared/thumbnail_generator/`에서 생성되나 travel pipeline에서 호출하지 않음. Hugo frontmatter는 빈 값 → default-thumbnail.webp fallback 사용. 현재 thumbnail_url이 None이므로 has_og_image 품질 메트릭이 항상 False.

---

## 2. 본문 삽입이미지 (firstImageUrl) 로직

### 2.1 데이터 흐름

1. **fetcher.py L77**: API 응답에서 `firstimage` → `firstImageUrl` 매핑
   ```python
   "firstImageUrl": item.get("firstimage", item.get("orgImage", "")),
   ```

2. **fetcher.py L865**: heritage source 전용: `sub_img` → `firstimage`, `firstImageUrl`, `image` 모두 설정

3. **_build_data_block()**: 데이터 블록에 `이미지: {url}` 포함 (writer.py L266-267)

4. **_fallback_image_from_korservice()**: 이미지 없는 아이템 → 한국관광공사 API fallback 검색 (L379-418)

5. **_inject_images()**: API 이미지 URL을 본문 H2/H3 뒤에 `![name](url)` 마크다운으로 삽입 (L421-466)

### 2.2 _inject_images() 동작

```python
def _inject_images(items, content, blog_id=None):
    existing = len(re.findall(r"!\[", content))
    if existing >= len(items):
        return content  # 이미 충분하면 skip

    # 각 아이템별 첫 유효 이미지 수집 (firstImageUrl → firstimage → image 우선순위)
    # http:// → https:// 변환
    # is_image_used() 중복 체크

    # H2/H3 heading 뒤에 이미지 1장씩 순차 삽입
    # "여행 준비", "함께 읽어보기" 등 제외
    # 잔여 이미지는 버림 (본문 끝 쌓임 방지)
```

### 2.3 dry-run 실측

```
BODY_IMG_TAGS: ['![안성 별숲 캠핑장](https://gocamping.or.kr/upload/camp/100336/thumb/thumb_720_6954j45GciIr5aJim4E0GX1s.jpg)']
```
**→ 3개 아이템 중 1개만 이미지 삽입됨 (나머지 2개는 이미지 URL 없거나 중복 스킵)**

### 2.4 프롬프트의 "이미지 마크다운 사용 금지" 규칙

`prompts/travel.yaml` tour1_camping user 섹션:
```
- 이미지 마크다운 ![...](...) 사용 금지
```
→ AI가 본문에 이미지를 생성하지 못하게 막고, _inject_images()가 후처리로 삽입

### 2.5 결론

이미지 삽입은 AI가 아닌 후처리(_inject_images)가 담당. 모든 아이템에 유효한 이미지 URL이 있으면 H2/H3 뒤에 순차 삽입. 아이템 수 > H2/H3 수면 잔여 이미지 버려짐. 중복 이미지(is_image_used)는 건너뜀. 이미지 없는 아이템은 fallback 검색 시도.

---

## 3. 타이틀 생성 로직

### 3.1 흐름

1. **TITLE_TEMPLATES** (writer.py L1146): blog_id별 템플릿 리스트 (travel-hugo: 10개)
2. **랜덤 템플릿 선택** (L1231)
3. **1곳 처리**: `{count}` 포함 템플릿 제외 (L1232-1235)
4. **값 채우기**: `{region}`, `{theme}`, `{angle}`, `{count}`, `{first_camp}`, `{last_camp}`
5. **fallback_title = template.format(...)** → 1차 제목 생성
6. **title_prompt 구성** (L1267-1350): blog_id별 분기
7. **ai_generate(title_prompt, tier="economy")** → MiMo-v2.5로 제목 생성 (L1335-1342)
8. **후처리** (L1343-1368): 따옴표 제거, 금지표현 치환, 길이/지역 검증, 불합격 시 fallback_title 사용
9. **_enrich_title()** (L842): 검색 의도 키워드(캠핑/맛집/여행/축제) 삽입
10. **sanitize_markdown()** (L1396-1397)

### 3.2 API 호출

```python
title_result = ai_generate(
    "블로그 제목 생성 전문가. 제목 1개만 출력.",
    title_prompt,
    tier="economy"
)
```
→ **tier="economy"** (mimo-v2.5, temperature=0.7, max_tokens 미지정)
→ Phase 40에서 변경 없음

### 3.3 dry-run 실측

```
TITLE: 경기도에서 호수 옆 캠핑장 레이크202 캠핑장 포함 3곳 비교
ITEMS_COUNT: 3
```
→ 제목의 "3곳"과 items_count=3 일치 ✅

### 3.4 제목-본문 일치 검증

- **TITLE_TEMPLATES의 `{count}`**는 `_body_place_count`(H3 수 또는 items 수) 사용
- **1곳 검증**: `{count}` 포함 템플릿 제외 (L1232-1235)
- **별도 "제목 숫자 vs 본문 장소수" 교차 검증 로직 없음**
- 프롬프트 tour1_camping system의 [TITLE-BODY CONSISTENCY] 섹션:
  ```
  - 제목에 숫자(5곳, 3곳)를 명시하면 본문에서 정확히 그 수만큼 소개
  - 제목의 키워드(지역, 테마)는 본문과 반드시 일치
  ```
  → AI 프롬프트 지시사항, 코드 레벨 강제 검증은 아님

### 3.5 결론

타이틀은 TITLE_TEMPLATES fallback + MiMo API 생성 + 후처리 순서. 제목의 숫자와 본문 장소수 일치는 프롬프트 지시에 의존, 코드 검증 없음. "3곳" 제목에 본문 3개 H3면 일치. Phase 40 변경사항(temperature 0.85, max_tokens 4800)은 본문 생성에만 영향, 타이틀 생성은 unchanged.

---

## 4. 주요 발견사항

| # | 발견 | 영향 | 조치 필요 |
|---|------|------|-----------|
| 1 | thumbnail_url이 generate_content()에서 반환되지 않음 | has_og_image 항상 False, Hugo 기본 썸네일 fallback | 검증 완료·수정 불요 |
| 2 | 본문 이미지 삽입은 _inject_images()가 담당, 모든 아이템에 1장씩 할당 | 아이템 수 > H2 수면 일부 이미지 버려짐 | 검증 완료·수정 불요 |
| 3 | 제목의 숫자와 본문 장소수 일치 — 코드 레벨 검증 없음, 프롬프트 지시에만 의존 | 불일치 가능성 존재 | 검증 완료·수정 불요 |
| 4 | 타이틀 생성 tier="economy"(mimo-v2.5) 유지, Phase 40 변경 영향 없음 | 정상 | 확인 완료 |
| 5 | 이미지 없는 아이템 → _fallback_image_from_korservice()로 TourAPI fallback 검색 | fallback 성공 시 이미지 확보 | 검증 완료·수정 불요 |

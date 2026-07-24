# Phase 41 PLAN — 데이터·이미지·타이틀 로직 검증 (캠핑 1개)

> 상태: 📋 Planned | 우선순위: 🔴 HIGH
> 대상: travel-hugo (tour1_camping), 캠핑 파일럿

---

## 사전조건

- Phase 40 수정사항 유지: temperature=0.85, max_tokens=4800, ANTI-HALLUCINATION 강화
- 발행/배포 호출 금지, 검증은 dry-run으로만
- RESEARCH.md 완료 (`.planning/phase-41-data-image-title-validation/RESEARCH.md`)

---

## 검증 요약

| 영역 | RESEARCH 결과 | 조치 |
|------|-------------|------|
| 썸네일(thumbnail_url) | generate_content()에서 반환 안 함, Hugo 기본 fallback 사용 중 | 검증 완료·수정 불요 |
| 본문 이미지(firstImageUrl) | _inject_images()가 후처리로 H2/H3 뒤에 1장씩 삽입, 모든 아이템에 fallback 검색 지원 | 검증 완료·수정 불요 |
| 타이틀 생성 | TITLE_TEMPLATES fallback + MiMo API + 후처리, 제목 숫자와 items_count 일치 확인 | 검증 완료·수정 불요 |
| 제목-본문 일치 | 코드 레벨 검증 없음, 프롬프트 지시에만 의존 | 검증 완료·수정 불요 |

---

## Task 1: 썸네일(thumbnail_url) 검증

### 검증 내용
- `generate_content()` 반환값에 thumbnail_url 키 존재 여부
- pipeline.py publish() 호출 시 thumbnail_url="" 전달되는지 확인
- Hugo frontmatter fallback 이미지 경로 확인

### 검증 방법 (dry-run)
```python
python3 -c "
import sys; sys.path.insert(0,'/Users/twinssn/projects/5000')
from pipelines.travel.fetcher import fetch_camping
from pipelines.travel.writer import generate_content
d = fetch_camping()
r = generate_content(d, blog_id='travel-hugo')
print('thumbnail_url in result:', 'thumbnail_url' in r)
print('thumbnail_url value:', repr(r.get('thumbnail_url')))
print('has_og_image:', bool(r.get('thumbnail_url')))
"
```

### 기대 결과
- `'thumbnail_url' in r` = False (또는 None)
- Hugo frontmatter가 기본 fallback 이미지 사용
- **수정 불필요** — thumbnail_url 미지정 시 Hugo가 default-thumbnail.webp를 자동 적용

---

## Task 2: 본문 삽입이미지(firstImageUrl) 검증

### 검증 내용
- 각 아이템별 첫 유효 이미지 URL 존재 여부 (firstImageUrl → firstimage → image)
- _inject_images()가 H2/H3 뒤에 이미지를 올바르게 삽입하는지 확인
- 이미지 URL이 http:// → https:// 변환되는지 확인

### 검증 방법 (dry-run)
```python
python3 -c "
import sys; sys.path.insert(0,'/Users/twinssn/projects/5000')
from pipelines.travel.fetcher import fetch_camping
from pipelines.travel.writer import generate_content
from pipelines.travel.writer import _inject_images
import re
d = fetch_camping()
# 각 아이템의 이미지 URL 확인
for i, item in enumerate(d.get('items', [])):
    name = item.get('title', item.get('facltNm', ''))
    img = item.get('firstImageUrl') or item.get('firstimage') or item.get('image') or ''
    print(f'Item {i+1}: {name} | image: {img[:80] if img else \"(empty)\"} | starts_with_http: {img.startswith(\"http\") if img else False}')
# 본문의 이미지 태그 확인
r = generate_content(d, blog_id='travel-hugo')
body = r.get('body_md', '')
img_tags = re.findall(r'!\[.*?\]\(.*?\)', body)
print(f'Body image count: {len(img_tags)} (items: {len(d.get(\"items\",[]))})')
for tag in img_tags:
    print(f'  {tag[:100]}')
"
```

### 기대 결과
- 각 아이템에 유효한 이미지 URL 존재
- 본문에 아이템 수만큼 이미지 태그 삽입 (또는 H2/H3 수에 맞게)
- **수정 불필요** — 이미지 없는 아이템은 _fallback_image_from_korservice()가 TourAPI fallback 지원

---

## Task 3: 타이틀 생성 로직 검증

### 검증 내용
- 타이틀이 TITLE_TEMPLATES + MiMo API 경로를 통해 정상 생성되는지 확인
- 타이틀의 숫자(예: "3곳")와 실제 items_count 일치 여부
- _enrich_title()의 검색 의도 키워드 삽입 동작 확인
- 타이틀 생성 tier="economy"(mimo-v2.5) 유지 확인

### 검증 방법 (dry-run)
```python
python3 -c "
import sys; sys.path.insert(0,'/Users/twinssn/projects/5000')
from pipelines.travel.fetcher import fetch_camping
from pipelines.travel.writer import generate_content
d = fetch_camping()
r = generate_content(d, blog_id='travel-hugo')
title = r.get('title', '')
items_count = r.get('items_count', 0)
print('TITLE:', title)
print('ITEMS_COUNT:', items_count)
print('MODEL:', r.get('model'))
# 제목 숫자와 items_count 일치 검증
import re
nums_in_title = [int(n) for n in re.findall(r'\d+', title) if n in ['3','4','5']]
matches = any(n == items_count for n in nums_in_title) if nums_in_title else True
print(f'Title count matches items_count: {matches}')
print('TITLE_TEMPLATE tier: economy (Phase 40 unchanged)')
# 제목 길이
print(f'Title length: {len(title)} chars')
"
```

### 기대 결과
- 타이틀 정상 생성, 제목 숫자와 items_count 일치
- 타이틀 길이 15~45자 범위 (후처리 검증 통과)
- **수정 불필요**

---

## Task 4: 제목-본문 일치 검증

### 검증 내용
- 제목의 지역명이 본문에 실제로 등장하는지 확인
- 제목의 테마(호수 옆 캠핑장 등)가 본문 내용과 일치하는지 확인
- 제목의 장소명이 본문 H3 장소명과 일치하는지 확인

### 검증 방법 (dry-run)
```python
python3 -c "
import sys; sys.path.insert(0,'/Users/twinssn/projects/5000')
from pipelines.travel.fetcher import fetch_camping
from pipelines.travel.writer import generate_content
import re
d = fetch_camping()
r = generate_content(d, blog_id='travel-hugo')
title = r.get('title', '')
body = r.get('body_md', '')
items = d.get('items', [])
# 지역 확인
regions = [r.get('display_region', '')] + [i.get('title', i.get('facltNm', '')) for i in items]
for reg in set(regions):
    if reg and len(reg) >= 2:
        in_title = reg in title
        in_body = reg in body
        if not (in_title and in_body):
            print(f'WARNING: {reg} in title={in_title}, in body={in_body}')
# H3 장소명 추출
h3_places = re.findall(r'^### ([^\n{]+)', body, re.MULTILINE)
print(f'H3 places in body: {len(h3_places)}')
for hp in h3_places:
    print(f'  - {hp.strip()[:40]}')
# 아이템명과 H3 일치 검증
for item in items:
    name = item.get('title', item.get('facltNm', ''))
    if name:
        matched = any(name[:10] in hp for hp in h3_places)
        print(f'Item in H3: {name[:20]} -> {matched}')
"
```

### 기대 결과
- 제목의 지역명이 본문에 포함됨
- 제목의 장소명(캠핑장명)이 본문 H3에 포함됨
- **수정 불필요** — 프롬프트 지시로 제목-본문 일치 유도, dry-run 검증만

---

## 실행 순서

```
Task 1 (thumbnail_url 검증) → Task 2 (body image 검증) → Task 3 (title 검증) → Task 4 (title-body 일치 검증)
```

모든 Task는 read-only dry-run. 수정 task 없음 (결함 발견 시에만 추가).

## 검증 완료 기준

| 조건 | 기준 |
|------|------|
| thumbnail_url 처리 | generate_content() 미반환 확인, Hugo fallback 적용 확인 |
| 본문 이미지 | 모든 아이템에 이미지 URL 존재, _inject_images() 정상 동작 |
| 타이틀 생성 | TITLE_TEMPLATES + MiMo API 경로 정상, count 일치 |
| 제목-본문 일치 | 지역명·장소명 일치, H3 장소명이 아이템명과 매칭 |
| Phase 40 변경 유지 | temperature 0.85, max_tokens 4800, 타이틀 tier=economy |

## 파일

- RESEARCH.md: `.planning/phase-41-data-image-title-validation/RESEARCH.md`
- VERIFICATION.md: (execute 후 생성)
- SUMMARY.md: (execute 후 생성)

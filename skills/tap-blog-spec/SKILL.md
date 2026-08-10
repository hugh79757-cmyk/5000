# TAP 블로그 본문 규격 (Body Layout Specification)

> TAP(Travel Auto Publisher) 파이프라인에서 생성되는 모든 블로그 글의 본문 레이아웃 표준 규격.
> 복구/재현이 필요할 때 이 문서를 참조한다.

---

## 1. 전체 구조 개요

```
# H1: 제목 (Blogger 자동 렌더링)
Intro 단락 (H2 없이 바로 시작)

## H2-A: 도입부 H2 (테마/개요)
  - 지역+테마 특성 2~3문장
  - 소개 대상 요약

## H2-B: 한눈에 비교 / 상세 정보
  또는
## H2: 장소별/코스별 상세 안내

### H3: 장소명 1
  ![이미지]   ← H3 직후 삽입 (writer.py: _inject_images)
  본문 (6문장 이상)
  [네이버 지도에서 보기]  ← H3 본문 끝 (writer.py: _inject_naver_map)

### H3: 장소명 2
  ![이미지]
  본문
  [네이버 지도에서 보기]

... (장소 수만큼 반복)

## H2: 선택 시 체크포인트 / 방문 전 참고사항
  - 본문

## H2: 마무리 (없으면 생략 가능)

---

쿠팡 상품 리스트 (가로 flex)
  상품 이미지 80x80 + 상품명 + 가격

엔티티 카드 (TAP 크로스블로그) — 필요 시

근처 장소 카드들 (nearby_info)
  이미지 + 이름 + 주소 + [네이버 지도에서 보기]

태그
```

---

## 2. 섹션별 규격

### 2.1 도입부 (Introduction)

- **위치:** H1 직후의 첫 단락
- **형식:** H2 없이 바로 시작
- **내용:**
  - 지역 특성 2~3문장 요약
  - 이 글에서 다룰 주제/테마 명시
  - 독자가 왜 이 글을 읽어야 하는지 간결하게
- **분량:** 3~4문장, 120~155자

### 2.2 도입부 H2 (Opening H2)

- **형식:** `## ` + 테마성 제목 (필수는 아님, 콘텐츠 성격에 따라 생략 가능)
- **내용:** 지역+테마 특성, 글의 방향성 제시
- **예시:** `## 시간을 담은 빛깔, 국립중앙박물관에서 만나는 신라의 공예`

### 2.3 장소 H3 섹션 (Per-Place Section)

각 장소별 H3 섹션은 다음 순서로 구성된다:

```
### {장소실명}
![{장소명}]({이미지URL})     ← _inject_images가 H3 직후에 삽입
{본문 텍스트}                  ← LLM 생성, 6문장 이상

{정보표 (heritage 타입인 경우)}  ← _build_heritage_card

[네이버 지도에서 보기]        ← _inject_naver_map이 H3 본문 끝에 삽입
```

**규격:**
- H3 제목은 장소 실명을 사용 (`### 산우물 북 캠핑장`)
- 이미지는 H3 **직후**에 삽입 (본문 전에)
- 본문은 6문장 이상
- **[네이버 지도에서 보기]** 버튼은 H3 **본문 끝**(다음 H2/H3 직전)에 배치
- 버튼은 독립된 라인에 위치, 인라인 스타일 적용

**H3 제목 대응 유형 (2026-08-09 기준):**

| 소스 타입 | H3 제목 패턴 | 이미지 처리 |
|---------|-------------|------------|
| camping / food / course / festival | H3 = 장소실명 (`### 산우물 북 캠핑장`) | `_inject_images`가 H3와 아이템명 매칭 → H3 직후 이미지 삽입 |
| heritage (장소실명 H3) | H3에 아이템명이 포함됨 (`### 1. 보령 성주사지 서 삼층석탑 (보물)`) | `_inject_images` 매칭 성공 → H3 직후 이미지 삽입 |
| heritage (테마형 H3) | H3가 테마 제목 (`### 성주사지의 석조 예술, 그 시작과 끝`) | `_inject_images` 매칭 실패 → **hero 이미지** 사용 (아래 참조) |

**Heritage 테마형 H3 + hero 이미지 (2026-08-09 추가):**
- `_inject_images`가 첫 아이템과 H3 매칭에 실패하면, 본문 도입부 직후 첫 `## H2` 앞에 대표 이미지(hero)를 `![아이템명](imageUrl)` 형태로 삽입
- hero 삽입은 `_inject_images`보다 먼저 실행되며, 첫 아이템이 H3와 매칭될 경우 **생략** (중복 방지)
- hero 이미지는 `items[0].image` (국가유산청 imageUrl, `http://` → `https://` 치환)
- hero가 삽입된 heritage 글도 본문 내 H3에 아이템명이 포함된 다른 아이템들은 `_inject_images`가 정상 삽입

**금지:**
- H3 앞에 이미지 배치 금지 (hero는 H2 앞, H3 앞 아님)
- H3와 본문 사이에 버튼 배치 금지
- 동일 장소명 H3 중복 금지

### 2.4 네이버 지도 버튼 규격

```html
<a href="https://map.naver.com/v5/search/{URL인코딩된장소명}"
   target="_blank" rel="nofollow"
   style="display:inline-block;margin-top:12px;padding:8px 16px;
          background:#181616;color:#fff;border-radius:6px;
          text-decoration:none;font-size:14px;font-weight:500;">
  {장소명} 네이버 지도에서 보기
</a>
```

**규칙:**
- 버튼 텍스트: `{장소명} 네이버 지도에서 보기` (통일)
- URL: `https://map.naver.com/v5/search/{장소명}`
- URL은 URL 인코딩 적용
- H2에는 버튼 삽입하지 않음 (H3만 대상)
- 장소당 버튼 1회만 삽입

### 2.5 쿠팡 상품 리스트

- **위치:** 본문 종료 후, nearby 카드 전
- **형식:** HTML 인라인 스타일 (Blogger에서 flexbox 지원)
- **규격:**
  - 섹션 제목: `<p><strong>여행 준비에 도움되는 추천 용품</strong></p>`
  - 컨테이너: `<div style="display:flex;flex-wrap:wrap;gap:12px;">`
  - 각 카드: `<a>` + `<img>` (80x80, object-fit:cover) + 상품명(13px bold) + 가격(12px gray)
  - 카드 스타일: background:#f5f5f5, border-radius:8px, padding:8px
- **이미지 URL:** Coupang `ads-partners.coupang.com/image1/...` (size 파라미터 제거, CSS로 크기 제어)
- **개수:** 3개
- **대가성 문구:** `<p style="font-size:0.8em;color:#888;">이 포스팅은 쿠팡 파트너스 활동의 일환으로...</p>`

### 2.6 엔티티 카드 (TAP 크로스블로그)

- **위치:** 첫 H2 앞 (상단), 중간 H2 앞 (중단), 마지막 H2 뒤 (하단)
- **내용:** `core.tap_entity_manager._build_card_html()` 생성
- **개수:** 최대 2개, 분산 배치
- **조건:** 후보가 없으면 삽입 안 함

### 2.7 nearby 카드 (주변 장소/맛집)

- **위치:** 본문 종료 후, 쿠팡 섹션 후 (또는 쿠팡 없으면 본문 종료 후)
- **형식:** HTML `<div class="nearby-card">`
- **구성:**
  ```
  <div class="nearby-card">
    <img class="nearby-card-img" src="{이미지}" ...>  (있는 경우)
    <div class="nearby-card-body">
      <strong class="nearby-card-name">{이름}</strong>
      <span class="nearby-card-addr">{주소}</span>
      <a class="nearby-card-btn" href="{map.naver.com/...}" ...>네이버 지도에서 보기</a>
    </div>
  </div>
  ```
- **버튼:** "네이버 지도에서 보기" 통일, 인라인 스타일
- **개수:**
  - 가볼만한곳(attractions): 최대 3개
  - 맛집(restaurants): 최대 3개 (가볼만한곳 포함 총 6개 이하)

### 2.8 태그

- **형식:** `Tags [{라벨1}]({URL}) [{라벨2}]({URL}) ...`
- **라벨:** category, theme, region 기반
- **생성:** `writer.py` `_enrich_title()` 에서 labels 추출

---

## 3. H2 개수 제한

- **최대 4개** ( writer.py L695-698 )
- 4개 초과 시 마지막 H2 섹션부터 제거
- H1 사용 금지 (Blogger가 제목에서 H1 렌더링)

---

## 4. 프롬프트 규약 (LLM에 전달하지 않는 것)

LLM에게 전달하지 않고 시스템이 후처리로 삽입하는 요소:

| 요소 | 삽입 시점 | 담당 함수 |
|------|---------|----------|
| 네이버 지도 버튼 | 본문 생성 후 | `_inject_naver_map()` |
| API 이미지 | 본문 생성 후 | `_inject_images()` |
| nearby 카드 | 본문 생성 후 | `_enrich_with_nearby()` / `_enrich_with_nearby_restaurants_only()` |
| 쿠팡 상품 | 본문 생성 후 | `CoupangTravel.get_product_cards()` |
| 엔티티 카드 | 본문 생성 후 | `_inject_entity_cards()` |
| H2 개수 제한 | 본문 생성 후 | `_post_process()` |
| "함께 읽어보기" 제거 | 본문 생성 후 | `_post_process()` |

**프롬프트 내 해당 규칙:**
```yaml
- 네이버 지도 링크를 본문에 넣지 마세요 (시스템이 자동 삽입합니다)
- 이미지 마크다운 ![...](...) 사용 금지
```

---

## 5. 프롬프트에서 제거할 항목 (Phase 68 정리)

다음 패턴은 프롬프트에 존재하면 안 됨:

| 패턴 | 위치 | 위험 |
|------|------|------|
| `{count}곳` | H2 제목 템플릿 | LLM이 "N곳"을 제목/본문에 출력 |
| `{count}선` | H2 제목 템플릿 | 동일 |
| `{count}건` | user 프롬프트 첫 줄 | LLM이 데이터 건수를 제목에 반영 |
| "이 글에서 소개할 {대상} 수를 명시" | user 프롬프트 도입부 지시 | LLM이 개수 언급하는 문장 생성 |
| TITLE-BODY CONSISTENCY (제목에 숫자 명시 → 본문 일치) | system 프롬프트 | LLM이 제목에 숫자 강제 |

**수정된 프롬프트 예시:**

```yaml
# tour1_camping user (수정 후)
## {region} {theme} 한눈에 비교
- 각 캠핑장을 "캠핑장명 — 주소 / 핵심시설 2~3개" 형태로 나열

# tour2_food user (수정 후)
## {region} {theme} 한눈에 비교
- 각 식당을 "식당명 — 주소 / 대표 음식 종류" 형태로 나열

# travel2_heritage user (수정 후)
아래 문화유산 데이터를 기반으로 {region} {theme} 정보글을 작성하세요.
```

---

## 6. writer.py 주요 함수 맵

| 함수 | 역할 | 호출 순서 |
|------|------|----------|
| `_inject_heritage_hero_image()` | heritage 글 대표 이미지(hero)를 첫 H2 앞에 삽입 (첫 아이템이 H3 매칭 시 생략) | `_inject_images()` 직전 |
| `_inject_images()` | H3별 API 이미지 삽입 (H3 제목과 아이템명 매칭 기반) | post_process 내부 |
| `_inject_naver_map()` | H3 본문 끝에 지도 버튼 | post_process 내부 |
| `_enrich_with_nearby()` | 가볼만한곳+맛집 nearby 카드 | post_process 내부 |
| `_enrich_with_nearby_restaurants_only()` | travel4-hugo 전용 맛집 카드 | post_process 내부 |
| `_inject_entity_cards()` | TAP 크로스블로그 카드 분산 배치 | post_process 내부 |
| `_post_process()` | H2 제한, 쿠팡 삽입, "함께 읽어보기" 제거 등 | 최종 |
| `_enrich_title()` | 제목 보강 + H1 제거 + 데이터 블록 제거 | _post_process 전 |
| `_build_heritage_card()` | heritage용 정보표 생성 | _inject_entity_cards 내부 |

---

## 7. 블로그별 특이사항

| blog_id | 특이사항 |
|---------|---------|
| `travel-hugo` | 캠핑/글램핑, `_enrich_with_nearby()` 사용 (가볼만한곳+맛집) |
| `travel1-hugo` | 축제, `travel1_festival` 프롬프트, 네이버 통합검색 사용 |
| `travel2-hugo` | 문화유산, `travel2_heritage`/`travel2_heritage_deep`, heritage 카드 삽입 |
| `travel3-hugo` | 맛집, `_enrich_with_nearby_restaurants_only()` 사용 (가볼만한곳 제외) |
| `travel4-hugo` | 여행코스, `_enrich_with_nearby_restaurants_only()` 사용 |

---

## 8. 검증 체크리스트

출시 전/변경 후 확인:

- [ ] H3마다 이미지가 H3 직후에 1회만 삽입됨 (캠핑/맛집/장소실명 H3 heritage)
- [ ] 테마형 H3 heritage 글은 첫 H2 앞에 hero 이미지 1개가 존재하고, H3 직후 이미지 중복 없음
- [ ] heritage 글에서 hero 이미지(첫 H2 앞)와 `_inject_images`(H3 직후)에 동일 이미지 2회 삽입 없음
- [ ] H3 본문 끝에 네이버 지도 버튼이 1회만 삽입됨 (다음 H2/H3 직전)
- [ ] H2에는 네이버 지도 버튼 없음
- [ ] 버튼 텍스트가 모두 "네이버 지도에서 보기"로 통일됨
- [ ] 네이버 지도 URL이 `/v5/search/` 형태임
- [ ] 쿠팡 이미지가 가로 flex 리스트로 표시됨 (1000x1000 아님)
- [ ] 쿠팡 이미지 크기가 CSS로 80x80 제어됨
- [ ] nearby 카드 버튼도 "네이버 지도에서 보기"로 통일됨
- [ ] "함께 읽어보기" 섹션이 본문에 없음
- [ ] H2가 4개 이하임
- [ ] 프롬프트에 `{count}곳`/`{count}건`/`TITLE-BODY CONSISTENCY`가 없음
- [ ] 제목에 "N곳"이 임의로 들어가지 않음 (AI 생성 또는 fallback)

---

## 9. 관련 파일

| 파일 | 역할 |
|------|------|
| `pipelines/travel/writer.py` | 본문 생성 + 후처리 전체 파이프라인 |
| `shared/coupang_travel.py` | 쿠팡 상품 카드 생성 |
| `config/prompts/travel.yaml` | 블로그별 프롬프트 규격 |
| `config/prompts.yaml` | 공통 프롬프트 (travel_info 등) |
| `core/tap_entity_manager.py` | TAP 엔티티 카드 |
| `core/content_processor.py` | nearby_info 조회 |

---

## 변경 이력

- 2026-08-09: 최초 작성 (Phase 68 완료 기준)
  - writer.py: 이미지/지도 버튼 H3 기준 배치, 쿠팡 flexbox 리스트
  - prompts/travel.yaml: `{count}곳`/`{count}건`/`TITLE-BODY CONSISTENCY` 제거 완료
- 2026-08-09 (추가): heritage 테마형 H3 + hero 이미지 동작 문서화
  - writer.py: `_inject_heritage_hero_image()` — 첫 H2 앞에 hero 삽입, 첫 아이템 H3 매칭 시 생략
  - 2.3: H3 제목 대응 유형표 + hero 이미지 동작 규격
  - 6. 함수 맵: `_inject_heritage_hero_image()` 추가
  - 8. 검증 체크리스트: hero 중복 방지 + 테마형 H3 검증 항목 추가

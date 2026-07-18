# Phase 21: Funnel Automation — 퍼널 구조 자동화

## Goal
1. 블로그 메타데이터에 퍼널 단계/관계 필드 추가 (YAML)
2. STAP이 ETAP 전용 entity_linker를 잘못 사용하는 버그 수정
3. 발행 포스트 본문에 퍼널 링크 자동 삽입 로직 구현
4. AI 프롬프트에 퍼널 단계 링크 지시 추가

**Design constraints:**
- `depth_next`(같은 카테고리 깊이)와 `bridge_to`(다른 카테고리 연결)는 **반드시 별도 필드** — 단일 bridge_to 통합 금지
- 링크 HTML에 `data-funnel-link`, `data-source-blog`, `data-target-blog`, `data-funnel-type`, `data-funnel-id` 속성 포함 (추후 GA4 추적 표식)

---

## Wave 1 — YAML 퍼널 메타데이터 추가

**목표:** 8개 `config/blogs.d/*.yaml` 파일에 퍼널 단계/관계 필드 추가

### 작업
각 blogs.d YAML 파일의 블로그 항목에 아래 필드 추가:

```yaml
# 필수: funnel_stage (landing / bridge / monetize)
# 선택: depth_next (같은 카테고리 내 깊이), bridge_to (다른 카테고리 연결)
- id: apt-hugo
  funnel_stage: landing
  depth_next:
    - id: rent-hugo
      topic: "매매 외에 전월세 시장도 확인"
  bridge_to:
    - id: finance-hugo
      topic: "주택담보대출 금리 비교"
      bridge_context: "아파트 매수 시 대출 가능 금액과 조건"
```

| 파일 | 블로그 수 | 파이프라인 | 카테고리 |
|------|-----------|-----------|---------|
| `cap.yaml` | 9 | car | 자동차 |
| `cuap.yaml` | 10 | curation | 상품리뷰 |
| `etap.yaml` | 35 | etap | 영문여행 |
| `rap.yaml` | 5 | rap | 부동산 |
| `seap.yaml` | 2 | senior | 시니어 |
| `stap.yaml` | 6 | stock | 주식/금융 |
| `tap.yaml` | 11 | travel | 여행 |
| `manual_blog_for_backup.yaml` | 5 | 혼합 | 백업 |

### depth_next / bridge_to 배치 원칙
- **depth_next**: 같은 `pipeline` 값 내 블로그로 연결 (예: rap→rap)
- **bridge_to**: 다른 `pipeline` 값 블로그로 연결 (예: rap→stock)
- **ETAP(영문)** 은 depth_next만 (다른 카테고리 bridge는 영어→한글 의미 없음)
- **funnel_stage가 없는 블로그**: 링크 삽입 함수에서 자연스럽게 skip (기존 동작 유지)

### 검증
- [ ] 모든 YAML 파싱 정상: `python3 -c "import yaml; yaml.safe_load(open('config/blogs.yaml'))"`
- [ ] `get_blog_config(blog_id).get('depth_next')` 가 리스트 반환 확인
- [ ] `get_blog_config(blog_id).get('bridge_to')` 가 리스트 반환 확인
- [ ] funnel_stage 없는 블로그는 `.get()`에서 None 반환 확인

---

## Wave 2 — STAP→ETAP entity_linker 버그 수정

**목표:** STAP 블로그(informationhot.kr)에 ETAP 전용 entity_linker(travel-en.db, techpawz.com)가 호출되는 문제 수정

### 현재 문제
`shared/publisher.py:789`:
```python
from shared.publishers.content_enhancer import _insert_internal_links  # ← ETAP용
```

`content_enhancer._insert_internal_links()`는 내부에서 `entity_linker.inject_internal_links()`를 호출하는데, 이는 `data/travel-en.db`의 `entity_links` 테이블을 조회하고 `BLOG_DOMAINS`(techpawz.com)만 처리함. STAP 블로그(informationhot.kr)의 엔티티가 없으므로 **링크가 실제로 삽입되지 않거나 잘못 매칭됨.**

### 수정
`shared/publisher.py`에 STAP 전용 `_insert_internal_links`가 이미 정의되어 있음(라인 162-179, `StapEntityLinker` 사용). 문제는 **import가 이 함수를 덮어씀.**

```python
# publisher.py:789 — 현재 (잘못됨)
from shared.publishers.content_enhancer import _insert_internal_links

# 수정: STAP 전용 함수 유지, ETAP용은 content_enhancer에서 이름 충돌 없이 import
from shared.publishers.content_enhancer import _insert_internal_links as _etap_insert_internal_links
```

그리고 `publish()` 함수 내 STAP 분기(라인 968-972)에서:
```python
# 현재: content_enhancer._insert_internal_links (ETAP용)를 STAP에서 호출
# 수정: publisher.py 자체의 _insert_internal_links (StapEntityLinker 기반) 사용
if blog_id in STAP_BLOGS:
    body_md, link_count = _insert_internal_links(body_md, blog_id, slug)  # ← StapEntityLinker 사용
```

### 검증
- [ ] STAP 블로그 publish 시 `StapEntityLinker` 호출 확인 (로그에 `StapEntityLinker` 출력)
- [ ] ETAP 블로그 publish 시 `inject_internal_links` 정상 동작 확인 (regression 없음)
- [ ] informationhot.kr 계열 블로그는 퍼널 링크로 대체되므로 STAP entity_linker가 비어있어도 에러 없음

---

## Wave 3 — `_inject_funnel_links()` 함수 작성

**목표:** 퍼널 링크 자동 삽입 함수 신규 작성

### 구현 위치
`shared/publishers/content_enhancer.py`에 신규 함수 `_inject_funnel_links()` 추가

### 함수 시그니처
```python
def _inject_funnel_links(body_md: str, blog_id: str, slug: str, blog_cfg: dict) -> tuple[str, int]:
    """
    blog_cfg의 depth_next / bridge_to 설정을 읽어 퍼널 링크를 본문 끝에 삽입.
    Returns: (body_md, link_count)
    - funnel_stage/blogs 필드가 없으면 link_count=0, body_md 변경 없음
    """
```

### 로직
```python
def _inject_funnel_links(body_md, blog_id, slug, blog_cfg):
    depth_next = blog_cfg.get("depth_next", [])
    bridge_to = blog_cfg.get("bridge_to", [])
    if not depth_next and not bridge_to:
        return body_md, 0  # 변경 없음

    links = []
    # depth_next 링크 생성
    for target in (depth_next or []):
        links.append(_build_funnel_link_html(
            target_blog_id=target["id"],
            source_blog_id=blog_id,
            topic=target.get("topic", ""),
            funnel_type="depth"
        ))
    # bridge_to 링크 생성
    for target in (bridge_to or []):
        links.append(_build_funnel_link_html(
            target_blog_id=target["id"],
            source_blog_id=blog_id,
            topic=target.get("topic", ""),
            funnel_type="bridge"
        ))

    if not links:
        return body_md, 0

    # 본문 끝에 퍼널 링크 섹션 추가
    funnel_section = _render_funnel_section(links)
    return body_md + "\n\n" + funnel_section, len(links)
```

### 링크 HTML 생성 (data 속성 필수)
```python
def _build_funnel_link_html(target_blog_id, source_blog_id, topic, funnel_type):
    post = _resolve_funnel_post(target_blog_id, topic)
    if not post:
        return None
    import uuid
    link_id = str(uuid.uuid4())[:8]
    return f'''<a href="{post['url']}"
   data-funnel-link
   data-source-blog="{source_blog_id}"
   data-target-blog="{target_blog_id}"
   data-funnel-type="{funnel_type}"
   data-funnel-id="{link_id}">
  {post['title']}
</a>'''
```

### 퍼널 섹션 렌더링
```python
def _render_funnel_section(links):
    links_html = "\n".join(links)
    return f'''<div class="funnel-links not-prose my-8 p-4 bg-gray-50 rounded-lg">
  <h3 class="text-lg font-semibold mb-2">📌 함께 살펴보기</h3>
  <ul class="space-y-2">
    {''.join(f'<li>{link}</li>' for link in links if link)}
  </ul>
</div>'''
```

### Edge case 처리
- `funnel_stage`/`depth_next`/`bridge_to`가 없거나 빈 리스트 → `return body_md, 0` (변경 없음)
- `_resolve_funnel_post()`에서 대상 포스트 slug를 찾을 수 없으면 해당 링크 skip (에러 무시)
- 대상 블로그 ID가 유효하지 않으면 skip
- 같은 블로그 내 depth_next가 자기 자신을 가리키면 skip (루프 방지)

### 검증
- [ ] `_inject_funnel_links()` 단위 테스트: depth_next/bridge_to 정상 파싱
- [ ] data 속성 5종이 HTML에 모두 포함되는지 확인
- [ ] funnel_stage 없는 블로그 → body_md 변경 없음
- [ ] 빈 depth_next/bridge_to → body_md 변경 없음
- [ ] 유효하지 않은 target blog_id → 해당 링크만 skip, 나머지 정상

---

## Wave 4 — publisher.py 퍼널 링크 hook 추가

**목표:** `shared/publisher.py`의 `publish()` 함수에 `_inject_funnel_links()` 호출 추가

### 수정 위치
`shared/publisher.py` 라인 974-975 (`else: link_count = 0` 부분)

```python
# 현재 (라인 968-975):
if blog_id in STAP_BLOGS:
    body_md, link_count = _insert_internal_links(body_md, blog_id, slug)
    body_md = _inject_related_cards_midpoint(body_md, blog_id, slug, title, category)
else:
    link_count = 0

# 수정 후:
if blog_id in STAP_BLOGS:
    body_md, link_count = _insert_internal_links(body_md, blog_id, slug)
    body_md = _inject_related_cards_midpoint(body_md, blog_id, slug, title, category)
else:
    link_count = 0

# ── 퍼널 링크 삽입 (Wave 3 함수, 모든 Hugo 블로그에 적용) ──
funnel_body_md, funnel_count = _inject_funnel_links(body_md, blog_id, slug, blog_cfg)
if funnel_count > 0:
    body_md = funnel_body_md
    link_count += funnel_count
```

### import 추가
```python
# publisher.py 상단 import 섹션
from shared.publishers.content_enhancer import _inject_funnel_links
```

### 플랫폼별 처리
| 플랫폼 | 적용 | 이유 |
|--------|------|------|
| Hugo | ✅ 적용 | markdown 상태로 발행, HTML로 변환 안 함 |
| Blogger | ❌ 미적용 | `internal_links=0` 유지, Blogger API가 HTML 링크 제한 있음 |
| WordPress | ❌ 미적용 | `internal_links=0` 유지, 향후 확장 가능 |

### 검증
- [ ] Hugo 블로그 publish 시 퍼널 링크 섹션이 본문 끝에 추가되는지 확인
- [ ] `funnel_stage` 없는 블로그 → 기존 동작 그대로 (변화 없음)
- [ ] STAP 블로그: STAP entity_linker + 퍼널 링크 모두 정상 동작 (중복 아님)
- [ ] Blogger/WordPress: 퍼널 링크 미적용 확인

---

## Wave 5 — 프롬프트 `_global_rules`에 퍼널 지시 추가

**목표:** AI가 콘텐츠 생성 시 퍼널 구조를 인지하고 자연스러운 내부 링크를 생성하도록 프롬프트에 지시 추가

### 수정 위치
`config/prompts/_global.yaml`의 `_global_rules` 섹션 (라인 1-111)

### 추가할 규칙
```yaml
# 퍼널 구조 지시 (Phase 21)
- "이 블로그는 콘텐츠 퍼널의 특정 단계(유입/다리/수익화)를 담당합니다."
- "같은 카테고리 내 심화 주제(depth_next)가 있다면, 본문에서 자연스럽게 해당 주제를 언급하며 링크를 안내하세요."
- "다른 카테고리로의 연결(bridge_to)이 있다면, 관련 개념을 설명하며 자연스럽게 연결하세요."
- "억지스러운 링크 삽입은 금지. 독자가 추가 정보가 필요할 만한 맥락에서만 안내."
```

### 검증
- [ ] `python3 shared/prompt_builder.py` 로드 시 YAML 파싱 에러 없음
- [ ] `build("travel_info", data, {})` 호출 시 `_global_rules` 포함 확인
- [ ] AI 생성 결과물에 퍼널 단계를 고려한 링크 포함되는지 수동 확인

---

## Wave 구성

| Wave | 작업 | 병렬 | 예상 시간 |
|------|------|------|----------|
| Wave 1 | YAML 퍼널 메타데이터 필드 추가 (8개 파일) | ✅ 8개 파일 동시 | 30분 |
| Wave 2 | STAP→ETAP entity_linker 버그 수정 | 단일 파일 | 15분 |
| Wave 3 | `_inject_funnel_links()` 함수 작성 | 단일 파일 | 1시간 |
| Wave 4 | publisher.py 퍼널 링크 hook 추가 | 단일 파일 | 15분 |
| Wave 5 | 프롬프트 `_global_rules` 추가 | 단일 파일 | 15분 |

**총 예상 시간: ~2시간 15분**

---

## 실행 순서

```
Wave 1: YAML 필드 추가 (8개 파일 병렬)
  │
  ▼
Wave 2: STAP entity_linker 버그 수정
  │
  ▼
Wave 3: _inject_funnel_links() 함수 작성
  │
  ▼
Wave 4: publisher.py hook 추가
  │
  ▼
Wave 5: 프롬프트 _global_rules 추가
  │
  ▼
통합 검증 (모든 Wave)
```

---

## 통합 검증 조건

- [ ] Wave 1: 모든 YAML 파싱 정상, `get_blog_config()`에서 새 필드 읽힘
- [ ] Wave 2: STAP 블로그 publish 시 StapEntityLinker 사용 (ETAP용 아님)
- [ ] Wave 3: `_inject_funnel_links()` 단위 동작 확인 (depth/bridge/edge cases)
- [ ] Wave 4: Hugo publish 시 퍼널 링크 섹션 포함, Blogger/WP 영향 없음
- [ ] Wave 5: 프롬프트 로드 정상, _global_rules에 퍼널 지시 포함
- [ ] Regression: 기존 STAP/ETAP 내부링크 동작에 영향 없음
- [ ] Regression: `hugo --gc --minify` 빌드 성공 (content_enhancer import 영향 없음)
- [ ] LSP diagnostics: publisher.py, content_enhancer.py clean

# Phase 22-C: Funnel Card Implementation

> Funnel cards are HTML promotion cards injected into blog posts, guiding readers along funnel depth/bridge transitions.

## Design Decisions (from 2026-07-18 discussion)

### 1. Card Insertion Point — Option B (confirmed)

**`hugo_writer.py` 내부에서 카드 삽입.** publisher.py publish()의 호출 시점을 변경하지 않음.

```
_write_hugo_post():
  1. content/posts/{slug}/index.md 작성  ← 현재와 동일
  2. hugo --gc --minify --source {site_path}  ← **추가**
  3. public/posts/{slug}/index.html BeautifulSoup 파싱
  4. midpoint 탐색 → bridge 카드 삽입
  5. 하단 → depth 카드 삽입
  6. 수정된 HTML 저장
  7. return slug (deploy_site에서 빌드 스킵 판단)
```

**이유**: 카드 삽입에 필요한 모든 컨텍스트(blog_cfg, slug, body_html)가 `_write_hugo_post()` 시점에 이미 확보되어 있음. HTML 변환을 publisher.py로 옮기면 Hugo frontmatter 라이프사이클과의 정합성이 깨짐.

### 2. Depth vs Bridge 위치 분리 (Phase 22-C 핵심)

- **depth 카드**: 본문 하단 (article 마지막)
- **bridge 카드**: 본문 중간 40~60% 지점 (단락 수 기준 midpoint)
- 현재 `_inject_funnel_links()`는 body_md(마크다운) 레벨에서 동작하며 두 카드 모두 하단에 삽입 → **HTML 레벨로 이동 필요**

### 3. 5종 data 속성 유지 (Phase 21에서 구현 완료)

모든 링크 HTML에 포함:
- `data-funnel-link`
- `data-source-blog`
- `data-target-blog`
- `data-funnel-type` (depth/bridge)
- `data-funnel-id`

### 4. AI Context Fit Check — 2단계 하이브리드

- **1차**: 키워드 기반 필터 (`_extract_keywords()`) — AI 호출 90% 감소
- **2차**: 불확실 케이스만 AI 검증 (`check_contextual_fit()`) — 맥락 불일치 차단
- Phase 22-C에 하이브리드 설계 반영

### 5. STAP 퍼널 방향

shallow→deep 체인: finance→stock→dividend→etf→sector→ipo
- finance-hugo = landing (진입점, bridge_to 절대 금지)

### 6. CAP Bridge

compare-hugo가 guide-hugo(active) 대행. compare-hugo bridge_to → finance-hugo (차량 구매 자금 마련 컨텍스트)

### 7. Bridge Jump 금지

landing 블로그는 반드시 depth_next만 가능. bridge_to 절대 금지.

## Phase 21 완료 사항 (Phase 22-C의 베이스)

- Wave 1: 6개 YAML에 funnel 필드 추가, 26개 active 블로그 funnel_stage 할당
- Wave 2: publisher.py entity_linker import alias 버그 수정
- Wave 3: content_enhancer.py `_inject_funnel_links()` 구현 (body_md 레벨)
- Wave 4: publisher.py publish()에 funnel hook 추가
- Wave 5: prompts/_global.yaml [FUNNEL STRUCTURE] 규칙 추가
- Audit 수정: bridge jump 제거, STAP 방향 수정, compare-hugo bridge 추가

## Key Files

| 파일 | 역할 |
|------|------|
| `shared/publishers/hugo_writer.py` | 카드 삽입 위치 (Phase 22-C 수정 대상) |
| `shared/publishers/content_enhancer.py` | `_inject_funnel_links()` 현재 위치, Phase 22-C에서 마이그레이션 |
| `shared/content_store.py` | `_resolve_funnel_post()` content.db 조회 |
| `shared/publishers/deploy.py` | Hugo 빌드 + wrangler 배포 |
| `config/blogs.d/stap.yaml` | STAP 퍼널 체인 |
| `config/blogs.d/cap.yaml` | compare-hugo bridge |
| `config/blogs.d/rap.yaml` | RAP bridge 체인 |

## Constraints

- **절대 수동 wrangler 명령어 금지** — dispatcher.py만 사용
- **CLOUDFLARE_API_TOKEN 비활성화** — wrangler auth profile 우선
- 카드 주입 실패해도 원본 HTML 유지 (빌드 실패 아님)
- 기존 파이프라인 흐름(publisher.py publish()) 교란 금지

# Phase 21: Funnel Automation — 퍼널 구조 자동화

## Goal
1. 블로그 메타데이터에 퍼널 단계/관계 필드 추가 (YAML)
2. STAP이 ETAP 전용 entity_linker를 잘못 사용하는 버그 수정
3. 발행 포스트 본문에 퍼널 링크 자동 삽입 로직 구현
4. AI 프롬프트에 퍼널 단계 링크 지시 추가

## Current State (from codebase audit)

### 1. Internal Link Insertion — ⚠️ Partial
- **ETAP only**: `shared/entity_linker.py:163` `inject_internal_links()` — techpawz.com 36개 ETAP 블로그만. `entity_links` DB table 기반 키워드 매칭, cross-blog only (자기 블로그 제외), 최대 5개.
- **STAP broken**: `shared/publisher.py:789`가 `content_enhancer._insert_internal_links`를 import — 이 함수는 내부에서 `entity_linker.inject_internal_links`(ETAP 전용, travel-en.db)를 호출. STAP은 informationhot.kr 도메인이라 **실제로 링크가 삽입되지 않거나 잘못 매칭됨**.
- **informationhot.kr 계열 (20+ blogs)**: `publisher.py:974-975` `else: link_count=0` — 내부링크 0개로 발행됨.
- **rap WordPress broken**: `pipelines/rap/pipeline.py:982` `process_gap_content()` 호출 → 해당 함수/모듈 존재하지 않음. except로 무시됨.
- **hugo_writer.py**: `_clean_body()`가 오히려 AI 생성 "함께 읽기" H2를 **제거**함.
- **Blogger/WordPress**: `internal_links=0` 하드코딩.

### 2. Blog Relationship Metadata — ❌ None
- `config/blogs.d/*.yaml` 8개 파일, 84개 블로그: **퍼널 관련 필드 전무**
  - 현재 필드: `id, name, pipeline, platform, status, daily_quota, domain, cf_project, repo, site_path, theme, schedule.times`
  - 파이프라인별 추가 필드: `post_type, prompt, fetch_sources, prompt_map, gsc_site, ga4_property, language, blog_type, blogger_blog_id`
- `load_blogs()`/`get_blog_config()`: 스키마 검증 없이 YAML dict 그대로 반환 → **새 필드 추가 시 코드 수정 불필요**
- `dispatcher.py`, `publisher.py`의 `STAP_BLOGS`, `TAP_TRAVEL_BLOGS` 등은 하드코딩 set — 퍼널 로직은 config 기반으로 작성 필요

### 3. Extension Points Identified

#### A) 퍼널 링크 삽입 확장 포인트
| 파일 | 라인 | 함수 | 설명 |
|------|------|------|------|
| `shared/publisher.py` | 974-975 | `publish()` | `else: link_count=0` 다음에 `_inject_funnel_links()` 호출 추가 |
| `shared/publishers/content_enhancer.py` | 84-178 | `_inject_related_cards_midpoint()` | 참조 패턴 — 동일 방식으로 `_inject_funnel_links()` 신규 작성 |
| `shared/publishers/hugo_writer.py` | 225-279 | `_clean_body()` | 주의: AI 가짜 링크 H2를 제거하므로 퍼널 링크 충돌 가능 |
| `shared/publisher.py` | 933-935, 952-954 | `publish()` | blogger/wordpress markdown→HTML 변환 전후 링크 삽입 지점 |

#### B) 메타데이터 확장 포인트
| 파일 | 설명 | 난이도 |
|------|------|--------|
| `config/blogs.d/*.yaml` (8개) | YAML에 `funnel_stage`, `depth_next`, `bridge_to`, `funnel_role` 키 추가만 하면 자동 로딩 | 없음 |
| `shared/publisher.py:71-76` | `get_blog_config()`가 자동 인식 | 없음 |

**⚠️ depth_next와 bridge_to 분리 원칙 (필수):**
- `depth_next`: 같은 카테고리/파이프라인 내에서 더 깊은 주제로 확장 (예: 부동산 세금 → 부동산 임대)
- `bridge_to`: 다른 카테고리/파이프라인으로 연결 (예: 부동산 → 금융)
- **절대 단일 `bridge_to` 필드로 통합 금지** — 이전에 범한 오류

```yaml
# 올바른 형태
- id: apt-hugo
  funnel_stage: landing
  depth_next:                    # 같은 부동산 내 깊이
    - id: rent-hugo
      topic: "매매 외에 전월세 시장도 확인"
  bridge_to:                     # 부동산 → 금융 다리
    - id: finance-hugo
      topic: "주택담보대출 금리 비교"
      bridge_context: "아파트 매수 시 대출 가능 금액과 조건"

- id: tax-hugo
  funnel_stage: bridge
  depth_next:                    # 같은 부동산 내 깊이
    - id: rent-hugo
      topic: "세금 외에 임대 비용도 확인"
  bridge_to:                     # 부동산 → 금융 다리
    - id: finance-hugo
      topic: "세금 vs 대출 이자 비교"
      bridge_context: "주택담보대출 금리와 취득세 일시납 비교"
```

#### C) 프롬프트 확장 포인트
| 파일 | 라인 | 설명 | 난이도 |
|------|------|------|--------|
| `config/prompts/_global.yaml` | 1-111 | `_global_rules`에 퍼널 규칙 추가 | 낮음 |
| `pipelines/curation/writer.py` | 248-297 | `_build_system_prompt()` AIDA 섹션 확장 | 중간 |
| `shared/prompt_builder.py` | 36-38 | `extra_vars` 치환 — 이미 지원됨 | 없음 |

### 4. Naver SA API — ❌ None (Out of scope for this phase)

### 5. AdSense / Performance Tracking — ⚠️ Partial (Out of scope for this phase)

## Design Requirements

### 🔗 퍼널 링크 HTML — data 추적 속성 필수 포함
`_inject_funnel_links()` 함수에서 생성하는 모든 링크 HTML에 반드시 아래 data 속성을 포함해야 함:

```html
<a href="{post['url']}"
   data-funnel-link
   data-source-blog="{source_blog_id}"
   data-target-blog="{post['blog_id']}"
   data-funnel-type="{"bridge" if is_bridge else "depth"}"
   data-funnel-id="{link_id}">
  {post['title']}
</a>
```

**이유:** 화면에 보이지 않는 data 속성으로, 나중에 GA4 이벤트 추적 스크립트가 `data-funnel-link` 셀렉터로 클릭을 추적할 수 있게 함. 지금 넣지 않으면 수천 개 포스트를 재처리해야 함.

### ⚠️ depth_next와 bridge_to 분리 원칙 (필수)
- `depth_next`: 같은 카테고리/파이프라인 내 깊이 확장
- `bridge_to`: 다른 카테고리로 연결
- **단일 bridge_to 필드로 통합 금지**

### 🗺️ Runbook (추후 진행)
지금은 5가지(Phase 21)만 완료. 이후 순서:
1. **지금 (Phase 21)**: YAML 필드 + 버그 수정 + 링크 삽입 함수 + 프롬프트
2. **1~2주 발행 후**: GA4 이벤트 추적 스크립트 추가 (Hugo 템플릿 1개)
3. **그 후**: `funnel_performance` 테이블 생성 및 데이터 수집
4. **데이터 충분 후**: IntentScore 계산 로직
5. **그 다음**: AI 제안·승인 루프

## Constraints
- 기존 파이프라인 발행 중단 없이 점진적 적용
- 새 필드는 YAML config 기반 (하드코딩 set 사용 금지)
- 정보 제목/본문에 억지스러운 링크 삽입 금지 (자연스러운 문맥 내에서만)

## Scope Boundary
- **In scope**: YAML funnel 필드, STAP entity_linker 버그 수정, funnel link insertion 함수, publisher.py hook, prompts _global_rules
- **Out of scope**: Naver SA API 연동, per-post revenue tracking, ROAS 계산, funnel_tracking 활성화, 대시보드 변경

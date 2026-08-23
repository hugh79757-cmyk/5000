# DASHBOARD REVENUE INTEGRATION ARCHITECTURE

> **분류:** Architecture (READ-ONLY 설계)
> **작성:** 2026-08-20
> **목적:** ops_dashboard(5060)에 revenue 데이터를 READ-ONLY로 통합하는 Phase 1 경계 설계
> **전제:** Phase 0 완료 (analytics.db 수집 정상화 + Q1~Q6 품질 게이트 통과)
> **제외:** DB 물리 병합, 기존 5050 제거, 수익 기반 자동 조치, 코드 변경

---

## 1. 현재 대시보드 비교 (READ-ONLY 감사 결과)

### 1-1. 아키텍처 비교

| 항목 | ops_dashboard (5060) | revenue dashboard (5050) |
|------|---------------------|--------------------------|
| **진입점** | `ops_dashboard/app.py` | `data/dashboard/app.py` |
| **프레임워크** | Flask | Flask |
| **포트** | 5060 (hardcoded) | 5050 (env `DASHBOARD_PORT`) |
| **인증** | HTTP Basic Auth (`OPS_USER`/`OPS_PASSWORD`, fail-closed) | **없음** |
| **바인딩** | `0.0.0.0` (외부 접근 가능) | `127.0.0.1` (로컬 전용) |
| **_own DB** | `ops_dashboard/ops.db` (SQLite, WAL) | 없음 (외부 DB 직접 읽기) |
| **테이블 수** | 12+ (blog_lifecycle, known_issues, check_results, standard_rules, daily_summary_events, notification_debounce, maintenance_checklist, pending_fixes, publish_error_events, pipeline_availability, resource_health, retry_blocked) | 0 (read-only) |
| **모니터링 대상** | 블로그 헬스/품질/정비/이슈/발행 에러 | 수익/트래픽/검색/품질 |
| **데이터 소스** | `ops.db` + `config/blogs.d/*.yaml` | `analytics.db` + `content.db` + `quality.db` + cache DBs |
| **런처** | `com.5000.ops-dashboard.plist` (launchd) | 수동 또는 별도 프로세스 |

### 1-2. 라우트/API 비교

#### ops_dashboard (5060) — Human Routes

| Method | Path | 기능 |
|--------|------|------|
| GET | `/` | Fleet Overview (블로그별 헬스 + attention 필터 + 페이지네이션) |
| GET | `/blog/<blog_id>` | 블로그 상세 (체크 결과 + 이슈 + 정비 체크리스트 + unpause 체크리스트) |
| GET | `/issues` | 열린 이슈 목록 |
| GET | `/publish-errors` | 발행 에러 이벤트 (페이지네이션) |
| GET | `/candidate-state` | 후보 가용성 상태 |
| GET | `/standards` | 표준 규칙 + 브랜드별 준수 현황 |

#### ops_dashboard (5060) — JSON API

| Method | Path | 기능 |
|--------|------|------|
| GET | `/api/fleet` | 전체 블로그 목록 |
| GET | `/api/attention` | 주의 필요 항목 |
| GET | `/api/issues` | 열린 이슈 |
| GET | `/api/standards` | 표준 규칙 |
| POST | `/api/run-checks` | 헬스체크 실행 |
| POST | `/api/maintenance/status` | 정비 상태 변경 |
| GET | `/api/publish-errors` | 발행 에러 조회 |
| GET | `/api/candidate-state` | 후보 가용성 |
| POST | `/api/maintenance/checklist` | 정비 체크리스트 실행 |
| GET | `/api/daily-summary` | 일일 알림 요약 |
| GET | `/api/readiness` | 확장 준비도 |
| GET | `/api/registry` | 통합 레지스트리 |
| POST | `/api/sync-yaml` | YAML→DB 강제 동기화 |
| GET | `/api/pending-fixes` | 자동수정 승인 큐 |
| POST | `/api/pending-fixes/<id>/approve` | 승인 실행 |
| POST | `/api/pending-fixes/<id>/reject` | 승인 거부 |

#### revenue dashboard (5050) — JSON API

| Method | Path | 기능 | DB |
|--------|------|------|-----|
| GET | `/api/health` | HTTP 헬스체크 (38개 사이트 병렬) | 없음 (네트워크 요청) |
| GET | `/api/posts/daily` | 일별 발행 현황 | content.db |
| GET | `/api/posts/weekly` | 주별 발행 현황 | content.db |
| GET | `/api/posts/total` | 전체 발행 수 | content.db + cache DBs |
| GET | `/api/revenue/daily` | 일별 AdSense 수익 | analytics.db (`adsense_daily`) |
| GET | `/api/revenue/by-domain` | 도메인별 수익 | analytics.db (`adsense_daily`) |
| GET | `/api/revenue/rpm` | RPM/CTR 추세 | analytics.db (`adsense_daily`) |
| GET | `/api/traffic/daily` | 일별 트래픽 | analytics.db (`ga4_daily`) |
| GET | `/api/traffic/by-blog` | 블로그별 트래픽 | analytics.db (`ga4_daily`) |
| GET | `/api/search/gsc/daily` | GSC 일별 검색 | analytics.db (`gsc_daily_summary`) |
| GET | `/api/search/bing/daily` | Bing 일별 검색 | analytics.db (`bing_daily_summary`) |
| GET | `/api/search/efficiency` | 블로그별 검색 효율 | analytics.db (`blog_efficiency`) |
| GET | `/api/summary` | 대시보드 통합 요약 | content.db + analytics.db |
| GET | `/api/quality/summary` | 콘텐츠 품질 요약 | quality.db |
| GET | `/api/quality/by-blog` | 블로그별 품질 | quality.db |
| GET | `/api/quality/markdown-issues` | 마크다운 이슈 추세 | quality.db |
| GET | `/api/quality/shortcodes` | 쇼트코드 사용 현황 | quality.db |
| GET | `/api/quality/hugo-build` | Hugo 빌드 성공률 | quality.db |

#### revenue dashboard (5050) — Page Routes

| Method | Path | 템플릿 |
|--------|------|--------|
| GET | `/` | `index.html` (메인) |
| GET | `/revenue` | `revenue.html` (도메인별 수익 차트 + RPM/CTR 추세) |
| GET | `/traffic` | `traffic.html` (트래픽 대시보드) |
| GET | `/search` | `search.html` (GSC/Bing 검색 성과) |
| GET | `/health` | `health.html` (사이트 헬스체크) |
| GET | `/quality` | `quality.html` (콘텐츠 품질) |

### 1-3. 블로그 식별자 비교

| 항목 | ops_dashboard (5060) | revenue dashboard (5050) |
|------|---------------------|--------------------------|
| **식별자** | `blog_id` (예: `rap-hugo`) | `blog_id` (동일 형식) + `domain` (별도) |
| **출처** | `config/blogs.d/*.yaml` → `id` 필드 | 하드코딩 `SITES` 리스트 (`api.py:37-83`) |
| **프리픽스** | `5000-{blog_id}` (모니터 ID용) | 없음 (blog_id 직접 사용) |
| **도메인 매핑** | `blog_lifecycle.domain` 컬럼 | `SITES[].url`에서 도메인 추출 |
| **커버리지** | ~50개 블로그 (YAML 기반) | 38개 사이트 (하드코딩) |
| **수익 데이터 연결** | 없음 (health 전용) | `adsense_daily.domain`으로 직접 쿼리 |
| **adsense_daily 키** | 없음 | `domain` 컬럼 (account, domain, date) |

**핵심 갭:** `adsense_daily`는 `(account, domain, date)`를 유니크 키로 사용하지만, ops_dashboard의 `blog_lifecycle`은 `blog_id`를 프라이머리 키로 사용한다. 두 시스템을 연결하려면 **domain ↔ blog_id 매핑**이 필요하다 (Phase 0 Task 4: `blog_identity_map`).

### 1-4. 인증 비교

| 항목 | ops_dashboard (5060) | revenue dashboard (5050) |
|------|---------------------|--------------------------|
| **인증 방식** | HTTP Basic Auth | **없음** |
| **env vars** | `OPS_USER`, `OPS_PASSWORD` (필수) | 없음 |
| **fail-closed** | Yes (env var 없으면 RuntimeError) | N/A |
| **세션/쿠키** | 없음 | 없음 |
| **CSRF 보호** | 없음 | 없음 |
| **네트워크 범위** | `0.0.0.0` (외부 접근 가능) | `127.0.0.1` (로컬 전용) |
| **보안 등급** | 중 (Basic Auth, RBAC 없음) | 낮 (인증 전무, 로컬 전용이지만 0.0.0.0 아님) |

**Phase 1 보안 고려사항:**
- 5060에 revenue 데이터를 노출하면 인증된 사용자만 접근 가능 (기존 동작 유지)
- 5050은 로컬 전용이므로 revenue 데이터가 이미 네트워크 없이 노출됨
- 통합 시 5060의 인증 범위가 revenue 데이터까지 확장됨 → 자연스러운 보안 강화

---

## 2. DB 스키마 비교

### 2-1. ops_dashboard/ops.db 테이블

| 테이블 | 프라이머리 키 | 핵심 컬럼 | 용도 |
|--------|-------------|-----------|------|
| `blog_lifecycle` | `blog_id` | brand, config_status, lifecycle_status, domain, theme, pipeline_path, maintenance_status, days_since_last_publish | 블로그별 라이프사이클 상태 |
| `known_issues` | `issue_id` | blog_ids, category, symptom, gsd_status, resolution_status | 알려진 이슈 |
| `check_results` | `id` (auto) | blog_id, check_name, status, detail, severity, checked_at | 헬스체크 실행 이력 |
| `standard_rules` | `rule_id` | target, severity, description, enabled | 표준 규칙 정의 |
| `daily_summary_events` | `id` (auto) | summary_date, problem_id, blog_id, count | 일일 알림 요약 |
| `notification_debounce` | — | 알림 디바운스 | 알림 중복 방지 |
| `maintenance_checklist` | `id` (auto) | blog_id, check_id, status, detail | 정비 체크리스트 |
| `pending_fixes` | `id` (auto) | blog_id, status, proposed diff | 자동수정 승인 큐 |
| `publish_error_events` | — | blog_id, reason, problem_id | 발행 에러 이벤트 |
| `pipeline_availability` | — | pipeline, state | 파이프라인 가용성 |
| `resource_health` | — | resource_id, state, last_at | 리소스 상태 |

### 2-2. analytics.db 테이블

| 테이블 | 유니크 키 | 핵심 컬럼 | 행 수 | 용도 |
|--------|---------|-----------|-------|------|
| `adsense_daily` | `(account, domain, date)` | page_views, clicks, estimated_earnings, rpm, ctr | 2,521 | AdSense 수익 (domain 단위) |
| `ga4_daily` | `(blog_id, date)` | sessions, total_users, page_views, bounce_rate, engagement_rate, ad_revenue | 251 | GA4 트래픽 (blog_id 단위) |
| `ga4_pages` | `(blog_id, date, page_path)` | sessions, page_views | 1,519 | GA4 페이지별 트래픽 |
| `ga4_traffic_sources` | `(blog_id, date, channel_group)` | sessions, users | 196 | GA4 트래픽 소스 |
| `gsc_daily_summary` | `(blog_id, date)` | total_clicks, total_impressions, avg_ctr, avg_position | 1,210 | GSC 요약 (blog_id 단위) |
| `gsc_keywords` | `(blog_id, date, query)` | clicks, impressions, ctr, position | 400 | GSC 키워드별 |
| `gsc_pages` | `(blog_id, date, page)` | clicks, impressions, ctr, position | **0** | GSC 페이지별 (수집 필요) |
| `bing_daily_summary` | `(blog_id, date)` | clicks, impressions, avg_position | 3,935 | Bing 요약 |
| `bing_keywords` | `(blog_id, date, query)` | clicks, impressions, position | 5,311 | Bing 키워드별 |
| `bing_pages` | `(blog_id, date, page)` | clicks, impressions, position | 3,029 | Bing 페이지별 |
| `blog_efficiency` | `(blog_id, date)` | efficiency_score, gsc_clicks, gsc_impressions, grade | 671 | 블로그별 검색 효율 |
| `sync_log` | — | — | 0 | 동기화 로그 |
| `indexing_log` | — | — | 0 | 색인 로그 |

### 2-3. 연결 키 불일치 분석

| 테이블 | 식별 키 | → ops_dashboard 연결 |
|--------|---------|---------------------|
| `adsense_daily` | `domain` | **불가** — `blog_lifecycle.domain`과 매핑 필요 |
| `ga4_daily` | `blog_id` | **가능** — 직접 조인 |
| `gsc_daily_summary` | `blog_id` | **가능** — 직접 조인 |
| `gsc_keywords` | `blog_id` | **가능** — 직접 조인 |
| `bing_daily_summary` | `blog_id` | **가능** — 직접 조인 |
| `blog_efficiency` | `blog_id` | **가능** — 직접 조인 |

**핵심 문제:** `adsense_daily`만 `domain` 키를 사용. 나머지는 모두 `blog_id`. ops_dashboard의 `blog_lifecycle`에 `domain` 컬럼이 있으므로, `blog_lifecycle.domain = adsense_daily.domain`으로 조인하면 되지만, adsense_daily의 domain이 blog_lifecycle의 domain과 정확히 일치하는지 검증 필요.

---

## 3. Phase 1 통합 경계 설계

### 3-1. 설계 원칙

1. **READ-ONLY:** analytics.db에 쓰기 없음. ops_dashboard가 analytics.db를 읽기만 함
2. **DB 물리 병합 금지:** analytics.db와 ops.db는 독립 유지
3. **기존 5050 유지:** data/dashboard는 그대로 두되, Phase 1에서 수익 데이터는 5060으로 집중
4. **수익 기반 자동 조치 금지:** 수익 데이터를 읽기만 하고, 발행 우선순위/자동 복구에는 반영하지 않음
5. **blog_identity_map 기반 연결:** domain ↔ blog_id 매핑은 `shared/blog_identity_map.py`를 통해 단일 소스로 관리

### 3-2. 통합 데이터 흐름

```
┌─────────────────────────────────────────────────────────┐
│                    analytics.db (read-only)              │
│  adsense_daily (domain) ──┐                             │
│  ga4_daily (blog_id) ─────┤                             │
│  gsc_daily_summary (bid) ─┤                             │
│  gsc_keywords (blog_id) ──┤                             │
│  bing_daily_summary (bid) ─┤                             │
│  blog_efficiency (blog_id) ┤                             │
└────────────────────────────┼────────────────────────────┘
                             │
                    ┌────────▼────────┐
                    │ blog_identity_  │
                    │ map.py          │
                    │ (domain↔blog_id)│
                    └────────┬────────┘
                             │
              ┌──────────────▼──────────────┐
              │  ops_dashboard (5060)        │
              │  /api/revenue/* (신규)        │
              │  /blog/<id> (확장)           │
              │  analytics_readonly.py (신규)│
              └─────────────────────────────┘
```

### 3-3. 신규 모듈: `ops_dashboard/analytics_readonly.py`

analytics.db를 읽기 전용으로 접근하는 헬퍼 모듈. ops_dashboard/app.py에서 lazy import.

```python
# ops_dashboard/analytics_readonly.py (신규 — Phase 1)
"""analytics.db READ-ONLY 접근 레이어.

원칙:
- analytics.db에 쓰기 금지 (connect 시 check_same_thread=True, immutable=False)
- blog_identity_map을 통해 domain→blog_id 변환
- 모든 쿼리는 날짜 필수 (무한 범위 쿼리 금지)
- max_rows 파라미터로 결과 제한 (기본 1000)
"""
```

**제공 함수 (설계):**

| 함수 | 입력 | 출력 | 설명 |
|------|------|------|------|
| `get_revenue_summary(days=30)` | 기간 | `{total_revenue, total_pv, total_clicks, avg_rpm, avg_ctr, daily_trend[]}` | 전체 수익 요약 |
| `get_revenue_by_blog(days=30)` | 기간 | `[{blog_id, revenue, pv, rpm, ctr, estimated_rpc}]` | 블로그별 수익 (blog_identity_map 경유) |
| `get_data_freshness()` | 없음 | `{adsense: {latest, gap_days}, ga4: {...}, gsc: {...}, bing: {...}}` | 각 데이터 소스 최신성 |
| `get_blog_analytics(blog_id, days=30)` | blog_id + 기간 | `{revenue, traffic, search, efficiency}` | 블로그별 종합 분석 |
| `get_collection_status()` | 없음 | `[{source, status, last_date, gap_days, error_count}]` | 수집 상태 모니터링 |
| `get_top_keywords(blog_id, days=28, limit=20)` | blog_id + 기간 | `[{query, clicks, impressions, ctr, position, est_revenue}]` | 상위 키워드 |

### 3-4. 신규 API 엔드포인트 (ops_dashboard/app.py에 추가)

**모든 엔드포인트는 `@require_auth` 적용 (기존 인증 유지)**

| Method | Path | 기능 | analytics_readonly 함수 |
|--------|------|------|------------------------|
| GET | `/api/revenue/summary` | 수익 요약 카드 | `get_revenue_summary()` |
| GET | `/api/revenue/by-blog` | 블로그별 수익 테이블 | `get_revenue_by_blog()` |
| GET | `/api/revenue/freshness` | 데이터 최신성 상태 | `get_data_freshness()` |
| GET | `/api/revenue/collection` | 수집 장애 상태 | `get_collection_status()` |
| GET | `/api/blog/<blog_id>/analytics` | 블로그별 종합 분석 | `get_blog_analytics()` |
| GET | `/api/blog/<blog_id>/keywords` | 블로그별 상위 키워드 | `get_top_keywords()` |

**쿼리 파라미터 공통:**
- `days` (기본 30, 최대 365) — 기간 필터
- `limit` (기본 20, 최대 100) — 결과 제한

### 3-5. 기존 라우트 확장 (blog detail 페이지)

`/blog/<blog_id>` 페이지에 **"Revenue" 섹션 추가** (READ-ONLY):

```
/blog/rap-hugo
├── 기존: Fleet Status, Checks, Issues, Maintenance, Unpause Checklist
├── 신규: Revenue Summary (최근 30일 수익/PV/RPM/CTR)
├── 신규: Traffic Summary (GA4 세션/사용자)
├── 신규: Search Summary (GSC 클릭/노출/CTR/순위)
└── 신규: Data Freshness (각 소스 최신성)
```

### 3-6. 신규 HTML 템플릿 조각

`ops_dashboard/templates/blog.html`에 revenue 섹션 추가:

```html
<!-- Revenue Summary Card (신규 — Phase 1) -->
<div class="card mb-3">
  <div class="card-header">Revenue (최근 {{ days }}일)</div>
  <div class="card-body">
    <div class="row">
      <div class="col-md-3">
        <h6>수익</h6>
        <p>${{ revenue.total_revenue }}</p>
      </div>
      <div class="col-md-3">
        <h6>PV</h6>
        <p>{{ revenue.total_pv }}</p>
      </div>
      <div class="col-md-3">
        <h6>RPM</h6>
        <p>${{ revenue.avg_rpm }}</p>
      </div>
      <div class="col-md-3">
        <h6>CTR</h6>
        <p>{{ revenue.avg_ctr }}%</p>
      </div>
    </div>
    <small class="text-muted">
      데이터 최신: {{ freshness.adsense.latest }} 
      (gap: {{ freshness.adsense.gap_days }}일)
    </small>
  </div>
</div>
```

---

## 4. blog_identity_map 설계 (Phase 0 Task 4 확장)

### 4-1. 현재 매핑 메커니즘

| 위치 | 매핑 방식 | 커버리지 | 문제 |
|------|----------|---------|------|
| `analytics_collector.py:184-228` | `URL_TO_BLOG_ID` dict (40개) | 하드코딩, domain→blog_id | 관리 어려움, 미매핑 domain 존재 |
| `ops_dashboard/db.py` | `blog_lifecycle.domain` | YAML 기반 (~50개) | adsense_daily의 domain과 정확히 일치하는지 미검증 |
| `data/dashboard/routes/api.py:37-83` | `SITES` 리스트 (38개) | 하드코딩 | 하드코딩, 동기화 안 됨 |
| `config/blogs.d/*.yaml` | `id` + `domain` 필드 | **진실 소스** | 수동 관리 |

### 4-2. blog_identity_map 통합 설계

```
config/blogs.d/*.yaml (진실 소스)
        │
        ▼
shared/blog_identity_map.py (Phase 0 Task 4)
        │
        ├── domain → blog_id (adsense_daily 연결용)
        ├── blog_id → domain (ops_dashboard 표시용)
        ├── blog_id → group (파이프라인 분류)
        └── unmapped_domains (인벤토리 밖 도메인 목록)
```

**ops_dashboard에서의 사용:**
```python
from shared.blog_identity_map import resolve_blog_id, get_blog_domain

# adsense_daily.domain → blog_id 변환
blog_id = resolve_blog_id("informationhot.kr")  # → "rap-hugo" (예시)

# blog_id → domain 변환 (ops_dashboard 표시용)
domain = get_blog_domain("rap-hugo")  # → "apt.informationhot.kr"
```

### 4-3. 매핑 검증 규칙

1. `config/blogs.d/*.yaml`의 모든 `id`+`domain`이 매핑에 포함
2. `adsense_daily`의 모든 `domain`이 매핑에 존재하거나 `unmapped`로 분류
3. 1:1 매핑 보장 (동일 domain이 여러 blog_id에 매핑되지 않음)
4. 매핑 불일치 시 경고 로그 (ops_dashboard 표시)

---

## 5. 데이터 품질/신뢰성 가드레일

### 5-1. analytics.db 읽기 시 주의사항

| 테이블 | 주의사항 | 대응 |
|--------|---------|------|
| `adsense_daily` | 3주 공백 (2026-07-28~) — Phase 0에서 복구 | `get_data_freshness()`가 gap_days 반환 |
| `adsense_daily` | account 1,2만 있음 (account 3 누락) — Phase 0에서 추가 | `get_collection_status()`가 account별 상태 반환 |
| `gsc_pages` | 0행 (A1 연결 불가) — Phase 0에서 수집 | `get_data_freshness()`가 0행 경고 |
| `gsc_keywords` | 14일 데이터만 (얇음) | 28일 trailing window (G3) 준수 |
| `blog_efficiency` | grade(F) 블로그 다수 | 등급 표시 + 수익 데이터와 교차 분석 |

### 5-2. 데이터 표시 규칙 (rev.2 스펙 준수)

| 규칙 | 내용 | 구현 위치 |
|------|------|----------|
| 추정 라벨 | `estimated_keyword_revenue` = "추정 수익"으로 표시 | `analytics_readonly.py` |
| true EPC 미표시 | attribution 데이터 없으므로 true EPC 필드 미노출 | API 응답에 미포함 |
| G1 | 클릭 < 3 키워드 기본 숨김 | `get_top_keywords()` WHERE clicks >= 3 |
| G3 | 28일 trailing window | 모든 집계 기본값 28일 |
| G4 | 데이터 지연 마커 | `get_data_freshness()`가 gap_days > 3이면 "지연" 플래그 |
| 이중 곱 금지 | `expected_incremental_revenue = 증분클릭 × estimated_revenue_per_organic_click` | 표시 로직에서 검증 |

---

## 6. 보안 고려사항

### 6-1. 현재 보안 상태

| 항목 | ops_dashboard (5060) | revenue dashboard (5050) |
|------|---------------------|--------------------------|
| 인증 | Basic Auth (fail-closed) | **없음** |
| 바인딩 | 0.0.0.0 | 127.0.0.1 |
| RBAC | 없음 | N/A |
| HTTPS | 없음 | 없음 |
| CSRF | 없음 | 없음 |

### 6-2. Phase 1 보안 영향

- **양호:** 5060에 revenue 데이터 추가해도 기존 Basic Auth가 보호
- **양호:** analytics.db는 READ-ONLY로 접근 (쓰기 금지)
- **주의:** revenue 데이터는 금융 정보이므로 추가 접근 통제 검토 필요
- **미완:** RBAC 미적용 — 모든 인증 사용자가 모든 revenue 데이터 접근 가능

### 6-3. 권장 보안 강화 (Phase 1 이후)

1. **RBAC:** revenue 데이터에 role-based 접근 제한 (admin만 전체 수익, viewer는 블로그별 수익만)
2. **감사 로그:** revenue API 접근 기록 (`/api/revenue/*` 요청 로그)
3. **데이터 마스킹:** 민감 수익 금액 마스킹 옵션 (summary만 공개, 상세는 인증 강화)

---

## 7. 기존 5050과의 관계

### 7-1. 공존 전략

| 항목 | Phase 1 이후 |
|------|-------------|
| 5050 (revenue dashboard) | **유지** — 기존대로 운영 |
| 5060 (ops_dashboard) | **확장** — revenue 섹션 추가 |
| revenue 데이터 소스 | **단일:** `analytics.db` (양쪽 동일 DB 읽기) |
| 수익 데이터 표시 | **5060에 집중** — fleet health + revenue 통합 |
| 5050 역할 | 로컬 개발/디버깅용 + 기존 기능 유지 |

### 7-2. 데이터 일관성

- 양쪽 대시보드가 같은 `analytics.db`를 읽으므로 데이터 일관성 보장
- `blog_identity_map.py`를 통해 도메인→blog_id 변환 로직 공유
- 5060이 `blog_lifecycle.domain`과 조인하는 반면, 5050은 `adsense_daily.domain`을 직접 사용 — 매핑 정합성 검증 필요

### 7-3. 향후 통합 (Phase 2+)

- Phase 2에서 5050의 revenue API를 5060으로 마이그레이션 검토
- 5050은 legacy로 전환 또는 통합
- **단, 본 문서의 범위는 Phase 1 READ-ONLY 설계에 한정**

---

## 8. 구현 순서 (Phase 1)

### Step 1: blog_identity_map 검증 (Phase 0 Task 4 완료 후)

- `config/blogs.d/*.yaml` 기반 매핑과 `adsense_daily.domain` 대조
- 미매핑 도메인 목록 출력
- 매핑 커버리지 ≥ 95% 확인

### Step 2: analytics_readonly.py 구현

- analytics.db READ-ONLY 연결 (check_same_thread=True)
- 6개 핵심 함수 구현
- 단위 테스트 (analytics.db 스냅샷 또는 테스트 DB)

### Step 3: API 엔드포인트 추가

- `ops_dashboard/app.py`에 6개 revenue API 라우트 추가
- `@require_auth` 데코레이터 적용
- 기존 에러 핸들러와 일관된 JSON 응답 형식

### Step 4: blog detail 페이지 확장

- `ops_dashboard/templates/blog.html`에 revenue 섹션 추가
- Jinja2 템플릿 렌더링 (analytics_readonly 함수 호출)
- 반응형 CSS (기존 다크 테마 호환)

### Step 5: 검증

- 모든 revenue API 엔드포인트가 200 반환 확인
- blog detail 페이지에 revenue 데이터 표시 확인
- 데이터 최신성 표시 확인 (gap_days 경고)
- 인증 없이 접근 시 401 반환 확인

---

## 9. 리스크 레지스트리

| # | 리스크 | 영향 | 완화 |
|---|--------|------|------|
| R1 | `adsense_daily.domain` ↔ `blog_lifecycle.domain` 불일치 | 수익 데이터 연결 실패 | Phase 0 Task 4에서 매핑 검증 |
| R2 | analytics.db 3주 공백 (Phase 0 미완료 시) | 빈 revenue 데이터 표시 | `get_data_freshness()`로 gap 표시 |
| R3 | `gsc_pages` 0행 (Phase 0 Task 5 미완료 시) | A1 연결 불가, 키워드→페이지 매핑 없음 | 키워드 섹션에서 "페이지 데이터 없음" 표시 |
| R4 | 5060 인증 우회 (0.0.0.0 바인딩) | 외부에서 revenue 데이터 접근 가능 | 기존 인증 유지 + 네트워크 접근 제어 |
| R5 | `blog_identity_map` 미매핑 도메인 > 5% | 수익 블로그 연결 불가 | unmapped 도메인 별도 표시 + 수동 매핑 |
| R6 | analytics.db 읽기 시 WAL 충돌 | 읽기 실패 | PRAGMA journal_mode=WAL + read_only 연결 |

---

## 10. 제외 사항 (명시적)

- **DB 물리 병합:** analytics.db와 ops.db를 합치지 않음
- **기존 5050 제거:** data/dashboard는 그대로 유지
- **수익 기반 자동 조치:** revenue 데이터로 발행 우선순위/자동 복구를 변경하지 않음
- **코드 변경:** 본 문서는 READ-ONLY 설계. 실제 구현은 Phase 1에서 수행
- **제휴 데이터:** 쿠팡/CJ 등 제휴 수익은 Phase 2+ 범위
- **A/B 실험:** 수익 기반 실험 인프라는 Phase 4 범위
- **RBAC:** Phase 1에서 인증 강화하지 않음 (기존 Basic Auth 유지)

---

## 참조 문서

- `docs/superpowers/specs/2026-08-20-keyword-revenue-dashboard-design.md` (rev.2 스펙)
- `docs/superpowers/plans/PHASE0_REVENUE_IMPLEMENTATION_PLAN.md` (Phase 0 구현 계획)
- `REVENUE_MATURITY_ROADMAP.md` (성숙도 로드맵)
- `REVENUE_CAPABILITY_AUDIT.md` (READ-ONLY 감사)
- `ops_dashboard/app.py` (5060 메인)
- `data/dashboard/app.py` (5050 메인)
- `shared/analytics_collector.py` (수집 파이프라인)

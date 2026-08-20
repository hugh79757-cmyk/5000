# REVENUE CAPABILITY AUDIT — 5000 프로젝트

> 감사 일시: 2026-08-20
> 감사 방식: READ-ONLY (코드·DB·설정 열람만, API 호출/변경/배포 없음)
> 감사 범위: ① AdSense 연동 ② 쿠팡/제휴 ③ 공통 revenue fact 모델 ④ 수익 데이터 의사결정 사용 ⑤ A/B 실험 인프라 ⑥ L0~L5 성숙도 평가 ⑦ 우선순위

---

## ① AdSense 연동 — [검증됨] 수집·표시 구현됨, granularity·최신성 결함

### 현황
| 항목 | 상태 | 근거 |
|---|---|---|
| API | AdSense Management API v2 (`adsense.v2`), OAuth 2.0 InstalledAppFlow, scope `adsense.readonly` | `shared/analytics_collector.py:56,285-287,309,647` |
| 클라이언트 시크릿 | `/Users/twinssn/Projects/blogdex/cli/client_secret_hugh7973.json`, `ADSENSE_CREDENTIALS_{1,2}twinssn.json` — `.env`/`api_keys.yaml`에는 AdSense 키 없음 | `analytics_collector.py:56,285` |
| 수집 주기 | launchd `com.5000.analytics.plist` 6시간(21600s) → `scripts/collect_analytics.sh` → `collect_adsense(days=3)` | plist:11-12, `collect_analytics.sh:30-37` |
| DB 테이블 | `data/analytics.db` `adsense_daily` (account, domain, date, page_views, clicks, estimated_earnings, rpm, ctr, collected_at, UNIQUE(account,domain,date)) | `.schema adsense_daily` |
| 보관 기간 | 보존/삭제 정책 없음 — 무제한 적재 (INSERT OR REPLACE로 일일 갱신) | grep 삭제코드 0건, `analytics_collector.py:691` |
| Granularity | **domain 단위만** — blog_id 컬럼 없음, post/URL 단위 없음. 도메인→blog_id 매핑 자동화 없음 | `analytics_collector.py:667` `dimensions=["DATE","DOMAIN_NAME"]` |
| 대시보드 | **ops_dashboard(5060)에는 수익 기능 없음.** 별도 `data/dashboard`(5050)에 `/api/revenue/daily|by-domain|rpm` + `/revenue` 화면 | `data/dashboard/routes/api.py:242-304`, `pages.py:13-15` |
| 최신성 | 수집된 최신 데이터 **2026-07-28/29 (약 3주 전)**. `collected_at` 컬럼은 있으나 대시보드 최신성 표시 없음 | `adsense_daily` 최신 행, `logs/analytics_collect.log` |
| 계정 커버리지 | 계정 1(twinssn), 2(informationhot)만 순회 — **계정 3(aikorea24) 수집 누락** | `analytics_collector.py:644` `for account_num in [1, 2]` |

### 판정
- 수집 파이프라인(launchd→collector→DB): **구현됨**
- 수익 대시보드: **구현됨** (단, ops_dashboard와 분리된 별도 앱)
- blog/post 단위 granularity: **미구현** (domain 단위가 한계)
- 보존 정책: **없음** (무한 적재)

---

## ② 쿠팡/제휴 기능 — 링크 생성은 구현, 성과 수집은 전무

### (A) 상품 검색/링크 생성: [검증됨] 구현됨
| 항목 | 상태 | 근거 |
|---|---|---|
| 방식 | REST 직접 호출 (공식 SDK 미설치) | `pip list | grep coupang` 0건 |
| 상품 검색 | `https://api-gateway.coupang.com/v2/providers/affiliate_open_api/apis/openapi/products/search` | `shared/coupang_travel.py:154-166` |
| 링크 생성 | `.../openapi/v1/deeplink` → `shortenUrl` (`/a/` 링크) | `coupang_travel.py:171-194` |
| 인증 | env `COUPANG_ACCESS_KEY/SECRET_KEY/PARTNER_ID` + HmacSHA256 자체 서명 | `coupang_travel.py:130-152` |
| 삽입 | `publisher.py:139-168` → `content_enhancer.py:25-40` → `inject_coupang()` → body_md에 MD 링크 주입 | `publisher.py`, `content_enhancer.py` |
| 변형 | travel/car/senior 3개 모듈 (여행·자동차·시니어 도메인별) | `shared/coupang_{travel,car,senior}.py` |
| 기타 제휴 | Trip.com/Skyscanner/Booking/Viator/Klook/Rentalcars 링크 생성기 (`shared/etap_affiliate.py`), ETAP H2 정규식 삽입 (`etap_affiliate_injector.py`) | `etap_affiliate.py:1-270` |

### (B) 성과 데이터 수집: [검증불가→사실상 부재] 구현 안 됨
| 항목 | 상태 | 근거 |
|---|---|---|
| 클릭/주문/취소/수수료 수집 | **없음** — reporting API 호출 코드 0건 | coupang_*.py, pipelines, ops_dashboard, scripts 전수 grep |
| 수집 주기/스케줄 | 없음 (cron/launchd/워크플로 미연동) | grep |
| subId/채널 ID | **미사용** — deeplink body가 `{"coupangUrls":[...]}`만, subId 필드 없음 | `coupang_travel.py:180-184` |
| 게시글 attribution | **없음** — 생성된 shortenUrl을 기록/반환하지 않음, `articles` 테이블에 affiliate 컬럼 없음 | `publisher.py:160-161`, `content_store.py:23-44` |
| DB 테이블 | 제휴 전용 테이블 없음. `funnel_tracking`(affiliate_clicks/conversions/revenue)은 스키마만 존재하고 **호출부 없음 → 빈 테이블** | `quality_recorder.py:70-89` |
| 대시보드 | 제휴 수익/클릭 API·화면 없음 (revenue API는 전부 AdSense 집계) | `data/dashboard/routes/api.py:239-357` |

### 특이사항
- **rate limit 제재 이력**: 모든 coupang 모듈 상단에 "2026-07-16 분당 50회 제재" 주석 — reporting 추가 시 제재 재발 위험.
- `scripts/fix_cta_links.py`는 `link.coupang.com` CTA만 대상, `fix_coupang_thumbs.py`는 쿠팡 URL 썸네일 교체 전용.

---

## ③ 공통 revenue fact 모델 — [검증됨] NOT_IMPLEMENTED (DB 3개 분리·조인 키 부재)

### 실제 DB 구조 (sqlite3 .tables 직접 확인)
| DB 파일 | 테이블 | 비고 |
|---|---|---|
| `ops_dashboard/ops.db` (3.6MB) | blog_lifecycle, check_results, known_issues, publish_error_events, pending_fixes, standard_rules, daily_summary_events, maintenance_checklist, pipeline_availability, resource_health, telegram_delivery_audit 등 15개 | **수익 테이블 없음.** blog_id 단위 운영 상태 |
| `data/analytics.db` (3.6MB) | adsense_daily, ga4_daily, ga4_pages, ga4_traffic_sources, gsc_daily_summary, gsc_keywords, gsc_pages, bing_*, blog_efficiency, indexing_log, sync_log | domain 단위(adsense) + blog_id 단위(blog_efficiency, GSC만) |
| `content.db` / `senior.db` | 빈 파일 (스키마 미생성 상태) | 콘텐츠 저장소로 추정되나 미사용 |
| `data/dashboard.db` | 빈 파일 (0바이트) | data/dashboard는 analytics.db 직접 조회 |

### 계층 연결 판정
- **post(게시글) 단위 수익 데이터: 없음** — URL/page dimension 미수집 (adsense는 DOMAIN_NAME까지만)
- **blog 단위**: `blog_efficiency`(blog_id, gsc_clicks, gsc_impressions, efficiency_score)만 존재 — **AdSense 수익 없음, 제휴 없음**
- **brand 단위**: blog_lifecycle에 brand 컬럼 있으나 revenue와 조인 경로 없음
- **도메인→blog_id 매핑**: 자동화 없음 (수동 대시보드 조회 시 domain GROUP BY만)

### 판정
**NOT_IMPLEMENTED.** 수익 지표를 post→blog→brand로 계층 조인할 수 있는 단일 revenue fact 모델(스키마/테이블/클래스)이 존재하지 않음. DB 3개가 분리되어 있고, adsense는 domain 단위, GSC는 blog 단위로 서로 다른 키를 사용.

---

## ④ 수익 데이터 의사결정 사용 — [검증됨] 전 지점 미사용 (수집만 하고 미활용)

| 의사결정 지점 | 수익 데이터 사용 | 실제 사용 입력 | 근거 |
|---|---|---|---|
| scheduler (발행 선정) | **NO** | daily_quota(정적 YAML), publish_ledger 건수, candidate_availability | `scheduler.py:347-431`, 수익 키워드 0건 |
| topic selector / keyword scoring | **NO** | priority 정적값, use_count, 키워드 매칭 점수 | `pipelines/car/topic_manager.py:23-39`, `shared/relevance_scorer.py:23-56`, `cuap_title_llm.py:20-39` |
| 콘텐츠 생성 (writer) | **NO** | 프롬프트 YAML, editorial 규칙. (`stock/writer.py`의 `revenue_t`는 기업 재무 데이터 — AdSense/제휴 아님) | `pipelines/stock/writer.py:55-78`, `prompts/travel.yaml:286` |
| CTA 삽입 | **NO** | H2 키워드 정적 매핑, 슬롯 ID 정적 주입 | `etap_affiliate_injector.py:89-95`, `hugo_writer.py:1262-1264` |
| 내부 링크 | **NO** | CROSS_GRAPH 정적, entity priority 정적값(기본 50) | `ops_dashboard/checks/crosslink.py:78-86`, `cuap_entity_linker.py:265-268` |
| 품질 복구 (dispatcher/autofix) | **NO** | ProblemSpec.severity 정적값, rule_id→FIXERS 매핑 | `dispatcher.py:1479-1525,943`, `problem_registry.py:21-28` |
| 대시보드 문제 우선순위 | **NO** | UnifiedEntry에 spec.severity 그대로 복사, 동적 가중 없음 | `ops_dashboard/registry/errors.py:25-35` |

### 수집 데이터 흐름 (호출 그래프)
```
analytics_collector (__main__ CLI 수동 실행 + launchd 6시간)
    → analytics.db INSERT (adsense_daily, ga4_*, gsc_*, bing_*)
        → data/dashboard/routes/api.py (대시보드 조회 read-only)
scheduler / dispatcher / pipelines / ops_dashboard → analytics_collector import ✗ (전무)
```

**결론: AdSense/GSC 수익·성과 데이터가 수집되어 대시보드에 표시될 뿐, 어떤 의사결정에도 입력되지 않음.** `quality_recorder.get_blog_quality_scores()`도 정의만 있고 호출부 없음.

---

## ⑤ A/B 테스트·실험 인프라 — [검증됨] NOT_IMPLEMENTED

| 기능 | 존재 | 근거 |
|---|---|---|
| 실험 프레임워크 | 없음 | `ab_test|experiment|split_test` production grep 0건 (audit-archive의 sitemap experiment 주석 제외) |
| 처리군/대조군 | 없음 | `treatment|control_group` 0건 (`variant`는 키워드 변형·테마 variant 맥락뿐) |
| 성과 기준선 | 없음 | `baseline`은 로그 유형·canary ID 맥락뿐, 실험용 기준선 테이블 없음 |
| 통계적 판정 | 없음 | `scipy|statsmodels|p_value|ttest|chisquare|bayesian` production 0건 |
| 조기 중단 guardrail | 없음 | `early stop|guardrail|kill switch` production 0건 |
| 롤백 | 없음 | `rollback|revert|restore`는 DB 트랜잭션·.bak 복구뿐, 게시글 배포 롤백 없음 |

---

## ⑥ L0~L5 성숙도 평가

| 영역 | L0~L5 | 상태 | 핵심 근거 |
|---|---|---|---|
| 발행 자동화 | **L4** | IMPLEMENTED | scheduler+dispatcher+14개 파이프라인, launchd 자동 실행, 배포 후 run-checks 검증. 수익 기반 발행 우선순위만 없음 |
| 운영 감시 | **L3** | IMPLEMENTED | 14개 checks 모듈, R01~R12/C01~C09/P01~P34, attention/fail_checks 집계, telegram_delivery_audit 알림 |
| 진단/복구 | **L2** | PARTIAL | pending-fix + autofix + 플레이북 구조는 있으나: R2-01 target_files/verify 빈 채 중단, ERROR_PLAYBOOKS R규칙 레시피 부재, 규칙 수정 시 앱 재시작 필요 |
| AdSense 데이터 | **L2** | PARTIAL | 수집(6h) + 별도 대시보드 표시 구현. domain 단위 한계, blog_id 미연결, 계정3 누락, 최신성 3주 공백 |
| 제휴 데이터 | **L0** | NOT_IMPLEMENTED | 링크 생성만 있고 클릭·주문·수수료 수집 전무, subId 없음 |
| Attribution | **L0** | NOT_IMPLEMENTED | subId 미사용, 게시글↔링크 매핑·기록 없음 |
| 실험 (A/B) | **L0** | NOT_IMPLEMENTED | 프레임워크/처리군/기준선/통계/guardrail/롤백 전무 |
| 수익 최적화 | **L0** | NOT_IMPLEMENTED | 수익 데이터가 7개 의사결정 지점 어디에도 입력 안 됨 |
| 거버넌스 | **L2** | PARTIAL | automation_level(full_auto/human_approval/human_only) + 승인 게이트 정의, AGENT_ENTRYPOINT 절차 존재. 단 pending-fix 중단·레시피 부재로 실제 순환 미달 |

---

## ⑦ 우선순위 로드맵 (예상 수익 영향 / 구현 난이도 / 위험 기준)

> 구현 순서 권장: A → B → C → D → E → F

### 중복 개발 금지 항목 (이미 존재 → 재개발하지 말 것)
1. **AdSense 수집 파이프라인** — `analytics_collector.py` + launchd plist + `adsense_daily` 테이블 (재개발 금지, 복구·보강만)
2. **수익 대시보드 화면/API** — `data/dashboard` `/revenue*` (재개발 금지, ops_dashboard 병합/이전 여부만 결정)
3. **쿠팡 상품 검색/링크 생성** — `coupang_{travel,car,senior}.py` (재개발 금지, subId 추가만)
4. **funnel_tracking 스키마** — `quality_recorder.py:70-89` (테이블 재설계 금지, 호출부 활성화만)
5. **GSC blog 단위 성과** — `blog_efficiency` (blog_id 단위 기반 활용)
6. **발행 자동화·운영 감시·거버넌스 구조** — scheduler/dispatcher/플레이북 (이미 L2~L4)

### 우선순위 표
| 순위 | 항목 | 예상 수익 영향 | 구현 난이도 | 위험 | 판정 |
|---|---|---|---|---|---|
| **A** | AdSense 수집 복구 + 도메인→blog_id 매핑 (계정3 포함) | **높음** — 3주째 수익 추적 공백, 수익 최적화의 전제 | 낮음 (매핑 테이블 + collect 재시작) | 낮음 | 현재 최신 데이터 07-28, 6h launchd가 돌았는지 로그 확인부터 |
| **B** | 제휴 성과 수집: subId 추가 + 쿠팡 reporting API | **높음** — 제휴 수익이 전혀 측정되지 않음 (측정만으로도 최적화 가능) | 중 (reporting API + subId 매핑) | **중** — rate limit 50/min 제재 이력, 분당 호출 제한 설계 필수 | 링크 생성은 이미 구현됨, 수집만 추가 |
| **C** | 수익 데이터 의사결정 연결: scheduler 발행 우선순위 + 문제 severity 가중 | **높음** — 저성과 블로그 감소/고성과 확대 | 중 | 낮음 | 기존 daily_quota/severity 구조에 수익 가중치 추가 |
| **D** | 공통 revenue fact 모델: adsense_daily에 blog_id 컬럼 + post 단위 수집 확장 | **중** — post 단위 최적화의 전제 | 중 | 낮음 | domain→blog_id 매핑 테이블 + UNIQUE 변경 |
| **E** | 거버넌스 보강: ERROR_PLAYBOOKS 레시피, pending-fix target_files/verify, 규칙 핫 리로드 | 간접 (자동 복구 순환 완성) | 낮음 | 낮음 | L2→L3 진입의 선결 조건 |
| **F** | A/B 실험 인프라 (제목/CTA/광고 배치) | 장기적 (검증된 개선만 적용) | 높음 (실험 프레임워크 전면 신규) | 중 (오발행·혼선 위험) | L4 달성 후 진입 권장 |

### 핵심 공백 요약
1. 수익 데이터가 의사결정과 완전 분리 (④ 전 지점 NO)
2. 제휴 성과 측정 전무 + subId 미사용 (②-B)
3. post 단위 수익 데이터 부재, DB 3개 분리 (③)
4. 실험 인프라 전무 (⑤)
5. AdSense 수집 3주 공백 + 계정3 누락 + 대시보드 분리 (①)
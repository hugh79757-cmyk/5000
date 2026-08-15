
## 기술문서 v2.6 추가분 (2026-06-25)

### 변경 이력 추가

| 날짜 | 버전 | 주요 변경 |
|---|---|---|
| 2026-06-25 | v2.6 | travel 블로그 발행 쿼터 5→2회로 감소, 축제 fallback 시스템 비활성화 |
| 2026-06-12 | v2.5 | humanize 단계 추가(5000+SAP), TAP sqlalchemy 설치, SEAP sync 가드, GAP 스케줄 비활성화, similar_title 반복 오류 확인 |

---

### 2026-06-25 주요 작업

#### 1. Travel 블로그 발행 쿼터 2회로 변경

**배경**: travel 블로그 4개가 하루 25-30건을 발행하면서 중복 체크에 걸리는 no_result가 빈번 발생. 발행 쿼터를 줄여 불필요한 시도를 감소시키고 ledger를 깔끔하게 유지.

**변경 파일**: `config/blogs.d/tap.yaml`

| 블로그 | 변경 전 | 변경 후 |
|---|---|---|
| travel-hugo (캠핑) | daily_quota: 5 | daily_quota: 2 |
| travel1-hugo (축제) | daily_quota: 5 | daily_quota: 2 |
| travel2-hugo (문화유산) | daily_quota: 5 | daily_quota: 2 |
| travel4-hugo (여행코스) | daily_quota: 5 | daily_quota: 2 |

**효과**: 하루 총 발행량 약 25건 → 8-10건으로 감소, 불필요한 시도 60% 감소

---

#### 2. 축제 fallback 시스템 비활성화

**배경**: `fetch_festival()`의 DEPLETION FALLBACK 로직이 이미 발행된 축제를 다시 선택하여 재발행하는 문제 발생. 새 축제가 없으면 발행하지 않도록 변경.

**변경 파일**: `pipelines/travel/fetcher.py`

**변경 내용**:
- `_is_fallback` 변수 제거 (라인 294)
- DEPLETION FALLBACK 로직 제거 (라인 311-367)
- `content_ids` 항상 설정 (fallback 우회 코드 제거)

**변경 전**:
```python
_is_fallback = True
logger.warning("festival 스마트발행: 발행 대상 0건 — published_ids fallback 시도")
# [DEPLETION FALLBACK] 모든 축제가 이미 발행됨 → published_ids 무시하고 재시도
urgent = []
high = []
# ... (이미 발행된 축제 재선택 로직)
```

**변경 후**:
```python
# [NO FALLBACK] 새 축제가 없으면 발행하지 않음 (이미 발행된 것 재발행 방지)
logger.warning("festival: 발행 대상 0건 — 새 축제 없음")
_tg_send("⚠️ travel1-hugo festival 새 축제 없음 — 발행 건너뜀")
conn.close()
return None
```

**효과**: 이미 발행된 축제 재발행 방지, refresh_festival 트리거 후 새 데이터만 발행

---

#### 3. 시郡구 7일 중복 체크 — 유지

**변경 없음** — 현재 7일이 적절함

---

### 수정 파일 목록 (2026-06-25)

| 파일 | 수정 내용 |
|---|---|
| `config/blogs.d/tap.yaml` | travel 블로그 4개 daily_quota 5→2 |
| `pipelines/travel/fetcher.py` | fetch_festival() fallback 시스템 비활성화 |

---

## 기술문서 v2.5 추가분 (2026-06-12)

### 변경 이력 추가

| 날짜 | 버전 | 주요 변경 |
|---|---|---|
| 2026-06-12 | v2.5 | humanize 단계 추가(5000+SAP), TAP sqlalchemy 설치, SEAP sync 가드, GAP 스케줄 비활성화, similar_title 반복 오류 확인 |

---

### 2026-06-12 주요 작업

#### 1. im-not-ai 한국어 humanize 단계 — 5000 파이프라인 적용

**배경**: AI 생성 한국어 글의 말투를 자연스럽게 교체하기 위해
[epoko77-ai/im-not-ai](https://github.com/epoko77-ai/im-not-ai) 의
패턴 룰셋을 5000 발행 파이프라인에 이식.

**생성 파일**: `shared/humanizer.py`

| 항목 | 내용 |
|---|---|
| 함수 | `humanize_korean(body_md, blog_id, title) → str` |
| AI 호출 | `ai_writer.generate()` tier=economy (gpt-4o-mini) 재사용 |
| 적용 패턴 | A계열(어미), C계열(AI특징), D계열(AI어투), F계열(번역투), G계열(Hedging) |
| 영문 보호 | 영문 비율 70%+ 시 즉시 원본 반환 (ETAP 자동 제외) |
| 길이 검증 | 결과물 85~115% 범위 이탈 시 원본 반환 |
| 실패 처리 | try/except — 실패해도 발행 중단 없음 |
| 처리 시간 | 평균 1.7s (테스트 기준) |

**수정 파일**: `shared/publisher.py` (719번 라인 직후)

```python
# ✅ humanize 단계 (2026-06-12 추가) — 한국어 파이프라인 전용
_KO_BLOG_IDS = {
    "rap-hugo", "rap2-hugo", "rap3-hugo", "rap4-hugo", "rap5-hugo",
    "travel-hugo", "travel1-hugo", "travel2-hugo", "travel3-hugo", "travel4-hugo",
    "stock-hugo", "stock1-hugo", "stock2-hugo", "stock3-hugo", "stock4-hugo", "stock5-hugo",
    "hotissue-hugo", "compare-hugo",
    "laptop-hugo", "appliance-hugo", "interior-hugo", "baby-hugo", "fitness-hugo",
    "senior-hugo", "senior2-hugo",
    ...
}
if blog_id in _KO_BLOG_IDS and body_md:
    try:
        from shared.humanizer import humanize_korean
        body_md = humanize_korean(body_md, blog_id, title)
    except Exception as _he:
        logger.warning(f"[HUMANIZE] 건너뜀 ({blog_id}): {_he}")
```

**레퍼런스**: `/Users/twinssn/Projects/im-not-ai/` (로컬 클론)

---

#### 2. im-not-ai 한국어 humanize 단계 — SAP 파이프라인 적용

**생성 파일**: `writers/humanizer.py` (SAP 전용)

| 항목 | 5000 | SAP |
|---|---|---|
| 파일 위치 | `shared/humanizer.py` | `writers/humanizer.py` |
| AI 호출 | `generate(tier="economy")` → dict | `generate_article(system, user)` → str |
| Tier | economy/default/fallback 3단 | 단일 클라이언트 (LLM_PROVIDER 설정 따름) |
| 블로그 필터 | `_KO_BLOG_IDS` 집합 | 전체 적용 (SAP 전 블로그 한국어) |
| 특화 보호 | 없음 | 선수명·팀명·경기 수치·표 구조 절대 변경 금지 |
| 처리 시간 | 평균 1.7s | 평균 1.8~3.9s |

**수정 파일**: `SAP/shared/publisher.py` (176번 라인 직후)

```python
# ✅ humanize 단계 (2026-06-12 추가)
if body_md:
    try:
        from writers.humanizer import humanize_korean
        body_md = humanize_korean(body_md, blog_id, title)
    except Exception as _he:
        logger.warning(f"[HUMANIZE] 건너뜀 ({blog_id}): {_he}")
```

---

#### 3. 6/11~12 장애 이력 및 해결

**3-1. TAP tap-blogger stage=unknown / stage=tap_subprocess_error**

- **현상**: 6/11 23:19 ~ 6/12 08:01 사이 6회 연속 실패
- **원인**: TAP venv에 `sqlalchemy` 미설치 → `core/camping_data.py` 등에서
  `No module named 'sqlalchemy'` → 중복 체크 실패 → subprocess 비정상 종료
- **해결**:
```bash
cd /Users/twinssn/Projects/TAP
source venv/bin/activate
pip install sqlalchemy  # 2.0.50 설치
```
- **확인**: `[중복 체크 통과] content_key: api_camping_...` 로그 정상 출력

---

**3-2. SEAP SeniorSync 실패 — API 타임아웃**

- **현상**: 매일 05:30 `[SeniorSync] 실패: ...` 오류 반복
- **원인**: `fetch_senior_services(max_pages=110)` → 최대 11,000건 API 호출
  → 외부 API(`api.odcloud.kr`) 응답 지연으로 스케줄러 타임아웃
- **현재 pending**: 762건 (충분)
- **해결 1**: `pipelines/senior/fetcher.py` 178번 라인

```python
# 수정 전
raw = fetch_senior_services(page=1, per_page=100, max_pages=110)
# 수정 후
raw = fetch_senior_services(page=1, per_page=100, max_pages=10)
```

- **해결 2**: `scheduler.py` `_run_senior_sync()` pending 가드 추가

```python
# ✅ pending 500건 이상이면 sync 불필요 (2026-06-12 추가)
if pending >= 500:
    logger.info(f"[SeniorSync] pending {pending}건 충분 — sync 스킵")
    return
```

---

**3-3. GAP keyword sync — 스크립트 파일 없음**

- **현상**: 매일 05:00 `GAP keyword sync stderr: ...sync_golden_to_gap.p` 오류
- **원인**: `scripts/sync_golden_to_gap.py` 파일 없음 (삭제 또는 미생성)
- **조치**: GAP 파이프라인 현재 미사용 → 스케줄 비활성화

```python
# scheduler.py 574~575번 라인 주석 처리
# schedule.every().day.at("05:00").do(_run_gap_keyword_sync)
# logger.info("GAP keyword sync scheduled at 05:00")
```

---

**3-4. CUAP auto_collector — No module named 'pipelines.curation' (미해결)**

- **현상**: 23:50 ~ 익일 07:57 매시간 반복 발생
- **원인**: 미확인 (import 직접 테스트는 OK)
- **추정**: auto_collector 실행 시 working directory 또는 PYTHONPATH 문제
- **상태**: ⚠️ 모니터링 중 — 다음 발생 시 상세 추적 필요

---

**3-5. similar_title 반복 실패 — 키워드 풀 고갈 의심**

| 블로그 | 실패 횟수 | 비고 |
|---|---|---|
| pet-hugo | 6/11~12 각 4회+ | CATCHUP 3회 모두 소진 |
| fitness-hugo | 6/11 3회, 6/12 3회 | |
| health-hugo | 6/12 4회 + 600s 타임아웃 | |
| appliance-hugo | 6/12 3회 | |
| laptop-hugo | 6/12 3회 | |
| camping-hugo | 6/11~12 반복 | stage=title_blocked |

- **원인**: 키워드 TTL 30일 + 카테고리 14일 중복 억제로 새 키워드 고갈
- **상태**: ⚠️ 키워드 풀 확대 필요 (특히 pet-hugo, health-hugo)

> **[2026-08-15 read-only 진단 — M06 잔량 지표 측정 왜곡 발견]**
> 위 3-5의 "TTL 30일 + 카테고리 14일 중복 억제로 고갈" 가설을 재검증한 결과, 근거가 부분만 성립함. 진단은 코드/config/DB 변경 없이 수행.

- **[검증됨] [정정] 발행 후보 풀은 KEYWORD_MAP과 동일 소스**: `ops_dashboard/checks/maintenance.py`의 `_check_keyword_availability`(L242-327)는 잔량을 `KEYWORD_MAP`(정적 Python dict, `pipelines/curation/keywords.py`) 정의수 − `published_products` 사용 distinct 수로 산출. 실제 발행 파이프라인도 `get_keywords(blog_id)` → `KEYWORD_MAP.get(blog_id, [])`(keywords.py:1774-1776)로 동일 소스를 사용. [정정] "파이프라인이 `naver_trending_keywords`를 소비"한다는 2026-08-15 주장은 오류였음.
- **[검증됨] [정정] 진짜 왜곡 원인은 계산 방식 차이**: 소스 불일치가 아니라, M06은 all-time used 차감(잔량 음수 가능, 예: interior -39)으로 계산하고, 파이프라인 `_select_keyword`(pipeline.py:154-223)는 publish_log 30일 윈도우 중복 제외(pipeline.py:167-171) + 14일 카테고리 억제(173-180,199) + 격리 제외(184) + 상품≥3(206-209)로 재활용하기 때문에 수치가 다름.
- **[검증됨] [정정] collected_at 기반 30일 TTL은 코드에 없음(미작동)**: `naver_trending_keywords`에서 `collected_at < now-30d`인 행이 514~935개 있으나, TTL로 후보를 삭제/필터하는 코드가 확인되지 않아 "사용 불가 사유로 작용" 여부는 미확정. (3-5의 "TTL 30일로 고갈" 가설은 이 지점에서 근거 부족.)
- **[검증됨] [정정] 8개 블로그 실발행 가능 후보 수(30일 윈도우, 재현 측정)**: `_select_keyword` 필터(30일 publish_log 제외 + 격리 제외 + 14일 카테고리 억제 + 상품≥3)를 그대로 재현해 `data/curation.db`에서 계산한 결과 — fitness 99, health 85, interior 76, laptop 72, beauty 52, baby 38, kitchen 37, camping 21. 재현 SQL: `SELECT keyword FROM publish_log WHERE blog_id=? AND published_at > datetime('now','-30 days')` (30일 사용분), `... '-14 days'` (카테고리 억제분), `SELECT keyword FROM keyword_health WHERE blog_id=? AND quarantined_until > datetime('now')` (격리분), `SELECT COUNT(*) FROM products WHERE keyword=?` ≥3 (상품분). → camping(21)만 임계 24 미달이고 나머지 7개는 초과.
- **[검증불가] [정정취소] 직전 초안의 "후보 153~242건" 수치는 재현 불가**: 초안이 적은 interior 194 / laptop 169 / kitchen 161 / beauty 153 / camping 173 / baby 242 / fitness 199 / health 172 는 각 블로그의 `KEYWORD_MAP` **정의 수 자체**(interior 140, laptop 101, kitchen 92, beauty 109, camping 103, baby 149, fitness 180, health 152)를 8개 전부 초과한다. 필터 후 부분집합이 원본 집합보다 클 수 없으므로 이 수치는 KEYWORD_MAP 기반 후보 수가 아니며, 산출 경로를 특정할 수 없어 폐기한다. 위 재현 측정치로 대체.
- **[검증됨] [보강] M06에 `real_candidates_30d` 병기 필드 추가**: 커밋 `72278e5fc` — 기존 all-time 잔량 필드와 pass/fail 판정은 무변경으로 두고, `_check_keyword_availability`(maintenance.py:316-350)에 30일 윈도우 실발행 후보 수를 병렬 계산해 병기. **상한 추정치 성격**: `_select_keyword`의 relevance gate(pipeline.py:211-217 `score_products`/`passes_gate`)는 재현하지 않으므로 실제 발행 가능 수는 이 값 이하다. 현재 값 = 위 재현 측정치와 일치(fitness 99 / health 85 / interior 76 / laptop 72 / beauty 52 / baby 38 / kitchen 37 / camping 21).

- **결론**: CUAP 블로그 활성화 차단의 근본 원인은 "키워드 소진"이 아니라 "M06 지표가 all-time used 차감 방식으로 계산하는 반면 파이프라인은 30일 윈도우 + 다단 필터로 재활용한다"는 계산 방식 차이. 실제 키워드 소스(KEYWORD_MAP)는 정상 보충 중. 회복 실행은 미수행(판정만).

---

**3-6. 텔레그램 알림 두절**

- **현상**: 6/12 07:56 `Failed to resolve 'api.telegram.org'`
- **원인**: M1 맥 일시적 DNS 장애
- **해결**: 스케줄러 재시작 후 자동 복구

---

### 스케줄러 재시작 (2026-06-12 08:58)

```bash
launchctl unload ~/Library/LaunchAgents/com.5000.scheduler.plist
launchctl load ~/Library/LaunchAgents/com.5000.scheduler.plist
```

**재시작 후 확인**:
- `Registered 138 jobs` ✅
- `GAP keyword sync scheduled` 로그 없음 ✅ (비활성화 확인)
- HealthCheck senior/stock 썸네일 정상 ✅
- CATCHUP appliance-hugo 발행 재개 ✅

---

### 수정 파일 목록 (2026-06-12)

| 파일 | 수정 내용 |
|---|---|
| `shared/humanizer.py` (신규) | 한국어 humanize 함수 (179줄) |
| `shared/publisher.py` | humanize 단계 삽입 (719번 라인) |
| `SAP/writers/humanizer.py` (신규) | SAP 전용 humanize 함수 (182줄) |
| `SAP/shared/publisher.py` | humanize 단계 삽입 (176번 라인) |
| `pipelines/senior/fetcher.py` | max_pages 110→10 |
| `scheduler.py` | SeniorSync pending 가드 추가, GAP 스케줄 주석 처리 |

---

### 잔여 과제

| 항목 | 우선순위 | 내용 |
|---|---|---|
| pet-hugo / health-hugo 키워드 풀 확대 | 🔴 높음 | similar_title 반복 실패 해소 |
| CUAP auto_collector 모듈 오류 추적 | 🟡 중간 | 매시간 반복 오류 근본 해결 |
| HUMANIZE 로그 스케줄러 파일 연동 | 🟡 중간 | shared.humanizer logger → scheduler.log |
| TAP Heritage 시군구 2건 조건 완화 | 🟡 중간 | heritage 296건 잔량 활용 |
| camping-hugo title_blocked 원인 분석 | 🟡 중간 | 제목 블록 패턴 확인 필요 |
| STAP collector venv 경로 수정 | 🟢 낮음 | `.venv/python3 없음` WARNING |

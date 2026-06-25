
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

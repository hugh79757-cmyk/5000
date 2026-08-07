# 61-F Dead-Code Report — 인라인 DB 경로 상수, shared/db.py 로 대체 (Report-Only)

> Phase 61 · Plan 61-09 · Stage F. 작성일: 2026-08-07
> **성격: 식별 전용 보고서.** 아무 코드도 삭제·수정하지 않는다 (destructive-ops 규칙).
> 삭제는 별도 Phase/승인 후 4단계 프로토콜로 수행한다.

---

## 1. 배경

Phase 61 (D-06)에서 분기별 SQLite DB 경로 해석을 `shared/db.py::get_db_path()` 로 중앙화했다.
본 보고서는 각 파이프라인 분기가 아직 들고 있는 인라인 DB 경로 상수 중, `get_db_path()` 로
대체 가능한 것을 **식별**한다. **실제 제거는 수행하지 않는다.**

`shared/db.py::_BRANCH_DB` 지원 분기: **car, rap, senior, curation, stock**.
`get_db_path()` 는 이 분기만 해석하며, 미지원 분기(travel, etap, gap)는 `ValueError` 를 던진다.

---

## 2. 분기별 인라인 DB 상수 전체 목록

아래는 `grep -rn "_DB_PATH\s*=\|DB_PATH\s*=" pipelines/ shared/` 실측 결과다.
각 상수는 3가지로 분류한다:
- **[중앙화됨]** 이미 `get_db_path()` 사용 — 삭제 대상 아님 (배선 확인용).
- **[인라인-대체후보]** 하드코딩 경로 — `get_db_path()` 로 대체 가능 (미래 삭제 후보).
- **[비대체]** `shared/db.py` 가 매핑하지 않는 파일 — 대체 불가 / 의도적 유지.

### 2.1 car (CAP)

| 파일:라인 | 상수 | 분류 | 대체 해석 |
|-----------|------|------|-----------|
| `pipelines/car/pipeline.py:27` | `CAR_DB_PATH = Path(_get_db_path("car"))` | **[중앙화됨]** — `from shared.db import get_db_path as _get_db_path` (L18) | `get_db_path("car") → data/car.db` |
| `pipelines/car/daily_refresh.py:18` | `DB_PATH = Path(__file__).parent.parent.parent / "data" / "car.db"` | **[인라인-대체후보]** | `get_db_path("car") → data/car.db` 로 동일 해석 가능 |

### 2.2 rap (RAP)

| 파일:라인 | 상수 | 분류 | 대체 해석 |
|-----------|------|------|-----------|
| `pipelines/rap/pipeline.py:22` | `RAP_DB_PATH = get_db_path("rap")` | **[중앙화됨]** | `get_db_path("rap") → data/rap.db` |
| `pipelines/rap/pipeline.py:24` | `GAP_DB_PATH = os.path.join(..., "data", "gap.db")` | **[비대체]** — `gap.db` 는 `get_db_path()` 미매핑. 코드 주석(L23)도 "gap.db 는 shared/db.py 로 배선하지 않음" 명시 | gap은 중앙화 범위 밖, 의도적 인라인 유지 |
| `pipelines/rap/rap_data_sync.py:24` | `RAP_DB_PATH = os.path.join(..., "data", "rap.db")` | **[인라인-대체후보]** | `get_db_path("rap") → data/rap.db` 로 동일 |

### 2.3 senior (SEAP)

| 파일:라인 | 상수 | 분류 | 대체 해석 |
|-----------|------|------|-----------|
| `pipelines/senior/fetcher.py:143` | `SENIOR_DB_PATH = get_db_path("senior")` | **[중앙화됨]** | `get_db_path("senior") → data/senior.db` |

### 2.4 curation (CUAP)

| 파일:라인 | 상수 | 분류 | 대체 해석 |
|-----------|------|------|-----------|
| `pipelines/curation/auto_collector.py:32` | `DB_PATH = BASE_DIR / "data" / "curation.db"` | **[인라인-대체후보]** | `get_db_path("curation") → data/curation.db` |
| `pipelines/curation/collector.py:50` | `DB_PATH = os.path.join(..., "data", "curation.db")` | **[인라인-대체후보]** | 동일 |
| `pipelines/curation/keyword_expander.py:26` | `DB_PATH = BASE_DIR / "data" / "curation.db"` | **[인라인-대체후보]** | 동일 |
| `pipelines/curation/naver_datalab_sync.py:31` | `DB_PATH = BASE_DIR / "data" / "curation.db"` | **[인라인-대체후보]** | 동일 |
| `pipelines/curation/pipeline.py:96` | `DB_PATH = Path(get_db_path("curation"))` | **[중앙화됨]** | `get_db_path("curation") → data/curation.db` |
| `pipelines/curation/keyword_health.py` | **(상수 없음)** | **[비대체]** | `db_path` 를 생성자 인자로 받음 (`KeywordHealthStore(db_path)`) — `data/curation.db` L21은 docstring 예시일 뿐 상수 아님 |

> **Review 정정 (신뢰성):** 61-REVIEWS.md는 curation "6개 상수"로 열거했으나, 실측 결과
> 인라인-대체후보는 **4개**(auto_collector/collector/keyword_expander/naver_datalab_sync)이고
> `pipeline.py:96`은 이미 중앙화됨, `keyword_health.py:21`은 **상수 아님**(docstring)이다.
> 따라서 curation의 "중앙화로 대체 가능한 인라인 상수"는 **4개**다 (6개 아님).

### 2.5 stock (STAP — 외부 분기, 계약만)

| 파일:라인 | 상수 | 분류 | 대체 해석 |
|-----------|------|------|-----------|
| `pipelines/stock/pipeline.py:17` | `DB_PATH = os.path.join(..., "data", "stock.db")` | **[비대체/주의]** | `get_db_path("stock")` 은 `stap_content.db`(ARTICLES_DB)를 반환 — **`stock.db` 와 다른 파일**. 대체하면 경로가 바뀜. 주의 |
| `pipelines/stock/fetcher.py:42` | `DB_PATH = os.path.join(..., "data", "stock.db")` | **[비대체/주의]** | 동일 — `stock.db` ≠ `stap_content.db` |

> stock 은 Phase 61에서 계약 정합만(물리 병합 금지). `stock.db` 인라인 상수는
> `get_db_path("stock")`(→stap_content.db)과 다른 파일을 가리키므로 무단 대체 금지. 별도 판단 필요.

### 2.6 etap — **중앙화 범위 밖** (Review 정정 반영)

- etap 에는 **다수의 `DB_PATH` 상수가 존재하지만 전부 `data/travel-en.db` 를 가리킨다.**
  `shared/db.py` 는 `travel`/`etap` 분기를 매핑하지 않는다 (`get_db_path('travel')` → `ValueError`,
  §6.4). 따라서 이 상수들은 **`shared/db.py` 로 대체 불가**이며 이 보고서의 "대체 대상"이 **아니다.**
- 실측: `pipelines/etap/` 에서 `DB_PATH` 할당 **72개**, `travel-en.db` 참조 파일 **144개**.
- **잘못된 함의 금지:** "etap 이 인라인 DB 상수 때문에 dead code"로 서술하지 않는다.
  etap 의 travel-en.db 상수는 중앙화 대상이 아니다.

### 2.7 travel — **인라인 DB 상수 없음** (Review 정정 반영)

- `pipelines/travel/` 에는 `*_DB_PATH` 인라인 상수가 **0개** (grep 실측).
- travel 은 `PUBLISH_LEDGER_DB`(content.db) + `ARTICLES_DB`(stap_content.db) +
  `FESTIVAL_DB` 를 `shared/db_paths.py` 로 사용한다 (PIPELINE-STANDARD §6.4).
- **잘못된 함의 금지:** travel 이 인라인 DB 상수를 가진 것으로 서술하지 않는다.

---

## 3. 정리 (치환 가능한 인라인-대체후보 집계)

`get_db_path()` 로 동일 해석 가능한 **[인라인-대체후보]** 인라인 상수:

| 분기 | 파일:라인 | 상수 | 목표 DB |
|------|-----------|------|---------|
| car | `daily_refresh.py:18` | `DB_PATH` | car.db |
| rap | `rap_data_sync.py:24` | `RAP_DB_PATH` | rap.db |
| curation | `auto_collector.py:32` | `DB_PATH` | curation.db |
| curation | `collector.py:50` | `DB_PATH` | curation.db |
| curation | `keyword_expander.py:26` | `DB_PATH` | curation.db |
| curation | `naver_datalab_sync.py:31` | `DB_PATH` | curation.db |

**인라인-대체후보 총 6개** (car 1, rap 1, curation 4).
이 6개는 `get_db_path()` 로 치환 가능한 미래 제거 후보다. **제거는 수행하지 않는다.**

**이미 중앙화됨 (배선 확인, 삭제 아님):** car/pipeline.py:27, rap/pipeline.py:22,
senior/fetcher.py:143, curation/pipeline.py:96.

**비대체 (중앙화 범위 밖):** rap GAP_DB_PATH(gap.db), curation keyword_health(상수 없음),
stock(다른 파일), etap(전부 travel-en.db), travel(상수 없음).

---

## 4. 결론 및 규칙

1. `shared/db.py` 는 car/rap/senior/curation/stock 만 매핑한다. **gap, travel, etap 는 대체 불가.**
2. `shared/db_paths.py` 는 **확장해 유지** (replace 금지, D-06/D-08) — 기존 심볼명 보존.
3. **명시: 삭제는 별도 Phase/승인 필요. 본 보고서는 식별만.**
   이 plan 61-09에서 어떤 파이프라인 코드도 삭제·수정하지 않았다.

---

## 5. 수정된 Review 항목 요약

| Review 항목 | 상태 |
|-------------|------|
| car: CAR_DB_PATH(pipeline.py:27) + DB_PATH(daily_refresh.py:18) | ✅ 열거 (각각 중앙화됨 / 인라인-대체후보) |
| rap: RAP_DB_PATH + GAP_DB_PATH | ✅ 열거 (중앙화됨 / 비대체) |
| senior: SENIOR_DB_PATH(fetcher.py) | ✅ 열거 (중앙화됨) |
| curation: 6개 상수 | ✅ 열거 — 단, 실측상 인라인-대체후보는 4개 (pipeline.py:96 중앙화됨, keyword_health.py 상수 아님) |
| travel / etap 인라인 DB 상수 없음(함의 금지) | ✅ 반영 — etap 는 travel-en.db 로 중앙화 범위 밖, travel 은 상수 0개 |

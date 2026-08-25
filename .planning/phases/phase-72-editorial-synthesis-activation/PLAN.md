---
phase: 72-editorial-synthesis-activation
plan: 01
type: execute
wave: 1
depends_on: []
autonomous: true
requirements: [PH72-SYN-ACTIVATE, PH72-DATA-REAL, PH72-QUALITY, PH72-PERSIST-BLOCK]
files_modified:
  - pipelines/etap/data_adapters.py
  - pipelines/etap/flight_writer.py
  - pipelines/etap/deals_writer.py
  - pipelines/etap/nature_writer.py
  - pipelines/car/pipeline.py
  - pipelines/stock/writer.py
  - pipelines/rap/writer.py
  - pipelines/curation/writer.py
  - pipelines/senior/writer.py
  - pipelines/travel/writer.py
  - pipelines/etap/topic_manager.py
  - pipelines/etap/uniqueness_check.py
  - pipelines/etap/quality_guard.py
  - dispatcher.py
  - tests/test_data_adapters.py
  - tests/test_editorial_quality.py
user_setup: []

must_haves:
  truths:
    - "9개 writer 모두 topic_type 전달로 비어있지 않은 synthesis(≥80자) 반환"
    - "adapter가 분기별 실DB에서 unique_data_points ≥3개 조회"
    - "synthesis 내 모든 수치가 unique_data 값 집합에 존재 (hallucination 차단)"
    - "synthesis 단락의 동일 블로그 최근 10건 대비 cosine < 0.7"
    - "S03/S04 위반 시 blocked=True 전환 (kill-switch로 warn-only 복귀 가능)"
  artifacts:
    - path: "pipelines/etap/data_adapters.py"
      provides: "11개 topic_type 어댑터 (기존4 + 신규7)"
    - path: "pipelines/etap/quality_guard.py"
      provides: "editorial_synthesis_quality_gate 신규 함수"
    - path: "pipelines/etap/uniqueness_check.py"
      provides: "editorial_cosine_check 신규 함수"
    - path: "tests/test_editorial_quality.py"
      provides: "품질 게이트 + hallucination + cosine 단위테스트"
  key_links:
    - from: "writer 9곳 _inject_editorial_synthesis"
      to: "pipelines/etap/data_adapters.get_unique_data_points"
      via: "topic dict의 topic_type/topic_id"
      pattern: "get_unique_data_points\\(_tt"
    - from: "dispatcher.py preflight S03"
      to: "<topic_table>.unique_data_points 저장값 (T4.1)"
      via: "역추적된 topic_id로 topic 테이블 조회"
      pattern: "unique_data_points"
---

# Phase 72: Editorial Synthesis 활성화 — 실행 계획

> 설계 문서는 `.planning/designs/PHASE-71-editorial-synthesis-activation.md` (명칭은 71,
> 실제 페이즈 = 72). CONTEXT.md 제약사항 그대로 인용해 각 태스크에 강제한다.

## Objective

**무엇:** writer가 호출하는 `editorial_synthesis_step()`에 실제 데이터가 흐르게 한다.
현재는 writer 헬퍼가 `topic.get("topic_type")`을 읽지만 호출부가 빈 `{}`를 넘겨
adapter가 `[]`를 반환 → synthesis no-op (CONTEXT.md 8-12행, 아래 §1 증거).

**왜:** S03(unique_data_points)/S04(editorial_synthesis) 품질 게이트가 warn-only로
누워 있고 (commit 7f635eea4), blocking 재활성화의 전제조건은 "실데이터 주입 동작"이다.

**산출물:** 11개 topic_type 어댑터, 10개 호출부 주입, 품질 게이트 2종(길이·hallucination·cosine),
unique_data_points DB 저장, S03/S04 blocking 전환(+kill-switch), 테스트 확장.

## 목표 (설계 문서 성공 기준, 그대로)

| # | 기준 | 검증 |
|---|------|------|
| A | 9개 writer 모두 비어있지 않은 synthesis 반환 (≥80자) | W3 통합테스트 (fixture 기반, LLM 0회) |
| B | unique_data_points ≥3개 저장 | sqlite3 SELECT 길이≥3 JSON 배열 |
| C | cosine similarity < 0.7 (동일 블로그 최근 10건 대비) | `editorial_cosine_check()` 단위테스트 |

예상 소요: **~9h / 2일**, Wave 4개.

---

## §0. 사전 베이스라인 (작업 시작 전 반드시 기록)

```bash
# targeted — 현재 15 passed 확인됨 (2026-08-25 플래너 실행)
OPS_TEST_MODE=1 .venv/bin/python -m pytest tests/test_data_adapters.py tests/test_editorial.py -q

# full — 현재 기준선: 33 failed / 654 passed / 1 skipped (--ignore=tests/ops_dashboard)
OPS_TEST_MODE=1 .venv/bin/python -m pytest tests/ -q --ignore=tests/ops_dashboard
```

**중요 발견 (CONTEXT.md "tests pass" 기술과 다름):**
- `OPS_TEST_MODE=1` 없이 실행하면 conftest autouse fixture `_guard_prod_ops_db`가
  운영 ops.db 경로 감지로 **전 테스트 ERROR** (tests/conftest.py:40). Fixture 자체가
  `OPS_TEST_MODE=1` 우회로 제공. 모든 pytest 명령 앞에 `OPS_TEST_MODE=1` 필수.
- 기존 실패 33건은 curation/shared/test_uniqueness/test_preflight_c01 계열 —
  editorial과 무관한 **선존재 결함**. 본 페이즈 완료 판정은 "33건 초과로 열화 없음" 기준.
- `tests/ops_dashboard/test_checker_patches_20260820.py`는 collection 자체가
  ImportError (`C06_GRACE_HOURS`가 ops_dashboard/checks/content_integrity.py에
  존재하지 않음) — 선존재, 본 페이즈 범위 외.

---

## §1. 현행 코드 증거 (플래너 직접 검증)

### 1.1 no-op의 원인 — 호출부가 빈 topic 전달

| writer 파일:line | 전달값 | 스코프 내 식별자 |
|---|---|---|
| `pipelines/travel/writer.py:1393` | `{}` | `data`(source_type/items), `blog_id` (fn :1070) |
| `pipelines/senior/writer.py:626` | `{}` | `topic_type`, `main_service["service_id"]` (:613-615) |
| `pipelines/curation/writer.py:1010` | `{}` | `keyword`, `products` (fn :799) |
| `pipelines/rap/writer.py:700` | `{}` | `keyword`, `trades` (fn generate_trade_article) |
| `pipelines/rap/writer.py:918` | `{}` | `keyword`, `subscriptions` (fn :899) |
| `pipelines/stock/writer.py:203` | `{}` | `disclosure`(corp_name/rcept_dt :38-40), `financials` |
| `pipelines/stock/writer.py:415` | `{}` | `topic_type`(문자열), `corp_data`, `extra_data` (fn :207) |
| `pipelines/etap/flight_writer.py:199` | city/slug만 | `topic` Row (**id 포함**) |
| `pipelines/etap/deals_writer.py:309` | city/slug만 | `topic` Row (**id 포함**) |
| `pipelines/etap/nature_writer.py:280` | city/slug만 | `topic` Row (**id 포함**) |

9개 writer 헬퍼는 전부 동일 로직: `_tt = topic.get("topic_type")` → 없으면 `[]` →
`editorial_synthesis_step`이 빈 unique_data에 `""` 반환 (`pipelines/etap/editorial_synthesis.py:54-55`)
→ body 무변경. 예: `pipelines/travel/writer.py:39-52`.

### 1.2 CAP(car) 특이사항 — 라이브 경로에 synthesis 호출 자체가 없음

- `pipelines/car/writer.py:18 write_article()` 안에 synthesis 블록 존재(:53-64)하나
  **호출자가 없음** (repo 전역 grep 결과 `scripts/scaffold_branch.py` 템플릿 문자열뿐).
  데드 코드.
- 실제 생성은 `pipelines/car/pipeline.py:245 generate_car(prompt_text, data)` →
  `:253 validate_body(body, data)` 인라인 경로. synthesis 주입 없음.
- 따라서 car는 **호출부 신설**(W1 T1.2)이 필요한 유일 분기.

### 1.3 adapter 현황 — topic_id 무시로 교차 오염 위험

- `ADAPTER_REGISTRY = {flight, viator, nature, deals}` 4종, 전부 travel-en.db만 조회
  (`pipelines/etap/data_adapters.py:185-190`, `_DB_PATH` :14).
- `get_unique_data_points(topic_type, topic_id)` — 미등록 type은 `[]` 반환, 절대 raise
  안 함 (:193-203). **W1에서 dict만 넣어도 신규 type은 자동 no-op → 안전 배포 가능.**
- ⚠️ `flight_adapter(topic_id=None)`은 topic_id를 **완전 무시**하고 flight_prices 전역
  `ORDER BY price ASC LIMIT 20` (:50-74). 다른 도시의 최저가를 해당 글 데이터로 합성할
  위험 = hallucination의 실제 경로. W2에서 수정.
- `nature_adapter`/`deals_adapter`는 topic_id로 row 조회 후 폴백 (:107-114, :149-156) — 양호.
- `viator_adapter`는 topic 개념 없음(전역 인기 상품, :77-100) — 현행 유지, 문서화만.

### 1.4 dispatcher S03/S04 warn-only 위치

- S03: `dispatcher.py:878-918`. ETAP 블로그 한정(`ETAP_PIPELINE_BLOGS` :586),
  publish_log에서 slug→topic_id 역추적 후 `unique_data_points_gate(body, source_data, threshold=3)` (:908).
  위반 append(:910-914) 후 **`blocked = True` 미설정** — 주석 "WARN-ONLY ... blocked 미설정".
- S04: `dispatcher.py:920-929`. 본문 내 미치환 `{{...}}` 마커 검출 방식. 마찬가지 blocked 미설정.
- S02에서 만든 `corpus` 변수(:862 부근)가 스코프에 있음 → cosine 체크 재배치 가능.

### 1.5 DB 컬럼 현황 (sqlite3 PRAGMA 실측)

| DB | unique_data_points 보유 테이블 |
|---|---|
| travel-en.db | **38개 topic 테이블 전부 + publish_log** ✓ |
| car.db | `topics` ✓ |
| rap.db | 없음 (publish_log: id/blog_id/data_type/data_key/title/published_at) |
| senior.db | 없음 (services: service_id 등 17컬럼) |
| stock.db | 없음 (publish_log: source_id 주소 가능) |
| curation.db | 없음 (publish_log: keyword 주소 가능) |
| stap_content.db | 없음 (articles) |
| gap.db | **파일만 존재, 테이블 0개** |

### 1.6 저장/신선도 경로

- 컬럼에 unique_data_points를 **쓰는 코드는 현재 존재하지 않음** (전역 grep 확인).
  읽는 곳도 없음 — 게이트가 매번 재구성하는 이유.
- 자연 훅: `pipelines/etap/topic_manager.py:232 mark_published_by_id()` — 이미
  publish_log INSERT + topics.exhausted UPDATE 수행. optional 파라미터 추가로 저장 연동.
- lastmod/dateModified는 **Phase 70에서 이미 구현됨** (hugo_writer.py:1421-1427,
  layouts/partials/schema.html:1-10) → W4 범위에서 제외, unique_data_points 저장만.

### 1.7 재사용 가능한 검증 도구

- `pipelines/etap/quality_guard.py:340 structural_similarity_gate(content, corpus, threshold)`
  — TF-IDF 코사인. :441 `unique_data_points_gate(content, source_data, threshold=3)`.
- `pipelines/etap/uniqueness_check.py:56 _fetch_corpus(blog_id)` — content.db에서
  동일 블로그 최근 문서 수집. cosine 체크의 corpus 소스로 재사용.

---

## §2. 파이프라인별 Adapter 매핑표 (W2 구현 대상)

| 브랜치 | writer | topic_type | 주소 키 | 데이터 소스 (table.column) | adapter 함수 |
|---|---|---|---|---|---|
| ETAP flight | flight_writer.py | `flight` | topic.id | flight_topics.origin/dest → flight_prices.price/stops/departure_date/airline | `flight_adapter` **수정**(id 스코핑) |
| ETAP deals | deals_writer.py | `deals` | topic.id | deals_topics.title/deal_count + flight_prices(origin join) | `deals_adapter` 유지(이미 id 사용) |
| ETAP nature | nature_writer.py | `nature` | topic.id | nature_topics.city/title + viator_tours.price/duration/category(city join) | `nature_adapter` 유지 |
| CAP car | pipeline.py 라이브 경로 | `car` | topic.id | car.db topics(컬럼 이미 존재) + data.base_price/model/trim | 신규 `car_adapter` |
| STAP evergreen | stock/writer.py:415 | `stock_evergreen` | topic_type 문자열(dividend_ranking 등) | stock.db dividend_ranking.rank/dividend_yield/dividend_per_share, corps | 신규 |
| STAP disclosure | stock/writer.py:203 | `stock_disclosure` | corp_code(추정: disclosure dict 키 — 구현 시 실측) | stock.db corps(재무 컬럼) | 신규 |
| RAP trade | rap/writer.py:700 | `rap_trade` | keyword(data_key) | rap.db trades(실거래가) | 신규 |
| RAP sub | rap/writer.py:918 | `rap_sub` | keyword | rap.db subscriptions/gongsijiga | 신규 |
| CUAP | curation/writer.py:1010 | `curation` | keyword | curation.db products(price/rating 등) | 신규 |
| SEAP | senior/writer.py:626 | `senior` | service_id | senior.db services(department/deadline 등) | 신규 |
| TAP | travel/writer.py:1393 | `tap` | **DB 주소 키 없음** | `data["items"]` 인메모리 파생(가격/날짜) | passthrough (§T2.4 설계결정) |

**TAP 설계 결정:** TAP은 5000 내부에 topic-id로 주소 가능한 로컬 스토어가
존재하지 않음(소스가 외부 TAP 프로젝트/API fetch). DB 키 없는 어댑터는 환각 경로가
되므로, writer 헬퍼에 `topic["unique_data"]` passthrough 1줄 추가 — 호출 스코프에
이미 있는 items에서 결정론적으로 points 추출. DB 이중조회도 없음(제약 부합).
*이 결정은 설계 문서 Wave 2 "분기별 DB 조회"에 대한 유일한 예외다.*

**LLM 제약 해석:** 기존 `editorial_synthesis.py`는 템플릿 기반 결정론, LLM 호출 0회
(모듈 docstring :1-6). "LLM은 synthesis 생성에만 1회" 제약은 **0회가 최소**이므로
현 구조 유지가 제약 충족. 신규 LLM 호출 추가 계획 없음.

---

## §3. Tasks

### 공통 규칙 (모든 태스크)

- **Additive only**: 기존 함수 시그니처 불변. 새 파라미터는 optional/default.
  기존 동작 경로 삭제·교체 금지.
- 모든 테스트 명령 앞 `OPS_TEST_MODE=1` (§0).
- 커밋은 wave당 최소 1개, W4 blocking 전환은 독립 커밋 (rollback 지점).
- **배포는 반드시 dispatcher.py 경유 또는 shared/publishers/deploy.deploy_site()**
  (AGENTS.md 배포 규칙). 수동 `wrangler pages deploy`/`wrangler deploy` 금지.
  git push = 형상관리 용도 only (Cloudflare git 빌드 월 500회 제한).

---

## Wave 1 — topic dict 주입 (~2h) `[독립 배포 가능]`

어댑터는 미등록 type에 `[]`를 반환하므로(data_adapters.py:195-198) 이 wave만으로
배포해도 동작 변화 없음(no-op 유지). 순수 준비 wave.

#### Task 1.1 — ETAP 3 writer 호출부에 topic_type+topic_id 주입
- **파일:** `pipelines/etap/flight_writer.py`, `pipelines/etap/deals_writer.py`, `pipelines/etap/nature_writer.py`
- **변경:** 각 `_inject_editorial_synthesis(content, {...})` 호출의 dict에
  `"topic_type": "flight"|"deals"|"nature"`와 `"topic_id": topic.get("id")` 추가.
  기존 city/country/slug 키는 **보존**(합성 context로 사용 중).
  - flight_writer.py:199, deals_writer.py:309, nature_writer.py:280.
  - `pick_*`가 반환하는 topic은 sqlite Row→dict로 `id` 보유 (flight_pipeline.py:139
    에서 `topic["id"]` 사용 실측).
- **검증:**
  ```bash
  OPS_TEST_MODE=1 .venv/bin/python -m pytest tests/test_data_adapters.py tests/test_editorial.py -q
  grep -n 'topic_type.*flight' pipelines/etap/flight_writer.py   # 199행 부근 1건
  grep -n 'topic_type.*deals' pipelines/etap/deals_writer.py     # 309행 부근 1건
  grep -n 'topic_type.*nature' pipelines/etap/nature_writer.py   # 280행 부근 1건
  ```
- **완료:** 3파일 모두 dict에 topic_type/topic_id 존재, 기존 테스트 green 유지.
- **예상:** 30분

#### Task 1.2 — CAP(car) 라이브 경로 synthesis 주입 신설
- **파일:** `pipelines/car/pipeline.py`
- **변수:** `validate_body(body, data)` 후 `data`에 model/trim/base_price 존재
  (pipeline.py:230 로그 실측), `topic` dict 스코프 내 (topic["post_type"] :236 사용).
- **변경:** 최종 body 확정 지점(재생성 분기 :264-266 이후)에 post_processor의
  공용 진입점 1회 호출 추가:
  `from pipelines.etap.post_processor import apply_editorial_synthesis;`
  `body = apply_editorial_synthesis(body, topic=topic, topic_type="car", topic_id=topic.get("id"))`.
  apply_editorial_synthesis는 registry 게이트 + try/except로 실패 시 원본 반환
  (post_processor.py:471-489) → additive 보장. 데드코드 car/writer.write_article은
  수정하지 않고 SUMMARY에 데드코드임을 기록만.
- **검증:**
  ```bash
  OPS_TEST_MODE=1 .venv/bin/python -c "
  from pipelines.etap.post_processor import apply_editorial_synthesis
  out = apply_editorial_synthesis('본문', topic={'id': 1}, topic_type='car', topic_id=1)
  assert out == '본문'  # car 어댑터 미등록 → no-op 확인
  print('ok')"
  grep -n 'apply_editorial_synthesis' pipelines/car/pipeline.py  # 1건
  ```
- **완료:** 라이브 경로에 호출 1회 존재, 어댑터 등록 전까지 no-op.
- **예상:** 20분

#### Task 1.3 — STAP/RAP/CUAP/SEAP 6 호출부 dict 주입
- **파일:** `pipelines/stock/writer.py`, `pipelines/rap/writer.py`,
  `pipelines/curation/writer.py`, `pipelines/senior/writer.py`
- **변경 (기존 `{}` → 식별자 포함 dict, 그 외 무변경):**
  - stock/writer.py:203 → `{"topic_type": "stock_disclosure", "topic_id": disclosure.get("corp_code") or disclosure.get("corp_name", "")}`
  - stock/writer.py:415 → `{"topic_type": "stock_evergreen", "topic_id": str(topic_type)}`
  - rap/writer.py:700 → `{"topic_type": "rap_trade", "topic_id": keyword}`
  - rap/writer.py:918 → `{"topic_type": "rap_sub", "topic_id": keyword}`
  - curation/writer.py:1010 → `{"topic_type": "curation", "topic_id": keyword}`
  - senior/writer.py:626 → `{"topic_type": "senior", "topic_id": main_service.get("service_id", "")}`
- **검증:**
  ```bash
  rg -n '"topic_type"' pipelines/stock/writer.py pipelines/rap/writer.py pipelines/curation/writer.py pipelines/senior/writer.py  # 각 파일 ≥1건, 빈 {} 잔여 0건
  rg -n '_inject_editorial_synthesis\([^)]+, \{\}\)' pipelines/  # 매칭 0건
  OPS_TEST_MODE=1 .venv/bin/python -m pytest tests/ -q --ignore=tests/ops_dashboard -k "editorial or data_adapters"
  ```
- **완료:** repo에서 빈 `{}` 전달 호출부 0건.
- **예상:** 30분

#### Task 1.4 — TAP passthrough 지원 + tap type 선언
- **파일:** `pipelines/travel/writer.py`
- **변경:**
  1. 헬퍼(travel/writer.py:39-46)의 데이터 해석 줄을
     `_ud = _t.get("unique_data") if _t.get("unique_data") is not None else (get_unique_data_points(_tt, ...) if _tt else [])`
     로 변경 — dict 키 추가일 뿐 시그니처 불변. 다른 writer는 건드리지 않음.
  2. :1393 호출부 → `{"topic_type": "tap"}`.
  3. items→points 결정론 추출은 W2 T2.4에서 연결 (이번엔 passthrough 통로만).
- **검증:**
  ```bash
  OPS_TEST_MODE=1 .venv/bin/python -c "
  import importlib, pipelines.travel.writer as w
  fn = w._inject_editorial_synthesis
  out = fn('BODY', {'topic_type': 'tap', 'unique_data': [{'label':'price','value':'15000','unit':'KRW','source_table':'items'}]})
  assert 'price 15000' in out and len(out) > len('BODY'), 'passthrough 실패'
  out2 = fn('BODY', {})           # 기존 no-op 경로 보존
  assert out2 == 'BODY'
  print('ok')"
  ```
- **완료:** passthrough 경로 동작 + 빈 topic no-op 회귀 없음.
- **예상:** 20분

---

## Wave 2 — adapter 실데이터 반환 (~3.5h) `[W1 필요, 독립 배포 가능]`

#### Task 2.1 — flight_adapter topic 스코핑 수정 (교차 오염 제거)
- **파일:** `pipelines/etap/data_adapters.py` (:50-74)
- **변경:** `flight_adapter(topic_id)`가 id로 flight_topics row를 먼저 조회해
  origin/destination 확보 → `flight_prices WHERE origin=? AND destination=?` 스코핑.
  row 없으면 현행 전역 폴백 **유지**(동작 변경 아님 — 우선순위 추가).
  반환 point 스키마 {label,value,unit,source_table} 불변.
- **배경:** 현행은 전역 LIMIT 20이라 다른 노선 최저가가 합성에 유입됨 (§1.3) —
  이것이 hallucination 위험의 실제 경로.
- **검증:**
  ```bash
  OPS_TEST_MODE=1 .venv/bin/python -c "
  from pipelines.etap.data_adapters import flight_adapter
  pts = flight_adapter(topic_id=999999)   # 없는 id → 폴백 경로, list 보장
  assert isinstance(pts, list)
  print('ok', len(pts))"
  OPS_TEST_MODE=1 .venv/bin/python -m pytest tests/test_data_adapters.py -q
  ```
- **완료:** 존재하는 topic_id로 조회 시 route가 해당 topic 노선과 일치.
- **예상:** 45분

#### Task 2.2 — 신규 adapter 7종 + registry 확장 + 테스트 assertion 확장
- **파일:** `pipelines/etap/data_adapters.py`, `tests/test_data_adapters.py`
- **변경:**
  1. §2 매핑표대로 `car_adapter`, `stock_evergreen_adapter`, `stock_disclosure_adapter`,
     `rap_trade_adapter`, `rap_sub_adapter`, `curation_adapter`, `senior_adapter` 신규.
     공통 유틸(`_connect`/`_query`/`_point`) 재사용, DB path는 각 분기 DB
     (data/car.db, data/stock.db, data/rap.db, data/curation.db, data/senior.db).
     기존 4종과 동일 계약: **절대 raise하지 않고 [] 반환**.
  2. `ADAPTER_REGISTRY`에 7키 추가 (기존 4키 불변).
  3. 테스트 assertion 확장 — `test_registry_has_four_keys`의
     `set(keys) == {...4}` 등식은 `set(keys) >= {...4}` 상등 유지 의미(원래 4키 존재
     보장)로 치환 + 신규 7키 존재 assertion 신설. 나머지 테스트 무수정.
     *이는 "기존 assertion 의미 보존" 제약의 적용이다.*
- **검증:**
  ```bash
  OPS_TEST_MODE=1 .venv/bin/python -m pytest tests/test_data_adapters.py -q          # 전부 pass
  OPS_TEST_MODE=1 .venv/bin/python -c "
  from pipelines.etap.data_adapters import get_unique_data_points as g
  for t in ['car','stock_evergreen','stock_disclosure','rap_trade','rap_sub','curation','senior']:
      r = g(t); assert isinstance(r, list), t
  print('ok')"
  ```
- **완료:** 11키 registry, 각 어댑터 실측 DB에서 ≥1 point 반환(데이터 있는 경우).
- **예상:** 90분

#### Task 2.3 — DB 마이그레이션 — 본 페이즈 제외 (후속 이월)
- **판단 근거:** rap/curation/stock/senior DB에는 본 페이즈에 unique_data_points
  **쓰기 경로가 없다** — T4.1 저장 연동은 ETAP 전용(topic_manager/flight_pipeline의
  mark_published). 컬럼만 추가하면 아무도 안 쓰는 데드 스키마가 되므로 YAGNI로 제외.
  성공기준 B는 travel-en.db(flight_topics 등)만으로 판정(§5 참조).
- **후속 절차(해당 브랜치 저장 연결 시):** 쓰기 경로와 함께 ALTER를 같은 태스크에서
  수행할 것. 그때 AGENTS.md 파괴적 작업 4단계 프로토콜(사전 카운트 → 사용자 확인 →
  백업 → 실행 → 사후 대조) + **라이브 스케줄러(launchd) 정지 확인 선행**(정지 확인
  전 실행 금지)을 반드시 적용.
- **검증:**
  ```bash
  git status --porcelain data/ | wc -l   # 0 = DB 미변경
  ```
- **완료:** data/*.db 변경 0건 (본 페이즈 파괴적 작업 없음).
- **예상:** 5분 (확인만)

#### Task 2.4 — TAP items 파생 points 빌더 연결
- **파일:** `pipelines/travel/writer.py`
- **변경:** `_derive_points_from_items(items)` 모듈内 신규 함수 — items의 가격/날짜/
  위치 필드를 {label,value,unit,source_table:"items"}로 변환(결정론, 상한 12개).
  generate_content 내 :1393 직전에 `topic_dict["unique_data"] = _derive_points_from_items(data.get("items", []))`
  주입. LLM 0회, DB 0회.
- **검증:**
  ```bash
  OPS_TEST_MODE=1 .venv/bin/python -c "
  from pipelines.travel.writer import _derive_points_from_items
  pts = _derive_points_from_items([{'title':'A','price':'15000'},{'title':'B'}])
  assert isinstance(pts, list) and all(set(p)=={'label','value','unit','source_table'} for p in pts)
  assert _derive_points_from_items([]) == []
  print('ok')"
  ```
- **완료:** items 있으면 ≥1 point, 없으면 [] (no-op 회귀 없음).
- **예상:** 25분

---

## Wave 3 — 합성 품질 검증 (~1.5h) `[W1·W2 필요]`

#### Task 3.1 — synthesis 품질 게이트 (길이 + hallucination)
- **파일:** `pipelines/etap/quality_guard.py` (신규 함수 추가), `tests/test_editorial_quality.py` (신규)
- **변경:** `editorial_synthesis_quality_gate(paragraph: str, unique_data: list) -> tuple[bool, dict]`
  신규 — (a) 길이 ≥80자, (b) paragraph 내 모든 숫자 토큰이 unique_data의
  value 문자열 집합에 포함(deterministic 템플릿이라 구조적으로 보장되나 회귀 방지),
  (c) 출처 source_table명 1개 이상 포함. 기존 게이트 함수들은 무수정.
- **behavior (테스트 먼저):**
  - 정상 synthesis(unique_data 3개, 수치 일치) → (True, {...})
  - 길이 50자 → False
  - 미존재 수치 "9999999" 삽입 → False
  - unique_data=[] + 빈 paragraph → False
- **검증:** `OPS_TEST_MODE=1 .venv/bin/python -m pytest tests/test_editorial_quality.py -x -v` (4+ pass)
- **완료:** 게이트 함수 + 테스트 green.
- **예상:** 40분

#### Task 3.2 — cosine <0.7 체크 + dispatcher S06(warn-only) 연결
- **파일:** `pipelines/etap/uniqueness_check.py` (신규 함수), `dispatcher.py` (S04 직후)
- **변경:**
  1. `editorial_cosine_check(paragraph: str, blog_id: str, threshold: float = 0.70) -> tuple[bool, float]`
     신규 — `_fetch_corpus(blog_id)`(:56) 재사용, **최근 10건만**, 본문 끝 synthesis
     단락과 TF-IDF 코사인 산출(기존 calculate_structural_similarity :134의 기계 재사용).
  2. dispatcher preflight S04 블록(:929) 직후에 S06 체크 추가: 본문 말미 synthesis
     단락 추출 → editorial_cosine_check → violations에 rule_id="S06" append.
     **blocked 설정 없음(WARN-ONLY)** — corpus 변수는 S02에서 만든 것 재사용.
- **검증:**
  ```bash
  OPS_TEST_MODE=1 .venv/bin/python -c "
  from pipelines.etap.uniqueness_check import editorial_cosine_check
  ok, cos = editorial_cosine_check('완전 새로운 고유 데이터 기반 문장입니다 15000원 2026년', 'travel-hugo')
  assert isinstance(ok, bool) and isinstance(cos, float)
  print('ok', cos)"
  OPS_TEST_MODE=1 .venv/bin/python -m pytest tests/test_editorial_quality.py -q
  ```
- **완료:** S06 warn-only 위반 기록 동작, 기존 S01~S05 로직 무변경.
- **예상:** 35분

#### Task 3.3 — no-LLM end-to-end 통합 테스트
- **파일:** `tests/test_editorial_quality.py` (클래스 추가)
- **변경:** synthetic fixture(topic dict + 실DB 어댑터 mock 없이 tmp sqlite 조립 또는
  실DB read-only 조회) → `get_unique_data_points` → `editorial_synthesis_step` →
  `editorial_synthesis_quality_gate` 파이프라인 테스트. ai_generate 호출 경로 없음.
  성공기준 A의 자동 검증(9 writer 헬퍼 로직은 동일 구현이므로 대표 경로 3종 +
  passthrough 1종 검증).
- **검증:** `OPS_TEST_MODE=1 .venv/bin/python -m pytest tests/test_editorial_quality.py -x -v` (8+ pass)
- **완료:** adapter→synthesis→gate 체인이 데이터 있을 때 ≥80자 단락 생성.
- **예상:** 20분

---

## Wave 4 — 저장 + S03/S04 blocking 재활성화 (~2h) `[W1~W3 필요, 마지막 전환]`

#### Task 4.1 — unique_data_points 저장 연동 (optional 파라미터)
- **파일:** `pipelines/etap/topic_manager.py`, `pipelines/etap/flight_pipeline.py`
- **변경:**
  1. `mark_published_by_id(...)`에 optional `unique_data_points=None` 추가(시그니처
     하위호환) — None이면 현행 SQL 그대로, 값 있으면 topics UPDATE SET 절에
     `unique_data_points = ?` 추가(json.dumps). publish_log INSERT는 무변경.
  2. ETAP 각 pipeline의 mark 호출부(flight_pipeline.mark_published :121-127은 별도
     구현 — 동일하게 optional 확장)에서 synthesis가 붙었던 article의 points 전달.
     points는 writer 반환 article에 `article["unique_data_points"]`로 실어
     (writer 수정 1줄 × 3 — dict 키 추가).
- **검증:**
  ```bash
  OPS_TEST_MODE=1 .venv/bin/python -m pytest tests/ -q --ignore=tests/ops_dashboard -k "topic_manager or mark_published" 
  # 시그니처 하위호환 확인
  OPS_TEST_MODE=1 .venv/bin/python -c "
  import inspect
  from pipelines.etap.topic_manager import mark_published_by_id
  sig = inspect.signature(mark_published_by_id)
  p = sig.parameters['unique_data_points']
  assert p.default is None
  print('ok')"
  ```
- **완료:** 기존 호출부 전부 무수정 동작, 새 값 전달 시 컬럼에 JSON 저장.
- **예상:** 50분

#### Task 4.2 — dispatcher S03/S04 blocking 전환 + kill-switch
- **파일:** `dispatcher.py` (:913-915, :927-928 부근)
- **변경:**
  1. kill-switch: `os.getenv("QUALITY_ENFORCE_S03_S04", "1") == "1"` 일 때만 blocked=True
     설정. "0"이면 현행 warn-only 유지. (false positive 발생 시 env 변경 + launchd
     재시작으로 즉시 복귀 — 재배포 불필요)
  2. S04 blocked=True 전환 (미치환 마커 존재 = CRITICAL 유지).
  3. S03 보강(additive): 기존 source_data 재구성이 비었고, 이미 역추적된 topic_id의
     `<topic_table>.unique_data_points`(T4.1이 topics 테이블에 저장한 값)가 있으면
     gate 입력으로 사용. 기존 재구성 로직은 폴백으로 보존.
     (publish_log에는 저장하지 않는다 — T4.1이 topics UPDATE만 하므로 읽는 위치를
     저장 위치와 일치시켜 도달 불가능한 죽은 경로를 방지.)
- **검증:**
  ```bash
  OPS_TEST_MODE=1 QUALITY_ENFORCE_S03_S04=1 .venv/bin/python -c "
  import os, re
  src = open('dispatcher.py').read()
  assert 'QUALITY_ENFORCE_S03_S04' in src
  print('ok')"
  OPS_TEST_MODE=1 .venv/bin/python -m pytest tests/test_preflight_c01.py -q  # 기존 preflight 테스트 열화 없음(현재 2 failed 선존재 — 증가만 금지)
  ```
- **완료:** default(enforce)에서 위반 시 blocked=True, kill-switch로 warn-only 복귀.
- **예상:** 40분

#### Task 4.3 — 최종 회귀 + 수용 체크리스트
- **파일:** 없음 (검증 전용)
- **검증:**
  ```bash
  # 1. targeted green
  OPS_TEST_MODE=1 .venv/bin/python -m pytest tests/test_data_adapters.py tests/test_editorial.py tests/test_editorial_quality.py -q
  # 2. full suite 열화 없음 (baseline 33 failed 초과 금지)
  OPS_TEST_MODE=1 .venv/bin/python -m pytest tests/ -q --ignore=tests/ops_dashboard 2>&1 | tail -1
  ```
- **완료 판정:** §5 체크리스트 전항 충족.
- **예상:** 20분

---

## §4. Wave 의존 그래프

```
W1 (주입, no-op) ──→ W2 (어댑터 실데이터) ──→ W3 (품질 게이트) ──→ W4 (저장 + blocking)
 │                        │                        │                    │
 └ T1.1~T1.4 병렬 가능     └ T2.1/T2.2/T2.4 병렬     └ T3.1∥T3.2→T3.3     └ T4.1→T4.2→T4.3
```

- W1 내부 4태스크: 서로 다른 파일 → 병렬 가능 (T1.4만 travel/writer.py 단일 점유).
- W2: T2.3은 제외됨(후속 이월) — 코드 태스크 T2.1/T2.2/T2.4만 병렬 실행.
- W3: T3.1과 T3.2는 서로 다른 파일 → 병렬 가능. T3.3은 둘 다 필요.
- W4: T4.1(저장)이 T4.2(stored-points 사용)의 선행.
- 각 wave 완료 시점마다 독립 배포 가능 (W1·W2는 동작 변화 없거나 additive,
  W3은 warn-only, W4만 blocking).

## §5. 최종 수용 체크리스트 (성공기준 ↔ 검증 매핑)

| 기준 | 검증 명령/방법 | 합격선 |
|---|---|---|
| 9 writer ≥80자 synthesis | T3.3 통합테스트 + 실발행 1건 샘플 확인(dispatcher.py 경유) | 9/9 경로 커버 |
| unique_data_points ≥3개 저장 | `sqlite3 data/travel-en.db "SELECT length(unique_data_points) FROM flight_topics WHERE unique_data_points IS NOT NULL ORDER BY rowid DESC LIMIT 1"` ≥ 3포인트 JSON | 저장 확인 |
| cosine < 0.7 | `editorial_cosine_check` 테스트 + 실발행 S06 로그에 위반 없음 | threshold 0.70 |
| 회귀 없음 | full suite failed ≤ 33 (baseline) | baseline 유지 |
| 배포 규칙 준수 | 배포 이력 전부 dispatcher.py/deploy_site 경유 | 수동 wrangler 0건 |

## Rollback 전략 (wave별 git revert 지점)

| Wave | revert 단위 | 폴백 동작 |
|---|---|---|
| W1 | 커밋 revert | dict만 변경 — 어댑터 미등록 type은 자동 `[]`(no-op), 사이드이펙트 0 |
| W2 | 어댑터 파일 커밋 revert | registry 키 소실 → `[]` 반환으로 자동 비활성(data_adapters.py:195-198) |
| W2-T2.3 | 불필요 (변경 없음) | 본 페이즈 ALTER 없음 — 후속 이월 시에만 백업/복원 적용 |
| W3 | S06 블록 revert | warn-only라 발행 영향 0 |
| W4 | **revert 전에 kill-switch 우선**: `QUALITY_ENFORCE_S03_S04=0` + launchd 재시작 | 즉시 warn-only 복귀, 재배포 불필요. 근본 해결은 W4 커밋 revert |

## Risks

| # | 위험 | 확률 | 영향 | 완화 |
|---|---|---|---|---|
| R1 | 합성 본문 수치 환각 | 낮음 | 품질/신뢰 | 결정론 템플릿(LLM 0회) + T3.1 숫자∈값집합 검사 + T2.1 교차오염 제거 |
| R2 | (이월됨) 후속 DB 마이그레이션 중 라이브 스케줄러 충돌 | — | 발행 지연 | 본 페이즈는 ALTER 없음. 이월 태스크에서 파괴적 4단계 프로토콜 + 스케줄러 정지 확인 선행 적용 |
| R3 | writer 회귀 (기존 발행 경로 파손) | 낮음~중 | 일일 발행 중단 | additive-only, dict 키 추가만, baseline 열화 감시(≤33 failed), wave별 배포 |
| R4 | W4 blocking 오탐(false positive)으로 발행량 급감 | 중간 | 발행량 | kill-switch env, S03은 ETAP 블로그 한정(dispatcher.py:586,879), 1주 관찰 후 판정 |
| R5 | 배포 결합 사고 (수동 wrangler, CLOUDFLARE_API_TOKEN) | 낮음 | 배포 실패/계정 오염 | AGENTS.md 규칙 명시: dispatcher.py 경유만, `env -u CLOUDFLARE_API_TOKEN` |
| R6 | disclosure dict에 corp_code 키 부재 | 중간(추정) | STAP 주소키 공란 | T2.2에서 실측 후 corp_name 폴백 — 어댑터는 [] 폴백이라 치명 없음 |

## Verification Plan 요약

- **BEFORE:** §0 두 명령 실행, 결과 기록 (targeted 15 passed / full 33F·654P).
- **Wave별:** 각 task의 `<검증>` 명령 + wave 종료 시 targeted 3파일 green.
- **FINAL:** §5 체크리스트. full suite는 baseline 대비 열화 없음이 기준
  (선존재 33 failed는 본 페이즈에서 수정하지 않음 — 범위 외).

<verification>
1. OPS_TEST_MODE=1 .venv/bin/python -m pytest tests/test_data_adapters.py tests/test_editorial.py tests/test_editorial_quality.py -q → 전부 pass
2. OPS_TEST_MODE=1 .venv/bin/python -m pytest tests/ -q --ignore=tests/ops_dashboard → failed ≤ 33
3. sqlite3: 본 페이즈 신규 ALTER 없음 확인 + T4.1 후 travel-en.db topics 저장 확인(§5)
4. dispatcher.py에 QUALITY_ENFORCE_S03_S04 분기 존재, S03/S04 blocked=True 경로 존재
</verification>

<success_criteria>
- [ ] 9개 writer 호출부가 topic_type(+가능한 식별자) 전달 — 빈 {} 잔여 0건
- [ ] ADAPTER_REGISTRY 11종, 각 adapter never-raise 계약 준수
- [ ] 성공기준 A/B/C 자동 검증 테스트 green
- [ ] S06(cosine) warn-only 연결, S03/S04 blocking + kill-switch
- [ ] unique_data_points 저장 경로(mark_published_by_id optional 확장) 동작
- [ ] data/*.db 변경 0건 (본 페이즈 파괴적 작업 없음 — ALTER는 후속 이월), baseline 열화 없음
</success_criteria>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| DB→synthesis | adapter가 읽은 값이 그대로 발행물 문장에 삽입됨 (SQL 결과 신뢰 전제) |
| LLM 본문→S04 | GPT 생성 본문에 미치환 마커 잔존 가능 |
| env→dispatcher | QUALITY_ENFORCE_S03_S04로 게이트 강도 제어 |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-72-01 | Tampering (데이터 오염) | flight_adapter 전역 질의 | mitigate | T2.1 topic 스코핑 — 타 노선 값 유입 원천 차단 |
| T-72-02 | Repudiation (근거 없는 수치) | editorial_synthesis 출력 | mitigate | T3.1 숫자∈unique_data 값집합 gate |
| T-72-03 | DoS (발행 대량 차단) | dispatcher S03/S04 flip | mitigate | kill-switch env + ETAP 한정 적용 + 관찰 기간 |
| T-72-04 | Info Disclosure | unique_data_points JSON 노출 | accept | 가격/날짜等 공개 정보뿐, 개인정보 없음 |
| T-72-SC | Tampering | (패키지 설치 없음) | n/a | 신규 의존성 추가 0건 — stdlib sqlite3/json만 사용 |
</threat_model>

<output>
`.planning/phases/phase-72-editorial-synthesis-activation/72-01-SUMMARY.md` 작성
(실행 완료 후). 커밋: wave별 분리 커밋, 메시지 접두사 `feat(72-xx)`/`test(72-xx)`.
</output>

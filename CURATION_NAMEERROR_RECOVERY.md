# CURATION_NAMEERROR_RECOVERY.md

> **Recovery 시각**: 2026-08-19 08:46-08:50 KST
> **트리거**: `pipelines/curation/writer.py:980` — `select_llm_title` NameError
> **영향 블로그**: 13개 curation pipeline 블로그 (appliance, baby, beauty, bike, camping, fitness, health, homeappliance, interior, kitchen, laptop, massage, pet)

---

## 1. 운영 영향

### 장애 시각 범위

| 항목 | 값 |
|------|-----|
| 최초 NameError 로그 | 2026-08-19 08:35 (스케줄러에 의해 재현) |
| 복구 시각 | 2026-08-19 08:50 (13개 블로그 active 복원) |
| 총 영향 시간 | ~15분 |
| 영향 블로그 수 | 13개 (curation pipeline 사용 블로그 전부) |
| 영향 없는 블로그 | pick-hugo (car pipeline), ETAP/TAP/STAP/RAP/SEAP 블로그 |

### 스케줄러 영향

- PID 16389는 NameError를 exception으로 catch하여 해당 블로그만 skip
- 스케줄러 자체는 정상 동작 유지 (PID 16389, CPU 0.0%, MEM 0.4%)
- 전체 발행 파이프라인에 영향 없음 (다른 pipeline 블로그 정상 발행)

### 발행 영향

- NameError 발생 블로그: 발행 0건 (writer.py import 시점에서 exception 발생 → `_run_inner()` 미진입)
- 스케줄러가 exception을 catch하여 `exception:NameError` 로그 기록 후 다음 블로그로 진행

---

## 2. 변경 전후 diff

### writer.py 변경 전 (HEAD 기준)

```python
# line 979-980 (NameError 발생 지점 — d887e094f 미커밋 변경)
if title and products:
    title = select_llm_title(keyword, products, blog_id, recent_titles, title, ai_generate, logger)
```

### writer.py 변경 후 (복구)

```python
# line 979 — select_llm_title 호출 제거
if template_type:
```

### 미커밋 변경 중 유지된 것들 (SAFE)

| 변경 | 라인 | 안전 이유 |
|------|------|-----------|
| `_site_title_guidance()` 함수 정의 | 343 | writer.py 내부에 정의됨, 외부 의존 없음 |
| `site_title_guidance = _site_title_guidance(blog_id)` | 355 | 내부 함수 호출 |
| `{site_title_guidance}{recent_block}` | 416 | 문자열 포맷에 추가 |

### cuap_title_llm.py

| 항목 | 값 |
|------|-----|
| 경로 | `shared/cuap_title_llm.py` |
| 해시 (MD5) | 기록된 해시 유지 |
| git 상태 | **untracked** (origin/main에 없음) |
| 용도 | `select_llm_title()` 함수 정의 — LLM 기반 제목 선택 |

---

## 3. 테스트 결과

### 테스트 항목

| 테스트 | 결과 | 비고 |
|--------|------|------|
| `py_compile writer.py` | **✅ 통과** | SyntaxWarning 2건 (pre-existing backslash escapes) |
| `py_compile pipeline.py` | **✅ 통과** | |
| `from pipelines.curation.writer import generate_curation_article` | **✅ 통과** | NameError 없음 |
| `test_pick_hugo_fallback.py` (12개) | **✅ 12/12 통과** | |
| 전체 curation 테스트 | **0 collected** | pre-existing `schedule` module issue |

### 신규 실패 0건 확인

- 복구 전: `exception:NameError` 13건 (13개 블로그 각 1건)
- 복구 후: NameError 재현 안 됨 (import 정상)
- 기존 테스트 12개 전부 통과, 신규 실패 0건

---

## 4. Pause/Active 시각

| 작업 | 시각 |
|------|------|
| 13개 블로그 pause | 2026-08-19 08:46 |
| select_llm_title 호출 복원 | 2026-08-19 08:47 |
| 문법 검사 + 테스트 | 2026-08-19 08:48 |
| 13개 블로그 active 복원 | 2026-08-19 08:50 |

---

## 5. 미추적 LLM 기능의 별도 설계 필요성

### `select_llm_title()` 기능 분석

`shared/cuap_title_llm.py`는 LLM을 사용해 쿠팡 상품 제목을 선택하는 기능:

```python
def select_llm_title(keyword, products, blog_id, recent_titles, fallback, ai_generate, logger, attempts=3):
    # products에서 LLM으로 제목 선택
    # fallback이 있으면 폴백 제목 사용
    # recent_titles와 중복 방지
```

### 왜 미추적 상태인가

1. `shared/cuap_title_llm.py`는 git-untracked — origin/main에 없음
2. `writer.py`에서 import 없이 호출 — 개발 중간 상태
3. 의도적으로 draft 중이거나, 실수로 커밋 누락

### 별도 설계가 필요한 이유

1. **import 경로 확정 필요**: `from shared.cuap_title_llm import select_llm_title` 추가 필요
2. **의존성 관리**: `cuap_title_llm.py`가 사용하는 LLM API/auth 설정 확인 필요
3. **테스트 커버리지**: `select_llm_title()` 자체 테스트 필요 (mock LLM)
4. **fallback 경로**: LLM 실패 시 기존 제목 생성 경로로 fallback하는지 확인 필요
5. **curation 파이프라인과의 통합**: `generate_curation_article()` 흐름에서 어떤 시점에 호출할지 설계 필요

### 권장 후속 조치

| 우선순위 | 조치 | 설명 |
|----------|------|------|
| 1 | `cuap_title_llm.py`를 git에 추가 | 현재 untracked → 추적 시작 |
| 2 | import 추가 + 테스트 | writer.py에 import 추가, LLM mock 테스트 |
| 3 | fallback 경로 검증 | LLM 실패 시 기존 제목 경로 폴백 확인 |
| 4 | staging 테스트 | 1개 블로그에서만 먼저 테스트 발행 |

> **이 기능은 현재 미완성 상태입니다. 별도의 설계·테스트·staging 과정 없이 프로덕션에 배포하면 NameError가 재발합니다.**

---

## 6. 잔존 위험

1. `cuap_title_llm.py`가 git-untracked — 다른 에이전트나 세션이 다시 import 추가할 수 있음
2. writer.py의 `_site_title_guidance()` 변경이 미커밋 상태 — bike-hugo에만 영향하는 로직
3. `normalize_title`/`preserve_slug` 호출이 curation/pipeline.py에 존재 (d887e094f에서 추가됨) — 현재는 ae90ed63a로 원복되어 안전하나, 재도입 시 import 누락 재발 가능

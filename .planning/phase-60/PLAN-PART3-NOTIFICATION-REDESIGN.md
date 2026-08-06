# Phase 60 Part 3 — 알림 재설계

> 작성: 2026-08-06 | 상태: 확정
> 배경: 하루 30~50건 텔레그램 소음 → "사람이 지금 손대야 하는 것"만 실시간, 나머지 일일 요약.

---

## 0. 현재 구조 분석

### 알림 경로 (3개, 모두 `_tg_error()` 경유)

| 경로 | 트리거 | 현재 동작 |
|------|--------|----------|
| `dispatcher.py → _tg_error()` | pipeline 실패 시 즉시 발송 | **모든 실패를 즉시 발송** (소음 주범) |
| `PublishMonitor.report()` | dispatcher/pipeline 훅 경유 | `ThresholdChecker` 쿨다운 적용, 중복 억제 |
| `shared/daily_report.py` | scheduler에서 1일 1회 | TAP/LAP 발행 건수 요약만 (P-code 미포함) |

### P-code 분류표 (problem_registry.py 기준)

| P-code | 이름 | severity | 현재 threshold | 분류 | 판정 근거 |
|--------|------|----------|---------------|------|----------|
| P04 | deploy_error | CRITICAL | always | **실시간** | 배포 실패 — 사람 조치 필요 |
| P05 | hugo_build_failed | CRITICAL | always | **실시간** | 빌드 실패 — 사람 조치 필요 |
| P06 | broken_featureimage | CRITICAL | always | **실시간** | 썸네일 404 — 사람 조치 필요 |
| P07 | cjk_leak | CRITICAL | always | **실시간** | 콘텐츠 오염 — 즉시 차단 필요 |
| P08 | llm_cot_leak | CRITICAL | always | **실시간** | CoT 누수 — 즉시 차단 필요 |
| P09 | image_url_repeat | CRITICAL | always | **실시간** | 이미지 반복 — 즉시 차단 필요 |
| P01 | no_result | MAJOR | consecutive:3 | **요약** | 데이터 없음 — 연속 3회 시 알림, 일상적 |
| P02 | no_content | MAJOR | consecutive:3 | **요약** | 생성 실패 — 연속 3회 시 알림, 일상적 |
| P03 | similar_title | MAJOR | consecutive:3 | **요약** | 유사제목 차단 — 정비 대상 블로그에서 예상 |
| P10 | title_blocked | MAJOR | consecutive:3 | **요약** | 제목 차단 — 일상적 |
| P11 | title_regenerate_failed | MAJOR | consecutive:3 | **요약** | 제목 재생성 실패 — 일상적 |
| P12 | content_quality_gate | MAJOR | consecutive:3 | **요약** | 품질 게이트 차단 — Q-code로 분류 |
| P13 | rate_limited | MAJOR | consecutive:3 | **요약** | API 차단 — 시간 지나면 자동 해소 |
| P14 | collect/quality gate | MAJOR | consecutive:3 | **요약** | 수집 실패 — 일상적 |
| P15 | validation_failed | MAJOR | consecutive:3 | **요약** | 검증 실패 — Q-code로 분류 |
| P20 | subprocess_error | MAJOR | consecutive:3 | **요약** | subprocess 에러 — 자동 재시도 |
| P21 | config_error | MAJOR | consecutive:3 | **요약** | 설정 오류 — 정비 대상 |
| P22 | llm_fallback_exhausted | MAJOR | consecutive:3 | **요약** | LLM 전체 실패 — 시간 지나면 해소 |
| P16 | duplicate_slug | MINOR | quiet | **요약** | 중복 slug — 로그만 |
| P17 | quota_met | MINOR | quiet | **요약** | 할당량 도달 — 정상 동작 |
| P18 | already_running | MINOR | quiet | **요약** | 동시 실행 — 정상 동작 |
| P19 | stale_data | MINOR | quiet | **요약** | 만료 데이터 — 로그만 |
| P23 | image_url_length | MINOR | quiet | **요약** | URL 길이 초과 — 로그만 |
| P24 | validation_defect | MINOR | quiet | **요약** | 검증 결함 — 로그만 |
| unknown | 미분류 | MINOR | quiet | **실시간** | 미등록 에러 — 원인 파악 필요 |

### 추가 소음원: standard_compliance

| 항목 | 현재 동작 | 변경 |
|------|----------|------|
| `standard_compliance` 텔레그램 푸시 | check_results에서 fail 시 푸시 | ** 계속 꺼둠** — 대시보드에서만 확인 |
| `_check_standard_compliance()` | M05 maintenance check | 텔레그램 연결 없음 (정상) |

---

## 1. 작업 1 — 알림 분류 기준

### 분류 규칙 (코드화)

```python
# shared/notification_classifier.py (신설)

REALTIME_PUSH_PROBLEMS = {
    # CRITICAL — 즉시 조치 필요
    "P04", "P05", "P06", "P07", "P08", "P09",
    # 미등록 에러 — 원인 파악 필요
    "unknown_failure",
}

# 그 외 전부 → daily_summary
# 분류가 애매하면 "요약"이 기본값 (소음 최소화 편향)
```

### 분류 근거

- **실시간**: 사람의 즉시 조치가 파이프라인에 영향을 미치는 에러
  - deploy/build는 사이트 장애
  - cjk/cot/image_repeat은 콘텐츠 오염 → 검색 엔진 페널티
  - unknown은 예상 못한 에러 → 근본 원인 파악 필요
- **요약**: 정상 동작의 일부이거나, 시간이 지나면 자동 해소되는 항목
  - no_result/no_content: 파이프라인이quota 내에서 시도 후 실패
  - similar_title/title_blocked: 정비 대상 블로그에서 예상되는 차단
  - rate_limited: 시간 지나면 해소
  - quota_met/already_running: 정상 동작
  - P16/P19/P23/P24: 로그만 (quiet)

---

## 2. 작업 2 — daily_summary 구현

### 요약 메시지 포맷

```
📋 일일 알림 요약 (2026-08-06)

🔴 배포/빌드: 0건
🟡 차단/실패: 12건
  P03 similar_title ×5 (beauty, interior, kitchen, pick, senior)
  P02 no_content ×3 (travel4, sector, ...)
  P12 quality_gate ×2 (...)
  P14 collect_error ×2 (...)
🔵 정보: 8건
  P17 quota_met ×8 (정상)

📊 총 20건 (실시간 0 + 요약 20)
🔗 상세: http://localhost:5060/api/attention
```

### 구현 위치

- `shared/daily_summary.py` (신설)
- `shared/daily_report.py` 기존 코드를 유지하면서 병렬로 신설
- ops.db `daily_summary` 테이블에 기록

### daily_summary 테이블

```sql
CREATE TABLE IF NOT EXISTS daily_summary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    summary_date TEXT NOT NULL,          -- '2026-08-06'
    total_events INTEGER NOT NULL,
    realtime_count INTEGER NOT NULL,
    summary_count INTEGER NOT NULL,
    breakdown_json TEXT NOT NULL,        -- {"P03": 5, "P02": 3, ...}
    message_text TEXT NOT NULL,          -- 텔레그램 발송용 전체 메시지
    sent_at TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
```

### 실행 주기

- `scheduler.py`에서 하루 1회 (예: 23:00) 실행
- 또는 `daily_report.py`에 병합

---

## 3. 작업 3 — 실시간 푸시 게이트

### 변경 대상

| 파일 | 현재 동작 | 변경 |
|------|----------|------|
| `dispatcher.py:744` | `_tg_error()` 모든 deploy_err에 즉시 발송 | 유지 (deploy는 실시간) |
| `dispatcher.py:753-762` | no_result/no_content에 즉시 발송 | **차단** → daily_summary로 이동 |
| `dispatcher.py:767-770` | duplicate_slug에 즉시 발송 | **차단** → daily_summary로 이동 |
| `dispatcher.py:789-807` | `monitor.report()` 병렬 발송 | 유지 (PublishMonitor가 자체 쿨다운 관리) |

### dispatcher.py 변경 요약

```python
# 기존:
if reason in ("no_result", "no_data", "fetch_error", "no_content"):
    _tg_error(blog_id, reason, ...)

# 변경:
if reason in ("no_result", "no_data", "fetch_error", "no_content"):
    _record_failure(blog_id, reason, ...)
    # _tg_error 제거 → daily_summary에서 집계
```

### 실시간 푸시에 포함할 내용

- detail/evidence/조치(action) 포함 (기존 템플릿 유지)
- 대시보드 링크 포함: `{DASHBOARD_URL}/blog/{blog_id}`

---

## 4. 작업 4 — 디바운스/상한

### 규칙

- **동일 P-code + 동일 블로그**: 하루 1회로 접기 (원건수는 요약에 반영)
- **전체 실시간 푸시 상한**: 시간당 최대 10건 (이상 시 초과분은 요약으로 이동)
- **구현**: `shared/notification_debounce.py` (신설)

### 디바운스 테이블

```sql
CREATE TABLE IF NOT EXISTS notification_debounce (
    blog_id TEXT NOT NULL,
    problem_id TEXT NOT NULL,
    push_date TEXT NOT NULL,           -- '2026-08-06'
    first_seen_at TEXT NOT NULL,
    suppressed_count INTEGER DEFAULT 0,
    PRIMARY KEY (blog_id, problem_id, push_date)
);
```

### 푸시 시점 로직

```python
def should_push(blog_id, problem_id):
    # 1. daily_summary에 기록
    # 2. debounce 테이블 확인
    existing = db.execute(
        "SELECT suppressed_count FROM notification_debounce "
        "WHERE blog_id=? AND problem_id=? AND push_date=today",
        (blog_id, problem_id))
    if existing:
        # 이미 오늘 푸시함 → 억제, suppressed_count++
        return False
    # 3. 새 이벤트 → 푸시 + debounce 등록
    return True
```

---

## 5. 시뮬레이션 (beauty-hugo 기준)

### 오늘 발생 이벤트 (실제 데이터)

| P-code | 건수 | 현재 | 변경 후 |
|--------|------|------|---------|
| P03 similar_title | 2건 | 즉시 발송 ×2 | **요약** (0건 실시간) |
| P04 deploy_error | 0건 | — | — |
| Q5/Q6 quality | M04 fail | 대시보드만 | 유지 |
| standard_compliance | M05 fail | 대시보드만 | 유지 |

**변경 전**: beauty-hugo → 하루 ~2건 텔레그램 (similar_title 2건)
**변경 후**: beauty-hugo → 0건 실시간, 요약에 P03 ×2 포함

### 전체 시뮬레이션 (50 블로그 기준)

| 항목 | 변경 전 (추정) | 변경 후 |
|------|---------------|---------|
| 실시간 푸시 | 30~50건/일 | 2~5건/일 |
| 일일 요약 | 0건 | 1건/일 (23:00) |
| 총 텔레그램 메시지 | 30~50건 | 3~6건 |

**소음 절감율**: ~90%

---

## 6. 신설 파일 요약

| 파일 | 용도 |
|------|------|
| `shared/notification_classifier.py` | P-code → 실시간/요약 분류 |
| `shared/daily_summary.py` | 일일 요약 생성 + 텔레그램 발송 |
| `shared/notification_debounce.py` | 동일 이벤트 하루 1회 억제 |

### 수정 파일

| 파일 | 변경 내용 |
|------|----------|
| `dispatcher.py` | no_result/no_content/duplicate_slug의 `_tg_error()` 호출 제거 |
| `ops_dashboard/db.py` | daily_summary + notification_debounce 테이블 추가 |
| `ops_dashboard/app.py` | /api/daily-summary 엔드포인트 추가 |
| `ops_dashboard/templates/index.html` | 오늘 요약 표시 영역 추가 |

---

## 7. 범위 제한

- **보류**: writer.py/prompts.yaml 등 콘텐츠 파이프라인 실수정 (Q5/Q6/STRUCT-07 등록 유지)
- **보류**: Part 4 (M03 크로스링크 자동검사)
- **이번 범위**: 알림 경로만 — notification_classifier, daily_summary, debounce

---

**Part 3 완료 후 Part 4(체크 보강) 착수 가능.**

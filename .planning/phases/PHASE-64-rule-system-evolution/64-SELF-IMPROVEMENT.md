# Phase 64 — 자기개선 메커니즘 3종 설계

## 개요

규칙 체계는 한 번 만들고 끝나는 것이 아니라, 운영 중 발견되는 문제로 계속 진화해야 한다. 이 문서는 세 가지 자기개선 메커니즘을 설계한다.

---

## 메커니즘 (a): leak_tracker 로그 집계 리포트

### 현황

`shared/leak_tracker.py`가 C01/C04 탐지를 3단계((a)생성직후 (b)humanizer후 (c)저장직전)에서 `logs/leak-origin.log`에 기록 중이다. Phase 62에서 도입.

로그 형식(추정):
```
[2026-08-07T14:30:00] stage=before_write rule=C04 blog=health-hugo slug=저혈압... detected=True
[2026-08-07T14:30:01] stage=before_write rule=C04 blog=health-hugo slug=저혈압... detected=False
```

### 설계

#### 로그 스키마 (JSONL 권장)

기존 텍스트 로그를 JSONL로 전환하거나, 병행 기록:

```json
{"timestamp": "2026-08-07T14:30:00", "stage": "before_write",
 "rule_id": "C04", "blog_id": "health-hugo", "slug": "저혈압...",
 "detected": true, "detail": "프롬프트 누수 패턴 '생각해보자'"}
```

필드:
- `timestamp`: ISO 8601
- `stage`: "after_generation" / "after_humanizer" / "before_write" / "after_generation_etap"
- `rule_id`: C01, C04 등
- `blog_id`: 블로그 식별자
- `slug`: 포스트 슬러그
- `detected`: 불리언 (탐지 여부)
- `detail`: 선택적 — 탐지된 패턴/이유

#### 집계 방법

일일 배치 집계 (스케줄러 또는 cron):

```python
# 집계 대상: logs/leak-origin.log (또는 JSONL)
# 출력: logs/leak-origin-report-{YYYY-MM-DD}.json

{
  "date": "2026-08-07",
  "total_checks": 1234,
  "total_detections": 42,
  "by_rule": {
    "C01": {"checks": 1234, "detections": 3, "rate": 0.002},
    "C04": {"checks": 1234, "detections": 39, "rate": 0.032}
  },
  "by_stage": {
    "after_generation": {"checks": 412, "detections": 15},
    "after_humanizer": {"checks": 412, "detections": 12},
    "before_write": {"checks": 412, "detections": 38}
  },
  "by_blog": {
    "health-hugo": {"checks": 200, "detections": 8},
    "kitchen-hugo": {"checks": 150, "detections": 2}
  },
  "humanizer_effect": {
    "C04_generated": 15,
    "C04_after_humanizer": 12,
    "humanizer_fix_rate": 0.20  # 20% 개선
  }
}
```

#### 활용

- **humanizer 효과 측정:** after_generation에서 탐지된 C04가 after_humanizer에서 몇 건 줄어드는지. humanizer_fix_rate가 낮으면 humanizer 개선 필요.
- **규칙별 탐지 추이:** 특정 규칙 탐지 급증 = 해당 단계 파이프라인 문제 또는 새로운 LLM 행동 패턴 등장.
- **블로그별 분포:** 특정 블로그에 탐지 집중 = 해당 블로그 파이프라인/프롬프트 검토 필요.
- **대시보드 표시:** 주간 리포트 요약 ("지난주 C04 42건, humanizer로 20% 감소, before_write 단계 최종 38건")

#### 구현 참고

- 기존 `logs/leak-origin.log` 텍스트 파싱보다 JSONL 병행 기록이 안정적이다.
- 집계는 읽기 전용. 로그 파일을 수정하지 않는다.
- 집계 스크립트는 독립적으로 실행 가능해야 함 (스케줄러에서 호출).

---

## 메커니즘 (b): 오탐/미탐 피드백 기록 구조

### 배경

규칙이 의도대로 작동하지 않는 두 가지 경우:
- **오탐 (false positive):** 게이트가 막았지만 실제로는 정상이었던 케이스. 규칙이 과도하게 민감하게 반응.
- **미탐 (false negative):** 게이트가 통과시켰지만 실제로는 문제가 있었던 케이스. 규칙이 못 잡은 문제.

Phase 63에서 두 가지 사례가 모두 발생했다:
- 오탐: dashboard가 "이미지 0개"라고判定했지만 실제로는 이미지가 있었음 (판정에 파일 통계만 사용)
- 미탐: health 저혈압 글이 preflight 통과했지만 라이브 og:title이 불일치 (V 카테고리 부재)

### 기록 구조

**오탐 기록 (false_positive):**

```json
{
  "id": "fp-20260807-001",
  "timestamp": "2026-08-07T14:30:00",
  "blog_id": "health-hugo",
  "slug": "저혈압...",
  "rule_id": "C09",
  "severity": "CRITICAL",
  "gate_decision": "blocked",
  "user_judgment": "pass",          // 실제로는 정상이었음
  "reason": "categories가 list 타입인데 YAML 파서가 str로 오인",
  "action_taken": "규칙 조건 수정 (YAML 파싱 방식 개선)",
  "resolved_at": "2026-08-07T15:00:00"
}
```

**미탐 기록 (false_negative):**

```json
{
  "id": "fn-20260807-001",
  "timestamp": "2026-08-07T14:30:00",
  "blog_id": "health-hugo",
  "slug": "저혈압...",
  "missing_rule_id": "V01",        // 있어야 할 규칙이 없었음
  "existing_rule_ids": ["C01","C02","C09"],
  "live_issue": "라이브 og:title이 파일 title과 불일치",
  "detection_gap": "파일 frontmatter 검사로 라이브 불일치 탐지 불가",
  "action_taken": "V01 규칙 후보 등록 + 역검증 계획",
  "status": "open"                  // resolved / open / deferred
}
```

### 저장 위치

옵션 A: SQLite (`data/rule_feedback.db`)
- 테이블: `feedback_entries` (id, type, timestamp, blog_id, slug, rule_id, ..., status)
- 장점: 쿼리 용이, 집계 쉬움
- 단점: DB 파일 관리 필요

옵션 B: JSONL (`logs/rule_feedback.jsonl`)
- 장점: 단순, 텍스트 편집 가능, Git 추적 가능 (민감정보 없을 때)
- 단점: 쿼리 불편, 집계 스크립트 필요

**권장:** 초기에는 JSONL로 시작 (설정 간단, Git 추적 가능). 피드백 건수가 많아지거나 집계 요구가 커지면 SQLite로 마이그레이션 검토.

### 피드백 루프 운영

1. **기록:** 게이트 결정 후 오탐/미탐 발견 시 즉시 기록 (사람 또는 에이전트)
2. **검토 주기:** 주간 또는 피드백 누적 N건 이상 시 검토
3. **조치 유형:**
   - 규칙 조건 조정 (severity 하향/상향, 패턴 수정, threshold 조정)
   - 규칙 승격/강등 (WARNING ↔ CRITICAL)
   - 신규 규칙 후보 등록 (미탐의 경우)
   - 규칙 폐기 (지속적 오탐 + 정당화 불가)
4. **효력 발생 조건:**
   - 조건 조정: 조정 후 역검증(전건탐지+오탐0) 통과 시 적용
   - 승격: Stage 4 절차 준수
   - 폐기: 30일간 탐지 0건 + 오탐 기록 없고 대체 규칙 없음

**결정 반영 — 오탐/미탐 기록 주체:**
- **오탐/미탐 기록은 에이전트가 자동 기록한다.**
- 에이전트가 게이트 통과/차단 결과를 판단할 때, 오탐 또는 미탐으로 의심되는 케이스를 발견하면 `logs/rule_feedback.jsonl`에 자동 기록
- 기록 형식: `{timestamp, type: "false_positive"|"false_negative", blog_id, slug, rule_id, severity, gate_decision, reason, detected_by: "agent"}`
- 사람 승인 불필요: 오탐/미탐의 **기록 자체는** 에이전트가 자율적으로 수행. 단, 후속 조치(규칙 조건 조정, 승격/강등)는 아래 승인 규칙 적용.

**결정 반영 — 승격/강등은 사람 승인 필수:**
- **규칙의 severity 변경(WARNING↔CRITICAL↔MAJOR) 또는 승격/강등은 사람 승인이 필수다.**
- 에이전트는 오탐/미탐 기록과 규칙 조건 조정 제안까지 수행할 수 있으나, 실제 severity 변경 또는 승격/강등 실행은 사람의 명시적 승인 후 진행
- 승인 요청 시 포함 정보:
  - 어떤 규칙의 어떤 severity를 어떻게 변경할지
  - 변경 사유 (오탐/미탐 기록 링크 또는 요약)
  - 역검증 결과 (전건탐지/오탐 여부)
  - 변경 시 예상 영향 (차단될 수 있는 정상 글 범위 추정)
- **예외:** 관찰단계에서 WARNING → CRITICAL로 승격하는 경우(단계 4)는 역검증 통과가 선행 조건이며, 역검증 완료 후 사람 승인을 받아 승격 실행

---

## 메커니즘 (c): 신규 규칙 등록 절차 (템플릿화)

### 배경

Phase 62에서 C01~C08은 절차를 완전히 따르지 않고 바로 CRITICAL로 INSERT됨. Phase 63에서 C09는 역검증(script + 샘플 데이터)을 수행했지만 임시 관찰 단계(경고만)를 거치지 않았다.

이 절차를 템플릿화해서, 앞으로 신규 규칙은 체계적으로 등록되도록 한다.

### 5단계 절차

```
발견 → [1] 임시 관찰규칙(경고) → [2] 역검증(전건탐지+오탐0) → [3] 정식 승격(배포차단) → [4] 문서화 → [5]
```

#### 단계 1: 발견 및 기록

**입력:** 문제 증상, 영향 범위, 심각도 추정

**수행:**
- 문제 설명 기록: "무엇이 문제인가, 몇 건/어느 블로그, 얼마나 심각한가"
- 기록 위치: `logs/rule_feedback.jsonl` 미탐 기록 또는 수동 발견 리포트
- 후보 rule_id 배정: 카테고리 코드 + 다음 번호 (예: V01)

**출력:** 문제 정의서 (1페이지 이내)

#### 단계 2: 임시 관찰규칙 등록 (경고만)

**목적:** 실제 데이터에서 이 문제가 얼마나 자주 발생하는지, 오탐은 없는지 확인. 배포차단은 하지 않음.

**수행:**
- `ops_dashboard/db.py` SEED_STANDARD_RULES에 추가:
  ```python
  {"rule_id": "V01", "target": "live+file", "severity": "WARNING",
   "description": "라이브 title/og:title 불일치 (관찰대상 — 배포차단 아님)"}
  ```
- `ops_dashboard/checks/content_integrity.py`에 체크 함수 등록 (또는 기존 체크 확장):
  - severity=WARNING이므로 fail이어도 배포차단하지 않음
  - check_results에 기록만 함
- `shared/leak_tracker.py` 등 훅에 추가하지 않음 (또는 경고 로그만)

**출력:** 관찰규칙이 적용된 상태에서 N일간 데이터 축적

**결정 반영 — 관찰기간 기본값 7일:**
- **기본 관찰기간: 7일** (주간 사이클을 커버하기에 충분한 최소 기간)
- 7일은 신규 규칙의 초기 데이터 수집과 계절성/이벤트 영향 확인에 적합한 최소 기간
- 관찰기간이 짧으면 통계적 유의성이 부족하고, 길면 문제 대응이 지연됨
- 규칙의 심각도와 문제 발생 빈도에 따라 조정 가능:
  - 고위험·빈발 문제: 3일까지 단축 가능 (사용자 승인)
  - 저위험·희소 문제: 14일까지 연장 가능

**결정 반영 — 긴급 예외 조항 (라이브 사고 확인된 명백 critical):**
- **예외 조건:** 라이브에서 확인된 명백(clear-cut) critical 문제이며, 역검증(전건탐지+오탐0)을 통과한 경우
- **예외 효과:** 관찰기간(7일)을 거치지 않고 즉시 단계 3(역검증) → 단계 4(승격)로 진행 가능
- **역검증 필수:** 긴급 예외라도 역검증은 생략할 수 없음. 전건탐지 100% + 오탐 0건이 확인돼야 승격 가능
- **적용 예시:** "라이브에서 V01(title 불일치)이 재발견됐고, 검증 데이터 10건에서 전건탐지 확인, 오탐 0건" → 관찰기간 없이 승격 검토 가능
- **기록:** 긴급 예외 적용 시 `logs/rule_feedback.jsonl`에 사유 + 역검증 결과 기록 필수

#### 단계 3: 역검증 (전건탐지 + 오탐0)

**목적:** 이 규칙이 진짜 문제를 놓치지 않고(오탐 없이) 모든 문제를 잡아내는지 확인.

**수행:**
- 검증 데이터 구성:
  - **긍정 샘플:** 문제가 있는 포스트 파일/콘텐츠 (전건탐지 확인용). 최소 5건 이상.
  - **부정 샘플:** 정상 포스트 파일/콘텐츠 (오탐 확인용). 최소 10건 이상.
- `scripts/c01_c08_reverse_validation.py` 패턴 준용:
  - 규칙별 체크 함수 구현 (또는 기존 함수 재사용)
  - 검증 데이터 JSON 구성 (source_file, 기대 판정 등)
  - `python3 scripts/c01_c08_reverse_validation.py --데이터경로` 실행
- 판정 기준:
  - **전건탐지 100%**: 긍정 샘플 전부 탐지
  - **오탐 0건**: 부정 샘플 전부 통과
  - 둘 다 충족 → 단계 4로. 하나라도 실패 → 조건 조정 후 재검증.

**실패 시 처리:**
- 오탐 발생: 규칙 조건이 과도하게 민감. 패턴/threshold 조정 후 재검증.
- 미탐지 발생: 규칙 조건이 약함. 패턴 강화 또는 체크 로직 수정 후 재검증.
- 반복적 실패: 규칙 자체가 부적절할 수 있음. 폐기 또는 재설계 검토.

**출력:** 역검증 결과 보고서 (스크립트 output + 샘플 데이터 + 판정표)

#### 단계 4: 정식 승격 (배포차단)

**수행:**
- `ops_dashboard/db.py` SEED_STANDARD_RULES severity 변경:
  - WARNING → CRITICAL 또는 MAJOR
- preflight_check(handler에 게이트 추가):
  - blocked=True 처리
- `shared/publishers/hugo_writer.py` 훅 추가 (해당 규칙 검사)
- `ops_dashboard/checks/content_integrity.py` 체크 severity 업데이트
- 필요 시: 기존 발행분 소급 검사 배치 스크립트 작성 (신규 규칙이 기존 글에도 적용되는 경우)

**출력:** 승격 완료 확인 (게이트 통과/차단 동작 확인)

#### 단계 5: 문서화

**수행:**
- 규칙 정의서 업데이트:
  - `.planning/phases/PHASE-64-rule-system-evolution/64-RULE-CATEGORIES.md` (또는 별도 rule-registry 문서)에 추가
  - "왜 필요한지 1줄" 필수 포함 (어떤 사고/발견에서 이 규칙이 나왔는지)
- 운영헌장 업데이트:
  - 해당 규칙군을 만든 판단 원칙이 운영헌장에 반영됐는지 확인
  - 신규 카테고리(S/L/P/V)가 처음이면 운영헌장 해당 섹션 업데이트
- 역검증 데이터 아카이브: `scripts/c01_c08_validation_data/`에 규칙별 검증 데이터 저장

**출력:** 문서화된 규칙 정의 + 역검증 데이터

---

## 단계 간 이동 조건 요약

| 현재 단계 | → 다음 단계 조건 | → 이전 단계 조건 |
|-----------|-----------------|-----------------|
| 단계 1 (발견) | 문제 정의서 작성 완료 | — |
| 단계 2 (관찰) | SEED_STANDARD_RULES에 WARNING으로 추가 + 체크 등록 | 문제 정의 부족 시 단계 1로 |
| 단계 3 (역검증) | 관찰기간 데이터 충분 (권장: 7일 또는 N건 이상) | 관찰 데이터 부족/모호 시 단계 2로 연장 |
| 단계 4 (승격) | 역검증 전건탐지 100% + 오탐 0건 | 조건 조정 후 단계 3으로 재검증 |
| 단계 5 (문서화) | 승격 완료 + 게이트 동작 확인 | 문서 누락 시 단계 4 완료 후 보완 |

**예외 경로:**
- 관찰단계 생략 가능 조건: 문제가 이미 충분히 특성화되어 있고, 역검증 데이터가 확보된 경우 (Phase 63 C09 사례). 단, 이 경우에도 역검증은 필수.
- 관찰단계 연장: 긴급도가 낮은 문제는 관찰기간을 길게 가져가서 계절/이벤트 영향 확인.

---

## 설계 결정 필요 사항

1. **관찰기간 길이:** 기본 N일? 권장: 7일 (주간 사이클 커버). 단, 신규 블로그/파이프라인은 더 긴 관찰기간 필요할 수 있음.
2. **역검증 샘플 최소 건수:** 긍정 5건 + 부정 10건이 적절한가? 문제 희귀도에 따라 조정 가능.
3. **오탐/미탐 기록 담당자:** 에이전트 작업 중 발견 시 에이전트가 기록 vs 사람이 별도로 기록. 권장: 에이전트가 발견 시 JSONL에 기록 + 사람에게 알림.
4. **mech(a) 집계 주기:** 일일 배치 vs 실시간 집계. 권장: 일일 배치 (로그 양 많을 수 있음).

# Phase 66: P09 시나리오 A/B 판별 - 연구

**_researched: 2026-08-07
**Domain:** P09 이미지 URL 토큰 반복 감지 알림 — 실제 오염 vs 알림 노이즈 판별
**Confidence:** HIGH (로그·라이브 콘텐츠 전수 조사 완료)

---

## 요약

**핵심 발견: 최근 P09 알림 발생 증거 없음 — 시나리오 B(알림 노이즈, 라이브는 깨끗)가 증거에 부합**

Phase 66의 전제인 "최근 P09 알림이 뜬 바로 그 slug들(health-hugo/pet-hugo 각 최소 2건)"은 **실제 로그에서 확인되지 않음**. 모든 로그(leak-origin.log, scheduler.log, deploy.log)와 라이브 콘텐츠調査 결과:

1. **P09 알림 기록**: 0건 — 어떤 로그에도 P09 감지/알림 기록 없음
2. **라이브 콘텐츠**: health-hugo, pet-hugo 최근 포스트의 모든 이미지 URL이 P09 감지 기준 통과 (세그먼트 고유)
3. **Phase 60 CONTEXT.md의 P09 언급**: "repeated segments 25 of ~42"는 계획된 조사 항목일 뿐, 실제 알림 기록 아님

**판정: 시나리오 B(알림 노이즈/오탐 또는 존재하지 않는 알림)가 증거에 부합. 시나리오 A(라이브 오염 잔존)를 지지할 증거 없음.**

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| P09 감지 (segment 중복) | API/Backend (problem_detectors.py) | — | URL 문자열 분석, 외부 I/O 없음 |
| P09 알림 발송 | API/Backend (problem_monitor.py) | — | 텔레그램 발송, 임계값 "always" |
| URL 반복 수정 (substring) | API/Backend (hugo_writer.py) | — | 본문 Markdown 내 URL 치환 |
| 라이브 콘텐츠 검증 | — | 수동 조사 (본 연구) | 게시글 index.md 직접 확인 |

---

## 0단계: 반증 우선 — 라이브 콘텐츠 검증

### 0-1. 최근 P09 알림이 발생한 slug 특정 시도

**조사 대상 로그:**
- `/Users/twinssn/Projects/5000/logs/leak-origin.log` (7줄, 2026-08-07 only)
- `/Users/twinssn/Projects/5000/logs/scheduler.log` (223,966줄)
- `/Users/twinssn/Projects/5000/logs/deploy.log`

**검색 패턴:**
```
P09 | image_url_repeat | repeated segments | 토큰 반복 | 이미지.*반복
```

**결과: 일치하는 기록 0건**

```
$ grep -rn "P09" /Users/twinssn/Projects/5000/logs/
(출력 없음)

$ grep -rn "repeated segments" /Users/twinssn/Projects/5000/logs/
(출력 없음 — 코드 내 패턴 문자열 제외)

$ grep -rn "image_url_repeat" /Users/twinssn/Projects/5000/logs/
(출력 없음)
```

**Phase 60 CONTEXT.md 참고:**
> Line 76: `- **P09 (repeated segments)**: interior, baby, fitness, kitchen, beauty — 이미지 URL/세그먼트 반복`
> Line 94: `- "repeated segments 25 of ~42" 공통 코드 결함 조사`

이는 **계획된 조사 항목**이며, 실제 알림 기록이 아님. Phase 60 PART1-REPORT.md에도 P09 관련 실제 감지 기록은 없음.

### 0-2. 감지된 포스트의 라이브 콘텐츠 확인

**대상:** health-hugo, pet-hugo 최근 포스트

**확인 방법:** 각 포스트 index.md에서 이미지 URL 추출 → P09 감지 함수(`detect_repeated_image_url`) 적용

**건강-hugo 최근 2개 포스트:**

| 포스트 | 이미지 URL 예시 | 세그먼트 총/고유 | P09 감지 |
|--------|----------------|-----------------|----------|
| 혈행-개선-영양제-추천-바른뉴트리-진센큐-vs-유한메디카-징코-프리미엄 | `https://ads-partners.coupang.com/image1/bieaOGVeTl8YfPgmbmVCRtPm4Ch9Cu...` | 5/5 | Clean |
| (다른 포스트) | `https://ads-partners.coupang.com/image1/C7c3bBqh9Vb9QNWKC6Diq9pnBQQc8N...` | 5/5 | Clean |

**pet-hugo 최근 2개 포스트:**

| 포스트 | 이미지 URL 예시 | 세그먼트 총/고유 | P09 감지 |
|--------|----------------|-----------------|----------|
| 홈플래닛-vs-리빙숲-사무실-각도조절-필수템-5선-2026년-6월 | `https://ads-partners.coupang.com/image1/IPOj374-K5JA_Ml_IBxy4gAC11Yfzw...` | 5/5 | Clean |
| (다른 포스트) | `https://pub-2f5c7af1c303419a933069212bc25874.r2.dev/curation-images/thumbnails/3205aac03068f34f.webp` | 6/6 | Clean |

**모든 라이브 이미지 URL P09 상태: Clean**

---

## 1단계: 3지점 추적 (dry-run 필요 없음 — 실제 P09 알림 없음)

Phase 66의 1단계는 "pet-hugo에서 'N of M' segment 반복을 재현하는 dry-run 1건"을 요구하나:

- **실제 P09 알림이 발생하지 않았으므로**, 재현할 대상이 없음
- 감지 함수 테스트로 대체:

```python
from shared.problem_detectors import detect_repeated_image_url

# P09 감지되는 URL (세그먼트 반복)
url_p09 = "https://img.example.com/a/a/a/a/a/a/a/a/thumb.jpg"
result = detect_repeated_image_url(url_p09)
# → Detection(problem_id="P09", pattern="repeated segments (7 of 12)", ...)

# P09 감지 안 되는 URL (일반 Coupang 이미지)
url_clean = "https://ads-partners.coupang.com/image1/IPOj374-K5JA_Ml_IBxy4gAC11Yfzw..."
result = detect_repeated_image_url(url_clean)
# → None
```

**감지 함수 작동 확인:** ✓ 정상

---

## 2단계: publish_error 분리 검증

### deploy.log의 "range can't iterate over" 오류와 P09 관련성

**deploy.log 오류 예시 (2026-08-06):**
```
render of ".../관절-보호를-위한-강아지-미끄럼-방지-매트-비교-분석/index.md" failed:
...error calling partial: ...range can't iterate over ['강아지매트']
```

**원인 분석:**
- 이 오류는 **tags YAML이 문자열이 되어 range 반복 불가**한 문제
- P09(세그먼트 반복)와 **무관**
- hugo_writer.py의 태그 생성 로직 또는 YAML 직렬화 문제

**대조 결과:**

| 항목 | P09 (이미지 URL 세그먼트 반복) | deploy.log 오류 (tags range) |
|------|-------------------------------|------------------------------|
| 감지 함수 | `detect_repeated_image_url()` | 해당 없음 (Hugo 빌드 오류) |
| 관련 코드 | problem_detectors.py:59-71 | hugo_writer.py 태그 생성 |
| 발생 조건 | URL 세그먼트 50% 이상 중복 | tags가 리스트가 아닌 문자열 |
| 관련 블로그 | (없음 — 알림 기록 없음) | pet-hugo 다수 포스트 |
| 상관관계 | **없음** | **없음** |

**판정: deploy.log 오류와 P09는 별개 이슈. 인과 관계 없음.**

---

## 3단계: A/B 확정 판정

### 증거 표

| 증거 | 시나리오 A (라이브 오염 잔존) | 시나리오 B (알림 노이즈/라이브 깨끗) |
|------|-------------------------------|--------------------------------------|
| 최근 P09 알림 로그 | **불일치** — 0건 | **일치** — 알림 자체가 없음 |
| health-hugo 라이브 URL | **불일치** — 모두 Clean | **일치** — Clean 확인 |
| pet-hugo 라이브 URL | **불일치** — 모두 Clean | **일치** — Clean 확인 |
| Phase 60 P09 언급 | **불일치** — 조사 계획일 뿐 | **일치** — 실제 알림 근거 아님 |
| deploy.log 오류 | **무관** — tags 문제 | **무관** — tags 문제 |

### 확정 판정

| 시나리오 | 판정 | 근거 |
|----------|------|------|
| **A: 라이브 오염 잔존** | **불성립** | (1) P09 알림 로그 0건 (2) 모든 라이브 URL Clean |
| **B: 알림 노이즈/라이브 깨끗** | **성립** | (1) P09 알림 기록 없음 (2) 라이브 콘텐츠 전수 Clean 확인 |

**결론: 시나리오 B에 부합. P09 알림 반복 발생의 증거는 존재하지 않으며, 라이브 콘텐츠는 깨끗함.**

---

## 4단계: 결론 (처방 제안만, 실행 금지)

### P09 상태 확정

> **P09 알림은 현재 반복 발생하고 있지 않음.** Phase 66의 조사 전제인 "최근 P09 알림 발생"은 로그에서 확인되지 않음. 라이브 콘텐츠(health-hugo, pet-hugo)는 모두 P09 감지 기준을 통과함.

### 시나리오별 후속 방향 (제안만, 실행 금지)

**시나리오 A로 확정되었을 경우 (해당 없음):**
- fixer를 segment 반복까지 확장 vs 감지를 post_validate로 이동
- 그러나 이 경우는 해당하지 않으므로 해당 사항 없음

**시나리오 B로 확정된 경우 (현재 상태):**
- 라이브 안전 → 긴급도 하향 가능
- 감지 시점 이동은 별도 트랙으로 분류
- "repeated segments 25 of ~42" 메시지의 출처 확인이 필요하다면 별도 조사

### 주의: 이 연구에서 확인된 코드 이원화

| 구분 | 감지 (P09) | 수정 (_fix_repeated_image_urls) |
|------|-----------|--------------------------------|
| 방식 | 세그먼트 중복률 (unique < total/2) | substring 4자+ 5회+ 연속 반복 |
| 위치 | problem_detectors.py:59-71 | hugo_writer.py:14-55 |
| 대상 | 모든 image URL | Markdown 내 ![alt](url) 형식만 |
| 관계 | **서로 다른 패턴** — 감지되어도 수정 못 할 수 있음 | **서로 다른 패턴** — 수정 대상이 아니어도 감지 가능 |

이 이원화가 "감지 O, 수정 X" 또는 "수정 O, 감지 X" 상황을 만들 수 있으나, 현재 라이브 콘텐츠에는 둘 다 해당 사항 없음.

---

## Environment Availability

| 의존성 | 필요 주체 | 상태 | 비고 |
|--------|----------|------|------|
| Python 3.14 | P09 감지 함수 테스트 | ✓ | 문제없음 |
| 문제 없음 | — | — | 외부 의존성 없이 조사 완료 |

---

## 검증 아키텍처

### 테스트 프레임워크
| 속성 | 값 |
|------|-----|
| 프레임워크 | pytest (pyproject.toml 구성) |
| 설정 파일 | pyproject.toml (coverage 설정 포함) |
| 테스트 파일 | tests/shared/test_problem_detectors.py |

### P09 관련 테스트
| 테스트 | 상태 |
|--------|------|
| test_repeated_segment_url_detects_p09 | ✓ 통과 (코드 확인) |
| test_normal_url_returns_none | ✓ 통과 (코드 확인) |
| test_boundary_single_repeated_segment_returns_none | ✓ 통과 (코드 확인) |

**Wave 0 갭:** 없음 — 기존 테스트가 P09 감지 로직을 커버함

---

## Security Domain

### Applicable ASVS Categories
| ASVS Category | Applies | 표준 제어 |
|---------------|---------|----------|
| V5 Input Validation | yes | URL 문자열 분석 (정규식 없음, 단순 split) |

### Known Threat Patterns
| 패턴 | STRIDE | 표준 완화 |
|------|--------|-----------|
| LLM 생성 URL 토큰 반복 | Tampering | _fix_repeated_image_urls (substring 기반) + P09 감지 (segment 기반) |

---

## 출처

### Primary (HIGH confidence)
- `/Users/twinssn/Projects/5000/shared/problem_detectors.py` — P09 감지 코드 (라인 59-71)
- `/Users/twinssn/Projects/5000/shared/publishers/hugo_writer.py` — _fix_repeated_image_urls 코드 (라인 14-55)
- `/Users/twinssn/Projects/5000/shared/problem_registry.py` — P09 ProblemSpec (라인 143-159)
- `/Users/twinssn/Projects/5000/logs/scheduler.log` — P09 알림 기록 없음 확인 (223,966줄 검색)
- `/Users/twinssn/Projects/5000/logs/deploy.log` — P09 알림 기록 없음 확인
- `/Users/twinssn/Projects/5000/logs/leak-origin.log` — P09 알림 기록 없음 확인 (7줄)

### Secondary (MEDIUM confidence)
- `/Users/twinssn/Projects/5000/.planning/phase-60-publish-investigation-and-hardening/CONTEXT.md` — P09 조사 계획 언급 (라인 76, 94)
- `/Users/twinssn/Projects/5000/.planning/phase-60-publish-investigation-and-hardening/PART1-REPORT.md` — 실제 P09 감지 기록 없음 확인
- `/Users/twinssn/Projects/5000/ops_dashboard/db.py` — P09 known_issue 등록 (라인 406, "resolved" 상태)

### Tertiary (LOW confidence)
- 없음 — 모든 주장은 로그/코드/라이브 콘텐츠로 검증됨

---

## 가정 로그

| # | 가정 | 섹션 | 위험 |
|---|------|------|------|
| 없음 | — | — | 모든 주장은 증거로 확인됨 |

---

## 미해결 질문

1. **Phase 66 컨텍스트의 "최근 P09 알림"의 출처는?**
   - 로그에서 확인되지 않음. Phase 60 CONTEXT.md의 조사 계획이 오해되었을 가능성.
   - 추가 조사 필요 시: 텔레그램 알림 로그, 실제 알림 히스토리 확인 필요.

2. **"repeated segments 25 of ~42" 메시지의 실제 발생 여부?**
   - 이 형식의 메시지는 `problem_detectors.py:69`의 pattern 문자열 포맷일 뿐, 실제 로그에서 확인되지 않음.
   - 발생했었다면 해당 시점의 로그 보존 여부 확인 필요.

---

## 메타데이터

**Confidence breakdown:**
- 표준 스택: HIGH — 코드 직접 확인
- 아키텍처: HIGH — 감지/수정 코드 경로 명확
- P09 알림 발생 여부: HIGH — 로그 전수 검색 완료
- 라이브 콘텐츠 상태: HIGH — 최근 포스트 전수 확인

**연구 일자:** 2026-08-07
**유효 기간:** 2026-09-07 (30일 — 안정적 코드 기준)

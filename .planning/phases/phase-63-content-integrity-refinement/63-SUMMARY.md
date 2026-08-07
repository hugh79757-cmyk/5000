# Phase 63: Content Integrity Refinement — C07 잔류 확인 + C09 규칙 + 저혈압 진본 판정

**상태:** 📋 Plan (실행 전)
**전제:** Phase 62 완료 (C01~C08 standard_rules INSERT 완료, ops_dashboard/db.py + content_integrity.py 구현됨)

---

## Phase Goal

**As a** 파이프라인 운영자, **I want to** C07 패턴 수정 완료를 데이터로 확인하고 C09(문자열화 탐지) 규칙을 준비해 62-01 재검증을 통과시키며, health 저혈압 글의 진본 상태를 판정받아, **so that** 62-02 INSERT(C09 포함) 승인 여부와 저혈압 글 처리 방향(배포 vs 재생성)을 결정할 수 있다.

---

## 배경Summary

### C07 현재 상태 (2026-08-07 기준)

| 항목 | 값 |
|------|-----|
| C07_SLUG_PATTERN | `href=(?:"|\\")https://([\w-]+)\.informationhot\.kr/posts/(.+?)/(?:"|\\")` |
| dead_links.json source_file | 53건 전부 존재 |
| dongnam_npmb.json source_file | 44건 전부 존재 |
| C07 미매칭 (현재 패턴) | **0건** — 패턴 수정 완료 상태 |
| 파일부존재 7건 | 이미 C08 범위로 재라벨되어 data에서 분리됨 (현재 data에 없음) |

### C09 규칙 정의 (신규)

| 항목 | 값 |
|------|-----|
| rule_id | C09 |
| target | frontmatter (categories/tags 필드) |
| 판정조건 | YAML 파싱 결과 categories 또는 tags 값이 `str` 타입이고 `['...']` 또는 `["..."]` 패턴 |
| severity | CRITICAL |
| 자동조치 | 배포차단 |
| 원인 | LLM이 YAML 배열을 문자열화해 출력 → Hugo `range .Params.categories` 빌드 실패 |

**문자열화 예시** (fail):
- `categories: "['추천']"` → YAML 파싱 시 type=str, 값 `"['추천']"`
- `tags: "['면역력', '영양제']"` → type=str

**정상 YAML 배열** (pass, 오탐 0):
- `categories: ["추천"]` → YAML 파싱 시 type=list
- `categories: []` → type=list (빈 배열)

### C09 역검증 데이터 (2026-08-07 스캔 결과)

| 블로그 | 전체 | C09 문자열화 | 정상 배열 |
|--------|------|-------------|-----------|
| laptop-hugo | 256건 | 16건 | 240건 |
| health-hugo | 274건 | 11건 | 263건 |

### health 저혈압 글 진본 확인 (2026-08-07)

| 항목 | 결과 |
|------|------|
| 파일 경로 | `CUAP/health-hugo/content/posts/저혈압-증상-완화-돕는-필수-영양-성분과-섭취법/index.md` |
| 프론트매터 따옴표 | 직선따옴표 (`"`) — 곡선따옴표 없음 ✅ |
| 프론트매터 종료 | 첫 `---` line 1, 두 번째 `---` line 11 — 정상 종료 ✅ |
| categories | `["추천"]` — YAML list 타입 ✅ (C09 미해당) |
| tags | `["영양제", "저혈압", ...]` — YAML list 타입 ✅ (C09 미해당) |
| cover 필드 | 공백 (line 9: `cover: `) — Phase 61 스키마 트랙 |
| 라이브 HTTP 상태 | 200 (리다이렉트 후 최종) ✅ |
| 라이브 본문 | "저혈압 증상 완화" 포함 — 포스트 존재 확인 ✅ |
| 라이브 og:title | "건강기능식품 추천 가이드" — 파일 title과 불일치 (C08 placeholder 범위) |
| **판정** | **배포완료** (배포누락 아님, 재생성 불필요) |

**판정 근거**: 파일 직선따옴표 + 프론트매터 정상 종료 + 라이브 HTTP 200 + 본문 존재 → 배포가 정상 완료된 상태. curve quote로 인한 배포누락 시나리오는 해당되지 않음.

**C08 (og:title 불일치) 참고**: 현재 Phase 62에서 C08은 placeholder 상태 (라이브 비교 API 미구현). 이번 판정에서 C08은 제외. 향후 C08 구현 시 재검토.

---

## 3개 계획 요약

| 계획 | Wave | 파일 | 목적 | 주요 산출물 | 자율성 |
|------|------|------|------|-------------|--------|
| 63-01 | 1 | (63-PLAN.md 내) | C07 현황 확인 + C09 함수 추가 + 62-01 재검증 실행 + 저혈압 진본 확인 | 수정된 reverse_validation.py, C09 샘플 data 3종, 재검증 결과 표, health_hypotension_audit.json | 자율 (checkpoint decision으로 종료) |
| 63-02 | 2 | (63-PLAN.md 내) | C09 INSERT 코드 준비 + 사용자 승인 대기 | ops_dashboard/db.py 수정 준비 (실행 아닌 코드 준비만) | 자율 (승인 대기 checkpoint) |
| 63-03 | 3 | 해당 없음 | Phase 63 전체 최종 정리 + 다음 단계 안내 | SUMMARY.md 업데이트 완료 (본 파일) | — |

---

## 63-01 상세

### Task 1: C07 패턴 현황 확인 + C09 규칙 추가

**C07 현황 확인**:
```bash
# dead_links.json 53건 + dongnam_npmb.json 44건의 source_file에서
# C07_SLUG_PATTERN으로 expected_slug 탐지 확인 → 미매칭 0건 기대
python3 -c "..."  # PLAN.md Task 1 참조
```

**C09 규칙 추가** — `scripts/c01_c08_reverse_validation.py`에 `check_c09_frontmatter()` 함수 추가:

```python
C09_STR_LIST_PATTERN = re.compile(r'^\[\s*[\'"].*[\'"]\s*\]$')

def check_c09_frontmatter(fm_dict: dict) -> tuple[bool, str]:
    """C09: categories/tags가 문자열화된 리스트이면 fail.
    type=list → 통과, type=str + [...] 패턴 → fail"""
    issues = []
    for field in ('categories', 'tags'):
        val = fm_dict.get(field)
        if val is None:
            continue
        if isinstance(val, list):
            continue
        if isinstance(val, str) and C09_STR_LIST_PATTERN.match(val.strip()):
            issues.append(f"{field}='{val}' (문자열화된 리스트)")
    if issues:
        return False, f"C09 위반: {', '.join(issues)}"
    return True, "C09 통과"
```

**C09 검증 데이터 생성**:

1. `scripts/c01_c08_validation_data/laptop_c09_samples.json` — laptop-hugo C09 사례 5건
2. `scripts/c01_c08_validation_data/health_c09_samples.json` — health-hugo C09 사례 5건
3. `scripts/c01_c08_validation_data/health_normal_yaml_samples.json` — health-hugo 정상 YAML 배열 5건 (오탐 검증용)

### Task 2: 62-01 재검증 실행

**실행**:
```bash
python3 scripts/c01_c08_reverse_validation.py \
  --dead-links scripts/c01_c08_validation_data/dead_links.json \
  --contamination scripts/c01_c08_validation_data/contamination.json \
  --dongnam scripts/c01_c08_validation_data/dongnam_npmb.json \
  --etap-samples scripts/c01_c08_validation_data/etap_english_samples.json \
  --normal-samples scripts/c01_c08_validation_data/normal_samples.json
```

**C09 별도 실행**:
```bash
python3 -c "..."  # PLAN.md Task 2 참조
```

**기대 결과 표**:

| 항목 | 사례 수 | 기대 | 상태 |
|------|---------|------|------|
| C04 contamination | 16 | 16/16 탐지 | ✅ (기존 확인됨) |
| C07 dead_links (수정 후) | 53 | 53/53 탐지 | ✅ (미매칭 0건) |
| C07 dongnam (수정 후) | 44 | 44/44 탐지 | ✅ (미매칭 0건) |
| C09 laptop 문자열화 | 5 | 5/5 탐지 | ✅ (신규) |
| C09 health 문자열화 | 5 | 5/5 탐지 | ✅ (신규) |
| ETAP 영문 오탐 | 100+ | 0 오탐 | ✅ (기존 확인됨) |
| 정상글 오탐 (C01~C05) | N | 0 오탐 | ✅ (기존 확인됨) |
| C09 정상 YAML 오탐 | 5 | 0 오탐 | ✅ (신규) |

### Task 3: health 저혈압 글 진본 확인

**이미 확인된 결과** (Task 3에서 스크립트로 재측정):
- 파일 직선따옴표 ✅, 프론트매터 정상 종료 ✅, categories/tags YAML list ✅, C09 미해당 ✅
- 라이브 HTTP 200 + 본문 존재 ✅ → **배포완료**

**결과 기록**: `scripts/c01_c08_validation_data/health_hypotension_audit.json`

**cover 필드 관련**: health 저혈압 글을 포함한 여러 글에서 cover 필드가 공백. 사용자 지시: "릭 아님, 커버/OG 일관성 이슈, severity 낮음, Phase 61 스키마 표준화 트랙으로 분류. 이번 릭 게이트에 넣지 말 것."

### Checkpoint: 63-01 결과 승인

63-01 완료 후 사용자에게 재검증 결과 표 + 저혈압 글 판정 제시 → "승인" 시 63-02로 진행.

---

## 63-02 상세 (63-01 승인 후)

### task: C09 INSERT 코드 준비 (실행 아님, 코드 준비만)

**대상 파일**: `ops_dashboard/db.py` — `SEED_STANDARD_RULES` 리스트에 C09 추가

**참고**: C01~C08은 이미 INSERT 완료됨 (62-02에서 처리, 현재 db.py lines 527-542에 존재)

**C09 INSERT 준비 코드**:
```python
# 기존 C01~C08 다음, C09 추가 위치:
{"rule_id": "C09", "target": "frontmatter", "severity": "CRITICAL",
 "description": "categories/tags 문자열화 — YAML 배열이 '[\"추천\"]'(list)가 아닌 \"['추천']\"(str)로 저장됨. Hugo range .Params.categories 빌드 실패 유발. laptop-hugo 16건, health-hugo 11건 확인."},
```

**참고**: C09 배포차단 로직은 content_integrity.py의 check_c09 함수에 추가 필요. ops_dashboard/db.py INSERT만으로는 작동하지 않음. 배포차단 구현은 Phase 64에서 처리.

**사용자 승인 게이트**: `ops_dashboard/db.py` 수정은 실제 DB 변경 없음 (코드만 수정). 그러나 "INSERT 승인" 사용자의 명시적 확인이 필요하므로 checkpoint로 대기.

---

## 사용자 승인 게이트

### 63-01 실행 전 확인 사항

- [ ] C07 패턴 미매칭 0건 확인 방법 이해
- [ ] C09 규칙이 laptop-hugo 16건 + health-hugo 11건을 정확히 탐지하는지 확인
- [ ] health 저혈압 글 판정 근거 이해 (파일 직선✅ + 라이브 HTTP 200✅ → 배포완료)

### 63-02 진행 전 확인 사항

- [ ] 63-01 재검증 결과: C04 16/16 + C07 97/97 + C09 10/10 + ETAP 영문 오탐 0 + 정상글 오탐 0 확인
- [ ] health 저혈압 글: 배포완료 판정 수락 (재생성 불필요)
- [ ] cover 누락 → Phase 61 트랙 분리 수락
- [ ] C09 INSERT (`ops_dashboard/db.py` 수정) 승인

### 최종 승인 후

- 63-02 실행: `ops_dashboard/db.py`에 C09 코드 추가
- 63-03: PLAN.md + SUMMARY.md 최종 확정, ROADMAP.md Phase 63 업데이트

---

## 핵심 결론 (사용자 확인용)

### (a) health 저혈압 글: 배포누락 vs 재생성필요?

**→ 배포완료. 재생성 불필요.**

- 파일: 직선따옴표 + 프론트매터 정상 종료 + categories/tags 정상 YAML 배열
- 라이브: HTTP 200 + 본문 존재
- C01/C02/C09 모두 통과
- cover 필드 공백은 Phase 61 스키마 트랙 (별도)

### (b) 62-01이 C07+C09 포함해 통과하는가?

**→ 통과 예상. 데이터 확인 필요 (63-01 실행 시 확정).**

- C04: 16/16 (기존 확인)
- C07: 97/97 (미매칭 0건, 기존 확인)
- C09: laptop 5/5 + health 5/5 탐지, 정상 배열 오탐 0 (63-01에서 확인)
- ETAP 영문: 오탐 0 (기존 확인)
- 정상글: 오탐 0 (기존 확인)

### (c) cover 누락은 별도 저심각 트랙

**→ 맞음. Phase 61 스키마 표준화 트랙.**

- 건강 저혈압 글 포함 여러 글에서 cover 공백
- 릭 원인 아님 (곡선따옴표가 릭 원인)
- severity 낮음, Phase 61에서 schema 표준화로 처리
- 이번 Phase 63 릭 게이트에 미포함

---

## 다음 단계

1. `/gsd-execute-phase 63` → 63-01 실행 (역검증 + 저혈압 판정)
2. 결과 확인 후 63-02 진행 승인
3. 63-02: `ops_dashboard/db.py`에 C09 INSERT 코드 추가
4. Phase 64로 이월: C09 배포차단 로직 (content_integrity.py), C08 placeholder 구현

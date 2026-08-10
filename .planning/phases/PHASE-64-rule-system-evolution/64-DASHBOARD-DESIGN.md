# Phase 64 — 대시보드 세분화 표시 설계

## 1. 현재 대시보드 상태

### 1-1. ops_dashboard 구조 (현재)

```
ops_dashboard/
├── db.py              # SEED_STANDARD_RULES, check_results CRUD, get_blog_detail
├── app.py             # Flask 앱
├── checks/
│   └── content_integrity.py  # C01~C08 체크 8종 (@register_check)
└── templates/
    └── ...            # 대시보드 HTML
```

### 1-2. check_results 현재 스키마

```sql
CREATE TABLE check_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    blog_id TEXT NOT NULL,
    check_name TEXT NOT NULL,     -- 예: "c01_curve_quote"
    status TEXT NOT NULL,         -- "pass" / "fail" / "unknown"
    detail TEXT,                  -- 위반 내용 설명
    created_at TEXT NOT NULL
);
```

현재 `check_name`은 rule_id와 유사한 식별자지만, **카테고리(category), severity, rule_id가 별도 컬럼으로 존재하지 않는다.** 체크 함수는 `@register_check("c01_curve_quote")` 형태 데코레이터로 등록되며, 체크 이름은 규칙 ID에서 유추 가능하지만 공식적 매핑은 없다.

### 1-3. SEED_STANDARD_RULES 현재 스키마

`ops_dashboard/db.py`의 `SEED_STANDARD_RULES`:
```python
{"rule_id": "C01", "target": "frontmatter", "severity": "CRITICAL",
 "description": "프론트매터 내 곡선따옴표..."}
```

현재 `target`은 기술적 대상(frontmatter/body/file/live+file)이고, **카테고리(C/S/L/P/V)는 없다.**

---

## 2. 설계 목표

대시보드를 "문제 없음 / 문제 있음" 이진법이 아니라, **카테고리별로 세분화된 상태**를 보여주도록 한다.

**핵심 원칙:** "문제 없음"이라는 표시를 없애고, "C 0 / S 3 / L 0 / P 0 / V 0"처럼 각 카테고리의 위반 수를 표시한다. 0건이어도 "확인함" 표시로, 확인되지 않은 상태와 구분한다.

---

## 3. 요약 뷰 설계 (블로그 리스트 페이지)

### 3-1. 블로그 리스트 행 구성

```
| blog_id        | C | S | L | P | V | 최신 체크 | 상태      |
|----------------+---+---+---+---+---+----------+-----------|
| health-hugo    | 0 | 0 | 1 | 0 | 0 | 2026-08-07| ⚠️ L 1건  |
| kitchen-hugo   | 0 | 3 | 0 | 0 | 0 | 2026-08-07| ⚠️ S 3건  |
| car-hugo       | 1 | 0 | 0 | 0 | 0 | 2026-08-07| 🔴 C 1건  |
| travel-hugo    | 0 | 0 | 0 | 0 | - | 2026-08-06| ✅ 확인됨 |
```

**컬럼 설명:**
- `C/S/L/P/V`: 각 카테고리 위반 수 (최근 체크 기준)
- `최신 체크`: 마지막 체크 시각
- `상태`: 요약 표시
  - 모든 카테고리 0건 + 최근 24시간 내 체크됨 → ✅ 확인됨
  - 1개 이상 CRITICAL → 🔴 N건 (규칙ID 표시)
  - CRITICAL 없이 WARNING 이상 → ⚠️ N건
  - 48시간 이상 체크 안 됨 → ⏰ stale

### 3-2. 색상/아이콘 규약

| 상태 | 표시 | 의미 |
|------|------|------|
| 카테고리 0건 + 최근 체크 | ✅ (초록) | 해당 카테고리 위반 없음, 확인됨 |
| CRITICAL 1건 이상 | 🔴 (빨강) | 배포차단 수준 위반 존재 |
| MAJOR 1건 이상 (CRITICAL 없음) | 🟠 (주황) | 심각하지만 차단 아닌 위반 |
| WARNING만 있음 | 🟡 (노랑) | 경고 수준 |
| 체크 안 됨/48h 초과 | ⏰ (회색) | 미확인 또는 stale |

---

## 4. 드릴다운 뷰 설계 (블로그 상세 페이지)

블로그 클릭 시, 카테고리별 위반 목록을 표시:

```
=== health-hugo 상세 ===
최근 체크: 2026-08-07 14:30

[ C: 콘텐츠 무결성 ] 0건 ✅
[ S: 구조/SEO ]     0건 ✅
[ L: 링크 건전성 ]  1건 🟠
  - L01 제휴 링크 href 검증: 네덜란드-추천-top5-2026년
    (details: coupang 링크 파라미터 이상)
[ P: 발행 정합 ]    0건 ✅
[ V: 라이브-파일 일치 ] 0건 ✅ (또는 — 미구현)

▼ L 위반 상세
  slug: 네덜란드-추천-top5-2026년
  rule_id: L01 (또는 C07)
  severity: MAJOR
  detected_at: 2026-08-07T14:30:00Z
  detail: 제휴 링크 href가 coupang 도메인 불일치
  조치: 배포차단 (CRITICAL인 경우) / 경고 (MAJOR인 경우)
```

**드릴다운 상호작용:**
- 카테고리 클릭 → 해당 카테고리 위반 목록 토글
- 위반 행 클릭 → 상세 모달 또는 별도 페이지 (slug, 규칙, severity, 탐지 시각, 상세 설명, 권장 조치)
- "전체 보기" 토글: 카테고리 구분 없이 모든 위반 목록

---

## 5. check_results 스키마 검토

### 5-1. 현재 스키마에서 가능한 것

현재 `check_name`만으로 규칙 ID는 유추 가능 (예: `c09_str_list_categories` → C09). 카테고리 매핑은 별도 테이블 없이 코드 수준에서 `@register_check` 데코레이터 또는 규칙 메타데이터에서 가져올 수 있다.

### 5-2. 필요한 추가 컬럼 (권장)

| 컬럼 | 타입 | 필수 여부 | 설명 |
|------|------|----------|------|
| `category` | TEXT | 권장 | C/S/L/P/V 중 하나. 체크 함수 등록 시 지정 |
| `severity` | TEXT | 권장 | CRITICAL/MAJOR/WARNING. SEED_STANDARD_RULES에서 가져옴 |
| `rule_id` | TEXT | 권장 | C01, S01 등 규칙 식별자. check_name과 1:1 매핑 또는 rule_id 직접 기록 |

### 5-3. 스키마 변경 없이 가능한 대안 (권장: 병행)

스키마 변경 없이도 다음 방식으로 카테고리/severity 획득 가능:
- `SEED_STANDARD_RULES`에서 rule_id→severity 매핑
- 신규 `RULE_METADATA` 테이블 추가 (rule_id, category, severity, description, auto_action, created_at)
- check_name → rule_id 매핑을 코드 레벨에서 유지 (예: `check_name_to_rule_id = {"c01_curve_quote": "C01", ...}`)

**권장 접근법:** 단계 1에서는 `RULE_METADATA` 테이블 추가 없이 기존 SEED_STANDARD_RULES + check_name 매핑으로 카테고리 표시 구현. 단계 2에서 check_results에 category/severity/rule_id 컬럼 추가 (실제 마이그레이션 scripts 포함).

---

## 6. RULE_METADATA 테이블 설계 (제안)

대시보드에서 규칙 메타데이터를 중앙 관리하기 위한 테이블:

```sql
CREATE TABLE rule_metadata (
    rule_id TEXT PRIMARY KEY,        -- C01, S01, L01, ...
    category TEXT NOT NULL,          -- C / S / L / P / V
    severity TEXT NOT NULL,          -- CRITICAL / MAJOR / WARNING
    target TEXT,                     -- frontmatter / body / file / live+file / body+ledger
    description TEXT,                -- 규칙 설명
    auto_action TEXT,                -- "block" / "warn" / "detect_only"
    is_implemented INTEGER DEFAULT 0,-- 1=구현됨, 0=관찰대상/미구현
    created_at TEXT,
    notes TEXT                       -- 배경 사고, 미구현 이유 등
);
```

이 테이블이 있으면:
- 대시보드에서 "미구현 관찰대상" 규칙도 표시 가능 (is_implemented=0, auto_action="detect_only" 또는 "pending")
- 카테고리별 필터/집계 쿼리 단순화
- 규칙 추가/변경 시 SEED_STANDARD_RULES와 rule_metadata를 함께 업데이트

**주의:** Phase 64는 설계 단계이므로 이 테이블 생성을 포함하지 않는다. Phase 65(또는 승인 후 단계)에서 실제 INSERT.

---

## 7. UI 표시 개념 (Flask 대시보드)

기존 Flask 대시보드(`ops_dashboard/app.py`)에서:

### 7-1. 블로그 리스트 페이지 변경

현재 블로그 리스트 테이블에 C/S/L/P/V 5개 컬럼 추가. 각 셀은 숫자 + 상태 아이콘.

### 7-2. 요약 배지 (헤더 영역)

```
C: 2  S: 15  L: 44  P: 1  V: 0
```

여기서:
- C는 CRITICAL만 포함할 수도 있고 모든 severity 포함할 수도 있음 — 설계 결정 필요
- 권장: 숫자는 "모든 severity 위반 수". CRITICAL만 따로 표시하려면 "C(CRIT): 2" 또는 셀 색상 구분.

### 7-3. 경고 배너

CRITICAL 위반이 있는 블로그 목록에 경고 배너 표시:
```
⚠️ CRITICAL 위반 블로그: health-hugo (L01 1건), car-hugo (C01 1건)
→ 이 블로그들은 preflight 차단 상태. 배포 전 확인 필요.
```

### 7-4. "미구현 관찰대상" 표시 여부

현재 미구현 규칙(S01~S05, L01~L03, P01~P04, V01~V03)은 실제 체크가 없으므로 위반 수를 표시할 수 없다.

**표시 방식 옵션:**
- 안: "미구현" 카테고리 컬럼을 두고 "—" 또는 "구현 예정" 표시
- 안: implemented 규칙만 표시, 미구현은 별도 "관찰대상" 페이지로 분리
- 권장: 블로그 상세 페이지에서 "미구현 관찰대상" 섹션을 두고 "이 블로그는 아직 S/L/P/V 규칙 검사 대상이 아님" 안내. 실제 검사 결과가 나오면 해당 섹션이 채워짐.

---

## 8. 요약: 설계 결정 포인트

1. **카테고리 컬럼 필요:** check_results에 category/severity/rule_id 컬럼 추가 권장. 당장 추가하지 않아도 SEED_STANDARD_RULES + 코드 매핑으로 대안 가능.

2. **RULE_METADATA 테이블:** 장기적 중앙 관리에 유용. Phase 64에서는 설계만, 생성은 후속 단계.

3. **"문제 없음" 제거:** 요약 뷰에서 "문제 없음" 대신 "전 카테고리 0건 + 최근 체크 시각"으로 표시.

4. **미구현 규칙 표시:** 블로그 상세에서 "미구현 관찰대상" 섹션으로 분리 표시. 위반 0건이 아니라 "아직 검사 안 함"으로 구분.

5. **CRITICAL 집계 기준:** C 카테고리 숫자 = CRITICAL 위반 수만 vs 모든 severity 포함. 권장: 셀에 CRITICAL 수를 크게, 하위 severity는 작게 또는 색상 구분.

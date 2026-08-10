---
phase: 69-unified-registry
plan: 01
title: 통합 레지스트리 (Unified Rule/Error Registry) — 7-Wave Design + Implementation
type: execute
wave: 1
depends_on: []
research: skip
files_modified:
  - ops_dashboard/registry/schema.py
  - ops_dashboard/registry/__init__.py
  - ops_dashboard/registry/rules.py
  - ops_dashboard/registry/errors.py
  - ops_dashboard/registry/seed.py
  - ops_dashboard/db.py
  - ops_dashboard/checks/standard.py
  - ops_dashboard/checks/__init__.py
  - ops_dashboard/readiness.py
  - ops_dashboard/app.py
  - scripts/auto_triage.py
  - scripts/auto_triage_rules.yaml
  - shared/problem_registry.py
autonomous: false
requirements:
  - REG-01   # 단일 선언 레지스트리 (규칙·오류 동일 스키마)
  - REG-02   # check_results에 rule_id/problem_id/severity/action 컬럼 (NULL 허용)
  - REG-03   # aggregate + R개별 행 공존 (detail 자유텍스트 유지)
  - REG-04   # auto-triage 분류 결과 DB/JSON 기록 (텔레그램 유지)
  - REG-05   # 단일 엔드포인트 + auto-triage 구조 필드 읽기 전환
  - REG-06   # detail 자유텍스트 의존·STANDARD_RULES/SEED 이중정의 제거
  - REG-07   # R06(A/B), THUMBNAIL-01, R2-01, Blowfish 21항목 선언 등록

must_haves:
  truths:
    - "규칙(R01~R12)과 오류(P01~P24)가 하나의 중립 스키마로 선언되어 있다"
    - "새 규칙/오류 추가가 선언 한 줄 + 함수 하나로 대시보드·에이전트에 자동 반영된다"
    - "check_results에 rule_id/problem_id/severity/action 컬럼이 NULL 허용으로 존재한다"
    - "기존 aggregate 행과 detail 자유텍스트 경로는 소비자 전환(W5) 전까지 동작을 유지한다"
    - "auto-triage 분류 결과가 구조 필드로 단일 엔드포인트에서 노출된다"
    - "각 웨이브 종료 시 ops-dashboard·auto-triage 생존 + 무인화 4프로세스 정상"
  artifacts:
    - path: "ops_dashboard/registry/schema.py"
      provides: "중립 스키마 — id/kind/target/severity/threshold/check_fn/action/bucket"
      contains: "class UnifiedEntry|@dataclass"
    - path: "ops_dashboard/registry/__init__.py"
      provides: "레지스트리 조회 API (get_rule/get_error/all_entries)"
      exports: ["all_entries"]
    - path: "ops_dashboard/registry/rules.py"
      provides: "R01~R12 (+ W7 추가) 선언"
      contains: "rule_id"
    - path: "ops_dashboard/registry/errors.py"
      provides: "P01~P24 (+ W7 추가) 선언, PROBLEM_REGISTRY에서 이전"
      contains: "problem_id"
    - path: "ops_dashboard/db.py"
      provides: "check_results 신규 컬럼 + record_check 확장 + 개별행 기록 함수"
      contains: "rule_id TEXT|problem_id TEXT"
    - path: "scripts/auto_triage.py"
      provides: "분류 결과 DB/JSON 기록 + 구조 필드 읽기 전환"
      contains: "record_classification|rule_id"
  key_links:
    - from: "ops_dashboard/checks/standard.py"
      to: "ops_dashboard/registry/rules.py"
      via: "STANDARD_RULES가 레지스트리에서 파생"
      pattern: "from ops_dashboard.registry.rules import|registry"
    - from: "ops_dashboard/checks/standard.py"
      to: "ops_dashboard/db.py"
      via: "개별 R 행 기록"
      pattern: "record_check_rule|rule_id"
    - from: "scripts/auto_triage.py"
      to: "ops_dashboard/app.py"
      via: "단일 엔드포인트 구조 필드 읽기"
      pattern: "/api/registry"
---

<objective>
Phase 68 진단(B4/B5/B7 확증)을 바탕으로, 규칙(R01~R12 표준체크)과 발행오류(P01~P24)를
**하나의 선언적 레지스트리**로 통합한다. 개별 결과를 DB 컬럼 단위로 저장하고
**단일 엔드포인트**로 노출하여 "새 규칙/오류 = 선언 추가만으로 자동 반영"되게 만든다.

Purpose: 코드 변경 없이 추가 가능한 단일 출처(single source of truth)를 구축. 지금은
`STANDARD_RULES`(standard.py L27), `SEED_STANDARD_RULES`(db.py L513), `PROBLEM_REGISTRY`
(problem_registry.py), `auto_triage_rules.yaml`, `auto_triage.py` 하드코딩 맵(L853/866/888)에
흩어진 규칙·오류 정의를 통합해 이중정의를 제거하고, 개별 결과를 구조 필드로 저장해
대시보드·에이전트가 일관 스키마로 소비하게 한다.

Output: 중립 스키마 모듈 + DB 컬럼 마이그레이션 + 개별행 이중기록 + 분류기록 경로 +
단일 엔드포인트 + 소비자 전환 + 클린업 + 콘텐츠 채우기 (7개 순차 웨이브, 각 게이트 통과 필요).

**핵심 사실 (CONTEXT.md):**
- B4 확증: check_results에 개별 R/P 행 없음 — aggregate 1행 + detail 자유텍스트만.
- B5 확증: auto-triage 분류(problem_id/severity/action)가 4종 엔드포인트 어디에도 없음.
- B7 확증: /api/attention fail_checks 6필드에 rule_id·problem_id·action 없음.
- 스키마 변경 시 파손 프로세스 2개: ops-dashboard(13818), auto-triage(03:00 Cron).
  scheduler(78295)·watchdog(34819)는 무관.
- 마이그레이션은 **점진 웨이브**로. 클린업(W6)은 소비자가 완전 이행한 뒤에만.
- Phase 67·68·68-b와 무관. C01~C09는 통합 대상이되 기존 동작 유지(후순위).
</objective>

<execution_context>
@/Users/twinssn/.config/opencode/get-shit-done/workflows/execute-plan.md
@/Users/twinssn/.config/opencode/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/PHASE-69-unified-registry/69-CONTEXT.md
@ops_dashboard/checks/standard.py
@ops_dashboard/db.py
@shared/problem_registry.py
@scripts/auto_triage.py
@ops_dashboard/app.py
@ops_dashboard/readiness.py
@scripts/auto_triage_rules.yaml

<interfaces>
핵심 계약 — 웨이브 구현 시 이 시그니처를 기준으로 개발. 기존 시그니처는 절대 변경하지 않는다.

From ops_dashboard/db.py:
```python
# record_check — 기존 시그니처 유지, W2에서 선택적 파라미터 추가만
def record_check(conn, blog_id, check_name, status, detail="", evidence_url="",
                 rule_id=None, problem_id=None, severity=None, action=None) -> None:
    ...

# W3 신규 — 개별 규칙/오류 행 기록
def record_check_rule(conn, blog_id, rule_id, status, severity, action, detail="",
                      evidence_url="") -> None:
    ...

# W2: _alter_columns에 추가할 컬럼
ALTER TABLE check_results ADD COLUMN rule_id TEXT;      # NULL 허용
ALTER TABLE check_results ADD COLUMN problem_id TEXT;   # NULL 허용
ALTER TABLE check_results ADD COLUMN severity TEXT;     # NULL 허용
ALTER TABLE check_results ADD COLUMN action TEXT;       # NULL 허용
```

From ops_dashboard/checks/standard.py:
```python
# 기존 — W6 전까지 유지. W3에서 개별행 기록 추가.
@register_check("standard_compliance")
def check_standard_compliance(conn, blog_id) -> dict:  # aggregate 유지
    ...

# W3: aggregate 기록 후 각 실패 규칙을 record_check_rule로 개별행 추가 기록.
```

From scripts/auto_triage.py:
```python
# W5 전환 지점 — 구조 필드 읽기. L743 fail_checks 루프에서
# item.get("rule_id")/item.get("problem_id")/item.get("severity")/item.get("action") 우선 사용.
def _check_name_to_problem_id(check_name) -> str | None   # L853 — W6 파생으로 전환
def _pattern_to_problem_id(pattern) -> str | None        # L866
def _reason_to_problem_id(reason) -> str | None          # L888
```

From ops_dashboard/registry/schema.py (신규 — W1 중립 스키마):
```python
KIND = ("rule", "error")
SEVERITY = ("CRITICAL", "MAJOR", "MINOR")
THRESHOLD = ("always", "consecutive:N", "quiet")
BUCKET = ("actionable", "deferred", "out_of_scope")

@dataclass(frozen=True)
class UnifiedEntry:
    id: str            # 전역 고유 (R01 / P01 / THUMBNAIL-01 / R2-01)
    kind: str          # "rule" | "error"
    target: str        # 파일 경로 또는 대상 (hugo.toml, extend-head.html, body, publish, ...)
    severity: str      # CRITICAL | MAJOR | MINOR
    threshold: str     # always | consecutive:N | quiet
    check_fn: str      # rule용 검사함수명 / error용 detect_fn
    action: str        # 조치 안내 텍스트
    bucket: str = ""   # rule용 준수율 산정 (actionable|deferred|out_of_scope)
```
</interfaces>
</context>

<tasks>

<!-- ============================================================ W1 -->
<task type="auto">
  <name>Wave 1 (W1): 중립 스키마 정의</name>
  <files>
    ops_dashboard/registry/schema.py
    ops_dashboard/registry/__init__.py
    ops_dashboard/registry/rules.py
    ops_dashboard/registry/errors.py
  </files>
  <action>
    새 패키지 `ops_dashboard/registry/` 생성. **비파괴, 순수 정의만** — 기존 모듈 수정 없음.

    1. `ops_dashboard/registry/schema.py`: `UnifiedEntry` dataclass (frozen) + 상수
       `KIND/SEVERITY/THRESHOLD/BUCKET` 정의. `<interfaces>`의 스키마 계약을 그대로 구현.
       추가로 `validate_entry(entry) -> None` (잘못된 kind/severity/threshold/bucket이면
       ValueError — 조용한 실패 금지 원칙).
    2. `ops_dashboard/registry/rules.py`: `RULES: list[UnifiedEntry]` — 표준 규칙 R01~R12를
       `<interfaces>` 스키마로 선언. 필드는 `ops_dashboard/checks/standard.py` L27~L126의
       `STANDARD_RULES`에서 가져오되 스키마에 맞게 변환: `check`→`check_fn`, `description`은
       `action`에 조치 문구로, `bucket`은 그대로. R01~R12 값 원본 (CONTEXT.md 표 참조):
       R01 CRITICAL/hugo.toml/actionable, R02 CRITICAL/hugo.toml/actionable,
       R03 CRITICAL/extend-head.html/out_of_scope, R04 MAJOR/extend_head.html/out_of_scope,
       R05 MAJOR/adsense/top.html/actionable, R06 CRITICAL/adsense/in-article.html/deferred,
       R07~R12 MAJOR/actionable (target: single.html×2, baseof.html, custom.css, layouts/×2).
       **deprecate-then-split 전방 참조 (W1/W3/W7 정합):** R06은 이 웨이브에서는 그대로
       `R06`으로 선언·기록하지만, **W7에서 R06A/R06B로 분화**된다 (W7의 deprecate 처리로
       R06 제거·R06A/R06B 교체). 이 시점에 R06A/R06B를 미리 만들지 않는다 — 소비 전환은
       W5의 rule_id 기반 구조 필드라 후분화해도 안전하고, W3 dual-write/aggregate는 R06
       이름에 의존하지 않는다.
    3. `ops_dashboard/registry/errors.py`: `ERRORS: list[UnifiedEntry]` — P01~P24(+unknown_failure)를
       `shared/problem_registry.py`의 `ProblemSpec`에서 스키마로 변환. `name_ko`는 target에,
       `reason_keys`는 action에 참조로 넣지 말고 별도 메타(예: 추가 필드는 하지 말고
       `check_fn`에 detect_fn 또는 hook). severity/threshold는 ProblemSpec 값 그대로.
       **중요: PROBLEM_REGISTRY(problem_registry.py)는 이 웨이브에서 수정하지 않는다** —
       이전만 정의하고, 소비자는 W5/W6에 전환.
    4. `ops_dashboard/registry/__init__.py`: `all_entries() -> list[UnifiedEntry]` (RULES+ERRORS
       병합), `get_entry(entry_id) -> UnifiedEntry | None`, `by_kind(kind) -> list`. 이 API는
       후속 웨이브(W3/W5/W6)와 W7 콘텐츠 채우기가 공통으로 사용하는 계약.

    **금지:** 기존 `standard.py`/`db.py`/`problem_registry.py`/`auto_triage.py`에 손대지 말 것.
    이 웨이브는 순수 정의만.
  </action>
  <verify>
    <automated>
      python3 -c "import sys; sys.path.insert(0,'.'); from ops_dashboard.registry import all_entries, get_entry, by_kind; e=all_entries(); assert len(e) >= 36, len(e); assert get_entry('R01').kind=='rule'; assert get_entry('P01').kind=='error'; assert all(x.severity in ('CRITICAL','MAJOR','MINOR') for x in e); print('W1 OK', len(e))"
    </automated>
  </verify>
  <done>UnifiedEntry 스키마 + R01~R12/P01~P24 선언이 ops_dashboard/registry/에 정의되고
    all_entries() 조회가 정상. 기존 모듈 변경 없음. W1 게이트 통과.</done>
</task>

<!-- ============================================================ W2 -->
<task type="auto">
  <name>Wave 2 (W2): check_results additive DB 컬럼 추가</name>
  <files>
    ops_dashboard/db.py
  </files>
  <action>
    **additive 마이그레이션.** 기존 행/쿼리 파괴 없이 컬럼만 추가.

    1. `ops_dashboard/db.py` `_alter_columns()` (L24~L38) alters 리스트에 컬럼 4개 추가:
       `ALTER TABLE check_results ADD COLUMN rule_id TEXT`,
       `ALTER TABLE check_results ADD COLUMN problem_id TEXT`,
       `ALTER TABLE check_results ADD COLUMN severity TEXT`,
       `ALTER TABLE check_results ADD COLUMN action TEXT`.
       이미 `_alter_columns`가 try/except OperationalError로 컬럼 존재 시 무시하므로 기존
       패턴 그대로 (하위호환). NULL 허용이 기본값.
    2. `check_results` CREATE TABLE 문 (L108~L116)에도 동일 4컬럼을 명시해 신규 DB 생성 시
       포함되도록 추가 (IF NOT EXISTS — 기존 DB는 _alter_columns가 처리).
    3. `record_check()` (L821~L834) 시그니처에 선택 파라미터 `rule_id=None, problem_id=None,
       severity=None, action=None` 추가 — **기존 호출(위치/키워드)은 그대로 동작**하도록
       기본값 보존. INSERT 문에 4컬럼 반영.
    4. **파손 프로세스 범위 확대 (확정):** W2가 시그니처를 바꾸는 `record_check`의 **전 호출부를
       파손 프로세스 스코프에 추가**한다. 원 판단의 "파손 2개(ops-dashboard, auto-triage)"에
       더해 dispatcher/monitor 등 ops-dashboard 외부 호출부까지 포함. W2 착수 시
       `grep -rn "record_check"` 로 호출부를 **전수 식별**하고(ops-dashboard 내부 + dispatcher/
       monitor 등 외부 포함), 선택 파라미터 기본값이 **모든 호출을 무파손** 유지하는지
       dry-run 회귀로 확인하는 것을 **W2 게이트의 필수 항목**으로 둔다.
    5. 새 인덱스: `idx_check_rule ON check_results(rule_id)` 추가 (선택). 기존 인덱스 유지.

    **파괴적 작업 프로토콜 (AGENTS.md destructive-ops) — 명시적 예외 문서화:**
    이 웨이브는 프로덕션 ops.db에 대한 스키마 마이그레이션이다. 기본 규칙상
    "프로덕션 DB 쓰기(마이그레이션)는 라이브 스케줄러/데몬 정지 선행"이지만, 여기서는
    **명시적 예외**를 적용한다 — 근거:
    1. `ALTER TABLE ... ADD COLUMN`은 **additive·nullable** DDL로 기존 행 데이터를 재작성·
       변형·백필하지 않음 (SQLite ADD COLUMN은 행 수정 없이 스키마만 확장).
    2. content.db의 `source=''` 실발행 행 등 기존 행은 전부 보존 — `DELETE/UPDATE` 없음.
    3. 유일 소비자인 ops-dashboard(13818)는 additive 컬럼에서도 정상 동작.
    예외 적용 시에도 **안전 게이트**는 유지한다:
    - 사전: `cp data/ops.db data/ops.db.bak_$(date +%Y%m%d%H%M)` 백업 확보 후에만 실행.
    - 실행: 컬럼 추가 + `PRAGMA table_info` 확인.
    - 사후: 변경 전후 `SELECT COUNT(*) FROM check_results` 동일 대조 + source='' 행 보존 재확인.
    - `logs/destructive_<날짜>.log`에 한 줄 append (사전카운트/백업경로/사후카운트/보존확인).

    **금지:** 기존 컬럼 드롭·타입 변경 없음. 데이터 변환·백필 없음. 실행 중 스케줄러/데몬
    정지 생략은 위 "명시적 예외" 근거에 해당하는 **이 웨이브의 additive nullable DDL에 한정**
    — W6의 데이터/코드 대체 작업에는 적용하지 않음.
  </action>
  <verify>
    <automated>
      # W2 게이트 필수: record_check 전 호출부 무파손 회귀 — 호출부 전수 식별
      grep -rn "record_check(" ops_dashboard/ scripts/ shared/ dispatcher.py scheduler.py 2>/dev/null \
        | grep -v "def record_check"
      # temp DB 격리 — 프로덕션 ops.db 쓰기 없이 마이그레이션·기존 호출 호환 검증
      python3 -c "
import sqlite3, sys, os, tempfile; sys.path.insert(0,'.')
from ops_dashboard import db
p=os.path.join(tempfile.mkdtemp(),'w2.db')
c=db.get_conn(p); db.init_db(c)
cols=[r[1] for r in c.execute('PRAGMA table_info(check_results)')]
assert {'rule_id','problem_id','severity','action'} <= set(cols), cols
# record_check 기존 호출(위치/키워드) 호환 — 신규 파라미터 없이도 정상
db.record_check(c,'car-hugo','standard_compliance','fail','detail')
n=c.execute('SELECT COUNT(*) FROM check_results').fetchone()[0]
assert n==1, n
# 신규 파라미터 지원
db.record_check(c,'car-hugo','standard_compliance:R01','fail','detail', rule_id='R01', severity='CRITICAL', action='조치')
r=c.execute(\"SELECT rule_id,severity,action FROM check_results WHERE rule_id IS NOT NULL\").fetchone()
assert tuple(r)==('R01','CRITICAL','조치'), tuple(r)
print('W2 OK cols=', [x for x in cols if x in ('rule_id','problem_id','severity','action')])
"
      # 파손 3개(ops-dashboard·auto-triage·record_check 전 호출부) 무파손 dry-run 회귀
      python3 scripts/auto_triage.py --dry-run
    </automated>
  </verify>
  <done>check_results에 rule_id/problem_id/severity/action 컬럼이 NULL 허용으로 존재.
    record_check가 신규 선택 파라미터 지원, 기존 호출 호환. W2 게이트 통과 — record_check
    전 호출부(grep 전수 식별) 무파손 dry-run 회귀 확인 포함.</done>
</task>

<!-- ============================================================ W3 -->
<task type="auto">
  <name>Wave 3 (W3): 개별 규칙행 dual-write (aggregate 유지)</name>
  <files>
    ops_dashboard/db.py
    ops_dashboard/checks/standard.py
  </files>
  <action>
    **dual-write**: 기존 aggregate `standard_compliance` 행 + detail 자유텍스트를 **유지**하고,
    실패 규칙 각각을 `rule_id/severity/action` 컬럼이 채워진 개별 R 행으로 추가 기록.

    1. `ops_dashboard/db.py`에 `record_check_rule(conn, blog_id, rule_id, status, severity,
       action, detail="", evidence_url="")` 신규 함수 추가. 내부적으로 `record_check()` 호출하되
       `rule_id=rule_id, problem_id=None, severity=severity, action=action` 전달. kind 구분은
       rule_id 접두사(R/C/THUMBNAIL 등)로 판별 — 별도 컬럼 불필요(스키마 최소화).
    2. `ops_dashboard/checks/standard.py` `check_standard_compliance()` (L496~L552):
       기존 aggregate 결과 생성 로직은 **그대로** 두고, 실패 루프(`failures`)에서 각 실패 규칙을
       `record_check_rule(conn, blog_id, rule_id, "fail", severity, action, detail)`으로
       **추가 기록**. action은 `ops_dashboard/registry/`의 해당 rule entry에서 가져온다
       (`from ops_dashboard.registry import get_entry`).
       주의: `run_all_checks`(__init__.py L27)가 이미 aggregate를 `record_check`로 기록하므로
       **이중 기록 위치가 aggregate와 개별행이 충돌하지 않게** — 개별행은 `rule_id` 컬럼이 채워지고
       `check_name`은 `standard_compliance:{rule_id}` 또는 rule_id 그대로 사용. 기존
       `get_attention_items`(db.py L722)의 latest 쿼리가 `GROUP BY blog_id, check_name`을 쓰므로
       개별행의 check_name을 rule_id로 바꾸면 기존 aggregate 행과 분리되어 안전함.
       → **개별행 check_name = rule_id 값**(예: "R01")으로 기록. aggregate는 "standard_compliance" 유지.
    3. rollback 수단: 이 웨이브는 순수 추가 기록이므로, 문제 시 `record_check_rule` 호출부만 제거하면
       원복 가능 (aggregate 경로는 무영향).

    **금지:** aggregate 행 기록 제거 금지, detail 자유텍스트 제거 금지, 기존 소비자
    (readiness.py L86~96, maintenance.py L230) 파괴 금지.
  </action>
  <verify>
    <automated>
      # temp DB 격리 — 프로덕션 ops.db 쓰기 없이 dual-write 검증 (W2와 동일 패턴)
      # run_all_checks의 개별행 수는 실제 블로그 실패 여부에 의존하므로, 개별행 생성은
      # 함수 수준(record_check_rule)에서 결정적으로 증명하고 run_all_checks는 스모크로 검증.
      python3 -c "
import sqlite3, sys, tempfile, os; sys.path.insert(0,'.')
from ops_dashboard import db
from ops_dashboard.checks import run_all_checks
p=os.path.join(tempfile.mkdtemp(),'w3.db')
c=db.get_conn(p); db.init_db(c)
# blog_lifecycle active 행 필요 (checks가 블로그 상태 의존)
c.execute(\"INSERT INTO blog_lifecycle (blog_id, brand, config_status) VALUES ('car-hugo','cap','active')\")
c.commit()
# 1) 개별행 기록 경로 — rule_id/severity/action 채워짐 (W3 핵심 dual-write 함수)
db.record_check_rule(c,'car-hugo','R01','fail','CRITICAL','조치','detail')
# 2) aggregate 기록 경로 — rule_id NULL, 개별행과 공존 증명
db.record_check(c,'car-hugo','standard_compliance','fail','detail')
ind=c.execute('SELECT check_name,rule_id,severity,action FROM check_results WHERE rule_id IS NOT NULL').fetchall()
agg=c.execute(\"SELECT COUNT(*) FROM check_results WHERE check_name='standard_compliance' AND rule_id IS NULL\").fetchone()[0]
assert len(ind)>=1 and (ind[0][1],ind[0][2])==('R01','CRITICAL'), ind
assert agg==1, agg
# 3) integration smoke — run_all_checks가 temp DB에서 예외 없이 실행 (개별행 증가 확인 가능)
run_all_checks(c, blog_ids=['car-hugo'])
live=c.execute('SELECT COUNT(*) FROM check_results WHERE rule_id IS NOT NULL').fetchone()[0]
print('W3 OK ind=',len(ind),'agg=',agg,'post-run individual rows=',live)
"
    </automated>
  </verify>
  <done>aggregate 행(`standard_compliance`, rule_id NULL)과 R 개별행(rule_id/severity/action 채움)이
    공존. dual-write 경로(record_check_rule)가 결정적으로 개별행을 생성하고 run_all_checks가
    temp DB에서 예외 없이 실행. detail 자유텍스트·aggregate 유지. W3 게이트 통과.</done>
</task>

<!-- ============================================================ W4 -->
<task type="auto">
  <name>Wave 4 (W4): auto-triage 분류 결과 DB/JSON 출력 경로 (B5 해소)</name>
  <files>
    ops_dashboard/db.py
    scripts/auto_triage.py
  </files>
  <action>
    **additive 경로 신설.** auto-triage 분류 결과(problem_id/severity/action)를 기존 텔레그램/요약
    출력을 유지한 채, DB와 JSON 파일에도 기록한다. B5 해소.

    1. `ops_dashboard/db.py`에 신규 테이블 `triage_classifications` 추가 (init_db):
       ```
       CREATE TABLE IF NOT EXISTS triage_classifications (
           id INTEGER PRIMARY KEY AUTOINCREMENT,
           blog_id TEXT NOT NULL,
           problem_id TEXT NOT NULL,
           severity TEXT DEFAULT '',
           action TEXT DEFAULT '',
           classification TEXT DEFAULT '',   -- escalated | auto_handled | silent | excluded ...
           detail TEXT DEFAULT '',
           created_at TEXT NOT NULL DEFAULT (datetime('now'))
       );
       ```
       + `record_triage_classification(conn, blog_id, problem_id, severity, action,
       classification, detail="")` 함수.
    2. `scripts/auto_triage.py` `run_triage()` (L705~L850): 분류가 결정되는 지점
        (`engine.triage_notification`, `engine._accumulate`) 이후에 `record_triage_classification`으로
        DB 기록. 데이터 소스는 TriageEngine의 누적 결과(summary)에서 추출. `problem_id/severity/action`
        은 engine이 이미 보유. **기존 텔레그램 발송(L839~848)·요약 파일(L834~837)은 그대로 유지.**
        **dry_run 게이트 필수:** `record_triage_classification` 호출을 `if not dry_run:` 조건으로 감싸
        dry-run 실행 시 DB 쓰기를 하지 않는다(테스트 격리 유지). 데이터 소스 DB(연결)는
        `ops_dashboard.db` 경로를 auto_triage에 주입 — 단, dry_run이면 쓰기 생략.
    3. 별도 JSON 경로: `scripts/auto_triage.py`에 분류 결과를
       `SUMMARY_LOG`와 같은 디렉토리에 `triage_classifications_YYYYMMDD.json`으로 덤프하는
       옵션 추가 — DB 접근 실패 시에도 JSON으로 기록되어 데이터 손실 없음(조용한 실패 금지).

    **금지:** 텔레그램·요약 출력 제거 금지. auto_triage 분류 로직(_check_name_to_problem_id 등)
    변경 금지 — 이 웨이브는 **출력 경로 추가만**.
  </action>
  <verify>
    <automated>
      python3 scripts/auto_triage.py --dry-run && python3 -c "
import sqlite3, sys, tempfile, os; sys.path.insert(0,'.')
from ops_dashboard import db
p=os.path.join(tempfile.mkdtemp(),'w4.db')  # temp DB 격리 — 프로덕션 ops.db 쓰기 없음
c=db.get_conn(p); db.init_db(c)
# write path 실제 발화 — 스키마 존재만이 아니라 행 삽입·필드 검증
db.record_triage_classification(c,'car-hugo','P01','CRITICAL','escalate','escalated','detail')
n=c.execute('SELECT COUNT(*) FROM triage_classifications').fetchone()[0]
assert n==1, n
r=c.execute('SELECT problem_id,severity,action FROM triage_classifications').fetchone()
assert tuple(r)==('P01','CRITICAL','escalate'), tuple(r)
print('W4 OK rows=',n,'fields=',tuple(r))
"
    </automated>
  </verify>
  <done>auto-triage 분류 결과가 DB(triage_classifications, write path가 행 삽입·필드로 검증됨)와
    JSON 파일에 기록됨. 텔레그램·요약 경로 유지. W4 게이트 통과.</done>
</task>

<!-- ============================================================ W5 -->
<task type="auto">
  <name>Wave 5 (W5): 단일 엔드포인트 + auto-triage 구조 필드 전환 (최대 위험)</name>
  <files>
    ops_dashboard/app.py
    ops_dashboard/db.py
    ops_dashboard/readiness.py
    scripts/auto_triage.py
  </files>
  <action>
    **최대 위험 웨이브.** auto-triage가 자유텍스트 파싱에서 구조 필드 읽기로 전환하는 지점.
    **BLOCKER B1 (필수):** W3이 기록한 개별 R/P 행의 `rule_id/problem_id/severity/action`
    컬럼이 fail_checks 루프(L743) item에 실제로 도달하고, 구조 필드 우선 매핑 경로가
    **실제로 발화**하도록 wiring까지 명시한다. "선언만 하고 안 타는" silent no-op 금지.

    1. `ops_dashboard/db.py` `get_attention_items()` (L722) 구조 필드 노출 (B1 wiring a):
       - L730~L743 SELECT에 `cr.rule_id, cr.problem_id, cr.severity, cr.action` 컬럼 추가.
       - L748~L755 fail_check dict에 동일 키 4개를 그대로 포함
         (`"rule_id": r["rule_id"], "problem_id": r["problem_id"], "severity": r["severity"],
         "action": r["action"]`). excluded_fail_checks dict에도 동일 포함.
       - 이로써 W3가 기록한 개별행(rule_id 채워짐)이 fail_checks loop에 구조 필드를 실어
         나른다. aggregate 행(`standard_compliance`, rule_id NULL)은 그대로 자유텍스트 폴백.
    2. `ops_dashboard/app.py` `_register_api_routes()` (L383~)에 **신규 단일 엔드포인트**
       `GET /api/registry` 추가 (`@require_auth`). 반환 JSON:
       - `rules`: check_results의 개별 R 행 + ops_dashboard/registry/의 rule 정의 병합
         (id/kind/target/severity/action/bucket + 최근 status).
       - `errors`: triage_classifications 최신 + ops_dashboard/registry/의 error 정의 병합.
       - 동일 스키마로 노출 — B7의 6필드 한계를 넘어 rule_id/problem_id/severity/action 포함.
       구현은 `ops_dashboard/db.py`에 `get_registry_view(conn) -> dict` 헬퍼로 추가.
    3. `scripts/auto_triage.py` 구조 필드 우선 매핑 (B1 wiring b — 레지스트리 조인 안전망):
       - `fetch_dashboard_data()` (L589) endpoints에 `("registry", "/api/registry")` 추가.
       - 신규 헬퍼 `_resolve_problem_id(item, registry_map) -> str` 추가. 우선순위:
         (1) `item.get("problem_id")`가 있으면 그대로 반환;
         (2) `item.get("rule_id")`가 있으면 `registry_map`의 `rule_id→problem_id` 역방향
         탐색으로 매핑 (registry의 rule entry에서 target/action으로 대응 error 매핑 또는
         rule_id 자체를 problem_id 후보로);
         (3) 둘 다 없으면 기존 `_pattern_to_problem_id`/`_check_name_to_problem_id` 폴백.
        - `registry_map`: `dashboard.get("registry")`의 rules에서 **`check_name→rule_id`로
          1차 조인**해 각 fail_check item의 `rule_id`를 확보한 뒤, `rule_id→problem_id` 매핑
          (`dict[rule_id, str]`, W5-2 검증과 동일 계약)으로 구성. fetch한 /api/registry가
          없거나 비면 `{}` — 폴백으로 안전 동작.
       - `run_triage()` L743 fail_checks 루프에서 `problem_id = _resolve_problem_id(item,
         registry_map)`로 교체. `ctx`에 `rule_id/problem_id/severity/action`도 함께 실어
         engine 분류에 구조 정보 전달.
       - **폴백 유지**: 구조 필드가 없는 레거시 엔드포인트 응답과의 하위호환을 위해
         기존 매핑 함수는 W6까지 제거하지 않는다.
    4. readiness.py는 그대로 (aggregate 준수율 계산 유지 — W5에서 변경 없음).

    **집중 게이트:** 이 웨이브 종료 시 auto-triage가 반드시 정상 동작해야 함. 구조 필드 읽기
    전환 후에도 dry-run 결과가 레거시와 동일한 problem_id 매핑을 산출하는지 비교 검증.

    **위험 (아래 threat_model T-69-W5 참조):** 구조 필드 우선 적용 시 필드 부재/형식 불일치로
    분류가 깨질 수 있음. 반드시 폴백 체인을 두고, dry-run으로 이전 대비 회귀가 없는지 확인.
  </action>
  <verify>
    <automated>
      # (1) get_attention_items가 W3 개별행 구조 필드를 노출하는지 — temp DB로 격리
      python3 -c "
import sqlite3, sys, tempfile, os; sys.path.insert(0,'.')
from ops_dashboard import db
p=os.path.join(tempfile.mkdtemp(),'w5.db')
c=db.get_conn(p); db.init_db(c)
db.record_check_rule(c,'car-hugo','R01','fail','CRITICAL','조치','detail')  # 개별행(rule_id 채움)
# blog_lifecycle에 active 행 필요
c.execute(\"INSERT INTO blog_lifecycle (blog_id, brand, config_status) VALUES ('car-hugo','cap','active')\")
c.commit()
atts=db.get_attention_items(c)
fc=atts['fail_checks']
assert fc and all(k in fc[0] for k in ('rule_id','problem_id','severity','action')), fc
assert fc[0]['rule_id']=='R01' and fc[0]['severity']=='CRITICAL', fc[0]
print('W5-1 OK structured fields surfaced:', {k:fc[0].get(k) for k in ('rule_id','problem_id','severity','action')})
" && \
      # (2) 구조 필드 기반 매핑 경로가 실제 발화 — 폴백 미호출 단언
      python3 -c "
import sys; sys.path.insert(0,'.'); import importlib
import scripts.auto_triage as at
m={}
pid=at._resolve_problem_id({'rule_id':'R01','problem_id':'P01','severity':'CRITICAL','action':'조치'}, m)
assert pid=='P01', pid  # 구조 필드 그대로 사용 — 폴백 불필요
pid2=at._resolve_problem_id({'rule_id':'R02'}, {'R02':'P99'})  # rule_id→registry 역방향 조인
assert pid2=='P99', pid2
pid3=at._resolve_problem_id({'check_name':'freshness'}, {})  # 폴백 경로 확인
assert pid3=='P01', pid3
print('W5-2 OK structure path used: P01/R02→P99, fallback freshness→P01')
" && \
      python3 -c "
import sys; sys.path.insert(0,'.')
from ops_dashboard import db
import os, tempfile
p=os.path.join(tempfile.mkdtemp(),'w5r.db'); c=db.get_conn(p); db.init_db(c)
v=db.get_registry_view(c)
assert isinstance(v.get('rules'), list) and isinstance(v.get('errors'), list), v.keys()
print('W5-3 OK registry view keys=', list(v.keys()))
" && python3 scripts/auto_triage.py --dry-run
    </automated>
  </verify>
  <done>/api/registry가 규칙 개별행 + 오류분류를 같은 스키마로 노출. get_attention_items가 개별행의
    rule_id/problem_id/severity/action 구조 필드를 fail_checks item에 포함. auto-triage가 구조
    필드 우선(`_resolve_problem_id`) + 자유텍스트 파싱 폴백으로 전환하고, 구조 필드 기반 매핑
    경로가 실제 발화(W5-2 검증)하며, dry-run 정상. W5 집중 게이트 통과.</done>
</task>

<!-- ============================================================ W6 -->
<task type="auto">
  <name>Wave 6 (W6): cleanup — 자유텍스트 의존·이중정의 제거</name>
  <files>
    ops_dashboard/db.py
    ops_dashboard/checks/standard.py
    scripts/auto_triage.py
    shared/problem_registry.py
    ops_dashboard/readiness.py
  </files>
  <action>
    **소비자가 완전 이행된 뒤에만.** W5에서 auto-triage가 구조 필드로 전환 완료된 것을 전제로,
    이중정의와 자유텍스트 의존을 제거한다.

    1. `ops_dashboard/db.py` `SEED_STANDARD_RULES` (L513~L546) + `seed_standard_rules()`
       (L549~L566) 제거 → `ops_dashboard/registry/rules.py`가 단일 출처. seed 시드는
       registry의 RULES에서 파생하는 `seed_from_registry()`로 대체 (표준 규칙 테이블 유지,
       정의만 단일화).
    2. `ops_dashboard/checks/standard.py` `STANDARD_RULES` (L27~L126) 제거 → `ops_dashboard/
       registry/rules.py`에서 `import`. `_CHECK_FUNCTIONS`(L480)는 check 함수 참조 맵으로 유지
       (함수 구현은 코드 — 제거 불가). `check_standard_compliance`의 rule 루프는 registry의
       RULES를 순회.
    3. `scripts/auto_triage.py` 하드코딩 맵 `_check_name_to_problem_id`(L853),
       `_pattern_to_problem_id`(L866), `_reason_to_problem_id`(L888) 제거 → `ops_dashboard/
       registry/errors.py` + `shared/problem_registry.py`의 역방향 탐색으로 파생.
       `_reason_to_problem_id`는 `shared/problem_registry.lookup_reason()` 재사용.
    4. `shared/problem_registry.py`: `PROBLEM_REGISTRY`는 그대로 유지하되, (선택) registry에서
       파생하도록 정리. **기존 dispatcher/monitor 소비자 파괴 금지** — `lookup_reason()/
       lookup_problem()/lookup_hook()` 시그니처 유지.
    5. `ops_dashboard/readiness.py`: `compute_standard_compliance`(L66)의 `rule_bucket`을
       `STANDARD_RULES` 직접 import(과거 L77) 대신 `ops_dashboard/registry/`의 bucket에서 파생.
       `_parse_failed_rules(row["detail"])`는 aggregate detail 자유텍스트가 제거되면 개별행의
       rule_id/severity로 대체 (개별행이 이미 컬럼화됨).

    **위험 (아래 T-69-W6 참조):** 제거 순서가 틀리면 파손. 반드시 registry import가 성공한 뒤
    제거. 이 웨이브는 파괴적 작업 프로토콜 적용 (기존 동작 대체). 전후 준수율 수치 대조 필수.
  </action>
  <verify>
    <automated>
      python3 -c "
import sys; sys.path.insert(0,'.')
from ops_dashboard.checks.standard import check_standard_compliance  # STANDARD_RULES 제거 확인
import ops_dashboard.checks.standard as s
assert not hasattr(s, 'STANDARD_RULES'), 'STANDARD_RULES should be removed'
from ops_dashboard.registry.rules import RULES
print('W6 OK rules from registry=', len(RULES))
" &&       python3 scripts/auto_triage.py --dry-run && python3 -c "
import sqlite3,sys; sys.path.insert(0,'.')
from ops_dashboard import db
from ops_dashboard.readiness import compute_standard_compliance
# 의도된 프로덕션 읽기: W6/W7은 실데이터로 준수율 전후 비교가 필요.
# init_db는 additive(_alter_columns)라 안전, 데이터 쓰기 없음(W2~W5와 달리 격리하지 않음).
c=db.get_conn(); db.init_db(c)
print('W6 readiness OK', compute_standard_compliance(c)['ratio'])
"
    
    </automated>
  </verify>
  <done>STANDARD_RULES/SEED_STANDARD_RULES 이중정의 제거, registry 단일 출처. detail 자유텍스트
    의존 제거, auto-triage가 registry 파생 맵 사용. readiness 준수율 동일 산출. W6 게이트 통과.</done>
</task>

<!-- ============================================================ W7 -->
<task type="auto">
  <name>Wave 7 (W7): 콘텐츠 채우기 — 선언으로 신규 규칙 등록 실증</name>
  <files>
    ops_dashboard/registry/rules.py
    ops_dashboard/registry/errors.py
    ops_dashboard/checks/standard.py
  </files>
  <action>
    "새 규칙 = 선언 한 줄 + 함수 1개" 실증. 아래 항목을 registry에 **선언으로만** 추가하고
    필요한 check 함수만 구현한다.

    1. `ops_dashboard/registry/rules.py`에 선언 추가 (스키마 형식):
       - **R06 A/B 분화**: 기존 R06을 R06A/R06B로 확장 (R06A: fluid+in-article format,
         R06B: outside push div). bucket은 deferred 유지 (STRUCT-16).
       - **THUMBNAIL-01**: 썸네일 존재/깨짐 검사 (target: featureimage/R2, CRITICAL,
         check_fn: `_check_thumbnail_01`).
       - **R2-01**: R2 업로드 URL 유효성 검사 (target: r2_uploader, MAJOR, check_fn:
         `_check_r2_01`).
       - **Blowfish 21 항목**: `hugo-blowfish-standardization` 스킬 기준의 Blowfish 표준
         검사 21개 선언 (extend-head.html, single.html, baseof.html, ad partials 등 —
         스킬 매핑 참조). 각각 id(예: BLOWFISH-01~21), target, severity, bucket, check_fn.
    2. `ops_dashboard/checks/standard.py`에 해당 check 함수 구현 (`_check_thumbnail_01`,
       `_check_r2_01`, Blowfish 검사 함수들). `_CHECK_FUNCTIONS` 맵에 등록.
       **모든 추가 항목의 `check_fn`은 실제 구현된 함수를 참조한다 — 빈 문자열 항목은 만들지
       않는다** ("새 규칙 = 선언 한 줄 + 함수 1개" 실증). Blowfish 21항목은
       `hugo-blowfish-standardization` 스킬의 검사 로직을 반영한 얇은 check 함수로 구현한다.
       실검사 활성화는 본 웨이브에서 완료한다.
    3. `ops_dashboard/registry/errors.py`에도 필요시 신규 오류 선언 추가 (있다면).
    4. registry `all_entries()`에 새 항목이 자동 포함되므로, W5의 `/api/registry`와
       `run_all_checks`가 선언 추가만으로 새 규칙을 반영 — 코드 변경 없이 추가됨을 실증.

    **R06 분화 처리 (deprecate-then-split — W1/W3와 정합, orphan 방지):**
    - W1이 선언·W3가 개별행(check_name='R06')으로 기록한 기존 R06은 W7에서
      **deprecated 처리**하고 R06A/R06B로 분화한다.
    - registry의 `RULES`에서 `R06` 항목을 제거하고 `R06A`/`R06B`로 교체 —
      `all_entries()`에 `R06` 미포함(`R06A`/`R06B`만).
    - 기존 check_results의 `check_name='R06'` 레거시 개별행은 **데이터 보존 목적으로 유지**하고
      재기록/마이그레이션하지 않는다. 신규 기록은 R06A/R06B로만 발생 (구조 필드 소비는 W5에서
      rule_id 기반이라 R06A/R06B가 자동 수용되며, 레거시 R06 행은 aggregate 자유텍스트 폴백 경로로
      여전히 읽힘).
    - **readiness 준수율 (W6/W7 순서 주의):** R06과 R06A/R06B의 bucket은 모두 **deferred**로
      동일하므로 R06→R06A/R06B 분화는 준수율 분자/분모를 바꾸지 않는다. W7 이후
      `compute_standard_compliance` 전후 ratio를 비교해 동일함을 대조 (W6 준수율 기준 대비).
  </action>
  <verify>
    <automated>
      python3 -c "
import sys; sys.path.insert(0,'.')
from ops_dashboard.registry import all_entries
ids=[e.id for e in all_entries()]
for want in ['R06A','R06B','THUMBNAIL-01','R2-01']:
    assert want in ids, want
# R06 orphan 방지 — deprecated-then-split: R06은 더 이상 활성 아님
assert 'R06' not in ids, 'legacy R06 still active'
assert all(e.check_fn for e in all_entries() if e.kind=='rule'), 'some rule has empty check_fn'
blow=[e for e in all_entries() if e.id.startswith('BLOWFISH-')]
assert len(blow) == 21, len(blow)
print('W7 OK total=', len(all_entries()), 'blowfish=', len(blow), 'R06_active=', 'R06' in ids)
" && python3 scripts/auto_triage.py --dry-run && python3 -c "
import sys; sys.path.insert(0,'.')
from ops_dashboard import db
from ops_dashboard.readiness import compute_standard_compliance
# 의도된 프로덕션 읽기: R06→R06A/B split 후 준수율 전후 비교용. init_db는 additive라 안전.
c=db.get_conn(); db.init_db(c)
r=compute_standard_compliance(c)
print('W7 readiness ratio=', r['ratio'])
"
    </automated>
  </verify>
  <done>R06(A/B) 분화로 기존 R06이 deprecated(비활성)되고, THUMBNAIL-01, R2-01, Blowfish 21항목이
    **실제 check 함수와 함께** 선언으로 등록됨 (check_fn 비어있지 않음). registry 자동 반영,
    run_all_checks가 선언 추가만으로 확장, readiness ratio가 W6 기준과 동일 유지.
    W7 게이트 통과.</done>
</task>

</tasks>

<!-- ============================================================ 공통 안전 게이트 -->
<safety_gate>
**공통 웨이브 게이트 (W1~W7 매 웨이브 종료 시 실행, 하나라도 깨지면 해당 웨이브에서 중단·롤백):**

1. **ops-dashboard 생존** (PID 13818): 프로세스 alive + `/api/attention`·`/api/readiness` HTTP 5060 정상(200 응답).
   ```
   ps -p 13818 -o pid=,comm= && curl -s -o /dev/null -w "%{http_code}" -u $DASHBOARD_USER:$DASHBOARD_PASS http://localhost:5060/api/readiness
   ```
2. **auto-triage 생존**: 03:00 Cron 스케줄 등록 확인 + `python3 scripts/auto_triage.py --dry-run` 정상 **+ 실모드(PROBLEM_ALERT_DRY_RUN=0) 정상 동작 확인**.
3. **무인화 4프로세스 정상** (scheduler 78295, watchdog 34819 포함): 전부 alive.
   ```
   ps -p 78295 -o pid=,comm= && ps -p 34819 -o pid=,comm= && ps aux | grep -E 'scheduler|watchdog|auto_triage' | grep -v grep | wc -l
   ```
4. **해당 웨이브 백업 태그 존재** — W1~W7 각 웨이브는 시작 전 프로덕션 ops.db 백업(`data/ops.db.bak_<ts>`) 또는 롤백 커밋 태그를 확보해두고, 웨이브 종료 시 그 존재를 확인한다.
5. 실패 시: 해당 웨이브의 변경 원복 (각 웨이브의 rollback 수단 + 백업 태그 활용) 후 원인 기록. 다음 웨이브 진행 금지.
</safety_gate>

<threat_model>
## Trust Boundaries
| Boundary | Description |
|----------|-------------|
| ops-dashboard API → check_results DB | 내부 HTTP API가 쓰는 쓰기 경로 (run-checks, dual-write) |
| auto-triage → ops-dashboard API | Cron 스크립트가 읽는 외부 HTTP 소비 경로 (W5 구조 필드 전환) |
| auto-triage → triage_classifications DB | 분류 결과 쓰기 경로 (W4 신설) |

## STRIDE Threat Register
| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-69-W5-01 | Spoofing | auto_triage.py 구조필드 읽기 | mitigate | /api/registry 응답의 rule_id/problem_id가 registry의 실제 id와 일치하는지 validate_entry로 검증, 불일치 시 폴백 |
| T-69-W5-02 | Tampering | auto_triage.py 필드 우선순위 | mitigate | 구조 필드 부재 시 반드시 기존 파싱으로 폴백 — dry-run으로 레거시 대비 매핑 회귀 비교 |
| T-69-W5-03 | DoS | /api/registry 신규 엔드포인트 | accept | 인증(require_auth) 적용, 내부 전용 — 낮은 노출 면적 |
| T-69-W6-01 | Tampering | standard.py STANDARD_RULES 제거 | mitigate | registry import 성공 확인 후 제거, readiness 준수율 전후 수치 대조 |
| T-69-W6-02 | Tampering | auto_triage.py 하드코딩 맵 제거 | mitigate | _reason_to_problem_id를 shared.problem_registry.lookup_reason()으로 대체 후 dry-run 회귀 검증 |
| T-69-W2-01 | Tampering | check_results 컬럼 추가 | mitigate | _alter_columns try/except 유지 + record_check 선택 파라미터 기본값으로 기존 호출 호환 |
| T-69-SC | Tampering | npm/pip/cargo installs | accept | 이 페이즈는 신규 패키지 설치 없음 (기존 Python 표준+프로젝트 deps만 사용) |
</threat_model>

<verification>
**Phase 69 완료 검증 — CONTEXT.md 검증 기준 매핑:**

| 검증 기준 (CONTEXT.md) | 충족 웨이브 | 확인 수단 |
|---|---|---|
| 단일 선언 레지스트리 — 규칙·오류 동일 스키마 | W1 | `all_entries()` — RULES+ERRORS 모두 UnifiedEntry |
| check_results에 rule_id/problem_id/severity/action 컬럼 (NULL 허용) | W2 | `PRAGMA table_info(check_results)` |
| W2 record_check 시그니처 무파손 — 전 호출부 회귀 | W2 | `grep -rn "record_check("` 전수 식별 + dry-run 회귀 |
| W3 이후 aggregate + R개별행 공존 (detail 유지) | W3 | `run_all_checks` 후 aggregate/개별행 쿼리 |
| W4 이후 auto-triage 분류 결과 DB/JSON 기록 (텔레그램 유지) | W4 | triage_classifications 테이블 + JSON 파일 |
| W5 이후 단일 엔드포인트 노출 + auto-triage 구조필드 전환 | W5 | `/api/registry` + auto-triage dry-run |
| W6 이후 자유텍스트 의존·이중정의 제거 | W6 | STANDARD_RULES/SEED 제거 확인 + readiness 동일 |
| W7 이후 R06(A/B)/THUMBNAIL-01/R2-01/Blowfish21 선언 등록 | W7 | `all_entries()` 포함 확인 |
| 매 웨이브 ops-dashboard·auto-triage 생존 + 무인화 4프로세스 정상 + 백업 태그 존재 | W1~W7 | 공통 안전 게이트 |

**회귀 안전망:** 매 웨이브 후 `python3 scripts/auto_triage.py --dry-run`과 readiness/attention
엔드포인트 200을 재확인. 기존 동작 보존은 "Break nothing that works" 원칙 — additive 웨이브
(W1~W5)에서는 기존 경로를 건드리지 않고, 제거(W6)는 소비자 전환 완료 후에만.
</verification>

<success_criteria>
- 단일 선언 레지스트리(ops_dashboard/registry/)가 규칙+오류를 동일 스키마로 정의하고,
  W7 콘텐츠가 선언 한 줄 + 함수 1개로 추가됨을 실증.
- check_results가 4개 신규 컬럼을 NULL 허용으로 보유, aggregate + 개별행 공존.
- auto-triage 분류 결과가 DB(triage_classifications)+JSON으로 기록, 단일 엔드포인트(/api/registry)
  로 구조 필드 노출, auto-triage가 구조 필드 읽기로 전환.
- STANDARD_RULES/SEED_STANDARD_RULES/하드코딩 맵 이중정의 제거 (registry 단일 출처).
- 7개 웨이브 전부 공통 안전 게이트 통과 — ops-dashboard·auto-triage 생존, 무인화 4프로세스 정상, 백업 태그 존재.
- 기존 동작 보존: aggregate 행, 텔레그램/요약 경로, dispatcher/monitor 소비자 시그니처 무파손 (record_check 전 호출부 포함).
</success_criteria>

<output>
Create `.planning/phases/PHASE-69-unified-registry/69-SUMMARY.md` when done
</output>

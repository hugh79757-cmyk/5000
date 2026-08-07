---
phase: 62-content-leak-prevention
plan: 02
type: execute
wave: 2
depends_on: ["62-01"]
files_modified:
  - ops_dashboard/db.py
autonomous: true
requirements: []
must_haves:
  truths:
    - "C01~C08 8개 규칙이 standard_rules 테이블에 INSERT됨"
    - "C02 severity CRITICAL, C04 severity CRITICAL, C08 severity CRITICAL"
    - "기존 R01~R12와 충돌 없음 (rule_id 중복 없음)"
  artifacts:
    - path: "ops_dashboard/db.py"
      provides: "C01~C08 standard_rules INSERT"
      contains: "C01|C02|C03|C04|C05|C06|C07|C08"
  key_links:
    - from: "SEED_STANDARD_RULES"
      to: "standard_rules 테이블"
      via: "INSERT OR IGNORE"
      pattern: "INSERT OR IGNORE INTO standard_rules"
---

<objective>
## 목표

역검증 통과 확인 후, C01~C08 규칙 정의를 `ops_dashboard/db.py`의 `SEED_STANDARD_RULES`에 INSERT.

## 배경

CONTEXT.md §기존 standard_rules 현황:
- R01~R12가 이미 등록되어 있음 (프론트엔드/테마 표준)
- C01~C08은 콘텐츠 무결성·누수 계열로 R01~R12와 별개 스콥

## 실행 게이트

**역검증(62-01)에서 "전건 탐지 + 오탐 0" 확인 후에만 진행.**
오탐 발생 시 INSERT 보류, 조건 수정 후 62-01에서 재검증.

**git tag 백업 먼저**: `git tag phase-62-pre-insert-$(date +%Y%m%d-%H%M%S)`
</objective>

<execution_context>
@/Users/twinssn/.config/opencode/get-shit-done/workflows/execute-plan.md
</execution_context>

<context>
@/Users/twinssn/Projects/5000/.planning/phases/phase-62-content-leak-prevention/CONTEXT.md
@/Users/twinssn/Projects/5000/ops_dashboard/db.py
@/Users/twinssn/Projects/5000/ops_dashboard/checks/standard.py
</context>

<tasks>

<task type="checkpoint:decision" gate="blocking">
  <what-built>역검증 결과 (62-01)</what-built>
  <how-to-verify>
62-01 역검증 스크립트 실행 결과 확인:
- dead_links 77건 전부 fail
- ETAP 영문 오탐 0
- 프롬프트 누수 전건 탐지
  </how-to-verify>
  <resume-signal>
- ✅ "승인" → git tag 백업 후 INSERT 진행
- ❌ "보류: [사유]" → 조건 수정 후 재검증
  </resume-signal>
</task>

<task type="auto">
  <name>Task 1: git tag 백업</name>
  <files>N/A (git tag)</files>
  <action>
INSERT 전에 git tag 백업을 생성한다.

```bash
cd /Users/twinssn/Projects/5000
git tag phase-62-pre-insert-$(date +%Y%m%d-%H%M%S)
git push origin phase-62-pre-insert-$(date +%Y%m%d-%H%M%S)
```
</action>
  <verify>
<automated>
git tag | grep phase-62-pre-insert
</automated>
  </verify>
  <done>
phase-62-pre-insert-YYYYMMDD-HHMMSS 태그 생성 완료
  </done>
</task>

<task type="auto">
  <name>Task 2: C01~C08 standard_rules INSERT</name>
  <files>ops_dashboard/db.py</files>
  <action>
`ops_dashboard/db.py`에 C01~C08 규칙을 추가한다.

**삽입 위치**: `SEED_STANDARD_RULES` 리스트 끝 (R12 다음)

**INSERT 문**:
```python
SEED_STANDARD_RULES: list[dict] = [
    # ... 기존 R01~R12 ...
    {"rule_id": "R12", "target": "layouts/", "severity": "MAJOR", "description": "No override files beyond the allowed set"},

    # C01~C08: 콘텐츠 무결성·누수 규칙 (Phase 62)
    {"rule_id": "C01", "target": "frontmatter", "severity": "MAJOR",
     "description": "프론트매터 내 곡선따옴표(' ' \" \") 사용 금지 — YAML 값(타이틀·description·카테고리·태그 등)에 직선따옴표(' \"') 아닌 곡선따옴표 포함 시 위반"},
    {"rule_id": "C02", "target": "frontmatter", "severity": "CRITICAL",
     "description": "프론트매터 미종료 — 첫 --- 이후 두 번째 --- 존재하지 않음 (전체 --- 홀수 카운트 판정 금지, 첫--- 이후 두 번째--- 존재 여부로만 판정)"},
    {"rule_id": "C03", "target": "body", "severity": "MAJOR",
     "description": "본문에 프론트매터 키 라인 유출 — title:, og_image:, featureimage:, date:, slug: 등 프론트매터 키 라인과 유사한 라인이 본문에 존재"},
    {"rule_id": "C04", "target": "body", "severity": "CRITICAL",
     "description": "본문에 LLM 프롬프트/사고문 누수 — 'Need think', 'We need to write', 'Let's think step by step', '먼저', '생각해보자' 등 LLM 지시 복술 흔적"},
    {"rule_id": "C05", "target": "frontmatter+publish", "severity": "CRITICAL",
     "description": "draft:true 발행 대상 — frontmatter에 draft: true가 설정되어 있는데 발행 파이프라인이 이를 발행 대상으로 처리"},
    {"rule_id": "C06", "target": "file+deploy", "severity": "MAJOR",
     "description": "로컬 mtime > 배포 시각 — 로컬 파일의 mtime이 마지막 배포 시각보다 최신 (배포 후 로컬에서 파일 수정된 상태)"},
    {"rule_id": "C07", "target": "body+cross-sell", "severity": "MAJOR",
     "description": "죽은 크로스셀 링크 — 크로스셀 카드가 가리키는 대상 slug가 DB에 published=0이거나 라이브에서 HTTP 404"},
    {"rule_id": "C08", "target": "live+file", "severity": "CRITICAL",
     "description": "라이브-파일 불일치 — 라이브 프런트와 로컬 파일 간 불일치 (제목 빔, og_image 유출 등)"},
]
```

**주의사항**:
- rule_id는 C01~C08 (R01~R12와 충돌 없음)
- severity: C02/C04/C08은 CRITICAL, C01/C03/C05/C06/C07은 MAJOR
- description은 CONTEXT.md §규칙 정의와 정확히 일치
</action>
  <verify>
<automated>
# INSERT 확인
python3 -c "
import sys; sys.path.insert(0, '.')
from ops_dashboard.db import seed_standard_rules, get_conn
conn = get_conn()
seed_standard_rules(conn)
rows = conn.execute('SELECT rule_id, target, severity FROM standard_rules WHERE rule_id LIKE \"C%\" ORDER BY rule_id').fetchall()
for r in rows:
    print(f'{r[\"rule_id\"]}: {r[\"target\"]} ({r[\"severity\"]})')
conn.close()
"
</automated>
  </verify>
  <done>
C01~C08 8개 규칙이 standard_rules 테이블에 INSERT됨. C02/C04/C08 CRITICAL, 나머지 MAJOR.
  </done>
</task>

</tasks>

<success_criteria>
- [ ] git tag phase-62-pre-insert-YYYYMMDD-HHMMSS 생성
- [ ] ops_dashboard/db.py SEED_STANDARD_RULES에 C01~C08 추가
- [ ] standard_rules 테이블에 C01~C08 8행 INSERT 확인
- [ ] C02/C04/C08 severity CRITICAL, 나머지 MAJOR 확인
- [ ] 기존 R01~R12와 rule_id 충돌 없음
</success_criteria>

<output>
ops_dashboard/db.py 수정

커밋 메시지 후보:
- `feat(phase-62): add C01~C08 content integrity rules to standard_rules`
</output>

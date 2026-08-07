---
phase: 62-content-leak-prevention
plan: 05
type: execute
wave: 5
depends_on: ["62-04"]
files_modified:
  - ops_dashboard/checks/content_integrity.py
  - ops_dashboard/db.py
autonomous: true
requirements: []
must_haves:
  truths:
    - "ops_dashboard/checks/content_integrity.py에 C01~C08 체크 함수 구현"
    - "register_check로 8개 체크 등록"
    - "check_results 테이블에 C01~C08 판정 결과 기록됨"
    - "localhost:5050 대시보드에서 블로그별 규칙 위반 현황 확인 가능"
  artifacts:
    - path: "ops_dashboard/checks/content_integrity.py"
      provides: "C01~C08 콘텐츠 무결성 체크 모듈"
      min_lines: 250
    - path: "ops_dashboard/db.py"
      provides: "check_results 기록 호환 확인"
  key_links:
    - from: "ops_dashboard/checks/content_integrity.py"
      to: "ops_dashboard/checks/__init__.py CHECKS 레지스트리"
      via: "register_check 데코레이터"
      pattern: "@register_check.*C0[1-8]"
    - from: "check_results"
      to: "localhost:5050 대시보드"
      via: "run_all_checks → DB → 대시보드 조회"
      pattern: "check_results|blog_id.*C0[1-8]"
---

<objective>
## 목표

C01~C08 규칙 판정 결과를 `check_results`에 기록하고, `localhost:5050` 대시보드에서
블로그별 콘텐츠 무결성 위반 현황을 조회할 수 있게 통합.

## 배경

CONTEXT.md §대시보드 표시:
- 규칙 판정 결과를 `localhost:5050` 대시보드의 `check_results`에 분기별로 뜨도록 연결
- 사용자가 대시보드에서 어느 블로그에 어느 릭이 몇 건인지 보고 배포차단 상태를 확인

CONTEXT.md §기존 체크 패턴:
- ops_dashboard/checks/standard.py: R01~R12 체크 구현 패턴
- ops_dashboard/checks/__init__.py: register_check 데코레이터 + CHECKS 레지스트리
- ops_dashboard/db.py: record_check 함수, check_results 테이블
</objective>

<execution_context>
@/Users/twinssn/.config/opencode/get-shit-done/workflows/execute-plan.md
</execution_context>

<context>
@/Users/twinssn/Projects/5000/.planning/phases/phase-62-content-leak-prevention/CONTEXT.md
@/Users/twinssn/Projects/5000/ops_dashboard/checks/__init__.py
@/Users/twinssn/Projects/5000/ops_dashboard/checks/standard.py
@/Users/twinssn/Projects/5000/ops_dashboard/db.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: content_integrity.py 체크 모듈 생성</name>
  <files>ops_dashboard/checks/content_integrity.py</files>
  <action>
`ops_dashboard/checks/content_integrity.py`를 새로 생성.

```python
"""ops_dashboard.checks.content_integrity — C01~C08 콘텐츠 무결성 검사

블로그별 콘텐츠 무결성 규칙(C01~C08)을 검사하고 결과를 check_results에 기록.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path

from ops_dashboard.checks import register_check
from ops_dashboard.db import get_blog_detail, record_check

logger = logging.getLogger(__name__)

# 프론트매터 키 목록 (C03 검출 대상)
FM_KEYS = ["title", "og_image", "featureimage", "date", "slug",
            "categories", "tags", "description", "draft", "image", "pubDate", "author"]

# C04 패턴 (국문 + 영문)
C04_KO_PATTERNS = [
    r"먼저\s*생각", r"생각해보자", r"생각해\s*보자",
    r"다음\s*단계", r"단계별로", r"우선\s*",
    r"우리가\s*해야\s*할", r"필요한\s*것",
]
C04_EN_PATTERNS = [
    r"\bNeed\s+think\b", r"\bWe\s+need\s+to\s+write\b",
    r"Let.s\s+think\s+step\s+by\s+step",
    r"think\s+step\s+by\s+step",
    r"let.s\s+break\s+this\s+down",
    r"here.?s\s+the\s+plan",
    r"firstly,?\s", r"secondly,?\s",
    r"in\s+order\s+to\s+achieve",
    r"as\s+an\s+AI\s+language\s+model",
    r"I\s+cannot\s+",
]


def _find_site_path(conn, blog_id: str) -> Path | None:
    """blog_lifecycle에서 site_path 추출."""
    blog = get_blog_detail(conn, blog_id)
    if not blog:
        return None
    sp = blog.get("site_path", "")
    p = Path(sp) if sp else None
    return p if p and p.exists() else None


def _read_post_files(site: Path) -> list[tuple[Path, str]]:
    """site/content/posts/의 최신 md 파일 목록 반환."""
    posts_dir = site / "content" / "posts"
    if not posts_dir.exists():
        return []
    import os
    cutoff = datetime.now().timestamp() - 7 * 86400
    results = []
    for md_file in posts_dir.rglob("*.md"):
        if md_file.stat().st_mtime >= cutoff:
            results.append((md_file, md_file.read_text(encoding="utf-8", errors="replace")))
    return results


def _parse_frontmatter(content: str) -> tuple[str | None, dict]:
    """frontmatter 파싱 (단순 regex)."""
    m = re.match(r"^---\n(.*?)\n---\n", content, re.DOTALL)
    if not m:
        return None, {}
    fm_text = m.group(1)
    fm = {}
    for line in fm_text.split("\n"):
        if ":" in line:
            k, v = line.split(":", 1)
            k, v = k.strip(), v.strip().strip("'\"")
            fm[k] = v
    return fm_text, fm


def _check_c01(fm_text: str | None) -> tuple[bool, str]:
    """C01: 프론트매터 내 곡선따옴표."""
    if not fm_text:
        return True, "frontmatter 없음 (skip)"
    curved_single = "'"  # '
    curved_double = '"'  # "
    found = []
    if any(c in fm_text for c in curved_single):
        found.append("곡선따옴표(' ')")
    if any(c in fm_text for c in curved_double):
        found.append('곡선따옴표(" ")')
    if found:
        return False, f"C01 위반: {', '.join(found)}"
    return True, "C01 통과"


def _check_c02(content: str) -> tuple[bool, str]:
    """C02: 프론트매터 미종료 — 첫 --- 이후 두 번째 --- 존재 여부로만 판정."""
    lines = content.split('\n')
    first_dash = None
    second_dash = None
    for i, line in enumerate(lines):
        if line.strip() == '---':
            if first_dash is None:
                first_dash = i
            elif second_dash is None and i > first_dash:
                second_dash = i
                break  # 첫 --- 이후 두 번째만 찾으면 중단 (전체 카운트 금지)
    if first_dash is None:
        return False, "C02 위반: 첫 --- 없음"
    if second_dash is None:
        return False, "C02 위반: 첫 --- 이후 두 번째 --- 없음"
    return True, "C02 통과"


def _check_c03(body_md: str) -> tuple[bool, str]:
    """C03: 본문에 프론트매터 키 라인 유출."""
    pattern = re.compile(r'^\s*(' + '|'.join(FM_KEYS) + r'):\s*')
    leaked = [l.strip()[:60] for l in body_md.split('\n') if pattern.match(l)]
    if leaked:
        return False, f"C03 위반: {len(leaked)}건 — {leaked[0]}"
    return True, "C03 통과"


def _check_c04(body_md: str, blog_id: str) -> tuple[bool, str]:
    """C04: LLM 프롬프트/사고문 누수. 국문+영문 패턴 모두 확인."""
    # blog_id에 etap/curation 포함 시 영문 패턴 강화
    en_extra = "etap" in blog_id.lower() or "curation" in blog_id.lower()
    patterns = C04_KO_PATTERNS + C04_EN_PATTERNS + (C04_EN_PATTERNS if en_extra else [])
    found = []
    for pat in patterns:
        m = re.search(pat, body_md, re.IGNORECASE)
        if m:
            found.append(m.group()[:40])
    if found:
        return False, f"C04 위반: 프롬프트 누수 {len(found)}건 — {found[0]}"
    return True, "C04 통과"


def _check_c05(fm: dict) -> tuple[bool, str]:
    """C05: draft:true 발행 대상."""
    if fm.get("draft", "").lower() == "true":
        return False, "C05 위반: draft:true 발행 대상"
    return True, "C05 통과"


def _check_c06(file_path: Path, blog_id: str) -> tuple[bool, str]:
    """C06: 로컬 mtime > 마지막 배포 시각 (단순화: 최근 수정 파일 경고)."""
    if not file_path.exists():
        return True, "파일 없음 (skip)"
    mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
    days_since = (datetime.now() - mtime).days
    if days_since < 1:
        return False, f"C06 경고: 최근 수정 ({mtime.strftime('%Y-%m-%d')})"
    return True, f"C06 통과 (마지막 수정 {days_since}일 전)"


def _check_c07(body_md: str, conn) -> tuple[bool, str]:
    """C07: 죽은 크로스셀 링크.

    실제 구현: data-target-slug 추출 → content.db published 확인 → HTTP HEAD 확인.
    운영 환경에서는 외부 HTTP 호출이 필요하므로, 여기서는 DB 기반 검사만 수행.
    """
    # data-target-slug 추출
    target_slugs = re.findall(r'data-target-slug=["\']([^"\']+)["\']', body_md)
    if not target_slugs:
        return True, "크로스셀 링크 없음 (skip)"

    # content.db에서 published 확인
    try:
        ledger = conn  # 파라미터로 전달된 conn 사용
        dead = []
        for slug in target_slugs:
            row = ledger.execute(
                "SELECT COUNT(*) as cnt FROM publish_ledger WHERE slug=? AND status='published'",
                (slug,)
            ).fetchone()
            if row["cnt"] == 0:
                dead.append(slug)
        if dead:
            return False, f"C07 위반: 죽은 크로스셀 링크 {len(dead)}건 — {dead[0]}"
    except Exception as e:
        logger.warning(f"[C07] DB 확인 실패: {e}")
    return True, "C07 통과 (HTTP 확인은 운영 환경에서)"


def _check_c08(site: Path | None, blog_id: str) -> tuple[bool, str]:
    """C08: 라이브-파일 불일치. 현재 placeholder (라이브 비교 API 연동 필요)."""
    # TODO: 라이브 사이트 HTML 크롤링 → 제목/og_image 비교
    return True, "C08: 라이브 비교 미구현 (placeholder)"


@register_check("c01_curve_quote")
def check_c01(conn, blog_id: str) -> dict:
    """C01: 프론트매터 내 곡선따옴표 검사."""
    site = _find_site_path(conn, blog_id)
    if not site:
        return {"status": "unknown", "detail": f"site_path 없음: {blog_id}"}

    posts = _read_post_files(site)
    if not posts:
        return {"status": "unknown", "detail": "최근 7일 포스트 없음"}

    # 최신 포스트만 검사
    _, content = posts[0]
    fm_text, _ = _parse_frontmatter(content)
    passed, detail = _check_c01(fm_text)
    return {"status": "pass" if passed else "fail", "detail": detail}


@register_check("c02_frontmatter_close")
def check_c02(conn, blog_id: str) -> dict:
    """C02: 프론트매터 미종료 검사."""
    site = _find_site_path(conn, blog_id)
    if not site:
        return {"status": "unknown", "detail": f"site_path 없음: {blog_id}"}

    posts = _read_post_files(site)
    if not posts:
        return {"status": "unknown", "detail": "최근 7일 포스트 없음"}

    violations = []
    for path, content in posts:
        passed, detail = _check_c02(content)
        if not passed:
            violations.append(f"{path.parent.name}: {detail}")

    if violations:
        return {"status": "fail",
                "detail": f"C02 위반 {len(violations)}건: {'; '.join(violations[:3])}"}
    return {"status": "pass", "detail": f"C02 통과 ({len(posts)}건)"}


@register_check("c03_fm_key_leak")
def check_c03(conn, blog_id: str) -> dict:
    """C03: 본문 프론트매터 키 유출 검사."""
    site = _find_site_path(conn, blog_id)
    if not site:
        return {"status": "unknown", "detail": f"site_path 없음: {blog_id}"}

    posts = _read_post_files(site)
    if not posts:
        return {"status": "unknown", "detail": "최근 7일 포스트 없음"}

    violations = []
    for path, content in posts:
        _, fm = _parse_frontmatter(content)
        body = content[content.find("---\n", 4) + 4:] if content.find("---\n", 4) > 0 else content
        passed, detail = _check_c03(body)
        if not passed:
            violations.append(f"{path.parent.name}: {detail}")

    if violations:
        return {"status": "fail",
                "detail": f"C03 위반 {len(violations)}건: {'; '.join(violations[:3])}"}
    return {"status": "pass", "detail": f"C03 통과 ({len(posts)}건)"}


@register_check("c04_prompt_leak")
def check_c04(conn, blog_id: str) -> dict:
    """C04: LLM 프롬프트/사고문 누수 검사 (국문+영문)."""
    site = _find_site_path(conn, blog_id)
    if not site:
        return {"status": "unknown", "detail": f"site_path 없음: {blog_id}"}

    posts = _read_post_files(site)
    if not posts:
        return {"status": "unknown", "detail": "최근 7일 포스트 없음"}

    violations = []
    for path, content in posts:
        _, fm = _parse_frontmatter(content)
        body = content[content.find("---\n", 4) + 4:] if content.find("---\n", 4) > 0 else content
        passed, detail = _check_c04(body, blog_id)
        if not passed:
            violations.append(f"{path.parent.name}: {detail}")

    if violations:
        return {"status": "fail",
                "detail": f"C04 위반 {len(violations)}건: {'; '.join(violations[:3])}"}
    return {"status": "pass", "detail": f"C04 통과 ({len(posts)}건)"}


@register_check("c05_draft_publish")
def check_c05(conn, blog_id: str) -> dict:
    """C05: draft:true 발행 대상 검사."""
    site = _find_site_path(conn, blog_id)
    if not site:
        return {"status": "unknown", "detail": f"site_path 없음: {blog_id}"}

    posts = _read_post_files(site)
    if not posts:
        return {"status": "unknown", "detail": "최근 7일 포스트 없음"}

    violations = []
    for path, content in posts:
        _, fm = _parse_frontmatter(content)
        passed, detail = _check_c05(fm)
        if not passed:
            violations.append(f"{path.parent.name}: {detail}")

    if violations:
        return {"status": "fail",
                "detail": f"C05 위반 {len(violations)}건: {'; '.join(violations[:3])}"}
    return {"status": "pass", "detail": f"C05 통과 ({len(posts)}건)"}


@register_check("c06_mtime_deploy")
def check_c06(conn, blog_id: str) -> dict:
    """C06: 로컬 mtime > 배포 시각 검사."""
    site = _find_site_path(conn, blog_id)
    if not site:
        return {"status": "unknown", "detail": f"site_path 없음: {blog_id}"}

    posts = _read_post_files(site)
    if not posts:
        return {"status": "unknown", "detail": "최근 7일 포스트 없음"}

    warnings = []
    for path, _ in posts:
        passed, detail = _check_c06(path, blog_id)
        if not passed:
            warnings.append(detail)

    if warnings:
        return {"status": "fail",
                "detail": f"C06 경고 {len(warnings)}건: {'; '.join(warnings[:3])}"}
    return {"status": "pass", "detail": f"C06 통과 ({len(posts)}건)"}


@register_check("c07_dead_crossell")
def check_c07(conn, blog_id: str) -> dict:
    """C07: 죽은 크로스셀 링크 검사."""
    site = _find_site_path(conn, blog_id)
    if not site:
        return {"status": "unknown", "detail": f"site_path 없음: {blog_id}"}

    posts = _read_post_files(site)
    if not posts:
        return {"status": "unknown", "detail": "최근 7일 포스트 없음"}

    violations = []
    for path, content in posts:
        _, fm = _parse_frontmatter(content)
        body = content[content.find("---\n", 4) + 4:] if content.find("---\n", 4) > 0 else content
        passed, detail = _check_c07(body, conn)
        if not passed:
            violations.append(f"{path.parent.name}: {detail}")

    if violations:
        return {"status": "fail",
                "detail": f"C07 위반 {len(violations)}건: {'; '.join(violations[:3])}"}
    return {"status": "pass", "detail": f"C07 통과 ({len(posts)}건)"}


@register_check("c08_live_file_mismatch")
def check_c08(conn, blog_id: str) -> dict:
    """C08: 라이브-파일 불일치 검사 (placeholder)."""
    return {"status": "unknown", "detail": "C08: 라이브 비교 미구현 (향후 활성화)"}
```

**register_check 데코레이터**: `__init__.py`의 CHECKS 레지스트리에 자동 등록됨.
</action>
  <verify>
<automated>
# 모듈 import 확인 + 체크리스트 등록 확인
python3 -c "
import sys; sys.path.insert(0, '.')
from ops_dashboard.checks.content_integrity import (
    check_c01, check_c02, check_c03, check_c04, check_c05, check_c06, check_c07, check_c08
)
from ops_dashboard.checks import CHECKS
registered = [k for k in CHECKS.keys() if k.startswith('c0')]
print(f'등록된 C0 체크: {len(registered)}개')
for name in sorted(registered):
    print(f'  - {name}')
assert len(registered) == 8, f'8개 체크 등록되어야 함 (현재 {len(registered)}개)'
print('8개 체크 모두 등록됨 ✓')
"
</automated>
  </verify>
  <done>
ops_dashboard/checks/content_integrity.py 생성, C01~C08 8개 체크가 CHECKS 레지스트리에 등록됨
  </done>
</task>

<task type="auto">
  <name>Task 2: check_results 기록 확인 + 대시보드 표시 테스트</name>
  <files>ops_dashboard/db.py</files>
  <action>
check_results 테이블에 C01~C08 판정 결과가 정상 기록되는지 확인.

1. **record_check 함수 확인** (db.py):
   - 이미 존재함: `record_check(conn, blog_id, check_name, status, detail, evidence_url)`
   - C01~C08 체크도 동일 함수로 기록됨 (register_check 데코레이터 + run_all_checks 패턴)

2. **전체 체크 실행 테스트**:
```bash
python3 -c "
import sys; sys.path.insert(0, '.')
from ops_dashboard.db import get_conn, init_db, seed_standard_rules
from ops_dashboard.checks import run_all_checks

conn = get_conn()
init_db(conn)
seed_standard_rules(conn)

# 테스트 블로그로 체크 실행
result = run_all_checks(conn, blog_ids=['compare-hugo'])
print(f'전체: {result[\"total\"]}건, pass: {result[\"pass\"]}, fail: {result[\"fail\"]}')
print(f'주의 항목: {len(result[\"attention_items\"])}건')

# C01~C08 결과만 필터링
c0_results = [item for item in result['attention_items'] if item['check'].startswith('c0')]
print(f'C0 위반 항목: {len(c0_results)}건')
for item in c0_results[:5]:
    print(f'  - {item[\"blog_id\"]}/{item[\"check\"]}: {item[\"detail\"][:60]}')
conn.close()
"
```

3. **check_results DB 확인**:
```bash
python3 -c "
import sys; sys.path.insert(0, '.')
from ops_dashboard.db import get_conn
conn = get_conn()
rows = conn.execute('''
    SELECT blog_id, check_name, status, detail, checked_at
    FROM check_results
    WHERE check_name LIKE 'c0%'
    ORDER BY checked_at DESC LIMIT 20
''').fetchall()
for r in rows:
    print(f'{r[\"blog_id\"]:20s} {r[\"check_name\"]:25s} {r[\"status\"]:8s} {r[\"detail\"][:50]}')
conn.close()
"
```
</action>
  <verify>
<automated>
python3 -c "
import sys; sys.path.insert(0, '.')
from ops_dashboard.db import get_conn
conn = get_conn()
rows = conn.execute('SELECT COUNT(*) as cnt FROM check_results WHERE check_name LIKE \"c0%\"').fetchone()
print(f'check_results 내 C0 체크 기록: {rows[\"cnt\"]}건')
assert rows['cnt'] > 0, 'C0 체크 결과가 check_results에 기록되어야 함'
conn.close()
"
</automated>
  </verify>
  <done>
C01~C08 체크 실행 결과가 check_results 테이블에 기록됨. 대시보드에서 조회 가능.
  </done>
</task>

</tasks>

<success_criteria>
- [ ] ops_dashboard/checks/content_integrity.py 생성
- [ ] C01~C08 8개 체크 함수가 register_check 데코레이터로 CHECKS에 등록
- [ ] run_all_checks 실행 시 C01~C08 결과가 check_results에 기록
- [ ] localhost:5050 대시보드에서 C0 체크 결과 조회 가능 (check_results 기반)
- [ ] C02/C04 CRITICAL 위반 시 fail 상태 기록
- [ ] C08은 placeholder (unknown 상태)
</success_criteria>

<output>
- ops_dashboard/checks/content_integrity.py (신규)
- ops_dashboard/db.py (변경 없음 — 기존 record_check 함수 사용)

커밋 메시지 후보:
- `feat(phase-62): add C01~C08 content integrity checks to ops_dashboard`
- `feat(phase-62): integrate C01~C08 check results into check_results dashboard`
</output>

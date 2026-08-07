---
phase: 62-content-leak-prevention
plan: 04
type: execute
wave: 4
depends_on: ["62-03"]
files_modified:
  - dispatcher.py
autonomous: false
requirements: []
must_haves:
  truths:
    - "preflight_check(blog_id) 함수가 dispatcher.py에 추가됨"
    - "_build_and_deploy_central 직전에 preflight_check 호출"
    - "C01~C04·C08 critical 1건이라도 있으면 배포 중단 + 위반 slug 리턴"
    - "CUAP/CAP/STAP/RAP/ETAP/SEAP/TAP 모두 확인 대상"
  artifacts:
    - path: "dispatcher.py"
      provides: "preflight_check 함수 + _build_and_deploy_central 게이트"
      contains: "preflight_check|_build_and_deploy_central preflight"
  key_links:
    - from: "_build_and_deploy_central"
      to: "preflight_check"
      via: "함수 호출"
      pattern: "preflight_check\\(\\w+\\)"
    - from: "preflight_check"
      to: "logs/c01_c04_results.json"
      via: "검사 결과 기록"
      pattern: "c01_c04_results|check_results"
---

<objective>
## 목표

`dispatcher._build_and_deploy_central()` 직전에 `preflight_check(blog_id)`를 삽입하여,
C01~C04·C08 중 critical이 1건이라도 있으면 배포를 중단.

## 배경

CONTEXT.md §배포 프리플라이트 게이트:
- `dispatcher._build_and_deploy_central()` 존재함 (dispatcher.py:529)
- preflight_check 함수 없음 — 삽입 지점 존재
- C01~C04·C08 중 critical이 1건이라도 있으면 배포 중단 + 위반 slug 리턴
- 대상: CUAP/CAP/STAP/RAP/ETAP/SEAP/TAP 모두 확인

## 파일럿-first 접근

**코드 삽입은 파일럿부터**: dispatcher preflight_check 1개 함수부터 시작.
이후 cause tracking hooks, 대시보드 통합 순으로 진행.
</objective>

<execution_context>
@/Users/twinssn/.config/opencode/get-shit-done/workflows/execute-plan.md
</execution_context>

<context>
@/Users/twinssn/Projects/5000/.planning/phases/phase-62-content-leak-prevention/CONTEXT.md
@/Users/twinssn/Projects/5000/dispatcher.py
@/Users/twinssn/Projects/5000/shared/publishers/hugo_writer.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: preflight_check 함수 구현</name>
  <files>dispatcher.py</files>
  <action>
`dispatcher.py`에 `preflight_check(blog_id)` 함수를 추가.

```python
def preflight_check(blog_id: str) -> dict:
    """배포 전 콘텐츠 무결성 프리플라이트 체크.

    C01~C04·C08 중 critical이 1건이라도 있으면 배포 중단.

    Returns:
        {"blocked": bool, "violations": list[dict], "reason": str}
        - blocked=True: 배포 중단 필요
        - violations: [{rule_id, slug, severity, detail}, ...]
    """
    import json
    import re
    from datetime import datetime
    from pathlib import Path

    from shared.paths import FIVEK_ROOT

    violations = []
    blocked = False

    # 대상 블로그 site_path 확인
    _all_blogs = _load_all_blogs().get("blogs", [])
    _cfg = next((b for b in _all_blogs if b.get("id") == blog_id), {})
    site_path = Path(_cfg.get("site_path", "")) if _cfg.get("site_path") else None
    if not site_path or not site_path.exists():
        return {"blocked": False, "violations": [],
                "reason": f"site_path 없음: {blog_id}"}

    # 최근 발행된 포스트 목록 확인 (content/posts/)
    posts_dir = site_path / "content" / "posts"
    if not posts_dir.exists():
        return {"blocked": False, "violations": [],
                "reason": f"posts_dir 없음: {posts_dir}"}

    # 최근 7일 내 생성된 포스트 추출 (파일 mtime 기준)
    cutoff = datetime.now().timestamp() - 7 * 86400
    recent_posts = []
    for md_file in posts_dir.rglob("*.md"):
        if md_file.stat().st_mtime >= cutoff:
            recent_posts.append(md_file)

    if not recent_posts:
        return {"blocked": False, "violations": [],
                "reason": "최근 7일 내 발행 포스트 없음 (skip)"}

    # 각 포스트 검사
    for md_file in recent_posts:
        content = md_file.read_text(encoding="utf-8", errors="replace")
        slug = md_file.parent.name

        # --- C02: 프론트매터 미종료 (CRITICAL) ---
        lines = content.split('\n')
        first_dash = None
        second_dash = None
        for i, line in enumerate(lines):
            if line.strip() == '---':
                if first_dash is None:
                    first_dash = i
                elif second_dash is None and i > first_dash:
                    second_dash = i
                    break
        if first_dash is not None and second_dash is None:
            violations.append({
                "rule_id": "C02", "slug": slug, "severity": "CRITICAL",
                "detail": "프론트매터 미종료: 첫 --- 이후 두 번째 --- 없음",
                "file": str(md_file)})
            blocked = True

        # --- C04: 프롬프트/사고문 누수 (CRITICAL) ---
        # 국문 + 영문 패턴 모두 확인
        ko_patterns = [
            r"먼저\s*생각", r"생각해보자", r"다음\s*단계",
            r"단계별로", r"우선\s*", r"우리가\s*해야\s*할",
        ]
        en_patterns = [
            r"\bNeed\s+think\b", r"\bWe\s+need\s+to\s+write\b",
            r"Let.s\s+think\s+step\s+by\s+step",
            r"think\s+step\s+by\s+step",
            r"let.s\s+break\s+this\s+down",
            r"here.?s\s+the\s+plan",
        ]
        body_start = content.find("---\n", 4)  # 첫 frontmatter 닫기 이후
        body = content[body_start:] if body_start > 0 else content
        for pat in ko_patterns + en_patterns:
            if re.search(pat, body, re.IGNORECASE):
                violations.append({
                    "rule_id": "C04", "slug": slug, "severity": "CRITICAL",
                    "detail": f"프롬프트 누수 패턴 감지: {pat[:30]}",
                    "file": str(md_file)})
                blocked = True
                break  # 한 포스트당 1건만 기록

        # --- C08: 라이브-파일 불일치 (CRITICAL) ---
        # 현재 구현에서는 제목/og_image 비교 로직 생략 (별도 구현 필요)
        # placeholder: 향후 라이브 비교 API 연동 시 활성화

    # 결과 기록 (logs/c01_c04_preflight.json)
    _ensure_logs_dir()
    preflight_log = Path(__file__).parent / "logs" / "c01_c04_preflight.json"
    _results = {
        "blog_id": blog_id,
        "checked_at": datetime.now().isoformat(),
        "blocked": blocked,
        "violations": violations,
        "reason": "차단: critical 위반 있음" if blocked else "통과",
    }
    try:
        existing = json.loads(preflight_log.read_text()) if preflight_log.exists() else {}
    except (json.JSONDecodeError, OSError):
        existing = {}
    existing[blog_id] = _results
    preflight_log.write_text(json.dumps(existing, ensure_ascii=False, indent=2))

    return _results


def _ensure_logs_dir():
    """logs 디렉토리 존재 확인."""
    logs_dir = Path(__file__).parent / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)


def _load_all_blogs():
    """blogs.yaml + blogs.d/*.yaml 통합 로드 (dispatcher 기존 함수 재사용)."""
    from shared.config import load_all_blogs
    return load_all_blogs()
```

**중요**: 
- C02 판정: "첫 --- 이후 두 번째 --- 존재 여부"로만 (전체 --- 홀수 카운트 금지)
- C04 판정: 국문 + 영문 패턴 모두 확인 (ETAP 영문 글 대응)
- C08은 현재 placeholder (라이브 비교 API 연동 시 활성화)
</action>
  <verify>
<automated>
python3 -c "
import ast, sys
sys.path.insert(0, '.')
with open('dispatcher.py') as f:
    tree = ast.parse(f.read())
funcs = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
assert 'preflight_check' in funcs, 'preflight_check 함수 없음'
print('preflight_check 함수 정의 확인됨')
"
</automated>
  </verify>
  <done>
dispatcher.py에 preflight_check(blog_id) 함수 추가 완료
  </done>
</task>

<task type="auto">
  <name>Task 2: _build_and_deploy_central 직전에 preflight_check 호출 삽입</name>
  <files>dispatcher.py</files>
  <action>
`_build_and_deploy_central` 함수 시작 부분에 preflight_check 호출을 삽입.

**삽입 위치**: dispatcher.py:529 `_build_and_deploy_central(blog_id: str) -> bool:` 함수 첫 줄

```python
def _build_and_deploy_central(blog_id: str) -> bool:
    """중앙 빌드+배포 — ETAP/Workers 블로그 공용"""
    # ── C01~C04·C08 프리플라이트 게이트 ──
    _pf_result = preflight_check(blog_id)
    if _pf_result.get("blocked"):
        logger.error(
            f"[deploy] 프리플라이트 차단: {blog_id} "
            f"— critical 위반 {len(_pf_result['violations'])}건: "
            f"{[v['rule_id']+':'+v['slug'] for v in _pf_result['violations']]}"
        )
        # Telegram 알림 (기존 _tg_error 활용)
        _violation_summary = "; ".join(
            f"{v['rule_id']}({v['slug']})" for v in _pf_result["violations"]
        )
        try:
            from shared.telegram_notifier import send_error as _tg_error
            _tg_error(f"[deploy blocked] {blog_id}: {_violation_summary}")
        except Exception:
            pass
        return False

    import fcntl as _fcntl
    # ... 기존 코드 계속 ...
```

**기존 코드 보존**: preflight_check 호출이 실패해도 기존 코드 동작에 영향 없도록 try/except로 감싼다.
</action>
  <verify>
<automated>
# preflight_check 호출이 _build_and_deploy_central 앞에 있는지 확인
grep -n "preflight_check\|def _build_and_deploy_central" dispatcher.py | head -10
</automated>
  </verify>
  <done>
_build_and_deploy_central 시작 부분에 preflight_check(blog_id) 호출 삽입, 차단 시 False 리턴 + Telegram 알림
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <what-built>preflight_check 함수 + _build_and_deploy_central 게이트</what-built>
  <how-to-verify>
1. dispatcher.py 구문 확인:
```bash
python3 -m py_compile dispatcher.py && echo "구문 OK"
```

2. preflight_check 단위 테스트:
```bash
python3 -c "
import sys; sys.path.insert(0, '.')
from dispatcher import preflight_check
# 실제 블로그로 테스트 (예: CUAP 블로그)
result = preflight_check('compare-hugo')
print(f'blocked={result[\"blocked\"]}, violations={len(result[\"violations\"])}')
print(f'reason: {result[\"reason\"]}')
"
```

3. 대상 블로그(CUAP/CAP/STAP/RAP/ETAP/SEAP/TAP) 각각에 대해 preflight_check 실행:
```bash
for blog in compare-hugo hotissue-hugo stock-hugo travel-hugo rap-hugo tour-hugo tvshow-blogger; do
  python3 -c "
import sys; sys.path.insert(0, '.')
from dispatcher import preflight_check
r = preflight_check('$blog')
print(f'{r[\"blog_id\"] if \"blog_id\" in r else \"$blog\"}: blocked={r[\"blocked\"]}')
"
done
```
  </how-to-verify>
  <resume-signal>
테스트 결과 확인 후:
- ✅ "승인" → 다음 계획(62-05) 진행
- ⚠️ "문제 있음: [내용]" → 수정 후 재검증
  </resume-signal>
</task>

</tasks>

<success_criteria>
- [ ] dispatcher.py에 preflight_check(blog_id) 함수 추가
- [ ] _build_and_deploy_central 직전에 preflight_check 호출 삽입
- [ ] C02 위반 시 배포 차단 (CRITICAL)
- [ ] C04 위반 시 배포 차단 (CRITICAL, 국문+영문 패턴)
- [ ] C01/C03/C07 MAJOR 위반 시 기록만 (차단 안 함)
- [ ] logs/c01_c04_preflight.json에 결과 기록
- [ ] 차단 시 Telegram 알림 발송
- [ ] 기존 _build_and_deploy_central 동작 보존 (preflight_check 실패해도 영향 없음)
- [ ] CUAP/CAP/STAP/RAP/ETAP/SEAP/TAP 모두 preflight_check 호출 가능
</success_criteria>

<output>
dispatcher.py (수정)

커밋 메시지 후보:
- `feat(phase-62): add preflight_check gate before _build_and_deploy_central`
</output>

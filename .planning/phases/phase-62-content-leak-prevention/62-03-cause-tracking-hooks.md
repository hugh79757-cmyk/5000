---
phase: 62-content-leak-prevention
plan: 03
type: execute
wave: 3
depends_on: ["62-02"]
files_modified:
  - shared/publishers/hugo_writer.py
  - shared/leak_tracker.py
autonomous: true
requirements: []
must_haves:
  truths:
    - "원인추적 훅 3개 지점이 모두 구현됨"
    - "생성 직후 훅: AI 작성 완료 후, humanizer 투입 전 C01/C04 검사"
    - "humanizer 통과 직후 훅: humanizer 변환 후, _write_hugo_post 전 C01/C04 검사"
    - "_write_hugo_post 저장 직전 훅: 파일 저장 직전 최종 C01/C04 검사"
    - "logs/leak-origin.log에 stage+slug+패턴 형태로 최초 탐지 지점 기록"
  artifacts:
    - path: "shared/leak_tracker.py"
      provides: "C01/C04 원인추적 훅 모듈"
      min_lines: 150
    - path: "shared/publishers/hugo_writer.py"
      provides: "원인추적 훅 삽입 지점 3곳"
      contains: "_check_leak_immediately_after|leak_tracker"
  key_links:
    - from: "shared/leak_tracker.py"
      to: "logs/leak-origin.log"
      via: "파일 append"
      pattern: "leak-origin\\.log"
    - from: "_write_hugo_post"
      to: "leak_tracker.check_c01_c04"
      via: "함수 호출"
      pattern: "leak_tracker\\.check_c01_c04"
---

<objective>
## 목표

C01(곡선따옴표)과 C04(프롬프트 누수)를 파이프라인 각 단계 경계에서 검사하는 **원인추적 훅 3개 지점**을 구현.

## 배경

CONTEXT.md §원인추적 훅 설계:
- C01과 C04를 파이프라인 각 단계 경계에서 검사해 **어느 단계에서 처음 나타나는지** 특정
- 3개 삽입 지점: (a) 생성 직후, (b) humanizer 통과 직후, (c) _write_hugo_post 저장 직전
- 같은 slug에 대해 여러 지점에서 탐지되면 **첫 지점만 기록** (중복 방지)

**중요**: 삽입 지점과 로직만 설계. 코드 삽입은 Phase 62 게이트(62-04/62-05)에서 수행.
</objective>

<execution_context>
@/Users/twinssn/.config/opencode/get-shit-done/workflows/execute-plan.md
</execution_context>

<context>
@/Users/twinssn/Projects/5000/.planning/phases/phase-62-content-leak-prevention/CONTEXT.md
@/Users/twinssn/Projects/5000/shared/publishers/hugo_writer.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: leak_tracker.py 모듈 생성</name>
  <files>shared/leak_tracker.py</files>
  <action>
`shared/leak_tracker.py` 모듈을 새로 생성한다.

```python
"""shared/leak_tracker.py — C01/C04 원인추적 훅

파이프라인 각 단계 경계에서 C01(곡선따옴표)과 C04(프롬프트 누수)를 검사하여
처음 탐지된 지점을 logs/leak-origin.log에 기록한다.

3개 삽입 지점:
  (a) 생성 직후: AI 작성 완료 후, humanizer 투입 전
  (b) humanizer 통과 직후: humanizer 변환 후, _write_hugo_post 전
  (c) _write_hugo_post 저장 직전: 파일 저장 직전 최종 검사
"""
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# 로그 파일 경로
LEAK_LOG_PATH = Path(__file__).parent.parent / "logs" / "leak-origin.log"

# C01: 곡선따옴표 (U+2018, U+2019, U+201C, U+201D)
_C01_CURVED_SINGLE = "'"  # '
_C01_CURVED_DOUBLE = '"'  # "

# C04: 프롬프트 누수 패턴 (국문 + 영문)
_C04_KO_PATTERNS = [
    r"먼저\s*생각", r"생각해보자", r"생각해\s*보자",
    r"다음\s*단계", r"단계별로", r"우선\s*",
    r"우리가\s*해야\s*할", r"필요한\s*것",
    r"생각\s*과정", r"결론부터\s*말하면",
]
_C04_EN_PATTERNS = [
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


def _ensure_log_dir():
    """로그 디렉토리 존재 확인."""
    LEAK_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)


def _log_leak_origin(stage: str, slug: str, rule_id: str, pattern_type: str, snippet: str) -> None:
    """leak-origin.log에 최초 탐지 기록.

    같은 slug에 대해 여러 지점에서 탐지되면 첫 지점만 기록(중복 방지).
    """
    _ensure_log_dir()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] stage={stage} slug={slug} rule={rule_id} type={pattern_type} snippet={snippet[:100]}\n"
    with open(LEAK_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(log_line)
    logger.warning(f"[LEAK-ORIGIN] {log_line.strip()}")


# 이미 기록된 slug 추적 (중복 방지 — 메모리 내)
 _logged_slugs: set[str] = set()


def _is_logged(slug: str) -> bool:
    """해당 slug가 이미 기록되었는지 확인."""
    return slug in _logged_slugs


def _mark_logged(slug: str) -> None:
    """해당 slug 기록 완료 표시."""
    _logged_slugs.add(slug)


def check_c01_c04(
    content: str,
    stage: str,
    slug: str,
    locale: str = "ko",
    log_originally: bool = True,
) -> dict:
    """C01(곡선따옴표) + C04(프롬프트 누수) 검사.

    Args:
        content: 검사 대상 텍스트 (frontmatter 또는 body)
        stage: 삽입 지점 식별자 ("after_generation" / "after_humanizer" / "before_write")
        slug: 포스트 slug
        locale: "ko" 또는 "en" (C04 패턴 선택)
        log_originally: True면 최초 탐지 지점만 기록, False면 기록 안 함 (재검증용)

    Returns:
        {"c01_detected": bool, "c04_detected": bool,
         "c01_patterns": list[str], "c04_patterns": list[str],
         "first_stage": str | None}  # 처음 탐지된 stage (없으면 None)
    """
    result = {
        "c01_detected": False,
        "c04_detected": False,
        "c01_patterns": [],
        "c04_patterns": [],
        "first_stage": None,
    }

    # C01 검사
    c01_found = []
    if any(c in content for c in _C01_CURVED_SINGLE):
        c01_found.append("곡선따옴표(' ')")
        result["c01_detected"] = True
    if any(c in content for c in _C01_CURVED_DOUBLE):
        c01_found.append('곡선따옴표(" ")')
        result["c01_detected"] = True
    result["c01_patterns"] = c01_found

    # C04 검사
    c04_found = []
    patterns = _C04_EN_PATTERNS if locale == "en" else _C04_KO_PATTERNS
    for pat in patterns:
        m = re.search(pat, content, re.IGNORECASE)
        if m:
            c04_found.append(m.group()[:40])
    if c04_found:
        result["c04_detected"] = True
        result["c04_patterns"] = c04_found

    # 로그 기록 (최초 탐지 지점만)
    if log_originally and (result["c01_detected"] or result["c04_detected"]):
        if not _is_logged(slug):
            _mark_logged(slug)
            if result["c01_detected"]:
                _log_leak_origin(stage, slug, "C01", "curve_quote", c01_found[0])
                result["first_stage"] = stage if result["first_stage"] is None else result["first_stage"]
            if result["c04_detected"]:
                _log_leak_origin(stage, slug, "C04", "prompt_leak", c04_found[0])
                result["first_stage"] = stage if result["first_stage"] is None else result["first_stage"]
        else:
            # 이미 기록된 slug — 추가 기록 안 함 (중복 방지)
            pass

    return result


# 후크 등록용 전역 저장소
_HOOKS: list[dict] = []


def register_hook(stage: str, check_fn: Callable[[str, str], dict]) -> None:
    """원인추적 훅 등록.

    Args:
        stage: 지점 식별자 ("after_generation", "after_humanizer", "before_write")
        check_fn: (content, slug) → {"c01_detected": bool, "c04_detected": bool, ...}
    """
    _HOOKS.append({"stage": stage, "check_fn": check_fn})
    logger.info(f"[LEAK-TRACKER] Hook registered: {stage}")


def run_hooks(content: str, slug: str, stage: str, locale: str = "ko") -> dict:
    """해당 stage의 훅을 실행하고 결과 반환."""
    results = []
    for hook in _HOOKS:
        if hook["stage"] == stage:
            result = hook["check_fn"](content, slug)
            result["stage"] = stage
            results.append(result)
    return {"stage": stage, "results": results}
</action>
  <verify>
<automated>
python3 -c "
import sys; sys.path.insert(0, '.')
from shared.leak_tracker import check_c01_c04, _C01_CURVED_SINGLE, _C04_KO_PATTERNS
# C01 테스트
r = check_c01_c04(\"title: '안녕하세요'\", 'after_generation', 'test-slug')
assert r['c01_detected'] == False, '직선 따옴표는 C01 위반 아님'
r2 = check_c01_c04(\"title: '안녕하세요'\", 'after_generation', 'test-slug')
assert r2['c01_detected'] == True, '곡선따옴표는 C01 위반'
# C04 테스트
r3 = check_c01_c04('먼저 생각해보자', 'after_generation', 'test-cot', locale='ko')
assert r3['c04_detected'] == True, 'C04 국문 패턴 탐지 실패'
print('leak_tracker 단위 테스트 통과')
"
</automated>
  </verify>
  <done>
shared/leak_tracker.py 생성, check_c01_c04 함수 + 로그 기록 작동 확인
  </done>
</task>

<task type="auto">
  <name>Task 2: hugo_writer.py에 훅 삽입 (3개 지점)</name>
  <files>shared/publishers/hugo_writer.py</files>
  <action>
`shared/publishers/hugo_writer.py`에 원인추적 훅 3개 지점을 삽입한다.

**지점 (a): 생성 직후** — AI 작성 완료 후, humanizer 투입 전
- 삽입 위치: `_write_hugo_post` 함수 시작부, `body_md = _clean_body(...)` 직전
- 검사 대상: raw body_md (AI 생성물 원본)
```python
# ── C01/C04 원인추적 훅 (a) 생성 직후 ──
try:
    from shared.leak_tracker import check_c01_c04
    _leak_result = check_c01_c04(body_md, "after_generation", slug, locale="ko")
    if _leak_result["c01_detected"] or _leak_result["c04_detected"]:
        logger.info(f"[LEAK-TRACKER] (a)생성직후 C01:{_leak_result['c01_detected']} C04:{_leak_result['c04_detected']} {slug}")
except ImportError:
    pass
```

**지점 (b): humanizer 통과 직후** — `_clean_body` 호출 후, 저장 전
- 삽입 위치: `body_md = _clean_body(body_md, site_path=site_path)` 다음 줄
- 검사 대상: humanizer 처리 후 body_md
```python
# ── C01/C04 원인추적 훅 (b) humanizer 통과 직후 ──
try:
    from shared.leak_tracker import check_c01_c04
    _leak_result = check_c01_c04(body_md, "after_humanizer", slug, locale="ko")
    if _leak_result["c01_detected"] or _leak_result["c04_detected"]:
        logger.info(f"[LEAK-TRACKER] (b)humanizer후 C01:{_leak_result['c01_detected']} C04:{_leak_result['c04_detected']} {slug}")
except ImportError:
    pass
```

**지점 (c): _write_hugo_post 저장 직전** — `content = fm + body_md` 이후, 파일 저장 직전
- 삽입 위치: `_ok, _err = _validate_frontmatter(fm)` 직전
- 검사 대상: 최종 content (fm + body_md)
```python
# ── C01/C04 원인추적 훅 (c) 저장 직전 ──
try:
    from shared.leak_tracker import check_c01_c04
    _leak_result = check_c01_c04(content, "before_write", slug, locale="ko")
    if _leak_result["c01_detected"] or _leak_result["c04_detected"]:
        logger.warning(f"[LEAK-TRACKER] (c)저장직전 C01:{_leak_result['c01_detected']} C04:{_leak_result['c04_detected']} — 배포중단 대상 {slug}")
        return {"success": False, "error": f"leak_detected: C01={_leak_result['c01_detected']}, C04={_leak_result['c04_detected']}"}
except ImportError:
    pass
```

**ETAP 파이프라인**: `_write_hugo_post_etap`도 동일한 3개 지점 필요 (내부에서 `_write_hugo_post` 호출하므로 (c)만 적용되지만, 생성 직후 (a)는 ETAP article content에 대해 별도 필요).

ETAP의 경우 `_write_hugo_post_etap` 시작부에 (a) 지점 추가:
```python
# ETAP (a) 생성 직후
content = article["content"]
try:
    from shared.leak_tracker import check_c01_c04
    _leak_result = check_c01_c04(content, "after_generation_etap", slug, locale="en")
    if _leak_result["c04_detected"]:
        logger.info(f"[LEAK-TRACKER] (a)ETAP생성직후 C04:{_leak_result['c04_detected']} {slug}")
except ImportError:
    pass
```

**주의**: 
- 로그 기록 로직은 `leak_tracker.py`가 담당 (hugo_writer.py는 호출만)
- 같은 slug에 대한 중복 로깅 방지: leak_tracker 내부 `_logged_slugs` 세트 사용
- `_write_hugo_post` (c) 지점에서는 탐지 시 발행 중단 (return {"success": False})
</action>
  <verify>
<automated>
# hugo_writer.py에 훅 삽입 확인
grep -n "leak_tracker\|LEAK-TRACKER" shared/publishers/hugo_writer.py | head -20

# 로그 파일 생성 확인 (실제 발행 없이 모듈 import만으로)
python3 -c "
import sys; sys.path.insert(0, '.')
from shared import leak_tracker
leak_tracker._ensure_log_dir()
print('logs 디렉토리 존재:', leak_tracker.LEAK_LOG_PATH.parent.exists())
"
</automated>
  </verify>
  <done>
shared/publishers/hugo_writer.py에 3개 지점 훅 삽입. (c) 지점에서 탐지 시 발행 중단.
  </done>
</task>

</tasks>

<success_criteria>
- [ ] shared/leak_tracker.py 모듈 생성, check_c01_c04 함수 작동
- [ ] logs/leak-origin.log에 stage+slug+패턴 형태로 기록
- [ ] hugo_writer.py (a) 생성 직후 훅: _clean_body 직전 삽입
- [ ] hugo_writer.py (b) humanizer 통과 직후 훅: _clean_body 직후 삽입
- [ ] hugo_writer.py (c) 저장 직전 훅: _validate_frontmatter 직전 삽입, 탐지 시 발행 중단
- [ ] ETAP: _write_hugo_post_etap (a) 지점 영문 locale="en"으로 삽입
- [ ] 동일 slug 중복 기록 방지 작동
</success_criteria>

<output>
- shared/leak_tracker.py (신규)
- shared/publishers/hugo_writer.py (수정)

커밋 메시지 후보:
- `feat(phase-62): add leak_tracker module for C01/C04 cause tracking`
- `feat(phase-62): add C01/C04 cause tracking hooks at 3 pipeline stages`
</output>

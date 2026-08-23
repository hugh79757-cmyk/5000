# TECH_DEBT_SCHEDULER_SYNTAX_SCAN.md

> **등록 시각**: 2026-08-19 08:30 KST
> **심각도**: 높음 (scheduler 전체 시작 차단)
> **상태**: 미해결 — 안정화 종료 전 구현 금지

---

## 문제 설명

`scheduler.py`의 `_check_python_syntax()`가 프로젝트 루트의 **모든 .py 파일**을 `ast.parse()`로 스캔. 하나라도 SyntaxError가 있으면 `sys.exit(1)`로 종료.

### 발생 사고

| 항목 | 값 |
|------|-----|
| 파일 | `patch_rotation2.py:50` — unterminated string literal |
| 영향 | scheduler.py 시작 자체가 차단됨 |
| pick-hugo 영향 | 스케줄 미실행 → 1차 canary 실패 (08:03) |
| 조치 | `patch_rotation2.py`를 `/tmp/5000_patches/`로 이동 |
| 잔존 위험 | 유사 임의 스크립트가 다시 프로젝트 루트에 생성되면 재발 |

### 근본 원인

`_check_python_syntax()`는 git 추적 여부와 무관하게 **전체 .py 파일**을 스캔. `shared/`, `pipelines/`, `scripts/` 외에도 임의 패치 스크립트(`patch_*.py`, `temp_*.py` 등)까지 포함.

---

## 제안 해결안: 격리 디렉터리 + 추적 파일 한정 검사 + 경고 모드

### 1단계: 격리 디렉터리 격리

```
# 현재
scheduler.py → 전체 .py 스캔 → SyntaxError → FATAL

# 변경 후
scheduler.py → 격리 디렉터리(_patches/) 제외 → git 추적 파일만 스캔 → SyntaxError → WARN (FATAL 아님)
```

### 2단계: 추적 파일 한정 검사

```python
def _check_python_syntax() -> None:
    """git 추적 파일만 문법 검사 — 임의 스크립트 격리"""
    import subprocess
    # git 추적 파일 목록
    tracked = subprocess.check_output(
        ["git", "ls-files", "*.py"], text=True
    ).strip().splitlines()
    errors = []
    for fpath in tracked:
        if not os.path.isfile(fpath):
            continue
        try:
            with open(fpath, encoding="utf-8") as fh:
                ast.parse(fh.read())
        except SyntaxError as e:
            errors.append(f"{fpath}:{e.lineno} — {e.msg}")
    if errors:
        # 경고 모드: FATAL 대신 WARNING + 로그
        print(f"[WARN] 문법 오류 발견 ({len(errors)}건) — 스케줄은 계속됩니다")
        for err in errors:
            print(f"  ⚠️  {err}", file=sys.stderr)
        # 로그 파일에 기록 (FATAL 아님)
        logger.warning(f"Python syntax errors: {errors}")
    # FATAL 제거: syntax error가 있어도 scheduler 시작
```

### 3단계: 경고 모드

| 현재 동작 | 변경 후 |
|-----------|---------|
| SyntaxError → `sys.exit(1)` | SyntaxError → `logger.warning()` + 로그 파일 |
| 1개 파일 오류로 전체 차단 | 개별 파일 오류는 로그만, scheduler 시작 |
| git 미추적 파일 포함 | git 추적 파일만 검사 |

### 구현 범위

| 항목 | 설명 |
|------|------|
| 변경 파일 | `scheduler.py` — `_check_python_syntax()` 함수 |
| 영향 범위 | scheduler 시작 로직만 |
| 테스트 | 기존 테스트 + SyntaxError 시 경고 로그 확인 테스트 1건 |
| 리스크 | 낮음 — 기존 동작의 FATAL→WARN 변경 |

### 구현 전제 조건

- [ ] pick-hugo 3회 연속 발행 성공 확인
- [ ] 24시간 안정화 기간 경과
- [ ] `patch_rotation2.py` 격리 상태 유지 확인

---

## patch_rotation2.py 격리 상태

| 항목 | 값 |
|------|-----|
| 원래 경로 | `/Users/twinssn/Projects/5000/patch_rotation2.py` |
| 현재 경로 | `/tmp/5000_patches/patch_rotation2.py` |
| MD5 | `058fe70989a7a0dee77d7733de70cf1a` |
| SHA256 | `4f36462d5a24aba2bb3c822bfa2b3096c3613487e887023664b891ae96d1ab8d` |
| 파일 크기 | 3596 bytes |
| 생성 시각 | 2026-08-18 23:41 KST |
| git 추적 | ❌ 미추적 |
| 참조 건수 | 0건 (어디서도 import/exec 안 됨) |
| 문법 오류 | line 50: unterminated string literal |
| 조치 | 삭제·수정 금지 — 격리 유지 |

---

> **이 문서는 기술부채 등록입니다. 안정화 종료 전 코드 변경은 수행하지 않았습니다.**

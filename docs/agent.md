# Agent.md — 5000 프로젝트 세션 기록

## 세션: 2026-06-30T12:00+09:00

### 발견된 문제

- **증상**: 2026-06-27 ~ 06-30 (4일간) 전 블로그 발행 중단
- **로그**: `shared/validators.py` line 156 `IndentationError: expected an indented block after 'if' statement on line 155`
- **원인**: `_check_naver_map()` 함수 내 `if not has_map:` 뒤에 본문 블록 누락. `def is_korean_content()`가 실수로 `if` 블록 body로 들여쓰기되어 Python 구문 오류 발생

### 조치

1. `shared/validators.py:155` — `if not has_map:` 아래 `return issues` 추가
2. `shared/validators.py:156` — `def is_korean_content` 들여쓰기 해제 → 모듈 레벨로 복원
3. `scheduler.py:104` — `_check_python_syntax()` 함수 추가 (전체 `.py` `ast.parse()` 구문 검증)
4. 스케줄러 재시작 (`launchctl stop/start com.5000.scheduler`)

### 재발방지

`_check_python_syntax()`가 scheduler 시작 시 전체 `.py` 파일의 `SyntaxError`/`IndentationError`를 검증. 발견 시 `sys.exit(1)`로 즉시 실패 처리.

### 세션 종료 시 문서 업데이트 규칙

- `agent.md`: 현재 세션에서 발견된 문제/조치/재발방지 기록
- `tech.md`: 시스템 구조/설계 결정사항 변경 시 업데이트
- `status.md`: 발행 현황/블로그 상태 변경 시 업데이트

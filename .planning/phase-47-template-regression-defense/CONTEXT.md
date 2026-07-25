# Phase 47 Context Decisions

> 생성: 2026-07-25
> 방식: gsd-discuss-phase workflow

---

## 이 토론을 시작하게 된 이유

이전 세션(템플릿 수정 작업)에서 **ADSENSE-GUIDE.md라는 공식 표준 문서가 존재함에도 이를 읽지 않고** 임의로 stock-hugo의 single.html을 Congo 원본 기반으로 재작성했다. 그 결과:
- 의도하지 않은 템플릿 구조 변경 발생
- "광고는 나오는데 타이틀이 사라진다"거나 "타이틀 상단 광고가 안 보인다"는 식의 **엉뚱한 작업**이 반복됨
- 원본 대비 증분(increment)이 아닌 완전 재작성(full rewrite)이 문제의 근본 원인

이러한 회귀(regression)를 방지하기 위해 **Phase 47**에서 방어 로직을 설계하기로 결정.

---

## 논의된 결정 사항

### 1. 방어 범위
- **결정**: STAP 6개 블로그(dividend, etf, finance, ipo, sector, stock)에 우선 적용
- stock-hugo(Congo 테마)도 포함하되, **별도 baseline 적용**
- 추후 확장 가능 (현재는 STAP으로 제한)

### 2. 문서 준수 강제 — PLAN.md 참조문서 필드
- **결정**: PLAN.md에 `ref_docs` 필드를 필수로 포함
  - 작업 유형에 따라 참조 문서 선언 (템플릿 → ADSENSE-GUIDE.md, 설정 → CONVENTIONS.md 등)
  - execute-phase 첫 task에서 해당 문서를 **반드시 읽도록 강제**
  - 읽지 않으면 execute-phase 진행 불가

### 3. 증분 감지 — PLAN.md 예상 diff + 실행 후 검증
- **결정**: PLAN.md에 **변경 요약(예상 diff)** 항목 추가
  - 수정할 파일과 예상 변경 내용(증분 추가 / 몇 줄 변경 등)을 plan에 명시
  - execute-phase 완료 후 **예상 diff vs 실제 diff** 비교
  - 예상치 못한 삭제(deletion) 발견 시 조치

### 4. 경보 체계
- **결정**: 위반 시 **실행 자체를 차단(BLOCK)** — 경고만 하지 않고 진행 불가
- 즉: 검증 통과 못하면 pipeline/실행이 중단되어야 함

### 5. GSD workflow 통합 단계
- **결정**: **plan-phase 단계**에서 검증 수행
  - plan에 예상 diff 명시
  - execute에서 plan 준수 확인
  - verify에서 최종 확인

---

## 아직 결정 안됨

### A. BLOCK의 구체적 기준
- deletion 1개만 있어도 즉시 차단? 일정 threshold 허용?
- `with` → `if` 변환처럼 동등한 변경과 실제 기능 소실을 어떻게 구분할지?

### B. Telegram 알림 병행 여부
- BLOCK과 함께 Telegram 알림을 보낼지?
- 아니면 stdout + exit code로만 처리할지?

### C. 참조 문서 목록 관리 방식
- `ref_docs` 필드에 들어갈 문서 목록(문서명 → 경로 매핑)을 누가 관리?
- AGENTS.md에 통합? 별도 manifest 파일?
- 문서가 존재하는지 없는지 검증은 어떻게?

### D. 검증 스크립트 구현 위치
- scripts/ 아래 별도 스크립트?
- gsd-sdk 플러그인?
- plan-phase workflow 자체에 내장?

### E. pre-commit hook 도입 여부
- gsd workflow 외에 git pre-commit 단계에서도 방어할지?
- plan-phase 검증과 중복되지 않도록 어떻게 설계할지?

---

## 다음 단계
- 위 "아직 결정 안됨" 항목들에 대한 추가 논의 필요
- 논의 완료 후 `/gsd-plan-phase phase-47`으로 상세 플랜 수립

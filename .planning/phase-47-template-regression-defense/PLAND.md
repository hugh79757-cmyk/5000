# Phase 47 — Hugo 템플릿 회귀 방어 로직 설계

## Objective
Hugo `single.html` 템플릿 수정 시 기능 소실(Hero, TOC, 관련글, 페이지네이션, 시리즈, 주가 차트 등)이 재발하지 않도록 방어 로직을 설계하고 구현한다.

## Context
- 이전 세션들에서 템플릿을 통째로 새로 작성하여 Hero, TOC, 관련글, 페이지네이션 등이 소실되는 회귀(regression)가 반복됨
- AGENTS.md Section 4에 템플릿 수정 규칙(원본 기준선, 증분 추가, diff 검증)이 추가됨
- STAP 블로그 6개 중 stock-hugo(Congo 테마)는 아직 템플릿 구조가 정리되지 않음
- ADSENSE-GUIDE.md를 참조하지 않고 작업하여 의도와 다른 수정이 발생함

## Task List
- [ ] ADSENSE-GUIDE.md 읽고 현재 stock-hugo 템플릿 상태 분석
- [ ] 기존 stock-hugo single.html(63줄 custom)의 각 요소(차트, 광고, 메타 등) 역할 파악
- [ ] 각 블로그별 템플릿 변경 이력 감사 (git log)
- [ ] 방어 로직 설계: integrity-checker 범위 결정
- [ ] scripts/integrity-checker.sh 재작성 (선택 시)
- [ ] 방어 로직을 CI/pre-commit/pipeline에 통합할지 결정
- [ ] ROADMAP.md 업데이트

---
slug: llm-leak-all-blogs
date: 2026-08-05
status: in-progress
scope: cap-tap-hugo-blogs
---

# Quick Task: LLM 오염 전수 재조사 및 공통 writer 근본 수정 (CAP + TAP)

## Description
cap 분기의 모든 Hugo 블로그 + TAP 분기의 모든 Hugo 블로그에서 LLM 사고과정/프롬프트
지시문/다국어 누수 오염 글을 재조사해 draft로 되돌리고, 공통 writer(`shared/ai_writer.py`
기반 파이프라인)의 파싱 결함을 근본 수정한다. 이전 hotissue 스캔은 한국어 패턴만
잡아 불완전했으므로 확장 시그니처로 재실행한다.

## Constraint / Scope
- 대상: CAP 8개(compare, deal, ev, guide, hotissue, tco, rank, pick) + TAP 5개(travel, travel1, travel2, travel3, travel4) Hugo 블로그
- 제외: Blogger 플랫폼 블로그(tap-blogger, tvshow-blogger, ud-blogger), 티스토리 계열 — 보고만 하고 수정 금지
- 파일 전체 재작성 금지, 라인 편집만
- 실발행/push 금지. 0·2·4단계 각각 별도 커밋
- hotissue-hugo는 1차 수정 완료 상태(ai_response_parser.py, 7건 draft) — 재스캔 대조 필수

## Phase 0 — 범위 확정 및 발행 정지 [커밋]
- config/blogs.d/에서 CAP/TAP Hugo 블로그 확정 (완료됨: CAP 8, TAP 5)
- 대상 블로그 status → paused (백업 → 라인 편집 → diff → YAML 검증)
- hotissue-hugo는 이미 paused (변경 불필요)
- Blogger/티스토리 계열: 수정 없이 목록 보고

## Phase 1 — 오염 시그니처 확장 및 전수 재조사
- 기존 7개 한국어 패턴 + 신규 시그니처:
  - 영어 사고과정: "The user has provided", "let me re-read", "Wait,", "we need to",
    "Let me", "I should", "Actually,", "First," 등 메타 문장
  - CJK 누수: 간체 키워드(我们, 需要, 根据, 注意, 规则, 禁止) + 한자 비중 과다 구간
  - 프롬프트 지시문 노출: "bold-list로 정리", "테이블 금지", "1~2문장으로 소개",
    "H2 없이", "최소 \d+문장", "~를 명시해야", "금지 표현", "체크포인트", "구조:", "도입부"
  - 금지어 역노출: "확인해 보시기 필요합니다", "보시기 필요합니다" 등 문법 파괴형
  - 테스트/더미 글, raw slug 제목, 의미없는 선행문자(ㅇㄴ 등)
- 블로그별 파일경로|매칭패턴|언어|심각도 표 출력
- hotissue 재스캔 결과 기존 7건 대비 증감 대조 보고

## Phase 2 — draft 전환 [커밋]
- 탐지된 전체 글 프론트매터 draft: true 라인 편집 (본문 불변)
- 블로그별 변경 건수 보고

## Phase 3 — 공통 writer 근본 진단
- (1) ai_response_parser가 한국어 문자열 매칭만 하는지
- (2) reasoning_content 분리 / thinking 태그 스트립 / "출력은 TITLE/BODY만" 방어 존재 여부
- (3) travel writer(hotissue)가 car writer와 같은 모듈인지 복제본인지
  - 확인 결과: shared/ai_writer.py 공통, ai_response_parser는 generate_car에만 통합됨 (travel 미적용)

## Phase 4 — 근본 수정 [커밋]
- (a) reasoning/thinking 구조적 분리 (reasoning_content 미사용 또는 thinking 태그 스트립)
- (b) 출력 계약 위반 시 무조건 폴백 재생성, raw 통과 금지
- (c) 누수 탐지기 언어 불문 강화 (CJK 비율, 라틴 문장 비율, 지시문 키워드)
- (d) 공통 모듈화: ai_writer.generate() 수준에서 모든 호출자가 방어 공유
- (e) 발행 전 게이트 "누수 0건" 필수

## Phase 5 — 검증
- 대상 블로그별 dry-run(force_draft) 2건 생성
- (a) 다국어 누수 0건 (b) 지시문 노출 0건 (c) 금지어 역노출 0건 (d) 제목·본문 정상 구조
- 블로그별 결과 표 보고

## Commit Plan
1. `fix(cap-tap): 오염 대상 블로그 발행 정지` (Phase 0)
2. `fix(cap-tap): 오염 글 draft 전환 N건` (Phase 2)
3. `fix(shared): LLM 누수 공통 방어 강화` (Phase 4)

# Phase 61: Pipeline Standardization & Branch Renewal - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-07
**Phase:** 61-Pipeline Standardization & Branch Renewal
**Areas discussed:** 리뉴얼 우선순위, 진행 방식

---

## 리뉴얼 우선순위 (복수 선택)

| Option | Description | Selected |
|--------|-------------|----------|
| 파이프라인 코드 구조 통일 | 7개 분기가 동일 모듈 골격 재편 | ✓ |
| config 스키마 통일 | blogs.d/*.yaml 표준 스키마 + 검증 도구 | ✓ |
| 실행 방식 통일 | STAP/TAP subprocess 러너 공용화 | ✓ |
| 외부 프로젝트 5000 통합 | TAP/STAP을 5000 표준 계약에 정합 | ✓ |
| 새 분기 생성 도구 | scaffold_branch.py (ETAP 35쌍 중복 근절) | ✓ |

**User's choice:** 5개 목표 전부 선택
**Notes:** 리뉴얼의 최우선 목표로 구조·스키마·실행방식·외부통합·도구 모두 포함. 단, 외부 프로젝트 통합은 "독립 저장소 흡수 병합"이 아닌 "표준 계약 정합" 방향으로 해석 (물리적 병합은 별도 Phase로 분리 — Deferred).

---

## 진행 방식

| Option | Description | Selected |
|--------|-------------|----------|
| 이 계획을 GSD Phase로 공식화 | /gsd-plan-phase로 정식 Phase 문서화 | ✓ |
| 우선 검토 후 재논의 | 계획 검토 후 다시 논의 | |
| 특정 단계만 상세화 | pilot 단계만 구체 설계 | |

**User's choice:** GSD Phase로 공식화
**Notes:** Phase 61로 ROADMAP 등록 완료. Phase 60 번호는 기존 비공식 phase(phase-60-publish-investigation-and-hardening)와 충돌하여 61로 재지정.

---

## Claude's Discretion

- 표준 run(cfg) 반환 키 세트는 파이프라인별 반환값 실측 후 계획 단계에서 확정
- 분기 전환 시 구조 변경 vs 동작 변경 분리 기준
- 레거시 .bak 정리 대상·보존 기준

## Deferred Ideas

- 외부 프로젝트 물리적 흡수 병합 → 별도 Phase
- 새 파이프라인 유형 추가 → 표준 골격 확정 후
- Ops Dashboard 확장 → Phase 59 후속
- .bak/레거시 실제 삭제 → 파괴적 작업 규칙 적용, 별도 승인 필요

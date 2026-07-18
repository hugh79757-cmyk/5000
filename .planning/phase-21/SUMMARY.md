# Phase 21: Funnel Automation — 퍼널 구조 자동화

## TL;DR
5개 Wave로 구성된 퍼널 자동화 기반 구축:
1. **YAML 메타데이터** — 8개 blogs.d 파일에 `funnel_stage`, `depth_next`, `bridge_to` 필드 추가
2. **STAP 버그 수정** — STAP 블로그에 ETAP 전용 entity_linker 잘못 호출하는 문제 수정
3. **링크 삽입 함수** — `_inject_funnel_links()` 신규 작성 (data-funnel-link 추적 속성 포함)
4. **publisher hook** — `publish()` 함수에 퍼널 링크 호출 추가
5. **프롬프트 지시** — `_global_rules`에 퍼널 단계 인지 지시 추가

## Wave 별 예상 시간
| Wave | 작업 | 시간 |
|------|------|------|
| 1 | YAML 필드 추가 (8개 파일) | 30분 |
| 2 | STAP entity_linker 버그 수정 | 15분 |
| 3 | `_inject_funnel_links()` 함수 작성 | 1시간 |
| 4 | publisher.py hook 추가 | 15분 |
| 5 | 프롬프트 `_global_rules` 추가 | 15분 |
| **합계** | | **~2시간 15분** |

## 핵심 설계 원칙
- `depth_next`(같은 카테고리)와 `bridge_to`(다른 카테고리) **별도 필드 필수**
- 링크 HTML에 `data-funnel-link` 등 5종 data 속성 포함 (GA4 추적 표식)
- funnel_stage 없는 블로그는 기존 동작 유지 (영향 없음)
- Blogger/WordPress 플랫폼은 퍼널 링크 미적용

## 파일
- PLAN.md: `.planning/phase-21/PLAN.md`
- CONTEXT.md: `.planning/phase-21/CONTEXT.md`

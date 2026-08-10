# CONTEXT.md — Phase 68: TAP/Travel "1곳" 하드코딩 제거

## 배경

- TAP(Travel Auto Publisher) 분기의 여행 블로그 5개(travel-hugo, travel1~4-hugo)에서 생성되는 모든 글의 제목과 SEO description에 "N곳"(특히 items=1일 때 "1곳")이 포함됨
- 지난 세션에서 축제·캠핑·먹거리·코스·문화유산 샘플 글들을 프롬프트 예시로 추가 — LLM이 자연스러운 글을 쓰게 하는 것이 목적
- "1곳"이라는 기계적인 표현은 이 목적에 반함

## 문제 요약 (tl;dr)

| # | 원인 | 위치 | 심각도 |
|---|------|------|--------|
| C1 | SEO description에 `{len(items)}곳`이 조건 없이 포함 | writer.py:1370 | **최고** |
| C2 | fallback 제목에 "1곳" 보정이 없음 | writer.py:1353-1356 | **높음** |
| C3 | `{count}` 템플릿 필터가 모든 템플릿에 `{count}` 포함 시 무효 | writer.py:1191-1194 | **중간** |
| C4 | 프롬프트 지시문에 "1곳" 표현 (2차 원인) | prompts/travel.yaml:87, prompts.yaml:393 | 낮음 |

## 계약 (계획 시 준수할 제약)

1. **기존 기능 보존**: 제목 템플릿 시스템, AI 제목 생성, fallback 로직의 기본 구조는 유지
2. **증분 수정**: "1곳" 문제만 해소. 다른 프롬프트 내용·구조·규칙은 건드리지 않음
3. **샘플 글 참조 유지**: `{samples}` 플레이스홀더와 샘플 글 참조 방식은 유지 (자연스러운 글쓰기가 목적)
4. **変化 범위**: `pipelines/travel/writer.py` + `config/prompts/travel.yaml` + `config/prompts.yaml` 만 수정
5. **블로그 범위**: travel-hugo, travel1-hugo, travel2-hugo, travel3-hugo, travel4-hugo (5개)
6. **기존 테스트 유지**: 기존 테스트가 있으면 green 유지

## 확정된 설계 결정

- **description 조건부화**: `len(items) > 1`일 때만 "{N}곳" 포함, 1개면 생략
- **fallback 제목 보강**: fallback 선택 시 "{count}" 없는 템플릿을 우선하거나, fallback에도 "1곳" 보정 적용
- **템플릿 필터 보강**: `_filtered` 비어있을 때 2차 필터 적용 (또는 템플릿 자체에 "{count}" 없는 대안 확보)
- **프롬프트 "1곳" → 자연스러운 표현**: "가장 추천하는 캠핑장 1곳" → "가장 추천하는 캠핑장" (본문용, 후순위)
- **travel2_heritage_deep의 "1건"은 유지**: 심층 분석 목적과 일치하므로 수정 대상 아님

## 성공 기준

1. items=1인 글의 description에 "1곳"이 포함되지 않음
2. fallback 제목에 "1곳"이 포함되지 않음 (AI 실패 케이스)
3. AI 제목 생성 성공 시에도 "1곳"이 자연스럽게 제거됨 (기존 보정 개선)
4. 프롬프트 지시문의 "1곳" 표현이 자연스러운 표현으로 교체됨 (선택적)
5. 기존 5개 블로그의 제목·description 생성 로직이 정상 동작 (회귀 없음)

## 범위 외 (Out of Scope)

- 샘플 글 내용 수정 (자연스러운 글쓰기를 위한 참조자 역할 유지)
- fetch 전략 변경 (heritage 1곳/묶기 전략)
- 다른 파이프라인의 "곳" 관련 표현 (curation 등)
- title_templates 전체 재설계 (필요 시 별도 phase)

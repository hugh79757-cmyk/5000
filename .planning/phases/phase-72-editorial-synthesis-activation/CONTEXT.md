# Phase 72: Editorial Synthesis 활성화 — Context

> 설계 문서가 PHASE-71 명칭으로 작성됐으나 실제 페이즈 번호는 **72**다.
> (Phase 71은 자동수정 폐루프로 이미 소진됨 — STATE.md 참조)

## 배경

- Phase 70에서 품질 게이트 S01~S05 추가 (commit f0fdf15f8)
- S03(unique_data_points), S04(editorial_synthesis)가 현재 warn-only (commit 7f635eea4)
- 원인: writer가 `editorial_synthesis_step()`을 호출하지만 topic dict에
  `topic_type`/`topic_id` 미전달 → data_adapters가 빈 값 반환 → synthesis no-op
- 목표: 실제 데이터 주입 구현 → S03/S04 blocking 재활성화 가능하게

## 핵심 코드 위치

| 파일 | 역할 |
|------|------|
| `.planning/designs/PHASE-71-editorial-synthesis-activation.md` | 설계 문서 (Wave 1~4 정의) |
| `pipelines/etap/data_adapters.py` | 4개 adapter 정의, 입력 없어서 빈 반환 |
| `pipelines/etap/editorial_synthesis.py` | synthesis 생성 로직 |
| `dispatcher.py:872-928` | S03/S04 quality guard (현재 WARN-ONLY) |
| 9개 writer | `editorial_synthesis_step()` 호출 존재 (파일당 grep -c 4) |
| `tests/test_data_adapters.py`, `tests/test_editorial.py` | pass, 단 no-op 빈 값 테스트 |

## DB 컬럼 현황

- `unique_data_points`: travel-en.db, car.db에 ALTER 완료
- 나머지 pipeline DB 미확인 — 플래너가 확인 필요 (gap.db, rap.db, senior.db,
  stock.db, curation.db, stap_content.db)

## Wave 구조 (설계 문서 기준)

1. **Wave 1**: dispatcher/topic_manager topic dict에 `topic_type`+`topic_id` 추가 (~5개 분기)
2. **Wave 2**: 각 파이프라인 adapter가 실제 DB/로컬 데이터 fetch → unique_data_points
3. **Wave 3**: synthesis 품질 검증 (100-150자, hallucination 방지, cosine < 0.7)
4. **Wave 4**: S03/S04 blocking 재활성화 + 회귀 테스트

## 파이프라인별 주입 후보 데이터

| 브랜치 | 데이터 종류 |
|--------|------------|
| ETAP (deals/nature/airports/watersports 등) | 가격, 날짜, 항공편 수 |
| CAP (ev/compare/guide 등) | 차량 스펙, 가격, 연비 |
| STAP (etf/ipo/sector) | 재무 지표, 수익률 |
| RAP (rap/rap2~5) | 매물 수, 평단가, 면적 |
| CUAP (14개 큐레이션) | 상품 가격, 평점, 리뷰 수 |

## 제약사항 (하드 제약)

- **Additive only** — 기존 파이프라인 동작 변경 금지
- LLM 호출 추가 최소화 (adapter는 DB/로컬 데이터 우선, LLM은 synthesis 생성 1회만)
- 각 Wave 독립 배포 가능
- blocking 재활성화는 Wave 4에서만 (이전 Wave는 warn-only 유지)
- 기존 테스트 green 유지

## 성공 기준 (설계 문서)

- 9개 writer 모두 비어있지 않은 synthesis 반환 (≥80자)
- unique_data_points ≥3개 저장
- cosine similarity < 0.7 (동일 블로그 최근 10건 대비)
- 예상 소요 ~9h (2일)

## 참조 리서치

- `.planning/phases/PHASE-70-quality-improvement/70-RESEARCH.md` — synthesis 설계
  결정(unified deterministic templates), 파일 계획, 테스트 명령 포함
- 상세 코드 리서치는 플래너가 직접 수행 (adapter 입출력, writer 호출부 9곳,
  topic dict 구성 지점, DB 스키마)

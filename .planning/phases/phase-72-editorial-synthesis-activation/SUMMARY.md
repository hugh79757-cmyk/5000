# Phase 72 — Editorial Synthesis 활성화: 계획 요약

> 작성: gsd-planner (2026-08-25) · 실행 대상 PLAN: `PLAN.md` (동일 디렉터리)

## 한 줄 목표

writer 9곳의 synthesis no-op을 해소 — topic dict에 topic_type/topic_id 주입 →
분기별 실DB 어댑터가 unique_data_points 공급 → 품질 게이트(길이/hallucination/cosine)
통과 → 저장 연동 후 S03/S04 blocking 재활성화.

## 구조

| 항목 | 값 |
|---|---|
| Wave 수 | 4 (W1 주입 → W2 어댑터 → W3 품질게이트 → W4 저장+blocking) |
| 태스크 수 | 14 (W1:4, W2:4, W3:3, W4:3) |
| 총 예상 | ~9h / 2일 |
| 신규 LLM 호출 | **0회** (기존 결정론 템플릿 유지 = "LLM 최소화" 제약 충족) |
| 파일 수정 | 코드 14 + 테스트 2 + DB 변경 0건 (ALTER 후속 이월) |

## Wave 요약

- **W1 (~2h):** 10개 호출부 빈 `{}` → 식별자 포함 dict. CAP(car)는 라이브 경로에
  synthesis 호출 자체가 없어 신설(pipeline.py). 어댑터 미등록 type은 자동 `[]`라
  이 wave 단독 배포 = no-op 보장.
- **W2 (~3.5h):** flight_adapter 교차오염 수정(topic_id 스코핑 — 현행 전역 LIMIT 20이
  hallucination 경로, data_adapters.py:50-74) + 신규 어댑터 7종 + TAP items 파생
  passthrough. DB ALTER는 본 페이즈 제외(쓰기 경로 부재 — YAGNI, 후속 이월).
- **W3 (~1.5h):** `editorial_synthesis_quality_gate`(≥80자·숫자∈값집합) +
  `editorial_cosine_check`(동일 블로그 최근 10건, threshold 0.70) → dispatcher S06
  warn-only. no-LLM 통합테스트.
- **W4 (~2h):** `mark_published_by_id` optional 확장으로 unique_data_points JSON 저장,
  dispatcher S03/S04 `blocked=True` 전환 + kill-switch `QUALITY_ENFORCE_S03_S04=0`
  (재배포 없이 warn-only 복귀).

## 플래너 검증에서 나온 계획 변경점 (설계 문서 대비)

1. **car writer.write_article은 데드코드** — 호출부 없음(repo 전역 grep).
   라이브 생성은 car/pipeline.py:245 인라인 경로 → 주입 지점을 pipeline.py로 결정.
2. **CONTEXT.md "tests pass"와 다름** — `OPS_TEST_MODE=1` 없으면 conftest guard가
   전 테스트 ERROR. 기준선: targeted 15 passed / full 33F·654P·1S
   (ops_dashboard 1건 collection ImportError 선존재, 범위 외).
3. **DB 컬럼 실측** — travel-en(38테이블)+car만 존재, rap/senior/stock/curation/
   stap_content 없음, gap.db는 테이블 0개. rap/senior/stock/curation ALTER는
   쓰기 경로가 없어 본 페이즈 제외(후속 이월 — 체커 W2 반영).
4. **TAP만 DB 주소키 부재** — items 인메모리 파생 passthrough로 해결 (유일한
   설계 문서 예외, PLAN §2 명시).
5. **dateModified/lastmod는 Phase 70에서 이미 구현됨**(hugo_writer.py:1421-1427)
   — W4 범위에서 제외, 저장 연동만 수행.

## Top 3 리스크

1. **R4 blocking 오탐 발행량 급감 (중간)** — kill-switch + ETAP 한정 + 관찰기간으로 완화.
2. **R3 writer 회귀 (낮~중)** — additive-only(dict 키 추가), baseline 열화 감시(≤33 failed).
3. **R1 합성 환각 (낮음)** — 결정론 템플릿(LLM 0회) + 숫자∈값집합 게이트 +
   flight 교차오염 원천 차단.

## 다음 단계

```
/gsd-execute-phase 72        # 또는 wave별 수동 실행
/clear 먼저                  # fresh context
```

배포 규칙 상기: 배포는 반드시 dispatcher.py 또는 deploy_site() 경유.
수동 wrangler 금지. git push는 형상관리 용도 only.

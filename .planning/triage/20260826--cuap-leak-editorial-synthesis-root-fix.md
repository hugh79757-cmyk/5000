---
date: 2026-08-26
type: fix
status: resolved
---

# CUAP 프롬프트 릭 근본 수정 (editorial_synthesis + hugo_writer 2중 방어)

## What
CUAP 뷰티/펫 블로그 포스트 본문에 지시문 형태 텍스트가 노출됨:
- Part A: `From products, verified records indicate product count N 개; category X; top product Y; min price A KRW; max price B KRW.`
- Part B: `This editorial synthesis is constructed exclusively from the verified source tables... preserving the integrity of the reported facts.`
70개 포스트(15개 CUAP 사이트) 영향. 사후 전수 정화 + 근본 수정 + 재발방지 2중 레이어 적용.

## Why
누수는 **LLM이 아님** — 결정론적 코드 출력.
`pipelines/etap/editorial_synthesis.py`의 `_sentence_for(table,points)`가 `From {table}, verified records indicate ...` (table='products' → Part A) 생성, `_FILLER`/`_FALLBACK`가 Part B 메타 블록. `editorial_synthesis_step()`이 단어수<100일 때 `_FILLER`를 본문에 덧붙임. `pipelines/curation/writer.py:_inject_editorial_synthesis`가 이 합성문을 **발행 본문에 직접 append** → CUAP product 데이터(source_table='products')만 가시적 문장 트리거. TAP는 이 경로 미사용.

## Files changed
- `pipelines/etap/editorial_synthesis.py` — `_FILLER`/`_FALLBACK` 메타 패딩 제거 (근본)
- `shared/publishers/hugo_writer.py` — 발행시점 Part A+B 자동 제거 확장 (재발방지)
- `shared/leak_tracker.py` — `_C04_EN_PATTERNS`에 `from products, verified records indicate` 추가 (탐지)
- `pipelines/curation/writer.py` — 호출부 식별(미수정, 설계상 공유 경로)

## How
1. 근본: editorial_synthesis가 메타 블록을 더 이상 생성하지 않음
2. 발행: hugo_writer가 두 파트 모두 strip
3. 탐지: C04 패턴 추가
4. 백필: 70개 포스트 strip + 15 CUAP 사이트 재배포(content/·public/ 0건 확인)

## Verification
- AST 파싱 OK (editorial_synthesis.py, hugo_writer.py)
- `grep -rl 'From products, verified records indicate' content/ public/` = 0
- 라이브 사이트 정화 확인 (15/15 배포 OK)
- `editorial_synthesis_step()` 반환 = 데이터 문장만 (HAS_LEAK_B=False)

## Commits
- e54e8c06c (detector + strip)
- 3cdafb4bf (hugo_writer Part A strip + detector)
- f20bc3aa7 (editorial_synthesis root + hugo_writer Part B strip)

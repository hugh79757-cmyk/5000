# CONTEXT.md — Phase 27: CUAP Cross-Sell Card 404 Fix

## Trigger
baby 블로그 하단 크로스셀 카드(주방용품추천·건강식품추천 등) 링크가 라이브에서 404 반환.
사용자 지시: "우선 이거 왜만들었는지. gsd문서에서 찾아보고 파악하고 진행하자" → Phase 25 문서 분석 후 수정 플랜 작성·세션 중지.

## Investigation Findings (2026-07-21, 검증됨)

### 1. 크로스셀 카드 생성 경로 (확인: cuap_entity_linker.py:310)
- `build_cross_sell_card(blog_id)` → `_target_blogs()`로 CROSS_GRAPH 대상 블로그 추출
  → `cuap_entities`(travel-en.db)에서 `published=1 AND blog_id=target ORDER BY priority DESC, rowid DESC LIMIT 1`
  → 해당 행의 `post_url`을 `<a href>`로 굽힘.
- URL은 `BLOG_DOMAINS[blog_id]`에서만 구성(외부 입력 차단, line 21/188).

### 2. 근본 원인 (확인: DB 조회 + 디스크 대조)
- `cuap_entities` 테이블 ROW 29건 전부 = **Phase 25 Wave 4 Task 8 `register_sample_cuap_entities.py`가 박은 샘플/테스트 데이터**.
- `-rec` 슬러그 10건(`20260720-{blog}-rec`) + `test-integration` 1건 + "OOO 추천 추천" 중복라벨 행 18건.
- **핵심: DB의 어떤 slug도 실제 `content/posts/` 에 존재하지 않음** (10개 블로그 전수 대조 → MISSING 10/10).
- 즉, `register_cuap_entity()`(Phase 25 Task 4, pipeline.py 발행 시 실제 글 등록 의도)가 **실제로는 1건도 호출되지 않음**.
- 카드는 "실제 발행된 글"을 가리키도록 설계됐으나, 테스트용 가짜 `-rec` 슬러그가 `published=1`로 남아 카드가 그걸 가리킴.

### 3. 라이브 피해 범위 (확인: grep + HTTP)
- `-rec` URL이 베이크된 발행 포스트 파일 = **16개** (`cuap/*/content/posts/**/index.md`).
- 타겟 페이지 라이브 상태: health 404, kitchen 500, appliance 404, fitness 404 (public에 `-rec` 파일 0개).

### 4. 실제 발행 글 존재 (확인: content/posts 디렉토리)
- 각 블로그 실제 발행 글: appliance 219 / baby 205 / beauty 112 / camping 95 / fitness 199 / health 102 / interior 260 / kitchen 111 / laptop 104 / pet 68건.
- 블로그별 최신 실제 slug(교체 타겟 후보, 예: baby→`2026년-7월-육아백과-추천-...`, kitchen→`2026년-7월-그릴가방-추천-...`).

## Design Intent (Phase 25 문서)
- `cuap_entities`는 **실제 발행 글**을 담아야 함. `register_cuap_entity()`가 pipeline.py 발행 훅에서 실slug + `post_url = BLOG_DOMAINS[blog_id]+"/"+slug+"/"`로 등록.
- `build_cross_sell_card`는 이 테이블에서 최신 실글을 카드로 노출.
- 샘플 `-rec` 데이터는 **테스트용**이었으나 `published=1`로 방치되어 카드가 가짜를 가리킴 = 버그.

## Constraints (위반 금지)
1. 도메인/Pub ID: CUAP = `*.informationhot.kr` → `ca-pub-6677996696534146` ONLY. rotcha(`8772`) 절대 혼합 금지(AGENTS.md §1). 본 페이즈는 URL 교체만 하므로 Pub ID 건드리지 않음.
2. 배포 금지: git push 배포 금지. 반드시 `dispatcher.py {blog_id}` 경유(Worker는 내부 wrangler). CLOUDFLARE_API_TOKEN env 제거 필수.
3. 점진적: baby(Worker) 먼저 수정·빌드·검증 → 타 블로그 확장.

## Open Decision (플랜 실행 시 확정)
DB 백필 전략:
- (A 권장) filesystem 스캔 백필 — 각 블로그 `content/posts/` 실slug를 `cuap_entities`에 `published=1`로 등록. `register_cuap_entity()` 미연결 확인됐으므로 가장 확실.
- (B) `register_cuap_entity()`를 pipeline.py 발행 훅에 실제 연결 후 신귀 발행에만 의존 — 기존 16건 베이크 포스트는 별도 교체 필요.
→ A로 진행, B는 향후 발행 자동화로 별도 태스크.

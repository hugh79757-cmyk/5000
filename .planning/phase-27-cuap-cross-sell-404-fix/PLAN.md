# PLAN.md — Phase 27: CUAP Cross-Sell Card 404 Fix

## Goal
baby 블로그 하단 크로스셀 카드가 가리키는 `-rec` 404 URL을 실제 발행 글 URL로 교정하고,
`cuap_entities` 테이블을 테스트 데이터에서 **실제 발행 글**로 백필하여 향후 발행 카드도 정상 링크되도록 한다.

## Root Cause (Confirmed)
- `build_cross_sell_card()`(cuap_entity_linker.py:310)는 `cuap_entities`에서 `published=1` 최신 행의 `post_url`을 카드 링크로 사용.
- 해당 테이블 29건 전부가 Phase 25 샘플/테스트 데이터(`20260720-{blog}-rec` 등)이며, **실제 발행된 slug는 0건**(디스크 대조 완료).
- `register_cuap_entity()`(Phase 25 Task 4)가 발행 시 1건도 호출되지 않음.
- 결과: 16개 발행 포스트에 `-rec` 404 URL이 본문에 베이크됨.

## CRITICAL CONSTRAINTS
1. 도메인/Pub ID: CUAP=`informationhot.kr`→`ca-pub-6677996696534146` ONLY. rotcha(`8772`) 절대 혼합 금지.
2. 배포 금지: git push 배포 금지. 반드시 `dispatcher.py {blog_id}` 경유(Worker는 내부 wrangler, CLOUDFLARE_API_TOKEN 제거).
3. 점진적: baby(Worker) 먼저 수정·빌드·검증 → 타 블로그 확장.

## Scope
**IN:**
- `cuap_entities`(travel-en.db) 테스트 행 전체 삭제(purge)
- filesystem 백필 스크립트: 각 CUAP 블로그 `content/posts/` 실slug → `cuap_entities` 등록(`published=1`, `post_url=BLOG_DOMAINS[blog]+"/"+slug+"/"`)
- 16개 베이크 포스트의 `-rec` URL → 실제 타겟 블로그 최신 발행 URL 교체
- 영향 블로그 재빌드·재배포(baby=Worker / 나머지=Pages via dispatcher)
- 라이브 HTTP 200 검증

**OUT:**
- `register_cuap_entity()` pipeline.py 발행 훅 실연결(향후 자동화) — 별도 태스크
- rotcha.kr / techpawz.com 확장 — 이 페이즈 범위 밖

---

## Tasks

### 27-01: cuap_entities 테스트 행 purge
- **WHAT**: travel-en.db `cuap_entities`에서 Phase 25 샘플/테스트 행 전체 삭제.
  - 대상: `post_slug LIKE '%-rec'`(10건) + `post_slug='test-integration'`(1건) + 라벨에 `추천 추천` 중복 포함된 행(테스트 표식, 전수 18건) — **단, 실slug와 디스크 대조해 실제 발행 글은 보존**.
- **HOW**: sqlite3 DELETE + 삭제 전 ROW 카운트 스냅샷 보관.
- **EXPECTED**: 삭제 후 `SELECT COUNT(*) FROM cuap_entities WHERE post_slug LIKE '%-rec'` = 0. 디스크에 존재하는 실slug 행만 잔존.
- **검증**: [검증됨] sqlite COUNT 쿼리.

### 27-02: filesystem 백필 스크립트 작성·실행
- **WHAT**: `scripts/backfill_cuap_entities.py` 신규(또는 `register_cuap_entity` 재활용).
  - 각 블로그(`appliance/baby/beauty/camping/fitness/health/interior/kitchen/laptop/pet`) `content/posts/` 디렉토리 스캔.
  - 각 블로그 최신 N개(기본 5) 실slug를 `cuap_entities`에 `published=1`, `entity_name=slug`, `link_label=slug에서 '추천' 분리`, `post_url=BLOG_DOMAINS[blog]+"/"+slug+"/"`로 등록.
  - 중복 방지: 기존 rowid 존재 시 skip(upsert).
- **HOW**: `shared/cuap_entity_linker.py`의 `BLOG_DOMAINS`/`_get_db()` 재사용. external input 차단 유지(line 21/188).
- **EXPECTED**: 백필 후 각 블로그 `cuap_entities WHERE published=1 AND blog_id=?` ≥ 1건, 모든 `post_url`이 디스크 실slug와 일치.
- **검증**: [검증됨] 백필 건수 per blog + 샘플 post_url이 `content/posts/{slug}` 존재 여부 grep.

### 27-03: 16개 베이크 포스트 `-rec` URL 교체
- **WHAT**: `cuap/*/content/posts/**/index.md`에서 `informationhot.kr/20260720-.*-rec/` 패턴을 실제 타겟 블로그 최신 발행 URL로 치환.
  - 매핑(URL host → 타겟 블로그 → 교체 slug): phase-27 CONTEXT의 "블로그별 최신 실제 slug" 표 참조.
    예: `kitchen.informationhot.kr/20260720-kitchen-rec/` → `kitchen.informationhot.kr/2026년-7월-그릴가방-추천-.../`
  - label(주방용품추천 등)은 실slug와 불일치하나 미관 이슈 → 27-04에서 label도 실slug 기반으로 정정(선택).
- **HOW**: sed/Edit으로 16파일 일괄 치환. 치환 전 파일 백업(`cp -r content/posts content/posts.bak-2703`).
- **EXPECTED**: 교체 후 `grep -rl "informationhot.kr/20260720-.*-rec/" cuap/*/content/posts/` = 0건.
- **검증**: [검증됨] grep 0건 + 치환된 URL이 `content/posts/{slug}` 존재 여부 확인.

### 27-04: 영향 블로그 재빌드·재배포 (baby 먼저)
- **WHAT**:
  1. baby-hugo(Worker): `dispatcher.py baby-hugo` → 내부 wrangler deploy(CLOUDFLARE_API_TOKEN 제거됨).
  2. 나머지 영향 블로그(Pages): `dispatcher.py {blog_id}` 순차 배포.
  - 배포 전 `hugo --gc --minify` 로컬 빌드 성공 확인.
- **HOW**: dispatcher 경유만. 수동 wrangler 절대 금지.
- **EXPECTED**: 배포 성공, baby 블로그 하단 카드 링크가 실제 포스트로 향함.
- **검증**: [검증됨] 배포 exit 0 + 라이브 URL HTTP 200(아래 27-05).

### 27-05: 라이브 검증
- **WHAT**: baby + 타겟 블로그 카드 링크 URLs에 대해 HTTP 상태 확인.
- **HOW**: `curl -s -o /dev/null -w "%{http_code}"` on each card URL from a sampled baby post.
- **EXPECTED**: 모든 카드 URL = 200. 404/500 = 0.
- **검증**: [검증됨] curl HTTP code 목록.

---

## Verification Loop
| Task | 검증 수단 | 기준 |
|------|----------|------|
| 27-01 | sqlite COUNT | `%-rec` = 0 |
| 27-02 | per-blog ROW COUNT + post_url↔디스크 대조 | 각 blog ≥1, URL 모두 실slug |
| 27-03 | grep `%-rec` | 0건 |
| 27-04 | dispatcher exit 0 | 배포 성공 |
| 27-05 | curl HTTP code | 전부 200 |

## 잔존 위험
- `register_cuap_entity()` 미연결로 **향후 신규 발행** 카드는 백필 데이터(27-02)에만 의존. 신규 발행 시 실slug 자동등록 훅은 별도 태스크(OUT).
- 27-03 label 불일치(예: "주방용품추천" 카드가 그릴가방 포스트 향함) — 기능상 404 해소되나 문맥 정합성은 미완. 별도 정교화 가능.
- 베이크 포스트 외 `cuap-spider-links.html` partial 경로(`cuap_cross_links`/`cuap_funnel` params)는 본 페이즈 대상 아님 — 별도 점검 권장.

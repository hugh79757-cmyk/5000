# RESEARCH: Phase 57 — RAP 분기 품질 진단·개선 (2026-08-03 실측 기반)

> 이 문서는 2026-08-03 RAP 분기 정검 세션의 실측 결과를 정리한 것.
> 모든 항목은 코드/DB/로그 인용으로 확정됨 (추측 금지 원칙).

## R1. 발행 현황 (content.db publish_ledger, status='published')

| 블로그 | 7일 발행 | 7일 쿼터(5×7) | 오늘(8/3) |
|--------|----------|--------------|-----------|
| rap-hugo | 35 | 35 | 2 (CATCHUP 복구 중) |
| rap2-hugo | 35 | 35 | 2 |
| rap3-hugo | 34 | 35 | 2 |
| rap4-hugo | 34 | 35 | 2 |
| rap5-hugo | 34 | 35 | 2 |

- 쿼터는 달성 중. 단, 8/3은 사용자 분기 정검(스케줄러 재시작 8회)으로 아침 슬롯이
  전부 밀려 CATCHUP(3회 제한)으로 복구된 비정상 하루
- scheduler.log 8/3 실패 패턴: rap2 10:49, rap3 10:53, rap5 11:03 write_failed →
  재시도(1/3)로 대부분 성공. rap4 12:53~13:03 600s 타임아웃 1회

## R2. P1+P2 확정 근거 (동일 키워드 재발행 + publish_log 누락)

```sql
-- rap.db publish_log
-- 오늘 발행 키워드 기준 조회 결과:
-- rap2 "음성군 지역 국민임대주택 예비입주자 모집 공고 ..." → 전체=1, 7일내=0
-- rap5 "대림아크로빌 강남구 실거래가"                     → 전체=1, 7일내=0
-- 같은 키워드가 오늘 2회씩 발행됨 (content.db source_id로 확인)
```

- publish_log 스키마: UNIQUE 제약 없음 (`idx_publish_blog(blog_id,data_type)` 일반 인덱스)
- pipeline.py:1027-1036: `INSERT OR IGNORE INTO publish_log` — try/except로 예외를
  삼키고 warning만 기록. **실패가 로그에 남아도 scheduler.log엔 안 보임**
  (scheduler.py:269 stdout 마지막 3줄만 [OUT]으로 기록 — dispatcher 상세 로그 유실 구조)
- 원인 후보 (단계 2에서 재현 확정): daily_refresh daemon 스레드(join 120s 초과 시
  살아있음)가 sqlite write lock 보유 → publish_log INSERT `database is locked`.
  `database is locked`는 코드베이스에서 5회 이상 기존 발생 이력 존재
- 연쇄: publish_log 누락 → `_pick_keyword` 3단계(7일 제외) 무력화 → 같은 키워드 재선택
  → 동일 콘텐츠 중복 발행 (SEO/품질 저하)

## R3. P3 확정 근거 (ai_writer fallback1 취약점)

- 커밋 `1dff13638` (브랜치 `fix/rap-subscription-backfill`만 존재, main 미병합):
  TIER_ORDER = ["default","fallback1","fallback2","fallback3","economy"]
- `config/models.yaml`: default/fallback/economy만 정의 → fallback1 키 없음
- `shared/ai_writer.py:100` `tier_config = config[attempt_tier]` → KeyError 'fallback1'
- scheduler.log 2026-08-03 11:03:14 실제 발생 (rap5-hugo) — 브랜치 정검 중 작업트리가
  해당 상태였을 때 스케줄러가 실행되며 전 분기 write_failed 유발
- 결론: main 병합 전 브랜치 코드 정리 필수. 현재 main은 안전 (변경 없음 확인)

## R4. P5 확정 근거 (키워드 풀 불균형)

- active 키워드: rap-hugo 2183 / rap3-hugo 2068 / rap4-hugo 2324 /
  **rap2-hugo 218 / rap5-hugo 395**
- rap2 키워드 예시: "음성군 지역 국민임대주택 예비입주자 모집 공고 [2026.03.23.]" —
  공고명 통짜 키워드로 공고 갱신 주기와 무관하게 재사용 위험
- 오염 여부(중국어/혼합어/타블로그 키워드)는 단계 2에서 풀 덤프로 확정 필요 —
  cuap에서 실제 원인이었음(Phase 56: kitchen 70개, beauty 100개 제거)

## R5. P6 의심 근거 (일일 갱신 신선도)

- refresh_log: 07-20~07-27 trades_added=0 (7일 연속 0건), 08-01 0건/08-02 2건,
  07-28~31 대량(9584~9791건), 08-03 8건
- trades 최신 deal_ymd=202608 (7건), rents=202608 (1건) — 월초 희소는 정상이나
  7일 연속 0건 구간은 API 소스 장애/에러 처리 추정. fetcher.py 소스 확인 필요

## R6. P7 확정 근거 (depth_next/funnel 미구현)

- `config/blogs.d/rap.yaml`: depth_next(rap-hugo→rap3/4/2), bridge_to(rap2/3/4→finance),
  funnel_stage(landing/bridge) 정의됨
- grep `.py` 전수: depth_next/funnel_stage/bridge_to 매칭 **0건** → 코드 미구현
- `_post_process`의 내부링크(pipeline.py:736-763)는 동일 블로그 무작위 3개 샘플 —
  퍼널 의도와 무관

## R7. P8 확정 근거 (테스트 부재)

- `tests/`: curation, shared, integration, test_dispatcher_registry.py —
  rap 관련 테스트 0건

## 단계 2에서 확정해야 할 미결 항목 (플랜 작업으로 포함)

1. publish_log INSERT 실패의 정확한 예외 (database is locked 재현 or 기타)
2. 키워드 풀 오염 실측 (rap2/rap5 풀 덤프 + 중국어/비주제어 비율)
3. refresh 0건 구간의 API 소스 원인 (fetcher 에러 로그)
4. 라이브 발행글 품질 실측 (1인칭/후기 프레임, CoT 노출, 800자 미만 — 단계 1 항목,
   이번 세션에서 미실시)

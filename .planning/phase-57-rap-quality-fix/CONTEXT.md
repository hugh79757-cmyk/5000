# CONTEXT: Phase 57 — RAP 분기 품질 진단·개선 (cuap 개선 경험 이식판)

## 배경

2026-08-03 RAP 분기 5개 블로그 정검 결과, 쿼터(7일 34~35/35건)는 달성 중이나
다음 문제들이 실측으로 확정됨. cuap(Phase 55/56)에서 검증된
"읽기전용 진단 → 근본원인 확정 → 좁은 수정 → 실측 → 카나리 확대" 방법론을
rap/cap/seap 분기에 이식 적용한다.

## 대상 분기·블로그 (지형도)

| 블로그 | 도메인 | 역할 | funnel_stage | 파이프라인 |
|--------|--------|------|--------------|-----------|
| rap-hugo | apt.informationhot.kr | 부동산 시세/청약 분석 | landing | pipelines/rap |
| rap2-hugo | apply.informationhot.kr | 청약 알리미 | bridge | pipelines/rap |
| rap3-hugo | tax.informationhot.kr | 부동산 세금 가이드 | bridge | pipelines/rap |
| rap4-hugo | rent.informationhot.kr | 전월세 리포트 | bridge | pipelines/rap |
| rap5-hugo | brand.informationhot.kr | 브랜드 아파트 백과 | landing | pipelines/rap |

- 전부: platform=hugo, theme=blowfish, managed_by=pipeline, daily_quota=5, 하루 5슬롯
- 흐름: `scheduler.py` → `dispatcher.py {blog_id}` (subprocess, timeout 600s)
  → `pipelines/rap/pipeline.py:run()` → fetcher/writer → `shared/publisher.py` (Hugo 발행+배포)
- DB: `data/rap.db` (keywords 7873, publish_log 1738, subscriptions 1215, trades 35158, rents 55769)
- 광고: informationhot 계열 → **ca-pub-6677996696534146** (로더+슬롯 일치 확인 완료, 정상)

## 확정 문제 (위반 → 근본원인, 코드/DB/로그 근거)

### P1+P2: 동일 키워드 연속 재발행 + publish_log 기록 누락 (심각)
- 실측: 2026-08-03 rap2-hugo가 "음성군 지역 국민임대주택 예비입주자 모집 공고"로
  12:26/12:41 2회, rap5-hugo가 "대림아크로빌 강남구 실거래가"로 13:13/14:00 2회 연속 발행
  (content.db publish_ledger source_id로 확인)
- 근거: rap.db publish_log — rap2 최근 7일 1건, rap5 2건뿐 (8/1·8/3 발행 다수 누락).
  오늘 발행 키워드 기준 publish_log "전체=1, 7일내=0" → 7일 제외 로직 무력화
- 원인 코드: `pipelines/rap/pipeline.py:1027-1036` publish_log INSERT가 try/except로
  실패를 삼킴(조용한 실패). 성공 발행 후 INSERT 누락 → `_pick_keyword` 3단계
  (`pipeline.py:111-121` publish_log 7일 조회)가 키워드를 배제 못함 → 재선택
- 추정 실패 원인: daily_refresh daemon 스레드(`pipeline.py:791-809`, join 120s 후에도
  살아있으면 계속 실행)와의 sqlite write lock 경합(`database is locked` —
  코드베이스 내 5회 이상 기존 발생 이력). **단계 2에서 재현 확정 필요**
- 부차: publish_log에 UNIQUE 제약 없음(일반 인덱스만) — INSERT OR IGNORE가
  아무것도 무시하지 못함. `_pick_keyword`의 중복 방지가 전적으로 publish_log
  기록 정확성에 의존하는 구조

### P3: ai_writer fallback1~3 브랜치 취약점 (잠복 위험)
- 근거: `fix/rap-subscription-backfill` 브랜치 커밋 `1dff13638`가
  TIER_ORDER=["default","fallback1","fallback2","fallback3","economy"]로 변경했으나
  `config/models.yaml`에는 default/fallback/economy만 존재 → `config[attempt_tier]`
  KeyError 'fallback1' (shared/ai_writer.py:100). 2026-08-03 11:03 스케줄러 로그에서
  실제 발생 확인 (rap5-hugo write_failed 원인)
- 현재 main은 안전(브랜치 미병합). **브랜치 병합 시 재발 확정적** — 병합 전 차단 필요
- 시사: 브랜치 정검 중 작업트리가 해당 상태일 때 스케줄러가 돌면 전 분기 write_failed

### P4: CATCHUP 폭주 시 write_failed 다발
- 근거: 8/3 10:23 스케줄러 기동 후 CATCHUP 1~3회 시도 중 50% 초회 실패
  (rap2 10:49, rap3 10:53, rap5 11:03 실패 → 재시도 성공)
- 원인: 슬롯 밀림 → 블로그 동시 발행 → AI 생성 실패/타임아웃. 재시도로 대부분 복구되나
  AI 호출 낭비 + 600s 타임아웃(rap4 13:03) 발생
- 참고: 8/3 아침 슬롯 밀림은 사용자 분기 정검(재시작)에 의한 일회성. 정상 상태가 아님

### P5: 키워드 풀 불균형
- 근거: active 키워드 — rap-hugo 2183, rap3 2068, rap4 2324 vs **rap2 218, rap5 395**
- 영향: 풀 소진 시 재사용 가속(P1과 결합 시 중복 발행 확률 급증). rap2는
  "음성군 지역 국민임대주택 예비입주자 모집 공고 [2026.03.23.]"처럼 공고명 통짜 키워드
  다수 → 공고 갱신 주기와 무관하게 반복 위험
- 추가 확인 필요(단계 2): 키워드 풀 오염(중국어/혼합어/타블로그 복사) 여부 — cuap에서
  실제 원인이었던 체크리스트 (7)

### P6: 일일 갱신 신선도 이상 (의심, 확정 필요)
- 근거: refresh_log — 07-20~07-27 trades_added=0 (7일 연속 0건),
  08-01/08-02 trades 0/2건 + subs_added=225 연속, 08-03 8건
- trades 최신 월 202608=7건, rents 202608=1건 (월초라 희소는 정상이나 7일 연속 0건은 이상)
- 영향: 데이터 신선도 저하 시 발행 콘텐츠 품질 저하. API 소스/에러 처리 확인 필요

### P7: depth_next/funnel_stage/bridge_to 미구현
- 근거: `config/blogs.d/rap.yaml`에 depth_next/bridge_to/funnel_stage 정의되어 있으나
  코드 구현 0건 (grep로 .py 매칭 없음) → 퍼널 심화/브릿지 내부링크가 실제로 안 삽입됨
- 영향: SEO/퍼널 전략 미실현. `_post_process` 내부링크는 동일 블로그 무작위 샘플만

### P8: RAP 테스트 부재
- 근거: `tests/`에 rap 관련 테스트 0건 (curation/shared/integration만 존재)
- 영향: 회귀 방지 불가. 수정 후 최소 단위 테스트 필요

## 적용 방법론 (사용자 지시, cuap 개선 경험 이식)

- 단계 0: 지형 파악 (읽기 전용) — 분기별 지형도 + 실패 reason 빈도표
- 단계 1: 라이브 실측 감사 (읽기 전용, 각 블로그 3~5건) — 제목/본문/관련성/cross-link 위반율표
- 단계 2: 근본 원인 확정 (읽기 전용, 코드/로그 Yes/No) — 위반→원인 매핑표(라인 특정)
  + cuap 원인 체크리스트 (1)~(7) 대조
- 단계 3: 수정안 (diff 초안, 배포 금지, 원인별 분리) — 각 수정에 검증 방법 명시
- 단계 4: 배포 + 실측 (승인 후, force_draft 유지) — 자동생성 2~3건 실측, 1건 실패 시 revert
- 단계 5: 카나리 확대 — 대표 1~2개 force_draft 카나리 → 안전 블로그 순차 확대

## 핵심 파일

| 파일 | 역할 |
|------|------|
| `pipelines/rap/pipeline.py` | RAP 메인 — _pick_keyword(74-139), publish_log INSERT(1027-1036), daily_refresh 스레드(791-809) |
| `pipelines/rap/rap_data_sync.py` | 일일 갱신 — daily_refresh(397-449), _parallel_sync(224-243) |
| `pipelines/rap/writer.py` | 기사 생성 — 프롬프트(_build_trade_system_prompt 322-628), 파싱(_parse_article 746-783) |
| `pipelines/rap/fetcher.py` | 데이터 수집 |
| `shared/ai_writer.py` | AI 생성 — tier 폴백(64, 100), 실패 시 RuntimeError(159-161) |
| `config/models.yaml` | LLM tier 설정 (default/fallback/economy) |
| `config/blogs.d/rap.yaml` | 5개 블로그 정의 (depth_next/bridge_to/funnel_stage 포함) |
| `data/rap.db` | keywords/publish_log/trades/rents/subscriptions/gongsijiga |
| `shared/publisher.py` | 공용 발행 (Hugo 배포) |

## 범위·제약

- rap 분기 5개 블로그 우선. cap/seap은 동일 방법론 재적용(본 페이즈에서 지형 파악만)
- 단계 0~2: 읽기 전용 (코드/프롬프트/설정 변경 없음, 배포 없음)
- 단계 3: diff 초안만 (적용 금지)
- 단계 4~5: 단계별 승인 후. force_draft 유지, 카나리 1~2개 우선
- 커밋은 원인별 분리 (P1+P2 / P3 / P5 / P6 / P7 / P8 각각 독립 revert 가능)
- force push 금지, wrangler 수동 배포 금지, 미해결 블로그 활성화 금지
- 발행 승격(force_draft 해제)은 draft 육안검수 후 별도 승인

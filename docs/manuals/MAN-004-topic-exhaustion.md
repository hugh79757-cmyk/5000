# MAN-004: 토픽 고갈 대응 매뉴얼

## 1. 정의
토픽 고갈 = 블로그의 미사용 토픽(exhausted=0 또는 used=0 또는 status!='exhausted')이 0건이 되어 자동 발행이 중단된 상태.

## 2. 영향
- 해당 블로그 발행 완전 중단
- scheduler.log에 "[ETAP] xxx-hugo 발행 중지 / 토픽 테이블: xxx_topics / 남은 토픽: 0개" 출력
- 대시보드에서 감지 불가 (현재) → §5 체크 구현으로 해소

## 3. 감지 방법

### 3.1 수동 확인 (현재)

```bash
# ETAP (per-table, 예시: watersports/nature/deals)
sqlite3 /Users/twinssn/Projects/5000/data/travel-en.db \
  "SELECT 'watersports_topics' as tbl, SUM(CASE WHEN exhausted=0 THEN 1 ELSE 0 END) as avail, COUNT(*) as total FROM watersports_topics
   UNION ALL SELECT 'nature_topics', SUM(CASE WHEN exhausted=0 THEN 1 ELSE 0 END), COUNT(*) FROM nature_topics
   UNION ALL SELECT 'deals_topics', SUM(CASE WHEN exhausted=0 THEN 1 ELSE 0 END), COUNT(*) FROM deals_topics;"

# ETAP 전체 스캔 (모든 *_topics)
sqlite3 /Users/twinssn/Projects/5000/data/travel-en.db \
  "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%_topics';" | while read t; do echo -n "$t: "; sqlite3 /Users/twinssn/Projects/5000/data/travel-en.db "SELECT SUM(CASE WHEN exhausted=0 THEN 1 ELSE 0 END) FROM $t;"; done

# CAP
sqlite3 /Users/twinssn/Projects/5000/data/car.db \
  "SELECT site_id, SUM(CASE WHEN status!='exhausted' THEN 1 ELSE 0 END) as avail, COUNT(*) as total FROM topics GROUP BY site_id HAVING avail < 10 ORDER BY avail;"

# STAP (source별 잔량 = collected_data - publish_log)
sqlite3 /Users/twinssn/Projects/STAP/data/stap.db \
  "SELECT source, COUNT(*) as total FROM collected_data GROUP BY source LIMIT 5;"
# 실제 가용은 get_unused_data() 로직 기준 — health check는 publish_log 대조

# RAP
sqlite3 /Users/twinssn/Projects/5000/data/rap.db \
  "SELECT blog_target, SUM(CASE WHEN status='active' THEN 1 ELSE 0 END) as avail, COUNT(*) as total FROM keywords GROUP BY blog_target HAVING avail < 10 ORDER BY avail;"

# CUAP (published_products 기반)
sqlite3 /Users/twinssn/Projects/5000/data/curation.db \
  "SELECT blog_id, COUNT(*) as published FROM published_products GROUP BY blog_id LIMIT 5;"
```

### 3.2 자동 감지 (§5 체크)
ops_dashboard/checks/topic_pool_health.py
- 임계값: <10건 WARNING, 0건 CRITICAL
- 주기: 매일 06:00 (harvest 후)
- 현재: 수동 실행 `.venv/bin/python ops_dashboard/checks/topic_pool_health.py`

## 4. 대응 절차

### 4.1 긴급 (0건 — 발행 중단됨)
1. 영향 범위 확인: 해당 블로그 마지막 발행일 확인
2. Option B 실행 (리셋): 가장 오래된 exhausted 토픽 200건 리셋
```sql
sqlite3 <DB_PATH> "UPDATE <table> SET exhausted=0 WHERE rowid IN (SELECT rowid FROM <table> WHERE exhausted=1 ORDER BY rowid ASC LIMIT 200);"
-- 예: sqlite3 /Users/twinssn/Projects/5000/data/travel-en.db "UPDATE watersports_topics SET exhausted=0 WHERE rowid IN (SELECT rowid FROM watersports_topics WHERE exhausted=1 ORDER BY rowid ASC LIMIT 200);"
```
3. scheduler 재시도 대기 (다음 스케줄) 또는 수동 trigger `python dispatcher.py <blog-id>`
4. 콘텐츠 중복 모니터링: 리셋된 토픽이 이전 발행과 동일 제목 생성 여부 확인

### 4.2 경고 (<10건 — 곧 고갈)
- Option A 실행 (expander): 해당 분기 expander 수동 실행
```bash
.venv/bin/python -m pipelines.curation.keyword_expander <blog-id>
```
- 생성량 확인 후 10건 이상이면 정상 복귀
- expander 미존재 분기: Option C (LLM 시드) 또는 수동 키워드 추가

### 4.3 예방 (>10건이지만 소비율 높음)
- 일일 소비량 계산: `grep -c "<blog>" logs/scheduler.log | 최근 7일 평균`
- 잔여일수 = 잔여토픽 / 일일소비
- 잔여일수 < 14일이면 §4.2 실행

## 5. DB 스키마 참조

| 분기 | DB 경로 | 테이블 | 미사용 조건 |
|------|---------|--------|-------------|
| ETAP | Projects/5000/data/travel-en.db | {blog}_topics (예: watersports_topics) | exhausted=0 |
| CAP | Projects/5000/data/car.db | topics | status!='exhausted' (status='pending') |
| STAP | Projects/STAP/data/stap.db | collected_data (+ publish_log 대조) | used=0 (get_unused_data 기준) |
| RAP | Projects/5000/data/rap.db | keywords | status='active' |
| CUAP | Projects/5000/data/curation.db | published_products / products | keyword_pool 아님, 발행 이력 대조 |

## 6. 영구 해결 (topic-pool-sustainability.md 참조)
- A) keyword_expander 전 분기 확대 (우선순위 1)
- B) 외부 API 수집 (네이버/Google Trends)
- C) LLM 시드 생성 → expander 연결

## 7. 이력

| 날짜 | 블로그 | 조치 | 결과 |
|------|--------|------|------|
| 2026-08-24 | watersports | 200건 리셋 | 209 avail, 100일 지속 (210 total) |
| 2026-08-24 | airports | 200건 리셋 | 251 avail (9324 total, 2.7%) |
| 2026-08-24 | nature | 50건 리셋 | 50 avail |
| 2026-08-24 | CAP ev | 50건 수동 INSERT | 50 avail (415 total) |

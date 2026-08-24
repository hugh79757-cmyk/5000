# MAN-003 deals/nature topics exhausted

## 증상
- `check_results` R13 또는 `publish_error_events` P01 `no_result`
- scheduler.log `CATCHUP ... no_result` 연속, `SELECT COUNT(*) FROM watersports_topics WHERE used=0` =0 (그러나 실제 테이블은 `status` 컬럼)
- 182+179 topics 전체 `exhausted=1` (이번 케이스)

## 진단
```bash
sqlite3 data/curation.db "SELECT name FROM sqlite_master WHERE name LIKE '%topic%';"
# 실제 위치: data/etap.db, data/travel-en.db 등 — find로 확인
for db in data/*.db; do echo "==$db"; sqlite3 "$db" "SELECT sql FROM sqlite_master WHERE type='table' AND name LIKE '%topic%';" 2>&1 | head -5; done
sqlite3 data/etap.db "SELECT COUNT(*) FROM deals_topics WHERE exhausted=0;" 2>&1 | head -5
```

## 조치 (내가 할 수 있는 것)
1. exhausted 플래그 해제 (재사용):
```bash
sqlite3 data/etap.db "UPDATE deals_topics SET exhausted=0 WHERE exhausted=1 LIMIT 50;"
```
2. 신규 토픽 주입 (외부 소스):
   - `pipelines/etap/collectors/topic_expander.py:162 watersports: {...}` 패턴으로 신규 크롤
   - `python -m pipelines.etap.topic_expander --blog deals-hugo --count 50`
3. harvester 보강: `shared/harvester`에 deals/nature 소스 추가 (Naver Datalab)

## 조치 (네가 해야 하는 것)
- 토픽 소스 승인: deals/nature는 외부 공공데이터가 제한적 — 수동으로 50개 주제 리스트 제공하면 내가 일괄 INSERT
- 빈도 결정: 주 1회 `UPDATE exhausted=0` 재순환 vs 월 1회 신규 주입 중 선택

## 검증
```bash
sqlite3 data/etap.db "SELECT COUNT(*) FROM deals_topics WHERE exhausted=0;"
hugo --gc --minify --source /Users/twinssn/Projects/ETAP/deals-hugo --themesDir /Users/twinssn/Projects/shared-themes 2>&1 | tail -3
```

## 영구 방지
- `check_results` R13 -> `content_freshness`와 연동, exhausted 10개 이하 시 Telegram alert
- `keyword_pool`과 동일한 `exhausted` 재사용 큐로 전환, `cron 02:00` 자동 `UPDATE ... LIMIT 50` — 코드 5줄이면 영구

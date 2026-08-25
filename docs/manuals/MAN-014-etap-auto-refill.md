# MAN-014 ETAP 토픽 고갈 자동 보충

## 조건
- 대상: deals / airlines / airports / nature / watersports
- 트리거: `exhausted=0` 잔여 토픽 수(`avail`) < 20

## 자동 조치
- 스케줄러: 매일 01:00 `_run_etap_expander()` 실행 (`scheduler.py:1422`)
- 동작: 5개 블로그 각각 `pipelines/etap/topic_expander.py {blog} --count 50 --execute`
- 순서: deals → airlines → airports → nature → watersports
- 타임아웃: 블로그당 300s, 실패 시 warning 로그 후 다음 블로그 계속

## 임계값
- `avail < 20` → WARNING (보충 예약)
- `avail == 0` → CRITICAL + 즉시 보충 (수동 `topic_expander.py --execute` 권장)
- 정상: `avail ≥ 50` 유지 권장

## 에스컬레이션
- 3일 연속 보충 후에도 `avail < 20` 지속 → 소스 확장 검토 (human)
  - synthetic 생성 로직 또는 외부 API 소스 추가 필요
  - `pipelines/etap/topic_expander.py` 생성기 확장 또는 `collectors/` 추가

## 검증
```bash
sqlite3 data/travel-en.db "SELECT 'deals', COUNT(*) FROM deals_topics WHERE exhausted=0 UNION ALL SELECT 'airports', COUNT(*) FROM airports_topics WHERE exhausted=0 UNION ALL SELECT 'nature', COUNT(*) FROM nature_topics WHERE exhausted=0 UNION ALL SELECT 'watersports', COUNT(*) FROM watersports_topics WHERE exhausted=0 UNION ALL SELECT 'airlines', COUNT(*) FROM airlines_topics WHERE exhausted=0;"
PYTHONPATH=/Users/twinssn/projects/5000 python3 ops_dashboard/checks/run_all_checks.py | grep PIPELINE
```

## 이력
- 2026-08-25 deals 184→330 (+146), airports 451→651 (+200), nature 97→197 (+100), watersports 204→304 (+100)

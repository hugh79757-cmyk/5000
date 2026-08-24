# MAN-002 sector-hugo API 키

## 영향
- STAP sector-hugo는 DART_API_KEY, DATA_GO_KR_API_KEY, FINLIFE_API_KEY 사용
- 위치: /Users/twinssn/Projects/STAP/pipelines/common_fetcher.py:17-25, STAP/.env.template

## 증상
- scheduler.log에 `sector 401/403/429` 또는 `DART 429 quota` 또는 `DATA_GO_KR invalid key`
- harvest 0건, R13/R17 게이트 연속

## 진단
```bash
grep -i "sector\|DART\|DATA_GO_KR" /Users/twinssn/Projects/5000/logs/scheduler.log | tail -20
grep -rn "DART_API_KEY\|DATA_GO_KR" /Users/twinssn/Projects/STAP --include="*.py" | head -10
cat ~/.env.common | grep -E "DART_API_KEY|DATA_GO_KR_API_KEY" | sed 's/=.*/=***/' 
```

## 조치 (내가 할 수 있는 것)
1. 키 존재 확인: `grep DART_API_KEY ~/.env.common` 없으면 템플릿 복사
2. 키 만료/쿼터 확인: `curl -s "https://apis.data.go.kr/..." | head` 로 200 확인
3. 캐시/재시도: `STAP/pipelines/common_fetcher.py`는 RateLimiter 내장, 키 교체 후 `nohup` 재시도

## 조치 (네가 해야 하는 것)
- 키 발급/갱신이 필요하면 아래 3곳에서 발급 후 `~/.env.common`에 추가:
  - DART: https://opendart.fss.or.kr (OpenDart 신청, 승인 1일)
  - DATA_GO_KR: https://www.data.go.kr (공공데이터포털, 활용신청)
  - FINLIFE: 금융감독원 FinLife
- 갱신 후: `grep DART_API_KEY ~/.env.common` 확인 → `launchctl unload/load com.5000.scheduler.plist` 또는 `pgrep` 재기동
- 키 값은 절대 git에 커밋 금지, `.env`는 gitignore

## 검증
```bash
python3 -c "import os; print('DART' if os.getenv('DART_API_KEY') else 'missing')"
sqlite3 ops_dashboard/ops.db "SELECT blog_id, standard_compliance FROM blog_lifecycle WHERE blog_id='sector-hugo'"
```

## 영구 방지
- 키 만료 30일 전 알림: `shared/publish_error_events`에 P01 quota 이벤트 → Telegram alert
- 키는 `~/.env.common` 단일 소스, `STAP/.env`는 템플릿만, 코드 수정 불필요

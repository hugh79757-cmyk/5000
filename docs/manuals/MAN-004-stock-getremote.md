# MAN-004 stock-hugo GetRemote SKIP

## 증상
- `ops_dashboard/ops.db` check_results `stock-hugo` 비정상 또는 scheduler.log `stock-hugo ... GetRemote ... SKIP`
- 빌드 시 `getJSON` / `GetRemote` 외부 API 호출 실패 -> Hugo 빌드 스킵

## 진단
```bash
grep -ri "GetRemote\|getJSON\|stock.*SKIP" /Users/twinssn/Projects/5000/logs/scheduler.log | tail -20
grep -rn "GetRemote\|getJSON" /Users/twinssn/Projects/STAP --include="*.html" --include="*.toml" | head -20
sqlite3 ops_dashboard/ops.db "SELECT blog_id, check_name, status, detail FROM check_results WHERE blog_id='stock-hugo' ORDER BY checked_at DESC LIMIT 10"
hugo --gc --minify --source /Users/twinssn/Projects/STAP/stock-hugo --themesDir /Users/twinssn/Projects/shared-themes 2>&1 | tail -20
```

## 조치 (내가 할 수 있는 것)
1. 빌드 캐시 클리어 + 재빌드:
```bash
rm -rf /Users/twinssn/Projects/STAP/stock-hugo/public /Users/twinssn/Projects/STAP/stock-hugo/resources
HUGO_THEMESDIR=/Users/twinssn/Projects/shared-themes hugo --gc --minify --source /Users/twinssn/Projects/STAP/stock-hugo 2>&1 | tail -20
```
2. GetRemote fallback: `layouts/partials`에서 `try` / `with resources.GetRemote` -> `else` 로 fallback 이미지/더미 데이터 바인딩
3. 오프라인 모드: `hugo.toml`에 `ignoreErrors = [\"error-remote-getjson\"]` 추가 검토 (빌드는 통과시키되 데이터는 stale)

## 조치 (네가 해야 하는 것)
- 외부 API (한국거래소 / 네이버 금융) 차단 여부 확인: `curl -I https://api...` 직접 호출
- API 키 갱신 필요 시 MAN-002 동일 절차로 `~/.env.common` 갱신 후 scheduler 재기동
- GetRemote 영구 실패 시 기능 제거 결정: stock-hugo에서 실시간 시세 위젯 제거 vs 유지

## 검증
```bash
HUGO_THEMESDIR=/Users/twinssn/Projects/shared-themes hugo --gc --minify --source /Users/twinssn/Projects/STAP/stock-hugo 2>&1 | grep -i "error\|built"
sqlite3 ops_dashboard/ops.db "SELECT status FROM check_results WHERE blog_id='stock-hugo' AND check_name='standard_compliance'"
```

## 영구 방지
- `resources.GetRemote`에 `timeout + retry` 래퍼 추가 (Hugo 0.122+ `try` 지원)
- 외부 API 장애 시 `default` 데이터로 빌드 통과, Telegram에 `STOCK_GETREMOTE_FAIL` 알림만 발송 (빌드 차단 방지)
- 주간 `hugo --gc` 크론에서 GetRemote 실패 카운트 -> 3회 연속 시 자동 `ignoreErrors` 토글 (코드 10줄)

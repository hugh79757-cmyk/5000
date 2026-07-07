#!/bin/bash
# Analytics daily collection (GA4 + GSC + AdSense + Efficiency)
# Runs every 6 hours via launchd
# Fallback: 각 수집기가 실패해도 나머지는 계속 실행

cd /Users/twinssn/Projects/5000
LOG_FILE="/Users/twinssn/Projects/5000/logs/analytics_collect.log"
TS=$(date '+%Y-%m-%d %H:%M:%S')

echo "[$TS] === Analytics 수집 시작 ===" >> "$LOG_FILE"

# GA4
echo "[$TS] GA4 수집..." >> "$LOG_FILE"
/opt/homebrew/bin/python3 -c "
from shared.analytics_collector import AnalyticsCollector
c = AnalyticsCollector()
r = c.collect_ga4(days=3)
print(f'GA4={r.get(\"rows\",0)}r PV={r.get(\"total_pv\",0)} err={len(r.get(\"errors\",[]))}')
" >> "$LOG_FILE" 2>&1 || echo "[$TS] ⚠️ GA4 실패 (계속)" >> "$LOG_FILE"

# GSC
echo "[$TS] GSC 수집..." >> "$LOG_FILE"
/opt/homebrew/bin/python3 -c "
from shared.analytics_collector import AnalyticsCollector
c = AnalyticsCollector()
r = c.collect_gsc(days=1)
print(f'GSC={r.get(\"sites\",0)}s clicks={r.get(\"clicks\",0)} err={len(r.get(\"errors\",[]))}')
" >> "$LOG_FILE" 2>&1 || echo "[$TS] ⚠️ GSC 실패 (계속)" >> "$LOG_FILE"

# AdSense (3개 계정)
echo "[$TS] AdSense 수집..." >> "$LOG_FILE"
/opt/homebrew/bin/python3 -c "
from shared.analytics_collector import AnalyticsCollector
c = AnalyticsCollector()
r = c.collect_adsense(days=3)
print(f'AdSense={r.get(\"rows\",0)}r \${r.get(\"total_earnings\",0)} err={len(r.get(\"errors\",[]))}')
" >> "$LOG_FILE" 2>&1 || echo "[$TS] ⚠️ AdSense 실패 (계속)" >> "$LOG_FILE"

# Efficiency
echo "[$TS] 효율성 계산..." >> "$LOG_FILE"
/opt/homebrew/bin/python3 -c "
from shared.analytics_collector import AnalyticsCollector
c = AnalyticsCollector()
r = c.compute_efficiency()
print(f'Efficiency={r.get(\"blog_count\",0)}b')
" >> "$LOG_FILE" 2>&1 || echo "[$TS] ⚠️ Efficiency 실패 (계속)" >> "$LOG_FILE"

echo "[$TS] === Analytics 수집 완료 ===" >> "$LOG_FILE"

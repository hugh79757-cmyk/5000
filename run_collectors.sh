#!/bin/bash
cd /Users/twinssn/Projects/5000
source .venv/bin/activate

LOG="logs/collector_$(date +%Y%m%d_%H%M).log"
echo "=== 수집 시작: $(date) ===" >> "$LOG"

python3 analytics/gsc_collector.py >> "$LOG" 2>&1
python3 analytics/adsense_collector.py 7 >> "$LOG" 2>&1
python3 analytics/ga4_collector.py >> "$LOG" 2>&1
python3 analytics/bing_collector.py >> "$LOG" 2>&1
python3 analytics/efficiency_scorer.py >> "$LOG" 2>&1

echo "=== 수집 완료: $(date) ===" >> "$LOG"

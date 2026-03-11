#!/bin/bash
cd /Users/twinssn/Projects/5000
source /Users/twinssn/Projects/5000/.venv/bin/activate
exec python3 /Users/twinssn/Projects/5000/scheduler.py >> /Users/twinssn/Projects/5000/logs/scheduler.log 2>&1

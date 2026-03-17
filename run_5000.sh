#!/bin/bash
cd /Users/twinssn/Projects/5000
export PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH
source /Users/twinssn/Projects/5000/.venv/bin/activate
exec python3 /Users/twinssn/Projects/5000/scheduler.py >> /Users/twinssn/Projects/5000/logs/scheduler.log 2>&1

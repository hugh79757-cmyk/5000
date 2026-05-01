#!/bin/bash
cd /Users/twinssn/Projects/5000
export PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH
source /Users/twinssn/Projects/5000/.venv/bin/activate
find /Users/twinssn/Projects/5000/shared/__pycache__ -name "publisher*.pyc" -delete 2>/dev/null || true
exec /Users/twinssn/Projects/5000/.venv/bin/python3 /Users/twinssn/Projects/5000/scheduler.py >> /Users/twinssn/Projects/5000/logs/scheduler.log 2>&1

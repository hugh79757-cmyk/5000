#!/usr/bin/env bash
cd /Users/twinssn/projects/5000
sep() { echo; echo "========== $1 =========="; echo; }
sep "curation/writer.py (500-570: fallback 구간)"; sed -n '240,270p;520,575p' pipelines/curation/writer.py
sep "curation/pipeline.py 전체"; cat pipelines/curation/pipeline.py
sep "curation/keywords.py (validate_keyword 존재 여부)"; grep -n "def validate_keyword" pipelines/curation/keywords.py || echo ">>> validate_keyword 없음 (Phase 12 버그 확인)"
sep "post_validator.py 헤더"; sed -n '1,60p' shared/post_validator.py
